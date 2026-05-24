# -*- coding: utf-8 -*-
"""
tpl_3pl_back_sync — stock.picking override on BACKEND
When backend operator validates WH/PICK, WH/PACK, WH/OUT or WH/IN, this
addon calls the client (3pl-cliente) via XML-RPC and validates the
corresponding ECO/PICK, ECO/PACK, ECO/OUT or ECO/IN automatically.
"""
import logging
import socket
import time
import xmlrpc.client
from odoo import models

_RETRY_ERRORS = (
    socket.timeout, socket.error, ConnectionError, TimeoutError,
    xmlrpc.client.ProtocolError,
)
_MAX_RETRIES = 3
_RETRY_DELAYS = [1, 2]  # seconds between attempts 1→2, 2→3

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        not_yet_done = self.filtered(lambda p: p.state != 'done')
        res = super().button_validate()
        for picking in not_yet_done:
            if picking.state != 'done':
                continue
            # Resolve owner: prefer tpl_owner_id (sale pickings), fall back to
            # the owner of the first move line (receipt pickings).
            owner_id = None
            if hasattr(picking, 'tpl_owner_id') and picking.tpl_owner_id:
                owner_id = picking.tpl_owner_id.id
            if not owner_id:
                ml = picking.move_line_ids[:1]
                if ml and ml.owner_id:
                    owner_id = ml.owner_id.id
            # Route to the correct client config by owner, fall back to
            # the single active config for backwards-compatibility.
            if owner_id:
                cfg = self.env['tpl.client.config'].get_for_owner(owner_id)
            else:
                cfg = self.env['tpl.client.config'].get_active()
            if not cfg:
                continue
            last_err = None
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    self._back_sync_step(picking, cfg)
                    last_err = None
                    break
                except _RETRY_ERRORS as e:
                    last_err = e
                    if attempt < _MAX_RETRIES:
                        delay = _RETRY_DELAYS[attempt - 1]
                        _logger.warning(
                            '3PL BackSync: transient error for %s '
                            '(attempt %d/%d, retry in %ds): %s',
                            picking.name, attempt, _MAX_RETRIES, delay, e)
                        time.sleep(delay)
                    else:
                        _logger.error(
                            '3PL BackSync: failed for %s after %d attempts: %s',
                            picking.name, _MAX_RETRIES, e)
                except Exception as e:
                    last_err = e
                    _logger.error(
                        '3PL BackSync: non-retryable error for %s: %s',
                        picking.name, e)
                    break
            if last_err:
                picking.message_post(
                    body='⚠️ 3PL BackSync error: %s' % last_err)
        return res

    # ── manual retry ────────────────────────────────────────────────────────

    def action_retry_back_sync(self):
        """Manual retry button: re-run the back-sync step for this picking."""
        self.ensure_one()
        owner_id = None
        if hasattr(self, 'tpl_owner_id') and self.tpl_owner_id:
            owner_id = self.tpl_owner_id.id
        if not owner_id:
            ml = self.move_line_ids[:1]
            if ml and ml.owner_id:
                owner_id = ml.owner_id.id
        if owner_id:
            cfg = self.env['tpl.client.config'].get_for_owner(owner_id)
        else:
            cfg = self.env['tpl.client.config'].get_active()
        if not cfg:
            raise ValueError('No 3PL client config found for this picking.')
        try:
            self._back_sync_step(self, cfg)
            self.message_post(body='✅ 3PL BackSync: manual retry succeeded.')
        except Exception as e:
            self.message_post(body='⚠️ 3PL BackSync error: %s' % e)
            raise

    # ── dispatch ────────────────────────────────────────────────────────────

    def _back_sync_step(self, picking, cfg):
        ptype = picking.picking_type_id
        type_name = (ptype.name or '').upper()
        code = ptype.code
        if code == 'incoming':
            self._back_sync_in(picking, cfg)
        elif code == 'internal' and 'PICK' in type_name:
            self._back_sync_pick(picking, cfg)
        elif code == 'internal' and 'PACK' in type_name:
            self._back_sync_pack(picking, cfg)
        elif code == 'outgoing':
            self._back_sync_out(picking, cfg)

    # ── origin helpers ───────────────────────────────────────────────────────

    def _get_sale_origin(self, picking):
        """Return S00XXX from group_id.name or picking.origin.

        Handles composite origins like 'S00016,WH/PICK/00015'.
        """
        if picking.group_id and picking.group_id.name:
            name = picking.group_id.name
            if name.startswith('S') and '/' not in name:
                return name
        if picking.origin:
            # Origin may be comma-separated (e.g. 'S00016,WH/PICK/00015')
            for part in picking.origin.split(','):
                part = part.strip()
                if part.startswith('S') and '/' not in part:
                    return part
        return None

    def _get_purchase_origin(self, picking):
        """Return the purchase order name (P00XXX) for an incoming picking.

        For WH/IN created by the client sync, origin is set to the PO name.
        For WH/IN created by a backend PO, origin is also the PO name.
        """
        if picking.group_id and picking.group_id.name:
            name = picking.group_id.name
            if name.startswith('P') and '/' not in name:
                return name
        if picking.origin:
            for part in picking.origin.split(','):
                part = part.strip()
                if part.startswith('P') and '/' not in part:
                    return part
        # Fallback: origin is set verbatim (could be any PO naming)
        return picking.origin or None

    # ── client picking lookup ────────────────────────────────────────────────

    def _find_client_picking(self, cfg, sale_origin, type_code,
                             type_name_keyword=None):
        """
        Find the client-side picking for the given sale order and type.
        Searches by group_id.name first (most reliable), then by origin.
        Returns the first matching record dict or None.
        """
        base_domain = [['state', 'not in', ['done', 'cancel']],
                       ['picking_type_id.code', '=', type_code]]
        if type_name_keyword:
            base_domain.append(
                ['picking_type_id.name', 'ilike', type_name_keyword])

        for extra in (
            [['group_id.name', '=', sale_origin]],
            [['origin', '=', sale_origin]],
        ):
            recs = cfg._client_call(
                'stock.picking', 'search_read',
                [base_domain + extra],
                {'fields': ['id', 'name'], 'limit': 1})
            if recs:
                return recs[0]
        return None

    # ── client picking validation ────────────────────────────────────────────

    def _validate_client_picking(self, cfg, client_picking_id):
        """
        1. Try to reserve the client picking (action_assign).
        2. If no move lines created, build them from move demands.
        3. Set quantity = demand on every move line.
        4. Call button_validate.
        """
        # Step 1: reserve
        cfg._client_call('stock.picking', 'action_assign',
                         [[client_picking_id]])

        # Step 2: check for move lines
        mls = cfg._client_call(
            'stock.move.line', 'search_read',
            [[['picking_id', '=', client_picking_id],
              ['state', 'not in', ['done', 'cancel']]]],
            {'fields': ['id', 'move_id', 'quantity']})

        if not mls:
            _logger.info(
                '3PL BackSync: no mls after action_assign on client '
                'picking id=%s — creating from move demands', client_picking_id)
            self._create_client_move_lines(cfg, client_picking_id)
            mls = cfg._client_call(
                'stock.move.line', 'search_read',
                [[['picking_id', '=', client_picking_id],
                  ['state', 'not in', ['done', 'cancel']]]],
                {'fields': ['id', 'move_id', 'quantity']})

        # Step 3: set quantity = demand
        moves = cfg._client_call(
            'stock.move', 'search_read',
            [[['picking_id', '=', client_picking_id],
              ['state', 'not in', ['done', 'cancel']]]],
            {'fields': ['id', 'product_uom_qty']})
        move_demand = {m['id']: m['product_uom_qty'] for m in moves}

        for ml in mls:
            move_id_val = ml.get('move_id')
            move_id = (move_id_val[0]
                       if isinstance(move_id_val, list) else move_id_val)
            demand = move_demand.get(move_id) if move_id else None
            if demand is None:
                demand = ml.get('quantity', 0)
            if demand != ml.get('quantity', 0):
                cfg._client_call('stock.move.line', 'write',
                                 [[ml['id']], {'quantity': demand}])

        # Step 4: validate.
        cfg._client_call('stock.picking', 'button_validate',
                         [[client_picking_id]],
                         {'context': {'skip_immediate': True,
                                      'skip_backorder': True}},
                         timeout=180)
        _logger.info('3PL BackSync: validated client picking id=%s',
                     client_picking_id)

    def _create_client_move_lines(self, cfg, client_picking_id):
        """Fallback: create move lines directly from move demands."""
        moves = cfg._client_call(
            'stock.move', 'search_read',
            [[['picking_id', '=', client_picking_id],
              ['state', 'not in', ['done', 'cancel']]]],
            {'fields': ['id', 'product_id', 'product_uom',
                        'product_uom_qty', 'location_id', 'location_dest_id']})
        for move in moves:
            cfg._client_call('stock.move.line', 'create', [{
                'picking_id': client_picking_id,
                'move_id': move['id'],
                'product_id': move['product_id'][0],
                'product_uom_id': move['product_uom'][0],
                'location_id': move['location_id'][0],
                'location_dest_id': move['location_dest_id'][0],
                'quantity': move['product_uom_qty'],
            }])

    # ── per-type sync methods ────────────────────────────────────────────────

    def _back_sync_in(self, picking, cfg):
        """
        When backend operator validates WH/IN, find the corresponding client
        ECO/IN (matched by PO origin) and validate it.
        If ECO/IN was already validated (client-driven mode), skip silently.
        """
        origin = self._get_purchase_origin(picking)
        if not origin:
            _logger.warning(
                '3PL BackSync IN: no purchase origin on %s', picking.name)
            return

        rec = self._find_client_picking(cfg, origin, 'incoming')
        if not rec:
            # Client-driven: ECO/IN was already validated before WH/IN
            _logger.info(
                '3PL BackSync IN: no pending client ECO/IN for %s '
                '(client-driven mode or already done)', origin)
            picking.message_post(
                body='3PL BackSync: no pending ECO/IN for %s '
                     '(client-driven or already done).' % origin)
            return

        self._validate_client_picking(cfg, rec['id'])
        picking.message_post(
            body='3PL BackSync: client %s validated.' % rec['name'])

    def _back_sync_pick(self, picking, cfg):
        origin = self._get_sale_origin(picking)
        if not origin:
            return
        rec = self._find_client_picking(cfg, origin, 'internal', 'pick')
        if not rec:
            _logger.warning(
                '3PL BackSync: no client PICK found for %s', origin)
            picking.message_post(
                body='⚠️ 3PL BackSync: client ECO/PICK not found for %s' % origin)
            return
        self._validate_client_picking(cfg, rec['id'])
        picking.message_post(
            body='3PL BackSync: client %s validated.' % rec['name'])

    def _back_sync_pack(self, picking, cfg):
        # WH/PACK.origin = WH/PICK name — get sale origin via group_id
        origin = self._get_sale_origin(picking)
        if not origin:
            # Try via linked WH/PICK
            wh_pick = self.env['stock.picking'].search(
                [('name', '=', picking.origin)], limit=1)
            if wh_pick:
                origin = self._get_sale_origin(wh_pick)
        if not origin:
            _logger.warning(
                '3PL BackSync: cannot determine sale origin for PACK %s',
                picking.name)
            return
        rec = self._find_client_picking(cfg, origin, 'internal', 'pack')
        if not rec:
            _logger.warning(
                '3PL BackSync: no client PACK found for %s', origin)
            picking.message_post(
                body='⚠️ 3PL BackSync: client ECO/PACK not found for %s' % origin)
            return
        self._validate_client_picking(cfg, rec['id'])
        picking.message_post(
            body='3PL BackSync: client %s validated.' % rec['name'])

    def _back_sync_out(self, picking, cfg):
        origin = self._get_sale_origin(picking)
        if not origin:
            return
        rec = self._find_client_picking(cfg, origin, 'outgoing')
        if not rec:
            _logger.warning(
                '3PL BackSync: no client OUT found for %s', origin)
            picking.message_post(
                body='⚠️ 3PL BackSync: client ECO/OUT not found for %s' % origin)
            return
        self._validate_client_picking(cfg, rec['id'])
        picking.message_post(
            body='3PL BackSync: client %s validated.' % rec['name'])
