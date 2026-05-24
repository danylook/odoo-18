{
    'name': 'TPL AI Inventory Forecast',
    'version': '18.0.1.0.0',
    'category': 'Inventory',
    'summary': 'AI-powered demand forecasting using Ollama LLM',
    'description': '''
AI Inventory Forecast powered by Ollama
========================================
Analyzes historical stock move data to predict future product demand.

Features:
- Statistical demand forecasting with trend analysis
- Dead stock detection
- Fast-moving item identification
- Reorder quantity suggestions (integrates with reordering rules)
- AI qualitative analysis via local Ollama LLM (llama3, qwen2, etc.)
- Per-client breakdown for 3PL operations
- KPI dashboard with graph & pivot views
- Daily cron job for automated forecast generation
    ''',
    'author': 'Custom',
    'depends': ['stock', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/cron.xml',
        'views/tpl_ai_forecast_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
