# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from math import floor

class ResPartner(models.Model):
    _inherit = "res.partner"


    @staticmethod
    def _validate_ci(vat):
        if not vat:
            return False
        vat = vat.replace("-", "").replace('.', '')
        sum = 0
        if not vat:
            return False
        if vat == 'x':
            return True
        try:
            int(vat)
        except ValueError:
            return False
        vat = "%08d" % int(vat)
        long = len(vat)
        if long > 8:
            return False
        code = [2, 9, 8, 7, 6, 3, 4]
        for f in range(0, long - 1):
            sum += int(vat[f]) * int(code[f])
        total = sum + int(vat[-1])
        subtraction = total % 10
        if subtraction != 0:
            return False
        return True

    @staticmethod
    def _validate_rut(vat):
        factor = '43298765432'
        sum = 0
        dig_check = None
        if not vat or len(vat) != 12:
            return False
        try:
            int(vat)
        except ValueError:
            return False
        for f in range(0, 11):
            sum += int(factor[f]) * int(vat[f])
        subtraction = 11 - floor((sum % 11))
        if subtraction < 10:
            dig_check = subtraction
        elif subtraction == 10:
            dig_check = ""
        elif subtraction == 11:
            dig_check = 0

        if not int(vat[11]) == dig_check:
            return False
        return True

    @api.constrains('vat', 'l10n_latam_identification_type_id')
    def check_vat(self):
        """ Since we validate more documents than the vat for Argentinian partners (CUIT - VAT AR, CUIL, DNI) we
        extend this method in order to process it. """
        # NOTE by the moment we include the CUIT (VAT AR) validation also here because we extend the messages
        # errors to be more friendly to the user. In a future when Odoo improve the base_vat message errors
        # we can change this method and use the base_vat.check_vat_ar method.s
        uy_docs = [self.env.ref('l10n_uy_fe.it_uy_rut').id,self.env.ref('l10n_uy_fe.it_uy_ci').id]
        l10n_uy_partners = self.filtered(lambda x: x.l10n_latam_identification_type_id.id in uy_docs)
        for partner in l10n_uy_partners:
            if partner.l10n_latam_identification_type_id.id == self.env.ref('l10n_uy_fe.it_uy_rut').id:
                if partner.vat and not partner._validate_rut(partner.vat):
                    raise ValidationError('Nro. de documento incorrecto')
            if partner.l10n_latam_identification_type_id.id == self.env.ref('l10n_uy_fe.it_uy_ci').id:
                if partner.vat and not partner._validate_ci(partner.vat):
                    raise ValidationError('Nro. de documento incorrecto')
        return super(ResPartner, self - l10n_uy_partners).check_vat()



