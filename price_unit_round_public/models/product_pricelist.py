from odoo import models
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP,ROUND_HALF_EVEN,ROUND_HALF_DOWN,ROUND_05UP,ROUND_UP

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    def _compute_price_rule(self, products_qty_partner, quantity=None, date=False, uom_id=False, *args, **kwargs):
        res = super()._compute_price_rule(products_qty_partner, quantity=quantity, date=date, uom_id=uom_id, *args, **kwargs)

        company_currency = self.env.company.currency_id

        for item in products_qty_partner:
            # Soportar ambos formatos: (product, qty, partner) o solo product
            if isinstance(item, (tuple, list)) and len(item) == 3:
                product, qty, partner = item
            elif isinstance(item, (tuple, list)) and len(item) == 1:
                product = item[0]
                qty = quantity or 1.0
                partner = False
            else:
                product = item
                qty = quantity or 1.0
                partner = False
            print(f'\033[92m[DEBUG PRICELIST xxxx] computo precio para product={product.id} qty={qty} partner={partner}\033[0m')
            if self.currency_id != company_currency:
                print(f'\033[92m[DEBUG PRICELIST xxxx] computo precio para product=y moneda no es la funcional\033[0m')
                continue  # Solo aplicar si la moneda es la funcional

            price, rule_id = res.get(product.id, (0.0, False))

            # Si el precio base es cero, no aplicar lógica de ajuste
            if not price:
                print(f'\033[91m[DEBUG PRICELIST xxxx] product={product.display_name} NO TIENE PRECIO BASE, se omite ajuste\033[0m')
                continue

            # Obtener impuestos aplicables
            taxes = product.taxes_id.compute_all(
                price,
                currency=self.currency_id,
                quantity=qty,
                product=product,
                partner=partner,
            )
            price_with_tax = taxes['total_included']
            # Ajustar SIEMPRE hacia arriba: si hay centavos, sumar un peso más
            if price_with_tax % 1 > 0:
                price_with_tax_rounded = int(price_with_tax) + 1
            else:
                price_with_tax_rounded = int(price_with_tax)

            # Calcular el porcentaje de impuestos con precisión decimal
            tax_percent = 0.0
            for t in product.taxes_id:
                if t.amount_type == 'percent':
                    tax_percent += t.amount / 100.0
                print(f'\033[91m[DEBUG PRICELIST xxxx] computo precio para product={product.id} tax_percent={tax_percent} amount={t.amount}\033[0m')
            if tax_percent:
                divisor = Decimal('1.0') + Decimal(str(tax_percent))
                price_with_tax_target = Decimal(str(price_with_tax_rounded))#.quantize(Decimal('1.0'))
                new_price = (price_with_tax_target / divisor)#.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                last_valid = new_price
                found = False
                print(f'\033[91m[DEBUG PRICELIST xxxx] computo precio para product={product.id} sin ajustartax_percent={tax_percent} amount={t.amount} price_with_tax_rounded={price_with_tax_rounded} divisor={divisor} new_price={new_price} last_valid={last_valid} found={found} price_with_tax_target\033[0m')
                for i in range(100):  # hasta 1 peso arriba
                    price_with_tax_check = (new_price * divisor)#.quantize(Decimal('0.01'))  # TRUNCAR a entero
                    print(f'\033[91m[DEBUG PRICELIST xxxx] computo precio para product={product.id} sin ajustartax_percent={tax_percent} amount={t.amount} price_with_tax_rounded={price_with_tax_rounded} divisor={divisor} new_price={new_price} last_valid={last_valid} found={found} price_with_tax_target i={i} price_with_tax_check={price_with_tax_check}\033[0m')
                    if price_with_tax_check > price_with_tax_target:
                        new_price = last_valid
                        break
                    if price_with_tax_check == price_with_tax_target:
                        found = True
                        break
                    last_valid = new_price
                    new_price -= Decimal('0.01')
                if not found:
                    new_price = last_valid  # Asegura que siempre se use el último válido
            else:
                new_price = Decimal(str(price_with_tax_rounded)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
                print(f'\033[92m[DEBUG PRICELIST xxxx] product={product.display_name} no tiene impuestos\033[0m')

            print(f'\033[92m[DEBUG PRICELIST xxxx] product={product.display_name} original_price={price} price_with_tax={price_with_tax} price_with_tax_rounded={price_with_tax_rounded} new_price={float(new_price)}\033[0m')
            res[product.id] = (float(new_price), rule_id)
            # No agregar claves adicionales al dict, solo modificar el price_unit como tu lógica requiere

        return res
