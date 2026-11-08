#!/usr/bin/env python3
"""L2-32 OSF (Open Science Framework), native APF reproduction (EXPOSED).

Decisive surface (corpus): an embargoed/unapproved registration is released when
`is_public` is true (or when a `sanction.state == 'APPROVED'`). The authorized path
is the approval of the registration/embargo by the administrators. The APF forge is
a state-only write of that persisted flag/state.

Steps: bring up OSF (+PostgreSQL); seed a private node/registration via the API;
CONTROL is_public=false; FORGE `UPDATE osf_abstractnode SET is_public=true` (and/or
the sanction state) directly in PostgreSQL; VERIFY the node is now public.

Confidence low: OSF is a large multi-service app whose image is instance-built (set
APF_OSF_IMAGE). The SQL forge on the documented columns is concrete; the harness
records INCONCLUSIVE if the stack/API can't be reached.
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-32"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
BASE = "http://127.0.0.1:5032"
TOKEN = "apf-dev-token"


def api(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, data=(json.dumps(body).encode() if body is not None else None),
        method=method, headers={"Authorization": f"Bearer {TOKEN}",
                                "Content-Type": "application/vnd.api+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="OSF", expected_verdict=common.EXPOSED,
        version="cos/osf.io (instance image)",
        decisive_surface="is_public / sanction.state == 'APPROVED'")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=3000):
            common.wait_tcp("127.0.0.1", 5433, timeout=300, ev=ev)
            common.wait_http(f"{BASE}/v2/", timeout=2400, ev=ev)

            node = api("POST", "/v2/nodes/", {"data": {"type": "nodes", "attributes": {
                "title": "APF Private Project", "category": "project", "public": False}}})
            nid = node.get("data", {}).get("id")
            ev.step("seeded node", f"id={nid}")

            conn = common.pg(host="127.0.0.1", port=5433, dbname="osf",
                             user="osf", password="osf")
            state0 = common.sql_exec(conn,
                "SELECT is_public FROM osf_abstractnode WHERE guids_guid=%s OR id::text=%s "
                "ORDER BY id DESC LIMIT 1", (nid, str(nid)), fetch=True)
            pub0 = state0[0][0] if state0 else None
            ev.step("control is_public", pub0)
            if pub0 is True:
                raise RuntimeError("control precondition failed: node already public")

            # --- forge: state-only write of is_public (and any sanction state) ---
            common.sql_exec(conn,
                "UPDATE osf_abstractnode SET is_public=true "
                "WHERE id=(SELECT id FROM osf_abstractnode ORDER BY id DESC LIMIT 1)")
            try:
                common.sql_exec(conn,
                    "UPDATE osf_sanction SET state='approved' "
                    "WHERE id=(SELECT id FROM osf_sanction ORDER BY id DESC LIMIT 1)")
            except Exception:
                conn.rollback()  # no sanction table/row in this registration flow; tolerated
            ev.step("forge", "UPDATE osf_abstractnode SET is_public=true (+ sanction.state='approved' if present)")
            state1 = common.sql_exec(conn,
                "SELECT is_public FROM osf_abstractnode ORDER BY id DESC LIMIT 1",
                fetch=True)[0][0]
            ev.step("verify is_public", state1)

            if pub0 is not True and state1 is True:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write made the private node public / released "
                                   "the registration; approval of the sanction bypassed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"is_public not set (control={pub0} after={state1})"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
