# -*- coding: utf-8 -*-
"""
tpl_3pl_sync — stock.picking override
Client-side forward sync (ECO/IN→WH/IN, ECO/PICK→WH/PICK, etc.) plus
backend-driven guard for outgoing steps.
"""
import logging
from odoo import models
_logger = logging.getLogger(__name__)


def _qty_done_mls(picking):
    result = []
    for ml in picking.move_line_ids:
        code = ml.product_id.default_code
        if code:
            result.append((code, ml.quantity))
    return result


def _find_backend_picking(cfg, origin, picking_type_id):
    ids = cfg._backend_call('stock.picking', 'search',
        [[['origin', '=', origin],
          ['picking_type_id', '=', picking_type_id],
          ['state', 'not in', ['done', 'cancel']]]],
        {'limit': 1})
    return ids[0] if ids else None


def _find_backend_pack(cfg, origin, pick_type_id, pack_type_id):
    pick_data = cfg._backend_call(
        'stock.picking', 'search_read',
        [[['origin', '=', origin],
          ['picking_type_id', '=', pick_type_id],
          ['state', '=', 'done']]],
        {'fields': ['name'], 'order': 'id desc', 'limit': 1})
    if not pick_data:
        return None, None
    pick_name = pick_data[0]['name']
    pack_ids = cfg._backend_call(
        'stock.picking', 'search',
        [[['origin', '=', pick_name],
          ['picking_type_id', '=', pack_type_id],
          ['state', 'not in', ['done', 'cancel']]]],
        {'limit': 1})
    return (pack_ids[0] if pack_ids else None), pick_name


def _validate_backend_picking(cfg, picking_id, product_qtys):
    mls = cfg._backend_call(
        'stock.move.line', 'search_read',
        [[['picking_id', '=', picking_id]]],
        {'fields': ['id', 'product_id']})
    qty_map = {}
    for code, qty in product_qtys:
        qty_map[code] = qty_map.get(code, 0) + qty
    for ml in mls:
        prod_id = ml['product_id'][0]
        prods = cfg._backend_call(
            'product.product', 'read', [[prod_id]],
            {'fields': ['default_code']})
        code = prods[0]['default_code'] if prods else None
        qty = qty_map.get(code, 0) if code else 0
        if qty:
            cfg._backend_call('stock.move.line', 'write',
                               [[ml['id']], {'quantity': qty}])
    cfg._backend_call('stock.picking', 'button_validate', [[picking_id]])


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        not_yet_done = self.filtered(lambda p: p.state != 'done')
        res = super().button_validate()
        cfg = self.env['tpl.sync.config'].get_active()
        if not cfg:
            return res
        for picking in not_yet_done:
            if picking.state != 'done':
                continue
            try:
                self._sync_picking_step(picking, cfg)
            except Exception as e:
                _logger.error(
                    '3PL Sync: picking sync failed for %s: %s',
                    picking.name, e)
                picking.message_post(body='⚠️ 3PL Sync error: %s' % e)
        return res

    def _sync_picking_step(self, picking, cfg):
        from .tpl_sync_config import BACKEND_PICKING_TYPES, BACKEND_LOCATIONS
        ptype = picking.picking_type_id
        code = ptype.code
        type_name = (ptype.name or '').upper()
        if code == 'incoming' and cfg.enabled_in:
            self._sync_in(picking, cfg, BACKEND_PICKING_TYPES, BACKEND_LOCATIONS)
        elif code == 'internal' and 'PICK' in type_name and cfg.enabled_pick:
            self._sync_pick(picking, cfg, BACKEND_PICKING_TYPES, BACKEND_LOCATIONS)
        elif code == 'internal' and 'PACK' in type_name and cfg.enabled_pack:
            self._sync_pack(picking, cfg, BACKEND_PICKING_TYPES)
        elif code == 'outgoing' and cfg.enabled_out:
            self._sync_out(picking, cfg, BACKEND_PICKING_TYPES)

    # ── IN step ─────────────────────────────────────────────────────

    def _sync_in(self, picking, cfg, PTYPES, LOCS):
        """
        When the client validates ECO/IN (incoming receipt):
        1. If a WH/IN already exists on the backend for the same origin
           (backend-driven: backend operator received goods first), skip —
           back-sync will validate ECO/IN when WH/IN is done.
        2. Otherwise create + validate WH/IN on the backend so backend
           stock reflects the receipt.
        Origin is the purchase order name (P00XXX).
        """
        origin = self._get_purchase_origin(picking)
        if not origin:
            _logger.warning(
                '3PL Sync IN: no purchase origin on %s', picking.name)
            return

        product_qtys = _qty_done_mls(picking)
        if not product_qtys:
            return

        # Backend-driven guard: if WH/IN already exists, backend operator
        # handles it and back-sync will validate ECO/IN.
        existing = cfg._backend_call(
            'stock.picking', 'search',
            [[['origin', '=', origin],
              ['picking_type_id', '=', PTYPES['in']],
              ['state', 'not in', ['cancel']]]],
            {'limit': 1})
        if existing:
            picking.message_post(
                body='3PL Sync: WH/IN already exists in backend for %s — '
                     'backend-driven mode, skipped.' % origin)
            return

        # Build move vals
        move_vals = []
        for code, qty in product_qtys:
            bprods = cfg._backend_call(
                'product.product', 'search_read',
                [[['default_code', '=', code]]],
                {'fields': ['id', 'uom_id'], 'limit': 1})
            if not bprods:
                continue
            bp = bprods[0]
            move_vals.append((0, 0, {
                'name': code,
                'product_id': bp['id'],
                'product_uom_qty': qty,
                'product_uom': bp['uom_id'][0],
                'location_id': LOCS['vendor'],
                'location_dest_id': LOCS['input'],
                'restrict_partner_id': cfg.backend_owner_id,
            }))

        if not move_vals:
            return

        in_id = cfg._backend_call('stock.picking', 'create', [{
            'picking_type_id': PTYPES['in'],
            'location_id': LOCS['vendor'],
            'location_dest_id': LOCS['input'],
            'origin': origin,
            'move_ids': move_vals,
        }])

        cfg._backend_call('stock.picking', 'action_confirm', [[in_id]])
        cfg._backend_call('stock.picking', 'action_assign', [[in_id]])

        # Set quantity on move lines
        mls = cfg._backend_call(
            'stock.move.line', 'search_read',
            [[['picking_id', '=', in_id]]],
            {'fields': ['id', 'product_id', 'quantity']})
        qty_map = dict(product_qtys)
        for ml in mls:
            prods = cfg._backend_call(
                'product.product', 'read',
                [[ml['product_id'][0]]], {'fields': ['default_code']})
            ml_code = prods[0]['default_code'] if prods else None
            qty = qty_map.get(ml_code, ml.get('quantity', 0))
            cfg._backend_call('stock.move.line', 'write',
                               [[ml['id']], {'quantity': qty}])

        cfg._backend_call('stock.picking', 'button_validate', [[in_id]])
        _logger.info(
            '3PL Sync IN: created+validated backend WH/IN id=%s for %s',
            in_id, origin)
        picking.message_post(
            body='3PL Sync: WH/IN id=%s created and validated in backend.' % in_id)

    # ── PICK step ───────────────────────────────────────────────────

    def _sync_pick(self, picking, cfg, PTYPES, LOCS):
        origin = self._get_sale_origin(picking)
        if not origin:
            return

        # Backend-driven mode guard
        existing_any = cfg._backend_call(
            'stock.picking', 'search',
            [[['origin', '=', origin],
              ['picking_type_id', '=', PTYPES['pick']],
              ['state', 'not in', ['cancel']]]],
            {'limit': 1})
        if existing_any:
            picking.message_post(
                body='3PL Sync: WH/PICK already exists in backend — '
                     'backend-driven mode, skipped.')
            return

        product_qtys = _qty_done_mls(picking)
        if not product_qtys:
            return
        move_vals = []
        for code, qty in product_qtys:
            bprods = cfg._backend_call(
                'product.product', 'search_read',
                [[['default_code', '=', code]]],
                {'fields': ['id', 'uom_id'], 'limit': 1})
            if not bprods:
                continue
            bp = bprods[0]
            move_vals.append((0, 0, {
                'name': code,
                'product_id': bp['id'],
                'product_uom_qty': qty,
                'product_uom': bp['uom_id'][0],
                'location_id': LOCS['stock'],
                'location_dest_id': LOCS['packing'],
                'restrict_partner_id': cfg.backend_owner_id,
            }))
        if not move_vals:
            return
        groups = cfg._backend_call(
            'procurement.group', 'search_read',
            [[['name', '=', origin]]],
            {'fields': ['id'], 'limit': 1})
        group_id = groups[0]['id'] if groups else False
        pick_id = cfg._backend_call('stock.picking', 'create', [{
            'picking_type_id': PTYPES['pick'],
            'location_id': LOCS['stock'],
            'location_dest_id': LOCS['packing'],
            'origin': origin,
            'group_id': group_id,
            'move_ids': move_vals,
        }])
        cfg._backend_call('stock.picking', 'action_confirm', [[pick_id]])
        cfg._backend_call('stock.picking', 'action_assign', [[pick_id]])
        mls = cfg._backend_call(
            'stock.move.line', 'search_read',
            [[['picking_id', '=', pick_id]]],
            {'fields': ['id', 'product_id', 'quantity']})
        qty_map = dict(product_qtys)
        for ml in mls:
            prods = cfg._backend_call(
                'product.product', 'read',
                [[ml['product_id'][0]]], {'fields': ['default_code']})
            ml_code = prods[0]['default_code'] if prods else None
            qty = qty_map.get(ml_code, ml.get('quantity', 0))
            cfg._backend_call('stock.move.line', 'write',
                               [[ml['id']], {'quantity': qty}])
        cfg._backend_call('stock.picking', 'button_validate', [[pick_id]])
        picking.message_post(
            body='3PL Sync: WH/PICK id=%s created and validated in backend.' % pick_id)

    # ── PACK step ───────────────────────────────────────────────────

    def _sync_pack(self, picking, cfg, PTYPES):
        origin = self._get_sale_origin(picking)
        if not origin:
            return
        product_qtys = _qty_done_mls(picking)
        pack_id, pick_name = _find_backend_pack(
            cfg, origin, PTYPES['pick'], PTYPES['pack'])
        if not pack_id:
            picking.message_post(
                body='3PL Sync: WH/PACK not found in backend for %s '
                     '(backend-driven mode).' % origin)
            return
        _validate_backend_picking(cfg, pack_id, product_qtys)
        self._fix_backend_out_moves(origin, pick_name, cfg, PTYPES)
        picking.message_post(
            body='3PL Sync: WH/PACK id=%s validated in backend.' % pack_id)

    def _fix_backend_out_moves(self, origin, pick_name, cfg, PTYPES):
        correct_outs = cfg._backend_call(
            'stock.picking', 'search_read',
            [[['origin', '=', origin],
              ['picking_type_id', '=', PTYPES['out']],
              ['state', 'not in', ['done', 'cancel']]]],
            {'fields': ['id', 'name', 'group_id']})
        if not correct_outs:
            return
        correct_out = correct_outs[0]
        correct_out_id = correct_out['id']
        bad_move_ids = set()
        group_id = (correct_out['group_id'][0]
                    if correct_out.get('group_id') else False)
        if group_id:
            by_group = cfg._backend_call(
                'stock.move', 'search_read',
                [[['group_id', '=', group_id],
                  ['picking_type_id', '=', PTYPES['out']],
                  ['picking_id', '!=', correct_out_id],
                  ['state', 'not in', ['done', 'cancel']]]],
                {'fields': ['id']})
            bad_move_ids.update(mv['id'] for mv in by_group)
        if pick_name:
            by_origin = cfg._backend_call(
                'stock.move', 'search_read',
                [[['origin', '=', pick_name],
                  ['picking_type_id', '=', PTYPES['out']],
                  ['picking_id', '!=', correct_out_id],
                  ['state', 'not in', ['done', 'cancel']]]],
                {'fields': ['id']})
            bad_move_ids.update(mv['id'] for mv in by_origin)
        if bad_move_ids:
            bad_ids = list(bad_move_ids)
            cfg._backend_call('stock.move', 'write',
                               [bad_ids, {'picking_id': correct_out_id}])
            bad_mls = cfg._backend_call(
                'stock.move.line', 'search_read',
                [[['move_id', 'in', bad_ids]]],
                {'fields': ['id']})
            if bad_mls:
                cfg._backend_call('stock.move.line', 'write',
                                   [[mv['id'] for mv in bad_mls],
                                    {'picking_id': correct_out_id}])

    # ── OUT step ────────────────────────────────────────────────────

    def _sync_out(self, picking, cfg, PTYPES):
        origin = self._get_sale_origin(picking)
        if not origin:
            return

        # Backend-driven mode guard
        existing_pick = cfg._backend_call(
            'stock.picking', 'search',
            [[['origin', '=', origin],
              ['picking_type_id', '=', PTYPES['pick']]]],
            {'limit': 1})
        if existing_pick:
            picking.message_post(
                body='3PL Sync: backend-driven mode — WH/OUT validation '
                     'handled by backend operator, skipping.')
            return

        product_qtys = _qty_done_mls(picking)
        pick_data = cfg._backend_call(
            'stock.picking', 'search_read',
            [[['origin', '=', origin],
              ['picking_type_id', '=', PTYPES['pick']],
              ['state', '=', 'done']]],
            {'fields': ['name'], 'order': 'id desc', 'limit': 1})
        pick_name = pick_data[0]['name'] if pick_data else None
        self._fix_backend_out_moves(origin, pick_name, cfg, PTYPES)
        out_id = None
        if pick_name:
            push_moves = cfg._backend_call(
                'stock.move', 'search_read',
                [[['origin', '=', pick_name],
                  ['picking_type_id', '=', PTYPES['out']],
                  ['state', 'not in', ['done', 'cancel']]]],
                {'fields': ['id', 'picking_id'], 'limit': 1})
            if push_moves:
                out_id = push_moves[0]['picking_id'][0]
        if not out_id:
            out_id = _find_backend_picking(cfg, origin, PTYPES['out'])
        if not out_id:
            picking.message_post(
                body='3PL Sync: WH/OUT not found in backend for origin %s '
                     '(backend-driven mode).' % origin)
            return
        stale_moves = cfg._backend_call(
            'stock.move', 'search_read',
            [[['picking_id', '=', out_id], ['origin', '=', False],
              ['state', 'not in', ['done', 'cancel']]]],
            {'fields': ['id']})
        if stale_moves:
            stale_ids = [mv['id'] for mv in stale_moves]
            cfg._backend_call('stock.move', 'write',
                               [stale_ids, {'state': 'cancel'}])
        other_outs = cfg._backend_call(
            'stock.picking', 'search_read',
            [[['origin', '=', origin],
              ['picking_type_id', '=', PTYPES['out']],
              ['id', '!=', out_id],
              ['state', 'not in', ['done', 'cancel']]]],
            {'fields': ['id']})
        for other in other_outs:
            has_push_move = False
            if pick_name:
                has_push_move = bool(cfg._backend_call(
                    'stock.move', 'search',
                    [[['picking_id', '=', other['id']],
                      ['origin', '=', pick_name],
                      ['state', 'not in', ['done', 'cancel']]]]))
            if not has_push_move:
                cfg._backend_call(
                    'stock.picking', 'action_cancel', [[other['id']]])
        waiting_moves = cfg._backend_call(
            'stock.move', 'search_read',
            [[['picking_id', '=', out_id], ['state', '=', 'waiting']]],
            {'fields': ['id']})
        if waiting_moves:
            cfg._backend_call('stock.move', 'write',
                               [[mv['id'] for mv in waiting_moves],
                                {'state': 'confirmed'}])
        cfg._backend_call('stock.picking', 'action_assign', [[out_id]])
        mls_after = cfg._backend_call(
            'stock.move.line', 'search_read',
            [[['picking_id', '=', out_id],
              ['state', 'not in', ['done', 'cancel']]]],
            {'fields': ['id'], 'limit': 1})
        if not mls_after:
            self._create_out_move_lines_manually(cfg, out_id)
        _validate_backend_picking(cfg, out_id, product_qtys)
        _logger.info('3PL Sync OUT: validated backend WH/OUT id=%s for %s',
                     out_id, origin)
        picking.message_post(
            body='3PL Sync: WH/OUT id=%s validated in backend.' % out_id)

    def _create_out_move_lines_manually(self, cfg, out_id):
        active_moves = cfg._backend_call(
            'stock.move', 'search_read',
            [[['picking_id', '=', out_id],
              ['state', 'not in', ['done', 'cancel']]]],
            {'fields': ['id', 'product_id', 'product_uom',
                        'product_uom_qty', 'location_id', 'location_dest_id']})
        for move in active_moves:
            prod_id = move['product_id'][0]
            src_loc = move['location_id'][0]
            dest_loc = move['location_dest_id'][0]
            needed = move['product_uom_qty']
            quants = cfg._backend_call(
                'stock.quant', 'search_read',
                [[['location_id', '=', src_loc],
                  ['product_id', '=', prod_id],
                  ['quantity', '>', 0]]],
                {'fields': ['id', 'lot_id', 'quantity',
                            'reserved_quantity', 'owner_id'],
                 'order': 'lot_id, id'})
            for q in quants:
                avail = q['quantity'] - q['reserved_quantity']
                if avail <= 0:
                    continue
                take = min(needed, avail)
                ml_vals = {
                    'picking_id': out_id,
                    'move_id': move['id'],
                    'product_id': prod_id,
                    'product_uom_id': move['product_uom'][0],
                    'location_id': src_loc,
                    'location_dest_id': dest_loc,
                    'quantity': take,
                }
                if q['lot_id']:
                    ml_vals['lot_id'] = q['lot_id'][0]
                if q['owner_id']:
                    ml_vals['owner_id'] = q['owner_id'][0]
                cfg._backend_call('stock.move.line', 'create', [ml_vals])
                needed -= take
                if needed <= 0:
                    break
            if needed > 0:
                _logger.warning(
                    '3PL Sync OUT: not enough stock for product %s '
                    'in loc %s (still need %s)', prod_id, src_loc, needed)

    # ── helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _get_sale_origin(picking):
        if picking.group_id and picking.group_id.name:
            name = picking.group_id.name
            if name.startswith('S'):
                return name
        if picking.origin and picking.origin.startswith('S'):
            return picking.origin
        return None

    @staticmethod
    def _get_purchase_origin(picking):
        """Return the purchase order name (P00XXX) for an incoming picking."""
        if picking.group_id and picking.group_id.name:
            name = picking.group_id.name
            if name.startswith('P'):
                return name
        if picking.origin and picking.origin.startswith('P'):
            return picking.origin
        # Fallback: use the picking name itself as origin key
        # so backend WH/IN can be linked back
        return picking.name or None
