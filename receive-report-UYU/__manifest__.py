# -*- coding: utf-8 -*-
{
    'name': 'Receive Report UYU PDF',
    'license': 'AGPL-3',
    'version': '18.0.1.0',
    'category': 'Payment',
    'depends': ['account', 'base', 'l10n_uy_check'],
    'data': [
        'report/payment_receipt_inherit.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
