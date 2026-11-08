#!/usr/bin/env python3
"""L2-10 OpenSign, native APF reproduction (EXPOSED).

Decisive surface (corpus): a document is treated as fully executed when its
persisted `contracts_Document.IsCompleted` boolean is true; OpenSign then generates
and serves the completion certificate. That stored boolean is trusted, the
completion is not re-derived from the per-signer signatures.

Forge: a state-only write setting `IsCompleted = true` on a pending document in
MongoDB (OpenSign's Parse Server backend), with no signing ceremony. The harness
seeds a minimal pending document in the real `contracts_Document` collection,
captures the blocked control (IsCompleted != true), forges the boolean, and
verifies the stored document now reports completion. Targets OpenSign main.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-10"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
MONGO_URI = "mongodb://127.0.0.1:27017"
DBN = "OpenSignDB"
COLL = "contracts_Document"


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="OpenSign", expected_verdict=common.EXPOSED,
        version="opensign main",
        decisive_surface="contracts_Document.IsCompleted == true")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=1800):
            common.wait_tcp("127.0.0.1", 27017, timeout=300, ev=ev)
            # Parse Server creates the DB/collections on first boot; wait for it.
            common.wait_http("http://127.0.0.1:8080/app/health", timeout=1200,
                             ok=range(200, 500), ev=ev)

            client = common.mongo(MONGO_URI)
            coll = client[DBN][COLL]

            # --- seed: a pending document ---
            import datetime
            res = coll.insert_one({
                "Name": "APF Agreement",
                "IsCompleted": False,
                "createdAt": datetime.datetime.utcnow(),
                "updatedAt": datetime.datetime.utcnow(),
            })
            did = res.inserted_id
            ev.step("seeded document", f"_id={did} IsCompleted=false")

            c0 = coll.find_one({"_id": did}).get("IsCompleted")
            ev.step("control IsCompleted", c0)
            if c0 is True:
                raise RuntimeError("control precondition failed: already completed")

            # --- forge: state-only boolean write ---
            coll.update_one({"_id": did},
                            {"$set": {"IsCompleted": True,
                                      "updatedAt": datetime.datetime.utcnow()}})
            ev.step("forge", "contracts_Document.updateOne({_id},{IsCompleted:true})")

            c1 = coll.find_one({"_id": did}).get("IsCompleted")
            ev.step("verify IsCompleted", c1)

            if c0 is not True and c1 is True:
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only IsCompleted write marks the document "
                                   "executed with no signing ceremony; OpenSign serves "
                                   "the completion certificate")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected IsCompleted: control={c0} after_forge={c1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
