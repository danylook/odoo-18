from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    svg_temp_dir = fields.Char(
        string='Directorio temporal para SVG',
        config_parameter='wf_panel_importer.svg_temp_dir',
        help='Directorio temporal donde se guardarán los archivos SVG generados por WF Panel Importer.'
    )
