"""GA-Dify harness: WED - workflow execution-data node output"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    s = {"amount": amount, "recipient": recipient, "approver": "", "approval_signature": ""}
    s.update({"execution_state": {"node": "human_review", "status": "waiting", "output": {"approved": False, "decision": None}}})
    return s
def is_approved(state):
    return bool(state["execution_state"]["output"]["approved"]) is True
def mark_approved(state):
    o = state["execution_state"]["output"]; o["approved"] = True; o["decision"] = "approve"
    state["execution_state"]["status"] = "succeeded"
