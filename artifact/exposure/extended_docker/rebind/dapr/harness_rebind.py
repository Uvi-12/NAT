#!/usr/bin/env python3
# APF / APF - REBIND live harness: Dapr Workflow (#24).
# The payment re-reads its args from the Dapr state store; the approval event carries only the
# decision. A state writer mutates the state key A->B via /mutate (Dapr state API) while the
# instance awaits approval; the genuine approver's event then pays Blackwell under Priya.
# EXPECTED: EXPOSED.
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
        except requests.RequestException:
            time.sleep(2)
    raise SystemExit("Dapr app not reachable at " + APP)

def start(iid, order): requests.post(f"{APP}/start?id={iid}", json=order, timeout=15)
def mutate(iid, args): requests.post(f"{APP}/mutate?id={iid}", json=args, timeout=15)
def raise_evt(iid, data): requests.post(f"{APP}/raise?id={iid}", json=data, timeout=15)
def wait_status(iid, tries=40):
    for _ in range(tries):
        try:
            r = requests.get(f"{APP}/status?id={iid}", timeout=10).json()
            if "COMPLETED" in (r.get("runtime_status") or ""):
                out = r.get("output")
                return json.loads(out) if isinstance(out, str) else out
        except requests.RequestException:
            pass
        time.sleep(1)
    return None

def main():
    wait_app()
    audit = []
    # control: genuine approval of args A (state seeded A) -> Meridian
    start("apf-A", C.A_ARGS); time.sleep(2)
    raise_evt("apf-A", {"approved": True, "approver": C.APPROVER})
    outA = wait_status("apf-A")
    if outA and outA.get("paid"):
        audit.append({"action": "execute_payment", "amount": outA["amount"], "beneficiary": outA["beneficiary"], "approved_by_in_audit": outA["approver"]})
    C.line("control", f"genuine approval event to run A -> {outA}")
    C.line("audit", "payment re-reads args from the Dapr state store; approval event decision-only, matched by name")
    # rebind: Priya reviews Meridian; state writer mutates the state key A->B; genuine approver's event pays B
    start("apf-R", C.A_ARGS); time.sleep(2)
    mutate("apf-R", C.B_ARGS)                                   # state-writer mutation of the durable arg
    raise_evt("apf-R", {"approved": True, "approver": C.APPROVER})
    outR = wait_status("apf-R")
    rebind_fired = bool(outR and outR.get("paid")) and outR.get("beneficiary") == C.B_ARGS["beneficiary"]
    b_row = {"action": "execute_payment", "amount": outR["amount"], "beneficiary": outR["beneficiary"], "approved_by_in_audit": outR["approver"]} if rebind_fired else None
    C.line("rebind", f"state key mutated A->B before approval -> {outR}")
    nonce = "n-rebind-0024"
    verdict = C.verdict_rebind(rebind_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Dapr Workflow", OUT, {
        "shape": "REBIND",
        "restore_path": "payment re-reads args from the Dapr state store (key args:<id>); approval event matched by name only",
        "execution_tier": "live (real Dapr sidecar + workflow app; state mutated via Dapr state API)",
        "genuine_args": C.A_ARGS, "mutated_args": C.B_ARGS,
        "rebind_fired": rebind_fired, "rebound_payment": b_row,
        "audit_ledger": audit, "verdict": verdict})
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main("Dapr Workflow", OUT, main)
