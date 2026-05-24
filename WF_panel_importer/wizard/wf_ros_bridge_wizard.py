"""
Wizard to launch / stop the WF ROS Bridge subprocess from the Odoo web UI.

The bridge script (services/wf_ros_bridge.py) runs as a detached background
process.  Its PID is persisted in ir.config_parameter so any Odoo user can
inspect or kill it across wizard sessions.
"""
from __future__ import annotations

import os
import signal
import subprocess
import textwrap
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

_PID_KEY    = "wf_ros_bridge.pid"
_STATUS_KEY = "wf_ros_bridge.status"


def _get_param(env, key, default=""):
    return env["ir.config_parameter"].sudo().get_param(key, default)


def _set_param(env, key, value):
    env["ir.config_parameter"].sudo().set_param(key, value)


class WFRosBridgeWizard(models.TransientModel):
    _name = "wf.ros.bridge.wizard"
    _description = "WF ROS Bridge Launcher"

    # ── configuration ─────────────────────────────────────────────────────
    section_name = fields.Char(
        string="Panel Section",
        default="L1_E8",
        required=True,
    )
    ros_setup_path = fields.Char(
        string="ROS setup.bash",
        default="/opt/ros/jazzy/setup.bash",
        help="Full path to the ROS2 setup.bash to source before launching the bridge.",
    )
    db_name = fields.Char(
        string="Database",
        default=lambda self: self.env.cr.dbname,
    )
    db_host = fields.Char(string="DB Host", default="localhost")
    db_port = fields.Integer(string="DB Port", default=5432)
    db_user = fields.Char(string="DB User", default="odoo")
    db_password = fields.Char(string="DB Password", default="odoo")

    # ── runtime state (read-only display) ─────────────────────────────────
    bridge_status = fields.Selection(
        [("stopped", "Stopped"), ("running", "Running")],
        string="Status",
        compute="_compute_bridge_status",
    )
    bridge_pid = fields.Integer(
        string="PID",
        compute="_compute_bridge_status",
    )
    log_tail = fields.Text(
        string="Log",
        compute="_compute_bridge_status",
        help="Last lines written to /tmp/wf_ros_bridge.log",
    )

    # ── computed status ────────────────────────────────────────────────────
    @api.depends()
    def _compute_bridge_status(self):
        for rec in self:
            pid_str = _get_param(self.env, _PID_KEY)
            pid = int(pid_str) if pid_str.isdigit() else 0
            running = False
            if pid:
                try:
                    os.kill(pid, 0)   # 0 = check existence only
                    running = True
                except (ProcessLookupError, PermissionError):
                    pass
            rec.bridge_pid    = pid if running else 0
            rec.bridge_status = "running" if running else "stopped"
            rec.log_tail      = _read_log_tail()

    # ── actions ───────────────────────────────────────────────────────────
    def action_start(self):
        self.ensure_one()
        if self.bridge_status == "running":
            return self._reload()

        bridge_script = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "services", "wf_ros_bridge.py",
        )

        cmd = textwrap.dedent(f"""\
            bash -c '
                if [ -f "{self.ros_setup_path}" ]; then
                    source "{self.ros_setup_path}"
                fi
                python3 {bridge_script} \\
                    --section  "{self.section_name}"  \\
                    --db       "{self.db_name}"        \\
                    --host     "{self.db_host}"        \\
                    --port     {self.db_port}          \\
                    --user     "{self.db_user}"        \\
                    --password "{self.db_password}"    \\
                >> /tmp/wf_ros_bridge.log 2>&1
            '
        """)

        proc = subprocess.Popen(
            cmd,
            shell=True,
            start_new_session=True,   # detach from Odoo's process group
        )
        _set_param(self.env, _PID_KEY, str(proc.pid))
        _set_param(self.env, _STATUS_KEY, "running")
        _logger.info("WF ROS Bridge started (PID %s)", proc.pid)
        return self._reload()

    def action_stop(self):
        self.ensure_one()
        pid_str = _get_param(self.env, _PID_KEY)
        pid = int(pid_str) if pid_str.isdigit() else 0
        if pid:
            try:
                # Kill the whole process group spawned by bash -c
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError) as e:
                _logger.warning("Could not kill PID %s: %s", pid, e)
        _set_param(self.env, _PID_KEY, "")
        _set_param(self.env, _STATUS_KEY, "stopped")
        _logger.info("WF ROS Bridge stopped (was PID %s)", pid)
        return self._reload()

    def action_refresh(self):
        return self._reload()

    # ── helpers ───────────────────────────────────────────────────────────
    def _reload(self):
        """Re-open the same wizard form so computed fields refresh."""
        return {
            "type":      "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "target":    "new",
            "context":   dict(
                self.env.context,
                default_section_name  = self.section_name,
                default_ros_setup_path= self.ros_setup_path,
                default_db_name       = self.db_name,
                default_db_host       = self.db_host,
                default_db_port       = self.db_port,
                default_db_user       = self.db_user,
                default_db_password   = self.db_password,
            ),
        }


def _read_log_tail(path="/tmp/wf_ros_bridge.log", lines=20) -> str:
    try:
        with open(path, "r") as fh:
            all_lines = fh.readlines()
            return "".join(all_lines[-lines:])
    except FileNotFoundError:
        return "(no log yet)"
