# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import date

class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_check = fields.Boolean(string='Es cheque', related='journal_id.is_check')
    check_number = fields.Integer(
        string='Numero',
        readonly=False,
        compute="_compute_check_number_readonly",
        store=True
    )
    bank_id = fields.Many2one(
        'res.bank',
        string='Banco',
        readonly=False,
        compute="_compute_bank_id_readonly",
        store=True
    )
    payment_date = fields.Date(
        string='Fecha de pago',
        default=fields.Date.today(),
        readonly=False,
        compute="_compute_payment_date_readonly",
        store=True
    )
    deposit_date = fields.Date(
        string='Fecha de deposito',
        default=fields.Date.today(),
        readonly=False,
        compute="_compute_deposit_date_readonly",
        store=True
    )
    check_state = fields.Selection(
        selection=[('holding', 'En mano'), ('deposited', 'Depositado'), ('cancel', 'Cancelado')],
        string='Estado del cheque',
        default='holding'
    )
    check_ids = fields.One2many(
        comodel_name='account.check',
        inverse_name='payment_id',
        string='Cheques'
    )
    is_readonly = fields.Boolean(compute="_compute_is_readonly", store=True)
    readonly = fields.Boolean(string='Read Only', compute='_compute_check_number_readonly', store=True)
    check_amount = fields.Float('Monto de cheques', compute='_compute_check_amount')

    @api.depends('state')
    def _compute_is_readonly(self):
        for rec in self:
            rec.is_readonly = rec.state != 'draft'

    @api.depends('state')
    def _compute_check_number_readonly(self):
        for rec in self:
            rec.readonly = rec.state != 'draft'

    @api.depends('state')
    def _compute_bank_id_readonly(self):
        for rec in self:
            rec.readonly = rec.state != 'draft'

    @api.depends('state')
    def _compute_payment_date_readonly(self):
        for rec in self:
            rec.readonly = rec.state != 'draft'

    @api.depends('state')
    def _compute_deposit_date_readonly(self):
        for rec in self:
            rec.readonly = rec.state != 'draft'

    def _compute_check_amount(self):
        for rec in self:
            res = 0
            for check in rec.check_ids:
                res += check.amount
            rec.check_amount = res

    def action_post(self):
        for rec in self:
            if rec.check_ids:
                for check in rec.check_ids:
                    if check.check_number == 0:
                        raise ValidationError('Debe ingresar el numero de cheque')
                    if not check.bank_id:
                        raise ValidationError('Debe ingresar el banco')
                    if not check.payment_date:
                        raise ValidationError('Debe ingresar la fecha de pago')
        for rec in self:
            if rec.check_ids:
                rec.amount_uyu = rec.check_amount
        return super(AccountPayment, self).action_post()

    def write(self, vals):
        for rec in self:
            if 'check_ids' in vals:
                vals['amount'] = rec.check_amount
        return super(AccountPayment, self).write(vals)

class AccountCheck(models.Model):
    _name = 'account.check'
    _description = 'account.check'
    bank_currency_id = fields.Many2one('res.currency', string='Currency', related='currency_id',
                                     readonly=True)

    def btn_deposit_check(self):
        self.ensure_one()
        # print("aca  self.currency_id.id",  self.currency_id.id )
        # print("aca  self.bank_currency_id", self.bank_currency_id)
        # print("aca llego 2")
        # print("aca  self.date", self.deposit_date)

        if not self.deposit_journal_id:
            raise ValidationError('No se selecciono banco a depositar')

        if self.payment_id.state == 'posted':
            journal_id = self.deposit_journal_id
            print("aca llego 3", self.deposit_journal_id, ' ', self.display_name)
            vals_move = {
                'journal_id': journal_id.id,
                'date': self.deposit_date,
                #'name': 'Asiento deposito cheque aca lo hace mal %s'%(self.display_name),
                'ref': self.display_name,
            }
            move_id = self.env['account.move'].create(vals_move)
            # print("aca llego journal_id.currency_id", journal_id.currency_id)
            # print("aca llego journal_id.currency_id.id", journal_id.currency_id.id)
            # print("self.payment_id.company_id.currency_id.id", self.payment_id.company_id.currency_id.id)
            amount = abs(self.payment_id.amount_company_currency_signed)
            if self.currency_id.id == self.payment_id.company_id.currency_id.id:
               # print("misma moneda que el sistema")
                amount = abs(self.amount)
                self.deposit_move_id = move_id.id

                vals_debit = {
                    'move_id': move_id.id,
                    'date': self.deposit_date,
                    'account_id': journal_id.default_account_id.id,
                    'debit': amount,
                    'name': 'Debito deposito de cheque %s'%(self.display_name),
                    }
                debit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_debit)
                vals_credit = {
                    'move_id': move_id.id,
                    'date': self.deposit_date,
                    'account_id': self.payment_id.journal_id.default_account_id.id,
                    'credit': amount,
                    'name': 'Credito deposito de cheque %s'%(self.display_name),
                }
                credit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_credit)
            else:
                amount = abs(self.amount)
                #print("diferente moneda que el sistema")
                #if self.payment_id.exchange_rate == 0:
                #raise ValidationError('No se puede ingresar un cheque EN UNA CUENTA CON DIFERENTE MONEDA') #sin tipo de cambio')
                amount_currency = abs(self.amount) / self.payment_id.exchange_rate
                #print("valor en pesos",amount_currency)
                self.deposit_move_id = move_id.id

                vals_debit = {
                    'move_id': move_id.id,
                    'date': self.deposit_date,
                    'account_id': journal_id.default_account_id.id,
                    'debit': amount,
                    'name': 'Debito deposito de cheque %s'%(self.display_name),
                    'currency_id': journal_id.currency_id.id,
                    'amount_currency': amount_currency,
                    }
                debit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_debit)
                vals_credit = {
                    'move_id': move_id.id,
                    'date': self.deposit_date,
                    'account_id': self.payment_id.journal_id.default_account_id.id,
                    'credit': amount,
                    'name': 'Credito deposito de cheque %s'%(self.display_name),
                    'currency_id': journal_id.currency_id.id,
                    'amount_currency': amount_currency * (-1),
                }
                credit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_credit)
            move_id.action_post()
            self.state = 'deposited'
    def btn_cancel_deposit_check(self):
        self.ensure_one()
        # print("aca  self.currency_id.id",  self.currency_id.id )
        # print("aca  self.bank_currency_id", self.bank_currency_id)
        # print("aca llego 2")
        # print("aca  self.date", self.deposit_date)

        if not self.deposit_journal_id:
            raise ValidationError('No se selecciono banco a depositar')
#            print("aca llego 3")
        if self.payment_id.state == 'posted':
            journal_id = self.deposit_journal_id
            vals_move = {
                'journal_id': journal_id.id,
                'date': self.deposit_date,
                'name': 'Asiento deposito cheque %s'%(self.display_name),
                'ref': self.display_name,
            }
            move_id = self.env['account.move'].create(vals_move)
            # print("aca llego journal_id.currency_id", journal_id.currency_id)
            # print("aca llego journal_id.currency_id.id", journal_id.currency_id.id)
            # print("self.payment_id.company_id.currency_id.id", self.payment_id.company_id.currency_id.id)
            amount = abs(self.payment_id.amount_company_currency_signed)
            if self.currency_id.id == self.payment_id.company_id.currency_id.id:
                print("misma moneda que el sistema")
                amount = abs(self.amount)
                self.deposit_move_id = move_id.id

                vals_debit = {
                    'move_id': move_id.id,
                    'date': self.deposit_date,
                    'account_id': journal_id.default_account_id.id,
                    'debit': amount,
                    'name': 'Debito deposito de cheque %s'%(self.display_name),
                    }
                debit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_debit)
                vals_credit = {
                    'move_id': move_id.id,
                    'date': self.deposit_date,
                    'account_id': self.payment_id.journal_id.default_account_id.id,
                    'credit': amount,
                    'name': 'Credito deposito de cheque %s'%(self.display_name),
                }
                credit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_credit)
            else:
                amount = abs(self.amount)
                #print("diferente moneda que el sistema")
                #if self.payment_id.exchange_rate == 0:
                #raise ValidationError('No se puede ingresar un cheque EN UNA CUENTA CON DIFERENTE MONEDA') #sin tipo de cambio')
                amount_currency = abs(self.amount) / self.payment_id.exchange_rate
                #print("valor en pesos",amount_currency)
                self.deposit_move_id = move_id.id

                vals_debit = {
                    'move_id': move_id.id,
                    'date': self.deposit_date,
                    'account_id': journal_id.default_account_id.id,
                    'debit': amount,
                    'name': 'Debito deposito de cheque %s'%(self.display_name),
                    'currency_id': journal_id.currency_id.id,
                    'amount_currency': amount_currency,
                    }
                debit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_debit)
                vals_credit = {
                    'move_id': move_id.id,
                    'date': self.deposit_date,
                    'account_id': self.payment_id.journal_id.default_account_id.id,
                    'credit': amount,
                    'name': 'Credito deposito de cheque %s'%(self.display_name),
                    'currency_id': journal_id.currency_id.id,
                    'amount_currency': amount_currency * (-1),
                }
                credit_id = self.env['account.move.line'].with_context({'check_move_validity': False}).create(vals_credit)
            move_id.action_post()
            self.state = 'deposited'
    def _compute_name(self):
        for rec in self:
            rec.name = '%s %s'%(rec.check_number,rec.bank_id.display_name)
    # def _compute_currency_id(self):
    #     for rec in self:
    #         rec.currency_id = fields.Many2one(
    #             related='journal_id.default_account_id.currency_id',
    #             string='Currency',
    #             store=True)
    #         print('moneda del banco', rec.currency_id)
    name = fields.Char('Nombre', compute=_compute_name)
    payment_id = fields.Many2one('account.payment',string='Pagos')
    check_number = fields.Integer(string='Numero')
    bank_id = fields.Many2one('res.bank',string='Banco')
    deposit_journal_id = fields.Many2one('account.journal', string='Banco de deposito')
    payment_date = fields.Date(string='Fecha de pago', default=fields.Date.today())
    deposit_date = fields.Date(string='Fecha de deposito', default=fields.Date.today())
    state = fields.Selection(selection=[('holding' , 'En mano') , ('deposited','Depositado'),('cancel','Cancelado')],
            string='Estado del cheque',
            default='holding')
    amount = fields.Float('Monto')
    currency_id = fields.Many2one('res.currency', string='Moneda', related='payment_id.journal_id.default_account_id.currency_id')
    #currency_id = fields.Many2one('res.currency', string='Moneda', compute=_compute_name)
    # ,related='journal_id
    # .default_account_id.currency_id')
    deposit_move_id = fields.Many2one('account.move', string='Asiento de deposito')
