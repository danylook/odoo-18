"""
WF ROS2 Bridge — REST API Controller
=====================================
All endpoints live under ``/api/wf/ros2/``.

ROS2 → Odoo  (inbound)
-----------------------
  GET  /api/wf/ros2/section/<id>/status
      Full piece list + current placement state for a panel section.

  GET  /api/wf/ros2/production/<id>/status
      Same, scoped to a Manufacturing Order.

  GET  /api/wf/ros2/productions/assembly
      List of active Assembly MOs (for ROS2 job discovery).

  POST /api/wf/ros2/piece/update
      ROS2 pushes one or many piece state changes.
      Body: { "production_id": <int>, "pieces": [
                { "component_id": <int>, "state": "placed"|"moving"|"error",
                  "robot_id": "arm_1", "x": 0.0, "y": 0.0, "z": 0.0,
                  "note": "" }
             ]}

  POST /api/wf/ros2/workorder/<id>/acknowledge
      Robot signals it is starting a work order
      (transitions state: pending/ready → progress).

Authentication
--------------
  Bearer token: ``Authorization: Bearer <odoo-api-key>``
  OR valid Odoo session cookie (web client).
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}

_VALID_STATES = {"pending", "moving", "placed", "error"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _json_resp(data, status=200):
    body = json.dumps(data, ensure_ascii=False)
    return request.make_response(
        body,
        headers={"Content-Type": "application/json; charset=utf-8", **_CORS_HEADERS},
        status=status,
    )


def _err(msg, status=400):
    return _json_resp({"error": msg}, status=status)


def _get_env():
    """Resolve authenticated env from Bearer token or fall back to session."""
    auth = request.httprequest.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            uid = request.env["res.users.apikeys"]._check_credentials(
                scope="rpc", key=auth[7:]
            )
            if uid:
                return request.env(user=uid)
        except Exception:
            pass
    return request.env


def _serialize_piece(comp, status_map):
    """Serialize a wf.panel.component with its current ROS2 status."""
    st = status_map.get(comp.id)
    return {
        "id": comp.id,
        "data_id": comp.data_id or "",
        "sequence": comp.sequence,
        "x": comp.x,
        "y": comp.y,
        "length": comp.data_length,
        "width": comp.data_width,
        "depth": comp.data_depth,
        "orientation": comp.data_orientation or "horizontal",
        "ros2": {
            "state": st.state if st else "pending",
            "robot_id": st.robot_id or "" if st else "",
            "x_actual": st.x_actual if st else 0.0,
            "y_actual": st.y_actual if st else 0.0,
            "z_actual": st.z_actual if st else 0.0,
            "updated_at": st.updated_at.isoformat() if st and st.updated_at else None,
            "note": st.note or "" if st else "",
        },
    }


def _build_status_response(env, section, production=None):
    """Build the full status JSON for a section."""
    from odoo.addons.WF_ros2_bridge.models.wf_ros2_piece_status import WFRos2PieceStatus  # noqa

    # Get or create status records
    domain = [("section_id", "=", section.id)]
    if production:
        domain.append(("production_id", "=", production.id))

    statuses = env["wf.ros2.piece.status"].sudo().search(domain)
    status_map = {s.component_id.id: s for s in statuses}

    pieces = [
        _serialize_piece(comp, status_map)
        for comp in section.component_ids.sorted(lambda c: (c.sequence, c.id))
    ]

    counts = {"pending": 0, "moving": 0, "placed": 0, "error": 0}
    for p in pieces:
        counts[p["ros2"]["state"]] = counts.get(p["ros2"]["state"], 0) + 1

    resp = {
        "section_id": section.id,
        "section_name": section.name,
        "panel": section.project_id.name if section.project_id else "",
        "pieces": pieces,
        "summary": counts,
    }
    if production:
        resp["production_id"] = production.id
        resp["production_name"] = production.name
        resp["is_assembly_mo"] = production.wf_is_assembly_mo
    return resp


# ── Controller ─────────────────────────────────────────────────────────────────

class WFRos2BridgeController(http.Controller):

    # ── GET /api/wf/ros2/section/<id>/status ──────────────────────────────────
    @http.route(
        "/api/wf/ros2/section/<int:section_id>/status",
        type="http", auth="none", methods=["GET", "OPTIONS"], csrf=False,
    )
    def section_status(self, section_id, **_kw):
        if request.httprequest.method == "OPTIONS":
            return _json_resp({})
        env = _get_env()
        section = env["wf.panel.section"].sudo().browse(section_id)
        if not section.exists():
            return _err(f"Section {section_id} not found", 404)
        return _json_resp(_build_status_response(env, section))

    # ── GET /api/wf/ros2/production/<id>/status ───────────────────────────────
    @http.route(
        "/api/wf/ros2/production/<int:production_id>/status",
        type="http", auth="none", methods=["GET", "OPTIONS"], csrf=False,
    )
    def production_status(self, production_id, **_kw):
        if request.httprequest.method == "OPTIONS":
            return _json_resp({})
        env = _get_env()
        prod = env["mrp.production"].sudo().browse(production_id)
        if not prod.exists():
            return _err(f"Production {production_id} not found", 404)
        section = prod.panel_section_id
        if not section:
            return _err(f"Production {production_id} has no panel section", 422)
        return _json_resp(_build_status_response(env, section, prod))

    # ── GET /api/wf/ros2/productions/assembly ─────────────────────────────────
    @http.route(
        "/api/wf/ros2/productions/assembly",
        type="http", auth="none", methods=["GET", "OPTIONS"], csrf=False,
    )
    def list_assembly_productions(self, **_kw):
        """Enumerate active Assembly MOs so ROS2 can discover pending jobs."""
        if request.httprequest.method == "OPTIONS":
            return _json_resp({})
        env = _get_env()
        prods = env["mrp.production"].sudo().search([
            ("wf_is_assembly_mo", "=", True),
            ("state", "not in", ["done", "cancel"]),
        ])
        data = []
        for p in prods:
            section = p.panel_section_id
            data.append({
                "production_id": p.id,
                "production_name": p.name,
                "state": p.state,
                "section_id": section.id if section else None,
                "section_name": section.name if section else "",
                "panel": section.project_id.name if section and section.project_id else "",
                "piece_count": len(section.component_ids) if section else 0,
            })
        return _json_resp({"assembly_productions": data, "count": len(data)})

    # ── POST /api/wf/ros2/piece/update ────────────────────────────────────────
    @http.route(
        "/api/wf/ros2/piece/update",
        type="http", auth="none", methods=["POST", "OPTIONS"], csrf=False,
    )
    def update_piece_status(self, **_kw):
        """
        ROS2 pushes piece state updates.

        Body JSON::

            {
              "production_id": 19,
              "pieces": [
                {
                  "component_id": 5,
                  "state": "placed",
                  "robot_id": "arm_1",
                  "x": 102.75, "y": 101.5, "z": 0.0,
                  "note": "Placed at T+45s"
                }
              ]
            }
        """
        if request.httprequest.method == "OPTIONS":
            return _json_resp({})

        env = _get_env()
        raw = request.httprequest.get_data(as_text=True)
        try:
            body = json.loads(raw)
        except (ValueError, TypeError):
            return _err("Invalid JSON body")

        production_id = body.get("production_id")
        pieces = body.get("pieces", [])
        if not isinstance(pieces, list) or not pieces:
            return _err("'pieces' must be a non-empty list")

        Status = env["wf.ros2.piece.status"].sudo()
        updated = []
        errors = []

        for item in pieces:
            comp_id = item.get("component_id")
            state = item.get("state", "pending")
            if state not in _VALID_STATES:
                errors.append({"component_id": comp_id, "error": f"Invalid state '{state}'"})
                continue

            # Find or create status record
            domain = [("component_id", "=", comp_id)]
            if production_id:
                domain.append(("production_id", "=", production_id))
            rec = Status.search(domain, limit=1)
            vals = {
                "state": state,
                "robot_id": item.get("robot_id", ""),
                "note": item.get("note", ""),
                "x_actual": float(item.get("x", 0.0)),
                "y_actual": float(item.get("y", 0.0)),
                "z_actual": float(item.get("z", 0.0)),
            }
            if rec:
                rec.write(vals)
            else:
                vals["component_id"] = comp_id
                if production_id:
                    vals["production_id"] = production_id
                rec = Status.create(vals)
            updated.append({"component_id": comp_id, "state": state, "status_id": rec.id})

        return _json_resp({
            "updated": updated,
            "errors": errors,
            "count": len(updated),
        })

    # ── POST /api/wf/ros2/workorder/<id>/acknowledge ──────────────────────────
    @http.route(
        "/api/wf/ros2/workorder/<int:workorder_id>/acknowledge",
        type="http", auth="none", methods=["POST", "OPTIONS"], csrf=False,
    )
    def acknowledge_workorder(self, workorder_id, **_kw):
        """
        Robot signals it is starting a work order.
        Transitions state: pending/ready/waiting → progress.

        Body (optional JSON)::

            { "robot_id": "arm_1", "note": "Starting assembly" }
        """
        if request.httprequest.method == "OPTIONS":
            return _json_resp({})

        env = _get_env()
        wo = env["mrp.workorder"].sudo().browse(workorder_id)
        if not wo.exists():
            return _err(f"Workorder {workorder_id} not found", 404)

        body = {}
        raw = request.httprequest.get_data(as_text=True)
        if raw:
            try:
                body = json.loads(raw)
            except (ValueError, TypeError):
                pass

        robot_id = body.get("robot_id", "ROS2")
        note = body.get("note", "")

        if wo.state not in ("pending", "ready", "waiting"):
            return _json_resp({
                "workorder_id": wo.id,
                "state": wo.state,
                "message": "Already in progress or done — no change.",
            })

        # Ensure status records exist
        if wo.production_id and wo.production_id.panel_section_id:
            from odoo.addons.WF_ros2_bridge.models.wf_ros2_piece_status import WFRos2PieceStatus
            WFRos2PieceStatus._ensure_for_production(env, wo.production_id)

        try:
            wo.button_start()
        except Exception as exc:
            _logger.warning("ROS2 acknowledge: button_start failed: %s", exc)

        msg_parts = [f"ROS2 — '{robot_id}' inició: {wo.name}"]
        if note:
            msg_parts.append(note)
        wo.production_id.message_post(
            body=" — ".join(msg_parts),
            subtype_xmlid="mail.mt_note",
        )
        return _json_resp({
            "workorder_id": wo.id,
            "workorder_name": wo.name,
            "state": wo.state,
            "message": "Acknowledged",
        })

    # ── GET /api/wf/ros2/section/<id>/pieces  (legacy, kept for compat) ───────
    @http.route(
        "/api/wf/ros2/section/<int:section_id>/pieces",
        type="http", auth="none", methods=["GET", "OPTIONS"], csrf=False,
    )
    def section_pieces_legacy(self, section_id, **_kw):
        """Backward-compatible alias — use /status instead."""
        return self.section_status(section_id=section_id)
