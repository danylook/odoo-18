from odoo import models, fields, api
import json
from datetime import datetime


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def reconcile(self, *args, **kwargs):
        res = super(AccountMoveLine, self).reconcile(*args, **kwargs)
        payment_date = None
        for rec in self:
            if rec.move_id.payment_ids:
                payment_date = rec.move_id.payment_ids[:1].date
        for rec in self:
            if rec.move_id.move_type == 'out_invoice':
                rec.move_id.payment_date = payment_date
        return res



class account_move(models.Model):
    _inherit = 'account.move'

    def _compute_payment_date(self):
        for inv in self:
            dates = []
            inv.payment_date = '2020-01-01'
            if isinstance(inv.invoice_payments_widget, bool):
                inv.payment_date = '2020-01-01'
                print('info 1', inv.payment_date)
            else:
                if inv.payment_state == 'paid' or inv.payment_state == 'partial':
                     for payment_info in json.loads(inv.invoice_payments_widget).get('content', []):
                        fecha = datetime.strptime(payment_info.get('date', ''), '%Y-%m-%d')
                        fecha = datetime.date(fecha)
                        if inv.payment_date < fecha:
                            inv.payment_date = fecha
                else:
                    inv.payment_date = ''

    #payment_date = fields.Date(compute='_compute_payment_date', store=True,)
    payment_date = fields.Date('Payment Date')

class commission_paydate_line(models.Model):
    _inherit = "account.invoice.line.agent"
    _order = "payment_date asc"

    object_id = fields.Many2one(comodel_name="account.move.line")
    payment_date = fields.Date(
            string="Payment date",
            related="invoice_id.payment_date",
            store=True,
         )
class commission_settlement_paydate_line(models.Model):
    _inherit = "commission.settlement.line"
    _order = "payment_date asc"
    object_id = fields.Many2one(comodel_name="account.invoice.line.agent")
    payment_date = fields.Date(
            string="Payment date",
            related="invoice_line_id.move_id.payment_date",
            #related="invoice_agent_line_id.payment_date",
            store=True,
         )

#class SettlementLine(models.Model):
#    _inherit = "commission.settlement.line"
#    _order = "payment_date asc"
#    object_id = fields.Many2one(comodel_name="account.invoice.line.agent")
#    payment_date = fields.Date(
#        string="Payment date",
#        related="invoice_agent_line_id.payment_date",
#        store=True,
#    )






