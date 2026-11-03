"""GA-StrandsAgentsSDK harness: SRS - session snapshot interrupt response"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    s = {"amount": amount, "recipient": recipient, "approver": "", "approval_signature": ""}
    s.update({"session_snapshot": {"interrupt": {"response": {"approved": False}}}, "agent_state": {"trusted_tools": []}})
    return s
def is_approved(state):
    return bool(state["session_snapshot"]["interrupt"]["response"]["approved"]) is True
def mark_approved(state):
    state["session_snapshot"]["interrupt"]["response"]["approved"] = True
