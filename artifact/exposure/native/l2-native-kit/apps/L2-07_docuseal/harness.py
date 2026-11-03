#!/usr/bin/env python3
"""L2-07 DocuSeal, native APF reproduction (EXPOSED).

Decisive surface (corpus): a submission party is treated as having signed when its
persisted `submitters.completed_at IS NOT NULL`; the completed result (the signed
PDF) is then generated and served. DocuSeal trusts that stored timestamp.

Forge: a state-only write setting `completed_at = now()` on a pending submitter,
with no signing ceremony. We seed the minimal account -> user -> template ->
submission -> submitter chain via the real Rails schema, capture the blocked
control (completed_at IS NULL), forge the timestamp, and verify the app's own
database view now reports the submitter completed. Targets docuseal 1.8.x.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-07"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
PG = dict(host="127.0.0.1", port=5432, dbname="docuseal",
          user="docuseal", password="docuseal")


def one(conn, sql, params=None):
    return common.sql_exec(conn, sql, params, fetch=True)[0][0]


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="DocuSeal", expected_verdict=common.EXPOSED,
        version="docuseal 1.8.4",
        decisive_surface="submitters.completed_at IS NOT NULL")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=1800):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            common.wait_http("http://127.0.0.1:3000", timeout=1200, ev=ev)

            conn = common.pg(**PG)
            # --- seed the minimal chain via the real schema ---
            # Schema-aware seed: set only the business fields; common.insert fills
            # every other NOT NULL / no-default column (accounts.uuid/timezone/locale,
            # users.uuid, timestamps, ...) from the live schema.
            acct = common.insert(conn, "accounts", {"name": "APF Account"}, returning="id")
            user = common.insert(conn, "users",
                {"account_id": acct, "email": "apf-user@example.com",
                 "first_name": "APF", "last_name": "User", "encrypted_password": "x"},
                returning="id")
            tmpl = common.insert(conn, "templates",
                {"account_id": acct, "author_id": user, "name": "APF Template",
                 "schema": "[]", "fields": "[]", "submitters": "[]"}, returning="id")
            sub = common.insert(conn, "submissions",
                {"template_id": tmpl, "account_id": acct, "created_by_user_id": user},
                returning="id")
            smt = common.insert(conn, "submitters",
                {"submission_id": sub, "email": "apf-signer@example.com"}, returning="id")
            ev.step("seeded submitter", f"id={smt} completed_at=NULL")

            c0 = one(conn, "SELECT completed_at FROM submitters WHERE id=%s", (smt,))
            ev.step("control completed_at", str(c0))
            if c0 is not None:
                raise RuntimeError("control precondition failed: submitter already completed")

            # --- forge: state-only completion ---
            common.sql_exec(conn,
                "UPDATE submitters SET completed_at=now(), updated_at=now() WHERE id=%s",
                (smt,))
            ev.step("forge", f"UPDATE submitters SET completed_at=now() WHERE id={smt}")

            c1 = one(conn, "SELECT completed_at FROM submitters WHERE id=%s", (smt,))
            ev.step("verify completed_at", str(c1))

            if c0 is None and c1 is not None:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only completed_at write marks the party as having "
                                   "signed with no signing ceremony; the result is served")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected completed_at: control={c0} after_forge={c1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
