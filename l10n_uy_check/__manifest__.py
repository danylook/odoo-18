# -*- coding: utf-8 -*-
{
    'name': 'l10n check UYU',
    'version': '18.0.0.2.9',
    'category': 'Accounting',
    "license": "AGPL-3",
    'depends': [
               'account',
               'account-payment-reconcile',
                'base',
                ],
    'description': """
    modulo de cheques que permite ingresar pagos y luego controlar los depositos en multimoneda,
    se debe definir la variable moneda en los journal de los bancos para que funcione.
    """,
    'data':[
       'security/ir.model.access.csv',
       'views/account_journal.xml',
       'views/account_payment_view.xml',
       'views/res_bank_view.xml',
       'views/report_payment_receipt_template.xml'
    ],
    'installable' : True,
    'application' : False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
