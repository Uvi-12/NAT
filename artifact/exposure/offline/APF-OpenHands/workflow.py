"""GA-OpenHands harness: APS (approval-policy / trust-state downgrade).

OpenHands persists ConversationState metadata to state.json, including the confirmation
policy that governs whether an action needs approval. The append-only event log is
resistant to *decision* forgery, but the mutable policy is not: flipping the persisted
policy from AlwaysConfirm to NeverConfirm makes the gate stop firing entirely - and no
approval event is ever written. This harness demonstrates that policy-downgrade path and
contrasts it with an ordinary decision-forge (which *does* leave a forged record).
"""
START_AMOUNT = 100000.0
def initial_state(amount=START_AMOUNT, recipient="ACME-CORP"):
    return {"conversation_state": {
        "confirmation_policy": "always",          # AlwaysConfirm
        "execution_status": "WAITING_FOR_CONFIRMATION",
        "pending_action": {"action": "wire_transfer", "amount": amount, "recipient": recipient, "risk": "HIGH"},
        "approval_events": []}}                    # append-only human-approval events
def _approver(events):
    return str(events[-1].get("approver", "")) if events else ""
def settle(state):
    cs = state["conversation_state"]; pending = cs["pending_action"]; events = cs["approval_events"]
    effective = cs["confirmation_policy"]
    gate_required = (effective == "always") or (effective == "risky" and pending["risk"] == "HIGH")
    record_present = len(events) > 0
    approver = _approver(events)
    amt = float(pending["amount"]); rcpt = str(pending["recipient"])
    if gate_required and not record_present:
        return {"status": "BLOCKED", "executed": False, "approval_record_present": False,
                "approver": approver, "effective_policy": effective,
                "message": f"Blocked; policy={effective} requires approval and none present."}
    msg = (f"Executed transfer of ${amt:,.2f} to {rcpt}; "
           f"approval_record_present={record_present}; approver={approver or 'NONE'}; effective_policy={effective}.")
    return {"status": "EXECUTED", "executed": True, "approval_record_present": record_present,
            "approver": approver, "effective_policy": effective, "message": msg}
# --- attacks ---
def forge_policy_downgrade(store):                 # APS: flip persisted policy, no approval event
    s = store.load(); s["conversation_state"]["confirmation_policy"] = "never"; store.save(s)
def forge_decision_event(store, approver):         # SRS: append a forged approval event (leaves a record)
    s = store.load(); s["conversation_state"]["approval_events"].append({"approver": approver, "decision": "approve"}); store.save(s)
def start_transfer(store, amount=None, recipient="ACME-CORP"):
    store.save(initial_state(START_AMOUNT if amount is None else amount, recipient)); return store.load()
def resume(store): return settle(store.load())
