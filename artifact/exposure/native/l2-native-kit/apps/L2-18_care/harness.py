#!/usr/bin/env python3
"""L2-18 care (OHC Network), native APF reproduction (EXPOSED).

Decisive surface: a patient-transfer (shifting) request is released to the
destination once approved. care persists this as `facility_shiftingrequest.status`
(an integer status). The authorized path is the approve action (role-gated); the
downstream flow trusts the persisted status. The APF forge is a state-only write
of that status to an approved value.

Steps: bring up care backend + PostgreSQL + Redis; locate a shifting request not
in an approved status; CONTROL; FORGE `UPDATE facility_shiftingrequest SET
status=<approved>`; VERIFY. If no shifting request exists (nothing seeded) or the
schema differs, record INCONCLUSIVE with the reason.

The approved status integer varies across care versions; override with
APF_CARE_APPROVED_STATUS (default 30, the DESTINATION-APPROVED-ish code).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-18"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
APPROVED = int(os.environ.get("APF_CARE_APPROVED_STATUS", "30"))


def db():
    return common.pg(host="127.0.0.1", port=5432, dbname="care",
                     user="postgres", password="postgres")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="care (OHC Network)", expected_verdict=common.EXPOSED,
        version="ohcnetwork/care:latest",
        decisive_surface="facility_shiftingrequest.status == approved releases transfer")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=600, ev=ev)
            conn = db()
            # wait for migrations to create the table
            import time
            table_ok = False
            for _ in range(120):
                try:
                    common.sql_exec(conn, "SELECT 1 FROM facility_shiftingrequest LIMIT 1",
                                    fetch=True)
                    table_ok = True
                    break
                except Exception:
                    time.sleep(5)
                    conn = db()
            if not table_ok:
                ev.verdict = common.INCONCLUSIVE
                ev.error = "facility_shiftingrequest table not present (migrations/schema differ)"
                return

            req = common.sql_exec(conn,
                "SELECT id, status FROM facility_shiftingrequest "
                "WHERE status IS DISTINCT FROM %s ORDER BY id LIMIT 1",
                (APPROVED,), fetch=True)
            if not req:
                ev.verdict = common.INCONCLUSIVE
                ev.error = ("no shifting request present, seed one via care's API "
                            "(facility/patient/user setup required)")
                return
            rid, st0 = req[0]
            ev.step("control shifting request", f"id={rid} status={st0} approved_code={APPROVED}")

            # --- forge: state-only write of the approval status ---
            common.sql_exec(conn, "UPDATE facility_shiftingrequest SET status=%s WHERE id=%s",
                            (APPROVED, rid))
            ev.step("forge", f"UPDATE facility_shiftingrequest SET status={APPROVED} WHERE id={rid}")

            st1 = common.sql_exec(conn,
                "SELECT status FROM facility_shiftingrequest WHERE id=%s", (rid,),
                fetch=True)[0][0]
            ev.step("verify status", st1)
            if st0 != APPROVED and st1 == APPROVED:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write approved the transfer; the role-gated "
                                   "approve action was bypassed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected status: control={st0} forge={st1} approved={APPROVED}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
