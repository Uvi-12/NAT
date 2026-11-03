#!/usr/bin/env python3
# APF / APF - REPLAY live harness: n8n (#31)
# Drives the REAL n8n engine. Approval = resuming a paused Wait node; the resume is a
# bearer keyed by execution id and the approval PAYLOAD (approver identity) carries no
# run/nonce binding. Tests whether run A's genuine approval payload, reused to resume run
# B, pays Blackwell under Priya. EXPECTED (hypothesis): EXPOSED. If any version-sensitive
# step cannot be driven, the harness emits INCONCLUSIVE with diagnostics rather than a
# wrong verdict.
import os, sys, time, json
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apf_common as C

OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "31_n8n")
BASE = os.environ.get("N8N_BASE", "http://localhost:5678")
S = requests.Session()
DIAG = {}

WF = {
    "name": "apf_payment",
    "nodes": [
        {"parameters": {"httpMethod": "POST", "path": "apf", "responseMode": "onReceived"},
         "id": "wh", "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [200, 300]},
        {"parameters": {"resume": "webhook", "options": {}},
         "id": "wait", "name": "Wait", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [460, 300]},
        {"parameters": {"assignments": {"assignments": [
            {"id": "a1", "name": "paid", "value": "={{ $json.body.approved }}", "type": "boolean"},
            {"id": "a2", "name": "approver", "value": "={{ $json.body.approver }}", "type": "string"}]}, "options": {}},
         "id": "set", "name": "Record", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [720, 300]},
    ],
    "connections": {
        "Webhook": {"main": [[{"node": "Wait", "type": "main", "index": 0}]]},
        "Wait": {"main": [[{"node": "Record", "type": "main", "index": 0}]]},
    },
    "settings": {},
}

def setup_owner():
    try:
        S.post(f"{BASE}/rest/owner/setup", json={"email": "apf@example.com", "firstName": "A",
               "lastName": "P", "password": "Apf123456!"}, timeout=15)
    except requests.RequestException as e:
        DIAG["owner"] = str(e)

def api_key():
    r = S.post(f"{BASE}/rest/api-keys", json={"label": "apf"}, timeout=15)
    if r.ok:
        j = r.json()
        return (j.get("data") or j).get("apiKey") or (j.get("data") or j).get("rawApiKey")
    DIAG["api_key"] = f"{r.status_code} {r.text[:120]}"
    return None

def import_wf(key):
    h = {"X-N8N-API-KEY": key}
    r = requests.post(f"{BASE}/api/v1/workflows", headers=h, json=WF, timeout=20)
    if not r.ok:
        DIAG["import"] = f"{r.status_code} {r.text[:160]}"; return None
    wid = r.json().get("id")
    ar = requests.post(f"{BASE}/api/v1/workflows/{wid}/activate", headers=h, timeout=15)
    DIAG["activate"] = f"{ar.status_code} active={ar.json().get('active') if ar.ok else '?'}"
    time.sleep(3)   # give n8n a moment to register the production webhook
    return wid

def trigger(order):
    # record the HTTP status so a 404 (inactive/path) or 500 is visible, not just network errors
    try:
        r = requests.post(f"{BASE}/webhook/apf", json=order, timeout=20)
        DIAG.setdefault("trigger", []).append(r.status_code)
        if r.status_code == 404:   # production webhook not live; fall back to the test webhook
            rt = requests.post(f"{BASE}/webhook-test/apf", json=order, timeout=20)
            DIAG.setdefault("trigger_test", []).append(rt.status_code)
    except requests.RequestException as e:
        DIAG.setdefault("trigger", []).append(str(e))

def waiting_exec_id(key, tries=25):
    h = {"X-N8N-API-KEY": key}
    for _ in range(tries):
        r = requests.get(f"{BASE}/api/v1/executions?status=waiting", headers=h, timeout=15)
        if r.ok:
            data = r.json().get("data", [])
            if data:
                return data[0]["id"]
        time.sleep(1)
    # nothing waiting: snapshot whatever executions exist so we can see if the run errored
    try:
        allx = requests.get(f"{BASE}/api/v1/executions?includeData=false&limit=5", headers=h, timeout=15)
        if allx.ok:
            DIAG["executions_seen"] = [
                {"id": e.get("id"), "status": e.get("status"), "finished": e.get("finished")}
                for e in allx.json().get("data", [])]
    except requests.RequestException as e:
        DIAG["executions_seen"] = str(e)
    return None

def resume(exec_id, payload):
    try:
        requests.post(f"{BASE}/webhook-waiting/{exec_id}", json=payload, timeout=15)
    except requests.RequestException as e:
        DIAG.setdefault("resume", []).append(str(e))

def exec_result(key, exec_id):
    h = {"X-N8N-API-KEY": key}
    r = requests.get(f"{BASE}/api/v1/executions/{exec_id}?includeData=true", headers=h, timeout=15)
    if not r.ok:
        return {}
    try:
        run = r.json()["data"]["resultData"]["runData"]
        rec = run.get("Record", [])
        return rec[0]["data"]["main"][0][0]["json"] if rec else {}
    except Exception:
        return {}

def emit(verdict, replay_fired, audit, b_row, extra):
    seen = set(); nonce = "n-runA-0031"
    C.line("verdict", verdict)
    rec = {"restore_path": "approval = resume of a paused Wait node; bearer keyed by execution id, payload approver unbound",
           "execution_tier": "live (real n8n engine)", "diagnostics": DIAG,
           "replay_fired": replay_fired, "replayed_payment": b_row,
           "audit_ledger": audit, "verdict": verdict}
    rec.update(extra)
    print("N8N_DIAG", __import__("json").dumps(DIAG)[:800])
    h = C.emit_evidence("n8n", OUT, rec)
    print("EVIDENCE_HASH16", h)

def main():
    # wait for n8n
    for _ in range(40):
        try:
            if S.get(f"{BASE}/healthz", timeout=5).ok:
                break
        except requests.RequestException:
            time.sleep(2)
    setup_owner()
    key = api_key()
    if not key or not import_wf(key):
        C.line("verdict", "INCONCLUSIVE"); emit("INCONCLUSIVE", False, [], None, {"note": "could not set up n8n API/workflow; see diagnostics"}); return
    audit = []

    # control: genuine approval resumes run A
    trigger(C.A_ARGS)
    eidA = waiting_exec_id(key)
    if not eidA:
        emit("INCONCLUSIVE", False, [], None, {"note": "run A did not reach waiting state"}); return
    resume(eidA, {"approved": True, "approver": C.APPROVER})
    time.sleep(2)
    rA = exec_result(key, eidA)
    if str(rA.get("paid")).lower() == "true":
        audit.append({"action": "execute_payment", "amount": C.A_ARGS["amount"],
                      "beneficiary": C.A_ARGS["beneficiary"], "approved_by_in_audit": rA.get("approver")})
    C.line("control", f"genuine approval resumed run A -> {rA}")

    # replay: run B resumed with run A's approval payload (reused approver identity)
    trigger(C.B_ARGS)
    eidB = waiting_exec_id(key)
    if not eidB:
        emit("INCONCLUSIVE", False, audit, None, {"note": "run B did not reach waiting state"}); return
    resume(eidB, {"approved": True, "approver": C.APPROVER})   # reused approval content
    time.sleep(2)
    rB = exec_result(key, eidB)
    replay_fired = str(rB.get("paid")).lower() == "true" and rB.get("approver") == C.APPROVER
    b_row = {"action": "execute_payment", "amount": C.B_ARGS["amount"],
             "beneficiary": C.B_ARGS["beneficiary"], "approved_by_in_audit": rB.get("approver")} if replay_fired else None
    C.line("audit", "resume is keyed by execution id; approval payload (approver) carries no binding")
    C.line("replay", f"reused run A approval payload resumed run B -> {rB}")
    verdict = C.verdict_from_state(replay_fired, True)
    emit(verdict, replay_fired, audit, b_row, {"result_runA": rA, "result_runB": rB})

if __name__ == "__main__":
    C.guarded_main('n8n', OUT, main)
