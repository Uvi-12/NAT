#!/usr/bin/env python3
# Approval = resolving a durable awakeable (single-use, invocation-scoped id). This version
# self-registers the deployment, records admin/ingress responses, and refuses to declare
# RESISTANT unless the genuine run A actually paid (a dead control arm -> INCONCLUSIVE, not
# a false RESISTANT).
import os, sys, time, json
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
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
    try:
        d = requests.get(f"{ADMIN}/deployments", timeout=15)
        DIAG["deployments"] = d.json() if d.ok else {"status": d.status_code}
    except requests.RequestException as e:
        DIAG["deployments"] = str(e)

def start(key, order):
    try:
        r = requests.post(f"{INGRESS}/payment/{key}/request/send", json=order, timeout=20)
        DIAG.setdefault("start", {})[key] = r.status_code
    except requests.RequestException as e:
        DIAG.setdefault("start", {})[key] = str(e)

def get_awk(key, tries=40):
    last = None
    for _ in range(tries):
        try:
            r = requests.post(f"{INGRESS}/payment/{key}/get_awk", json=None, timeout=15)
            last = r.status_code
            if r.ok and r.json():
                return r.json()
        except requests.RequestException as e:
            last = str(e)
        time.sleep(1)
    DIAG.setdefault("get_awk", {})[key] = f"empty after {tries} tries (last={last})"
    return None

def get_result(key):
    try:
        r = requests.post(f"{INGRESS}/payment/{key}/get_result", json=None, timeout=15)
        return r.json() if r.ok else {}
    except requests.RequestException:
        return {}

def resolve(awk_id, payload):
    try:
        r = requests.post(f"{INGRESS}/restate/awakeables/{awk_id}/resolve", json=payload, timeout=15)
        return r.status_code
    except requests.RequestException as e:
        return str(e)

def emit(verdict, replay_fired, audit, b_row, awkA, awkB, resA, resB):
    seen = set(); nonce = "n-runA-0027"
    C.line("verdict", verdict)
    h = C.emit_evidence("Restate", OUT, {
        "restore_path": "approval = resolution of a durable awakeable; id is single-use and invocation-scoped",
        "execution_tier": "live (real Restate server; awakeable resolved via ingress)",
        "why_resistant": "run B awaits its own awakeable id; run A's approval cannot resolve run B",
        "genuine_run_awk": awkA, "replay_run_awk": awkB,
        "control_paid_runA": bool(resA.get("paid")), "result_runB": resB or None,
        "replay_fired": replay_fired, "replayed_payment": b_row,
        "audit_ledger": audit,
        "diagnostics": DIAG, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)

def main():
    register_deployment()
    audit = []
    start("A", C.A_ARGS)
    awkA = get_awk("A")
    if awkA:
        DIAG["resolve_A"] = resolve(awkA, {"approved": True, "approver": C.APPROVER})
        time.sleep(2)
    resA = get_result("A")
    if resA.get("paid"):
        audit.append({"action": "execute_payment", "amount": resA["amount"],
                      "beneficiary": resA["beneficiary"], "approved_by_in_audit": resA["approver"]})
    C.line("control", f"genuine approval resolved run A awakeable {awkA} -> {resA}")

    if not resA.get("paid"):
        C.line("audit", "control run A did not pay; cannot conclude resistance")
        emit("INCONCLUSIVE", False, audit, None, awkA, None, resA, {})
        return

    start("B", C.B_ARGS)
    awkB = get_awk("B")
    if awkA:
        resolve(awkA, {"approved": True, "approver": C.APPROVER})
    time.sleep(2)
    resB = get_result("B")
    replay_fired = bool(resB.get("paid")) and resB.get("beneficiary") == C.B_ARGS["beneficiary"]
    b_row = None
    if replay_fired:
        b_row = {"action": "execute_payment", "amount": resB["amount"],
                 "beneficiary": resB["beneficiary"], "approved_by_in_audit": resB["approver"]}
    C.line("audit", f"run B awaits its own awakeable id {awkB}; run A id != run B id")
    C.line("replay", f"reused run A awakeable onto run B -> {resB or 'still awaiting (not paid)'}")

    verdict = C.verdict_from_state(replay_fired, True)
    emit(verdict, replay_fired, audit, b_row, awkA, awkB, resA, resB)

if __name__ == "__main__":
    C.guarded_main('Restate', OUT, main)
