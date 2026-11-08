"""GA-SemanticKernel harness: CRV - checkpointed step-state approval boolean"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    s = {"amount": amount, "recipient": recipient, "approver": "", "approval_signature": ""}
    s.update({"approval_state": {"transfer_approved": False}})
    return s
def is_approved(state):
    return bool(state["approval_state"]["transfer_approved"]) is True
def mark_approved(state):
    state["approval_state"]["transfer_approved"] = True
