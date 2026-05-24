# -*- coding: utf-8 -*-
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class Tpl3plStock(models.Model):
    _name = 'tpl.3pl.stock'
    _description = '3PL Stock Snapshot'
    _order = 'product_ref'

    product_ref = fields.Char('Internal Ref', readonly=True)
    product_name = fields.Char('Product', readonly=True)
    qty_on_hand = fields.Float('Qty at 3PL', readonly=True, digits=(16, 3))
    uom = fields.Char('UoM', readonly=True)
    location = fields.Char('Location', readonly=True)
    last_sync = fields.Datetime('Last Sync', readonly=True)

    @api.model
    def _get_config(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        url = get('tpl3pl.server.url', '').rstrip('/')
        key = get('tpl3pl.api.key', '')
        if not url or not key:
            raise UserError(_(
                '3PL server URL and API key must be configured in '
                'Settings → 3PL Integration.'
            ))
        return url, key

    @api.model
    def _get_3pl_location(self):
        """Get or create the virtual 3PL warehouse location under Physical Locations."""
        loc = self.env['stock.location'].sudo().search([
            ('name', '=', '3PL Warehouse'),
            ('usage', '=', 'internal'),
        ], limit=1)
        if not loc:
            parent = self.env.ref('stock.stock_location_locations')
            loc = self.env['stock.location'].sudo().create({
                'name': '3PL Warehouse',
                'usage': 'internal',
                'location_id': parent.id,
                'active': True,
                'comment': 'Virtual mirror of external 3PL stock — managed automatically by sync.',
            })
            _logger.info('3PL: created virtual location id=%d', loc.id)
        return loc

    @api.model
    def _get_or_create_product(self, ref, name, uom_name):
        """Find product by internal ref, creating it if it doesn't exist on this server."""
        product = self.env['product.product'].sudo().search(
            [('default_code', '=', ref)], limit=1
        )
        if not product:
            # Find or use Units as UoM fallback
            uom = self.env['uom.uom'].sudo().search(
                [('name', '=', uom_name)], limit=1
            ) or self.env.ref('uom.product_uom_unit', raise_if_not_found=False)

            tmpl = self.env['product.template'].sudo().create({
                'name': name,
                'default_code': ref,
                'type': 'consu',
                'is_storable': True,
                'uom_id': uom.id if uom else False,
                'uom_po_id': uom.id if uom else False,
            })
            product = tmpl.product_variant_id
            _logger.info('3PL sync: auto-created product ref=%s name=%s', ref, name)
        return product

    @api.model
    def _sync_virtual_stock(self, products_data):
        """Mirror API stock quantities into the 3PL virtual location.

        Uses stock.quant._update_available_quantity() so movements are
        recorded properly and the stock is visible in standard inventory views.
        Products missing on this server are auto-created.
        """
        location = self._get_3pl_location()
        StockQuant = self.env['stock.quant'].sudo()

        # Build map of current quants in 3PL location: {product_id: quant}
        existing_quants = StockQuant.search([('location_id', '=', location.id)])
        current = {q.product_id.id: q for q in existing_quants}

        # Build target map from API data: {product_id: target_qty}
        target = {}
        for p in products_data:
            ref = p.get('ref', '')
            qty = float(p.get('qty_on_hand', 0.0))
            if not ref:
                continue
            product = self._get_or_create_product(
                ref, p.get('name', ref), p.get('uom', 'Units')
            )
            if product:
                target[product.id] = qty

        # Zero out products no longer returned by the API
        for pid, quant in current.items():
            if pid not in target and quant.quantity != 0:
                StockQuant._update_available_quantity(
                    quant.product_id, location, -quant.quantity
                )
                _logger.info('3PL sync: zeroed out product id=%d in 3PL location', pid)

        # Update or create quantities for products in API response
        for pid, qty in target.items():
            product = self.env['product.product'].sudo().browse(pid)
            if pid in current:
                delta = qty - current[pid].quantity
                if abs(delta) > 0.001:
                    StockQuant._update_available_quantity(product, location, delta)
                    _logger.info(
                        '3PL sync: updated product id=%d delta=%.3f → %.3f',
                        pid, delta, qty,
                    )
            else:
                if qty > 0:
                    StockQuant._update_available_quantity(product, location, qty)
                    _logger.info('3PL sync: created quant product id=%d qty=%.3f', pid, qty)

    @api.model
    def action_sync(self):
        url, key = self._get_config()
        req = urllib.request.Request(
            url + '/api/3pl/stock',
            headers={'X-API-Key': key},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise UserError(_('3PL API error %s: %s') % (e.code, e.read().decode()))
        except Exception as e:
            raise UserError(_('Could not reach 3PL server: %s') % str(e))

        products = data.get('products', [])
        now = datetime.now()

        # Update snapshot table (custom 3PL view)
        self.search([]).unlink()
        for p in products:
            self.create({
                'product_ref': p.get('ref', ''),
                'product_name': p.get('name', ''),
                'qty_on_hand': p.get('qty_on_hand', 0.0),
                'uom': p.get('uom', ''),
                'location': p.get('location', ''),
                'last_sync': now,
            })

        # Mirror into real stock quants (virtual 3PL Warehouse location)
        self._sync_virtual_stock(products)

        _logger.info('3PL stock sync: %d products', len(products))
        return True

    def action_sync_button(self):
        self.env['tpl.3pl.stock'].action_sync()
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class Tpl3plOrderPush(models.TransientModel):
    _name = 'tpl.3pl.order.push'
    _description = 'Push Order to 3PL'

    picking_id = fields.Many2one('stock.picking', string='Transfer', required=True)
    origin = fields.Char('Reference', required=True)
    order_type = fields.Selection([
        ('inbound', 'Inbound (Receive at 3PL)'),
        ('outbound', 'Outbound (Deliver from 3PL)'),
    ], string='Type', required=True, default='outbound')
    address = fields.Char('Delivery Address')
    contact_name = fields.Char('Contact Name')
    contact_phone = fields.Char('Contact Phone')
    note = fields.Char('Note')
    line_ids = fields.One2many('tpl.3pl.order.push.line', 'wizard_id', string='Products')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking_id = self.env.context.get('active_id')
        if picking_id:
            picking = self.env['stock.picking'].browse(picking_id)
            code = picking.picking_type_id.code
            res['picking_id'] = picking_id
            res['origin'] = picking.origin or picking.name
            res['order_type'] = 'inbound' if code == 'incoming' else 'outbound'
            res['line_ids'] = [
                (0, 0, {
                    'product_ref': m.product_id.default_code or '',
                    'product_name': m.product_id.name,
                    'qty': m.product_uom_qty,
                })
                for m in picking.move_ids
            ]
        return res

    def action_push(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        url = get('tpl3pl.server.url', '').rstrip('/')
        key = get('tpl3pl.api.key', '')
        if not url or not key:
            raise UserError(_('3PL server URL and API key must be configured in Settings.'))

        payload = {
            'origin': self.origin,
            'note': self.note or '',
            'products': [
                {'ref': l.product_ref, 'qty': l.qty}
                for l in self.line_ids if l.product_ref
            ],
        }
        if self.order_type == 'outbound':
            payload['address'] = self.address or ''
            payload['contact_name'] = self.contact_name or ''
            payload['contact_phone'] = self.contact_phone or ''

        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url + '/api/3pl/order/' + self.order_type,
            data=body,
            headers={'X-API-Key': key, 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise UserError(_('3PL API error %s: %s') % (e.code, e.read().decode()))
        except Exception as e:
            raise UserError(_('Could not reach 3PL server: %s') % str(e))

        self.picking_id.message_post(
            body=_('Pushed to 3PL — ref: %s | type: %s | state: %s') % (
                result.get('3pl_ref', ''),
                self.order_type,
                result.get('state', ''),
            )
        )
        return {'type': 'ir.actions.act_window_close'}


class Tpl3plOrderPushLine(models.TransientModel):
    _name = 'tpl.3pl.order.push.line'
    _description = 'Order Push Line'

    wizard_id = fields.Many2one('tpl.3pl.order.push', ondelete='cascade')
    product_ref = fields.Char('Internal Ref', required=True)
    product_name = fields.Char('Product')
    qty = fields.Float('Qty', required=True, default=1.0)
