#!/usr/bin/env python3
# APF / APF - REPLAY live harness: Dapr Workflow (#24)
# Drives the REAL Dapr workflow app. Approval = an external workflow event matched by NAME
# only, with no run/nonce/args binding. Confirms live that a genuine approval reused for
# run B fires run B's payment under Priya: the event carries no binding, so any party able
# to deliver it authorizes run B. EXPECTED: EXPOSED (replay_fired = True).
# Note: this confirms the no-binding property live. The stronger state-writer variant (a
# state writer copying run A's persisted event into run B's history in the Redis state
# store) is the same weakness reached through the persistence layer.
import os, sys, time, json
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apf_common as C

OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "24_dapr")
APP = os.environ.get("DAPR_APP", "http://localhost:5001")

def wait_app():
    for _ in range(40):
        try:
            requests.post(f"{APP}/start?id=_probe", json={"amount": 0, "beneficiary": "_"}, timeout=5)
            return
        except requests.RequestException:
            time.sleep(2)
    raise SystemExit("Dapr app not reachable at " + APP)

def start(iid, order):
    requests.post(f"{APP}/start?id={iid}", json=order, timeout=15)

def raise_evt(iid, data):
    requests.post(f"{APP}/raise?id={iid}", json=data, timeout=15)

def wait_status(iid, tries=40):
    for _ in range(tries):
        r = requests.get(f"{APP}/status?id={iid}", timeout=10).json()
        if "COMPLETED" in (r.get("runtime_status") or ""):
            out = r.get("output")
            try:
                return json.loads(out) if isinstance(out, str) else out
            except Exception:
                return out
        time.sleep(1)
    return None

def main():
    wait_app()
    audit = []
    # ---- control: genuine approval event to run A ----
    start("apf-A", C.A_ARGS)
    time.sleep(2)
    raise_evt("apf-A", {"approved": True, "approver": C.APPROVER})
    outA = wait_status("apf-A")
    if outA and outA.get("paid"):
        audit.append({"action": "execute_payment", "amount": outA["amount"],
                      "beneficiary": outA["beneficiary"], "approved_by_in_audit": outA["approver"]})
    C.line("control", f"genuine approval event to run A -> {outA}")

    genuine = {"approved": True, "approver": C.APPROVER}
    C.line("audit", f"approval event matched by NAME only; no run/nonce binding: {genuine}")

    # ---- replay: reuse run A's approval content, delivered to run B ----
    start("apf-B", C.B_ARGS)
    time.sleep(2)
    raise_evt("apf-B", dict(genuine))   # reused approver identity, unbound
    outB = wait_status("apf-B")
    replay_fired = bool(outB and outB.get("paid")) and outB.get("beneficiary") == C.B_ARGS["beneficiary"]
    b_row = None
    if replay_fired:
        b_row = {"action": "execute_payment", "amount": outB["amount"],
                 "beneficiary": outB["beneficiary"], "approved_by_in_audit": outB["approver"]}
    C.line("replay", f"reused run A approval delivered to run B -> {outB}")

    seen = set(); nonce = "n-runA-0024"

    verdict = C.verdict_from_state(replay_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Dapr Workflow", OUT, {
        "restore_path": "approval = external workflow event matched by name only; no run/nonce/args binding",
        "execution_tier": "live (real Dapr sidecar + workflow app)",
        "genuine_run": "apf-A", "replay_run": "apf-B",
        "replay_fired": replay_fired, "replayed_payment": b_row,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main('Dapr Workflow', OUT, main)
