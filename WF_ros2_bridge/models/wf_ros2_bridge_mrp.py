"""
wf_ros2_bridge_mrp.py — Extiende mrp.production con botón "Enviar a Robot".
"""
import json
import logging
import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MrpProductionROS2(models.Model):
    _inherit = "mrp.production"

    ros2_bridge_url = fields.Char(
        string="URL Bridge ROS2",
        compute="_compute_ros2_bridge_url",
    )

    def _compute_ros2_bridge_url(self):
        ICP = self.env["ir.config_parameter"].sudo()
        base = ICP.get_param("wf.ros2.bridge_url", "https://ros2.ecolight.com.uy")
        for rec in self:
            rec.ros2_bridge_url = base

    def action_send_to_robot(self):
        """Envía esta MO al robot vía HTTPS POST."""
        self.ensure_one()
        if self.state not in ("confirmed", "progress"):
            raise UserError(_(
                "Solo se pueden enviar órdenes en estado "
                "Confirmada o En Progreso."
            ))

        url = self.ros2_bridge_url.rstrip("/") + "/start_job"

        # Construir cutting_list desde las piezas del panel
        cutting_list = []
        if self.panel_section_id:
            for comp in self.panel_section_id.component_ids:
                cutting_list.append({
                    "id": comp.id,
                    "data_id": comp.data_id or "",
                    "sequence": comp.sequence,
                    "x": comp.x,
                    "y": comp.y,
                    "length": comp.data_length,
                    "width": comp.data_width,
                    "depth": comp.data_depth,
                })

        payload = {
            "production_id": self.id,
            "product_name": self.product_id.display_name,
            "product_qty": self.product_qty,
            "cutting_list": cutting_list,
        }

        # Log detallado de las piezas enviadas
        _logger.info(
            "Enviando MO %s (%s) a ROS2 — %d piezas:\n%s",
            self.name, self.product_id.display_name,
            len(cutting_list),
            json.dumps(cutting_list, indent=2, ensure_ascii=False),
        )

        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            result = resp.json()
        except requests.ConnectionError as e:
            raise UserError(_(
                f"No se pudo conectar con el robot ({url}): {e}"
            )) from e
        except requests.Timeout:
            raise UserError(_(
                "Tiempo de espera agotado al contactar al robot."
            ))
        except Exception as e:
            raise UserError(_(
                f"Error al enviar orden al robot: {e}"
            )) from e

        self.message_post(
            body=_("Orden enviada a ROS2 — production_id=%(pid)s, respuesta=%(r)s",
                   pid=self.id, r=result.get("status", "?")),
            subtype_xmlid="mail.mt_note",
        )

        _logger.info(
            "Orden %s enviada a ROS2: %s", self.name, result)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Enviado a Robot"),
                "message": _(
                    "Orden %(name)s enviada correctamente a ROS2",
                    name=self.name,
                ),
                "sticky": False,
                "type": "success",
            },
        }