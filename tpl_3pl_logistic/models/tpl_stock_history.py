from datetime import date
from collections import defaultdict
from odoo import models, fields, api


class TplStockHistory(models.Model):
    _name = 'tpl.stock.history'
    _description = 'Stock History (Daily Snapshot)'
    _order = 'date desc, owner_id, location_id'

    date = fields.Date(string='Date', required=True, index=True)
    owner_id = fields.Many2one('res.partner', string='Client / Owner', index=True)
    location_id = fields.Many2one('stock.location', string='Location')
    fee_rate_id = fields.Many2one('tpl.fee.rate', string='Fee Rate')
    product_id = fields.Many2one('product.product', string='Product')
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        store=True,
    )
    lot_id = fields.Many2one('stock.lot', string='Lot / Serial')
    package_id = fields.Many2one('stock.quant.package', string='Package')
    package_type = fields.Char(string='Package Type', compute='_compute_package_type', store=True)
    quantity = fields.Float(string='Quantity', digits='Product Unit of Measure')
    uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        related='product_id.uom_id',
        store=True,
    )
    invoiced = fields.Boolean(string='Invoiced', default=False)
    invoice_line_id = fields.Many2one('account.move.line', string='Invoice Line')

    @api.depends('package_id', 'package_id.package_type_id')
    def _compute_package_type(self):
        for rec in self:
            pack = rec.package_id
            rec.package_type = pack.package_type_id.name if pack else ''

    def _cron_daily_stock(self):
        today = date.today()
        self.search([('date', '=', today)]).unlink()
        quants = self.env['stock.quant'].search([
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
        ])
        for sq in quants:
            owner = sq.owner_id or sq.product_id.product_tmpl_id.owner_id
            if not owner:
                continue
            fee_rate = sq.location_id.fee_rate_id or False
            self.create({
                'date': today,
                'owner_id': owner.id,
                'location_id': sq.location_id.id,
                'fee_rate_id': fee_rate.id if fee_rate else False,
                'product_id': sq.product_id.id,
                'lot_id': sq.lot_id.id if sq.lot_id else False,
                'package_id': sq.package_id.id if sq.package_id else False,
                'quantity': sq.quantity,
            })

    def _cron_monthly_invoices(self):
        today = date.today()
        uninvoiced = self.search([('invoiced', '=', False), ('owner_id', '!=', False)])
        if not uninvoiced:
            return
        by_owner = defaultdict(lambda: defaultdict(float))
        owner_records = defaultdict(list)
        for record in uninvoiced:
            key = (record.fee_rate_id.id if record.fee_rate_id else 0,
                   record.fee_rate_id.name if record.fee_rate_id else 'Storage')
            by_owner[record.owner_id.id][key] += record.quantity
            owner_records[record.owner_id.id].append(record.id)
        for owner_id, fee_groups in by_owner.items():
            invoice_lines = []
            for (rate_id, rate_name), total_qty in fee_groups.items():
                if 'high' in rate_name.lower() or 'bay' in rate_name.lower():
                    product = self.env.ref('tpl_3pl_logistic.product_storage_highbay', raise_if_not_found=False)
                else:
                    product = self.env.ref('tpl_3pl_logistic.product_storage_ground', raise_if_not_found=False)
                if not product:
                    continue
                fee_rate_rec = self.env['tpl.fee.rate'].browse(rate_id) if rate_id else None
                unit_price = fee_rate_rec.daily_rate if fee_rate_rec else product.list_price
                invoice_lines.append((0, 0, {
                    'product_id': product.product_variant_id.id,
                    'name': 'Storage fee (' + rate_name + ') - ' + today.strftime('%B %Y'),
                    'quantity': total_qty,
                    'price_unit': unit_price,
                }))
            if not invoice_lines:
                continue
            self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': owner_id,
                'invoice_date': today,
                'invoice_origin': '3PL Storage ' + today.strftime('%B %Y'),
                'invoice_line_ids': invoice_lines,
            })
            self.browse(owner_records[owner_id]).write({'invoiced': True})
