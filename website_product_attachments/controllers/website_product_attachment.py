# -*- coding: utf-8 -*-
import base64
import io

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleAttachments(WebsiteSale):

    def _prepare_product_values(self, product, category, search, **kwargs):
        values = super()._prepare_product_values(product, category, search, **kwargs)
        attachments = request.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'product.template'),
            ('res_id', '=', product.id),
            ('access_token', '=', False),
        ], order='id')
        values['attachments'] = attachments
        return values

    @http.route(['/attachment/download'], type='http', auth='public')
    def download_attachment(self, attachment_id):
        attachment = request.env['ir.attachment'].sudo().search(
            [('id', '=', int(attachment_id))], limit=1
        )
        if not attachment:
            return request.redirect('/shop')

        if attachment.type == 'url':
            return request.redirect(attachment.url or '/shop')

        if attachment.datas:
            data = io.BytesIO(base64.standard_b64decode(attachment.datas))
            return http.send_file(data, filename=attachment.name, as_attachment=True)

        return request.not_found()
