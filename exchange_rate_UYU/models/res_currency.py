from odoo import tools, models, fields, api, _
from datetime import datetime,date
import requests
from bs4 import BeautifulSoup
from py_bcu.bcu_cotizacion import get_cotizacion
from odoo.exceptions import ValidationError

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def get_rou_exchange_rate(self):
        cot = get_cotizacion()
        print(cot)
        # r = requests.get('https://www.bcu.gub.uy/Estadisticas-e-Indicadores/Paginas/Cotizaciones.aspx')
        # soup = BeautifulSoup(r.text, 'lxml')
        #
        # tds = soup.find_all('td',class_='Moneda alt')
        # index = -1
        # for i,td in enumerate(tds):
        #     if td.get_text() == 'DLS. USA BILLETE':
        #         index = i
        #         break
        # if index > (-1):
        #     exchange_rate = soup.find_all('td',class_='Venta alt')[index].get_text()
        #     if exchange_rate != '':
                #exchange_rate = float(exchange_rate.replace(',','.'))

        ini = 2  # posición inicial de la subcadena
        fin = 7  # posición final de la subcadena (excluida)

        exchange_rate = cot[0]
        print (exchange_rate)
        currency_id = self.env.ref('base.USD')
        vals = {
                'name': str(date.today()),
                'rate': 1 / (exchange_rate or 1),
                'currency_id': currency_id.id,
                }
        new_rate = self.env['res.currency.rate'].search([
            ('name','=',str(date.today())),
            ('currency_id','=',currency_id.id)])
        if not new_rate:
            res = self.env['res.currency.rate'].create(vals)
        else:
            new_rate.write(vals)

class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    def _compute_inverse_rate(self):
        for rec in self:
            res = 0
            if rec.rate > 0:
                res = 1 / rec.rate
            rec.inverse_rate = res

    inverse_rate = fields.Float('Tipo de Cambio Inverso',compute=_compute_inverse_rate)
