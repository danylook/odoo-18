from odoo import models
from decimal import Decimal, ROUND_DOWN

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @property
    def website_price(self):
        price = super().website_price
        # Truncar a dos decimales hacia abajo
        return float(Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_DOWN))
    
    def _get_combination_info(self, combination=False, product_id=False, add_qty=1, pricelist_id=False, parent_combination=False, only_template=False, **kwargs):
        res = super()._get_combination_info(combination, product_id, add_qty, pricelist_id, parent_combination, only_template, **kwargs)

        # Si tienes un pricelist con moneda igual a la funcional, puedes aplicar redondeo
        if res.get('price') and pricelist_id:
            pricelist = self.env['product.pricelist'].browse(pricelist_id)
            company_currency = self.env.company.currency_id
            if pricelist.currency_id == company_currency:
                price_with_tax = res.get('price')  # Precio con impuestos ya calculado
                price_with_tax_rounded = round(price_with_tax)

                taxes = self.taxes_id.compute_all(
                    price_with_tax,
                    currency=pricelist.currency_id,
                    quantity=1.0,
                    product=self,
                    partner=self.env.user.partner_id
                )
                tax_percent = sum(t.amount / 100.0 for t in self.taxes_id if t.amount_type == 'percent')

                if tax_percent:
                    price_unit_calc = Decimal(str(price_with_tax_rounded)) / (Decimal('1') + Decimal(str(tax_percent)))
                else:
                    price_unit_calc = Decimal(str(price_with_tax_rounded))

                price_unit_calc = price_unit_calc.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                print(f'\033[94m[DEBUG COMBO] price_with_tax={price_with_tax} price_with_tax_rounded={price_with_tax_rounded} tax_percent={tax_percent} price_unit_calc={float(price_unit_calc)}\033[0m')
                res['price'] = float(price_unit_calc)

        return res