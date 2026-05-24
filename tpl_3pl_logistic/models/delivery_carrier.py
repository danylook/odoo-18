from odoo import models, fields


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    tpl_is_own_truck = fields.Boolean(
        string='3PL Own Truck',
        default=False,
        help='Enable to use 3PL custom weight/volume rate tiers for pricing.',
    )
    tpl_rate_ids = fields.One2many(
        'tpl.delivery.rate',
        'carrier_id',
        string='3PL Rate Tiers',
    )
    tpl_delivery_product_id = fields.Many2one(
        'product.product',
        string='Delivery Invoice Product',
        domain="[('type', '=', 'service')]",
        help='Service product used on delivery invoices.',
    )

    def tpl_get_rate_for_weight(self, weight_kg):
        self.ensure_one()
        rates = self.tpl_rate_ids.filtered('active').sorted('min_weight')
        for rate in rates:
            if weight_kg >= rate.min_weight:
                if not rate.max_weight or weight_kg <= rate.max_weight:
                    return rate
        return rates[:1]

    def tpl_compute_delivery_price(self, weight_kg, volume_m3):
        self.ensure_one()
        if not self.tpl_is_own_truck:
            return 0.0
        rate = self.tpl_get_rate_for_weight(weight_kg)
        if not rate:
            return 0.0
        return rate.compute_price(weight_kg, volume_m3)
