# -*- coding: utf-8 -*-
from odoo import models, _
from odoo.exceptions import UserError

_3PL_LOCATION_NAME = '3PL Warehouse'


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def action_apply_inventory(self):
        """Block manual inventory adjustments on the 3PL virtual location.

        Only system/admin users (base.group_system) may bypass this.
        All other users get a UserError explaining that stock must be
        managed from the 3PL server.
        """
        if not self.env.user.has_group('base.group_system'):
            tpl_quants = self.filtered(
                lambda q: q.location_id.name == _3PL_LOCATION_NAME
                and q.location_id.usage == 'internal'
            )
            if tpl_quants:
                raise UserError(_(
                    'Direct inventory adjustments on "3PL Warehouse" stock are '
                    'not allowed. Stock is managed automatically by the 3PL server. '
                    'To adjust quantities, please contact your 3PL warehouse operator.'
                ))
        return super().action_apply_inventory()
