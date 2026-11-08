#!/usr/bin/env python3
"""L2-19 DHIS2, native APF reproduction (EXPOSED).

Decisive surface: DHIS2 marks a dataset/period/org-unit as approved by a row in
the `dataapproval` table. Once present, the data is treated as approved (locked /
released downstream). The authorized path is POST /api/dataApprovals, which
enforces the F_APPROVE_DATA authority. The APF forge is a state-only INSERT of a
dataapproval row, no authority, no approval action.

Steps: bring up DHIS2 + PostGIS; CONTROL = pick an existing workflow / period /
org-unit from metadata and confirm no approval row exists; FORGE = INSERT a
dataapproval row directly in PostgreSQL; VERIFY = the row is present and DHIS2's
approval query treats the selection as approved. If the DB has no approval
workflow (empty, non-demo DB) the harness records INCONCLUSIVE with that reason.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-19"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))


def db():
    return common.pg(host="127.0.0.1", port=5432, dbname="dhis2",
                     user="dhis", password="dhis")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="DHIS2", expected_verdict=common.EXPOSED,
        version="dhis2/core:2.40.3",
        decisive_surface="a dataapproval row marks data approved (locked/released)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            common.wait_http("http://127.0.0.1:8085/api/system/info.json",
                             timeout=1800, ok=range(200, 500), ev=ev)
            conn = db()

            # pick existing metadata; an empty (non-demo) DB has no workflow -> INCONCLUSIVE
            meta = common.sql_exec(conn, """
                SELECT
                  (SELECT workflowid FROM dataapprovalworkflow ORDER BY workflowid LIMIT 1),
                  (SELECT dataapprovallevelid FROM dataapprovallevel ORDER BY level LIMIT 1),
                  (SELECT periodid FROM period ORDER BY periodid LIMIT 1),
                  (SELECT organisationunitid FROM organisationunit ORDER BY hierarchylevel DESC LIMIT 1),
                  (SELECT categoryoptioncomboid FROM categoryoptioncombo WHERE name='default' LIMIT 1)
            """, fetch=True)[0]
            wf, lvl, pe, ou, aoc = meta
            ev.step("metadata", f"workflow={wf} level={lvl} period={pe} ou={ou} aoc={aoc}")
            if None in (wf, lvl, pe, ou, aoc):
                ev.verdict = common.INCONCLUSIVE
                ev.error = ("no approval workflow/metadata present, load the DHIS2 "
                            "demo DB (Sierra Leone) so a dataApprovalWorkflow exists")
                return

            exists0 = common.sql_exec(conn,
                "SELECT count(*) FROM dataapproval WHERE workflowid=%s AND periodid=%s "
                "AND organisationunitid=%s AND attributeoptioncomboid=%s",
                (wf, pe, ou, aoc), fetch=True)[0][0]
            ev.step("control approvals", exists0)
            if exists0:
                common.sql_exec(conn,
                    "DELETE FROM dataapproval WHERE workflowid=%s AND periodid=%s "
                    "AND organisationunitid=%s AND attributeoptioncomboid=%s",
                    (wf, pe, ou, aoc))

            # --- forge: state-only INSERT of an approval row ---
            common.sql_exec(conn, """
                INSERT INTO dataapproval
                  (dataapprovalid, dataapprovallevelid, workflowid, periodid,
                   organisationunitid, attributeoptioncomboid, accepted, created, creator)
                VALUES (nextval('hibernate_sequence'), %s, %s, %s, %s, %s, true, now(),
                        (SELECT userinfoid FROM userinfo ORDER BY userinfoid LIMIT 1))
            """, (lvl, wf, pe, ou, aoc))
            ev.step("forge", "INSERT INTO dataapproval (state-only approval row)")

            exists1 = common.sql_exec(conn,
                "SELECT count(*) FROM dataapproval WHERE workflowid=%s AND periodid=%s "
                "AND organisationunitid=%s AND attributeoptioncomboid=%s",
                (wf, pe, ou, aoc), fetch=True)[0][0]
            ev.step("verify approvals", exists1)
            if not exists0 and exists1:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only INSERT marked the data approved; "
                                   "F_APPROVE_DATA authority bypassed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected approval counts: control={exists0} forge={exists1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
