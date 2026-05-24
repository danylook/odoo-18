# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
	'name': "Product Image On Purchase Order Line",
	'version': "18.0.0.0",
	'category': "Purchase",
    'license':'OPL-1',
	'summary': "Display product image on purchase order line print product image on purchase order report print image on purchase order line product image print product image on purchase line product image in purchase order line",
	'description': """
		
			Display product image on purchase order line. It will also display product image on purchase order report. 
		
			Product Image On Purchase Order Line in odoo,
			Purchase report with product image in odoo,
			product image on purchase order line and purchase report in odoo,
			Identify product via image in odoo,
			Identify priduct via image on purchase report in odoo,

	""",
	'author': "BROWSEINFO",
	"website" : "https://www.browseinfo.com/demo-request?app=purchase_order_line_product_image&version=18&edition=Community",
    'depends': ['base', 'purchase'],
	'data': [
			'report/purchase_order_report.xml',
			'views/view_purchase_order.xml',
			],
	'demo': [],
	'installable': True,
	'auto_install': False,
	'application': False,
	"live_test_url":'https://www.browseinfo.com/demo-request?app=purchase_order_line_product_image&version=18&edition=Community',
	 "images":['static/description/Banner.gif'],
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
