#!/usr/bin/env python3
# APF / APF - SUPPRESS live harness: AWS Step Functions (#30).
# The payment waits for a single-use task token returned via SendTaskSuccess; execution state is
# service-managed. Without the approver's token the execution stays RUNNING; a state writer has no
# API to advance it or delete a state transition, and any callback leaves a recorded transition
# (FORGE, a different shape). So the payment cannot run with the approval-required record ABSENT.
# EXPECTED: RESISTANT (suppress_fired=False).
import os, sys, time, json
import boto3
from botocore.config import Config
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import apf_common as C
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "30_step_functions")
ENDPOINT = os.environ.get("SFN_ENDPOINT", "http://localhost:8083")
ROLE = "arn:aws:iam::012345678901:role/DummyRole"
sf = boto3.client("stepfunctions", endpoint_url=ENDPOINT, region_name="us-east-1",
                  aws_access_key_id="dummy", aws_secret_access_key="dummy",
                  config=Config(retries={"max_attempts": 2}))

def wait_local():
    for _ in range(30):
        try: sf.list_state_machines(); return
        except Exception: time.sleep(2)
    raise SystemExit("Step Functions Local not reachable at " + ENDPOINT)
def poll_token(activity_arn, tries=30):
    for _ in range(tries):
        r = sf.get_activity_task(activityArn=activity_arn, workerName="apf-worker")
        if r.get("taskToken"): return r["taskToken"], json.loads(r.get("input") or "{}")
        time.sleep(1)
    return None, None

def main():
    wait_local()
    audit = []
    activity_arn = sf.create_activity(name="apf-approval-" + str(int(time.time())))["activityArn"]
    asl = {"StartAt": "WaitApproval", "States": {"WaitApproval": {"Type": "Task", "Resource": activity_arn, "End": True}}}
    sm = sf.create_state_machine(name="apf-payment-" + str(int(time.time())), definition=json.dumps(asl), roleArn=ROLE)["stateMachineArn"]
    # control: genuine approval returns the token -> SUCCEEDED
    exA = sf.start_execution(stateMachineArn=sm, input=json.dumps(C.A_ARGS))["executionArn"]
    tokA, inA = poll_token(activity_arn)
    sf.send_task_success(taskToken=tokA, output=json.dumps({"approved": True, "approver": C.APPROVER}))
    time.sleep(1)
    stA = sf.describe_execution(executionArn=exA)["status"]
    if stA == "SUCCEEDED":
        audit.append({"action": "execute_payment", "amount": inA["amount"], "beneficiary": inA["beneficiary"], "approved_by_in_audit": C.APPROVER})
    C.line("control", f"genuine approval returned run A token -> execution {stA}")
    C.line("audit", "the gate is a task-token wait; the only advance path is SendTaskSuccess with the approver's single-use token; execution state is service-owned")
    # launder: a foreign Blackwell execution (args B) has its OWN task token; the Meridian approval
    # was a SendTaskSuccess against run A's single-use token and cannot be re-parented onto run L.
    exL = sf.start_execution(stateMachineArn=sm, input=json.dumps(C.B_ARGS))["executionArn"]
    tokL, inL = poll_token(activity_arn)   # foreign execution's own token; run A's approval does not apply
    time.sleep(2)
    stL = sf.describe_execution(executionArn=exL)["status"]
    launder_fired = (stL == "SUCCEEDED")
    C.line("launder", f"foreign execution has its own token; run A's approval cannot be re-parented; foreign status={stL}; foreign paid? {launder_fired}")
    verdict = C.verdict_launder(launder_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("AWS Step Functions", OUT, {
        "shape": "LAUNDER",
        "restore_path": "each approval is returned against its execution's single-use task token and state transitions are service-owned; a foreign execution cannot inherit another execution's token or approval",
        "execution_tier": "live (Step Functions Local; activity task token)",
        "why_resistant": "a task token is issued per execution and consumed once; no cross-execution re-parent path, so a foreign execution has no approval of its own",
        "foreign_execution_status": stL,
        "approval_issued_for": C.A_ARGS, "foreign_action": C.B_ARGS,
        "launder_fired": launder_fired, "laundered_payment": None,
        "audit_ledger": audit, "verdict": verdict})
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main("AWS Step Functions", OUT, main)
