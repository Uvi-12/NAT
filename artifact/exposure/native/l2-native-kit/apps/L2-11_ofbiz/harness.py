#!/usr/bin/env python3
"""L2-11 Apache OFBiz, native APF reproduction (EXPOSED).

Decisive surface: a sales order is released to picking/shipping when
`OrderHeader.statusId == 'ORDER_APPROVED'`. The authorized path is the order
approval service (which enforces security permissions). The APF forge is a
state-only write of that persisted status, bypassing the service.

Steps: bring up OFBiz + PostgreSQL (demo data loads sample orders); pick a demo
order that is not yet approved (CONTROL); UPDATE order_header SET status_id =
'ORDER_APPROVED' directly in PostgreSQL (FORGE); read it back and confirm OFBiz's
persisted order status is now approved (VERIFY). If no seed order is available,
record INCONCLUSIVE rather than forcing a result.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-11"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
PG = dict(host="127.0.0.1", port=5432, dbname="ofbiz", user="ofbiz", password="ofbiz")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Apache OFBiz", expected_verdict=common.EXPOSED,
        version="apache/ofbiz:23.01.01",
        decisive_surface="OrderHeader.statusId == 'ORDER_APPROVED'")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            # OFBiz is slow to load seed+demo data; wait for the https port.
            common.wait_tcp("127.0.0.1", 8443, timeout=2000, ev=ev)

            conn = common.pg(**PG)
            # Wait until demo data is present (order_header populated).
            import time
            order_id = None
            for _ in range(60):
                rows = common.sql_exec(
                    conn,
                    "SELECT order_id, status_id FROM order_header "
                    "WHERE order_type_id='SALES_ORDER' AND status_id <> 'ORDER_APPROVED' "
                    "ORDER BY order_id LIMIT 1", fetch=True)
                if rows:
                    order_id, status0 = rows[0]
                    break
                time.sleep(10)
            if not order_id:
                ev.verdict = common.INCONCLUSIVE
                ev.error = "no un-approved demo sales order found in order_header (demo data not loaded?)"
                return
            ev.step("control order", f"order_id={order_id} status_id={status0}")

            common.sql_exec(
                conn, "UPDATE order_header SET status_id='ORDER_APPROVED' WHERE order_id=%s",
                (order_id,))
            ev.step("forge", f"UPDATE order_header SET status_id='ORDER_APPROVED' WHERE order_id={order_id}")

            status1 = common.sql_exec(
                conn, "SELECT status_id FROM order_header WHERE order_id=%s",
                (order_id,), fetch=True)[0][0]
            ev.step("verify", f"status_id={status1}")

            if status0 != "ORDER_APPROVED" and status1 == "ORDER_APPROVED":
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write set the order to ORDER_APPROVED "
                                   "without the approval service; order is now releasable")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected statuses control={status0} after_forge={status1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
