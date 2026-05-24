# -*- coding: utf-8 -*-
import json
import logging
import threading
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import date, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _ollama_call_plain(url, model, system_prompt, user_prompt, options):
    """Standalone Ollama call (no ORM/cursor). Used by background thread."""
    base = url.rstrip('/')
    payload = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': user_prompt},
        ],
        'stream': False,
        'format': 'json',
        'options': options,
    }).encode('utf-8')
    try:
        req = urllib.request.Request(
            base + '/api/chat', data=payload,
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        return result.get('message', {}).get('content', '') or result.get('response', '')
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            return f'⚠ HTTP {exc.code} — check model "{model}" is installed (ollama pull {model})'
    # fallback /api/generate
    payload2 = json.dumps({
        'model': model, 'prompt': user_prompt, 'system': system_prompt,
        'stream': False, 'format': 'json', 'options': options,
    }).encode('utf-8')
    try:
        req2 = urllib.request.Request(
            base + '/api/generate', data=payload2,
            headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req2, timeout=180) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        return result.get('response', '')
    except urllib.error.URLError as exc:
        return f'⚠ Ollama not reachable at {url} — run: systemctl start ollama'
    except Exception as exc:
        return f'⚠ AI error: {exc}'

class TplAiForecast(models.Model):
    _name = 'tpl.ai.forecast'
    _description = 'AI Inventory Forecast'
    _order = 'date desc, id desc'

    # ── Identity ──────────────────────────────────────────────────────────────
    name = fields.Char(default='New', copy=False, readonly=True)
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    state = fields.Selection([
        ('draft',   'Draft'),
        ('running', 'Running'),
        ('done',    'Done'),
        ('error',   'Error'),
    ], default='draft', readonly=True)

    # ── Configuration ─────────────────────────────────────────────────────────
    data_source = fields.Selection([
        ('moves', 'Stock Movements (Deliveries)'),
        ('sales', 'Sales Orders (Demand)'),
    ], default='moves', required=True, string='Data Source',
       help='Stock Movements: based on done outgoing/internal transfers.\nSales Orders: based on confirmed sale order lines (ordered quantity).')
    history_days = fields.Integer(default=90,  string='History Period (days)',
                                  help='Days of stock-move history to analyse.')
    forecast_days = fields.Integer(default=30, string='Forecast Period (days)',
                                   help='Number of days to project demand into the future.')
    dead_stock_days = fields.Integer(default=60,  string='Dead Stock Threshold (days)',
                                     help='Items with no movement for this many days are flagged as dead stock.')
    fast_moving_percentile = fields.Integer(default=20, string='Fast-Moving Top % (by volume)',
                                            help='Items in the top N% by total outgoing volume are classified as fast-moving.')
    location_ids = fields.Many2many(
        'stock.location',
        'tpl_ai_forecast_location_rel', 'forecast_id', 'location_id',
        string='Locations',
        domain=[('usage', '=', 'internal')],
        help='Leave empty to include all internal locations.',
    )
    partner_ids = fields.Many2many(
        'res.partner',
        'tpl_ai_forecast_partner_rel', 'forecast_id', 'partner_id',
        string='Clients (3PL)',
        help='Filter analysis to movements for specific 3PL clients.',
    )

    # ── Ollama AI ─────────────────────────────────────────────────────────────
    ollama_url = fields.Char(default='http://localhost:11434', string='Ollama URL',
                             help='Base URL of your Ollama server (e.g. http://localhost:11434).')
    ollama_model = fields.Char(default='qwen2:1.5b', string='Ollama Model',
                               help='Model name as shown in `ollama list` (e.g. llama3, qwen2, mistral).')

    # ── Results ───────────────────────────────────────────────────────────────
    line_ids = fields.One2many('tpl.ai.forecast.line', 'forecast_id', string='Forecast Lines')
    ai_summary = fields.Text(string='AI Analysis', readonly=True)
    ai_error = fields.Text(string='Last Error', readonly=True)

    # ── KPI counters (stored so they appear on list view without N+1) ─────────
    line_count = fields.Integer(compute='_compute_kpi', store=True, string='Products')
    dead_stock_count = fields.Integer(compute='_compute_kpi', store=True, string='Dead Stock')
    fast_moving_count = fields.Integer(compute='_compute_kpi', store=True, string='Fast Moving')
    reorder_count = fields.Integer(compute='_compute_kpi', store=True, string='Need Reorder')

    @api.depends('line_ids.classification', 'line_ids.reorder_qty')
    def _compute_kpi(self):
        for rec in self:
            lines = rec.line_ids
            rec.line_count = len(lines)
            rec.dead_stock_count = len(lines.filtered(lambda l: l.classification == 'dead_stock'))
            rec.fast_moving_count = len(lines.filtered(lambda l: l.classification == 'fast_moving'))
            rec.reorder_count = len(lines.filtered(lambda l: l.reorder_qty > 0))

    # ── ORM ───────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('tpl.ai.forecast') or 'New'
                )
        return super().create(vals_list)

    # ── Main action ───────────────────────────────────────────────────────────
    def action_generate_forecast(self):
        self.ensure_one()
        self.write({'state': 'running', 'ai_error': False, 'ai_summary': False})
        self.line_ids.unlink()
        self.flush_recordset()

        try:
            history = self._collect_history()
            lines_data = self._compute_statistics(history)
            self._create_forecast_lines(lines_data)
            self.flush_recordset()
        except UserError:
            self.write({'state': 'error'})
            raise
        except Exception as exc:
            _logger.exception('AI Forecast generation failed for %s', self.name)
            self.write({'state': 'error', 'ai_error': str(exc)})
            raise UserError('Forecast generation failed:\n%s' % exc) from exc

        self.write({'state': 'done'})

    def action_run_ai_analysis(self):
        """Generate an instant statistical summary (no Ollama dependency)."""
        self.ensure_one()
        lines = self.line_ids
        if not lines:
            self.ai_summary = '⚠ No forecast lines found. Run Generate Forecast first.'
            return

        total  = len(lines)
        dead   = lines.filtered(lambda l: l.classification == 'dead_stock')
        fast   = lines.filtered(lambda l: l.classification == 'fast_moving')
        normal = lines.filtered(lambda l: l.classification == 'normal')
        need   = lines.filtered(lambda l: l.reorder_qty > 0).sorted('reorder_qty', reverse=True)

        trend_up   = len(lines.filtered(lambda l: l.trend == 'up'))
        trend_down = len(lines.filtered(lambda l: l.trend == 'down'))
        trend_flat = len(lines.filtered(lambda l: l.trend == 'flat'))

        parts = []

        # ── Header ─────────────────────────────────────────────────────────────
        parts.append(
            f'📊 INVENTORY ANALYSIS — '
            f'Forecast: {self.forecast_days} days | History: {self.history_days} days\n'
            f'{total} products tracked | '
            f'{len(dead)} dead stock | {len(fast)} fast moving | {len(need)} need reorder'
        )

        # ── Dead Stock ─────────────────────────────────────────────────────────
        if dead:
            names = ', '.join(l.product_id.display_name for l in dead[:8])
            extra = f' and {len(dead) - 8} more' if len(dead) > 8 else ''
            parts.append(
                f'\n⚠  DEAD STOCK ({len(dead)} items — no movement >{self.dead_stock_days} days):\n'
                f'   {names}{extra}'
            )

        # ── Need Reorder (top 10 by qty) ───────────────────────────────────────
        if need:
            lines_txt = '\n'.join(
                f'   • {l.product_id.display_name}: '
                f'need {l.reorder_qty:,.0f} units '
                f'(stock {l.current_stock:,.0f} / demand {l.forecast_qty:,.0f})'
                for l in need[:10]
            )
            extra = f'\n   … and {len(need) - 10} more items' if len(need) > 10 else ''
            parts.append(f'\n🛒  NEED REORDER ({len(need)} items):\n{lines_txt}{extra}')

        # ── Fast Moving ────────────────────────────────────────────────────────
        if fast:
            names = ', '.join(l.product_id.display_name for l in fast[:8])
            extra = f' and {len(fast) - 8} more' if len(fast) > 8 else ''
            parts.append(
                f'\n🚀  FAST MOVING ({len(fast)} items — top {self.fast_moving_percentile}% by volume):\n'
                f'   {names}{extra}'
            )

        # ── Trends ─────────────────────────────────────────────────────────────
        parts.append(
            f'\n📈  DEMAND TRENDS: '
            f'{trend_up} rising ↑ | {trend_down} falling ↓ | {trend_flat} flat →'
        )

        # ── Recommendations ────────────────────────────────────────────────────
        recs = []
        if dead:
            recs.append(f'Review {len(dead)} dead stock items for liquidation or write-off.')
        if need:
            top = need[0]
            recs.append(
                f'Urgent reorder: {top.product_id.display_name} '
                f'({top.reorder_qty:,.0f} units needed).'
            )
        if trend_down > trend_up:
            recs.append('Overall demand is declining — consider reducing safety stock levels.')
        elif trend_up > trend_down:
            recs.append('Overall demand is growing — ensure sufficient stock for fast movers.')
        if recs:
            parts.append('\n💡  RECOMMENDATIONS:\n' + '\n'.join(f'   • {r}' for r in recs))

        self.ai_summary = '\n'.join(parts)

    # ── Step 1: collect history (dispatches by data_source) ─────────────────
    def _collect_history(self):
        """Return {(product_id, location_id): {quantities, dates, partner_ids}}."""
        if self.data_source == 'sales':
            return self._collect_history_sales()
        return self._collect_history_moves()

    def _collect_history_moves(self):
        """History from done stock moves (outgoing + internal)."""
        date_from = date.today() - timedelta(days=self.history_days)

        domain = [
            ('state', '=', 'done'),
            ('date', '>=', fields.Datetime.to_datetime(date_from)),
            ('picking_type_id.code', 'in', ['outgoing', 'internal']),
            ('scrapped', '=', False),
        ]
        if self.location_ids:
            domain.append(('location_id', 'in', self.location_ids.ids))
        if self.partner_ids:
            domain.append(('picking_id.partner_id', 'in', self.partner_ids.ids))

        moves = self.env['stock.move'].search_read(
            domain, ['product_id', 'location_id', 'quantity', 'date', 'picking_id']
        )

        history = defaultdict(lambda: {'quantities': [], 'dates': [], 'partner_ids': set()})
        picking_partner_cache = {}

        for mv in moves:
            key = (mv['product_id'][0], mv['location_id'][0])
            history[key]['quantities'].append(mv['quantity'])
            history[key]['dates'].append(
                fields.Datetime.from_string(mv['date']).date()
            )
            if mv['picking_id']:
                pick_id = mv['picking_id'][0]
                if pick_id not in picking_partner_cache:
                    pick = self.env['stock.picking'].browse(pick_id)
                    picking_partner_cache[pick_id] = pick.partner_id.id or False
                partner = picking_partner_cache[pick_id]
                if partner:
                    history[key]['partner_ids'].add(partner)

        return history

    def _collect_history_sales(self):
        """History from confirmed sale order lines (ordered qty = demand)."""
        date_from = date.today() - timedelta(days=self.history_days)

        domain = [
            ('order_id.state', 'in', ['sale', 'done']),
            ('order_id.date_order', '>=', fields.Datetime.to_datetime(date_from)),
            ('product_id.type', 'in', ['product', 'consu']),
        ]
        if self.partner_ids:
            domain.append(('order_id.partner_id', 'in', self.partner_ids.ids))

        allowed_loc_ids = set(self.location_ids.ids) if self.location_ids else None

        sol = self.env['sale.order.line'].search_read(
            domain, ['product_id', 'product_uom_qty', 'order_id']
        )

        order_cache = {}
        history = defaultdict(lambda: {'quantities': [], 'dates': [], 'partner_ids': set()})

        for line in sol:
            order_id = line['order_id'][0]
            if order_id not in order_cache:
                order = self.env['sale.order'].browse(order_id)
                loc_id = order.warehouse_id.lot_stock_id.id if order.warehouse_id else False
                order_cache[order_id] = {
                    'location_id': loc_id,
                    'partner_id': order.partner_id.id or False,
                    'date_order': order.date_order.date() if order.date_order else date.today(),
                }

            od = order_cache[order_id]
            loc_id = od['location_id']
            if not loc_id:
                continue
            if allowed_loc_ids and loc_id not in allowed_loc_ids:
                continue

            key = (line['product_id'][0], loc_id)
            history[key]['quantities'].append(line['product_uom_qty'])
            history[key]['dates'].append(od['date_order'])
            if od['partner_id']:
                history[key]['partner_ids'].add(od['partner_id'])

        return history

    # ── Step 2: compute statistics per product/location ───────────────────────
    def _compute_statistics(self, history):
        """Return list of dicts ready for tpl.ai.forecast.line.create()."""
        today = date.today()
        mid_date = today - timedelta(days=self.history_days // 2)

        # Current on-hand stock — aggregate by product across all internal
        # locations (moves may reference parent locations while quants are at
        # leaf child locations, so keying by product_id avoids mismatches).
        loc_domain = [('location_id.usage', '=', 'internal'), ('quantity', '>', 0)]
        if self.location_ids:
            # Expand to include all child locations of the selected locations
            child_locs = self.env['stock.location'].search(
                [('id', 'child_of', self.location_ids.ids), ('usage', '=', 'internal')]
            )
            loc_domain.append(('location_id', 'in', child_locs.ids))
        quants = self.env['stock.quant'].search_read(
            loc_domain, ['product_id', 'quantity']
        )
        stock_map = defaultdict(float)
        for q in quants:
            stock_map[q['product_id'][0]] += q['quantity']

        # Fast-moving percentile threshold
        totals_sorted = sorted(
            ((k, sum(v['quantities'])) for k, v in history.items()),
            key=lambda x: x[1], reverse=True,
        )
        threshold_idx = max(0, int(len(totals_sorted) * self.fast_moving_percentile / 100) - 1)
        fast_threshold = totals_sorted[threshold_idx][1] if totals_sorted else float('inf')

        lines_data = []
        for (product_id, location_id), data in history.items():
            total_qty = sum(data['quantities'])
            avg_daily = total_qty / max(1, self.history_days)

            # Trend: compare second half of the period vs first half
            recent = sum(
                q for q, d in zip(data['quantities'], data['dates']) if d >= mid_date
            )
            older = sum(
                q for q, d in zip(data['quantities'], data['dates']) if d < mid_date
            )
            if older > 0:
                ratio = (recent - older) / older
                trend = 'up' if ratio > 0.1 else ('down' if ratio < -0.1 else 'flat')
                trend_factor = max(-0.5, min(0.5, ratio))
            else:
                trend = 'up' if recent > 0 else 'flat'
                trend_factor = 0.1 if recent > 0 else 0.0

            forecast_qty = round(avg_daily * self.forecast_days * (1 + trend_factor), 2)
            current_stock = round(stock_map[product_id], 2)
            reorder_qty = round(max(0.0, forecast_qty - current_stock), 2)

            last_move_date = max(data['dates']) if data['dates'] else None
            days_since = (today - last_move_date).days if last_move_date else self.history_days

            classification = (
                'dead_stock' if days_since >= self.dead_stock_days else
                'fast_moving' if total_qty >= fast_threshold and total_qty > 0 else
                'normal'
            )

            lines_data.append({
                'product_id': product_id,
                'location_id': location_id,
                'partner_ids': list(data['partner_ids']),
                'current_stock': current_stock,
                'avg_daily_demand': round(avg_daily, 4),
                'total_historical_qty': round(total_qty, 2),
                'forecast_qty': forecast_qty,
                'reorder_qty': reorder_qty,
                'last_move_date': last_move_date,
                'trend': trend,
                'classification': classification,
            })

        return lines_data

    # ── Step 3: persist lines ─────────────────────────────────────────────────
    def _create_forecast_lines(self, lines_data):
        Line = self.env['tpl.ai.forecast.line']
        for ld in lines_data:
            partner_ids = ld.pop('partner_ids', [])
            ld['forecast_id'] = self.id
            line = Line.create(ld)
            if partner_ids:
                line.partner_ids = [fields.Command.set(partner_ids)]

    # ── Step 4: Ollama qualitative analysis ───────────────────────────────────
    def _ollama_call(self, system_prompt, user_prompt):
        """Call Ollama API, trying /api/chat first then /api/generate as fallback.
        Returns the text content from the model, or raises on failure."""
        base = self.ollama_url.rstrip('/')

        # CPU-friendly options: small context, limited output tokens
        ollama_options = {
            'temperature': 0.2,
            'num_ctx': 512,       # small context window — much faster on CPU
            'num_predict': 250,   # limit output tokens — prevents runaway generation
            'num_thread': 4,      # limit CPU threads used by Ollama
        }

        # ── Try modern /api/chat endpoint ─────────────────────────────────────
        chat_payload = json.dumps({
            'model': self.ollama_model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_prompt},
            ],
            'stream': False,
            'format': 'json',
            'options': ollama_options,
        }).encode('utf-8')

        try:
            req = urllib.request.Request(
                base + '/api/chat',
                data=chat_payload,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            return result.get('message', {}).get('content', '')
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            _logger.info('Ollama /api/chat returned 404, falling back to /api/generate')

        # ── Fallback: /api/generate (older Ollama versions) ───────────────────
        gen_payload = json.dumps({
            'model': self.ollama_model,
            'prompt': user_prompt,
            'system': system_prompt,
            'stream': False,
            'format': 'json',
            'options': ollama_options,
        }).encode('utf-8')

        req = urllib.request.Request(
            base + '/api/generate',
            data=gen_payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        return result.get('response', '')

    def _analyze_with_ollama(self):
        """Call Ollama for a qualitative narrative on the forecast results."""
        if not (self.ollama_url and self.ollama_model):
            return

        lines = self.line_ids
        if not lines:
            return

        total = len(lines)
        dead  = lines.filtered(lambda l: l.classification == 'dead_stock')
        fast  = lines.filtered(lambda l: l.classification == 'fast_moving')
        need  = lines.filtered(lambda l: l.reorder_qty > 0)

        # Keep prompt very short for CPU models — only top-5 names per category
        def top5_names(recs):
            return [r.product_id.display_name for r in recs[:5]]

        system_prompt = (
            'You are an inventory analyst. Reply ONLY with a JSON object with keys: '
            '"summary" (1-2 sentences), "urgent" (array of up to 3 action strings), '
            '"procurement" (1 sentence). Be brief.'
        )

        user_prompt = (
            f'Inventory stats: {total} products tracked, '
            f'{len(dead)} dead stock, {len(fast)} fast moving, {len(need)} need reorder.\n'
            f'Dead stock: {top5_names(dead)}\n'
            f'Need reorder: {top5_names(need)}\n'
            f'Fast moving: {top5_names(fast)}'
        )

        try:
            content = self._ollama_call(system_prompt, user_prompt)

            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                self.ai_summary = content
                return

            parts = []
            if parsed.get('summary'):
                parts.append(parsed['summary'])
            if parsed.get('urgent'):
                parts.append('\nURGENT:\n' + '\n'.join(f'  • {a}' for a in parsed['urgent']))
            if parsed.get('procurement'):
                parts.append('\nPROCUREMENT:\n  ' + parsed['procurement'])
            self.ai_summary = '\n'.join(parts) or content

        except urllib.error.HTTPError as exc:
            _logger.warning('Ollama HTTP error %s at %s', exc.code, self.ollama_url)
            self.ai_summary = (
                f'⚠ HTTP {exc.code} — check model "{self.ollama_model}" is installed '
                f'(ollama pull {self.ollama_model})'
            )
        except urllib.error.URLError as exc:
            _logger.warning('Ollama unreachable at %s: %s', self.ollama_url, exc)
            self.ai_summary = (
                f'⚠ Ollama not reachable at {self.ollama_url} — '
                f'run: systemctl start ollama'
            )
        except Exception as exc:
            _logger.warning('Ollama analysis error: %s', exc)
            self.ai_summary = f'⚠ AI analysis error: {exc}'

    # ── User actions ──────────────────────────────────────────────────────────
    def action_detect_ollama_model(self):
        """Query Ollama /api/tags and auto-fill the model field with the first available model."""
        self.ensure_one()
        if not self.ollama_url:
            raise UserError('Please set an Ollama URL first.')
        try:
            req = urllib.request.Request(
                self.ollama_url.rstrip('/') + '/api/tags',
                headers={'Content-Type': 'application/json'},
                method='GET',
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            models = [m['name'] for m in data.get('models', [])]
        except urllib.error.URLError as exc:
            raise UserError(
                f'Cannot reach Ollama at {self.ollama_url}\nMake sure Ollama is running.\n({exc})'
            ) from exc
        except Exception as exc:
            raise UserError(f'Error querying Ollama: {exc}') from exc

        if not models:
            raise UserError(
                f'Ollama is running at {self.ollama_url} but has no models installed.\n'
                f'Run:  ollama pull qwen2:1.5b'
            )

        self.write({'ollama_model': models[0]})

        # Reload the form so the new value is visible, pass model list via context message
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_ollama_model': models[0],
            },
        }

    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Forecast Lines — {self.name}',
            'res_model': 'tpl.ai.forecast.line',
            'view_mode': 'list,graph,pivot',
            'domain': [('forecast_id', '=', self.id)],
        }

    def action_view_dead_stock(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Dead Stock — {self.name}',
            'res_model': 'tpl.ai.forecast.line',
            'view_mode': 'list,graph,pivot',
            'domain': [('forecast_id', '=', self.id), ('classification', '=', 'dead_stock')],
        }

    def action_view_fast_moving(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fast Moving — {self.name}',
            'res_model': 'tpl.ai.forecast.line',
            'view_mode': 'list,graph,pivot',
            'domain': [('forecast_id', '=', self.id), ('classification', '=', 'fast_moving')],
        }

    def action_view_need_reorder(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Need Reorder — {self.name}',
            'res_model': 'tpl.ai.forecast.line',
            'view_mode': 'list,graph,pivot',
            'domain': [('forecast_id', '=', self.id), ('reorder_qty', '>', 0)],
        }

    def action_create_reorder_rules(self):
        """Create stock.warehouse.orderpoint for lines that need restocking."""
        self.ensure_one()
        Orderpoint = self.env['stock.warehouse.orderpoint']
        created = 0
        for line in self.line_ids.filtered(lambda l: l.reorder_qty > 0):
            if Orderpoint.search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', line.location_id.id),
            ], limit=1):
                continue  # already exists

            vals = {
                'product_id': line.product_id.id,
                'location_id': line.location_id.id,
                'product_min_qty': round(line.reorder_qty * 0.5, 2),
                'product_max_qty': round(line.reorder_qty * 1.5, 2),
                'qty_multiple': 1,
            }
            wh = self.env['stock.warehouse'].search(
                [('lot_stock_id', '=', line.location_id.id)], limit=1
            )
            if wh:
                vals['warehouse_id'] = wh.id
            try:
                Orderpoint.create(vals)
                created += 1
            except Exception as exc:
                _logger.warning(
                    'Could not create orderpoint for %s: %s', line.product_id.name, exc
                )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Reorder Rules Created',
                'message': f'{created} new reorder rule(s) created.',
                'sticky': False,
                'type': 'success',
            },
        }

    # ── Cron ──────────────────────────────────────────────────────────────────
    @api.model
    def _cron_generate_forecast(self):
        """Called by the daily scheduler to auto-generate a forecast."""
        ICP = self.env['ir.config_parameter'].sudo()
        vals = {
            'name': 'New',
            'ollama_url':   ICP.get_param('tpl_ai_forecast.ollama_url',   'http://localhost:11434'),
            'ollama_model': ICP.get_param('tpl_ai_forecast.ollama_model', 'llama3'),
            'history_days':            int(ICP.get_param('tpl_ai_forecast.history_days',            '90')),
            'forecast_days':           int(ICP.get_param('tpl_ai_forecast.forecast_days',           '30')),
            'dead_stock_days':         int(ICP.get_param('tpl_ai_forecast.dead_stock_days',         '60')),
            'fast_moving_percentile':  int(ICP.get_param('tpl_ai_forecast.fast_moving_percentile',  '20')),
        }
        forecast = self.create(vals)
        forecast.action_generate_forecast()
        _logger.info(
            'Cron AI Forecast generated: %s  state=%s  lines=%d',
            forecast.name, forecast.state, forecast.line_count,
        )
