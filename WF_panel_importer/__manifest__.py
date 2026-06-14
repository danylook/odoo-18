{
    "name": "WF Panel Importer",
    "version": "18.0.2.5.0",
    "license": "AGPL-3",
    "summary": "Import woodframe panel data from PDF and generate BOM and MO (WF version)",
    "description": """
Este módulo permite importar especificaciones de paneles tipo woodframe desde un archivo PDF. (Copia WF)
Extrae detalles del proyecto y listas de corte, y crea los registros de panel, BOM y órdenes de fabricación en Odoo.

Incluye utilidades para convertir cada página del PDF en SVG antes de la importación:
- `wizard/pdf_to_svg_by_page_separado-paso1.py` para Windows 11, que usa la instalación local de Inkscape con la sintaxis clásica.
- `wizard/pdf_to_svg_by_page_separado_paso1_linux_full.py` para entornos Ubuntu/Debian. Replica la llamada mínima de Windows (usa `--export-page` y cae a `--pages` si hace falta) para conservar todos los elementos del SVG.
- `wizard/pipeline_svg_colores_inicial_linux.py` orquesta los pasos Linux, llamando a los generadores `_linux` y al script de glTF.

Dependencias clave:
- sudo add-apt-repository ppa:inkscape.dev/stable
-sudo apt update
- sudo apt install inkscape
- Paquetes del sistema: `sudo apt update && sudo apt install -y inkscape python3-scipy`
- Paquetes Python en el entorno de Odoo: `pip install PyPDF2 pdfplumber numpy cryptography pyOpenSSL scipy`

Ejecución rápida en Linux:
`python3 wizard/pipeline_svg_colores_inicial_linux.py <ruta_pdf> <directorio_salida_svg>`
    """,
    "category": "Manufacturing",
    "author": "wally",
    "depends": ["base",
                "mrp",
                "product",
                "model_viewer_widget"],
    "data": [
        "security/ir.model.access.csv",
        "views/wf_panel_import_wizard.xml",
        "views/wf_panel_views.xml",
        "data/ir_config_parameter.xml",
        "views/res_config_settings_view.xml",
        "views/wf_panel_section_views.xml",
        "views/panel_mrp_dictionary_wizard_views.xml",
        "views/wf_ros_bridge_wizard.xml",
    ],
    "installable": True,
    "application": True
    }