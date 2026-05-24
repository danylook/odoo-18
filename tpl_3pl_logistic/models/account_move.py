from odoo import models, fields
from dateutil.relativedelta import relativedelta


class AccountMove(models.Model):
    _inherit = 'account.move'

    tpl_storage_period_start = fields.Date(string='Storage Period Start')
    tpl_storage_period_end = fields.Date(string='Storage Period End')
    tpl_next_invoice_date = fields.Date(string='Next Invoice Date')
    tpl_invoice_period = fields.Selection([
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ], string='Invoice Period')

    def action_create_next_recurring_invoice(self):
        self.ensure_one()
        if not self.tpl_invoice_period:
            return
        delta = {
            'weekly': relativedelta(weeks=1),
            'monthly': relativedelta(months=1),
            'yearly': relativedelta(years=1),
        }[self.tpl_invoice_period]
        new_date = (self.invoice_date or fields.Date.today()) + delta
        new_invoice = self.copy({
            'invoice_date': new_date,
            'tpl_storage_period_start': new_date,
            'tpl_storage_period_end': new_date + delta,
            'tpl_next_invoice_date': new_date + delta,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': new_invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
