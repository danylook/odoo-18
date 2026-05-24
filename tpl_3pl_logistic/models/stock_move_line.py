from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    tpl_operation_type = fields.Char(
        string='3PL Operation',
        compute='_compute_tpl_operation_type',
    )

    @api.depends('picking_id.picking_type_id.name')
    def _compute_tpl_operation_type(self):
        for line in self:
            if line.picking_id and line.picking_id.picking_type_id:
                line.tpl_operation_type = line.picking_id.picking_type_id.name
            else:
                line.tpl_operation_type = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for line in records:
            owner = line.product_id.product_tmpl_id.owner_id
            if owner and line.owner_id != owner:
                line.owner_id = owner
        return records
