# -*- coding: utf-8 -*-
import logging
import xmlrpc.client
import socket
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class _TimeoutTransport(xmlrpc.client.Transport):
    """xmlrpc.client Transport with configurable socket timeout (HTTP)."""
    def __init__(self, timeout=60, *a, **kw):
        super().__init__(*a, **kw)
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class _TimeoutSafeTransport(xmlrpc.client.SafeTransport):
    """xmlrpc.client SafeTransport with configurable socket timeout (HTTPS)."""
    def __init__(self, timeout=60, *a, **kw):
        super().__init__(*a, **kw)
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class TplClientConfig(models.Model):
    _name = 'tpl.client.config'
    _description = '3PL Client Connection Config'
    _rec_name = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    client_url = fields.Char('Client URL', required=True,
                             help='Base URL of the client Odoo instance, '
                                  'e.g. http://3pl-cliente.ecolight.com.uy')
    client_db = fields.Char('Client DB', required=True)
    client_user = fields.Char('Client User', required=True, default='admin')
    client_password = fields.Char('Client Password', required=True)
    # Which backend partner represents this client company.
    # Set this to the res.partner id of the client in the backend (3pl) database.
    # All stock quants/moves owned by this partner will be synced back to this
    # client Odoo instance.
    owner_partner_id = fields.Many2one(
        'res.partner', string='Owner Partner (backend)',
        required=True,
        help='The partner in THIS backend database that represents this client '
             'company. Used to route back-sync calls to the correct client.')

    def _get_transport(self, timeout):
        """Return the correct transport based on client_url scheme."""
        if self.client_url.startswith('https://'):
            return _TimeoutSafeTransport(timeout=timeout)
        return _TimeoutTransport(timeout=timeout)

    def _client_call(self, model, method, args, kwargs=None, timeout=60):
        """Execute XML-RPC call on the 3PL client Odoo instance."""
        self.ensure_one()
        try:
            common = xmlrpc.client.ServerProxy(
                self.client_url + '/xmlrpc/2/common',
                transport=self._get_transport(timeout=timeout))
            uid = common.authenticate(
                self.client_db, self.client_user, self.client_password, {})
            if not uid:
                raise ValueError(
                    'Cannot authenticate to client %s as %s' %
                    (self.client_url, self.client_user))
            m = xmlrpc.client.ServerProxy(
                self.client_url + '/xmlrpc/2/object',
                transport=self._get_transport(timeout=timeout))
            return m.execute_kw(
                self.client_db, uid, self.client_password,
                model, method, args, kwargs or {})
        except Exception as e:
            _logger.error('3PL BackSync RPC [%s.%s]: %s', model, method, e)
            raise

    @api.model
    def get_active(self):
        """Return the first active config (single-client compatibility)."""
        return self.search([('active', '=', True)], limit=1)

    @api.model
    def get_for_owner(self, owner_partner_id):
        """Return the config for a given backend owner partner id.
        
        Use this in multi-client setups to route back-sync to the correct
        client instance.
        """
        cfg = self.search([
            ('active', '=', True),
            ('owner_partner_id', '=', owner_partner_id),
        ], limit=1)
        if not cfg:
            _logger.warning(
                '3PL BackSync: no client config for owner partner id=%s',
                owner_partner_id)
        return cfg
