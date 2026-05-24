# -*- coding: utf-8 -*-
{
    'name': 'Exchange Rate UYU',
    'version': '18.0.1.0.1',
    'author': 'Daniel Bazzi',
    
    'category': 'Accounting',
    'depends': [
                ],
    "license": "AGPL-3",
'description': """
    instalar el servicio de actualizacion al BCU

sudo pip3 install py-bcu
    """,
    'data':[
        'currency_view.xml',
        'data/ir_cron.xml',
    ],
    'installable' : True,
    'application' : False,
    'external_dependencies': {"python": ["bs4", "requests", "py-bcu"]},
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
