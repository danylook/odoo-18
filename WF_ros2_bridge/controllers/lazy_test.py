"""Minimal lazy-import controller for testing."""
from odoo import http
import json

class LazyPingController(http.Controller):

    @http.route("/api/lazy/ping", type="http", auth="none", csrf=False)
    def ping(self):
        return http.request.make_response(
            json.dumps({"status": "lazy_ok"}),
            headers={"Content-Type": "application/json"}
        )
