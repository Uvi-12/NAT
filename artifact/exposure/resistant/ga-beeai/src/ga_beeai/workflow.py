"""Drive BeeAI's real AskPermissionRequirement gate.

BeeAI's HITL approval is the ``AskPermissionRequirement``. When a guarded tool is about
to run, the requirement calls a handler (``self._handler(tool, input)``), a live
decision at that moment, and blocks the tool if the handler returns False. The
decision is never serialized to a store that is reloaded on resume.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from beeai_framework.agents.requirement.requirements.ask_permission import AskPermissionRequirement
from beeai_framework.tools import StringToolOutput

TOOL_NAME = "wire_transfer"


class _Tool:
    def __init__(self, name: str) -> None:
        self.name = name


class _StartEvent:
    """Stands in for the tool 'start' event the requirement gates on."""

    def __init__(self, tool_input: dict) -> None:
        self.input = tool_input
        self.output = None


async def run_gate(handler: Callable[[object, dict], Awaitable[bool]], *, amount: float = 100_000.0) -> bool:
    """Run the real AskPermissionRequirement gate with ``handler`` as the live decision.

    Returns True if the tool is permitted (the gate left the output untouched), False if
    the gate blocked it.
    """
    requirement = AskPermissionRequirement(handler=handler)
    tool = _Tool(TOOL_NAME)
    event = _StartEvent({"amount": amount, "recipient": "ACME-CORP"})
    await requirement._ask(tool, event)
    return not isinstance(event.output, StringToolOutput)


async def settle(handler: Callable[[object, dict], Awaitable[bool]], *, amount: float = 100_000.0,
                 recipient: str = "ACME-CORP", approver: str = "") -> dict:
    """Run the gate and report the settlement outcome."""
    permitted = await run_gate(handler, amount=amount)
    if permitted:
        return {
            "status": "EXECUTED",
            "executed": True,
            "message": f"Executed transfer of ${amount:,.2f} to {recipient}; approved by {approver or 'live handler'}.",
        }
    return {"status": "REJECTED", "executed": False, "message": "Transfer rejected; tool not permitted by the live handler."}
