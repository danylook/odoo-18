# pylint: disable=pointless-statement
{
    "name": "WF ROS2 Bridge",
    "version": "18.0.1.0.3",
    "license": "AGPL-3",
    "summary": "Integracion ROS2 - API REST, estado de piezas y visor 3D de avance",
    "category": "Manufacturing",
    "description": """# 🧩 WF ROS2 Bridge
Puente de integración entre **Odoo** y sistemas robóticos **ROS2** para monitorización en tiempo real del estado de colocación de piezas durante la fabricación de paneles.

---

## 🔧 Modelo: `wf.ros2.piece.status`
Por cada pieza de un panel se crea un registro que guarda el estado ROS2:

- **State:** `pending` → `moving` → `placed` / `error`
- **Posición real** (x, y, z) reportada por el robot
- **Posición objetivo** copiada del componente del panel
- **Robot ID** que realizó la colocación

Al cambiar de estado: notifica por bus de Odoo (tiempo real) y dispara un webhook HTTP al bridge ROS2.

---

## 🌐 API REST
Todas las rutas bajo `/api/wf/ros2/` con autenticación vía Bearer token o sesión:

| Método | Ruta | Descripción |
|---|---|---|
| GET | /api/wf/ros2/section/&lt;id&gt;/status | Estado completo de una sección |
| GET | /api/wf/ros2/production/&lt;id&gt;/status | Estado filtrado por MO |
| GET | /api/wf/ros2/productions/assembly | MOs de ensamblaje activas |
| POST | /api/wf/ros2/piece/update | ROS2 envía cambios de estado de piezas |
| POST | /api/wf/ros2/workorder/&lt;id&gt;/acknowledge | Robot inicia orden de trabajo |

---

## 🎮 Visor 3D en Tiempo Real
Widget OWL con **Three.js** que se inyecta como pestaña **"Vista 3D — ROS2"** en las órdenes de fabricación:

- ✅ Cubos 3D coloreados por estado: gris (pendiente), naranja (moviendo), verde (colocada), rojo (error)
- ✅ Suelo verde y grid helper como referencia
- ✅ Leyenda HUD con conteos en vivo
- ✅ Tooltip al hacer hover sobre cada pieza
- ✅ Controles: arrastrar para rotar, rueda para zoom, click derecho para mover
- ✅ Actualización instantánea vía Odoo Bus + polling fallback cada 5s

---

## ⚙️ Configuración

- **Dependencias:** WF_panel_manufacturing, model_viewer_widget
- **Autenticación:** API Keys de Odoo (Bearer token)

### Parámetros del sistema (ir.config_parameter)

| Clave | Valor |
|---|---|
| wf.ros2.bridge_url | https://ros2.ecolight.com.uy |
| wf.ros2.odoo_db | wally |
| wf.ros2.odoo_password | admin_ecolight |
| wf.ros2.odoo_url | https://wally.ecolight.com.uy |
| wf.ros2.odoo_user | info@ecolight.com.uy |
| wf_panel_importer.output_dir | /tmp/wf_panel_output |
| wf_panel_importer.svg_temp_dir | /opt/odoo18/extra-addons/others-18.0/WF_panel_importer/data_importer/ |

---

## 📋 Menús

- **Fabricación → ROS2 Bridge → Estado de piezas**
- **Dentro de una MO:** Pestaña "Vista 3D — ROS2"
""",
    "depends": ["WF_panel_manufacturing", "model_viewer_widget"],
    "data": [
        "security/ir.model.access.csv",
        "views/wf_ros2_piece_status_views.xml",
        "views/mrp_production_views.xml"
    ],
    "assets": {
        "web.assets_backend": [
            "https://unpkg.com/three@0.160.0/build/three.min.js",
            "WF_ros2_bridge/static/src/css/wf_panel_3d_viewer.css",
            "WF_ros2_bridge/static/src/xml/wf_panel_3d_viewer.xml",
            "WF_ros2_bridge/static/src/js/wf_panel_3d_viewer.js"
        ]
    },
    "installable": True,
    "application": False
}
