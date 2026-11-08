#!/usr/bin/env python3
# APF / APF - REPLAY reproduction harness: Flowable OSS (#35)
#
# Restore path: approval = process variables (approved, approver) set at a user task and
# persisted by the engine. Flowable trusts its persisted state; the gated service task
# fires on ${approved == true} with no re-verification of who approved or which run/args
# were approved. Threat model: a state writer with access to the persisted process state
# reuses run A's genuine approval variables for run B (a different instance / beneficiary),
# so run B's payment executes named to Priya with no fresh decision. The variables REST
# endpoint here stands in for that persisted-state write (a real state writer would edit
# rejects the reuse.
#
# Self-proving: verdict derived from Flowable's own historic variables on run B.
#
# Usage:
#   pip install requests
#   docker compose up -d      # wait until the REST app is up
#   python3 harness_flowable.py
import sys, os, time
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apf_common as C

BASE = os.environ.get("FLOWABLE_BASE", "http://localhost:8080/flowable-rest/service")
AUTH = ("rest-admin", "test")
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence")), "35_flowable")
HERE = os.path.dirname(os.path.abspath(__file__))


def wait_up():
    for _ in range(60):
        try:
            r = requests.get(BASE + "/repository/deployments", auth=AUTH, timeout=5)
            if r.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise SystemExit("Flowable REST did not come up in time")


def deploy():
    with open(os.path.join(HERE, "apf_payment.bpmn20.xml"), "rb") as fh:
        r = requests.post(BASE + "/repository/deployments", auth=AUTH,
                          files={"file": ("apf_payment.bpmn20.xml", fh, "text/xml")}, timeout=30)
    if not r.ok:
        raise SystemExit("deploy failed: %s %s" % (r.status_code, r.text[:300]))


def start(amount, beneficiary):
    r = requests.post(BASE + "/runtime/process-instances", auth=AUTH, json={
        "processDefinitionKey": "apf_payment",
        "variables": [
            {"name": "amount", "value": amount, "type": "integer"},
            {"name": "beneficiary", "value": beneficiary, "type": "string"},
        ]}, timeout=30)
    if not r.ok:
        raise SystemExit("start failed: %s %s" % (r.status_code, r.text[:300]))
    return r.json()["id"]


def task_of(pid):
    for _ in range(30):
        r = requests.get(BASE + "/runtime/tasks?processInstanceId=" + pid, auth=AUTH, timeout=15)
        data = r.json().get("data", [])
        if data:
            return data[0]["id"]
        time.sleep(1)
    return None


def complete(task_id, variables):
    r = requests.post(BASE + "/runtime/tasks/" + task_id, auth=AUTH,
                      json={"action": "complete", "variables": variables}, timeout=30)
    if not r.ok:
        raise SystemExit("complete failed: %s %s" % (r.status_code, r.text[:300]))


def set_process_vars(pid, variables):
    # persisted-state write: inject variables onto a running instance (stands in for a
    # state writer editing the process-state rows directly)
    r = requests.post(BASE + "/runtime/process-instances/" + pid + "/variables", auth=AUTH,
                      json=variables, timeout=30)
    return r.status_code


def hist_vars(pid):
    r = requests.get(BASE + "/history/historic-variable-instances?processInstanceId=" + pid,
                     auth=AUTH, timeout=15)
    out = {}
    for item in r.json().get("data", []):
        v = item.get("variable", {})
        out[v.get("name")] = v.get("value")
    return out


def main():
    wait_up()
    deploy()
    audit = []

    # ---- control: genuine approval on instance A ----
    pidA = start(C.A_ARGS["amount"], C.A_ARGS["beneficiary"])
    tA = task_of(pidA)
    complete(tA, [{"name": "approved", "value": True, "type": "boolean"},
                  {"name": "approver", "value": C.APPROVER, "type": "string"}])   # genuine approver
    time.sleep(1)
    hvA = hist_vars(pidA)
    if hvA.get("paid") in (True, "true"):
        audit.append({"action": "execute_payment", "amount": hvA.get("amount"),
                      "beneficiary": hvA.get("beneficiary"), "approved_by_in_audit": hvA.get("approver")})
    C.line("control", f"genuine approval by {C.APPROVER} -> historic vars: paid={hvA.get('paid')} approver={hvA.get('approver')} beneficiary={hvA.get('beneficiary')}")

    genuine_vars = {"approved": True, "approver": C.APPROVER}
    C.line("audit", f"reusable persisted approval variables (no run/nonce binding): {genuine_vars}")

    # ---- replay: state writer reuses run A's approval variables for run B ----
    pidB = start(C.B_ARGS["amount"], C.B_ARGS["beneficiary"])
    tB = task_of(pidB)
    # inject run A's genuine approval into B's persisted state (reuse, no fresh decision)
    set_process_vars(pidB, [{"name": "approved", "value": True, "type": "boolean"},
                            {"name": "approver", "value": C.APPROVER, "type": "string"}])
    # a non-approver actor (the state writer / an automated job) moves the token; the
    # approved/approver already present in state are the reused genuine approval
    complete(tB, [])
    time.sleep(1)
    hvB = hist_vars(pidB)
    replay_fired = (hvB.get("paid") in (True, "true")) and hvB.get("beneficiary") == C.B_ARGS["beneficiary"] \
        and hvB.get("approver") == C.APPROVER
    b_row = None
    if replay_fired:
        b_row = {"action": "execute_payment", "amount": hvB.get("amount"),
                 "beneficiary": hvB.get("beneficiary"), "approved_by_in_audit": hvB.get("approver")}
        audit.append(b_row)
    C.line("replay", f"reused run A approval for run B -> historic vars: paid={hvB.get('paid')} approver={hvB.get('approver')} beneficiary={hvB.get('beneficiary')}")

    seen = set(); nonce = "n-runA-0035"

    verdict = C.verdict_from_state(replay_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Flowable", OUT, {
        "restore_path": "approval = persisted process variables (approved, approver) gating a service task; engine re-verifies neither approver nor run/args",
        "flowable_image": "flowable/flowable-rest:7.0.1",
        "genuine_run": pidA, "replay_run": pidB,
        "replay_fired": replay_fired, "replayed_payment": b_row,
        "historic_vars_runA": hvA, "historic_vars_runB": hvB,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)


if __name__ == "__main__":
    C.guarded_main('Flowable', OUT, main)
