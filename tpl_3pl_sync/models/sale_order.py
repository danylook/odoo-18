# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()
        cfg = self.env['tpl.sync.config'].get_active()
        if cfg and cfg.enabled_sale_confirm:
            for order in self:
                try:
                    self._sync_create_backend_pickings(order, cfg)
                except Exception as e:
                    _logger.error(
                        '3PL Sync: sale confirm sync failed for %s: %s',
                        order.name, e)
                    order.message_post(
                        body='⚠️ 3PL Sync: failed to create backend pickings: %s' % e)
        return res

    def _sync_get_or_create_backend_partner(self, partner, cfg):
        """Find or create a partner on the backend matching the client partner."""
        if not partner or not partner.name:
            return False
        domain = [['name', '=', partner.name]]
        if partner.email:
            domain = ['|', ['email', '=', partner.email]] + domain
        existing = cfg._backend_call(
            'res.partner', 'search_read',
            [domain],
            {'fields': ['id'], 'limit': 1})
        if existing:
            return existing[0]['id']
        vals = {'name': partner.name, 'customer_rank': 1}
        for fld in ('street', 'street2', 'city', 'zip', 'phone', 'email'):
            val = getattr(partner, fld, False)
            if val:
                vals[fld] = val
        if partner.country_id:
            countries = cfg._backend_call(
                'res.country', 'search_read',
                [[['code', '=', partner.country_id.code]]],
                {'fields': ['id'], 'limit': 1})
            if countries:
                vals['country_id'] = countries[0]['id']
        new_id = cfg._backend_call('res.partner', 'create', [vals])
        _logger.info('3PL Sync: created backend partner id=%s name=%s',
                     new_id, partner.name)
        return new_id

    def _sync_create_backend_pickings(self, order, cfg):
        """
        After sale confirm, create WH/PICK + WH/PACK + WH/OUT on the backend
        with proper move chaining (move_orig_ids / move_dest_ids).

        Chaining prevents Odoo's push rules from creating duplicate moves.

        Chain:  WH/PICK (ready) → WH/PACK (waiting) → WH/OUT (waiting)

        The 3PL operator does all warehouse work on the backend.
        tpl_3pl_back_sync reflects each validation back to the client:
          WH/PICK done → ECO/PICK validated
          WH/PACK done → ECO/PACK validated
          WH/OUT  done → ECO/OUT  validated
        """
        from .tpl_sync_config import BACKEND_LOCATIONS, BACKEND_PICKING_TYPES

        # ── resolve backend products ──────────────────────────────────────
        lines = []
        for line in order.order_line:
            code = line.product_id.default_code
            if not code:
                continue
            bprods = cfg._backend_call(
                'product.product', 'search_read',
                [[['default_code', '=', code]]],
                {'fields': ['id', 'uom_id'], 'limit': 1})
            if not bprods:
                _logger.warning(
                    '3PL Sync sale confirm: product %s not in backend', code)
                continue
            bp = bprods[0]
            lines.append({
                'name': line.product_id.name,
                'product_id': bp['id'],
                'uom_id': bp['uom_id'][0],
                'qty': line.product_uom_qty,
            })

        if not lines:
            _logger.warning(
                '3PL Sync sale confirm: no mappable products in %s', order.name)
            return

        # ── procurement group (one per SO) ────────────────────────────────
        group_id = cfg._backend_call(
            'procurement.group', 'create', [{'name': order.name}])

        def _move_vals(loc_from, loc_to, procure='make_to_stock', orig_ids=None):
            mvs = []
            for l in lines:
                mv = {
                    'name': l['name'],
                    'product_id': l['product_id'],
                    'product_uom_qty': l['qty'],
                    'product_uom': l['uom_id'],
                    'location_id': loc_from,
                    'location_dest_id': loc_to,
                    'restrict_partner_id': cfg.backend_owner_id,
                    'procure_method': procure,
                }
                mvs.append((0, 0, mv))
            return mvs

        # ── Step 1: WH/PICK — Stock → Packing Zone ───────────────────────
        pick_id = cfg._backend_call('stock.picking', 'create', [{
            'picking_type_id': BACKEND_PICKING_TYPES['pick'],
            'location_id': BACKEND_LOCATIONS['stock'],
            'location_dest_id': BACKEND_LOCATIONS['packing'],
            'origin': order.name,
            'group_id': group_id,
            'move_ids': _move_vals(
                BACKEND_LOCATIONS['stock'],
                BACKEND_LOCATIONS['packing'],
                procure='make_to_stock'),
        }])
        pick_move_ids = [m['id'] for m in cfg._backend_call(
            'stock.move', 'search_read',
            [[['picking_id', '=', pick_id]]],
            {'fields': ['id']})]

        # ── Step 2: WH/PACK — Packing Zone → Output ──────────────────────
        # make_to_order so it waits for PICK; move_orig_ids links to PICK moves
        pack_move_data = []
        for i, l in enumerate(lines):
            mv = {
                'name': l['name'],
                'product_id': l['product_id'],
                'product_uom_qty': l['qty'],
                'product_uom': l['uom_id'],
                'location_id': BACKEND_LOCATIONS['packing'],
                'location_dest_id': BACKEND_LOCATIONS['output'],
                'restrict_partner_id': cfg.backend_owner_id,
                'procure_method': 'make_to_order',
            }
            if i < len(pick_move_ids):
                mv['move_orig_ids'] = [(4, pick_move_ids[i])]
            pack_move_data.append((0, 0, mv))

        pack_id = cfg._backend_call('stock.picking', 'create', [{
            'picking_type_id': BACKEND_PICKING_TYPES['pack'],
            'location_id': BACKEND_LOCATIONS['packing'],
            'location_dest_id': BACKEND_LOCATIONS['output'],
            'origin': order.name,
            'group_id': group_id,
            'move_ids': pack_move_data,
        }])
        pack_move_ids = [m['id'] for m in cfg._backend_call(
            'stock.move', 'search_read',
            [[['picking_id', '=', pack_id]]],
            {'fields': ['id']})]

        # Back-link: PICK moves → PACK moves (prevents push rule duplication)
        for i, pm_id in enumerate(pick_move_ids):
            if i < len(pack_move_ids):
                cfg._backend_call('stock.move', 'write',
                                  [[pm_id], {'move_dest_ids': [(4, pack_move_ids[i])]}])

        # ── Step 3: WH/OUT — Output → Customer ───────────────────────────
        # make_to_order, linked to PACK moves
        out_move_data = []
        for i, l in enumerate(lines):
            mv = {
                'name': l['name'],
                'product_id': l['product_id'],
                'product_uom_qty': l['qty'],
                'product_uom': l['uom_id'],
                'location_id': BACKEND_LOCATIONS['output'],
                'location_dest_id': BACKEND_LOCATIONS['customer'],
                'restrict_partner_id': cfg.backend_owner_id,
                'procure_method': 'make_to_order',
            }
            if i < len(pack_move_ids):
                mv['move_orig_ids'] = [(4, pack_move_ids[i])]
            out_move_data.append((0, 0, mv))

        shipping = order.partner_shipping_id
        backend_partner_id = self._sync_get_or_create_backend_partner(
            shipping, cfg)

        def _addr_line(p):
            parts = [p.name]
            for attr in ('street', 'street2'):
                val = getattr(p, attr, False)
                if val:
                    parts.append(val)
            city = ' '.join(filter(None, [
                getattr(p, 'zip', '') or '',
                getattr(p, 'city', '') or '',
            ])).strip()
            if city:
                parts.append(city)
            if p.country_id:
                parts.append(p.country_id.name)
            if getattr(p, 'phone', False):
                parts.append('Tel: %s' % p.phone)
            if getattr(p, 'email', False):
                parts.append('Email: %s' % p.email)
            return '\n'.join(parts)

        delivery_note = 'Client: %s\nSO: %s\nDeliver to:\n%s' % (
            order.partner_id.name, order.name, _addr_line(shipping))
        if order.client_order_ref:
            delivery_note = 'Ref: %s\n%s' % (order.client_order_ref, delivery_note)

        out_vals = {
            'picking_type_id': BACKEND_PICKING_TYPES['out'],
            'location_id': BACKEND_LOCATIONS['output'],
            'location_dest_id': BACKEND_LOCATIONS['customer'],
            'origin': order.name,
            'group_id': group_id,
            'move_ids': out_move_data,
            'note': delivery_note,
        }
        if backend_partner_id:
            out_vals['partner_id'] = backend_partner_id

        out_id = cfg._backend_call('stock.picking', 'create', [out_vals])
        out_move_ids = [m['id'] for m in cfg._backend_call(
            'stock.move', 'search_read',
            [[['picking_id', '=', out_id]]],
            {'fields': ['id']})]

        # Back-link: PACK moves → OUT moves (prevents push rule duplication)
        for i, pm_id in enumerate(pack_move_ids):
            if i < len(out_move_ids):
                cfg._backend_call('stock.move', 'write',
                                  [[pm_id], {'move_dest_ids': [(4, out_move_ids[i])]}])

        # ── Step 4: confirm pickings ──────────────────────────────────────
        # PICK: confirm + assign (ready to pick)
        cfg._backend_call('stock.picking', 'action_confirm', [[pick_id]])
        cfg._backend_call('stock.picking', 'action_assign', [[pick_id]])
        # PACK: confirm (will be 'waiting' until PICK done)
        cfg._backend_call('stock.picking', 'action_confirm', [[pack_id]])
        # OUT: confirm (will be 'waiting' until PACK done)
        cfg._backend_call('stock.picking', 'action_confirm', [[out_id]])

        _logger.info(
            '3PL Sync: created WH/PICK=%s WH/PACK=%s WH/OUT=%s for %s',
            pick_id, pack_id, out_id, order.name)
        order.message_post(
            body='3PL Sync: WH/PICK id=%s, WH/PACK id=%s, WH/OUT id=%s '
                 'created in backend for %s. Deliver to: %s' % (
                     pick_id, pack_id, out_id, order.name, shipping.name))
