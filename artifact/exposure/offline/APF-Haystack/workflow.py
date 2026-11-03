"""GA-Haystack harness: TCA - restored tool-call approval field"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    s = {"amount": amount, "recipient": recipient, "approver": "", "approval_signature": ""}
    s.update({"pipeline_state": {"restored_tool_call": {"tool": "transfer_money", "approved": False}}})
    return s
def is_approved(state):
    return bool(state["pipeline_state"]["restored_tool_call"]["approved"]) is True
def mark_approved(state):
    state["pipeline_state"]["restored_tool_call"]["approved"] = True
