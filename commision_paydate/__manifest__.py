{
    'name': "Commissions Payment Date",

    'description': """
        Add filter to calculate commissions by payment date
    """,
    "category": "Sales Management",
    'version': '18.0.0.5.1',
    "license": "AGPL-3",
    "depends": [
        "account",
        "commission_oca",
        "account_commission_oca",
	    "l10n_uy_fe"
    ],

    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'wizards/commission_make_settle_views.xml',
        "reports/commission_settlement_report.xml",
        "reports/report_settlement_templates.xml",
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
