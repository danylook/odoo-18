from odoo import models, fields

class WFPanel(models.Model):
    _name = 'wf.panel'
    _description = 'WF Panel'
    _order = 'name'

    name = fields.Char('Panel Name', required=True)
    project = fields.Char('Project')
    model = fields.Char('Model')
    site_address = fields.Char('Site Address')
    date = fields.Date('Date')
    designer = fields.Char('Designer')
    #line_ids = fields.One2many('wf.panel.line', 'panel_id', string='Panel Lines')
    manufactured_product_id = fields.Many2one(
        'product.product',
        string='Manufactured Product',
        copy=False,
        help='Producto terminado asociado al panel para procesos de fabricación.',
    )
    bom_id = fields.Many2one('mrp.bom', string='BOM')
    production_id = fields.Many2one('mrp.production', string='Production Order')
    level = fields.Char('Level')
    bundle = fields.Char('Bundle')
    section_ids = fields.One2many('wf.panel.section', 'project_id', string='Panel Sections')

    def _ensure_manufactured_product(self, section):
        """Find or create a product.product for *section* and link it back.

        The product is named ``{project} - {section.name}`` and is of type
        'consu' (consumable) so it requires no inventory tracking by default.
        Returns the product.product record or None on failure.
        """
        self.ensure_one()
        if section.manufactured_product_id:
            return section.manufactured_product_id

        project_label = self.project or self.name or ""
        product_name = f"{project_label} - {section.name}" if project_label else section.name

        Product = self.env["product.product"].sudo()
        product = Product.search([("name", "=", product_name)], limit=1)
        if not product:
            product = Product.create({
                "name": product_name,
                "type": "consu",
            })

        section.sudo().write({"manufactured_product_id": product.id})
        return product
