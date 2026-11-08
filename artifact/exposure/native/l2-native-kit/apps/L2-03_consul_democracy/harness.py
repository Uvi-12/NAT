#!/usr/bin/env python3
"""L2-03 Consul Democracy, native APF reproduction (EXPOSED).

Decisive surface (corpus): a participatory-budget investment reaches the funding
ballot / winners list once `budget_investments.selected` is true. The authorized
path is the admin "select for final voting" action; the APF forge is a state-only
write of that persisted `selected` flag.

Steps: bring up the real Consul Democracy image + PostgreSQL; seed the minimal
budget -> group -> heading -> investment chain via SQL; CONTROL that the
investment is not selected; FORGE `UPDATE budget_investments SET selected='t'`;
VERIFY the row is now selected (reaches the funding ballot). EXPOSED, or
INCONCLUSIVE + reason on any failure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-03"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
PG = dict(host="127.0.0.1", port=5432, dbname="consul_production",
          user="consul", password="consul")


def seed_investment(conn):
    """Create a minimal budget/group/heading/investment chain. Returns id."""
    q = common.sql_exec
    # a budget in the 'selecting' phase
    bid = q(conn, "INSERT INTO budgets (name_en, phase, currency_symbol, created_at, updated_at) "
                  "VALUES ('APF Budget','selecting','$',now(),now()) RETURNING id",
            fetch=True)[0][0]
    gid = q(conn, "INSERT INTO budget_groups (budget_id, name_en, created_at, updated_at) "
                  "VALUES (%s,'APF Group',now(),now()) RETURNING id", (bid,), fetch=True)[0][0]
    hid = q(conn, "INSERT INTO budget_headings (group_id, name_en, price, population, created_at, updated_at) "
                  "VALUES (%s,'APF Heading',100000,1000,now(),now()) RETURNING id", (gid,), fetch=True)[0][0]
    iid = q(conn, "INSERT INTO budget_investments "
                  "(budget_id, heading_id, group_id, title, cached_votes_up, selected, created_at, updated_at) "
                  "VALUES (%s,%s,%s,'APF Investment',0,false,now(),now()) RETURNING id",
            (bid, hid, gid), fetch=True)[0][0]
    return iid


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Consul Democracy", expected_verdict=common.EXPOSED,
        version="consuldemocracy:master",
        decisive_surface="budget_investments.selected == true")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            common.wait_http("http://127.0.0.1:3000/", timeout=1800, ev=ev)

            conn = common.pg(**PG)
            iid = seed_investment(conn)
            ev.step("seeded investment", f"id={iid}")

            sel0 = common.sql_exec(conn, "SELECT selected FROM budget_investments WHERE id=%s",
                                   (iid,), fetch=True)[0][0]
            ev.step("control selected", sel0)
            if sel0:
                raise RuntimeError("control precondition failed: investment already selected")

            common.sql_exec(conn, "UPDATE budget_investments SET selected='t' WHERE id=%s", (iid,))
            ev.step("forge", f"UPDATE budget_investments SET selected='t' WHERE id={iid}")

            sel1 = common.sql_exec(conn, "SELECT selected FROM budget_investments WHERE id=%s",
                                   (iid,), fetch=True)[0][0]
            ev.step("verify selected", sel1)

            if (not sel0) and sel1:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write marked the investment selected; it now "
                                   "reaches the funding ballot without the admin selection action")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected: control={sel0} after_forge={sel1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
