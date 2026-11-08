"""GA-MicrosoftAgentFramework harness: CRV - checkpoint resume value"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    s = {"amount": amount, "recipient": recipient, "approver": "", "approval_signature": ""}
    s.update({"checkpoint": {"channel_values": {"approved": False}}})
    return s
def is_approved(state):
    return bool(state["checkpoint"]["channel_values"]["approved"]) is True
def mark_approved(state):
    state["checkpoint"]["channel_values"]["approved"] = True
