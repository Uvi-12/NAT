#!/usr/bin/env python3
# APF / APF - REPLAY live harness: AWS Step Functions (#30)
# Runs against Step Functions Local. Approval = returning a task token via SendTaskSuccess
# for a .waitForTaskToken activity task. Confirms live that run A's genuine approval
# (run A's task token) cannot advance run B: run B mints its own token; reusing run A's
# token does not complete run B. EXPECTED: RESISTANT (replay_fired = False).
import os, sys, time, json
import boto3
from botocore.config import Config
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apf_common as C

OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "30_step_functions")
ENDPOINT = os.environ.get("SFN_ENDPOINT", "http://localhost:8083")
ROLE = "arn:aws:iam::012345678901:role/DummyRole"

sf = boto3.client("stepfunctions", endpoint_url=ENDPOINT, region_name="us-east-1",
                  aws_access_key_id="dummy", aws_secret_access_key="dummy",
                  config=Config(retries={"max_attempts": 2}))

def wait_local():
    for _ in range(30):
        try:
            sf.list_state_machines(); return
        except Exception:
            time.sleep(2)
    raise SystemExit("Step Functions Local not reachable at " + ENDPOINT)

def poll_token(activity_arn, tries=30):
    for _ in range(tries):
        r = sf.get_activity_task(activityArn=activity_arn, workerName="apf-worker")
        if r.get("taskToken"):
            return r["taskToken"], json.loads(r.get("input") or "{}")
        time.sleep(1)
    return None, None

def main():
    wait_local()
    audit = []
    activity_arn = sf.create_activity(name="apf-approval-" + str(int(time.time())))["activityArn"]
    asl = {"StartAt": "WaitApproval", "States": {
        "WaitApproval": {"Type": "Task", "Resource": activity_arn, "End": True}}}
    sm = sf.create_state_machine(name="apf-payment-" + str(int(time.time())),
                                 definition=json.dumps(asl), roleArn=ROLE)["stateMachineArn"]

    # ---- control: genuine approval returns run A's task token ----
    exA = sf.start_execution(stateMachineArn=sm, input=json.dumps(C.A_ARGS))["executionArn"]
    tokA, inA = poll_token(activity_arn)
    sf.send_task_success(taskToken=tokA, output=json.dumps({"approved": True, "approver": C.APPROVER}))
    time.sleep(1)
    stA = sf.describe_execution(executionArn=exA)["status"]
    if stA == "SUCCEEDED":
        audit.append({"action": "execute_payment", "amount": inA["amount"],
                      "beneficiary": inA["beneficiary"], "approved_by_in_audit": C.APPROVER})
    C.line("control", f"genuine approval returned run A token -> execution {stA}")

    # ---- replay: run B mints its own token; reuse run A's token (already used) ----
    exB = sf.start_execution(stateMachineArn=sm, input=json.dumps(C.B_ARGS))["executionArn"]
    tokB, inB = poll_token(activity_arn)   # run B's own distinct token
    reuse_error = None
    try:
        sf.send_task_success(taskToken=tokA, output=json.dumps({"approved": True, "approver": C.APPROVER}))
    except Exception as e:
        reuse_error = type(e).__name__
    time.sleep(1)
    stB = sf.describe_execution(executionArn=exB)["status"]
    replay_fired = (stB == "SUCCEEDED")
    b_row = None
    if replay_fired:
        b_row = {"action": "execute_payment", "amount": inB["amount"],
                 "beneficiary": inB["beneficiary"], "approved_by_in_audit": C.APPROVER}
    C.line("audit", f"run B has its own task token; reusing run A token raised {reuse_error}")
    C.line("replay", f"reused run A token onto run B -> execution {stB}")
    # cleanup: release run B's token so the local engine can settle
    try:
        sf.send_task_failure(taskToken=tokB, error="apf", cause="no genuine approval for run B")
    except Exception:
        pass

    seen = set(); nonce = "n-runA-0030"

    verdict = C.verdict_from_state(replay_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("AWS Step Functions", OUT, {
        "restore_path": "approval = SendTaskSuccess(taskToken, output) for a .waitForTaskToken activity task; token is single-use, execution-scoped",
        "execution_tier": "live (Step Functions Local; activity task token callback executed)",
        "why_resistant": "run B mints its own token; run A's token is single-use and does not advance run B",
        "reuse_token_error": reuse_error,
        "genuine_run": exA, "replay_run": exB,
        "replay_fired": replay_fired, "replayed_payment": b_row,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main('AWS Step Functions', OUT, main)
