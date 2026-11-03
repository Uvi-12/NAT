"""An approval workflow built on a Semantic Kernel process step.

Semantic Kernel does not ship a human-in-the-loop persistence layer; an application
that pauses a process for approval must serialize the step state itself and restore it
later. On restore the state is rebuilt with ``ApprovalState.model_validate`` and handed
to the step via ``activate``. This module models that boundary: a settlement decision
reads ``transfer_approved`` from the restored step state and executes or rejects.
"""
from __future__ import annotations

from pydantic import BaseModel
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepState

APPROVAL_THRESHOLD = 10_000.0
START_AMOUNT = 100_000.0
_STEP_NAME = "ApprovalStep"


class ApprovalState(BaseModel):
    amount: float = START_AMOUNT
    recipient: str = "ACME-CORP"
    transfer_approved: bool = False
    approver: str = ""
    executed: bool = False
    approval_signature: str = ""


class ApprovalStep(KernelProcessStep):
    """A process step whose state records the human approval decision."""

    state: ApprovalState = ApprovalState()

    async def activate(self, state) -> None:
        self.state = state.state or ApprovalState()

    def decision(self) -> str:
        return "approved" if self.state.transfer_approved else "blocked"


async def restore_step(data: dict) -> ApprovalStep:
    """Rebuild the approval step from serialized state via the SK restore path."""
    approval_state = ApprovalState.model_validate(data)
    step = ApprovalStep()
    await step.activate(
        KernelProcessStepState(name=_STEP_NAME, id=_STEP_NAME, version="1.0", state=approval_state)
    )
    return step


async def settle(data: dict) -> dict:
    """Restore the step state and execute or reject the transfer accordingly."""
    step = await restore_step(data)
    state = step.state
    approved = step.decision() == "approved"

    if approved:
        message = (
            f"Executed transfer of ${state.amount:,.2f} to {state.recipient}; "
            f"approved by {state.approver or 'unnamed'}."
        )
        return {
            "status": "EXECUTED",
            "executed": True,
            "approved": True,
            "approver": state.approver,
            "message": message,
        }
    return {
        "status": "REJECTED",
        "executed": False,
        "approved": bool(state.transfer_approved),
        "approver": state.approver,
        "message": "Transfer rejected; no valid approval recorded.",
    }


def initial_state(amount: float = START_AMOUNT, recipient: str = "ACME-CORP") -> dict:
    """Return the serialized state for a new, unapproved transfer."""
    return ApprovalState(amount=amount, recipient=recipient).model_dump()


async def start_transfer(store, *, amount: float = START_AMOUNT, recipient: str = "ACME-CORP") -> dict:
    """Persist the initial unapproved state through ``store`` and return it."""
    state = initial_state(amount, recipient)
    store.save(state)
    return state


async def resume(store) -> dict:
    """Restore persisted state and report the settlement outcome."""
    return await settle(store.load())
