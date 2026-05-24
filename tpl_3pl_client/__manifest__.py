# -*- coding: utf-8 -*-
{
    'name': '3PL Client Integration',
    'version': '18.0.1.0.0',
    'summary': 'Connect to 3PL logistics server for stock sync and order management',
    'depends': ['base', 'stock', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/res_config_settings_views.xml',
        'views/tpl_3pl_stock_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
