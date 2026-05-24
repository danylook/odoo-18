# -*- coding: utf-8 -*-
{
    'name': 'Payment Exchange Rate UYU',
    'version': '18.0.2.9',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': ['account'],
    'description': """
        Define la variable moneda en los journal de los bancos para manejar
        tipo de cambio en pagos en moneda extranjera (UYU).
    """,
    'data': ['views/payment_view.xml'],
    'installable': True,
    'application': False,
}
