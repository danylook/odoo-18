import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class Tpl3plClientRate(models.Model):
    _name = 'tpl.3pl.client.rate'
    _description = '3PL Per-Client Billing Rates'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner', string='Client', required=True, index=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company, required=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True,
    )

    # --- Inbound (receiving) ---
    inbound_enabled = fields.Boolean('Charge Inbound / Receiving', default=True)
    inbound_product_id = fields.Many2one(
        'product.product', string='Inbound Service Product',
        domain=[('type', '=', 'service')],
        help='Leave blank to use the default Handling Charges - Input product.',
    )
    inbound_price = fields.Float('Inbound Price', digits=(12, 4))
    inbound_mode = fields.Selection([
        ('operation', 'Per Operation (flat fee per receipt)'),
        ('line', 'Per Product Line'),
        ('unit', 'Per Unit Received'),
    ], string='Inbound Mode', default='operation')

    # --- Outbound (delivery) ---
    outbound_enabled = fields.Boolean('Charge Outbound / Delivery', default=True)
    outbound_product_id = fields.Many2one(
        'product.product', string='Outbound Service Product',
        domain=[('type', '=', 'service')],
        help='Leave blank to use the default Handling Charges - Output product.',
    )
    outbound_price = fields.Float('Outbound Price', digits=(12, 4))
    outbound_mode = fields.Selection([
        ('operation', 'Per Operation (flat fee per shipment)'),
        ('unit', 'Per Unit Shipped'),
    ], string='Outbound Mode', default='operation')

    _sql_constraints = [
        ('partner_company_unique', 'unique(partner_id, company_id)',
         'Only one billing rate configuration per client per company.'),
    ]

    def _get_or_create_draft_invoice(self):
        """Return an open draft invoice for this client, or create a new one."""
        self.ensure_one()
        today = fields.Date.today()
        invoice = self.env['account.move'].search([
            ('partner_id', '=', self.partner_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'draft'),
            ('company_id', '=', self.company_id.id),
        ], limit=1, order='id desc')
        if not invoice:
            invoice = self.env['account.move'].create({
                'partner_id': self.partner_id.id,
                'move_type': 'out_invoice',
                'invoice_date': today,
                'company_id': self.company_id.id,
                'invoice_origin': '3PL Auto-billing',
            })
        return invoice

    def _resolve_product(self, code):
        """Return the service product for inbound or outbound, with fallback to module defaults."""
        self.ensure_one()
        if code == 'incoming':
            product = self.inbound_product_id
            if not product:
                tmpl = self.env.ref(
                    'tpl_3pl_logistic.product_handling_input', raise_if_not_found=False)
                product = tmpl.product_variant_id if tmpl else self.env['product.product']
        else:
            product = self.outbound_product_id
            if not product:
                tmpl = self.env.ref(
                    'tpl_3pl_logistic.product_handling_output', raise_if_not_found=False)
                product = tmpl.product_variant_id if tmpl else self.env['product.product']
        return product

    def bill_picking(self, picking):
        """Create an invoice line for a validated picking."""
        self.ensure_one()
        code = picking.picking_type_id.code

        if code == 'incoming':
            if not self.inbound_enabled:
                return
            product = self._resolve_product('incoming')
            if not product:
                return
            price = self.inbound_price or product.lst_price
            if self.inbound_mode == 'operation':
                qty = 1.0
                desc = 'Inbound receiving: %s' % picking.name
            elif self.inbound_mode == 'line':
                qty = float(len(picking.move_ids))
                desc = 'Inbound receiving (%d lines): %s' % (int(qty), picking.name)
            else:
                qty = sum(picking.move_ids.mapped('quantity'))
                desc = 'Inbound receiving (%g units): %s' % (qty, picking.name)

        elif code == 'outgoing':
            if not self.outbound_enabled:
                return
            product = self._resolve_product('outgoing')
            if not product:
                return
            price = self.outbound_price or product.lst_price
            if self.outbound_mode == 'operation':
                qty = 1.0
                desc = 'Outbound delivery: %s' % picking.name
            else:
                qty = sum(picking.move_ids.mapped('quantity'))
                desc = 'Outbound delivery (%g units): %s' % (qty, picking.name)
        else:
            return

        if qty <= 0:
            return

        invoice = self._get_or_create_draft_invoice()
        invoice.write({
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id,
                'name': desc,
                'quantity': qty,
                'price_unit': price,
            })]
        })
