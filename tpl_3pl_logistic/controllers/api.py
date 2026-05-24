# -*- coding: utf-8 -*-
"""
3PL REST API
============
All endpoints require header:  X-API-Key: <key>

GET  /api/3pl/stock                   → client stock summary
GET  /api/3pl/order/<ref>/status      → picking status by origin ref
POST /api/3pl/order/inbound           → create inbound picking request
POST /api/3pl/order/outbound          → create outbound picking request
"""
import json
import logging
from datetime import datetime

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


def _json(data, status=200):
    return request.make_response(
        json.dumps(data, default=str),
        headers=[('Content-Type', 'application/json')],
        status=status,
    )


def _auth_client(req):
    """Validate X-API-Key header. Returns (api_key_record, error_response)."""
    key = req.httprequest.headers.get('X-API-Key', '').strip()
    if not key:
        return None, _json({'error': 'Missing X-API-Key header'}, 401)
    rec = req.env['tpl.3pl.api.key'].sudo().search(
        [('key', '=', key), ('active', '=', True)], limit=1
    )
    if not rec:
        return None, _json({'error': 'Invalid or inactive API key'}, 401)
    rec.sudo().write({'last_call': datetime.now()})
    return rec, None


def _partner_ids(partner):
    ids = [partner.id]
    if partner.parent_id:
        ids.append(partner.parent_id.id)
        ids += partner.parent_id.child_ids.ids
    else:
        ids += partner.child_ids.ids
    return list(set(ids))


class Tpl3plApi(http.Controller):

    # ── Stock ────────────────────────────────────────────────────────
    @http.route('/api/3pl/stock', type='http', auth='none', methods=['GET'], csrf=False)
    def api_stock(self, **kwargs):
        api_key, err = _auth_client(request)
        if err:
            return err

        partner = api_key.partner_id
        pids = _partner_ids(partner)

        quants = request.env['stock.quant'].sudo().search([
            ('owner_id', 'in', pids),
            ('location_id.usage', '=', 'internal'),
            ('quantity', '>', 0),
        ])

        products = {}
        for q in quants:
            ref = q.product_id.default_code or str(q.product_id.id)
            key = ref
            if key not in products:
                products[key] = {
                    'ref': ref,
                    'name': q.product_id.name,
                    'uom': q.product_uom_id.name,
                    'qty_on_hand': 0.0,
                    'location': q.location_id.complete_name,
                }
            products[key]['qty_on_hand'] += q.quantity

        return _json({
            'client': partner.name,
            'as_of': datetime.now().isoformat(),
            'products': list(products.values()),
        })

    # ── Order status ──────────────────────────────────────────────────
    @http.route('/api/3pl/order/<string:ref>/status', type='http', auth='none', methods=['GET'], csrf=False)
    def api_order_status(self, ref, **kwargs):
        api_key, err = _auth_client(request)
        if err:
            return err

        partner = api_key.partner_id
        pids = _partner_ids(partner)

        picking = request.env['stock.picking'].sudo().search([
            ('origin', '=', ref),
            ('partner_id', 'in', pids),
        ], limit=1)

        if not picking:
            return _json({'error': f'Order not found: {ref}'}, 404)

        return _json({
            'ref': ref,
            '3pl_name': picking.name,
            'type': picking.picking_type_code,
            'state': picking.state,
            'scheduled_date': picking.scheduled_date,
            'date_done': picking.date_done,
            'partner': picking.partner_id.name,
        })

    # ── Create inbound ────────────────────────────────────────────────
    @http.route('/api/3pl/order/inbound', type='http', auth='none', methods=['POST'], csrf=False)
    def api_create_inbound(self, **kwargs):
        api_key, err = _auth_client(request)
        if err:
            return err

        try:
            body = json.loads(request.httprequest.data or b'{}')
        except Exception:
            return _json({'error': 'Invalid JSON body'}, 400)

        partner = api_key.partner_id
        ref = body.get('ref') or body.get('origin', '')
        products = body.get('products', [])
        note = body.get('note', '')

        if not products:
            return _json({'error': 'products list is required'}, 400)

        # Find receipt operation type
        picking_type = request.env['stock.picking.type'].sudo().search([
            ('code', '=', 'incoming'),
            ('warehouse_id', '!=', False),
        ], limit=1)
        if not picking_type:
            return _json({'error': '3PL has no inbound operation type configured'}, 500)

        moves = []
        errors = []
        for item in products:
            item_ref = item.get('ref') or item.get('default_code', '')
            qty = float(item.get('qty', item.get('quantity', 0)))
            product = request.env['product.product'].sudo().search(
                [('default_code', '=', item_ref)], limit=1
            )
            if not product:
                errors.append(f'Product not found: {item_ref}')
                continue
            moves.append((0, 0, {
                'name': product.name,
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': qty,
                'location_id': picking_type.default_location_src_id.id or request.env.ref('stock.stock_location_suppliers').id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'company_id': picking_type.company_id.id,
            }))

        if errors:
            return _json({'error': 'Product errors', 'details': errors}, 400)

        picking = request.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type.id,
            'partner_id': partner.id,
            'origin': ref,
            'note': note,
            'move_ids': moves,
            'owner_id': partner.id,
            'company_id': picking_type.company_id.id,
        })
        picking.action_confirm()

        return _json({
            'status': 'created',
            '3pl_ref': picking.name,
            'origin': ref,
            'state': picking.state,
        }, 201)

    # ── Create outbound ───────────────────────────────────────────────
    @http.route('/api/3pl/order/outbound', type='http', auth='none', methods=['POST'], csrf=False)
    def api_create_outbound(self, **kwargs):
        api_key, err = _auth_client(request)
        if err:
            return err

        try:
            body = json.loads(request.httprequest.data or b'{}')
        except Exception:
            return _json({'error': 'Invalid JSON body'}, 400)

        partner = api_key.partner_id
        ref = body.get('ref') or body.get('origin', '')
        products = body.get('products', [])
        address = body.get('address', '')
        contact_name = body.get('contact_name', '')
        contact_phone = body.get('contact_phone', '')
        note = body.get('note', '')

        if not products:
            return _json({'error': 'products list is required'}, 400)

        picking_type = request.env['stock.picking.type'].sudo().search([
            ('code', '=', 'outgoing'),
            ('warehouse_id', '!=', False),
        ], limit=1)
        if not picking_type:
            return _json({'error': '3PL has no outbound operation type configured'}, 500)

        moves = []
        errors = []
        for item in products:
            item_ref = item.get('ref') or item.get('default_code', '')
            qty = float(item.get('qty', item.get('quantity', 0)))
            product = request.env['product.product'].sudo().search(
                [('default_code', '=', item_ref)], limit=1
            )
            if not product:
                errors.append(f'Product not found: {item_ref}')
                continue
            moves.append((0, 0, {
                'name': product.name,
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': qty,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id or request.env.ref('stock.stock_location_customers').id,
                'company_id': picking_type.company_id.id,
            }))

        if errors:
            return _json({'error': 'Product errors', 'details': errors}, 400)

        full_note = note
        if address:
            full_note = f'Deliver to: {address}\n' + full_note
        if contact_name or contact_phone:
            full_note += f'\nContact: {contact_name} {contact_phone}'.strip()

        picking = request.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type.id,
            'partner_id': partner.id,
            'origin': ref,
            'note': full_note.strip(),
            'move_ids': moves,
            'owner_id': partner.id,
            'company_id': picking_type.company_id.id,
        })
        picking.action_confirm()

        return _json({
            'status': 'created',
            '3pl_ref': picking.name,
            'origin': ref,
            'state': picking.state,
        }, 201)
