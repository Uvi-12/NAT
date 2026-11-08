#!/usr/bin/env python3
# APF / APF - SUPPRESS live harness: Dapr Workflow (#24).
# The approval is an external event matched by NAME with no reviewer authentication, and the
# instance state is a mutable Dapr state-store value (no forced immutable approval record). An
# in-scope actor raises the approval event with no reviewer, so the payment runs unapproved and
# the audit shows no approver. EXPECTED: EXPOSED.
import os, sys, time, json
import requests
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import apf_common as C
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "24_dapr")
APP = os.environ.get("DAPR_APP", "http://localhost:5001")

def wait_app():
    for _ in range(40):
        try:
            requests.post(f"{APP}/start?id=_probe", json={"amount": 0, "beneficiary": "_"}, timeout=5); return
        except requests.RequestException: time.sleep(2)
    raise SystemExit("Dapr app not reachable at " + APP)
def start(iid, order): requests.post(f"{APP}/start?id={iid}", json=order, timeout=15)
def raise_evt(iid, data): requests.post(f"{APP}/raise?id={iid}", json=data, timeout=15)
def wait_status(iid, tries=40):
    for _ in range(tries):
        try:
            r = requests.get(f"{APP}/status?id={iid}", timeout=10).json()
            if "COMPLETED" in (r.get("runtime_status") or ""):
                out = r.get("output"); return json.loads(out) if isinstance(out, str) else out
        except requests.RequestException: pass
        time.sleep(1)
    return None

def main():
    wait_app()
    audit = []
    # control: genuine approval event -> paid
    start("apf-A-s", C.A_ARGS); time.sleep(2)
    raise_evt("apf-A-s", {"approved": True, "approver": C.APPROVER})
    outA = wait_status("apf-A-s")
    if outA and outA.get("paid"):
        audit.append({"action": "execute_payment", "amount": outA["amount"], "beneficiary": outA["beneficiary"], "approved_by_in_audit": outA["approver"]})
    C.line("control", f"genuine approval event to run A -> {outA}")
    C.line("audit", "the approval external event is matched by name with no reviewer authentication; the instance state is a mutable state-store value")
    # launder: a foreign Blackwell instance (args B) is raised with Priya's genuine Meridian approval;
    # the external event carries the approver but not the args, so the Meridian approval covers Blackwell.
    start("apf-L-l", C.B_ARGS); time.sleep(2)
    raise_evt("apf-L-l", {"approved": True, "approver": C.APPROVER})   # Priya's (Meridian) approval reused
    outL = wait_status("apf-L-l")
    launder_fired = bool(outL and outL.get("paid")) and (outL.get("beneficiary") == C.B_ARGS["beneficiary"]) and (outL.get("approver") == C.APPROVER)
    l_row = {"action": "execute_payment", "amount": outL["amount"], "beneficiary": outL["beneficiary"], "approved_by_in_audit": outL.get("approver"), "approval_issued_for": C.A_ARGS["beneficiary"]} if launder_fired else None
    C.line("launder", f"foreign Blackwell instance re-parented onto {C.APPROVER}'s Meridian approval -> {outL}")
    verdict = C.verdict_launder(launder_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Dapr Workflow", OUT, {
        "shape": "LAUNDER",
        "restore_path": "the instance approval is a mutable Dapr state-store value not bound to the args; a foreign Blackwell instance re-parents onto Priya's genuine Meridian approval",
        "execution_tier": "live (real Dapr sidecar + workflow app)",
        "caveat": "EXPOSED contingent on state-store trust",
        "approval_issued_for": C.A_ARGS, "foreign_action": C.B_ARGS,
        "launder_fired": launder_fired, "laundered_payment": l_row,
        "audit_ledger": audit, "verdict": verdict})
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main("Dapr Workflow", OUT, main)
