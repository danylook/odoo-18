from odoo import fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    tpl_client_owner_id = fields.Many2one(
        'res.partner',
        string='3PL Client Owner',
        related='product_id.product_tmpl_id.owner_id',
        store=True,
        readonly=True,
        index=True,
    )
