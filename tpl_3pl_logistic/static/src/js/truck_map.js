/** @odoo-module **/
import { Component, useState, onWillStart, onMounted, onPatched, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS  = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";

function loadLeaflet() {
    return new Promise((resolve, reject) => {
        if (window.L) { resolve(); return; }
        // CSS
        if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = LEAFLET_CSS;
            document.head.appendChild(link);
        }
        // JS
        const script = document.createElement("script");
        script.src = LEAFLET_JS;
        script.onload = resolve;
        script.onerror = () => reject(new Error("Failed to load Leaflet.js"));
        document.head.appendChild(script);
    });
}

class TruckMap extends Component {
    static template = "tpl_3pl_logistic.TruckMap";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.mapRef = useRef("mapContainer");
        this._map = null;
        this._markers = [];
        this._refreshTimer = null;

        this.state = useState({
            loading: true,
            trucks: [],
            error: null,
        });

        onWillStart(() => this._initialize());
        onMounted(() => this._tryInitMap());
        onPatched(() => this._tryInitMap());
        onWillUnmount(() => {
            if (this._refreshTimer) clearInterval(this._refreshTimer);
            if (this._map) { this._map.remove(); this._map = null; }
        });
    }

    async _initialize() {
        try {
            await loadLeaflet();
            await this._fetchTrucks();
        } catch (e) {
            this.state.error = String(e.message || e);
        } finally {
            this.state.loading = false;
        }
    }

    async _fetchTrucks() {
        const pickings = await this.orm.searchRead(
            "stock.picking",
            [
                ["picking_type_code", "=", "outgoing"],
                ["state", "in", ["assigned", "done"]],
                ["driver_id", "!=", false],
            ],
            ["name", "driver_id", "partner_id", "state", "scheduled_date"]
        );

        const driverIds = [...new Set(pickings.map(p => p.driver_id[0]))];
        const partners = driverIds.length
            ? await this.orm.searchRead(
                "res.partner",
                [["id", "in", driverIds]],
                ["id", "name", "tpl_gps_lat", "tpl_gps_lng", "tpl_gps_updated"]
            )
            : [];

        const dMap = Object.fromEntries(partners.map(p => [p.id, p]));
        this.state.trucks = pickings
            .map(p => {
                const d = dMap[p.driver_id[0]];
                if (!d || !d.tpl_gps_lat || !d.tpl_gps_lng) return null;
                return {
                    ref: p.name,
                    stateLabel: p.state === "done" ? "Delivered" : "In Transit",
                    stateColor: p.state === "done" ? "#28a745" : "#dc3545",
                    driverName: d.name,
                    lat: d.tpl_gps_lat,
                    lng: d.tpl_gps_lng,
                    gpsUpdated: d.tpl_gps_updated || "—",
                    dest: p.partner_id ? p.partner_id[1] : "—",
                };
            })
            .filter(Boolean);
    }

    _tryInitMap() {
        if (!window.L || this.state.loading) return;
        if (!this._map && this.mapRef.el) {
            this._initMap();
        } else if (this._map) {
            this._updateMarkers();
        }
    }

    _initMap() {
        const el = this.mapRef.el;
        if (!el || !window.L) return;

        const center = this.state.trucks.length
            ? [this.state.trucks[0].lat, this.state.trucks[0].lng]
            : [20, 0];

        this._map = window.L.map(el, { zoomControl: true }).setView(center, this.state.trucks.length ? 11 : 3);

        window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 19,
        }).addTo(this._map);

        this._updateMarkers();
        this._refreshTimer = setInterval(() => this.refresh(), 60000);
    }

    _truckIcon(color) {
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36">
            <circle cx="18" cy="18" r="17" fill="${color}" stroke="white" stroke-width="2"/>
            <rect x="7" y="13" width="13" height="10" rx="1" fill="white"/>
            <polygon points="20,13 29,16 29,23 20,23" fill="white"/>
            <circle cx="10" cy="24" r="2.5" fill="${color}" stroke="white" stroke-width="1.5"/>
            <circle cx="26" cy="24" r="2.5" fill="${color}" stroke="white" stroke-width="1.5"/>
        </svg>`;
        return window.L.divIcon({
            html: svg,
            className: "",
            iconSize: [36, 36],
            iconAnchor: [18, 18],
            popupAnchor: [0, -18],
        });
    }

    _updateMarkers() {
        if (!this._map || !window.L) return;
        for (const m of this._markers) m.remove();
        this._markers = [];

        if (!this.state.trucks.length) return;

        const bounds = [];
        for (const truck of this.state.trucks) {
            const marker = window.L.marker([truck.lat, truck.lng], {
                icon: this._truckIcon(truck.stateColor),
                title: `${truck.driverName} — ${truck.ref}`,
            }).addTo(this._map);

            marker.bindPopup(`
                <div style="min-width:190px;font-family:sans-serif">
                    <div style="font-size:14px;font-weight:700;border-bottom:1px solid #eee;padding-bottom:5px;margin-bottom:6px">
                        🚚 ${truck.driverName}
                    </div>
                    <table style="width:100%;font-size:12px;border-collapse:collapse">
                        <tr><td style="color:#888;padding:2px 8px 2px 0">Delivery</td><td><b>${truck.ref}</b></td></tr>
                        <tr><td style="color:#888;padding:2px 8px 2px 0">Status</td>
                            <td><b style="color:${truck.stateColor}">${truck.stateLabel}</b></td></tr>
                        <tr><td style="color:#888;padding:2px 8px 2px 0">Destination</td><td>${truck.dest}</td></tr>
                        <tr><td style="color:#888;padding:2px 8px 2px 0">GPS Updated</td>
                            <td style="color:#999;font-size:11px">${truck.gpsUpdated}</td></tr>
                    </table>
                </div>`);

            this._markers.push(marker);
            bounds.push([truck.lat, truck.lng]);
        }

        if (bounds.length === 1) {
            this._map.setView(bounds[0], 12);
        } else {
            this._map.fitBounds(bounds, { padding: [40, 40] });
        }
    }

    async refresh() {
        await this._fetchTrucks();
        this._updateMarkers();
    }
}

registry.category("actions").add("tpl_truck_map", TruckMap);
