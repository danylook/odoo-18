"""
wf_ros2_res_config_settings.py — Settings para ROS2 Bridge en Manufacturing.
"""
from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ── ROS2 Bridge URL ──────────────────────────────────────────────
    wf_ros2_bridge_url = fields.Char(
        string="URL del Bridge ROS2",
        default="https://ros2.ecolight.com.uy",
        config_parameter="wf.ros2.bridge_url",
        help="URL base del servidor FastAPI del bridge ROS2 "
             "(ej: https://ros2.ecolight.com.uy)",
    )

    wf_ros2_bridge_timeout = fields.Integer(
        string="Timeout (segundos)",
        default=10,
        config_parameter="wf.ros2.bridge_timeout",
        help="Tiempo máximo de espera para respuesta del bridge ROS2.",
    )

    # ── Odoo → ROS2 (para que el bridge sepa dónde llamar) ──────────
    wf_ros2_odoo_url = fields.Char(
        string="URL de Odoo",
        default="https://wally.ecolight.com.uy",
        config_parameter="wf.ros2.odoo_url",
        help="URL pública de esta instancia Odoo (el bridge la necesita).",
    )

    wf_ros2_odoo_db = fields.Char(
        string="Base de datos Odoo",
        default="wally",
        config_parameter="wf.ros2.odoo_db",
    )

    wf_ros2_odoo_user = fields.Char(
        string="Usuario Odoo para robot",
        default="info@ecolight.com.uy",
        config_parameter="wf.ros2.odoo_user",
        help="Usuario con acceso a mrp.production que usará el bridge.",
    )

    wf_ros2_odoo_password = fields.Char(
        string="Contraseña",
        default="",
        config_parameter="wf.ros2.odoo_password",
        help="Contraseña del usuario Odoo para el bridge ROS2.",
    )