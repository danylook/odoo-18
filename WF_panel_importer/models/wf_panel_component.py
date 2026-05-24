from odoo import models, fields


class WFPanelComponent(models.Model):
    _name = "wf.panel.component"
    _description = "WF Panel Component"
    _order = "sequence, id"

    section_id = fields.Many2one(
        "wf.panel.section",
        string="Sección",
        required=True,
        ondelete="cascade",
    )
    project_id = fields.Many2one(
        related="section_id.project_id",
        string="Proyecto",
        store=True,
    )
    sequence = fields.Integer(default=10)
    # svg_id = fields.Char(string="ID SVG")
    data_id = fields.Char(string="ID Datos")
    data_path = fields.Text(string="Ruta SVG")
    x = fields.Float(string="X", digits=(16, 4))
    y = fields.Float(string="Y", digits=(16, 4))
    # svg_width = fields.Float(string="Ancho SVG", digits=(16, 4))
    # svg_height = fields.Float(string="Alto SVG", digits=(16, 4))
    data_length = fields.Float(string="Largo", digits=(16, 3))
    data_width = fields.Float(string="Ancho", digits=(16, 3))
    data_depth = fields.Float(string="Profundidad", digits=(16, 3))
    data_orientation = fields.Selection(
        [
            ("horizontal", "Horizontal"),
            ("vertical", "Vertical"),
        ],
        string="Orientación",
    )
