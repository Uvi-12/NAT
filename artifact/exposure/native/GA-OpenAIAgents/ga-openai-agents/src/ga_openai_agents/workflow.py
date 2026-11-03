"""An approval workflow built on OpenAI Agents SDK tool-approval state.

When a tool is marked ``needs_approval``, the SDK interrupts the run and serializes its
run state (including the approvals map) so the run can be resumed once a human approves.
On resume the approvals are rebuilt with ``RunContextWrapper._rebuild_approvals`` and the
Runner consults ``is_tool_approved`` before invoking the tool. This module models that
boundary: a settlement step checks ``is_tool_approved`` and executes or rejects.
"""
from __future__ import annotations

from agents.run_context import RunContextWrapper

APPROVAL_THRESHOLD = 10_000.0
START_AMOUNT = 100_000.0
TOOL_NAME = "wire_transfer"
CALL_ID = "call_wire_001"


def initial_state(amount: float = START_AMOUNT, recipient: str = "ACME-CORP") -> dict:
    """Return serialized run state for a new, unapproved transfer."""
    return {
        "amount": amount,
        "recipient": recipient,
        "approver": "",
        "executed": False,
        "approvals": {},
    }


def settle(state: dict) -> dict:
    """Rebuild approvals via the SDK and execute or reject the transfer."""
    context: RunContextWrapper = RunContextWrapper(context=None)
    context._rebuild_approvals(state.get("approvals", {}))
    approved = context.is_tool_approved(TOOL_NAME, CALL_ID) is True
    approver = str(state.get("approver", ""))

    if approved:
        amount = float(state.get("amount", 0.0))
        message = (
            f"Executed transfer of ${amount:,.2f} to {state.get('recipient', 'n/a')}; "
            f"approved by {approver or 'unnamed'}."
        )
        return {"status": "EXECUTED", "executed": True, "approved": True, "approver": approver, "message": message}

    return {
        "status": "REJECTED",
        "executed": False,
        "approved": context.is_tool_approved(TOOL_NAME, CALL_ID) is True,
        "approver": approver,
        "message": "Transfer rejected; tool not approved.",
    }


def start_transfer(store, *, amount: float = START_AMOUNT, recipient: str = "ACME-CORP") -> dict:
    """Persist the initial unapproved run state and return it."""
    state = initial_state(amount, recipient)
    store.save(state)
    return state


def resume(store) -> dict:
    """Restore the run state and report the settlement outcome."""
    return settle(store.load())
