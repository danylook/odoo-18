from odoo import http

class PingTest(http.Controller):
    @http.route("/api/ping", type="http", auth="none", csrf=False)
    def ping(self):
        return http.request.make_response("{\"status\": \"ok\"}", headers={"Content-Type": "application/json"})

