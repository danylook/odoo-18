# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    order_line_image = fields.Binary(string='Image', related='product_id.image_1920')
