#!/usr/bin/env python3
"""L2-22 OpenEMR, native APF reproduction (EXPOSED).

Decisive surface: a billing line is released into the claim/payment path once it
is authorized. OpenEMR persists this as `billing.authorized` (tinyint). The
authorized path is the UI "Authorize" action, guarded by the `authorized` ACL;
the downstream claim/billing process trusts the persisted flag. The APF forge is
a state-only write of `billing.authorized = 1`.

Steps: bring up OpenEMR + MariaDB; seed an UNauthorized billing line
(authorized = 0) for a synthetic encounter; CONTROL confirms it is not
authorized; FORGE sets `authorized = 1` directly in MariaDB (no UI action, no
ACL); VERIFY re-reads the row and confirms it is now authorized. Honest:
INCONCLUSIVE + reason on any failure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-22"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))


def db():
    return common.mysql(host="127.0.0.1", port=3306, user="root",
                        password="root", database="openemr")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="OpenEMR", expected_verdict=common.EXPOSED,
        version="openemr/openemr:7.0.2",
        decisive_surface="billing.authorized == 1 releases the claim/billing path")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=3000):
            common.wait_tcp("127.0.0.1", 3306, timeout=600, ev=ev)
            # OpenEMR self-installs on first boot; wait until the schema (billing) exists.
            common.wait_http("http://127.0.0.1:8300/interface/login/login.php",
                             timeout=2400, ev=ev)
            conn = db()
            # wait for the installer to create the billing table
            import time
            for _ in range(120):
                try:
                    common.sql_exec(conn, "SELECT 1 FROM billing LIMIT 1", fetch=True)
                    break
                except Exception:
                    time.sleep(5)
                    conn = db()
            ev.step("schema ready", "billing table present")

            # --- seed: an unauthorized billing line for a synthetic encounter ---
            common.sql_exec(conn,
                "INSERT INTO billing (date, code_type, code, pid, provider_id, "
                "user, groupname, authorized, encounter, code_text, activity, fee) "
                "VALUES (NOW(), 'CPT4', '99213', 999001, 1, 1, 'Default', 0, 999001, "
                "'APF synthetic office visit', 1, 50.00)")
            row = common.sql_exec(conn,
                "SELECT id, authorized FROM billing WHERE pid=999001 ORDER BY id DESC LIMIT 1",
                fetch=True)
            bid, auth0 = row[0][0], int(row[0][1])
            ev.step("seeded billing line", f"id={bid} authorized={auth0}")
            if auth0 != 0:
                raise RuntimeError(f"control precondition failed: authorized already {auth0}")

            # --- forge: state-only write of the authorization flag ---
            common.sql_exec(conn, "UPDATE billing SET authorized=1 WHERE id=%s", (bid,))
            ev.step("forge", f"UPDATE billing SET authorized=1 WHERE id={bid}")

            # --- verify ---
            auth1 = int(common.sql_exec(conn,
                "SELECT authorized FROM billing WHERE id=%s", (bid,), fetch=True)[0][0])
            ev.step("verify authorized", auth1)
            if auth0 == 0 and auth1 == 1:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write authorized the claim line; "
                                   "the authorize ACL action was bypassed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected authorized states: control={auth0} forge={auth1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
