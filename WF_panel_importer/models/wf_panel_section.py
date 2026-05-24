from odoo import models, fields


class WFPanelSection(models.Model):
    _name = "wf.panel.section"
    _description = "WF Panel Section"
    _order = "name, id"

    project_id = fields.Many2one(
        "wf.panel",
        string="Proyecto",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(string="Panel", required=True)
    source_file = fields.Char(string="Archivo SVG")
    manufactured_product_id = fields.Many2one(
        "product.product",
        string="Producto Fabricado",
        copy=False,
        help="Producto terminado generado automáticamente para este panel.",
    )
    component_ids = fields.One2many(
        "wf.panel.component",
        "section_id",
        string="Componentes",
    )
    component_count = fields.Integer(
        string="Componentes",
        compute="_compute_component_count",
    )

    def _compute_component_count(self):
        for section in self:
            section.component_count = len(section.component_ids)

    def action_show_piece_dictionary(self):
        self.ensure_one()
        # Generar el diccionario antes de abrir el wizard
        ctx = dict(self.env.context)
        ctx.update({
            'active_id': self.id,
            'active_model': 'wf.panel.section',
        })
        wizard = self.env['panel.mrp.dictionary.wizard'].with_context(ctx).create({})
        wizard.action_panel_mrp_dictionary_wizard()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Diccionario de piezas',
            'res_model': 'panel.mrp.dictionary.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }
