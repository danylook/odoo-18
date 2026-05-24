import json
import logging
from odoo import fields, http
from odoo.http import request
_logger = logging.getLogger(__name__)

HTML_PAGE = '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">\n<title>Driver Tracking</title>\n<style>\n* { box-sizing: border-box; margin: 0; padding: 0; }\nbody { font-family: -apple-system, BlinkMacSystemFont, sans-serif;\n       background: #f0f4f8; min-height: 100vh; display: flex;\n       flex-direction: column; align-items: center; padding: 20px; }\n.card { background: white; border-radius: 16px; padding: 28px 24px;\n        width: 100%; max-width: 420px; box-shadow: 0 4px 24px rgba(0,0,0,.10);\n        margin-top: 20px; }\nh1 { font-size: 22px; font-weight: 700; color: #2c3e50; margin-bottom: 4px; }\n.driver { font-size: 15px; color: #6c757d; margin-bottom: 24px; }\n.status-dot { display: inline-block; width: 12px; height: 12px;\n              border-radius: 50%; margin-right: 8px; vertical-align: middle; }\n.dot-green { background: #28a745; animation: pulse 1.5s infinite; }\n.dot-red   { background: #dc3545; }\n.dot-grey  { background: #adb5bd; }\n@keyframes pulse {\n  0%,100% { box-shadow: 0 0 0 0 rgba(40,167,69,.4); }\n  50%      { box-shadow: 0 0 0 8px rgba(40,167,69,0); }\n}\n.status-line { font-size: 15px; font-weight: 600; color: #2c3e50; margin-bottom: 16px; }\n.info-grid { display: grid; grid-template-columns: auto 1fr; gap: 8px 16px;\n             font-size: 13px; margin-bottom: 20px; }\n.info-label { color: #6c757d; }\n.info-value { color: #212529; font-weight: 500; word-break: break-all; }\n.btn { width: 100%; padding: 14px; border: none; border-radius: 10px;\n       font-size: 15px; font-weight: 600; cursor: pointer; color: white; }\n.btn-stop  { background: #dc3545; }\n.btn-start { background: #28a745; }\n.btn:disabled { opacity: .5; cursor: default; }\n.error-box { background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px;\n             padding: 12px; font-size: 13px; color: #856404;\n             margin-bottom: 16px; display: none; }\n</style>\n</head>\n<body>\n<div class="card">\n  <h1>&#128666; Driver Tracking</h1>\n  <div class="driver" id="driverName">__DRIVER__</div>\n  <div class="error-box" id="errorBox"></div>\n  <div class="status-line">\n    <span class="status-dot dot-grey" id="dot"></span>\n    <span id="statusText">Starting...</span>\n  </div>\n  <div class="info-grid">\n    <span class="info-label">Latitude</span><span class="info-value" id="lat">--</span>\n    <span class="info-label">Longitude</span><span class="info-value" id="lng">--</span>\n    <span class="info-label">Accuracy</span><span class="info-value" id="acc">--</span>\n    <span class="info-label">Last sent</span><span class="info-value" id="lastSent">--</span>\n    <span class="info-label">Updates sent</span><span class="info-value" id="cnt">0</span>\n  </div>\n  <button class="btn btn-start" id="mainBtn" onclick="toggleTracking()">Start Tracking</button>\n</div>\n<script>\nconst TOKEN = "__TOKEN__";\nconst POST_URL = "/tpl/driver/gps";\nconst MIN_MS = 15000;\nlet watchId = null, lastPost = 0, cnt = 0, active = false;\nfunction showErr(m){var b=document.getElementById("errorBox");b.textContent=m;b.style.display=m?"block":"none";}\nfunction setDot(c){document.getElementById("dot").className="status-dot dot-"+c;}\nfunction toggleTracking(){active?stopTracking():startTracking();}\nfunction startTracking(){\n  if(!navigator.geolocation){showErr("Geolocation not supported");return;}\n  showErr(""); active=true;\n  document.getElementById("mainBtn").textContent="Stop Tracking";\n  document.getElementById("mainBtn").className="btn btn-stop";\n  document.getElementById("statusText").textContent="Waiting for GPS...";\n  setDot("grey");\n  watchId=navigator.geolocation.watchPosition(onPos,onErr,{enableHighAccuracy:true,timeout:30000,maximumAge:5000});\n}\nfunction stopTracking(){\n  if(watchId!==null)navigator.geolocation.clearWatch(watchId);\n  watchId=null; active=false;\n  document.getElementById("mainBtn").textContent="Start Tracking";\n  document.getElementById("mainBtn").className="btn btn-start";\n  document.getElementById("statusText").textContent="Stopped"; setDot("grey");\n}\nfunction onPos(pos){\n  var lat=pos.coords.latitude,lng=pos.coords.longitude,acc=Math.round(pos.coords.accuracy);\n  document.getElementById("lat").textContent=lat.toFixed(7);\n  document.getElementById("lng").textContent=lng.toFixed(7);\n  document.getElementById("acc").textContent=acc+"m";\n  document.getElementById("statusText").textContent="GPS locked"; setDot("green");\n  var now=Date.now(); if(now-lastPost<MIN_MS)return; lastPost=now;\n  fetch(POST_URL,{method:"POST",headers:{"Content-Type":"application/json"},\n    body:JSON.stringify({token:TOKEN,lat:lat,lng:lng})})\n  .then(function(r){return r.json();})\n  .then(function(d){\n    if(d.ok){cnt++;document.getElementById("cnt").textContent=cnt;\n      document.getElementById("lastSent").textContent=new Date().toLocaleTimeString();}\n    else showErr("Server: "+(d.error||"unknown"));\n  }).catch(function(e){showErr("Network: "+e.message);});\n}\nfunction onErr(e){\n  var m={1:"Location permission denied.",2:"Position unavailable.",3:"GPS timeout."};\n  showErr(m[e.code]||"GPS error: "+e.message); setDot("red");\n  document.getElementById("statusText").textContent="GPS error";\n}\nstartTracking();\n</script>\n</body></html>\n'

class TruckTrackingController(http.Controller):

    @http.route('/tpl/driver/track/<string:token>', auth='public', type='http', csrf=False)
    def tracking_page(self, token, **kwargs):
        partner = request.env['res.partner'].sudo().search(
            [('tpl_tracking_token', '=', token)], limit=1)
        if not partner:
            return request.not_found()
        html = HTML_PAGE.replace('__TOKEN__', token).replace('__DRIVER__', partner.name or 'Driver')
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route('/tpl/driver/gps', auth='public', type='http', methods=['POST'], csrf=False)
    def update_gps(self, **kwargs):
        _json = lambda d: request.make_response(json.dumps(d), headers=[('Content-Type', 'application/json')])
        try:
            data = json.loads(request.httprequest.data)
            token = data.get('token', '').strip()
            lat = float(data['lat'])
            lng = float(data['lng'])
        except Exception as e:
            return _json({'error': str(e)})
        if not token:
            return _json({'error': 'missing token'})
        partner = request.env['res.partner'].sudo().search(
            [('tpl_tracking_token', '=', token)], limit=1)
        if not partner:
            return _json({'error': 'invalid token'})
        partner.write({'tpl_gps_lat': lat, 'tpl_gps_lng': lng,
                       'tpl_gps_updated': fields.Datetime.now()})
        _logger.debug("GPS update: %s lat=%.6f lng=%.6f", partner.name, lat, lng)
        return _json({'ok': True})
