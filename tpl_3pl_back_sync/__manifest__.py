{
    'name': '3PL Back Sync',
    'version': '18.0.1.0',
    'summary': 'When backend validates WH/PICK→PACK→OUT, notify client ECO pickings',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/tpl_client_config_views.xml',
        'views/stock_picking_views.xml',
        'data/tpl_client_config_data.xml',
    ],
    'installable': True,
    'auto_install': False,
}
