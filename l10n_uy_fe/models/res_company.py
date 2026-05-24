# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class ResCompany(models.Model):
    _inherit = "res.company"

    def _localization_use_documents(self):
        """ Uruguayan localization use documents """
        self.ensure_one()
        return True if self.country_id.code == "UY" else super()._localization_use_documents()
