# PROCEDURE: 3PL Sync System — Client & Server Configuration

| | |
|---|---|
| **Document No.** | PRO-3PL-001 |
| **Revision** | 1.0 |
| **Date** | 2026-05-13 |
| **Author** | IT / Systems Administration |
| **Status** | Approved |

---

## 1. PURPOSE

This procedure defines the steps required to configure, connect, and verify the synchronization
between a **3PL Warehouse Backend** (Odoo server) and one or more **Client Odoo Instances**.
It ensures that stock movements validated on the client are mirrored to the warehouse backend,
and that warehouse validations are reflected back to the client, maintaining data integrity
across both systems.

---

## 2. SCOPE

Applies to:
- Initial setup of new client Odoo instances
- Addition of new client companies to an existing 3PL backend
- Maintenance and verification of existing connections

---

## 3. DEFINITIONS

| Term | Description |
|---|---|
| **Backend** | The 3PL warehouse Odoo instance. Manages physical stock operations (WH/PICK, WH/PACK, WH/OUT, WH/IN). |
| **Client** | The client company's Odoo instance. Manages sales orders and sends ECO/PICK, ECO/PACK, ECO/OUT, ECO/IN operations. |
| **Owner Partner** | A `res.partner` record in the Backend database that uniquely identifies a client company. All stock moves belonging to that client carry this partner as owner. |
| **tpl.client.config** | Backend model. One record per connected client. Stores URL, credentials, and owner partner linkage. |
| **tpl.sync.config** | Client model. One record per backend connection. Stores backend URL, credentials, and owner ID. |
| **default_code** | Internal reference of a product. Must be identical on both Client and Backend for product matching to work. |
| **HTTPS** | Required protocol for all inter-system communication. HTTP (plain text) must not be used in production. |

---

## 4. RESPONSIBILITIES

| Role | Responsibility |
|---|---|
| **3PL System Administrator** | Performs all setup steps on the Backend (.65). Creates owner partners, creates `tpl.client.config` records. |
| **Client IT Administrator** | Performs setup steps on the Client Odoo. Creates `tpl.sync.config` record. Ensures products have matching `default_code`. |
| **3PL Operations Manager** | Validates the connection test. Signs off before go-live. |

---

## 5. SYSTEM OVERVIEW

```
CLIENT ODOO (e.g. https://3pl-cliente.ecolight.com.uy)
  ↓  On ECO/PICK validate → calls Backend XML-RPC → creates/validates WH/PICK
  ↑  On WH/PICK validate → Backend calls Client XML-RPC → validates ECO/PICK

BACKEND ODOO (https://3pl.ecolight.com.uy)
  - Receives inbound/outbound orders from one or more clients
  - Routes each operation to the correct client via owner_partner_id
```

---

## 6. PRE-REQUISITES

Before starting, confirm:

- [ ] Backend Odoo module `tpl_3pl_back_sync` is installed and active
- [ ] Client Odoo module `tpl_3pl_sync` is installed and active
- [ ] Both systems are accessible via HTTPS from each other's server IP
- [ ] SSL certificates are valid on both URLs
- [ ] Products to be managed exist on both systems with **identical `default_code`**
- [ ] Firewall allows outbound HTTPS (port 443) from backend server IP to client URL and vice versa

---

## 7. PROCEDURE

### 7.1 — Backend: Create the Client Company Partner

> Performed by: **3PL System Administrator**

1. Log in to the Backend: `https://3pl.ecolight.com.uy` (admin / Admin@1234)
2. Navigate to **Contacts**
3. Click **New**
4. Fill in:
   - **Company Name**: the client's company name (e.g. `Ecolight SA`)
   - **Company Type**: Company
5. Click **Save**
6. Note the record **ID** (visible in the URL: `/web#id=XX&model=res.partner`).
   This ID is the `owner_partner_id` and the `backend_owner_id` used in steps 7.2 and 7.3.

> **Example**: Partner `ecoprueba sa` has id=16 in the backend database.

---

### 7.2 — Backend: Create the Client Connection Record

> Performed by: **3PL System Administrator**

1. Navigate to **Inventory → Configuration → Warehouse Management → 3PL Client Connections**
2. Click **New**
3. Fill in the following fields:

| Field | Value | Notes |
|---|---|---|
| **Name** | e.g. `Ecolight (3pl-cliente)` | Descriptive label |
| **Active** | ✓ Checked | Must be active for sync to work |
| **Owner Partner (backend)** | Select the partner created in step 7.1 | Links stock ownership to this client |
| **Client URL** | `https://3pl-cliente.ecolight.com.uy` | Must use HTTPS. No trailing slash. |
| **Client DB** | `3pl-cliente` | Exact database name on the client Odoo |
| **Client User** | `admin` | User with access to stock operations |
| **Client Password** | (client admin password) | Stored encrypted in database |

4. Click **Save**

> ⚠️ Never use `http://` in the Client URL field. Always use `https://`.

---

### 7.3 — Client: Create the Sync Configuration Record

> Performed by: **Client IT Administrator**

1. Log in to the Client Odoo: `https://3pl-cliente.ecolight.com.uy` (admin / Admin@1234)
2. Navigate to **Inventory → Configuration → 3PL Sync**
3. Click **New** (or edit the existing record)
4. Fill in the following fields:

| Field | Value | Notes |
|---|---|---|
| **Name** | e.g. `3PL Warehouse Backend` | Descriptive label |
| **Backend URL** | `https://3pl.ecolight.com.uy` | Must use HTTPS. No trailing slash. |
| **Backend DB** | `3pl` | Exact database name on the backend |
| **Backend User** | `admin` | Backend admin user |
| **Backend Password** | (backend admin password) | |
| **Backend Owner ID** | `16` | The integer ID of the partner created in step 7.1 |
| **On Sale Confirm → sync** | ✓ | Enables order sync on sale confirmation |
| **On ECO/PICK done → validate WH/PICK** | ✓ | |
| **On ECO/PACK done → validate WH/PACK** | ✓ | |
| **On ECO/OUT done → validate WH/OUT** | ✓ | |

5. Click **Save**

> ⚠️ The **Backend Owner ID** must match exactly the `res.partner` ID in the **Backend** database
> (not the client database). Verify with the 3PL System Administrator.

---

### 7.4 — Products: Verify Internal References Match

> Performed by: **Client IT Administrator** + **3PL System Administrator**

For every product that will be stored at the 3PL warehouse:

1. On the **Client Odoo**: go to **Inventory → Products** → open the product → note the **Internal Reference** (`default_code`)
2. On the **Backend Odoo**: go to **Inventory → Products** → find the same product → verify the **Internal Reference** is identical
3. If they differ, correct the Internal Reference on one side to match the other
4. Products without an Internal Reference will be skipped during sync — assign one before go-live

---

### 7.5 — Connection Test

> Performed by: **3PL System Administrator**

Run the following verification from the backend server terminal:

```bash
python3 << 'EOF'
import xmlrpc.client, ssl

# Test backend → client connection
backend_url = 'https://3pl.ecolight.com.uy'
client_url  = 'https://3pl-cliente.ecolight.com.uy'
pwd = 'Admin@1234'

# Authenticate to backend
uid_b = xmlrpc.client.ServerProxy(f'{backend_url}/xmlrpc/2/common').authenticate('3pl','admin',pwd,{})
print(f"Backend auth OK, uid={uid_b}")

# Read client config from backend
m_b = xmlrpc.client.ServerProxy(f'{backend_url}/xmlrpc/2/object')
cfg = m_b.execute_kw('3pl',uid_b,pwd,'tpl.client.config','search_read',
    [[['active','=',True]]], {'fields':['name','client_url','owner_partner_id']})
print(f"Client configs: {cfg}")

# Authenticate to client
uid_c = xmlrpc.client.ServerProxy(f'{client_url}/xmlrpc/2/common').authenticate('3pl-cliente','admin',pwd,{})
print(f"Client auth OK, uid={uid_c}")

# Read sync config from client
m_c = xmlrpc.client.ServerProxy(f'{client_url}/xmlrpc/2/object')
scfg = m_c.execute_kw('3pl-cliente',uid_c,pwd,'tpl.sync.config','search_read',
    [[['active','=',True]]], {'fields':['name','backend_url','backend_owner_id']})
print(f"Sync configs: {scfg}")

print("All connections OK")
EOF
```

Expected output:
```
Backend auth OK, uid=2
Client configs: [{'name': 'Ecolight (3pl-cliente)', 'client_url': 'https://3pl-cliente.ecolight.com.uy', 'owner_partner_id': [16, 'ecoprueba sa']}]
Client auth OK, uid=2
Sync configs: [{'name': '3PL Warehouse Backend', 'backend_url': 'https://3pl.ecolight.com.uy', 'backend_owner_id': 16}]
All connections OK
```

If authentication fails, verify URLs, database names, and credentials.

---

### 7.6 — Functional Test (First Order)

> Performed by: **3PL Operations Manager** + **Client IT Administrator**

1. On the **Client Odoo**, create a Sale Order with at least one product that has a matching `default_code`
2. Confirm the sale → a **Delivery Order (ECO/OUT)** is created
3. Validate the picking chain: ECO/PICK → ECO/PACK → ECO/OUT
4. On the **Backend Odoo**, verify that the corresponding WH/PICK → WH/PACK → WH/OUT were created and auto-validated
5. Check the chatter on each picking for the message `3PL BackSync: validated WH/...`
6. Verify stock levels decreased on the backend for the correct owner partner

---

## 8. MULTI-CLIENT SETUP

To add a second client company, repeat steps 7.1 through 7.5 for the new client:

| Step | Backend (.65) | New Client Odoo |
|---|---|---|
| 7.1 | Create new `res.partner` for new company (e.g. id=25) | — |
| 7.2 | Create new `tpl.client.config` with `owner_partner_id=25`, `client_url=https://new-client.example.com` | — |
| 7.3 | — | Create `tpl.sync.config` with `backend_url=https://3pl.ecolight.com.uy`, `backend_owner_id=25` |
| 7.4 | Verify product `default_code` matches | Verify product `default_code` matches |
| 7.5 | Run connection test | — |

Each client's stock is fully segregated by the `owner_partner_id` — there is no cross-contamination
between clients.

---

## 9. CURRENT PRODUCTION CONFIGURATION

### Backend — https://3pl.ecolight.com.uy (database: 3pl)

| Field | Value |
|---|---|
| Admin user | admin |
| Server IP | 192.168.1.65 |
| Addon path | `/opt/odoo18/extra-addons/others-18.0/tpl_3pl_back_sync/` |

### Client — https://3pl-cliente.ecolight.com.uy (database: 3pl-cliente)

| Field | Value |
|---|---|
| Admin user | admin |
| Server IP | 192.168.1.64 |
| Addon path | `/opt/odoo18/extra-addons/others-18.0/tpl_3pl_sync/` |
| Owner partner in backend | `ecoprueba sa` (id=16) |

### Portal access (backend)

| Field | Value |
|---|---|
| Portal URL | https://3pl.ecolight.com.uy/my/3pl/stock |
| Test user | ecoprueba.portal@3pl.com |
| Password | ecoprueba123 |

---

## 10. TROUBLESHOOTING

| Symptom | Probable Cause | Resolution |
|---|---|---|
| Sync message not appearing on picking | `tpl.sync.config` inactive or wrong backend URL | Check Inventory → Configuration → 3PL Sync |
| `Cannot authenticate to backend` error | Wrong URL, DB name, or password | Verify all fields in `tpl.sync.config` |
| Product skipped during sync | Product has no `default_code` or codes don't match | Assign matching Internal Reference on both sides |
| `no client config for owner partner id=X` in backend logs | `tpl.client.config` missing for that owner | Create record in Inventory → Configuration → 3PL Client Connections |
| SSL error (`CERTIFICATE_VERIFY_FAILED`) | Client or backend URL uses self-signed certificate | Install valid certificate or add CA to trust store |
| Sync works on HTTP but not HTTPS | Nginx not forwarding `/xmlrpc/` correctly | Verify nginx proxy config passes `/xmlrpc/2/` to Odoo |

---

## 11. REVISION HISTORY

| Rev | Date | Author | Description |
|---|---|---|---|
| 1.0 | 2026-05-13 | IT Admin | Initial issue |

---

*End of document PRO-3PL-001 Rev 1.0*
