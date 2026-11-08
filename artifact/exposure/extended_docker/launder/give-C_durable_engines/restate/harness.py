#!/usr/bin/env python3
# APF / APF - SUPPRESS live harness: Restate (#27).
# The payment awaits a per-invocation awakeable; a resolution is recorded in Restate's engine-owned
# append-only journal. There is no in-scope API to advance the invocation without a recorded
# resolution, and any resolution leaves evidence (FORGE, a different shape). So the payment cannot
# run with the approval-required record ABSENT. EXPECTED: RESISTANT (suppress_fired=False).
import os, sys, time
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
    try: requests.post(f"{INGRESS}/payment/{key}/request/send", json=order, timeout=20)
    except requests.RequestException as e: DIAG.setdefault("start", {})[key] = str(e)
def get_awk(key, tries=40):
    for _ in range(tries):
        try:
            r = requests.post(f"{INGRESS}/payment/{key}/get_awk", json=None, timeout=15)
            if r.ok and r.json(): return r.json()
        except requests.RequestException: pass
        time.sleep(1)
    return None
def resolve(awk_id, payload):
    try: return requests.post(f"{INGRESS}/restate/awakeables/{awk_id}/resolve", json=payload, timeout=15).status_code
    except requests.RequestException as e: return str(e)
def get_result(key):
    try:
        r = requests.post(f"{INGRESS}/payment/{key}/get_result", json=None, timeout=15)
        return r.json() if r.ok else {}
    except requests.RequestException: return {}

def main():
    register_deployment()
    audit = []
    # control: genuine approval resolves the awakeable -> paid
    start("A-s", C.A_ARGS); awkA = get_awk("A-s")
    if awkA: resolve(awkA, {"approved": True, "approver": C.APPROVER}); time.sleep(2)
    resA = get_result("A-s")
    if resA.get("paid"):
        audit.append({"action": "execute_payment", "amount": resA["amount"], "beneficiary": resA["beneficiary"], "approved_by_in_audit": resA["approver"]})
    C.line("control", f"genuine approval resolved run A awakeable {awkA} -> {resA}")
    C.line("audit", "the gate is a per-invocation awakeable; the only advance path is a resolution recorded in the append-only journal")
    # launder: a foreign Blackwell invocation (args B) has its OWN awakeable and no resolution; the
    # Meridian resolution was recorded in run A's journal, keyed to it, and cannot be inherited.
    start("L-l", C.B_ARGS); awkL = get_awk("L-l"); time.sleep(3)
    resL = get_result("L-l")
    launder_fired = bool(resL.get("paid"))
    C.line("launder", f"foreign awakeable {awkL} has no resolution of its own; run A's resolution cannot be inherited; foreign paid? {launder_fired} (result={resL})")
    verdict = C.verdict_launder(launder_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Restate", OUT, {
        "shape": "LAUNDER",
        "restore_path": "every resolution is recorded in its invocation's append-only journal against a per-invocation awakeable; a foreign invocation cannot inherit another invocation's resolution",
        "execution_tier": "live (real Restate server; awakeable via ingress)",
        "why_resistant": "an awakeable resolution is bound to the invocation it was issued for; no cross-invocation re-parent path, so a foreign invocation has no resolution of its own",
        "genuine_run_awk": awkA, "foreign_run_awk": awkL, "result_foreign": resL or None,
        "approval_issued_for": C.A_ARGS, "foreign_action": C.B_ARGS,
        "launder_fired": launder_fired, "laundered_payment": None,
        "audit_ledger": audit, "diagnostics": DIAG, "verdict": verdict})
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main("Restate", OUT, main)
