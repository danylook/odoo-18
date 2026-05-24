from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    owner_id = fields.Many2one(
        'res.partner',
        string='3PL Client Owner',
        help='The client company that owns this product in the 3PL warehouse.',
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.owner_id and not rec.is_storable:
                rec.write({'is_storable': True, 'tracking': 'lot'})
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'owner_id' in vals and vals.get('owner_id'):
            for rec in self:
                if not rec.is_storable:
                    super(ProductTemplate, rec).write({'is_storable': True, 'tracking': 'lot'})
        return res
