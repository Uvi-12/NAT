#!/usr/bin/env python3
# APF / APF - REBIND live harness: n8n (#31)  [best-effort; least-certain live case]
# Drives the REAL n8n engine. The payment reads amount/beneficiary from an external HTTP source
# (a harness-controlled sink = a mutable store the payment re-reads), then a Wait node gates on
# a human approval (resume). A state writer mutates the sink A->B while the run is paused; the
# genuine approver resumes, the payment re-fetches the mutated args and pays Blackwell under
# Priya. EXPECTED: EXPOSED. If any version-sensitive step cannot be driven, the harness emits
# INCONCLUSIVE with diagnostics rather than a wrong verdict (n8n live was INCONCLUSIVE in REPLAY).
import os, sys, time, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import apf_common as C
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "31_n8n")
BASE = os.environ.get("N8N_BASE", "http://localhost:5678")
SINK_PORT = int(os.environ.get("APF_SINK_PORT", "8799"))
SINK_HOST_FOR_N8N = os.environ.get("APF_SINK_HOST", "host.docker.internal")
S = requests.Session()
DIAG = {}
CURRENT_ARGS = dict(C.A_ARGS)   # the mutable store the payment re-reads

class SinkHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        body = json.dumps(CURRENT_ARGS).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

def start_sink():
    srv = HTTPServer(("0.0.0.0", SINK_PORT), SinkHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

SINK_URL = f"http://{SINK_HOST_FOR_N8N}:{SINK_PORT}/args"
WF = {
    "name": "apf_payment_rebind",
    "nodes": [
        {"parameters": {"httpMethod": "POST", "path": "apf", "responseMode": "onReceived"},
         "id": "wh", "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [200, 300]},
        {"parameters": {"resume": "webhook", "options": {}},
         "id": "wait", "name": "Wait", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [420, 300]},
        {"parameters": {"url": SINK_URL, "options": {}},
         "id": "http", "name": "FetchArgs", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [640, 300]},
        {"parameters": {"assignments": {"assignments": [
            {"id": "a1", "name": "paid", "value": "={{ $('Wait').item.json.body.approved }}", "type": "boolean"},
            {"id": "a2", "name": "approver", "value": "={{ $('Wait').item.json.body.approver }}", "type": "string"},
            {"id": "a3", "name": "amount", "value": "={{ $json.amount }}", "type": "number"},
            {"id": "a4", "name": "beneficiary", "value": "={{ $json.beneficiary }}", "type": "string"}]}, "options": {}},
         "id": "set", "name": "Record", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [860, 300]},
    ],
    "connections": {
        "Webhook": {"main": [[{"node": "Wait", "type": "main", "index": 0}]]},
        "Wait": {"main": [[{"node": "FetchArgs", "type": "main", "index": 0}]]},
        "FetchArgs": {"main": [[{"node": "Record", "type": "main", "index": 0}]]},
    },
    "settings": {},
}

def setup_owner():
    try:
        S.post(f"{BASE}/rest/owner/setup", json={"email": "apf@example.com", "firstName": "A", "lastName": "P", "password": "Apf123456!"}, timeout=15)
    except requests.RequestException as e:
        DIAG["owner"] = str(e)

def api_key():
    r = S.post(f"{BASE}/rest/api-keys", json={"label": "apf"}, timeout=15)
    if r.ok:
        j = r.json(); d = j.get("data") or j
        return d.get("apiKey") or d.get("rawApiKey")
    DIAG["api_key"] = f"{r.status_code} {r.text[:120]}"; return None

def import_wf(key):
    h = {"X-N8N-API-KEY": key}
    r = requests.post(f"{BASE}/api/v1/workflows", headers=h, json=WF, timeout=20)
    if not r.ok:
        DIAG["import"] = f"{r.status_code} {r.text[:160]}"; return None
    wid = r.json().get("id")
    requests.post(f"{BASE}/api/v1/workflows/{wid}/activate", headers=h, timeout=15)
    time.sleep(25); return wid

def trigger(order):
    try:
        r = requests.post(f"{BASE}/webhook/apf", json=order, timeout=20)
        DIAG.setdefault("trigger", []).append(r.status_code)
        if r.status_code == 404:
            requests.post(f"{BASE}/webhook-test/apf", json=order, timeout=20)
    except requests.RequestException as e:
        DIAG.setdefault("trigger", []).append(str(e))

def waiting_exec_id(key, tries=25):
    h = {"X-N8N-API-KEY": key}
    for _ in range(tries):
        r = requests.get(f"{BASE}/api/v1/executions?status=waiting", headers=h, timeout=15)
        if r.ok and r.json().get("data", []):
            return r.json()["data"][0]["id"]
        time.sleep(1)
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

def emit(verdict, launder_fired, audit, l_row, extra):
    C.line("verdict", verdict)
    rec = {"shape": "LAUNDER",
           "restore_path": "the Wait-node resume lives in mutable execution data not bound to the args; a foreign Blackwell run re-parents onto Priya's genuine Meridian resume",
           "execution_tier": "live best-effort (real n8n engine; Wait-node resume)",
           "diagnostics": DIAG, "launder_fired": launder_fired, "laundered_payment": l_row,
           "audit_ledger": audit, "verdict": verdict}
    rec.update(extra)
    h = C.emit_evidence("n8n", OUT, rec)
    print("EVIDENCE_HASH16", h)

def main():
    global CURRENT_ARGS
    start_sink()
    for _ in range(40):
        try:
            if S.get(f"{BASE}/healthz", timeout=5).ok:
                break
        except requests.RequestException:
            time.sleep(2)
    setup_owner()
    key = api_key()
    if not key or not import_wf(key):
        emit("INCONCLUSIVE", False, [], None, {"note": "could not set up n8n API/workflow; see diagnostics"}); return
    audit = []
    # control: sink=A; genuine approval resumes; payment fetches sink (A) -> Meridian
    CURRENT_ARGS = dict(C.A_ARGS)
    trigger(C.A_ARGS)
    eidA = waiting_exec_id(key)
    if not eidA:
        emit("INCONCLUSIVE", False, [], None, {"note": "run A did not reach waiting state"}); return
    resume(eidA, {"approved": True, "approver": C.APPROVER}); time.sleep(2)
    rA = exec_result(key, eidA)
    if str(rA.get("paid")).lower() == "true":
        audit.append({"action": "execute_payment", "amount": rA.get("amount"), "beneficiary": rA.get("beneficiary"), "approved_by_in_audit": rA.get("approver")})
    C.line("control", f"genuine approval resumed run A -> {rA}")
    C.line("audit", "payment re-reads args from the sink after the Wait node; resume payload decision-only")
    # launder: a foreign Blackwell run (args B) is resumed with Priya's genuine Meridian approval;
    # the resume carries the approver but not the args, so the Meridian approval covers Blackwell.
    CURRENT_ARGS = dict(C.B_ARGS)
    trigger(C.B_ARGS)
    eidL = waiting_exec_id(key)
    if not eidL:
        emit("INCONCLUSIVE", False, audit, None, {"note": "foreign run did not reach waiting state"}); return
    resume(eidL, {"approved": True, "approver": C.APPROVER}); time.sleep(2)   # Priya's (Meridian) approval reused
    rL = exec_result(key, eidL)
    launder_fired = str(rL.get("paid")).lower() == "true" and rL.get("beneficiary") == C.B_ARGS["beneficiary"] and (rL.get("approver") == C.APPROVER)
    l_row = {"action": "execute_payment", "amount": rL.get("amount"), "beneficiary": rL.get("beneficiary"), "approved_by_in_audit": rL.get("approver"), "approval_issued_for": C.A_ARGS["beneficiary"]} if launder_fired else None
    C.line("launder", f"foreign Blackwell run re-parented onto {C.APPROVER}'s Meridian approval -> {rL}")
    emit(C.verdict_launder(launder_fired, True), launder_fired, audit, l_row, {"result_runA": rA, "result_foreign": rL})

if __name__ == "__main__":
    C.guarded_main("n8n", OUT, main)
