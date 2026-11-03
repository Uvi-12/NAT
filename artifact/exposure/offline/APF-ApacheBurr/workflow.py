"""GA-ApacheBurr harness: CRV - persisted application State"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    s = {"amount": amount, "recipient": recipient, "approver": "", "approval_signature": ""}
    s.update({"app_state": {"approved": False}})
    return s
def is_approved(state):
    return bool(state["app_state"]["approved"]) is True
def mark_approved(state):
    state["app_state"]["approved"] = True
