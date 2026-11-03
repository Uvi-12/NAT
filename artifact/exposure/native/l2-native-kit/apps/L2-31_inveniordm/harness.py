#!/usr/bin/env python3
"""L2-31 InvenioRDM, native APF reproduction (EXPOSED).

Decisive surface (corpus): a record becomes world-readable when
`access.protection.record == 'public'`. The authorized path is publish / an access
change (permission-checked). The APF forge is a state-only write of that value in
the record's persisted JSONB metadata.

Steps: bring up InvenioRDM (+PostgreSQL+OpenSearch+Redis+RabbitMQ); create a
restricted draft/record via the REST API; CONTROL access.record='restricted';
FORGE the JSONB `access.record` to 'public' directly in PostgreSQL; VERIFY the
record metadata now reports public access.

Confidence low: a production InvenioRDM image is instance-built (set
APF_INVENIO_IMAGE); the forge on the documented JSONB field is concrete, and the
harness records INCONCLUSIVE if the stack/API can't be reached.
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-31"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
BASE = "https://127.0.0.1:5031"
TOKEN = "apf-dev-token"


def api(method, path, body=None):
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        BASE + path, data=(json.dumps(body).encode() if body is not None else None),
        method=method, headers={"Authorization": f"Bearer {TOKEN}",
                                "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        return json.loads(r.read() or b"{}")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="InvenioRDM", expected_verdict=common.EXPOSED,
        version="inveniordm (instance image)",
        decisive_surface="access.protection.record == 'public'")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=3000):
            common.wait_tcp("127.0.0.1", 5431, timeout=300, ev=ev)
            common.wait_http(f"{BASE}/api", timeout=2400, ev=ev)

            rec = api("POST", "/api/records", {
                "access": {"record": "restricted", "files": "restricted"},
                "files": {"enabled": False},
                "metadata": {"title": "APF Record", "resource_type": {"id": "dataset"},
                             "creators": [{"person_or_org": {"name": "APF, Test",
                                           "type": "personal"}}],
                             "publication_date": "2027-01-01"}})
            rid = rec.get("id")
            ev.step("seeded record", f"id={rid}")

            conn = common.pg(host="127.0.0.1", port=5431, dbname="inveniordm",
                             user="inveniordm", password="inveniordm")
            state0 = common.sql_exec(conn,
                "SELECT json->'access'->>'record' FROM rdm_records_metadata "
                "ORDER BY created DESC LIMIT 1", fetch=True)[0][0]
            ev.step("control access.record", state0)
            if state0 == "public":
                raise RuntimeError("control precondition failed: record already public")

            # --- forge: state-only JSONB write ---
            common.sql_exec(conn,
                "UPDATE rdm_records_metadata SET json = jsonb_set(json, '{access,record}', '\"public\"') "
                "WHERE id=(SELECT id FROM rdm_records_metadata ORDER BY created DESC LIMIT 1)")
            ev.step("forge", "jsonb_set(access.record -> 'public')")
            state1 = common.sql_exec(conn,
                "SELECT json->'access'->>'record' FROM rdm_records_metadata "
                "ORDER BY created DESC LIMIT 1", fetch=True)[0][0]
            ev.step("verify access.record", state1)

            if state0 != "public" and state1 == "public":
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only JSONB write made the restricted record public; "
                                   "access-change permission bypassed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"access.record not public (control={state0} after={state1})"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
