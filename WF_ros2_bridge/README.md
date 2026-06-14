# WF ROS2 Bridge

**Puente de integración entre Odoo y sistemas robóticos ROS2** para monitorización en tiempo real del estado de colocación de piezas durante la fabricación de paneles.

---

## 📦 Estructura del addon

```
WF_ros2_bridge/
├── __manifest__.py          → Declaración del módulo
├── controllers/
│   └── ros2_api.py          → API REST (inbound desde ROS2)
├── models/
│   └── wf_ros2_piece_status.py  → Modelo de datos de estado de piezas
├── security/
│   └── ir.model.access.csv  → Permisos (grupos MRP user/manager)
├── static/src/
│   ├── css/wf_panel_3d_viewer.css   → Estilos del visor 3D
│   ├── js/wf_panel_3d_viewer.js     → Visor 3D con Three.js (OWL widget)
│   └── xml/wf_panel_3d_viewer.xml   → Template OWL del visor
└── views/
    ├── wf_ros2_piece_status_views.xml  → Vistas tree/form/action/menú
    └── mrp_production_views.xml        → Inyecta el visor 3D en la MO
```

---

## 🔧 1. Modelo: `wf.ros2.piece.status`

Por cada **pieza de un panel** se crea un registro que guarda:

| Campo | Descripción |
|---|---|
| `component_id` | Relación a la pieza (`wf.panel.component`) |
| `section_id` | Sección del panel (related) |
| `production_id` | Orden de fabricación (MO) |
| `state` | Estado ROS2: `pending` → `moving` → `placed` / `error` |
| `robot_id` | Identificador del robot que la colocó |
| `x_actual`, `y_actual`, `z_actual` | Posición real reportada por ROS2 |
| `x_target`, `y_target` | Posición objetivo (copiada del componente) |
| `note` | Notas del robot |
| `updated_at` | Última actualización |

### Flujo de cambio de estado

Cuando un registro cambia de estado:

1. **Actualiza `updated_at`** automáticamente.
2. **Envía notificación por bus de Odoo** al canal `wf_ros2_section_<section_id>` → todos los clientes web con el visor 3D abierto se actualizan al instante.
3. **Dispara un webhook HTTP** a la URL configurada en `ir.config_parameter` → `wf.ros2.bridge_url` (ej: `http://ros2-bridge:8080/publish`), publicando en el tópico ROS2 `/wf/piece_status`.

### Helper: `_ensure_for_production()`

Crea registros de estado `pending` para todas las piezas de una sección vinculada a una MO. Es **idempotente** (se puede llamar múltiples veces sin duplicar).

---

## 🌐 2. API REST

Todas las rutas viven bajo `/api/wf/ros2/`. Soportan **CORS** (acceso desde cualquier origen) y autenticación vía **Bearer token** (API key de Odoo) o sesión normal.

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| **GET** | `/api/wf/ros2/section/<id>/status` | Lista completa de piezas + estado actual de una sección |
| **GET** | `/api/wf/ros2/production/<id>/status` | Mismo pero filtrado por MO |
| **GET** | `/api/wf/ros2/productions/assembly` | Lista MOs de ensamblaje activas (para que ROS2 descubra trabajos) |
| **POST** | `/api/wf/ros2/piece/update` | **ROS2 envía cambios de estado** de una o varias piezas |
| **POST** | `/api/wf/ros2/workorder/<id>/acknowledge` | Robot confirma que inicia una orden de trabajo |
| **GET** | `/api/wf/ros2/section/<id>/pieces` | Alias legacy de `/status` |

### POST `/api/wf/ros2/piece/update` — Formato del body

```json
{
  "production_id": 19,
  "pieces": [
    {
      "component_id": 5,
      "state": "placed",
      "robot_id": "arm_1",
      "x": 102.75,
      "y": 101.5,
      "z": 0.0,
      "note": "Placed at T+45s"
    }
  ]
}
```

Si el registro de estado no existe, lo **crea automáticamente**.

### POST `/api/wf/ros2/workorder/<id>/acknowledge`

El robot notifica que empieza una orden de trabajo. Solo funciona si la WO está en estado `pending`, `ready` o `waiting`. Además:
- Crea los registros de estado de piezas si no existen
- Llama a `wo.button_start()` para iniciar la WO
- Publica un mensaje en el chatter de la MO

---

## 🎮 3. Visor 3D en Tiempo Real

Es un **widget OWL** registrado como `wf_panel_3d_viewer` que se inyecta como una pestaña **"Vista 3D — ROS2"** en el formulario de la MO (solo visible si la MO tiene `panel_section_id`).

### Características

- **Three.js** cargado desde CDN para renderizado 3D
- Cada pieza se muestra como un **cubo 3D** coloreado según su estado:
  - `pending` → gris `#888888`
  - `moving` → naranja `#ffaa00`
  - `placed` → verde `#22bb44`
  - `error` → rojo `#ff3333`
- **Suelo verde semitransparente** y **grid helper** como referencia
- **Leyenda HUD** en la esquina inferior izquierda con conteos
- **Tooltip** al hacer hover sobre una pieza (muestra ID, estado, posición, dimensiones, robot)

### Controles del mouse

| Acción | Control |
|---|---|
| Rotar órbita | Arrastrar con click izquierdo |
| Pan (desplazar) | Arrastrar con click derecho |
| Zoom | Rueda del mouse |

### Actualización en tiempo real

1. **Odoo Bus** (canal `wf_ros2_section_<id>`) — actualización instantánea cuando cambia un estado
2. **Polling fallback** cada 5 segundos — si el bus no está disponible

---

## 🔄 4. Flujo completo típico

```
ROS2 Robot                          Odoo                          Browser (Usuario)
    │                                 │                                │
    │  POST /workorder/5/acknowledge  │                                │
    │────────────────────────────────▶│  button_start()                │
    │                                 │  Crea status records           │
    │                                 │  Publica en chatter            │
    │                                 │                                │
    │  POST /piece/update             │                                │
    │  (pieza 5 → "moving")           │                                │
    │────────────────────────────────▶│                                │
    │                                 │  write() → bus notification   │
    │                                 │──────────────────────────────▶│ 3D: pieza se
    │                                 │                                │ vuelve naranja
    │  POST /piece/update             │                                │
    │  (pieza 5 → "placed")           │                                │
    │────────────────────────────────▶│                                │
    │                                 │  write() → bus notification   │
    │                                 │  → webhook HTTP a ROS2 bridge │ 3D: pieza se
    │                                 │──────────────────────────────▶│ vuelve verde
```

---

## ⚙️ Configuración necesaria

1. **Dependencias**: `WF_panel_manufacturing` y `model_viewer_widget`
2. **API Keys**: Los robots ROS2 se autentican vía Bearer token (API key de Odoo) o sesión web

### Parámetros del sistema (ir.config_parameter)

Estos valores se configuran en *Ajustes → Parámetros del sistema* de Odoo:

| Clave | Valor | Descripción |
|---|---|---|
| `wf.ros2.bridge_url` | `https://ros2.ecolight.com.uy` | URL del bridge ROS2 (webhook para publicar en tópico ROS2 `/wf/piece_status`) |
| `wf.ros2.odoo_db` | `wally` | Base de datos de Odoo que ROS2 debe usar para autenticarse |
| `wf.ros2.odoo_password` | `admin_ecolight` | Contraseña del usuario de Odoo para autenticación ROS2 |
| `wf.ros2.odoo_url` | `https://wally.ecolight.com.uy` | URL pública de la instancia Odoo |
| `wf.ros2.odoo_user` | `info@ecolight.com.uy` | Email del usuario de Odoo para autenticación ROS2 |
| `wf_panel_importer.output_dir` | `/tmp/wf_panel_output` | Directorio temporal de salida para archivos generados por el importador de paneles |
| `wf_panel_importer.svg_temp_dir` | `/opt/odoo18/extra-addons/others-18.0/WF_panel_importer/data_importer/` | Directorio donde el importador busca/copia archivos SVG de paneles |

---

## 📋 Menús en Odoo

- **Fabricación → ROS2 Bridge → Estado de piezas**: Lista de todos los registros de estado con colores por estado
- **Dentro de una MO**: Pestaña **"Vista 3D — ROS2"** con el visor 3D interactivo
