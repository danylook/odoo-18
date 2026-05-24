# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.depends_context('company')
    def _compute_is_image_true(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'purchase_orderline_image.show_product_image_in_report_purchase'
        )
        for rec in self:
            rec.is_image_true = bool(param) and param != 'False'

    is_image_true = fields.Boolean(
        string='Show Image in Report',
        compute='_compute_is_image_true',
    )
