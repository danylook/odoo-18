# Cross-System Communication Protocol
## 3pl-cliente ↔ 3pl (Warehouse Backend)

**Version:** 1.0  
**Date:** 2026-05-11  
**Systems:**
- **Client system:** `3pl-cliente.ecolight.com.uy` — Odoo 18, db: `3pl-cliente`  
- **Warehouse backend:** `3pl.ecolight.com.uy` — Odoo 18, db: `3pl`, host: `192.168.1.65`

---

## 1. Architecture Overview

```
┌──────────────────────────────────┐       ┌──────────────────────────────────┐
│  CLIENT SYSTEM                   │       │  WAREHOUSE BACKEND               │
│  3pl-cliente.ecolight.com.uy     │       │  3pl.ecolight.com.uy             │
│                                  │       │                                  │
│  Company: ecoprueba sa           │       │  Company: 3PL Services Ltd       │
│  Warehouse: ECO (pick_pack_ship) │       │  Warehouse: WH  (pick_pack_ship) │
│                                  │       │  + tpl_3pl_logistic addon        │
│  ECO/PICK → ECO/PACK → ECO/OUT  │       │  WH/PICK → WH/PACK → WH/OUT     │
└──────────────────────────────────┘       └──────────────────────────────────┘
         │  Current protocol: MANUAL                   │
         └──────────────── JSON-RPC ──────────────────→│
```

**Current state:** Communication is **manual / operator-driven**. There is no automated webhook
or event bus between the two systems. Each step must be triggered manually on the corresponding system.

---

## 2. Full Order Flow with Trigger Points

### Step 0 — Product & Stock Setup (one-time, done manually)
| Action | System | How |
|--------|--------|-----|
| Create product (e.g. ECO-LED-001) | Backend (3pl) | Inventory → Products |
| Set `owner_id = ecoprueba sa` on product | Backend (3pl) | Product form → Owner field |
| Receive stock via WH/IN receipt | Backend (3pl) | Inventory → Receipts |
| Create same product in client system | Client (3pl-cliente) | Must match SKU exactly |

---

### Step 1 — Sale Order Confirmation
| Event | System | Trigger | Result |
|-------|--------|---------|--------|
| Customer creates/confirms sale order | Client | `sale.order.action_confirm()` | `ECO/PICK` created (state: `confirmed`) |
| Operator creates outbound order | Backend | Manual or portal `/my/3pl/order/new?type=out` | `WH/OUT` created (state: `confirmed`) |

**Current gap:** S00007 in 3pl-cliente and WH/OUT/00024 in 3pl backend are linked by matching
the `origin` field (`S00007`), not by automated API call. The WH/OUT must be created manually
in the backend referencing the same sale order number.

**Recommended automation:**
```python
# On 3pl-cliente: after sale.order.action_confirm(), call backend via XML-RPC:
backend_m.execute_kw(backend_db, backend_uid, backend_pwd,
    'stock.picking', 'create', [{
        'picking_type_id': 2,       # WH: Delivery Orders
        'location_id': 11,          # WH/Output
        'location_dest_id': 5,      # Partners/Customers
        'partner_id': 16,           # ecoprueba sa in backend db
        'origin': sale_order.name,
        'move_ids': [(0,0,{
            'product_id': <product id in backend>,
            'product_uom_qty': line.product_uom_qty,
        }) for line in sale_order.order_line]
    }])
```

---

### Step 2 — PICK (Stock → Packing Zone)
| Event | System | Trigger | Notes |
|-------|--------|---------|-------|
| `ECO/PICK` validated | Client | Operator clicks Validate | Moves goods ECO/3PL Warehouse → ECO/Packing Zone |
| `WH/PICK` created + validated | Backend | **Manual** | Must match same products/quantities |

**Recommended automation (backend PICK creation triggered by client PICK validation):**
```python
pick_id = backend_m.execute_kw(backend_db, backend_uid, backend_pwd,
    'stock.picking', 'create', [{
        'picking_type_id': 3,       # WH: Pick
        'location_id': 8,           # WH/Stock
        'location_dest_id': 12,     # WH/Packing Zone
        'partner_id': 16,           # ecoprueba sa
        'origin': eco_pick.name,
        'move_ids': [(0,0, {
            'product_id': ...,
            'product_uom_qty': ...,
            'restrict_partner_id': 16,  # ecoprueba sa (owner filter)
        }) for line in eco_pick.move_lines]
    }])
backend_m.execute_kw(..., 'stock.picking', 'action_confirm', [[pick_id]])
backend_m.execute_kw(..., 'stock.picking', 'action_assign',  [[pick_id]])
```

---

### Step 3 — PACK (Packing Zone → Output)
| Event | System | Trigger | Notes |
|-------|--------|---------|-------|
| `ECO/PACK` validated | Client | Operator (or auto via Next Transfer) | Moves goods ECO/Packing Zone → ECO/Output |
| `WH/PACK` created | Backend | **Automatic** — push rule id=10 fires when WH/PICK is validated | WH/PACK auto-created in `assigned` state |
| `WH/PACK` validated | Backend | Operator clicks Validate | Moves goods WH/Packing Zone → WH/Output |

**Push rule involved (backend):**
- Rule 10: `WH/Packing Zone → WH/Output`, action=`push`, procure=`make_to_order`
- Created automatically when WH/PICK is validated — no manual trigger needed

---

### Step 4 — OUT / Ship (Output → Customers)
| Event | System | Trigger | Notes |
|-------|--------|---------|-------|
| `ECO/OUT` validated | Client | Operator validates, confirms SMS dialog | Sale order becomes invoiceable |
| `WH/OUT` validated | Backend | Operator validates (stock must be at WH/Output) | Triggers tpl.stock.history cron; enables storage invoice |

**Important:** WH/OUT `origin` must contain the sale order name (e.g. `S00007`) so the
`tpl_3pl_logistic` module can correlate storage and handling records.

---

## 3. Stock Ownership Convention

All products stored in the 3PL warehouse must have `owner_id` set at the product level
(`product.template.owner_id`). This is enforced by the addon:

- `models/product_template.py` — forces `type=product` + `tracking=lot` when owner is set
- `models/stock_move_line.py` — auto-sets `owner_id` from `product.owner_id` on move line create

The `owner_id` on stock quants (`stock.quant.owner_id`) must match the client company's
partner in the backend system:
- Client company: ecoprueba sa → Backend partner id: **16**

---

## 4. XML-RPC Connection Parameters

### Client system calling Backend
```python
import xmlrpc.client

BACKEND_URL  = "http://192.168.1.65:8069"   # internal, or https://3pl.ecolight.com.uy
BACKEND_DB   = "3pl"
BACKEND_USER = "admin"
BACKEND_PWD  = "Admin@1234"

common = xmlrpc.client.ServerProxy(BACKEND_URL + "/xmlrpc/2/common")
uid    = common.authenticate(BACKEND_DB, BACKEND_USER, BACKEND_PWD, {})
m      = xmlrpc.client.ServerProxy(BACKEND_URL + "/xmlrpc/2/object")
```

### Backend calling Client system
```python
CLIENT_URL  = "https://3pl-cliente.ecolight.com.uy"
CLIENT_DB   = "3pl-cliente"
CLIENT_USER = "admin"
CLIENT_PWD  = "Admin@1234"
```

---

## 5. Key ID Mappings

| Concept | Client (3pl-cliente) | Backend (3pl) |
|---------|---------------------|---------------|
| Warehouse | ECO (id=1) | WH (id=1) |
| Stock location | ECO/3PL Warehouse (id=25) | WH/Stock (id=8) |
| Input | ECO/Input (id=9) | WH/Input (id=9) |
| Packing Zone | ECO/Packing Zone (id=12) | WH/Packing Zone (id=12) |
| Output | ECO/Output (id=11) | WH/Output (id=11) |
| Customers | Partners/Customers (id=5) | Partners/Customers (id=5) |
| Picking type: Pick | ECO: Pick | My Company: Pick (id=3) |
| Picking type: Pack | ECO: Pack | My Company: Pack (id=4) |
| Picking type: OUT | ECO: Delivery Orders | My Company: Delivery Orders (id=2) |
| Customer partner | ecoprueba sa (id=1) | ecoprueba sa (id=16) |
| ECO-LED-001 product | id=71 | id=71 |
| ECO-STRIP-001 product | id=72 | id=72 |

---

## 6. Known Issues & Gotchas

### Push rule merges moves into the wrong OUT
When WH/PACK is validated, push rule 11 (Output→Customers) adds new moves into the
**oldest existing assigned OUT for that partner** instead of the intended OUT. Workaround:
```python
# Reassign moves and move lines to the correct OUT picking:
m.execute_kw(db, uid, pwd, 'stock.move', 'write',
    [[<move_ids>], {'picking_id': correct_out_id}])
m.execute_kw(db, uid, pwd, 'stock.move.line', 'write',
    [[<ml_ids>], {'picking_id': correct_out_id}])
```
**Long-term fix:** always create pickings with a `procurement.group` so Odoo matches by group.

### WH/OUT created without procurement group
WH/OUT/00024 was created manually without `group_id`, so Odoo could not auto-chain upstream
PICK/PACK. Always create the OUT with a group:
```python
group_id = m.execute_kw(db, uid, pwd, 'procurement.group', 'create',
    [{'name': sale_order_name}])
# Pass group_id when creating the picking
```

### property_stock_customer must point to an active location
If the partner's `property_stock_customer` points to an archived location, sale order
confirmation fails with UserError. Verify before confirming:
```python
m.execute_kw(db, uid, pwd, 'res.partner', 'read',
    [[partner_id]], {'fields': ['property_stock_customer']})
```

---

## 7. Sequence Diagram (Current Manual Flow)

```
Client Operator        Client Odoo              Backend Odoo        3PL Operator
      │                     │                        │                    │
      │─ Confirm S00007 ───→│                        │                    │
      │                     │─ ECO/PICK created      │                    │
      │                     │                        │←── Create WH/OUT ──│
      │                     │                        │    origin=S00007   │
      │─ Validate PICK ────→│                        │                    │
      │                     │                        │←── Create WH/PICK ─│
      │                     │                        │    (manually)      │
      │─ Validate PACK ────→│                        │                    │
      │                     │                        │←── Validate PICK ──│
      │                     │                        │    WH/PACK created │
      │                     │                        │    (auto, rule 10) │
      │                     │                        │←── Validate PACK ──│
      │                     │                        │    stock→Output    │
      │─ Validate OUT ─────→│                        │←── Validate OUT ───│
      │                     │  Sale invoiceable      │    Delivery done   │
```

---

## 8. Recommended Automation (tpl_3pl_sync addon skeleton)

Implement an addon on the **client system** that overrides `button_validate`:

```python
# addons/tpl_3pl_sync/models/stock_picking.py
import xmlrpc.client
from odoo import models

BACKEND = {
    'url': 'http://192.168.1.65:8069',
    'db': '3pl',
    'user': 'admin',
    'pwd': 'Admin@1234',
}

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        for picking in self.filtered(lambda p: p.state == 'done'):
            if picking.picking_type_code == 'internal' and 'PICK' in picking.name:
                self._backend_create_pick(picking)
            elif picking.picking_type_code == 'outgoing':
                self._backend_notify_out(picking)
        return res

    def _get_backend(self):
        m = xmlrpc.client.ServerProxy(BACKEND['url'] + '/xmlrpc/2/common')
        uid = m.authenticate(BACKEND['db'], BACKEND['user'], BACKEND['pwd'], {})
        return xmlrpc.client.ServerProxy(BACKEND['url'] + '/xmlrpc/2/object'), uid

    def _backend_create_pick(self, picking):
        m, uid = self._get_backend()
        # ... create WH/PICK on backend and action_assign
        pass

    def _backend_notify_out(self, picking):
        m, uid = self._get_backend()
        # ... find corresponding WH/OUT by origin and button_validate it
        pass
```
