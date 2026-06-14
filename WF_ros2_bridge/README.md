# WF ROS2 Bridge

**Versión:** 18.0.1.0.3  
**Repositorio:** [github.com/danylook/WF_ros2_bridge](https://github.com/danylook/WF_ros2_bridge)

Puente de integración entre **Odoo 18** y sistemas robóticos **ROS2** para monitorización en tiempo real del estado de colocación de piezas durante la fabricación de paneles woodframe.

---

## 📁 Estructura del addon

```
WF_ros2_bridge/
├── __manifest__.py              → Declaración del módulo
├── __init__.py
├── controllers/
│   ├── __init__.py
│   ├── ros2_api.py              → API REST (inbound desde ROS2)
│   ├── ping_test.py             → Healthcheck simple
│   └── lazy_test.py             → Healthcheck alternativo
├── models/
│   ├── __init__.py
│   ├── wf_ros2_piece_status.py  → Modelo de estado de piezas
│   ├── wf_ros2_bridge_mrp.py    → Botón "Enviar a Robot"
│   ├── wf_ros2_res_config.py    → Configuración del bridge
│   └── wf_ros2_res_config_settings.py → Config extendida
├── security/
│   └── ir.model.access.csv      → Permisos
├── static/
│   ├── description/index.html   → Descripción del módulo
│   └── src/
│       ├── css/wf_panel_3d_viewer.css
│       ├── js/wf_panel_3d_viewer.js
│       └── xml/wf_panel_3d_viewer.xml
└── views/
    ├── mrp_production_views.xml
    ├── wf_ros2_piece_status_views.xml
    └── wf_ros2_bridge_settings.xml
```

---

## 🧩 Modelos

### `wf.ros2.piece.status` — `WFRos2PieceStatus`

Rastrea el estado de colocación de cada pieza del panel.

| Campo | Tipo | Descripción |
|---|---|---|
| `component_id` | Many2one → `wf.panel.component` | Pieza del panel |
| `section_id` | Related → `component_id.section_id` | Sección (store=True) |
| `production_id` | Many2one → `mrp.production` | Orden de fabricación |
| `state` | Selection | `pending` / `moving` / `placed` / `error` |
| `robot_id` | Char | Identificador del robot |
| `x_actual`, `y_actual`, `z_actual` | Float | Posición real reportada por ROS2 |
| `x_target`, `y_target` | Related → `component_id.x/y` | Posición objetivo |
| `updated_at` | Datetime | Última actualización |
| `note` | Text | Nota ROS2 |

**Métodos:**

| Método | Descripción |
|---|---|
| `write(vals)` | Sobrescribe ORM: actualiza `updated_at`, dispara notificación bus + webhook si cambia `state` |
| `_broadcast_state_change()` | Envía actualización por bus de Odoo al canal `wf_ros2_section_<id>` (visor 3D en tiempo real) |
| `_notify_ros2_bridge(section_id, updates)` | POSTea cambios de estado al bridge ROS2 externo (webhook HTTP) |
| `_ensure_for_production(env, production)` | **(classmethod)** Crea registros de estado faltantes para todos los componentes de una MO (idempotente) |

### `mrp.production` — `MrpProductionROS2` (inherit)

| Campo/Método | Descripción |
|---|---|
| `ros2_bridge_url` | Char (compute) — URL del bridge desde parámetros del sistema |
| `_compute_ros2_bridge_url()` | Lee `wf.ros2.bridge_url` de `ir.config_parameter` |
| `action_send_to_robot()` | **Botón "Enviar a Robot"** — envía MO + cutting_list al bridge via `POST /start_job` |

### `res.config.settings` — Configuración

| Campo | Parámetro sistema | Descripción |
|---|---|---|
| `wf_ros2_bridge_url` | `wf.ros2.bridge_url` | URL del bridge ROS2 |
| `wf_ros2_odoo_url` | `wf.ros2.odoo_url` | URL de Odoo para el bridge |
| `wf_ros2_odoo_db` | `wf.ros2.odoo_db` | Base de datos |
| `wf_ros2_odoo_user` | `wf.ros2.odoo_user` | Usuario Odoo para robot |
| `wf_ros2_odoo_password` | `wf.ros2.odoo_password` | Contraseña |
| `wf_ros2_bridge_timeout` | `wf.ros2.bridge_timeout` | Timeout (segundos) |
| `wf_ros2_bridge_port` | `wf.ros2.bridge_port` | Puerto del bridge |
| `wf_ros2_poll_interval` | `wf.ros2.poll_interval` | Intervalo de polling (s) |

---

## 🌐 API REST

Todas las rutas bajo `/api/wf/ros2/`. Autenticación vía **Bearer token** (API key de Odoo) o sesión web.

### Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| **GET** | `/api/wf/ros2/section/<id>/status` | Estado completo de una sección (piezas + estado ROS2) |
| **GET** | `/api/wf/ros2/production/<id>/status` | Estado filtrado por MO |
| **GET** | `/api/wf/ros2/productions/assembly` | Lista MOs de ensamblaje activas (descubrimiento ROS2) |
| **POST** | `/api/wf/ros2/piece/update` | ROS2 envía cambios de estado de una o varias piezas |
| **POST** | `/api/wf/ros2/workorder/<id>/acknowledge` | Robot confirma inicio de WO |
| **GET** | `/api/ping` | Healthcheck simple |
| **GET** | `/api/lazy/ping` | Healthcheck alternativo |

### Helpers internos del controlador

| Helper | Descripción |
|---|---|
| `_get_env()` | Autentica via Bearer token o sesión web |
| `_serialize_piece(comp, status_map)` | Serializa componente con estado ROS2 |
| `_build_status_response(env, section, production)` | Construye JSON completo de estado |
| `_json_resp(data, status)` | Normaliza respuesta JSON |
| `_err(msg, status)` | Normaliza respuesta de error |

---

## 🎮 Visor 3D en Tiempo Real

Widget OWL con **Three.js** que se inyecta como pestaña **"Vista 3D — ROS2"** en el formulario de la MO.

- Cubos 3D coloreados por estado: gris (pendiente), naranja (moviendo), verde (colocada), rojo (error)
- Suelo verde semitransparente + grid helper
- Leyenda HUD con conteos en vivo
- Tooltip al hacer hover
- Controles: arrastrar (rotar), rueda (zoom), click derecho (mover)
- Actualización instantánea vía Odoo Bus + polling fallback cada 5s

---

## 🔄 Flujo de datos

```
ROS2 Robot                     Odoo                          Browser (Usuario)
    │                            │                                │
    │ POST /workorder/5/acknowledge                               │
    │───────────────────────────▶│  button_start()                │
    │                            │  Crea status records           │
    │                            │                                │
    │ POST /piece/update         │                                │
    │ (pieza → "moving")         │                                │
    │───────────────────────────▶│                                │
    │                            │  write() → bus notification   │
    │                            │──────────────────────────────▶│ 3D: naranja
    │                            │  → webhook HTTP a ROS2 bridge │
    │ POST /piece/update         │                                │
    │ (pieza → "placed")         │                                │
    │───────────────────────────▶│                                │
    │                            │  write() → bus notification   │
    │                            │──────────────────────────────▶│ 3D: verde
```

---

## ⚙️ Parámetros del sistema

| Clave | Valor | Descripción |
|---|---|---|
| `wf.ros2.bridge_url` | `https://ros2.ecolight.com.uy` | URL del bridge ROS2 |
| `wf.ros2.odoo_db` | `wally` | Base de datos Odoo |
| `wf.ros2.odoo_password` | `admin_ecolight` | Contraseña del usuario Odoo |
| `wf.ros2.odoo_url` | `https://wally.ecolight.com.uy` | URL pública de Odoo |
| `wf.ros2.odoo_user` | `info@ecolight.com.uy` | Email del usuario Odoo |
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
