from odoo import models, fields


class CustomCompany(models.Model):
    _name = 'custom.company'
    _description = 'Custom Company'

    def _compute_report_company_id(self):
        for rec in self:
            rec.report_company_id = self.env.company

    report_company_id = fields.Many2one(
        'res.company', 'Compania Reporte',
        compute="_compute_report_company_id"
    )
