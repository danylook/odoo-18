# -*- coding: utf-8 -*-
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class Tpl3plWebhook(http.Controller):

    @http.route('/webhook/3pl', type='http', auth='none', methods=['POST'], csrf=False)
    def webhook_3pl(self, **kwargs):
        get = request.env['ir.config_parameter'].sudo().get_param
        secret = get('tpl3pl.webhook.secret', '')
        incoming = request.httprequest.headers.get('X-Webhook-Secret', '')
        if secret and not hmac.compare_digest(str(secret), str(incoming)):
            _logger.warning('3PL webhook: bad secret from %s', request.httprequest.remote_addr)
            return request.make_response('Unauthorized', status=401)

        try:
            body = json.loads(request.httprequest.data or b'{}')
        except Exception:
            return request.make_response('Bad Request', status=400)

        event = body.get('event', '')
        origin = body.get('origin', '')
        _logger.info('3PL webhook received: event=%s origin=%s', event, origin)

        if event == 'picking.validated':
            try:
                request.env['tpl.3pl.stock'].sudo().action_sync()
            except Exception as e:
                _logger.error('3PL webhook stock sync failed: %s', e)

        return request.make_response(
            json.dumps({'status': 'ok', 'event': event}),
            headers=[('Content-Type', 'application/json')],
        )
