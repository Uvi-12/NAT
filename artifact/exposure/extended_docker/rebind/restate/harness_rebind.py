#!/usr/bin/env python3
# APF / APF - REBIND live harness: Restate (#27).
# The invocation input (order) is recorded in Restate's engine-owned, append-only journal; the
# approval is a durable awakeable resolution. A state writer has no API to alter the recorded
# invocation input, and the awakeable payload is decision-only, so the mutated argument cannot
# run under the one approval. EXPECTED: RESISTANT.
import os, sys, time, json
import requests
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import apf_common as C
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "27_restate")
INGRESS = os.environ.get("RESTATE_INGRESS", "http://localhost:8080")
ADMIN = os.environ.get("RESTATE_ADMIN", "http://localhost:9070")
SERVICE_URI = os.environ.get("RESTATE_SERVICE_URI", "http://host.docker.internal:9080")
DIAG = {}

def register_deployment():
    try:
        r = requests.post(f"{ADMIN}/deployments", json={"uri": SERVICE_URI, "use_http_11": True, "force": True}, timeout=20)
        DIAG["register"] = {"status": r.status_code, "body": r.text[:200]}
    except requests.RequestException as e:
        DIAG["register"] = {"error": str(e)}

def start(key, order):
    try:
        requests.post(f"{INGRESS}/payment/{key}/request/send", json=order, timeout=20)
    except requests.RequestException as e:
        DIAG.setdefault("start", {})[key] = str(e)

def get_awk(key, tries=40):
    for _ in range(tries):
        try:
            r = requests.post(f"{INGRESS}/payment/{key}/get_awk", json=None, timeout=15)
            if r.ok and r.json():
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(1)
    return None

def resolve(awk_id, payload):
    try:
        return requests.post(f"{INGRESS}/restate/awakeables/{awk_id}/resolve", json=payload, timeout=15).status_code
    except requests.RequestException as e:
        return str(e)

def get_result(key):
    try:
        r = requests.post(f"{INGRESS}/payment/{key}/get_result", json=None, timeout=15)
        return r.json() if r.ok else {}
    except requests.RequestException:
        return {}

def emit(verdict, rebind_fired, audit, b_row, awkA, awkR, resA, resR):
    nonce = "n-rebind-0027"
    C.line("verdict", verdict)
    h = C.emit_evidence("Restate", OUT, {
        "shape": "REBIND",
        "restore_path": "invocation input in engine-owned append-only journal; awakeable decision-only; no state-writer arg mutation path",
        "execution_tier": "live (real Restate server; awakeable resolved via ingress)",
        "genuine_args": C.A_ARGS, "mutated_args": C.B_ARGS,
        "genuine_run_awk": awkA, "rebind_run_awk": awkR,
        "control_paid_runA": bool(resA.get("paid")), "result_rebind": resR or None,
        "rebind_fired": rebind_fired, "rebound_payment": b_row,
        "audit_ledger": audit, "diagnostics": DIAG, "verdict": verdict})
    print("EVIDENCE_HASH16", h)

def main():
    register_deployment()
    audit = []
    # control: genuine approval of args A
    start("A", C.A_ARGS)
    awkA = get_awk("A")
    if awkA:
        resolve(awkA, {"approved": True, "approver": C.APPROVER}); time.sleep(2)
    resA = get_result("A")
    if resA.get("paid"):
        audit.append({"action": "execute_payment", "amount": resA["amount"], "beneficiary": resA["beneficiary"], "approved_by_in_audit": resA["approver"]})
    C.line("control", f"genuine approval resolved run A awakeable {awkA} -> {resA}")
    if not resA.get("paid"):
        emit("INCONCLUSIVE", False, audit, None, awkA, None, resA, {}); return
    C.line("audit", "invocation input frozen in journal; awakeable payload decision-only (cannot carry args)")
    # rebind: Priya reviews Meridian; a state writer resolves the awakeable with B args - service ignores them
    start("R", C.A_ARGS)
    awkR = get_awk("R")
    if awkR:
        resolve(awkR, {"approved": True, "approver": C.APPROVER, "amount": C.B_ARGS["amount"], "beneficiary": C.B_ARGS["beneficiary"]})
        time.sleep(2)
    resR = get_result("R")
    rebind_fired = bool(resR.get("paid")) and resR.get("beneficiary") == C.B_ARGS["beneficiary"]
    b_row = {"action": "execute_payment", "amount": resR.get("amount"), "beneficiary": resR.get("beneficiary"), "approved_by_in_audit": resR.get("approver")} if rebind_fired else None
    C.line("rebind", f"awakeable resolved with B args + frozen journal input -> {resR}")
    emit(C.verdict_rebind(rebind_fired, True), rebind_fired, audit, b_row, awkA, awkR, resA, resR)

if __name__ == "__main__":
    C.guarded_main("Restate", OUT, main)
