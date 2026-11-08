"""GA-OpenAIAgentsSDK harness: SRS - RunState/session approvals"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    s = {"amount": amount, "recipient": recipient, "approver": "", "approval_signature": ""}
    s.update({"run_state": {"approvals": {"wire_transfer": {"approved": [], "rejected": []}}}})
    return s
def is_approved(state):
    return len(state["run_state"]["approvals"]["wire_transfer"]["approved"]) > 0
def mark_approved(state):
    state["run_state"]["approvals"]["wire_transfer"]["approved"] = ["call_1"]
