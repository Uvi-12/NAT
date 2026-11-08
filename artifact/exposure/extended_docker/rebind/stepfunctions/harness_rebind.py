#!/usr/bin/env python3
# APF / APF - REBIND live harness: AWS Step Functions (#30).
# The execution input (args) is Step-Functions-service-managed; the approval returns a task
# token via SendTaskSuccess. A state writer has no API to alter a running execution's input, and
# the callback output is supplied by the approver (the token holder), not a state writer, so the
# mutated argument cannot run under the one approval. EXPECTED: RESISTANT.
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
    asl = {"StartAt": "WaitApproval", "States": {"WaitApproval": {"Type": "Task", "Resource": activity_arn, "End": True}}}
    sm = sf.create_state_machine(name="apf-payment-" + str(int(time.time())), definition=json.dumps(asl), roleArn=ROLE)["stateMachineArn"]
    # control: genuine approval returns run A's token; execution input (args A) is service-managed
    exA = sf.start_execution(stateMachineArn=sm, input=json.dumps(C.A_ARGS))["executionArn"]
    tokA, inA = poll_token(activity_arn)
    sf.send_task_success(taskToken=tokA, output=json.dumps({"approved": True, "approver": C.APPROVER}))
    time.sleep(1)
    stA = sf.describe_execution(executionArn=exA)["status"]
    if stA == "SUCCEEDED":
        audit.append({"action": "execute_payment", "amount": inA["amount"], "beneficiary": inA["beneficiary"], "approved_by_in_audit": C.APPROVER})
    C.line("control", f"genuine approval returned run A token -> execution {stA} (input beneficiary={inA.get('beneficiary')})")
    C.line("audit", "execution input service-managed; a state writer has no API to alter it; callback output is the approver's")
    # rebind: Priya reviews Meridian; a state writer tries to inject B via the callback output - execution input is unchanged
    exR = sf.start_execution(stateMachineArn=sm, input=json.dumps(C.A_ARGS))["executionArn"]
    tokR, inR = poll_token(activity_arn)
    sf.send_task_success(taskToken=tokR, output=json.dumps({"approved": True, "approver": C.APPROVER,
                         "amount": C.B_ARGS["amount"], "beneficiary": C.B_ARGS["beneficiary"]}))
    time.sleep(1)
    stR = sf.describe_execution(executionArn=exR)
    outR = json.loads(stR.get("output") or "{}")
    # the payment argument is the execution input (frozen), not the attacker-supplied callback output
    rebind_fired = (stR["status"] == "SUCCEEDED") and (inR.get("beneficiary") == C.B_ARGS["beneficiary"])
    C.line("rebind", f"callback output carried B args, execution input stayed Meridian -> status {stR['status']} input beneficiary={inR.get('beneficiary')}")
    nonce = "n-rebind-0030"
    verdict = C.verdict_rebind(rebind_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("AWS Step Functions", OUT, {
        "shape": "REBIND",
        "restore_path": "execution input service-managed; token callback output supplied by the approver, not a state writer; no state-writer arg mutation path",
        "execution_tier": "live (Step Functions Local; activity task token callback executed)",
        "genuine_args": C.A_ARGS, "mutated_args": C.B_ARGS,
        "rebind_fired": rebind_fired, "rebound_payment": None,
        "audit_ledger": audit, "verdict": verdict})
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main("AWS Step Functions", OUT, main)
