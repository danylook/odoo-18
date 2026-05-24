from odoo import models, api, fields
from decimal import Decimal, ROUND_DOWN

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('product_id', 'tax_ids', 'quantity')
    def _onchange_product_force_public_price_round(self):
        move = self.move_id
        product = self.product_id

        if not product or not move or not move.invoice_origin:
            return

        SaleOrder = self.env['sale.order']
        origin_order = SaleOrder.search([('name', '=', move.invoice_origin)], limit=1)

        # Aplica a cualquier lista de precios con la moneda funcional de la compañía (sin usar is_public)
        if origin_order and origin_order.pricelist_id \
           and origin_order.pricelist_id.currency_id == move.company_id.currency_id:

            price_base = product.lst_price
            product_currency = getattr(product, 'currency_id', None)
            pricelist_currency = origin_order.pricelist_id.currency_id
            company_currency = move.company_id.currency_id

            # Si el producto tiene un currency_id y es diferente al de la lista, convertir
            if product_currency and product_currency != pricelist_currency:
                price_base = product_currency._convert(
                    product.lst_price,
                    pricelist_currency,
                    move.company_id,
                    move.invoice_date or move.create_date or fields.Date.today()
                )

            taxes = self.tax_ids.compute_all(
                price_base,
                currency=move.currency_id,
                quantity=1.0,
                product=product,
                partner=move.partner_id
            )
            price_with_tax = taxes['total_included']
            price_with_tax_rounded = round(price_with_tax)

            # Calcular el price_unit para que el total con impuestos sea el redondeado
            tax_percent = 0.0
            for t in self.tax_ids:
                if t.amount_type == 'percent':
                    tax_percent += t.amount / 100.0
            if tax_percent:
                divisor = Decimal('1.0') + Decimal(str(tax_percent))
                price_with_tax_target = Decimal(str(price_with_tax_rounded)).quantize(Decimal('1.0'))
                # Buscar el price_unit más alto que NO supere el objetivo
                new_price = (price_with_tax_target / divisor).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                last_valid = new_price
                for i in range(100):  # hasta 1 peso arriba
                    price_with_tax_check = (new_price * divisor).quantize(Decimal('1.0'))  # TRUNCAR a entero para la factura
                    if price_with_tax_check > price_with_tax_target:
                        new_price = last_valid
                        break
                    if price_with_tax_check == price_with_tax_target:
                        break
                    last_valid = new_price
                    new_price += Decimal('0.01')
            else:
                new_price = Decimal(str(price_with_tax_rounded)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            print(f'\033[95m[DEBUG ROUND AML] lst_price={product.lst_price} price_base={price_base} price_with_tax={price_with_tax} price_with_tax_rounded={price_with_tax_rounded} price_unit_calc={float(new_price)}\033[0m')
            self.price_unit = float(new_price)
        elif product and move and move.company_id and product.lst_price and move.currency_id == move.company_id.currency_id:
            # Si no hay orden de venta, pero la moneda es funcional, redondea el precio unitario
            self.price_unit = float(Decimal(str(product.lst_price)).quantize(Decimal('0.01'), rounding=ROUND_DOWN))
