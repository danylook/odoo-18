{
    'name': '3PL Sync — Client ↔ Warehouse',
    'version': '18.0.1.0',
    'category': 'Inventory/Logistics',
    'summary': 'Automatically mirrors every PICK/PACK/OUT step from this client system to the 3PL warehouse backend via XML-RPC.',
    'author': 'Custom',
    'depends': ['stock', 'sale_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/tpl_sync_config_views.xml',
        'data/tpl_sync_config_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
