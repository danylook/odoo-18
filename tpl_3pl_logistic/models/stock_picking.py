import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    tpl_owner_id = fields.Many2one(
        'res.partner',
        string='3PL Client Owner',
        compute='_compute_tpl_owner_id',
        store=True,
    )
    tpl_handling_invoiced = fields.Boolean(
        string='Handling Fee Invoiced',
        default=False,
    )

    @api.depends('move_ids.product_id.product_tmpl_id.owner_id')
    def _compute_tpl_owner_id(self):
        for picking in self:
            owners = picking.move_ids.mapped('product_id.product_tmpl_id.owner_id')
            if owners and len(owners) == 1:
                picking.tpl_owner_id = owners[0]
            else:
                picking.tpl_owner_id = False

    def _action_done(self):
        res = super()._action_done()
        for picking in self:
            if picking.state != 'done':
                continue
            if picking.tpl_handling_invoiced:
                continue
            if picking.picking_type_id.code not in ('incoming', 'outgoing'):
                continue
            owner = picking.tpl_owner_id or picking.partner_id
            if not owner:
                continue
            search_ids = [owner.id]
            if owner.parent_id:
                search_ids.append(owner.parent_id.id)
            config = self.env['tpl.3pl.client.rate'].search([
                ('partner_id', 'in', search_ids),
                ('company_id', '=', picking.company_id.id),
            ], limit=1)
            if not config:
                continue
            try:
                config.bill_picking(picking)
                picking.tpl_handling_invoiced = True
            except Exception:
                _logger.exception(
                    '3PL auto-billing failed for picking %s', picking.name)
        return res

    def action_create_handling_invoice(self):
        self.ensure_one()
        if not self.tpl_owner_id:
            return
        is_inbound = self.picking_type_id.code == 'incoming'
        ref = 'tpl_3pl_logistic.product_handling_input' if is_inbound \
            else 'tpl_3pl_logistic.product_handling_output'
        try:
            product = self.env.ref(ref)
        except Exception:
            return
        qty = sum(self.move_ids.mapped('product_uom_qty')) or 1.0
        label = ('Handling Input: ' if is_inbound else 'Handling Output: ') + self.name
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.tpl_owner_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.product_variant_id.id,
                'name': label,
                'quantity': qty,
                'price_unit': product.list_price,
            })],
        })
        self.tpl_handling_invoiced = True
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
