# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Payment Provider: Mercado Pago uruguay",
    'version': '18.0.3.0.0',
    'category': 'Accounting/Payment Providers',
    #'sequence': 350,
    'summary': "A payment provider covering Uruguay.",
    'description': " ",  # Non-empty string to avoid loading the README file.
    'depends': ['payment'],
    'data': [
        'views/payment_mercado_pago_uy_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_method_data.xml'
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
}
