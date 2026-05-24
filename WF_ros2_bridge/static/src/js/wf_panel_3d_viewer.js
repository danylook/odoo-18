/** @odoo-module **/
/**
 * WF Panel 3D Viewer — ROS2 Bridge
 * ================================
 * An OWL view_widget that renders a Three.js 3D scene showing all pieces of
 * a panel section at their target positions, coloured by ROS2 placement state.
 *
 * Piece states and colours:
 *   pending   →  #888888  (grey)
 *   moving    →  #ffaa00  (orange)
 *   placed    →  #22bb44  (green)
 *   error     →  #ff3333  (red)
 *
 * Real-time updates via Odoo bus (channel: wf_ros2_section_<sectionId>).
 * Falls back to 5-second HTTP polling if bus is unavailable.
 *
 * Mouse controls:
 *   Left drag   → orbit (azimuth / elevation)
 *   Right drag  → pan
 *   Wheel       → zoom
 *   Hover       → tooltip with piece info
 *
 * Three.js is pre-loaded via the manifest assets bundle (CDN).
 */

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const STATE_COLOR = {
    pending: 0x888888,
    moving:  0xffaa00,
    placed:  0x22bb44,
    error:   0xff3333,
};

// ── Component ─────────────────────────────────────────────────────────────────

class WFPanel3DViewer extends Component {
    static template = "WF_ros2_bridge.Panel3DViewer";
    static props = {
        record: { type: Object, optional: true },
        node:   { type: Object, optional: true },
    };

    setup() {
        this.canvasRef    = useRef("canvas");
        this.containerRef = useRef("container");
        this.tooltipRef   = useRef("tooltip");

        this.state = useState({
            loading: true,
            error: null,
            pieceCount: 0,
            counts: { pending: 0, moving: 0, placed: 0, error: 0 },
        });

        // Three.js internals
        this._renderer  = null;
        this._scene     = null;
        this._camera    = null;
        this._animFrame = null;
        this._meshes    = {};   // component_id → Mesh
        this._raycaster = null;
        this._mouse     = null;

        // Orbit state
        this._orbit = { theta: Math.PI / 6, phi: Math.PI / 3.5, radius: 300, tx: 0, ty: 0, tz: 0 };

        this._pollTimer = null;
        this._busActive = false;

        try {
            this._busService = useService("bus_service");
        } catch (_) {
            this._busService = null;
        }

        onMounted(() => this._init());
        onWillUnmount(() => this._cleanup());
    }

    // ── Section / production IDs from the form record ─────────────────────────

    get _sectionId() {
        const rec = this.props.record;
        if (!rec) return null;
        // Many2one field returns [id, name] or false
        const f = rec.data?.panel_section_id;
        return f ? f[0] : null;
    }

    get _productionId() {
        const rec = this.props.record;
        if (!rec) return null;
        return rec.data?.id || null;
    }

    // ── Init / cleanup ────────────────────────────────────────────────────────

    async _init() {
        const sectionId = this._sectionId;
        if (!sectionId) {
            this.state.loading = false;
            this.state.error = "Sin sección de panel vinculada.";
            return;
        }
        try {
            const data = await this._fetchStatus(sectionId);
            this._buildScene(data);
            this._subscribeTobus(sectionId);
            this._startPolling(sectionId);
            this.state.loading = false;
        } catch (e) {
            this.state.loading = false;
            this.state.error = `Error: ${e.message || e}`;
        }
    }

    _cleanup() {
        if (this._animFrame)  cancelAnimationFrame(this._animFrame);
        if (this._pollTimer)  clearInterval(this._pollTimer);
        if (this._renderer)   { this._renderer.dispose(); this._renderer = null; }
        if (this._busActive && this._busService && this._sectionId) {
            try { this._busService.removeChannel?.(`wf_ros2_section_${this._sectionId}`); } catch (_) {}
        }
    }

    // ── Data fetching ─────────────────────────────────────────────────────────

    async _fetchStatus(sectionId) {
        const url = `/api/wf/ros2/section/${sectionId}/status`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }

    // ── Bus subscription ──────────────────────────────────────────────────────

    _subscribeTobus(sectionId) {
        if (!this._busService) return;
        try {
            const channel = `wf_ros2_section_${sectionId}`;
            this._busService.addChannel(channel);
            this._busService.subscribe("wf_ros2_piece_status", (payload) => {
                if (payload?.section_id === sectionId) {
                    this._applyUpdates(payload.updates || []);
                }
            });
            this._busActive = true;
        } catch (_) {
            // Bus not available — polling will cover it
        }
    }

    // ── Polling fallback ──────────────────────────────────────────────────────

    _startPolling(sectionId) {
        this._pollTimer = setInterval(async () => {
            try {
                const data = await this._fetchStatus(sectionId);
                this._applyFullUpdate(data);
            } catch (_) {}
        }, 5000);
    }

    // ── Three.js scene ────────────────────────────────────────────────────────

    _buildScene(data) {
        const THREE = window.THREE;
        const container = this.containerRef.el;
        const canvas    = this.canvasRef.el;
        const W = container.clientWidth  || 800;
        const H = container.clientHeight || 520;

        // Renderer
        const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
        renderer.setSize(W, H, false);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setClearColor(0x0d0d1a, 1);
        this._renderer = renderer;

        // Scene
        const scene = new THREE.Scene();
        this._scene = scene;

        // Lighting
        scene.add(new THREE.AmbientLight(0xffffff, 0.55));
        const sun = new THREE.DirectionalLight(0xffffff, 0.85);
        sun.position.set(200, 400, 200);
        scene.add(sun);
        const fill = new THREE.DirectionalLight(0x88aaff, 0.25);
        fill.position.set(-200, 100, -200);
        scene.add(fill);

        // Camera
        const camera = new THREE.PerspectiveCamera(45, W / H, 0.5, 20000);
        this._camera = camera;

        // Raycaster for hover tooltip
        this._raycaster = new THREE.Raycaster();
        this._mouse = new THREE.Vector2(-9999, -9999);

        // Build pieces
        this._populatePieces(scene, data);

        // Controls
        this._setupMouseControls(canvas);

        // Handle resize
        this._resizeObserver = new ResizeObserver(() => {
            const cW = container.clientWidth;
            const cH = container.clientHeight;
            renderer.setSize(cW, cH, false);
            camera.aspect = cW / cH;
            camera.updateProjectionMatrix();
        });
        this._resizeObserver.observe(container);

        // Render loop
        const animate = () => {
            this._animFrame = requestAnimationFrame(animate);
            this._updateCameraFromOrbit();
            this._raycaster.setFromCamera(this._mouse, camera);
            const hits = this._raycaster.intersectObjects(Object.values(this._meshes));
            this._showTooltip(hits[0]?.object || null, hits[0]);
            renderer.render(scene, camera);
        };
        animate();
    }

    _populatePieces(scene, data) {
        const THREE = window.THREE;
        const pieces = data.pieces || [];

        // Remove old
        Object.values(this._meshes).forEach(m => scene.remove(m));
        this._meshes = {};

        if (!pieces.length) return;

        // Compute bounds for base panel + initial camera
        let maxX = 0, maxZ = 0;
        pieces.forEach(p => {
            maxX = Math.max(maxX, p.x + p.length);
            maxZ = Math.max(maxZ, p.y + p.width);
        });

        // Green base panel
        const baseGeo = new THREE.BoxGeometry(maxX, 1, maxZ);
        const baseMat = new THREE.MeshLambertMaterial({ color: 0x1a4a1a, opacity: 0.6, transparent: true });
        const base = new THREE.Mesh(baseGeo, baseMat);
        base.position.set(maxX / 2, -0.5, maxZ / 2);
        scene.add(base);

        // Grid helper
        const gridSize = Math.ceil(Math.max(maxX, maxZ) / 10) * 10;
        const grid = new THREE.GridHelper(gridSize * 1.2, Math.floor(gridSize / 10), 0x334433, 0x223322);
        grid.position.set(maxX / 2, 0, maxZ / 2);
        scene.add(grid);

        // Set orbit target to panel center
        this._orbit.tx = maxX / 2;
        this._orbit.ty = 0;
        this._orbit.tz = maxZ / 2;
        this._orbit.radius = Math.max(maxX, maxZ) * 1.8;

        // Pieces
        const counts = { pending: 0, moving: 0, placed: 0, error: 0 };

        pieces.forEach(p => {
            const ros2 = p.ros2 || {};
            const state = ros2.state || "pending";
            const color = STATE_COLOR[state] ?? STATE_COLOR.pending;
            counts[state] = (counts[state] || 0) + 1;

            const w = Math.max(p.length, 0.5);   // X
            const h = Math.max(p.depth,  1.0);   // Y (height)
            const d = Math.max(p.width,  0.5);   // Z

            const geo = new THREE.BoxGeometry(w, h, d);
            const mat = new THREE.MeshLambertMaterial({ color });
            const mesh = new THREE.Mesh(geo, mat);

            mesh.position.set(
                p.x + w / 2,
                h / 2,
                p.y + d / 2,
            );
            mesh.userData = {
                pieceId:  p.id,
                dataId:   p.data_id,
                state,
                ros2,
                length: p.length, width: p.width, depth: p.depth,
                x: p.x, y: p.y,
            };
            scene.add(mesh);
            this._meshes[p.id] = mesh;
        });

        this.state.pieceCount = pieces.length;
        this.state.counts = counts;
    }

    // ── Update helpers ────────────────────────────────────────────────────────

    _applyUpdates(updates) {
        /** Apply partial state updates (from bus). */
        const counts = { ...this.state.counts };
        for (const upd of updates) {
            const mesh = this._meshes[upd.component_id];
            if (!mesh) continue;
            const old = mesh.userData.state;
            const st  = upd.state || "pending";
            if (old !== st) {
                mesh.material.color.setHex(STATE_COLOR[st] ?? STATE_COLOR.pending);
                mesh.userData.state = st;
                mesh.userData.ros2  = { ...mesh.userData.ros2, ...upd };
                counts[old]  = Math.max(0, (counts[old] || 0) - 1);
                counts[st]   = (counts[st] || 0) + 1;
            }
        }
        this.state.counts = counts;
    }

    _applyFullUpdate(data) {
        /** Rebuild colours from a full /status response (polling fallback). */
        const counts = { pending: 0, moving: 0, placed: 0, error: 0 };
        for (const p of (data.pieces || [])) {
            const state = p.ros2?.state || "pending";
            const mesh  = this._meshes[p.id];
            if (mesh) {
                mesh.material.color.setHex(STATE_COLOR[state] ?? STATE_COLOR.pending);
                mesh.userData.state = state;
                mesh.userData.ros2  = p.ros2;
            }
            counts[state] = (counts[state] || 0) + 1;
        }
        this.state.counts = counts;
    }

    // ── Orbit camera ──────────────────────────────────────────────────────────

    _updateCameraFromOrbit() {
        const { theta, phi, radius, tx, ty, tz } = this._orbit;
        const sinPhi = Math.sin(phi);
        this._camera.position.set(
            tx + radius * sinPhi * Math.sin(theta),
            ty + radius * Math.cos(phi),
            tz + radius * sinPhi * Math.cos(theta),
        );
        this._camera.lookAt(tx, ty, tz);
    }

    _setupMouseControls(canvas) {
        let drag = false;
        let panDrag = false;
        let lx = 0, ly = 0;
        const orbit = this._orbit;

        canvas.addEventListener("contextmenu", e => e.preventDefault());

        canvas.addEventListener("mousedown", e => {
            if (e.button === 0) { drag = true; lx = e.clientX; ly = e.clientY; }
            if (e.button === 2) { panDrag = true; lx = e.clientX; ly = e.clientY; }
        });
        canvas.addEventListener("mouseup",    () => { drag = false; panDrag = false; });
        canvas.addEventListener("mouseleave", () => { drag = false; panDrag = false; this._mouse.set(-9999, -9999); });

        canvas.addEventListener("mousemove", e => {
            // Update normalised mouse for raycaster
            const rect = canvas.getBoundingClientRect();
            this._mouse.set(
                ((e.clientX - rect.left) / rect.width)  * 2 - 1,
                -((e.clientY - rect.top)  / rect.height) * 2 + 1,
            );

            if (drag) {
                orbit.theta -= (e.clientX - lx) * 0.005;
                orbit.phi    = Math.max(0.05, Math.min(Math.PI / 2 - 0.02, orbit.phi + (e.clientY - ly) * 0.005));
                lx = e.clientX; ly = e.clientY;
            }
            if (panDrag) {
                const speed = orbit.radius * 0.001;
                const dx = (e.clientX - lx) * speed;
                const dy = (e.clientY - ly) * speed;
                orbit.tx -= Math.cos(orbit.theta) * dx;
                orbit.tz += Math.sin(orbit.theta) * dx;
                orbit.ty += dy;
                lx = e.clientX; ly = e.clientY;
            }
        });

        canvas.addEventListener("wheel", e => {
            e.preventDefault();
            orbit.radius = Math.max(20, orbit.radius + e.deltaY * 0.4);
        }, { passive: false });
    }

    // ── Tooltip ───────────────────────────────────────────────────────────────

    _showTooltip(mesh, hit) {
        const el = this.tooltipRef.el;
        if (!el) return;
        if (!mesh || !hit) {
            el.style.display = "none";
            return;
        }
        const ud = mesh.userData;
        const state_label = { pending: "Pendiente", moving: "En movimiento", placed: "Colocada", error: "Error" };
        el.innerHTML = `
            <b>${ud.dataId}</b><br/>
            Estado: ${state_label[ud.state] || ud.state}<br/>
            Pos: X=${ud.x.toFixed(2)}, Y=${ud.y.toFixed(2)}<br/>
            L=${ud.length.toFixed(1)}" W=${ud.width.toFixed(1)}" D=${ud.depth.toFixed(1)}"
            ${ud.ros2?.robot_id ? "<br/>Robot: " + ud.ros2.robot_id : ""}
        `;
        // Position tooltip near cursor
        if (hit.event) {
            const rect = this.canvasRef.el.getBoundingClientRect();
            el.style.left = `${hit.event.clientX - rect.left + 12}px`;
            el.style.top  = `${hit.event.clientY - rect.top  - 10}px`;
        }
        el.style.display = "block";
    }
}

// ── Registration ──────────────────────────────────────────────────────────────

registry.category("view_widgets").add("wf_panel_3d_viewer", {
    component: WFPanel3DViewer,
    extractProps: ({ record, node }) => ({ record, node }),
});
