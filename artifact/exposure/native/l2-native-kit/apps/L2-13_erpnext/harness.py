#!/usr/bin/env python3
"""L2-13 ERPNext, native APF reproduction (EXPOSED).

Decisive surface: a Purchase Order is Submitted (releasable / a payment target)
when `docstatus == 1`. The authorized path is the Submit workflow action (which
runs validations and the submit permission). The APF forge is a state-only write
of `docstatus` to 1, bypassing Submit.

Steps: bring up ERPNext + MariaDB + Redis; create a supplier, item, and a draft
Purchase Order (docstatus 0) via the Frappe REST API (CONTROL); UPDATE the
persisted `tabPurchase Order`.docstatus to 1 directly in MariaDB (FORGE); re-read
the PO through the REST API and confirm ERPNext now reports it Submitted (VERIFY).
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-13"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
BASE = "http://apf.localhost:8000"
HOSTHDR = "apf.localhost"
AUTH = "token "  # filled after login; ERPNext default admin/admin
MYSQL = dict(host="127.0.0.1", port=3306, user="root", password="admin", database="")


def api(method, path, body=None, sid=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Host", HOSTHDR)
    req.add_header("Content-Type", "application/json")
    if sid:
        req.add_header("Cookie", f"sid={sid}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read() or b"{}")


def login():
    # returns the sid cookie from /api/method/login
    url = BASE + "/api/method/login"
    data = json.dumps({"usr": "Administrator", "pwd": "admin"}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Host", HOSTHDR)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        for c in r.headers.get_all("Set-Cookie") or []:
            if c.startswith("sid="):
                return c.split("sid=", 1)[1].split(";", 1)[0]
    raise RuntimeError("ERPNext login returned no sid cookie")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="ERPNext", expected_verdict=common.EXPOSED,
        version="frappe/erpnext:v15.42.0",
        decisive_surface="tabPurchase Order.docstatus == 1 (Submitted)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=3000):
            common.wait_tcp("127.0.0.1", 3306, timeout=600, ev=ev)
            common.wait_http(f"{BASE}/api/method/ping", timeout=2400, ev=ev)

            sid = login()
            ev.step("login", "sid acquired")
            # minimal masters
            api("POST", "/api/resource/Supplier",
                {"supplier_name": "APF Supplier", "supplier_group": "All Supplier Groups",
                 "supplier_type": "Company"}, sid)
            api("POST", "/api/resource/Item",
                {"item_code": "APF-WIDGET", "item_group": "All Item Groups",
                 "stock_uom": "Nos", "is_purchase_item": 1}, sid)
            # draft PO (docstatus defaults to 0)
            st, resp = api("POST", "/api/resource/Purchase Order", {
                "supplier": "APF Supplier",
                "schedule_date": "2027-01-01",
                "items": [{"item_code": "APF-WIDGET", "qty": 5, "rate": 10,
                           "schedule_date": "2027-01-01"}],
            }, sid)
            po = resp.get("data", {}).get("name")
            if not po:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"could not create draft PO: {st} {resp}"
                return
            ev.step("seeded PO", f"name={po}")

            _, r0 = api("GET", f"/api/resource/Purchase Order/{po}", sid=sid)
            ds0 = r0.get("data", {}).get("docstatus")
            ev.step("control docstatus", ds0)
            if ds0 == 1:
                raise RuntimeError("control precondition failed: PO already Submitted")

            # forge: state-only write in MariaDB (site db name is hashed; find it)
            conn = common.mysql(**MYSQL)
            dbs = common.sql_exec(conn, "SHOW DATABASES", fetch=True)
            site_db = next((d[0] for d in dbs if d[0].startswith("_")), None)
            if not site_db:
                ev.verdict = common.INCONCLUSIVE
                ev.error = "could not locate the ERPNext site database"
                return
            common.sql_exec(conn, f"USE `{site_db}`")
            common.sql_exec(conn, "UPDATE `tabPurchase Order` SET docstatus=1 WHERE name=%s", (po,))
            ev.step("forge", f"UPDATE `tabPurchase Order` SET docstatus=1 WHERE name={po} (db={site_db})")

            _, r1 = api("GET", f"/api/resource/Purchase Order/{po}", sid=sid)
            ds1 = r1.get("data", {}).get("docstatus")
            ev.step("verify docstatus", ds1)

            if ds0 != 1 and ds1 == 1:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only docstatus write made ERPNext report the PO "
                                   "Submitted/releasable without the Submit action")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected docstatus control={ds0} after_forge={ds1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
