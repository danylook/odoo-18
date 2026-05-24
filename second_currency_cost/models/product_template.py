from odoo import models, api, fields
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_cost_id = fields.Many2one(
        'res.currency',
        string="Cost and Sale Currency",
        help="Currency for cost and sale",
        required=True, readonly=False
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    currency_cost_id = fields.Many2one('res.currency',
        related="company_id.currency_cost_id",
        required=True, readonly=False,
        string='Cost Currency',
        help="Currency for cost and sale"
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.depends('company_id', 'company_id.currency_cost_id')
    def _compute_currency_id(self):
        for template in self:
            company = self.env.company
            if not company.currency_cost_id:
                raise UserError('Please configure a cost currency in company settings first.')
            template.currency_id = company.currency_cost_id
            template.cost_currency_id = company.currency_cost_id
