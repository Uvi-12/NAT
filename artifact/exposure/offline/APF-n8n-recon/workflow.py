"""GA-n8n harness: WED - workflow execution data"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    s = {"amount": amount, "recipient": recipient, "approver": "", "approval_signature": ""}
    s.update({"run_data": {"gate": {"approved": False}}})
    return s
def is_approved(state):
    return bool(state["run_data"]["gate"]["approved"]) is True
def mark_approved(state):
    state["run_data"]["gate"]["approved"] = True
