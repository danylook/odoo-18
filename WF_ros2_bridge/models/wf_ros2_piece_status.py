"""
wf.ros2.piece.status
====================
Tracks the real-time placement state of each panel piece as reported by ROS2.

States
------
pending   → piece not yet touched
moving    → robot is carrying the piece to its target position
placed    → piece confirmed placed at target coordinates
error     → robot reported an error for this piece

When a state changes, the record notifies:
  1. The Odoo bus channel ``wf_ros2_section_<section_id>`` so all browser
     clients update the 3D viewer in real time.
  2. An outbound webhook to the configured ROS2 HTTP bridge URL
     (ir.config_parameter key: ``wf.ros2.bridge_url``), publishing to the
     ROS2 topic ``/wf/piece_status``.
"""

import logging
import urllib.request
import json as _json

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class WFRos2PieceStatus(models.Model):
    _name = "wf.ros2.piece.status"
    _description = "ROS2 — Estado de colocación de piezas"
    _rec_name = "component_id"
    _order = "section_id, sequence"

    # ── Identidad ────────────────────────────────────────────────────
    component_id = fields.Many2one(
        "wf.panel.component",
        string="Pieza",
        required=True,
        ondelete="cascade",
        index=True,
    )
    section_id = fields.Many2one(
        related="component_id.section_id",
        string="Sección",
        store=True,
        index=True,
    )
    sequence = fields.Integer(
        related="component_id.sequence",
        string="Secuencia",
        store=True,
    )
    data_id = fields.Char(
        related="component_id.data_id",
        string="ID Pieza",
        store=True,
    )
    production_id = fields.Many2one(
        "mrp.production",
        string="Orden de fabricación",
        ondelete="set null",
        index=True,
    )

    # ── Estado ROS2 ───────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("moving", "En movimiento"),
            ("placed", "Colocada"),
            ("error", "Error"),
        ],
        string="Estado",
        default="pending",
        required=True,
        index=True,
    )
    robot_id = fields.Char(string="Robot ID")
    note = fields.Text(string="Nota ROS2")
    updated_at = fields.Datetime(
        string="Última actualización",
        default=fields.Datetime.now,
    )

    # ── Posición real reportada por el robot ──────────────────────────
    x_actual = fields.Float(string="X real", digits=(16, 4))
    y_actual = fields.Float(string="Y real", digits=(16, 4))
    z_actual = fields.Float(string="Z real", digits=(16, 4))

    # ── Posición objetivo (copiada del componente) ────────────────────
    x_target = fields.Float(
        related="component_id.x",
        string="X objetivo",
        store=True,
    )
    y_target = fields.Float(
        related="component_id.y",
        string="Y objetivo",
        store=True,
    )

    # ─────────────────────────────────────────────────────────────────
    # ORM overrides
    # ─────────────────────────────────────────────────────────────────

    def write(self, vals):
        if "state" not in vals:
            vals.setdefault("updated_at", fields.Datetime.now())
        else:
            vals["updated_at"] = fields.Datetime.now()
        result = super().write(vals)
        if "state" in vals:
            self._broadcast_state_change()
        return result

    # ─────────────────────────────────────────────────────────────────
    # Bus notification
    # ─────────────────────────────────────────────────────────────────

    def _broadcast_state_change(self):
        """Push an Odoo bus message for each changed record so the 3D viewer
        updates in real time without polling."""
        by_section = {}
        for rec in self:
            by_section.setdefault(rec.section_id.id, []).append({
                "component_id": rec.component_id.id,
                "data_id": rec.data_id or "",
                "state": rec.state,
                "x_actual": rec.x_actual,
                "y_actual": rec.y_actual,
                "z_actual": rec.z_actual,
                "robot_id": rec.robot_id or "",
            })
        for section_id, updates in by_section.items():
            channel = f"wf_ros2_section_{section_id}"
            self.env["bus.bus"]._sendone(
                channel,
                "wf_ros2_piece_status",
                {"updates": updates, "section_id": section_id},
            )
            self._notify_ros2_bridge(section_id, updates)

    # ─────────────────────────────────────────────────────────────────
    # Outbound ROS2 webhook
    # ─────────────────────────────────────────────────────────────────

    def _notify_ros2_bridge(self, section_id, updates):
        """POST state changes to the configured ROS2 HTTP bridge so it can
        publish on the /wf/piece_status topic.

        Set ir.config_parameter ``wf.ros2.bridge_url`` to e.g.
        ``http://ros2-bridge:8080`` (rosbridge_server or ros2-web-bridge).
        """
        bridge_url = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("wf.ros2.bridge_url", "")
        )
        if not bridge_url:
            return
        payload = _json.dumps({
            "topic": "/wf/piece_status",
            "msg": {
                "section_id": section_id,
                "updates": updates,
            },
        }).encode()
        url = bridge_url.rstrip("/") + "/publish"
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2)
        except Exception as exc:
            _logger.warning("WF ROS2 bridge call failed (%s): %s", url, exc)

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    @classmethod
    def _ensure_for_production(cls, env, production):
        """Create missing status records for all components in the section
        linked to *production*. Safe to call multiple times (idempotent)."""
        section = production.panel_section_id
        if not section:
            return env["wf.ros2.piece.status"].browse()
        existing = env["wf.ros2.piece.status"].search([
            ("section_id", "=", section.id),
            ("production_id", "=", production.id),
        ])
        existing_comp_ids = existing.mapped("component_id").ids
        to_create = [
            {
                "component_id": comp.id,
                "production_id": production.id,
                "state": "pending",
            }
            for comp in section.component_ids
            if comp.id not in existing_comp_ids
        ]
        if to_create:
            env["wf.ros2.piece.status"].create(to_create)
        return env["wf.ros2.piece.status"].search([
            ("section_id", "=", section.id),
            ("production_id", "=", production.id),
        ])
