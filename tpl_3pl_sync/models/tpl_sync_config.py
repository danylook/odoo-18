# -*- coding: utf-8 -*-
import logging
import xmlrpc.client

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

BACKEND_PICKING_TYPES = {
    'in':   1,    # My Company: Receipts
    'pick': 3,    # My Company: Pick
    'pack': 4,    # My Company: Pack
    'out':  2,    # My Company: Delivery Orders
}
BACKEND_LOCATIONS = {
    'vendor':  4,   # Partners/Vendors
    'input':   9,   # WH/Input
    'stock':   8,   # WH/Stock
    'packing': 12,  # WH/Packing Zone
    'output':  11,  # WH/Output
    'customer': 5,  # Partners/Customers
}


class TplSyncConfig(models.Model):
    _name = 'tpl.sync.config'
    _description = '3PL Backend Sync Configuration'
    _rec_name = 'name'

    name = fields.Char('Name', required=True, default='3PL Warehouse Backend')
    active = fields.Boolean(default=True)
    backend_url = fields.Char(
        'Backend URL', required=True,
        default='http://192.168.1.65:8069',
        help='Base URL of the 3PL warehouse Odoo instance.',
    )
    backend_db = fields.Char(
        'Backend Database', required=True, default='3pl',
    )
    backend_user = fields.Char(
        'Backend Login', required=True, default='admin',
    )
    backend_password = fields.Char(
        'Backend Password', required=True, default='Admin@1234',
    )
    backend_owner_id = fields.Integer(
        'Owner partner ID in backend', default=16,
        help='res.partner ID of this client company in the backend database.',
    )
    enabled_in = fields.Boolean(
        'On ECO/IN done → create + validate WH/IN', default=True,
    )
    enabled_sale_confirm = fields.Boolean(
        'On sale confirm → create WH/OUT', default=True,
    )
    enabled_pick = fields.Boolean(
        'On ECO/PICK done → create + validate WH/PICK', default=True,
    )
    enabled_pack = fields.Boolean(
        'On ECO/PACK done → validate WH/PACK', default=True,
    )
    enabled_out = fields.Boolean(
        'On ECO/OUT done → validate WH/OUT', default=True,
    )

    # ── connection helpers ───────────────────────────────────────────

    def _get_backend_proxy(self):
        """Return (m, uid) xmlrpc proxies for the backend."""
        self.ensure_one()
        common = xmlrpc.client.ServerProxy(self.backend_url + '/xmlrpc/2/common')
        uid = common.authenticate(
            self.backend_db, self.backend_user, self.backend_password, {})
        if not uid:
            raise ValueError(
                'Cannot authenticate to backend %s as %s' %
                (self.backend_url, self.backend_user))
        m = xmlrpc.client.ServerProxy(self.backend_url + '/xmlrpc/2/object')
        return m, uid

    def _backend_call(self, model, method, args, kwargs=None):
        """Execute a single RPC call on the backend, logging errors."""
        self.ensure_one()
        try:
            m, uid = self._get_backend_proxy()
            return m.execute_kw(
                self.backend_db, uid, self.backend_password,
                model, method, args, kwargs or {})
        except Exception as e:
            _logger.error(
                '3PL Sync RPC error [%s.%s]: %s', model, method, e)
            raise

    # ── product mapping (by default_code) ───────────────────────────

    def _map_products(self, move_ids):
        """
        Given client stock.move IDs, return a list of dicts ready to use
        in backend move_ids [(0,0,{...})].
        Maps by product.default_code which must be identical on both sides.
        """
        self.ensure_one()
        moves = self.env['stock.move'].browse(move_ids)
        result = []
        for mv in moves:
            code = mv.product_id.default_code
            if not code:
                _logger.warning(
                    '3PL Sync: move %s has no default_code, skipping', mv.id)
                continue
            # Find product on backend by default_code
            backend_prods = self._backend_call(
                'product.product', 'search_read',
                [[['default_code', '=', code]]],
                {'fields': ['id', 'uom_id'], 'limit': 1})
            if not backend_prods:
                _logger.warning(
                    '3PL Sync: product %s not found in backend, skipping', code)
                continue
            bp = backend_prods[0]
            result.append({
                'product_id': bp['id'],
                'product_uom_qty': mv.product_uom_qty,
                'product_uom': bp['uom_id'][0],
                'restrict_partner_id': self.backend_owner_id,
            })
        return result

    @api.model
    def get_active(self):
        """Return the first active config record, or None."""
        return self.search([('active', '=', True)], limit=1)
