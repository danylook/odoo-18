from odoo import models, api, fields
from datetime import date


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model_create_multi
    def create(self, vals_list):
        updated_vals_list = []
        company = self.env.company
        second_currency = company.currency_cost_id

        for vals in vals_list:
            stock_valuation_account = None
            stock_output_account = None
            stock_input_account = None

            if 'product_id' in vals and vals['product_id']:
                product = self.env['product.product'].browse(vals['product_id'])
                categ = product.categ_id
                if categ:
                    stock_valuation_account = categ.property_stock_valuation_account_id and categ.property_stock_valuation_account_id.code
                    stock_output_account = categ.property_stock_account_output_categ_id and categ.property_stock_account_output_categ_id.code
                    stock_input_account = categ.property_stock_account_input_categ_id and categ.property_stock_account_input_categ_id.code

            if second_currency and (stock_output_account or stock_valuation_account or stock_input_account):
                if 'account_id' in vals and vals['account_id']:
                    account = self.env['account.account'].browse(vals['account_id'])
                    if account.code in filter(None, [stock_output_account, stock_valuation_account, stock_input_account]):
                        move_date = vals.get('date', fields.Date.context_today(self))
                        rate = self.env['res.currency.rate'].search([
                            ('currency_id', '=', second_currency.id),
                            ('name', '<=', move_date)
                        ], limit=1, order='name desc')
                        if rate:
                            inverse_rate = rate.inverse_rate

                            amount_currency = 0.0
                            if vals.get('debit', 0.0):
                                amount_currency = vals.get('debit', 0.0)
                            elif vals.get('credit', 0.0):
                                amount_currency = -abs(vals.get('credit', 0.0))

                            debit = vals.get('debit', 0.0) * inverse_rate
                            credit = vals.get('credit', 0.0) * inverse_rate

                            vals['debit'] = debit
                            vals['credit'] = credit
                            vals['amount_currency'] = amount_currency
                            vals['currency_id'] = second_currency.id

            updated_vals_list.append(vals)

        return super().create(updated_vals_list)
