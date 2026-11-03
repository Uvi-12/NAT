#!/usr/bin/env python3
"""L2-05 Your Priorities, native APF reproduction (EXPOSED).

Decisive surface (corpus): an idea (post) is shown as officially accepted /
completed when `posts.official_status` is set to an accepted value (2 = successful
in Your Priorities' encoding). The authorized path is an admin setting the
official status; the APF forge is a state-only write of that persisted column.

Steps: bring up the real Your Priorities image + PostgreSQL; seed (or reuse) a
post with official_status = 0 (none); CONTROL that it is not accepted; FORGE
`UPDATE posts SET official_status = 2`; VERIFY the post is now officially accepted.
EXPOSED, or INCONCLUSIVE + reason on any failure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-05"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
PG = dict(host="127.0.0.1", port=5432, dbname="yrpri_production",
          user="yrpri", password="yrpri")
ACCEPTED = 2  # Your Priorities official_status: 0 none, 1 inProgress, 2 successful, 3 failed


def pick_post(conn):
    rows = common.sql_exec(conn, "SELECT id, official_status FROM posts ORDER BY id LIMIT 1",
                           fetch=True)
    if rows:
        return rows[0][0]
    # create a minimal post if an app-seeded one is absent
    grp = common.sql_exec(conn, "SELECT id FROM groups ORDER BY id LIMIT 1", fetch=True)
    if not grp:
        raise RuntimeError("no groups present to attach a post (app seed did not run)")
    gid = grp[0][0]
    pid = common.sql_exec(conn,
        "INSERT INTO posts (name, description, group_id, official_status, counter_endorsements_up, "
        " created_at, updated_at) VALUES ('APF Idea','APF test idea',%s,0,0,now(),now()) "
        "RETURNING id", (gid,), fetch=True)[0][0]
    return pid


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Your Priorities", expected_verdict=common.EXPOSED,
        version="openactivtech/yourpriorities:latest",
        decisive_surface="posts.official_status == 2 (successful)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            common.wait_http("http://127.0.0.1:4242/", timeout=1800, ev=ev)

            conn = common.pg(**PG)
            pid = pick_post(conn)
            common.sql_exec(conn, "UPDATE posts SET official_status=0 WHERE id=%s", (pid,))
            s0 = common.sql_exec(conn, "SELECT official_status FROM posts WHERE id=%s",
                                 (pid,), fetch=True)[0][0]
            ev.step("control official_status", s0)
            if s0 == ACCEPTED:
                raise RuntimeError("control precondition failed: post already accepted")

            common.sql_exec(conn, "UPDATE posts SET official_status=%s WHERE id=%s", (ACCEPTED, pid))
            ev.step("forge", f"UPDATE posts SET official_status={ACCEPTED} WHERE id={pid}")

            s1 = common.sql_exec(conn, "SELECT official_status FROM posts WHERE id=%s",
                                 (pid,), fetch=True)[0][0]
            ev.step("verify official_status", s1)

            if s0 != ACCEPTED and s1 == ACCEPTED:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write set the official status to accepted; the "
                                   "idea is shown as officially successful with no admin action")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected: control={s0} after_forge={s1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
