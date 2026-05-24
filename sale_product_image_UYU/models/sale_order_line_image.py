# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    order_line_image = fields.Binary(
        string="Image",
        related="product_id.image_1920",
        help='Product Image in Sale Order Line'
    )
