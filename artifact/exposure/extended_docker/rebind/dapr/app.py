#!/usr/bin/env python3
# Dapr workflow app under test (REBIND). The payment re-reads amount/beneficiary from the Dapr
# STATE STORE (key args:<id>) via an activity AFTER the approval event. Approval is delivered as
# an external workflow event matched by NAME only. A state writer mutates the state key via
# /mutate (the Dapr state API) while the instance awaits approval, so the workflow replays with
# the mutated argument and pays it under the one approval.
import json
import dapr.ext.workflow as wf
from dapr.clients import DaprClient
from flask import Flask, request, jsonify

STATE = "statestore"
wfr = wf.WorkflowRuntime()

def read_args(ctx, iid: str):
    with DaprClient() as d:
        r = d.get_state(store_name=STATE, key="args:" + iid)
        return json.loads(r.data) if r.data else {}

def payment_workflow(ctx: wf.DaprWorkflowContext, order: dict):
    approval = yield ctx.wait_for_external_event("approval")            # matched by NAME only
    args = yield ctx.call_activity(read_args, input=ctx.instance_id)    # re-read args from the state store
    if approval and approval.get("approved") and args:
        return {"paid": True, "amount": args["amount"], "beneficiary": args["beneficiary"], "approver": approval.get("approver")}
    return {"paid": False}

wfr.register_workflow(payment_workflow)
wfr.register_activity(read_args)

app = Flask(__name__)
client = wf.DaprWorkflowClient()

@app.route("/start", methods=["POST"])
def start():
    iid = request.args["id"]; order = request.json
    with DaprClient() as d:                                             # seed args (A)
        d.save_state(store_name=STATE, key="args:" + iid, value=json.dumps(order))
    client.schedule_new_workflow(workflow=payment_workflow, input=order, instance_id=iid)
    return jsonify({"instance_id": iid})

@app.route("/mutate", methods=["POST"])
def mutate():
    iid = request.args["id"]
    with DaprClient() as d:                                             # state-writer mutation of the durable arg
        d.save_state(store_name=STATE, key="args:" + iid, value=json.dumps(request.json))
    return jsonify({"ok": True})

@app.route("/raise", methods=["POST"])
def raise_evt():
    client.raise_workflow_event(instance_id=request.args["id"], event_name="approval", data=request.json)
    return jsonify({"ok": True})

@app.route("/status", methods=["GET"])
def status():
    st = client.get_workflow_state(request.args["id"])
    return jsonify({"runtime_status": str(st.runtime_status), "output": st.serialized_output if st else None})

if __name__ == "__main__":
    wfr.start()
    app.run(host="0.0.0.0", port=5001)
