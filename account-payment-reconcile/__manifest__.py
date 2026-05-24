# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Payment Reconcile UYU',
    'license': 'AGPL-3',
    'version': '18.0.0.2.9',
    'category': 'Sale',
    'depends': ['account','base'],
    'description': """
    se debe definir la variable moneda en los journal de los bancos para que funcione bien rev 2.
    """,
    'data': [
        'account_view.xml',
        'security/ir.model.access.csv',
        'wizard/wizard_view.xml',
    ],
    'demo': [
        ],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
