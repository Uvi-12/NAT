#!/usr/bin/env python3
# APF / APF - REBIND reproduction harness: Flowable OSS (#35)
#
# REBIND shape: ONE genuine human approval of the payment as reviewed (args A = Meridian),
# but before the gated service task executes a state writer mutates the approved call's
# arguments to B. The amount/beneficiary are persisted process variables that the pay task
# reads at execution time; Flowable trusts its persisted state and re-verifies neither the
# approver nor which args were approved. A state writer with access to the persisted process
# state (the /variables REST endpoint here stands in for a direct H2/RDBMS row edit) changes
# amount/beneficiary A->B while the instance waits at the user task; the genuine approver then
# completes the task, and the pay task fires on ${approved == true} with the MUTATED args,
# paying Blackwell under Priya. The approval is bound to neither the argument values nor a nonce.
#
# Self-proving: verdict derived from Flowable's own historic variables on the rebind run.
#
# Usage:
#   pip install requests
#   docker compose up -d      # wait until the REST app is up
#   python3 harness_rebind.py
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
            if requests.get(BASE + "/repository/deployments", auth=AUTH, timeout=5).ok:
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
    # persisted-state write: mutate EXISTING variables on a running instance. Flowable REST
    # updates an existing variable with PUT on the individual variable (POST on the collection
    # creates and errors when it already exists), so PUT each one.
    statuses = {}
    for v in variables:
        r = requests.put(BASE + "/runtime/process-instances/" + pid + "/variables/" + v["name"],
                         auth=AUTH, json=v, timeout=30)
        statuses[v["name"]] = r.status_code
    return statuses


def runtime_var(pid, name):
    r = requests.get(BASE + "/runtime/process-instances/" + pid + "/variables/" + name, auth=AUTH, timeout=15)
    return r.json().get("value") if r.ok else None


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

    # ---- control: genuine approval of args A (Meridian) ----
    pidA = start(C.A_ARGS["amount"], C.A_ARGS["beneficiary"])
    tA = task_of(pidA)
    complete(tA, [{"name": "approved", "value": True, "type": "boolean"},
                  {"name": "approver", "value": C.APPROVER, "type": "string"}])   # genuine approver
    time.sleep(1)
    hvA = hist_vars(pidA)
    paidA = hvA.get("paid_to") not in (None, "BLOCKED")
    if paidA:
        audit.append({"action": "execute_payment", "amount": hvA.get("amount"),
                      "beneficiary": hvA.get("paid_to"), "approved_by_in_audit": hvA.get("approver")})
    C.line("control", f"genuine approval by {C.APPROVER} -> pay consumed beneficiary: paid_to={hvA.get('paid_to')} approver={hvA.get('approver')}")
    C.line("audit", "the user-task approval carries the approver but not the action; it can be reused to cover a different process instance")

    # ---- launder: a foreign Blackwell process (args B) completes reusing Priya's genuine Meridian
    #      approval; no genuine review of the Blackwell payment took place ----
    pidL = start(C.B_ARGS["amount"], C.B_ARGS["beneficiary"])
    tL = task_of(pidL)
    complete(tL, [{"name": "approved", "value": True, "type": "boolean"},
                  {"name": "approver", "value": C.APPROVER, "type": "string"}])   # Priya's (Meridian) approval reused
    time.sleep(1)
    hvL = hist_vars(pidL)
    paidL = hvL.get("paid_to") not in (None, "BLOCKED")
    launder_fired = paidL and hvL.get("paid_to") == C.B_ARGS["beneficiary"] and hvL.get("approver") == C.APPROVER
    l_row = None
    if launder_fired:
        l_row = {"action": "execute_payment", "amount": hvL.get("amount"),
                 "beneficiary": hvL.get("paid_to"), "approved_by_in_audit": hvL.get("approver"),
                 "approval_issued_for": C.A_ARGS["beneficiary"]}
        audit.append(l_row)
    C.line("launder", f"foreign Blackwell payment re-parented onto {C.APPROVER}'s approval issued for {C.A_ARGS['beneficiary']} -> paid_to={hvL.get('paid_to')} approver={hvL.get('approver')!r}")

    verdict = C.verdict_launder(launder_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Flowable", OUT, {
        "shape": "LAUNDER",
        "restore_path": "the user-task approval carries the approver but not the action; a foreign Blackwell payment reuses Priya's genuine Meridian approval as its provenance",
        "execution_tier": "give-code (real Flowable REST + BPMN; run on Docker to confirm)",
        "flowable_image": "flowable/flowable-rest:7.0.1",
        "genuine_run": pidA, "launder_run": pidL,
        "approval_issued_for": C.A_ARGS, "foreign_action": C.B_ARGS,
        "launder_fired": launder_fired, "laundered_payment": l_row,
        "historic_vars_runA": hvA, "historic_vars_runL": hvL,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)


if __name__ == "__main__":
    C.guarded_main("Flowable", OUT, main)
