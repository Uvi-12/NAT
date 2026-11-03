"""A high-value transfer gated by a PydanticAI approval-required tool.

PydanticAI gates a tool with ``requires_approval=True``. On run, the call is
deferred: the agent returns ``DeferredToolRequests`` rather than executing the
tool. The decision is supplied on resume through the ``DeferredToolResults`` API
(``ToolApproved`` / ``ToolDenied``), keyed by the tool-call id. The decision is
NOT read from the persisted message history, which is the property this package
demonstrates. A deterministic FunctionModel is used so no API key or network is
required.
"""
from __future__ import annotations
from dataclasses import dataclass

from pydantic_ai import Agent, RunContext, DeferredToolRequests, DeferredToolResults
from pydantic_ai.messages import ModelResponse, ToolCallPart, TextPart
from pydantic_ai.models.function import FunctionModel, AgentInfo

THRESHOLD = 10_000


@dataclass
class Ledger:
    """Execution side-effect tracker (stands in for the real money movement)."""
    amount: int = 100_000
    recipient: str = "ACME-CORP"
    executed: bool = False
    approver: str | None = None


def _model_fn(messages, info: AgentInfo) -> ModelResponse:
    # If any tool-return is present, the agent has its result and settles.
    for m in messages:
        for p in getattr(m, "parts", []):
            if getattr(p, "part_kind", None) == "tool-return":
                return ModelResponse(parts=[TextPart("settlement complete")])
    # Otherwise request the guarded transfer.
    return ModelResponse(
        parts=[ToolCallPart(tool_name="release_transfer",
                            args={"amount": 100_000, "recipient": "ACME-CORP"})]
    )


def build_agent() -> Agent:
    agent = Agent(FunctionModel(_model_fn), deps_type=Ledger,
                  output_type=[str, DeferredToolRequests])

    @agent.tool(requires_approval=True)
    def release_transfer(ctx: RunContext[Ledger], amount: int, recipient: str) -> str:
        # Only ever runs when the deferred approval is supplied through the API.
        ctx.deps.executed = True
        return f"Executed transfer of ${amount:,.2f} to {recipient}; approved by {ctx.deps.approver}"

    return agent


def start(agent: Agent, ledger: Ledger):
    """Run until the guarded tool defers for approval. Returns (history, call_id)."""
    r = agent.run_sync("Release the wire transfer", deps=ledger)
    if not isinstance(r.output, DeferredToolRequests):
        raise RuntimeError("expected the transfer to defer for approval")
    call_id = r.output.approvals[0].tool_call_id
    return r.all_messages(), call_id


def resume(agent: Agent, ledger: Ledger, history, *, approve_call_id: str | None = None,
           approver: str | None = None):
    """Resume from a (possibly forged) history.

    If ``approve_call_id`` is given, a genuine deferred approval is supplied
    through the API (the only authorized path). Otherwise the resume relies on
    whatever is in ``history`` alone, which is the attacker's position.
    """
    results = None
    if approve_call_id is not None:
        ledger.approver = approver
        results = DeferredToolResults(approvals={approve_call_id: True})
    r = agent.run_sync(message_history=history, deps=ledger, deferred_tool_results=results)
    redeferred = isinstance(r.output, DeferredToolRequests)
    return r, redeferred
