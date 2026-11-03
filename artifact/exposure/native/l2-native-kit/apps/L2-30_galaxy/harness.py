#!/usr/bin/env python3
"""L2-30 Galaxy, native APF reproduction (EXPOSED).

Decisive surface (corpus): a `published`/`importable` boolean on a history (or
dataset/workflow) makes it world-importable. The authorized path is the share/
publish action (permission-checked). The APF forge is a state-only write of that
persisted boolean, after which Galaxy treats the history as published.

Steps:
  1. bring up the real Galaxy image against an external PostgreSQL,
  2. create a user + a private history through Galaxy's own API,
  3. CONTROL: the history is not published,
  4. FORGE: `UPDATE history SET published=true, importable=true` directly in PG,
  5. VERIFY: Galaxy's API now reports the history as published,
  6. EXPOSED (or INCONCLUSIVE + reason).
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-30"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
BASE = "http://127.0.0.1:8030"
MASTER = "apf-master-key"


def api(method, path, key, body=None):
    url = f"{BASE}{path}{'&' if '?' in path else '?'}key={key}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Galaxy", expected_verdict=common.EXPOSED,
        version="galaxy/galaxy:23.1",
        decisive_surface="history.published/importable boolean -> world-importable")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5430, timeout=300, ev=ev)
            common.wait_http(f"{BASE}/api/version", timeout=1800, ev=ev)

            # create a user with the master key, then an API key for it
            user = api("POST", "/api/users", MASTER,
                       {"username": "apfuser", "email": "apfuser@example.com",
                        "password": "apf-passw0rd"})
            uid = user["id"]
            keyinfo = api("POST", f"/api/users/{uid}/api_key", MASTER)
            ukey = keyinfo if isinstance(keyinfo, str) else keyinfo.get("api_key", keyinfo)
            hist = api("POST", "/api/histories", ukey, {"name": "APF private history"})
            hid = hist["id"]
            ev.step("seeded history", f"id={hid}")

            h0 = api("GET", f"/api/histories/{hid}", ukey)
            ev.step("control published", h0.get("published"))
            if h0.get("published"):
                raise RuntimeError("control precondition failed: history already published")

            # --- forge: state-only write of the published/importable flags ---
            conn = common.pg(host="127.0.0.1", port=5430, dbname="galaxy",
                             user="galaxy", password="galaxy")
            # history.id in the API is encoded; match on the stored slug/name instead
            common.sql_exec(conn,
                "UPDATE history SET published=true, importable=true WHERE name=%s",
                ("APF private history",))
            ev.step("forge", "UPDATE history SET published=true, importable=true")

            h1 = api("GET", f"/api/histories/{hid}", ukey)
            ev.step("verify published", h1.get("published"))
            if not h0.get("published") and h1.get("published"):
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write published the history; share/publish "
                                   "permission check bypassed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"published flag not reflected (control={h0.get('published')} after={h1.get('published')})"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
