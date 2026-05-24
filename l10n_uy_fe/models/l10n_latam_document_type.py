from odoo import models, api, fields, _
from odoo.exceptions import UserError
class L10nLatamDocumentType(models.Model):

    _inherit = 'l10n_latam.document.type'

    l10n_uy_doc_type = fields.Char("tipo dgi")
