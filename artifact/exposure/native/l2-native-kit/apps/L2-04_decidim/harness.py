#!/usr/bin/env python3
"""L2-04 Decidim, native APF reproduction (EXPOSED).

Decisive surface (corpus): a user's eligibility to vote / sign is gated by a
`decidim_authorizations` record (a granted verification). The authorized path is
a verification workflow that issues the authorization; the APF forge is a
state-only insert of a granted authorization row, marking the user verified
without any verification taking place.

Steps: bring up the real Decidim image + PostgreSQL; pick/seed a user; CONTROL
that the user has no granted authorization; FORGE an INSERT into
`decidim_authorizations` with `granted_at` set; VERIFY the user is now verified.
EXPOSED, or INCONCLUSIVE + reason on any failure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-04"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
PG = dict(host="127.0.0.1", port=5432, dbname="decidim_prod",
          user="decidim", password="decidim")


def ensure_user(conn):
    """Return a user id, reuse a seeded user or create a minimal one."""
    rows = common.sql_exec(conn, "SELECT id, decidim_organization_id FROM decidim_users "
                                 "WHERE deleted_at IS NULL ORDER BY id LIMIT 1", fetch=True)
    if rows:
        return rows[0][0], rows[0][1]
    org = common.sql_exec(conn, "SELECT id FROM decidim_organizations ORDER BY id LIMIT 1",
                          fetch=True)
    if not org:
        raise RuntimeError("no decidim_organizations present (seed did not run)")
    oid = org[0][0]
    uid = common.sql_exec(conn,
        "INSERT INTO decidim_users (decidim_organization_id, email, name, nickname, "
        " encrypted_password, confirmed_at, created_at, updated_at, sign_in_count) "
        "VALUES (%s,'apf-voter@example.com','APF Voter','apf_voter','x',now(),now(),now(),0) "
        "RETURNING id", (oid,), fetch=True)[0][0]
    return uid, oid


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Decidim", expected_verdict=common.EXPOSED,
        version="decidim:0.28",
        decisive_surface="decidim_authorizations.granted_at IS NOT NULL")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            common.wait_http("http://127.0.0.1:3000/", timeout=1800, ev=ev)

            conn = common.pg(**PG)
            uid, oid = ensure_user(conn)
            ev.step("user", f"id={uid} org={oid}")

            g0 = common.sql_exec(conn, "SELECT count(*) FROM decidim_authorizations "
                                       "WHERE decidim_user_id=%s AND granted_at IS NOT NULL",
                                 (uid,), fetch=True)[0][0]
            ev.step("control granted authorizations", g0)
            if g0:
                raise RuntimeError("control precondition failed: user already verified")

            common.sql_exec(conn,
                "INSERT INTO decidim_authorizations "
                "(decidim_user_id, name, unique_id, granted_at, created_at, updated_at, metadata) "
                "VALUES (%s,'id_documents',%s,now(),now(),now(),'{}')",
                (uid, f"apf-{uid}"))
            ev.step("forge", "INSERT decidim_authorizations granted_at=now() (state-only)")

            g1 = common.sql_exec(conn, "SELECT count(*) FROM decidim_authorizations "
                                       "WHERE decidim_user_id=%s AND granted_at IS NOT NULL",
                                 (uid,), fetch=True)[0][0]
            ev.step("verify granted authorizations", g1)

            if g0 == 0 and g1 >= 1:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only insert granted a verification; the user is now "
                                   "eligible to vote/sign with no verification workflow run")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected: control={g0} after_forge={g1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
