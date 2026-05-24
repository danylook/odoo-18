# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_image_true = fields.Boolean(
        string="Show Image",
        compute="_compute_is_image_true"
    )

    def _compute_is_image_true(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'sale_product_image_UYU.is_show_product_image_in_sale_report'
        )
        for rec in self:
            rec.is_image_true = bool(param)
