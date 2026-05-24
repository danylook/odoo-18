from odoo import models, fields, api


class StockPickingTplDelivery(models.Model):
    _inherit = 'stock.picking'

    tpl_shipping_volume = fields.Float(
        string='Shipping Volume (m3)',
        digits=(16, 4),
        help='Volume in cubic metres for delivery cost calculation.',
    )
    tpl_delivery_cost = fields.Float(
        string='Delivery Cost',
        digits=(16, 4),
        compute='_compute_tpl_delivery_cost',
        store=True,
        help='Cost computed from 3PL rate tiers (chargeable weight + volume).',
    )
    tpl_delivery_invoiced = fields.Boolean(
        string='Delivery Fee Invoiced',
        default=False,
    )

    @api.depends(
        'carrier_id',
        'carrier_id.tpl_is_own_truck',
        'carrier_id.tpl_rate_ids',
        'shipping_weight',
        'tpl_shipping_volume',
    )
    def _compute_tpl_delivery_cost(self):
        for picking in self:
            carrier = picking.carrier_id
            if carrier and carrier.tpl_is_own_truck:
                weight = picking.shipping_weight or 0.0
                volume = picking.tpl_shipping_volume or 0.0
                picking.tpl_delivery_cost = carrier.tpl_compute_delivery_price(weight, volume)
            else:
                picking.tpl_delivery_cost = 0.0

    def action_tpl_create_delivery_invoice(self):
        self.ensure_one()
        if not self.tpl_owner_id:
            return
        carrier = self.carrier_id
        if not carrier or not carrier.tpl_is_own_truck:
            return
        product = carrier.tpl_delivery_product_id
        if not product:
            product = self.env.ref(
                'tpl_3pl_logistic.product_delivery_own_truck',
                raise_if_not_found=False,
            )
        if not product:
            return
        carrier_name = carrier.name or ''
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.tpl_owner_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': 'Delivery: ' + self.name + ' via ' + carrier_name,
                'quantity': 1,
                'price_unit': self.tpl_delivery_cost,
            })],
        })
        self.tpl_delivery_invoiced = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
