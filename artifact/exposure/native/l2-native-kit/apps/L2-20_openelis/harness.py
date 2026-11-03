#!/usr/bin/env python3
"""L2-20 OpenELIS Global, native APF reproduction (EXPOSED).

Decisive surface: a lab result is released to the ordering provider once its
analysis is validated/finalized. OpenELIS persists this as
`clinlims.analysis.status_id` pointing at a result status. The authorized path is
the validation screen (validation role). The APF forge is a state-only write of
`analysis.status_id` to the finalized/validated status.

Steps: bring up OpenELIS app + its PostgreSQL; resolve the "Finalized" analysis
status id from the status reference; pick an analysis not yet in that status;
CONTROL; FORGE `UPDATE analysis SET status_id = <finalized>`; VERIFY. If no
analysis exists (no seeded order), record INCONCLUSIVE with that reason.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-20"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))


def db():
    return common.pg(host="127.0.0.1", port=5432, dbname="clinlims",
                     user="clinlims", password="clinlims",
                     options="-c search_path=clinlims")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="OpenELIS Global", expected_verdict=common.EXPOSED,
        version="ghcr.io/i-tech-uw/openelis-global-2:latest",
        decisive_surface="analysis.status_id == finalized releases the result")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=600, ev=ev)
            conn = db()

            # resolve a finalized/validated analysis status id from the status table
            fin = common.sql_exec(conn,
                "SELECT id FROM status_of_sample WHERE status_type='ANALYSIS' "
                "AND (name ILIKE '%%finalized%%' OR name ILIKE '%%validat%%' "
                "OR name ILIKE '%%accept%%') ORDER BY id LIMIT 1", fetch=True)
            if not fin:
                ev.verdict = common.INCONCLUSIVE
                ev.error = "could not resolve a finalized analysis status id (status schema differs)"
                return
            fin_id = fin[0][0]

            an = common.sql_exec(conn,
                "SELECT id, status_id FROM analysis WHERE status_id IS DISTINCT FROM %s "
                "ORDER BY id LIMIT 1", (fin_id,), fetch=True)
            if not an:
                ev.verdict = common.INCONCLUSIVE
                ev.error = "no non-finalized analysis present, seed a lab order first"
                return
            aid, st0 = an[0]
            ev.step("control analysis", f"id={aid} status_id={st0} finalized_id={fin_id}")

            # --- forge: state-only write of the analysis status ---
            common.sql_exec(conn, "UPDATE analysis SET status_id=%s WHERE id=%s",
                            (fin_id, aid))
            ev.step("forge", f"UPDATE analysis SET status_id={fin_id} WHERE id={aid}")

            st1 = common.sql_exec(conn, "SELECT status_id FROM analysis WHERE id=%s",
                                  (aid,), fetch=True)[0][0]
            ev.step("verify status", st1)
            if str(st0) != str(fin_id) and str(st1) == str(fin_id):
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write finalized the result; the validation "
                                   "role action was bypassed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected status: control={st0} forge={st1} finalized={fin_id}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
