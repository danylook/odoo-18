# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint
import requests

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request, Response


_logger = logging.getLogger(__name__)


class MercadoPagoController(http.Controller):
    _return_url = '/return'
    _webhook_url = '/webhook'

    @http.route(_return_url, type='http', methods=['GET'], auth='public')
    def mercado_pago_uy_return_from_checkout(self, **data):
        """ Process the notification data sent by Mercado Pago after redirection from checkout.

        :param dict data: The notification data.
        """
        _logger.info("[DEBUG] Entrando a mercado_pago_uy_return_from_checkout con data: %s", pprint.pformat(data))
        # Handle the notification data.
        _logger.info("Handling redirection from Mercado Pago with data:\n%s", pprint.pformat(data))
        if data.get('payment_id') != 'null':
            _logger.info("[DEBUG] Llamando a _handle_notification_data desde return con: %s", data)
            request.env['payment.transaction'].sudo()._handle_notification_data(
                'mercado_pago_uy', data
            )
        else:
            _logger.info("[DEBUG] El usuario canceló el pago o no se recibió payment_id")

        # Redirect the user to the status page.
        return request.redirect('/payment/status')

    @http.route(
        f'{_webhook_url}/<reference>', type='http', auth='public', methods=['POST'], csrf=False
    )
    def mercado_pago_uy_webhook(self, reference, **_kwargs):
        # Log headers y cuerpo crudo
        _logger.info("[WEBHOOK] Headers: %s", dict(request.httprequest.headers))
        raw_body = request.httprequest.get_data(as_text=True)
        _logger.info("[WEBHOOK] Raw body: %s", raw_body)
        try:
            data = request.get_json_data()
            topic = request.httprequest.args.get('topic') or data.get('topic') or data.get('type')
            merchant_order_id = request.httprequest.args.get('id') or data.get('data', {}).get('id')
            resource = data.get('resource') or f"https://api.mercadolibre.com/merchant_orders/{merchant_order_id}"

            _logger.info("Procesando notificación: id=%s, topic=%s, reference=%s", merchant_order_id, topic, reference)
            _logger.info("Datos JSON: %s", pprint.pformat(data))

            provider = request.env['payment.provider'].sudo().search([('code', '=', 'mercado_pago_uy')], limit=1)
            access_token = provider.mercado_pago_uy_access_token if provider else None
            if not access_token:
                _logger.error("No se encontró access_token de Mercado Pago en la configuración del proveedor.")
                return Response('Falta access_token', status=500, headers={'Content-Type': 'text/plain'})

            if topic == 'merchant_order' and merchant_order_id:
                resp = requests.get(
                    resource,
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                if resp.status_code != 200:
                    _logger.error("Error al consultar la merchant_order en Mercado Pago: %s", resp.text)
                    return Response('Error consultando merchant_order', status=500, headers={'Content-Type': 'text/plain'})
                merchant_order = resp.json()
                payments = merchant_order.get('payments', [])
                if not payments:
                    _logger.warning("La merchant_order %s no tiene pagos asociados. No se procesará ningún pago.", merchant_order_id)
                for payment in payments:
                    payment_id = payment.get('id')
                    if not payment_id:
                        _logger.warning("Se encontró un pago sin 'id' en la merchant_order %s. Datos del pago: %s", merchant_order_id, payment)
                        continue
                    _logger.info("Procesando payment_id %s para referencia %s", payment_id, reference)
                    _logger.info("Llamando a _handle_notification_data con: %s", {'external_reference': reference, 'payment_id': payment_id})
                    try:
                        request.env['payment.transaction'].sudo()._handle_notification_data(
                            'mercado_pago_uy', {'external_reference': reference, 'payment_id': payment_id}
                        )
                        _logger.info("Procesamiento de pago exitoso para payment_id %s", payment_id)
                    except Exception as e:
                        _logger.exception("Error procesando payment_id %s: %s", payment_id, str(e))
                        # Ejemplo de notificación a admin (adaptar según tus necesidades):
                        # request.env['mail.mail'].sudo().create({
                        #     'subject': 'Error en Webhook Mercado Pago',
                        #     'body_html': f'<pre>{str(e)}</pre>',
                        #     'email_to': 'admin@tudominio.com',
                        # }).send()
                return Response('merchant_order procesado', status=200, headers={'Content-Type': 'text/plain'})

            elif topic in ('payment', 'payment.created', 'payment.updated'):
                payment_id = request.httprequest.args.get('id') or data.get('data', {}).get('id')
                if not payment_id:
                    _logger.error("No se recibió payment_id en la notificación de pago.")
                    return Response('Falta payment_id', status=400, headers={'Content-Type': 'text/plain'})
                _logger.info("Procesando notificación de pago: payment_id=%s, reference=%s", payment_id, reference)
                try:
                    request.env['payment.transaction'].sudo()._handle_notification_data(
                        'mercado_pago_uy', {'external_reference': reference, 'payment_id': payment_id}
                    )
                except Exception as e:
                    _logger.exception("Error procesando payment_id %s: %s", payment_id, str(e))
                    return Response('Error procesando pago', status=500, headers={'Content-Type': 'text/plain'})
                return Response('payment procesado', status=200, headers={'Content-Type': 'text/plain'})

            else:
                _logger.warning("Notificación recibida con topic desconocido: %s", topic)
                return Response('topic desconocido', status=400, headers={'Content-Type': 'text/plain'})

        except Exception as e:
            _logger.exception("Error inesperado en el webhook de Mercado Pago: %s", str(e))
            # Ejemplo de notificación a admin (adaptar según tus necesidades):
            # request.env['mail.mail'].sudo().create({
            #     'subject': 'Error crítico en Webhook Mercado Pago',
            #     'body_html': f'<pre>{str(e)}</pre>',
            #     'email_to': 'admin@tudominio.com',
            # }).send()
            return Response('Error interno del servidor', status=500, headers={'Content-Type': 'text/plain'})



