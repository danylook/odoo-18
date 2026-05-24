# -*- coding: utf-8 -*-
{
    'name': 'l10n_uy_fe',
    'version': '18.0.1.13.1',
    'category': 'Accounting',
    "license": "AGPL-3",
    'depends': [
               'om_account_accountant',
               'account',
               'account_debit_note',
               'l10n_latam_base',
               'l10n_latam_invoice_document',
                ],
    'data':[
       'views/dgi_menuitem.xml',
       'views/l10n_latam_identification_type.xml',
       'views/l10n_latam_document_type_view.xml',
       'views/account_move.xml',
       'views/account_journal.xml',
       'views/payment_view.xml',
       'data/l10n_latam.document.type.csv',
       'data/l10n_latam_identification_type_data.xml',
       'data/ir_config_parameter.xml',
       #'security/ir.model.access.csv'
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_uy_fe/static/src/components/account_move.js",
        ],
    },
    'installable' : True,
    'application' : False,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
