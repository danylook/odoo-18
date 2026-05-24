from odoo import tools,fields, models, api, _
from datetime import date,datetime
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero

class AccountMove(models.Model):
    _inherit = 'account.move'

    def invoice_small_cents_reconcile(self):
        for rec in self.filtered(lambda m: m.move_type in ['out_invoice','entry'] \
                and m.state == 'posted' and m.amount_residual > 0):
            journal_id = self.env['account.journal'].search([('code','=','CENT')])
            aml_obj = self.env['account.move.line']
            for inv_line in rec.line_ids:
                if inv_line.account_id.id == rec.partner_id.property_account_receivable_id.id:
                    aml_obj += inv_line
                    if rec.currency_id.id != rec.company_id.currency_id.id:
                        exchange_rate = round(inv_line.debit / inv_line.amount_currency,2)
                        # print('\033[93mtipo de cambio recibo\033[0m', exchange_rate)  # Amarillo
                        residual = inv_line.amount_residual_currency
                    else:
                        residual = inv_line.amount_residual
            debit_account_id = self.env['account.account'].search([('code','=','999001')])
            if not debit_account_id:
                raise ValidationError('No hay cuenta 999001 para perdida diferencia de efectivo')
            if not journal_id:
                raise ValidationError('No hay diario para ajustes de centavos')
            if residual == 0:
                raise ValidationError('Se quiere ajustar una factura sin deuda')
            vals_move = {
                'journal_id': journal_id.id,
                'name': 'Asiento ajuste de pago %s'%(rec.display_name),
                'ref': 'Asiento ajuste de pago %s'%(rec.display_name),
                'partner_id': rec.partner_id.id,
                }
            move_id = self.env['account.move'].create(vals_move)
            vals_debit = {
                'move_id': move_id.id,
                'account_id': debit_account_id.id,
                'currency_id': rec.currency_id.id,
                'amount_currency': residual,
                'debit': residual * exchange_rate,
                'partner_id': rec.partner_id.id,
                'name': 'Debito diferencia de efectivo %s'%(rec.display_name),
                }
            debit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_debit)
            vals_credit = {
                'move_id': move_id.id,
                'account_id': rec.partner_id.property_account_receivable_id.id,
                'currency_id': rec.currency_id.id,
                'amount_currency': residual * (-1),
                'credit': residual * exchange_rate,
                'partner_id': rec.partner_id.id,
                'name': 'Credito diferencia de efectivo %s'%(rec.display_name),
                }
            credit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_credit)
            move_id.post()
            aml_obj += credit_id
            aml_obj.reconcile()



class AccountPayment(models.Model):
    _inherit = 'account.payment'

    def action_post(self):
        # print('\033[96mcreo un pago\033[0m')  # Cyan
        res = super(AccountPayment, self).action_post()
        for rec in self:
            # print(f'\033[93mTasa de cambio (venta -> funcional):\033[0m', getattr(rec, 'exchange_rate', 'N/A'))  # Amarillo
            if getattr(rec, 'exchange_rate', 1) == 1:
                # print(f'\033[91mTasa de cambio equivocada: {getattr(rec, "exchange_rate", "N/A")}\033[0m')  # Rojo
                pass
            # print(f'\033[92mDía de pago:\033[0m', rec.date)  # Verde
            # Mostrar monedas usadas en la conversión
            # print(f'\033[96mMoneda funcional (base UYU):\033[0m', rec.company_id.currency_id)
            # print(f'\033[96mMoneda de la venta (base USD):\033[0m', rec.currency_id)
            if rec.reconcile_ids:
                aml_obj = self.env['account.move.line']
                payment_line = None
                for line in rec.move_id.line_ids:
                    if line.account_id.id == rec.partner_id.property_account_receivable_id.id:
                        payment_line = line
                if payment_line:
                    aml_obj += payment_line
                    amount_uyu = 0
                    for reconcile_id in rec.reconcile_ids:
                        aml_obj += reconcile_id.move_line_id
                        amount_uyu = reconcile_id.amount_residual
                    aml_obj.reconcile()
                    recon_ids = self.env['account.partial.reconcile'].search([('credit_move_id','=',payment_line.id)])

            # print('\033[96mmoneda del pago\033[0m', rec.currency_id, ' \033[96mmoneda de la cuenta\033[0m', rec.journal_id.default_account_id.currency_id.id)
            if rec.currency_id.id != rec.journal_id.default_account_id.currency_id.id:
                # Usar la moneda funcional como base UYU y la moneda de la venta como base USD
                base_uyu = rec.company_id.currency_id
                base_usd = rec.currency_id
                amount_payment = base_usd._convert(
                    rec.amount,
                    base_uyu,
                    rec.company_id,
                    rec.date or fields.Date.today()
                )
                conversion_rate = base_usd._convert(
                    1,
                    base_uyu,
                    rec.company_id,
                    rec.date or fields.Date.today()
                )
                amount_uyu = rec.currency_id._convert(
                    rec.amount,
                    rec.company_id.currency_id,
                    rec.company_id,
                    rec.date or fields.Date.today()
                )
                residual = amount_uyu - amount_payment
                # Solo buscar el diario y crear asiento si hay diferencia de moneda
                journal_id = self.env['account.journal'].search([('code','=','CAMBI')])
                if not journal_id:
                    # print('\033[94mNo hay diario de diferencia de cambio, pero la transacción continúa porque no hay diferencia de moneda.\033[0m')
                    pass
                else:
                    narration = 'Pago %s \nMonto en DOL%s\nTipo de cambio %s\nTipo de cambio pago %s'%(rec.name,rec.amount,rec.exchange_rate,conversion_rate)
                    # print('\033[96mnarration\033[0m', narration)  # Cyan
                    # print('\033[93mvals_move\033[0m', vals_move)  # Amarillo
                    # print('\033[92mexchange_move_id\033[0m', rec.exchange_move_id)  # Verde
                    vals_move = {
                        'journal_id': journal_id.id,
                        'date': rec.date,
                        'name': 'Asiento diferencia de cambio pago %s %s'%(rec.display_name,rec.date),
                        'ref': '%s'%(rec.display_name),
                        'move_type': 'entry',
                        'narration': narration,
                        }
                    move_id = self.env['account.move'].create(vals_move)
                    rec.exchange_move_id = move_id.id
                    if residual > 0:
                        vals_credit = {
                            'date': rec.date,
                            'move_id': move_id.id,
                            'account_id': self.env['account.account'].search([('code','=','430200')]).id,
                            'credit': residual,
                            'name': 'Credito diferencia de cambio %s'%(rec.display_name),
                            }
                        credit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_credit)
                        vals_debit = {
                            'date': rec.date,
                            'move_id': move_id.id,
                            #'account_id': rec.partner_id.property_account_receivable_id.id,
                            'account_id': rec.journal_id.default_account_id.id,
                            'debit': residual,
                            'name': 'Debito diferencia de cambio %s'%(rec.display_name),
                            }
                        debit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_debit)
                    else:
                        vals_credit = {
                            'date': rec.date,
                            'move_id': move_id.id,
                            #'account_id': rec.partner_id.property_account_receivable_id.id,
                            'account_id': rec.journal_id.default_account_id.id,
                            'credit': abs(residual),
                            'name': 'Credito diferencia de cambio %s'%(rec.display_name),
                            }
                        credit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_credit)
                        vals_debit = {
                            'date': rec.date,
                           'move_id': move_id.id,
                           'account_id': self.env['account.account'].search([('code','=','530200')]).id,
                           'debit': abs(residual),
                           'name': 'Debito diferencia de cambio %s'%(rec.display_name),
                            }
                        debit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_debit)
                    move_id.post()
            else:
                # print('\033[94mNo se requiere asiento de diferencia de cambio: monedas iguales\033[0m')
                pass
        return res

    class CustomAccountMove(models.Model):
        _inherit = 'account.move'

        @api.model
        def create_currency_exchange_diff_move(self, partner_id):
            # Buscar los pagos en moneda extranjera del partner
            payments = self.env['account.payment'].search([
                ('partner_id', '=', partner_id),
                ('currency_id', '!=', False)
            ])

            # Calcular la diferencia de cambio para cada pago
            diff_moves = payments._create_exchange_rate_difference_entries()

            # Combinar todas las diferencias de cambio en un solo asiento
            # diff_move = self.create({
            #     'partner_id': partner_id,
            #     'journal_id': < ID de diario para Currency Exchange Rate Difference >,
            #     'ref': 'Diferencia de cambio de pagos en moneda extranjera',
            #     'line_ids': [(0, 0, line) for diff in diff_moves for line in diff.line_ids],
            # })
            # return diff_move.id
            # Eliminado porque diff_move no está definido y no se implementa la lógica de combinación
            return True

    # def action_validate_payment(self):
    # # Realizar el pago
    #     res = super(AccountPayment, self).action_validate()
    #
    #         # Verificar si hay una diferencia cambiaria
    #         if self.currency_id and self.currency_id != self.journal_id.currency_id:
    #             # Crear el asiento contable por la diferencia cambiaria
    #             account_move_obj = self.env['account.move']
    #             debit_account_id = self.journal_id.default_debit_account_id.id
    #             credit_account_id = self.journal_id.default_credit_account_id.id
    #             debit_amount = 0
    #             credit_amount = 0
    #             if self.amount_currency > self.amount:
    #                 debit_amount = self.amount_currency - self.amount
    #             else:
    #                 credit_amount = self.amount - self.amount_currency
    #             move_lines = [(0, 0, {
    #                 'name': self.name,
    #                 'account_id': debit_account_id,
    #                 'debit': debit_amount,
    #                 'credit': credit_amount,
    #                 'currency_id': self.currency_id.id,
    #                 'amount_currency': debit_amount or -credit_amount,
    #             }), (0, 0, {
    #                 'name': self.name,
    #                 'account_id': credit_account_id,
    #                 'debit': credit_amount,
    #                 'credit': debit_amount,
    #                 'currency_id': self.currency_id.id,
    #                 'amount_currency': credit_amount or -debit_amount,
    #             })]
    #             move = account_move_obj.create({
    #                 'ref': self.communication or '',
    #                 'journal_id': self.journal_id.id,
    #                 'date': self.payment_date,
    #                 'line_ids': move_lines,
    #             })
    #
    #             # Validar el asiento contable por la diferencia cambiaria
    #             move.action_post()
    #
    #         return res

    def btn_add_invoices(self):
        self.ensure_one()
        if self.state not in ['draft']:
            raise ValidationError('El estado del documento es incorrecto 1')
        if self.payment_type not in ['inbound']:
            return
        domain = [
                ('move_id.partner_id.id','=',self.partner_id.id),
                ('move_id.state','=','posted'),
                ('account_id','=',self.partner_id.property_account_receivable_id.id),
                #('move_id.move_type','=','out_invoice'),
                ('account_id.reconcile','=',True),
                ('amount_residual','!=',0),
                ]
        for reconcile_id in self.reconcile_ids:
            reconcile_id.unlink()
        if self.payment_type == 'inbound':
            domain.append(('debit','>',0))
        amls = self.env['account.move.line'].search(domain)
        for aml in amls:
            vals_reconcile = {
                    'payment_id': self.id,
                    'move_line_id': aml.id,
                    }
            reconcile_id = self.env['account.payment.reconcile'].create(vals_reconcile)

    def btn_payment_reconcile(self):
        self.ensure_one()
        if self.state not in ['posted']:
            raise ValidationError('El estado del documento es incorrecto 3')
        if self.payment_type not in ['inbound']:
            raise ValidationError('El tipo del documento es incorrecto 4')
        domain = [
                ('move_id.partner_id.id','=',self.partner_id.id),
                ('move_id.state','=','posted'),
                ('move_id.move_type','=','out_invoice'),
                ('account_id','=',self.partner_id.property_account_receivable_id.id),
                ('account_id.reconcile','=',True),
                ('amount_residual','!=',0),
                ]
        if self.payment_type == 'inbound':
            domain.append(('debit','>',0))
        amls = self.env['account.move.line'].search(domain)
        payment_move_line_id = None
        for line in self.move_id.line_ids:
            if line.amount_residual < 0 and line.account_id.reconcile \
                    and line.account_id.id == self.partner_id.property_account_receivable_id.id:
                payment_move_line_id = line
        if not payment_move_line_id:
            raise ValidationError('No hay linea a conciliar')
        wizard_id = self.env['payment.reconcile.wizard'].create({
            'payment_id': self.id,
            'payment_move_line_id': payment_move_line_id.id,
            })
        for aml in amls:
            vals_line = {
                    'wizard_id': wizard_id.id,
                    'move_line_id': aml.id,
                    'selected': None,
                    }
            line_id = self.env['payment.reconcile.line.wizard'].create(vals_line)
        return {
               'name': _('Conciliar pago'),
               'res_model': 'payment.reconcile.wizard',
               'res_id': wizard_id.id,
               'view_mode': 'form',
               'type': 'ir.actions.act_window',
               'target': 'new',
               }

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            self.btn_add_invoices()

    reconcile_ids = fields.One2many(comodel_name='account.payment.reconcile',inverse_name='payment_id',string='Facturas')
    exchange_move_id = fields.Many2one('account.move',string='Asiento diferencia tipo de cambio')

class AccountPaymentReconcile(models.Model):
    _name = 'account.payment.reconcile'
    _description = 'account.payment.reconcile'

    def _compute_amounts(self):
        for rec in self:
            rec.amount = rec.move_line_id.debit
            rec.amount_residual = rec.move_line_id.amount_residual
            rec.amount_currency = rec.move_line_id.amount_currency
            rec.amount_residual_currency = rec.move_line_id.amount_residual_currency
            rec.currency_id = rec.move_line_id.currency_id.id

    payment_id = fields.Many2one('account.payment','Pago')
    move_line_id = fields.Many2one('account.move.line','Apunte contable')
    move_id = fields.Many2one(comodel_name='account.move',string='Factura',related='move_line_id.move_id')
    account_id = fields.Many2one('account.account','Cuenta contable')
    amount = fields.Float('Monto', compute='_compute_amounts')
    amount_residual = fields.Float('Monto pendiente', compute='_compute_amounts')
    amount_currency = fields.Float('Monto moneda', compute='_compute_amounts')
    amount_residual_currency = fields.Float('Monto pendiente moneda', compute='_compute_amounts')
    currency_id = fields.Many2one('res.currency', 'Moneda', compute='_compute_amounts')
