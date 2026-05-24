# -*- coding: utf-8 -*-
{
    'name': 'Purchase Order Line Images',
    'summary': 'Order Line Images In Purchase and Report',
    'description': 'Order Line Images In Purchase and Report',
    'version': '18.0.1.0.0',
    'category': 'Purchase/Purchase',
    'author': 'Cybrosys Techno Solutions',
    'license': 'LGPL-3',
    'depends': ['purchase'],
    'data': [
        'views/purchase_order_line_image.xml',
        'views/res_config_settings.xml',
        'report/purchase_order_report.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
