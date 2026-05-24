from odoo import fields,models, api, _
from odoo.exceptions import UserError, ValidationError


class PaymentReconcileWizard(models.TransientModel):
    _name = "payment.reconcile.wizard"
    _description = "payment.reconcile.wizard"

    def btn_confirm(self):
        aml_obj = self.env['account.move.line']
        aml_obj += self.payment_move_line_id
        for line in self.line_ids:
            if line.selected:
                aml_obj += line.move_line_id
        aml_obj.reconcile()

    @api.depends('line_ids')
    def _compute_selected_amount(self):
        for rec in self:
            #rec.selected_amount = sum(rec.line_ids.filtered(lambda l: l.selected == True).mapped('amount_residual'))
            selected_amount = 0
            for line in rec.line_ids:
                if line.selected:
                    selected_amount = selected_amount + line.amount_residual
            rec.selected_amount = selected_amount

    def _compute_amount_payment(self):
        for rec in self:
            rec.amount_payment = rec.payment_move_line_id.amount_residual

    payment_id = fields.Many2one(comodel_name='account.payment',string='Pago')
    line_ids = fields.One2many(comodel_name='payment.reconcile.line.wizard',inverse_name='wizard_id',string='Lineas')
    amount_payment = fields.Float('Monto a conciliar',compute=_compute_amount_payment)
    payment_move_line_id = fields.Many2one('account.move.line','Linea contable pago')
    selected_amount = fields.Float('Monto seleccionado',compute=_compute_selected_amount,store=True)

class PaymentReconcileLineWizard(models.TransientModel):
    _name = 'payment.reconcile.line.wizard'
    _description = 'payment.reconcile.line.wizard'

    def _compute_amount_residual(self):
        for rec in self:
            rec.amount_residual = rec.move_line_id.amount_residual

    wizard_id = fields.Many2one('payment.reconcile.wizard',string='Wizard')
    move_line_id = fields.Many2one('account.move.line','Linea Factura')
    account_id = fields.Many2one('account.account','Cuenta Contable',related='move_line_id.account_id')
    move_id = fields.Many2one('account.move','Factura',related='move_line_id.move_id')
    amount_residual = fields.Float('Monto residual',compute=_compute_amount_residual)
    selected = fields.Boolean('Selected')
