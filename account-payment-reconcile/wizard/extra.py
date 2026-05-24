from odoo import models, fields, api

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model
    def _get_currency_rate(self, company_currency_id, payment_currency_id, payment_date):
        currency_rate_obj = self.env['res.currency.rate']
        # Buscar la tasa de cambio más cercana a la fecha de pago
        currency_rate = currency_rate_obj.search([('currency_id', '=', payment_currency_id),
                                                   ('name', '<=', payment_date),
                                                   ('company_id', '=', self.env.company.id)],
                                                 order='name desc', limit=1)
        if not currency_rate:
            # Si no se encuentra ninguna tasa de cambio, utilizar la tasa del día anterior
            currency_rate = currency_rate_obj.search([('currency_id', '=', payment_currency_id),
                                                       ('name', '<', payment_date),
                                                       ('company_id', '=', self.env.company.id)],
                                                     order='name desc', limit=1)
        if not currency_rate:
            # Si aún no se encuentra ninguna tasa de cambio, utilizar la tasa base de la empresa
            currency_rate = 1.0 / self.env.company.currency_id.rate
        else:
            currency_rate = currency_rate.rate
        # Convertir a la moneda base de la empresa
        return 1.0 / (currency_rate / self.env.company.currency_id.rate)

    def _create_exchange_difference_move(self):
        """Crear un asiento contable por la diferencia cambiaria"""
        move_obj = self.env['account.move']
        move_line_obj = self.env['account.move.line']

        company_currency_id = self.env.company.currency_id.id
        payment_currency_id = self.currency_id.id
        payment_date = self.payment_date

        if payment_currency_id == company_currency_id:
            # Si la moneda del pago es la misma que la moneda de la empresa, no es necesaria una diferencia cambiaria
            return

        currency_rate = self._get_currency_rate(company_currency_id, payment_currency_id, payment_date)

        amount_currency = self.amount * -1
        amount_residual_currency = self.amount_residual * -1
        residual_currency = self.residual * -1

        # Crear las líneas del asiento contable
        move_lines = [
            {
                'name': self.name or '/',
                'account_id': self.partner_id.property_account_receivable_id.id,
                'debit': residual_currency,
                'credit': 0,
                'currency_id': payment_currency_id,
                'amount_currency': amount_residual_currency,
                'partner_id': self.partner_id.id,
            },
            {
                'name': self.name or '/',
                'account_id': self.journal_id.default_debit_account_id.id,
                'debit': 0,
                'credit': residual_currency,
                'currency_id': payment_currency_id,
                'amount_currency': amount_residual_currency,
                'partner_id': self.partner_id.id,
            },
            {
                'name': self.name or '/',
                'account_id': self.journal_id.profit_account_id.id,
                'debit': amount_currency - residual_currency,
                'credit': residual_currency - amount_currency,
                '

        class AccountPayment(models.Model):
            _inherit = 'account.payment'

            def action_post(self):
                # Call the parent method
                res = super(AccountPayment, self).action_post()

                # Check if the payment has currency
                if self.currency_id:
                    # Compute the difference in currency
                    currency_diff = self.amount - self.currency_id._convert(
                        self.amount, self.journal_id.currency_id, self.company_id, self.payment_date)

                    # Create a move line for the difference in currency
                    diff_line = self._create_exchange_rate_difference_line(currency_diff)

                    # Add the move line to the payment move
                    self.move_id.write({'line_ids': [(0, 0, diff_line)]})

                return res

            def _create_exchange_rate_difference_line(self, amount):
                return {
                    'name': _('Exchange Rate Difference'),
                    'debit': amount > 0 and amount or 0.0,
                    'credit': amount < 0 and -amount or 0.0,
                    'account_id': self.journal_id.default_debit_account_id.id,
                    'partner_id': self.partner_id.id,
                    'currency_id': self.currency_id.id,
                }