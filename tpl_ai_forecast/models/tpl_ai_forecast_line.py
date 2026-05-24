# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TplAiForecastLine(models.Model):
    _name = 'tpl.ai.forecast.line'
    _description = 'AI Forecast Line'
    _order = 'classification, reorder_qty desc'

    # ── Relations ─────────────────────────────────────────────────────────────
    forecast_id = fields.Many2one(
        'tpl.ai.forecast', required=True, ondelete='cascade', index=True
    )
    product_id = fields.Many2one(
        'product.product', required=True, index=True, string='Product'
    )
    product_categ_id = fields.Many2one(
        related='product_id.categ_id', store=True, string='Category'
    )
    location_id = fields.Many2one(
        'stock.location', required=True, string='Location'
    )
    partner_ids = fields.Many2many(
        'res.partner',
        'tpl_ai_forecast_line_partner_rel', 'line_id', 'partner_id',
        string='3PL Clients',
    )

    # ── Statistical data ──────────────────────────────────────────────────────
    current_stock = fields.Float(digits=(16, 2), string='Current Stock')
    avg_daily_demand = fields.Float(digits=(16, 4), string='Avg Daily Demand')
    total_historical_qty = fields.Float(digits=(16, 2), string='Historical Qty')
    forecast_qty = fields.Float(digits=(16, 2), string='Forecast Demand')
    reorder_qty = fields.Float(digits=(16, 2), string='Suggested Reorder Qty')
    last_move_date = fields.Date(string='Last Movement')

    # ── Classification ────────────────────────────────────────────────────────
    trend = fields.Selection([
        ('up',   '↑ Upward'),
        ('flat', '→ Flat'),
        ('down', '↓ Downward'),
    ], string='Demand Trend')

    classification = fields.Selection([
        ('normal',     'Normal'),
        ('dead_stock', 'Dead Stock'),
        ('fast_moving','Fast Moving'),
    ], default='normal', index=True, string='Classification')

    # ── Computed ──────────────────────────────────────────────────────────────
    coverage_days = fields.Float(
        compute='_compute_coverage_days',
        string='Stock Coverage (days)',
        digits=(16, 1),
        help='How many days current stock covers at average daily demand.',
    )

    @api.depends('current_stock', 'avg_daily_demand')
    def _compute_coverage_days(self):
        for rec in self:
            rec.coverage_days = (
                rec.current_stock / rec.avg_daily_demand
                if rec.avg_daily_demand > 0 else 0.0
            )
