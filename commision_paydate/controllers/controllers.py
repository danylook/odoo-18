# -*- coding: utf-8 -*-
# from odoo import http


# class CommisionPaydate(http.Controller):
#     @http.route('/commision_paydate/commision_paydate', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/commision_paydate/commision_paydate/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('commision_paydate.listing', {
#             'root': '/commision_paydate/commision_paydate',
#             'objects': http.request.env['commision_paydate.commision_paydate'].search([]),
#         })

#     @http.route('/commision_paydate/commision_paydate/objects/<model("commision_paydate.commision_paydate"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('commision_paydate.object', {
#             'object': obj
#         })
