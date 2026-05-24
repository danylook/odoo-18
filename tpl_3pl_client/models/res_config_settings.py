# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    tpl3pl_server_url = fields.Char(
        string='3PL Server URL',
        help='Base URL of the 3PL Odoo server, e.g. http://192.168.1.65:8069',
        config_parameter='tpl3pl.server.url',
    )
    tpl3pl_api_key = fields.Char(
        string='3PL API Key',
        help='API key issued by the 3PL server for this client',
        config_parameter='tpl3pl.api.key',
    )
    tpl3pl_webhook_secret = fields.Char(
        string='Webhook Secret',
        help='Secret to verify incoming webhook calls from the 3PL server',
        config_parameter='tpl3pl.webhook.secret',
    )
