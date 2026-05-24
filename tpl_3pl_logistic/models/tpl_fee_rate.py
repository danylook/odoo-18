from odoo import models, fields


class TplFeeRate(models.Model):
    _name = 'tpl.fee.rate'
    _description = 'Fee Rate'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    daily_rate = fields.Float(string='Daily Rate (per unit)', digits=(16, 4), default=0.0)
    monthly_rate = fields.Float(string='Monthly Rate (per unit)', digits=(16, 4), default=0.0)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    note = fields.Text(string='Notes')
    location_ids = fields.One2many('stock.location', 'fee_rate_id', string='Locations')
    active = fields.Boolean(default=True)
