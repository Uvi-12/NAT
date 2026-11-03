#!/usr/bin/env python3
"""L2-21 OpenHIM, native APF reproduction (EXPOSED).

Decisive surface: OpenHIM Core persists each interoperability transaction in
MongoDB with a `status` field (Processing / Successful / Completed / Failed).
Downstream routing, re-run and reporting trust that persisted status. The APF
forge is a state-only write of a transaction's `status` to a success value,
without the transaction actually having completed through the authorized path.

Steps: bring up OpenHIM Core + MongoDB; seed a transaction document in
`Processing`; CONTROL confirms it is not a success state; FORGE sets
`status = 'Successful'` directly in MongoDB; VERIFY re-reads it. Honest:
INCONCLUSIVE + reason on any failure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-21"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
URI = "mongodb://127.0.0.1:27017"


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="OpenHIM", expected_verdict=common.EXPOSED,
        version="jembi/openhim-core:v8.4.0",
        decisive_surface="transactions.status == 'Successful' trusted by routing")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=1800):
            common.wait_tcp("127.0.0.1", 27017, timeout=300, ev=ev)
            # let core create the openhim database/collections on first boot
            common.wait_http("http://127.0.0.1:8080/heartbeat", timeout=600,
                             ok=range(200, 500), ev=ev)
            cli = common.mongo(URI)
            db = cli["openhim"]

            # --- seed: a transaction in a non-success state ---
            import datetime
            res = db["transactions"].insert_one({
                "clientID": None,
                "status": "Processing",
                "request": {"path": "/apf/claim", "method": "POST",
                            "timestamp": datetime.datetime.utcnow()},
                "response": {"status": 202},
                "apf_synthetic": True,
            })
            tid = res.inserted_id
            status0 = db["transactions"].find_one({"_id": tid})["status"]
            ev.step("seeded transaction", f"_id={tid} status={status0}")
            if status0 == "Successful":
                raise RuntimeError("control precondition failed: already Successful")

            # --- forge: state-only status write ---
            db["transactions"].update_one({"_id": tid},
                                          {"$set": {"status": "Successful"}})
            ev.step("forge", "transactions.status := 'Successful'")

            # --- verify ---
            status1 = db["transactions"].find_one({"_id": tid})["status"]
            ev.step("verify status", status1)
            if status0 != "Successful" and status1 == "Successful":
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only write marked the transaction Successful; "
                                   "downstream routing/reporting trusts the persisted status")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected status: control={status0} forge={status1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
