# -*- coding: utf-8 -*-
"""
stock.picking extension for 3PL client.

Hooks into all 3 delivery steps (Pick → Pack → Ship) and notifies
the 3PL server at each step so warehouse staff can track progress.

  PICK step → POST /api/3pl/order/step   (step=pick)
  PACK step → POST /api/3pl/order/step   (step=pack)
  SHIP step → POST /api/3pl/stock/consume (validates physical stock on 3PL)
"""
import json
import logging
import urllib.request
import urllib.error

from odoo import models

_logger = logging.getLogger(__name__)

# Map warehouse picking-type sequence_code → step name sent to 3PL server
_STEP_MAP = {
    'PICK': 'pick',
    'PACK': 'pack',
    'OUT':  'ship',
}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        res = super()._action_done()
        for picking in self.filtered(lambda p: p.state == 'done'):
            seq = picking.picking_type_id.sequence_code
            step = _STEP_MAP.get(seq)
            if not step:
                continue
            try:
                if step == 'ship':
                    picking._notify_3pl_consumption()
                else:
                    picking._notify_3pl_step(step)
            except Exception as e:
                _logger.error(
                    '3PL step notification failed for picking %s step=%s: %s',
                    picking.name, step, e,
                )
        return res

    # ── helpers ─────────────────────────────────────────────────────

    def _get_3pl_config(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        return get('tpl3pl.server.url', '').rstrip('/'), get('tpl3pl.api.key', '')

    def _order_ref(self):
        """Return the sale order name for this picking via procurement group or origin."""
        return (
            (self.group_id.name if self.group_id else None)
            or self.origin
            or self.name
        )

    def _post_to_3pl(self, path, payload):
        url, key = self._get_3pl_config()
        if not url or not key:
            return
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url + path,
            data=body,
            headers={'X-API-Key': key, 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
            _logger.info('3PL %s → %s: %s', path, self.name, result)
        except urllib.error.HTTPError as e:
            _logger.error(
                '3PL %s HTTP %s for %s: %s', path, e.code, self.name, e.read().decode()
            )
        except Exception as e:
            _logger.error('3PL %s error for %s: %s', path, self.name, e)

    # ── step notifications ───────────────────────────────────────────

    def _notify_3pl_step(self, step):
        """Notify 3PL of a pick or pack step completion."""
        products = []
        for move in self.move_ids.filtered(lambda m: m.state == 'done'):
            ref = move.product_id.default_code
            if not ref:
                continue
            qty = sum(move.move_line_ids.mapped('quantity'))
            if qty > 0:
                products.append({'ref': ref, 'qty': qty})

        if not products:
            return

        self._post_to_3pl('/api/3pl/order/step', {
            'ref': self._order_ref(),
            'step': step,
            'picking': self.name,
            'products': products,
        })

    def _notify_3pl_consumption(self):
        """POST consumed quantities to /api/3pl/stock/consume (final Ship step)."""
        url, key = self._get_3pl_config()
        if not url or not key:
            return

        tpl_location = self.env['stock.location'].sudo().search([
            ('name', '=', '3PL Warehouse'),
            ('usage', '=', 'internal'),
        ], limit=1)
        if not tpl_location:
            return

        consumed = {}
        for move in self.move_ids.filtered(lambda m: m.state == 'done'):
            for ml in move.move_line_ids.filtered(
                lambda l: l.location_id.id == tpl_location.id
            ):
                ref = ml.product_id.default_code
                if not ref:
                    continue
                consumed[ref] = consumed.get(ref, 0.0) + ml.quantity

        if not consumed:
            return

        self._post_to_3pl('/api/3pl/stock/consume', {
            'origin': self._order_ref(),
            'picking': self.name,
            'products': [{'ref': r, 'qty': q} for r, q in consumed.items()],
        })
