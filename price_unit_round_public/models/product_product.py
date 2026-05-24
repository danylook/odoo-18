from odoo import models
from decimal import Decimal, ROUND_DOWN

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @property
    def website_price(self):
        price = super().website_price
        return float(Decimal(str(price)).quantize(Decimal('0.01'), rounding=ROUND_DOWN))