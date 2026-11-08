"""GA-Agno harness: ALS - approval-lifecycle status"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    s = {"amount": amount, "recipient": recipient, "approver": "", "approval_signature": ""}
    s.update({"approval_record": {"action": "wire_transfer", "status": "pending", "approver": None, "decision": None}})
    return s
def is_approved(state):
    return state["approval_record"]["status"] == "approved"
def mark_approved(state):
    r = state["approval_record"]; r["status"] = "approved"; r["decision"] = "approve"
