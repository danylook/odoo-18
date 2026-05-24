/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

class WarehouseMap extends Component {
    static template = "tpl_3pl_logistic.WarehouseMap";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            locations: [],
            quantsByLoc: {},
            maxX: 1,
            maxY: 1,
            selectedCell: null,
            loading: true,
        });
        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        this.state.selectedCell = null;

        const locations = await this.orm.searchRead(
            "stock.location",
            [["tpl_map_active", "=", true]],
            ["id", "name", "complete_name", "tpl_map_x", "tpl_map_y"]
        );

        const locIds = locations.map(l => l.id);
        const quantsByLoc = {};

        if (locIds.length > 0) {
            const quants = await this.orm.searchRead(
                "stock.quant",
                [["location_id", "in", locIds], ["quantity", ">", 0]],
                ["location_id", "product_id", "lot_id", "quantity", "package_id", "owner_id"]
            );
            for (const q of quants) {
                const lid = q.location_id[0];
                if (!quantsByLoc[lid]) quantsByLoc[lid] = [];
                quantsByLoc[lid].push(q);
            }
        }

        this.state.locations = locations;
        this.state.quantsByLoc = quantsByLoc;
        this.state.maxX = locations.length
            ? Math.max(...locations.map(l => l.tpl_map_x || 1))
            : 1;
        this.state.maxY = locations.length
            ? Math.max(...locations.map(l => l.tpl_map_y || 1))
            : 1;
        this.state.loading = false;
    }

    get grid() {
        const rows = [];
        for (let y = 1; y <= this.state.maxY; y++) {
            const cols = [];
            for (let x = 1; x <= this.state.maxX; x++) {
                const loc = this.state.locations.find(
                    l => l.tpl_map_x === x && l.tpl_map_y === y
                ) || null;
                const quants = loc ? (this.state.quantsByLoc[loc.id] || []) : [];
                cols.push({ x, y, loc, quants });
            }
            rows.push({ y, cols });
        }
        return rows;
    }

    get colRange() {
        return Array.from({ length: this.state.maxX }, (_, i) => i + 1);
    }

    selectCell(cell) {
        if (!cell.loc) return;
        const same = this.state.selectedCell && this.state.selectedCell.loc.id === cell.loc.id;
        this.state.selectedCell = same ? null : cell;
    }

    getCellClass(cell) {
        const cls = ["tpl-wh-cell"];
        if (!cell.loc) {
            cls.push("tpl-wh-cell-void");
        } else if (cell.quants.length > 0) {
            cls.push("tpl-wh-cell-occupied");
        } else {
            cls.push("tpl-wh-cell-free");
        }
        if (
            this.state.selectedCell &&
            cell.loc &&
            this.state.selectedCell.loc.id === cell.loc.id
        ) {
            cls.push("tpl-wh-cell-selected");
        }
        return cls.join(" ");
    }

    async refresh() {
        await this.loadData();
    }
}

registry.category("actions").add("tpl_warehouse_map", WarehouseMap);
