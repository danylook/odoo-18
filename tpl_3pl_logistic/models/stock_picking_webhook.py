# -*- coding: utf-8 -*-
import json
import logging
import threading

import requests as req_lib

from odoo import models

_logger = logging.getLogger(__name__)


class StockPickingWebhook(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        result = super().button_validate()
        # Fire webhook asynchronously so it never blocks validation
        for picking in self.filtered(lambda p: p.state == 'done'):
            self._fire_webhook_async(picking)
        return result

    @staticmethod
    def _fire_webhook_async(picking):
        def _send():
            try:
                env = picking.env
                partner = picking.owner_id or picking.partner_id
                if not partner:
                    return
                api_keys = env['tpl.3pl.api.key'].sudo().search([
                    ('partner_id', 'in', [partner.id, partner.parent_id.id] if partner.parent_id else [partner.id]),
                    ('active', '=', True),
                    ('webhook_url', '!=', False),
                ])
                if not api_keys:
                    return

                # Build stock snapshot for affected products
                product_ids = picking.move_ids.mapped('product_id').ids
                quants = env['stock.quant'].sudo().search([
                    ('owner_id', '=', partner.id),
                    ('location_id.usage', '=', 'internal'),
                    ('product_id', 'in', product_ids),
                ])
                stock = {}
                for q in quants:
                    ref = q.product_id.default_code or str(q.product_id.id)
                    stock[ref] = stock.get(ref, 0) + q.quantity

                payload = {
                    'event': 'stock_update',
                    'triggered_by': picking.name,
                    'origin': picking.origin or '',
                    'type': picking.picking_type_code,
                    'products': [
                        {'ref': ref, 'qty_on_hand': qty}
                        for ref, qty in stock.items()
                    ],
                }

                for api_key in api_keys:
                    headers = {'Content-Type': 'application/json'}
                    if api_key.webhook_secret:
                        headers['X-Webhook-Secret'] = api_key.webhook_secret
                    try:
                        resp = req_lib.post(
                            api_key.webhook_url,
                            json=payload,
                            headers=headers,
                            timeout=10,
                        )
                        _logger.info('3PL webhook → %s: HTTP %s', api_key.webhook_url, resp.status_code)
                    except Exception as e:
                        _logger.warning('3PL webhook failed for %s: %s', api_key.webhook_url, e)
            except Exception as e:
                _logger.error('3PL webhook thread error: %s', e)

        t = threading.Thread(target=_send, daemon=True)
        t.start()
