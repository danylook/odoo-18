# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.depends('currency_id', 'journal_id')
    def _compute_display_exchange_rate(self):
        for rec in self:
            rec.display_exchange_rate = (
                rec.currency_id
                and rec.journal_id.default_account_id.currency_id
                and rec.currency_id != rec.journal_id.default_account_id.currency_id
            )

    @api.depends('exchange_rate', 'amount')
    def _compute_converted_amount(self):
        for rec in self:
            if rec.exchange_rate > 0:
                rec.converted_amount = rec.amount * rec.exchange_rate
            else:
                rec.converted_amount = rec.amount

    display_exchange_rate = fields.Boolean(
        string='display_exchange_rate',
        compute='_compute_display_exchange_rate',
        store=True,
    )
    exchange_rate = fields.Float(string='Tipo de cambio', default=1)
    amount_uyu = fields.Float(string='Monto UYU')
    converted_amount = fields.Float(
        string='Monto convertido',
        compute='_compute_converted_amount',
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('amount_uyu', 0) > 0:
                if not vals.get('exchange_rate'):
                    raise ValidationError(_('Debe ingresar el tipo de cambio'))
                vals['amount'] = vals['amount_uyu'] / vals['exchange_rate']
        return super().create(vals_list)

    def write(self, vals):
        if 'exchange_rate' in vals and vals.get('exchange_rate', 0) == 0:
            raise ValidationError(_('Tipo de cambio debe ser mayor a 0'))
        if vals.get('amount_uyu', 0) > 0:
            for rec in self:
                rate = vals.get('exchange_rate') or rec.exchange_rate
                if not rate:
                    raise ValidationError(_('Debe ingresar el tipo de cambio'))
                vals['amount'] = vals['amount_uyu'] / rate
        return super().write(vals)

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        """Override to apply custom exchange rate when set."""
        if self.exchange_rate > 0 and force_balance is None and not write_off_line_vals:
            if self.amount_uyu > 0:
                force_balance = self.amount_uyu
            else:
                force_balance = self.amount * self.exchange_rate
        return super()._prepare_move_line_default_vals(
            write_off_line_vals=write_off_line_vals,
            force_balance=force_balance,
        )
