import workflow
def start_transfer(store, amount=None, recipient="ACME-CORP"):
    a = workflow.START_AMOUNT if amount is None else amount
    store.save(workflow.initial_state(a, recipient)); return store.load()
def settle(state):
    approved = bool(workflow.is_approved(state)); approver = str(state.get("approver", ""))
    if approved:
        amt = float(state["amount"]); rcpt = str(state["recipient"])
        msg = f"Executed transfer of ${amt:,.2f} to {rcpt}; approved by {approver or 'unnamed'}."
        return {"status": "EXECUTED", "executed": True, "approved": True, "approver": approver, "message": msg}
    return {"status": "REJECTED", "executed": False, "approved": bool(workflow.is_approved(state)),
            "approver": approver, "message": "Transfer rejected; approval not present in restored state."}
def resume(store): return settle(store.load())
def inject_approval(store, approver):
    s = store.load(); workflow.mark_approved(s); s["approver"] = approver; store.save(s)
