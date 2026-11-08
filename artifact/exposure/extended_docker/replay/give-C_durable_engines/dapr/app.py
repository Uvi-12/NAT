#!/usr/bin/env python3
# Dapr workflow app under test: approval delivered as an external workflow event.
import dapr.ext.workflow as wf
from flask import Flask, request, jsonify

wfr = wf.WorkflowRuntime()

def payment_workflow(ctx: wf.DaprWorkflowContext, order: dict):
    approval = yield ctx.wait_for_external_event("approval")   # matched by NAME only
    if approval and approval.get("approved"):
        return {"paid": True, "amount": order["amount"],
                "beneficiary": order["beneficiary"], "approver": approval.get("approver")}
    return {"paid": False}

wfr.register_workflow(payment_workflow)

app = Flask(__name__)
client = wf.DaprWorkflowClient()

@app.route("/start", methods=["POST"])
def start():
    iid = client.schedule_new_workflow(workflow=payment_workflow, input=request.json,
                                        instance_id=request.args["id"])
    return jsonify({"instance_id": iid})

@app.route("/raise", methods=["POST"])
def raise_evt():
    client.raise_workflow_event(instance_id=request.args["id"], event_name="approval",
                                data=request.json)
    return jsonify({"ok": True})

@app.route("/status", methods=["GET"])
def status():
    st = client.get_workflow_state(request.args["id"])
    return jsonify({"runtime_status": str(st.runtime_status),
                    "output": st.serialized_output if st else None})

if __name__ == "__main__":
    wfr.start()
    app.run(host="0.0.0.0", port=5001)
