# WF Panel Importer

**Versión:** 18.0.2.5.0  
**Repositorio:** [github.com/danylook/WF_panel_importer](https://github.com/danylook/WF_panel_importer)

Importa especificaciones de paneles woodframe desde archivos PDF, extrae detalles del proyecto y listas de corte, y crea los registros de panel, BOM y órdenes de fabricación en Odoo 18.

---

## 📁 Estructura del addon

```
WF_panel_importer/
├── __manifest__.py
├── __init__.py
├── data/
├── data_importer/               → Scripts Python del pipeline de procesamiento
│   ├── pdf_parser.py
│   ├── pdf_to_svg_by_page_separado-paso1.py
│   ├── pipeline_svg_colores_inicial.py
│   ├── content_only_colores_elegidos_con_marco_con_oblicuos_directo_paso_2.py
│   ├── convertir_paths_transform_a_absoluto_nuevopaso 3.py
│   ├── paths_a_rects_filtrado_puntos_paso4final.py
│   ├── reescalar_rects_svg_paso5.py
│   ├── piezasrealespaso5.py
│   ├── generoGLPpaso6.py
│   ├── avg_to_glb.py
│   ├── promt.py
│   ├── pruebaocr.py
│   ├── pdftoOCRpasoprevio.py
│   └── pasopostpdf.py
├── models/
│   ├── __init__.py
│   ├── wf_panel.py              → Modelo wf.panel
│   ├── wf_panel_section.py      → Modelo wf.panel.section
│   ├── wf_panel_component.py    → Modelo wf.panel.component
│   ├── wf_panel_line.py         → Modelo wf.panel.line (legacy)
│   ├── res_config_settings.py   → Configuración
│   ├── panelxxx.py              → (vacío, legacy)
│   └── panel_linexxx.py         → (vacío, legacy)
├── security/
├── services/
│   ├── production.py             → Crea orden de fabricación
│   └── wf_ros_bridge.py         → Notifica al bridge ROS2
├── static/
├── views/
└── wizard/
    ├── __init__.py
    ├── wf_panel_import_wizard.py           → Wizard principal de importación
    ├── wf_panel_import_wizard_backup.py    → Backup del wizard
    ├── panel_mrp_dictionary_wizard.py      → Diccionario de piezas
    ├── pdf_to_svg_by_page_separado_paso1_linux.py
    ├── pdf_to_svg_by_page_separado_paso1_linux_full.py
    ├── pipeline_svg_colores_inicial_linux.py
    ├── content_only_colores_elegidos_con_marco_con_oblicuos_directo_paso_2_linux.py
    ├── convertir_paths_transform_a_absoluto_nuevopaso 3.py
    ├── paths_a_rects_filtrado_puntos_paso4final.py
    ├── reescalar_rects_svg_paso5.py
    ├── pdftoOCRpasoprevio.py
    ├── generoGLPpaso6.py
    ├── generate_panel_metadata_svg.py
    └── wf_ros_bridge_wizard.py
```

---

## 🧩 Modelos

### `wf.panel` — `WFPanel`

Panel woodframe (proyecto).

| Campo | Tipo | Descripción |
|---|---|---|
| `name` | Char | Nombre del panel |
| `project` | Char | Proyecto |
| `model` | Char | Modelo |
| `site_address` | Char | Dirección de obra |
| `date` | Date | Fecha |
| `designer` | Char | Diseñador |
| `level` | Char | Nivel |
| `bundle` | Char | Bundle |
| `manufactured_product_id` | Many2one → `product.product` | Producto terminado |
| `bom_id` | Many2one → `mrp.bom` | Lista de materiales |
| `production_id` | Many2one → `mrp.production` | Orden de fabricación |
| `section_ids` | One2many → `wf.panel.section` | Secciones del panel |

**Métodos:**

| Método | Descripción |
|---|---|
| `_ensure_manufactured_product(section)` | Busca o crea un `product.product` para una sección y lo vincula |

### `wf.panel.section` — `WFPanelSection`

Sección de un panel (una "tabla" del PDF).

| Campo | Tipo | Descripción |
|---|---|---|
| `project_id` | Many2one → `wf.panel` | Proyecto al que pertenece |
| `name` | Char | Nombre de la sección |
| `source_file` | Char | Archivo SVG fuente |
| `manufactured_product_id` | Many2one → `product.product` | Producto fabricado |
| `component_ids` | One2many → `wf.panel.component` | Componentes de la sección |
| `component_count` | Integer (compute) | Cantidad de componentes |

**Métodos:**

| Método | Descripción |
|---|---|
| `_compute_component_count()` | Calcula cuántos componentes tiene la sección |
| `action_show_piece_dictionary()` | Abre el wizard "Diccionario de piezas" |

### `wf.panel.component` — `WFPanelComponent`

Pieza individual dentro de una sección del panel.

| Campo | Tipo | Descripción |
|---|---|---|
| `section_id` | Many2one → `wf.panel.section` | Sección (requerido) |
| `project_id` | Related → `section_id.project_id` | Proyecto (store=True) |
| `sequence` | Integer | Orden (default 10) |
| `data_id` | Char | ID de datos (código de pieza) |
| `data_path` | Text | Ruta SVG |
| `x`, `y` | Float | Posición en el panel |
| `data_length` | Float | Largo |
| `data_width` | Float | Ancho |
| `data_depth` | Float | Profundidad |
| `data_orientation` | Selection | `horizontal` / `vertical` |

### `wf.panel.line` — `WFPanelLine` (legacy)

Líneas genéricas del panel (modelo legacy).

| Campo | Descripción |
|---|---|
| `panel_id` | Many2one → `wf.panel` |
| `sequence` | Orden |
| `label`, `member`, `description` | Texto descriptivo |
| `qty` | Cantidad |
| `length`, `width` | Dimensiones |

### `res.config.settings` — Configuración

| Campo | Parámetro sistema | Descripción |
|---|---|---|
| `svg_temp_dir` | `wf_panel_importer.svg_temp_dir` | Directorio temporal para SVGs |

---

## 🧙 Wizard principal: `wf.panel.import.wizard`

**Clase:** `WFPanelImportWizard`  
**Función principal:** `action_import()`

Asistente paso a paso que orquesta todo el pipeline de importación:

1. Carga el PDF
2. Convierte páginas a SVG (Paso 1)
3. Filtra por colores y detecta contornos de piezas (Paso 2)
4. Convierte paths con transformaciones a coordenadas absolutas (Paso 3)
5. Convierte paths a rectángulos y filtra puntos (Paso 4)
6. Reescala coordenadas al tamaño real del panel (Paso 5)
7. Crea `wf.panel`, `wf.panel.section`, `wf.panel.component`
8. Genera archivo GLB (3D) del panel (Paso 6)

### Wizards adicionales

| Wizard | Función | Propósito |
|---|---|---|
| `panel.mrp.dictionary.wizard` | `action_panel_mrp_dictionary_wizard()` | Muestra diccionario de piezas parseadas con productos coincidentes |
| `wf.ros.bridge.wizard` | `action_send_pieces()` | Envía piezas del panel al bridge ROS2 |

---

## 🔧 Pipeline de procesamiento (6 pasos)

| Paso | Archivo | Descripción |
|---|---|---|
| **Paso 1** | `pdf_to_svg_by_page_separado-paso1.py` | Convierte páginas del PDF a SVG individuales |
| **Paso 2** | `pipeline_svg_colores_inicial.py` | Filtra SVG por colores elegidos, procesa paths, detecta contornos |
| **Paso 3** | `convertir_paths_transform_a_absoluto_nuevopaso 3.py` | Convierte paths SVG con transformaciones a coordenadas absolutas |
| **Paso 4** | `paths_a_rects_filtrado_puntos_paso4final.py` | Convierte paths a rectángulos, filtra puntos, obtiene piezas |
| **Paso 5** | `reescalar_rects_svg_paso5.py` | Reescala coordenadas al tamaño real del panel en pulgadas |
| **Paso 6** | `generoGLPpaso6.py` | Genera archivo GLB (3D) del panel |

### Servicios

| Archivo | Función | Propósito |
|---|---|---|
| `services/production.py` | `create_production_order()` | Crea orden de fabricación (MO) desde piezas importadas |
| `services/wf_ros_bridge.py` | `notify_bridge()` | Envía notificación al bridge ROS2 con datos de piezas |

---

## ⚙️ Parámetros del sistema

| Clave | Valor | Descripción |
|---|---|---|
| `wf_panel_importer.svg_temp_dir` | `/opt/odoo18/extra-addons/others-18.0/WF_panel_importer/data_importer/` | Directorio temporal para SVGs |
| `wf_panel_importer.output_dir` | `/tmp/wf_panel_output` | Directorio de salida para archivos generados |
