#!/usr/bin/env python3
"""L2-14 LedgerSMB, native APF reproduction (EXPOSED).

Decisive surface: a GL transaction is posted/effective when its persisted
`approved` flag is true (`transactions.approved` / `acc_trans.approved`). The
authorized path is the approval workflow (an authorized user approving). The APF
forge is a state-only write of `approved = true`.

LedgerSMB keeps data in a company database created during setup. This harness
connects to PostgreSQL, locates a company database that has the LedgerSMB
`transactions` table, finds an un-approved transaction (CONTROL), forges
`approved = true` (FORGE), and reads it back (VERIFY). If no company database /
un-approved transaction exists (setup not completed), it records INCONCLUSIVE.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-14"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
PG = dict(host="127.0.0.1", port=5432, user="postgres", password="postgres")


def company_dbs(conn):
    rows = common.sql_exec(
        conn, "SELECT datname FROM pg_database WHERE datistemplate=false "
              "AND datname NOT IN ('postgres')", fetch=True)
    return [r[0] for r in rows]


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="LedgerSMB", expected_verdict=common.EXPOSED,
        version="ledgersmb/ledgersmb:1.11",
        decisive_surface="transactions.approved == true")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=1800):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            common.wait_tcp("127.0.0.1", 5762, timeout=900, ev=ev)

            # find a company DB with an un-approved transaction (wait for setup)
            target = txn = status0 = None
            for _ in range(30):
                admin = common.pg(dbname="postgres", **PG)
                for db in company_dbs(admin):
                    try:
                        c = common.pg(dbname=db, **PG)
                        rows = common.sql_exec(
                            c, "SELECT id, approved FROM transactions "
                               "WHERE approved IS NOT TRUE ORDER BY id LIMIT 1", fetch=True)
                        if rows:
                            target, (txn, status0) = db, rows[0]
                            break
                    except Exception:
                        continue
                if target:
                    break
                time.sleep(10)

            if not target:
                ev.verdict = common.INCONCLUSIVE
                ev.error = ("no LedgerSMB company database with an un-approved transaction "
                            "found (company setup/seed not completed in this run)")
                return
            ev.step("control txn", f"db={target} id={txn} approved={status0}")

            c = common.pg(dbname=target, **PG)
            common.sql_exec(c, "UPDATE transactions SET approved=true WHERE id=%s", (txn,))
            ev.step("forge", f"UPDATE transactions SET approved=true WHERE id={txn} (db={target})")
            status1 = common.sql_exec(
                c, "SELECT approved FROM transactions WHERE id=%s", (txn,), fetch=True)[0][0]
            ev.step("verify", f"approved={status1}")

            if not status0 and status1:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write approved the GL transaction without the "
                                   "approval workflow; it is now posted/effective")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected approved control={status0} after_forge={status1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
