from odoo import models, api, fields
from decimal import Decimal, ROUND_HALF_UP, getcontext, ROUND_DOWN

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_id', 'tax_id', 'product_uom_qty')
    def _onchange_product_id_force_public_price_round(self):
        order = self.order_id
        product = self.product_id

        if not product or not order or not order.pricelist_id:
            return

        # Determinar el precio base en la moneda de la lista de precios
        price_base = product.lst_price
        product_currency = getattr(product, 'currency_id', None)
        pricelist_currency = order.pricelist_id.currency_id
        company_currency = order.company_id.currency_id

        # Si el producto tiene un currency_id y es diferente al de la lista, convertir
        if product_currency and product_currency != pricelist_currency:
            price_base = product_currency._convert(
                product.lst_price,
                pricelist_currency,
                order.company_id,
                order.date_order or order.create_date or fields.Date.today()
            )
        # Aplica a cualquier lista de precios con la moneda funcional de la compañía (sin is_public)
        if pricelist_currency == company_currency:
            taxes = self.tax_id.compute_all(
                price_base,
                currency=order.currency_id,
                quantity=1.0,
                product=product,
                partner=order.partner_id
            )
            price_with_tax = taxes['total_included']
            price_with_tax_rounded = round(price_with_tax)

            # Calcular el price_unit para que el total con impuestos sea el redondeado
            tax_percent = 0.0
            for t in self.tax_id:
                if t.amount_type == 'percent':
                    tax_percent += t.amount / 100.0
            if tax_percent:
                price_unit_calc = Decimal(str(price_with_tax_rounded)) / (Decimal('1') + Decimal(str(tax_percent)))
                price_unit_calc = price_unit_calc.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            else:
                price_unit_calc = Decimal(str(price_with_tax_rounded)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            print(f'\033[95m[DEBUG ROUND] lst_price={product.lst_price} price_base={price_base} price_with_tax={price_with_tax} price_with_tax_rounded={price_with_tax_rounded} price_unit_calc={float(price_unit_calc)}\033[0m')
            self.price_unit = float(price_unit_calc)
