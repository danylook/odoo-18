# -*- coding: utf-8 -*-
import secrets
from odoo import models, fields, api


class Tpl3plApiKey(models.Model):
    _name = 'tpl.3pl.api.key'
    _description = '3PL API Key'
    _order = 'partner_id'

    name = fields.Char('Label', required=True)
    partner_id = fields.Many2one(
        'res.partner', string='Client', required=True,
        domain=[('tpl_client_owner_id', '=', False)],
    )
    key = fields.Char('API Key', readonly=True, copy=False)
    active = fields.Boolean(default=True)
    webhook_url = fields.Char(
        'Webhook URL',
        help='POST stock updates here when a picking is validated. Leave empty to disable.',
    )
    webhook_secret = fields.Char(
        'Webhook Secret',
        help='Sent as X-Webhook-Secret header so the client can verify the call.',
    )
    last_call = fields.Datetime('Last API Call', readonly=True)
    note = fields.Text('Notes')

    def action_generate_key(self):
        for rec in self:
            rec.key = secrets.token_urlsafe(32)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('key'):
                vals['key'] = secrets.token_urlsafe(32)
        return super().create(vals_list)
