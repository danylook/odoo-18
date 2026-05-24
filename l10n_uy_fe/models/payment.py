# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import requests
import json
import base64

class AccountPayment(models.Model):
    _inherit = "account.payment"

    def post_payment_dgi(self):
        for rec in self:
            if rec.state != 'posted':
                raise ValidationError('No se puede comunicar a DGI pagos no confirmados')
            move_id = None
            for move_line in rec.move_id.line_ids.filtered(lambda l: l.account_id.internal_type == 'receivable' and l.credit != 0):
                url = "%s/v2/recibos/crear"%(self.env['ir.config_parameter'].sudo().get_param('biller_uy_url'))
                domain = [('credit_move_id','=',move_line.id)]
                reconcile_ids = self.env['account.partial.reconcile'].search(domain)
                bearer_token = ''
                debit_move_ids = self.env['account.partial.reconcile']
                document_types = []
                total_reconciled_amount = 0
                for reconcile_id in reconcile_ids:
                    if reconcile_id.debit_move_id.move_id.journal_id.bearer_token:
                        bearer_token = reconcile_id.debit_move_id.move_id.journal_id.bearer_token
                    doc_code = reconcile_id.debit_move_id.move_id.l10n_latam_document_type_id.code
                    if doc_code and doc_code not in document_types:
                        move_id = reconcile_id.debit_move_id.move_id
                        document_types.append(doc_code)
                        debit_move_ids += reconcile_id
                        total_reconciled_amount = total_reconciled_amount + abs(reconcile_id.debit_amount_currency)
                if len(document_types) == 0:
                    raise ValidationError('Pago sin facturas conciliadas')
                if len(document_types) != 1:
                    raise ValidationError('No se puede informar a DGI pagos de dos tipos de documento diferentes %s'%(document_types))
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer %s"%(bearer_token)
                }
                cliente_dict = {
                    "tipo_documento": rec.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code,
                    "documento": rec.partner_id.vat,
                    "razon_social": rec.partner_id.name,
                    "nombre_fantasia": rec.partner_id.name,
                    "sucursal": {
                        "direccion": rec.partner_id.street,
                        "ciudad": rec.partner_id.city,
                        "pais": rec.partner_id.country_id.code
                        }
                    }
                pago_dict = {
                        'fecha': str(rec.date),
                        'monto': abs(rec.amount),
                        'referencia': rec.ref or rec.name,
                        }
                payment_dict = {
                        "tipo_comprobante": move_id.l10n_latam_document_type_id.code,
                        "forma_pago": move_id.forma_pago,
                        "sucursal": move_id.journal_id.l10n_uy_sucursal,
                        "moneda": rec.currency_id.name,
                        "montos_brutos": 0,
                        "fecha_emision": str(rec.date),
                        }
                        #"tasa_cambio": rec.exchange_rate,
                        #}
                referencias = []
                for debit_move_id in debit_move_ids:
                    vals = {
                            "padre": debit_move_id.debit_move_id.move_id.biller_id,
                            "total": debit_move_id.debit_amount_currency,
                            #"total": debit_move_id.debit_move_id.move_id.amount_total_in_currency_signed,
                            }
                    referencias.append(vals)
                payment_dict["cliente"] = cliente_dict
                payment_dict["referencias"] = referencias
                payment_dict["pago"] = pago_dict
                payload = json.dumps(payment_dict)
                response = requests.request("POST", url, headers=headers, data=payload)
                if response.status_code >= 400:
                    raise ValidationError(response.text)
                else:
                    response = response.json()
                    rec.biller_id = response.get('id')
                    rec.serie = response.get('serie')
                    rec.numero = response.get('numero')
                    rec.biller_hash = response.get('hash')
                    rec.name = '%s-%s'%(rec.serie,rec.numero)
                self.env.cr.commit()


    payload = fields.Text('Payload',copy=False)
    token = fields.Char('Token',copy=False)
    biller_id = fields.Char('Biller ID',index=True,copy=False)
    serie = fields.Char('Serie',copy=False)
    numero = fields.Char('Numero',copy=False)
    biller_hash = fields.Char('Hash',copy=False)
