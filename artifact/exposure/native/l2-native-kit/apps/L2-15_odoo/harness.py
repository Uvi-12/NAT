#!/usr/bin/env python3
"""L2-15 Odoo Community, native APF reproduction (EXPOSED).

Decisive surface (from the corpus): a purchase order is committed/orderable when
`purchase.order.state == 'purchase'`. The authorized path is the `button_confirm`
action (which enforces the purchase-approval group and any approval threshold).
The APF forge is a state-only write of that persisted `state` value, bypassing
button_confirm, the order is then treated as confirmed by Odoo.

This harness:
  1. brings up the real Odoo image + PostgreSQL,
  2. seeds a supplier, a product, and a draft purchase order via Odoo's own
     XML-RPC API,
  3. CONTROL: confirms the order is not yet committed (state != 'purchase'),
  4. FORGE: performs a state-only `UPDATE purchase_order SET state='purchase'`
     directly in PostgreSQL (no button_confirm, no group check),
  5. VERIFY: re-reads the order through Odoo's XML-RPC API and confirms Odoo now
     reports it as a confirmed purchase order,
  6. writes an EXPOSED evidence record (or INCONCLUSIVE + reason on any failure).

Reference template for the kit's other app harnesses. Targets Odoo 17.
"""
import os
import sys
import xmlrpc.client

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-15"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
URL = "http://127.0.0.1:8069"
DB = "apfdb"
LOGIN, PWD = "admin", "admin"


def rpc_login():
    common_proxy = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
    uid = common_proxy.authenticate(DB, LOGIN, PWD, {})
    if not uid:
        raise RuntimeError("Odoo XML-RPC authentication failed (admin/admin)")
    models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")
    return uid, models


def call(models, uid, model, method, *args, **kw):
    return models.execute_kw(DB, uid, PWD, model, method, list(args), kw)


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Odoo Community", expected_verdict=common.EXPOSED,
        version="odoo:17", decisive_surface="purchase.order.state == 'purchase'")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            # Odoo initialises the DB on first boot (-i purchase); wait for web + db.
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            common.wait_http(f"{URL}/web/login", timeout=1800, ev=ev)

            uid, models = rpc_login()
            ev.step("xmlrpc auth", f"uid={uid}")

            # --- seed: supplier, product, draft PO ---
            partner = call(models, uid, "res.partner", "create",
                           {"name": "APF Test Supplier", "supplier_rank": 1})
            product = call(models, uid, "product.product", "create",
                           {"name": "APF Widget", "purchase_ok": True,
                            "list_price": 10.0, "standard_price": 8.0})
            po = call(models, uid, "purchase.order", "create", {
                "partner_id": partner,
                "order_line": [(0, 0, {
                    "product_id": product, "product_qty": 5, "price_unit": 8.0,
                    "name": "APF Widget", "date_planned": "2027-01-01 00:00:00",
                })],
            })
            ev.step("seeded PO", f"po_id={po}")

            state0 = call(models, uid, "purchase.order", "read", [po], ["state"])[0]["state"]
            ev.step("control state", state0)
            if state0 == "purchase":
                raise RuntimeError(f"control precondition failed: PO already 'purchase' ({state0})")

            # --- forge: state-only write directly in PostgreSQL ---
            conn = common.pg(host="127.0.0.1", port=5432, dbname=DB,
                             user="odoo", password="odoo")
            common.sql_exec(conn, "UPDATE purchase_order SET state=%s WHERE id=%s",
                            ("purchase", po))
            ev.step("forge", f"UPDATE purchase_order SET state='purchase' WHERE id={po}")

            # --- verify: Odoo's own API now reports it confirmed ---
            state1 = call(models, uid, "purchase.order", "read", [po],
                          ["state", "name"])[0]
            ev.step("verify state", state1)

            if state0 != "purchase" and state1.get("state") == "purchase":
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write released the committed PO; "
                                   "button_confirm authorization bypassed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected states: control={state0} after_forge={state1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
