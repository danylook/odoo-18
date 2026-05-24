from odoo import models, fields


class StockLocation(models.Model):
    _inherit = 'stock.location'

    fee_rate_id = fields.Many2one(
        'tpl.fee.rate',
        string='Fee Rate',
        help='Billing fee rate applied to stock stored in this location.',
    )
    tpl_map_active = fields.Boolean(
        string='Show on Map',
        default=False,
        help='Display this location on the warehouse map.',
    )
    tpl_map_x = fields.Integer(
        string='Map Column (X)',
        default=1,
        help='Column position on the warehouse map (left=1).',
    )
    tpl_map_y = fields.Integer(
        string='Map Row (Y)',
        default=1,
        help='Row position on the warehouse map (top=1).',
    )
