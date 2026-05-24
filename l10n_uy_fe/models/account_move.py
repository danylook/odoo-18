# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import requests
import json
import base64
import qrcode
from io import BytesIO
import time

INDICADOR_FACTURACION = [
    ('1', 'Exento de IVA'),
    ('2', 'Tasa mínima'),
    ('3', 'Tasa básica'),
    ('4', 'Otra tasa'),
    ('5', 'Entrega gratuita'),
    ('6', 'Producto o servicio no facturable'),
    ('7', 'Producto o servicio no facturable negativo'),
    ('8', 'Ítem a rebajar en e-remitos y en e-remitos de exportación'),
    ('9', 'Ítem a anular en resguardos'),
    ('10', 'Exportación y asimiladas'),
    ('11', 'Impuesto percibido'),
    ('12', 'IVA en suspenso'),
    ('13', 'Ítem vendido no contribuyente'),
    ('14', 'Ítem vendido contribuyente monotributo'),
    ('15', 'Ítem vendido contribuyente IMEBA')
]

class AccountMove(models.Model):
    _inherit = "account.move"

    forma_pago = fields.Selection(
        selection=[('1', 'contado'), ('2', 'credito')],
        string='Forma de pago',
        default='2',
        copy=False
    )
    token = fields.Char('Token', copy=False)
    payload = fields.Text('Payload', copy=False)
    biller_id = fields.Char('Biller ID', index=True, copy=False)
    serie = fields.Char('Serie', copy=False)
    numero = fields.Char('Numero', copy=False)
    biller_hash = fields.Char('Hash', copy=False)
    tot_iva_tasa_min = fields.Float('Total IVA Tasa Mínima', copy=False)
    tot_iva_tasa_base = fields.Float('Total IVA Tasa Base', copy=False)
    tot_iva_tasa_otra = fields.Float('Total IVA Tasa Otra', copy=False)
    es_nota_ajuste = fields.Boolean('Es Nota Ajuste', copy=False)
    cae_nro = fields.Char('Nro. CAE', copy=False)
    cae_inicio = fields.Integer('CAE Inicio', copy=False)
    cae_fin = fields.Integer('CAE Fin', copy=False)
    cae_fecha_expiracion = fields.Date('Fecha Expiración CAE', copy=False)
    related_invoices_ids = fields.Many2many(
        'account.move',
        'related_accont_invoices',
        'refund_id',
        'move_id',
        'Facturas referenciadas',
        copy=False
    )
    comprobante_dgi_pdf = fields.Binary('Comprobante DGI', copy=False)
    fe_qr_url = fields.Char('URL QR', compute='_compute_fe_qr_url')
    qr_code = fields.Binary('QR Code', copy=False)
    footer_line = fields.Char('Footer Line', compute="_compute_footer_line")
    extra_footer_line = fields.Text('Extra Footer Line', compute="_compute_extra_footer_line")

    @api.depends('l10n_latam_available_document_type_ids', 'debit_origin_id')
    def _compute_l10n_latam_document_type(self):
        for rec in self.filtered(lambda x: x.state == 'draft'):
            document_types = rec.l10n_latam_available_document_type_ids._origin
            document_types = document_types.filtered(
                lambda x: x.l10n_uy_doc_type == rec.partner_id.l10n_latam_identification_type_id.l10n_uy_dgi_code
            )
            if document_types:
                rec.l10n_latam_document_type_id = document_types[0].id

    @api.depends('cae_nro', 'cae_inicio', 'cae_fin', 'create_date', 'cae_fecha_expiracion')
    def _compute_footer_line(self):
        for rec in self:
            rec.footer_line = (
                f"Iva al dia | Nro CAE: {rec.cae_nro} | Rango: {rec.cae_inicio} - {rec.cae_fin} | "
                f"CAE Fecha de autorización: {str(rec.create_date)[:10]} | CAE vencimiento: {rec.cae_fecha_expiracion}"
            )

    @api.depends('footer_line')
    def _compute_extra_footer_line(self):
        for rec in self:
            footer_text = self.env['ir.config_parameter'].sudo().get_param('footer_line', '')
            rec.extra_footer_line = footer_text

    @api.depends('state', 'move_type', 'biller_hash')
    def _compute_fe_qr_url(self):
        for rec in self:
            res = ''
            values = []
            if rec.state == 'posted' and rec.move_type in ['out_refund', 'out_invoice'] and rec.biller_hash:
                dgi_qr_url = self.env['ir.config_parameter'].sudo().get_param(
                    'dgi_qr_url', 'https://www.efactura.dgi.gub.uy/consultaQR/cfe?'
                )
                rut = rec.company_id.partner_id.vat
                values.append(dgi_qr_url + rut)
                values.append(rec.l10n_latam_document_type_id.code)
                values.append(rec.serie)
                values.append(rec.numero)
                values.append(str(rec.amount_total))
                date_invoice = rec.invoice_date.strftime('%d/%m/%Y')
                values.append(date_invoice)
                values.append(rec.biller_hash)
            rec.fe_qr_url = res + ','.join(values)

    def update_qr_code(self):
        for rec in self:
            if rec.fe_qr_url:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(rec.fe_qr_url)
                qr.make(fit=True)
                img = qr.make_image()
                temp = BytesIO()
                img.save(temp, format="PNG")
                qr_image = base64.b64encode(temp.getvalue())
                rec.qr_code = qr_image

    def btn_pull_pdf(self):
        self.ensure_one()
        if not self.biller_id:
            raise ValidationError('El documento no cuenta con biller_id')
        if not self.journal_id:
            raise ValidationError('No hay diario para el presente documento')
        self.env['account.journal'].obtener_comprobantes()
        url = f"{self.env['ir.config_parameter'].sudo().get_param('biller_uy_url')}/v2/comprobantes/pdf?id={self.biller_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.journal_id.bearer_token}"
        }
        response = requests.request("POST", url, headers=headers)
        if response.status_code == 200:
            self.comprobante_dgi_pdf = response.content
            self.update_qr_code()

    def action_post(self):
        for rec in self.filtered(lambda m: m.move_type == 'out_refund'):
            if not rec.related_invoices_ids:
                raise ValidationError('Debe indicar facturas relacionadas para las notas de crédito')
        res = super(AccountMove, self).action_post()
        for rec in self.filtered(lambda m: m.move_type in ['out_invoice', 'out_refund']):
            if rec.journal_id.bearer_token and rec.invoice_line_ids:
                url = f"{self.env['ir.config_parameter'].sudo().get_param('biller_uy_url')}/v2/comprobantes/crear"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {rec.journal_id.bearer_token}"
                }
                items = [
                    {
                        "cantidad": line.quantity,
                        "concepto": line.name,
                        "precio": line.price_unit * (1 - (line.discount / 100)),
                        "indicador_facturacion": line.indicador_facturacion
                    }
                    for line in rec.invoice_line_ids
                ]
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
                invoice_dict = {
                    "tipo_comprobante": int(rec.l10n_latam_document_type_id.code),
                    "forma_pago": rec.forma_pago,
                    "adenda": rec.narration or '',
                    "fecha_vencimiento": rec.invoice_date_due.strftime('%d/%m/%Y') if rec.invoice_date_due else '',
                    "sucursal": rec.journal_id.l10n_uy_sucursal,
                    "moneda": rec.currency_id.name,
                    "montos_brutos": 0,
                    "cliente": cliente_dict if rec.partner_id.name != 'CONSUMIDOR FINAL' else '-',
                    "items": items
                }
                if rec.move_type == 'out_refund' and rec.related_invoices_ids:
                    if rec.related_invoices_ids[0].biller_id:
                        invoice_dict["referencias"] = rec.related_invoices_ids.mapped('biller_id')
                    else:
                        invoice_dict["referencias"] = [
                            {
                                'tipo': str(rec.related_invoices_ids[0].l10n_latam_document_type_id.code),
                                'serie': rec.related_invoices_ids[0].name[:1],
                                'numero': rec.related_invoices_ids[0].name[1:],
                            }
                        ]
                payload = json.dumps(invoice_dict)
                response = requests.request("POST", url, headers=headers, data=payload)
                if response.status_code >= 400:
                    raise ValidationError(response.text)
                else:
                    response_data = response.json()
                    rec.biller_id = response_data.get('id')
                    rec.serie = response_data.get('serie')
                    rec.numero = response_data.get('numero')
                    rec.biller_hash = response_data.get('hash')
                    self.env.cr.commit()
        time.sleep(5)
        for rec in self.filtered(lambda m: m.move_type in ['out_invoice', 'out_refund']):
            try:
                rec.btn_pull_pdf()
            except Exception:
                continue
        return res

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    indicador_facturacion = fields.Selection(
        selection=INDICADOR_FACTURACION,
        string='Indicador Facturación',
        default='3',
        copy=False
    )
