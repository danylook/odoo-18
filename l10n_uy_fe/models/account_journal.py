# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import date
import requests
import json

class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def obtener_comprobantes(self, date_parm=None):
        journals = self.env['account.journal'].search([('type','=','sale'),('bearer_token','!=',False),('l10n_uy_sucursal','!=',False)])
        for journal in journals:
            if not date_parm:
                date_parm = str(date.today())
            url = "%s/v2/comprobantes/obtener?sucursal=%s&desde=%s 00:00:00&hasta=%s 23:59:59"%(self.env['ir.config_parameter'].sudo().get_param('biller_uy_url'),journal.l10n_uy_sucursal,date_parm,date_parm)
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer %s"%(journal.bearer_token)
            }
            payload = {}
            response = requests.request("GET", url, headers=headers, data=payload)
            if response.status_code == 200:
                documents = response.json()
                for doc in documents:
                    biller_id = str(doc.get('id'))
                    move = self.env['account.move'].search([('biller_id','=',biller_id)])
                    if move:
                        vals = {
                                'cae_nro': doc.get('cae').get('numero'),
                                'cae_inicio': doc.get('cae').get('inicio'),
                                'cae_fin': doc.get('cae').get('fin'),
                                'cae_fecha_expiracion': doc.get('cae').get('fecha_expiracion'),
                                'es_nota_ajuste': doc.get('esNotaAjuste'),
                                'tot_iva_tasa_min': doc.get('tot_iva_tasa_min'),
                                'tot_iva_tasa_base': doc.get('tot_iva_tasa_base'),
                                'tot_iva_tasa_otra': doc.get('tot_iva_tasa_otra'),
                                }
                        move.write(vals)


    l10n_uy_sucursal = fields.Integer('Sucursal', help="Usar el valor de Inicio/Ajustes/Sucursales en Biller")
    bearer_token = fields.Char('Bearer Token')
