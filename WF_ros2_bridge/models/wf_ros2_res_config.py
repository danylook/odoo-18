from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    wf_ros2_bridge_url = fields.Char(
        string="URL del Bridge ROS2",
        config_parameter="wf.ros2.bridge_url",
        help="Dirección HTTP del bridge ROS2 (ej: http://192.168.1.134:8090). "
             "Se auto-registra al iniciar el bridge.",
    )
    wf_ros2_odoo_url = fields.Char(
        string="URL de Odoo",
        config_parameter="wf.ros2.odoo_url",
        default="http://192.168.1.70:8069",
        help="URL que el bridge usa para conectarse a Odoo.",
    )
    wf_ros2_bridge_port = fields.Integer(
        string="Puerto del Bridge",
        config_parameter="wf.ros2.bridge_port",
        default=8090,
        help="Puerto HTTP donde escucha el bridge ROS2.",
    )
    wf_ros2_poll_interval = fields.Integer(
        string="Intervalo de polling (s)",
        config_parameter="wf.ros2.poll_interval",
        default=5,
        help="Segundos entre cada consulta de MOs activas.",
    )
