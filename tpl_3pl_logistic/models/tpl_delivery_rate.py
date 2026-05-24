from odoo import models, fields, api


class TplDeliveryRate(models.Model):
    _name = 'tpl.delivery.rate'
    _description = '3PL Delivery Rate (Weight/Volume Tier)'
    _order = 'carrier_id, min_weight'

    name = fields.Char(string='Rate Name', required=True)
    carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Carrier',
        required=True,
        ondelete='cascade',
    )
    min_weight = fields.Float(string='Min Weight (kg)', digits=(16, 3), default=0.0)
    max_weight = fields.Float(
        string='Max Weight (kg)', digits=(16, 3), default=0.0,
        help='0 = no upper limit',
    )
    base_price = fields.Float(
        string='Base Price', digits=(16, 4), default=0.0,
        help='Fixed base charge regardless of weight/volume',
    )
    price_per_kg = fields.Float(string='Price / kg', digits=(16, 4), default=0.0)
    price_per_m3 = fields.Float(string='Price / m3', digits=(16, 4), default=0.0)
    volumetric_factor = fields.Float(
        string='Volumetric Factor',
        digits=(16, 0),
        default=5000.0,
        help='volume_cm3 / factor = volumetric weight (kg). Standard = 5000.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    def compute_price(self, weight_kg, volume_m3):
        self.ensure_one()
        vol_weight_kg = (volume_m3 * 1_000_000.0) / (self.volumetric_factor or 5000.0)
        chargeable_weight = max(weight_kg or 0.0, vol_weight_kg)
        cost = self.base_price
        cost += chargeable_weight * self.price_per_kg
        cost += (volume_m3 or 0.0) * self.price_per_m3
        return round(cost, 4)

    @api.constrains('min_weight', 'max_weight')
    def _check_weight_range(self):
        for rec in self:
            if rec.max_weight and rec.max_weight <= rec.min_weight:
                raise models.ValidationError(
                    'Max Weight must be greater than Min Weight (or 0 for no limit).'
                )
