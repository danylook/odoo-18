# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    show_product_image_in_report_purchase = fields.Boolean(
        string='Show Product Image In Report',
        config_parameter='purchase_orderline_image.show_product_image_in_report_purchase',
    )
