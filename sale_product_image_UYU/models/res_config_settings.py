# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    is_show_product_image_in_sale_report = fields.Boolean(
        string="Show Product Image",
        config_parameter='sale_product_image_UYU.is_show_product_image_in_sale_report',
        help='Show product image in sale report'
    )
