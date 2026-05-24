from odoo import models, fields, tools


class TplStockAge(models.Model):
    _name = 'tpl.stock.age'
    _description = 'Stock Time Report (Days in Storage)'
    _auto = False  # SQL view — read-only
    _order = 'days_in_stock desc'

    owner_id = fields.Many2one('res.partner', string='Client', readonly=True)
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_tmpl_id = fields.Many2one(
        'product.template', string='Product Template', readonly=True)
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)
    first_seen = fields.Date(string='First Seen', readonly=True)
    last_seen = fields.Date(string='Last Seen', readonly=True)
    days_in_stock = fields.Integer(string='Days in Storage', readonly=True)
    avg_qty = fields.Float(
        string='Avg Daily Qty', digits='Product Unit of Measure', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'tpl_stock_age')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW tpl_stock_age AS (
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY h.owner_id, h.product_id, h.location_id
                    )::integer                              AS id,
                    h.owner_id,
                    h.product_id,
                    pt.id                                  AS product_tmpl_id,
                    h.location_id,
                    MIN(h.date)                            AS first_seen,
                    MAX(h.date)                            AS last_seen,
                    (MAX(h.date) - MIN(h.date) + 1)        AS days_in_stock,
                    AVG(h.quantity)                        AS avg_qty
                FROM tpl_stock_history h
                JOIN product_product pp ON pp.id = h.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE h.owner_id IS NOT NULL
                GROUP BY h.owner_id, h.product_id, h.location_id, pt.id
            )
        """)
