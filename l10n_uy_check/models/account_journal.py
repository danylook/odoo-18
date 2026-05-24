# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import date
import requests
import json

class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_check = fields.Boolean('Is Check')
