# BeeAI replay harness (AskPermissionRequirement standing-rule path).
# Restore path: AskPermissionRequirement gates tool use via a handler(tool, input)->bool.
# With remember_choices=True the decision is cached by TOOL NAME (self._state[tool.name]),
# with no binding to args/run/nonce, and reused for every later invocation without
# re-asking. APF replay: a genuine "allow pay" decision made for run A (Meridian) is
# cached and silently reused to authorize run B (Blackwell) with no fresh decision.
# This harness exercises the real AskPermissionRequirement._ask caching path (the same
# path the RequirementAgent drives on each tool "start" event), both in the exposed
# standing-rule mode and the resistant default per-invocation mode.
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apf_common as C
from beeai_framework.agents.requirement.requirements.ask_permission import AskPermissionRequirement
from beeai_framework.tools import StringToolOutput

OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence")), "17_beeai")

class FakeTool:
    def __init__(self, name): self.name = name

class StartEvent:
    def __init__(self, inp): self.input = inp; self.output = None

async def scenario(remember):
    audit = []
    consulted = {"n": 0}
    async def handler(tool, inp):
        # a careful human/handler: approves the Meridian payment it is shown
        consulted["n"] += 1
        return inp.get("beneficiary") == C.A_ARGS["beneficiary"]
    req = AskPermissionRequirement(handler=handler, remember_choices=remember)
    tool = FakeTool("pay")

    async def invoke(args):
        ev = StartEvent(dict(args))
        await req._ask(tool, ev)                    # real caching path
        denied = isinstance(ev.output, StringToolOutput)
        if not denied:
            audit.append({"action": "execute_payment", "amount": args["amount"],
                          "beneficiary": args["beneficiary"], "approved_by_in_audit": C.APPROVER})
        return not denied

    paidA = await invoke(C.A_ARGS)                  # genuine approval of Meridian
    paidB = await invoke(C.B_ARGS)                  # reuse attempt for Blackwell
    return audit, consulted["n"], paidA, paidB

async def main():
    # exposed path: standing rule (remember_choices=True)
    auditX, consultX, pA_X, pB_X = await scenario(remember=True)
    C.line("control", f"genuine approval of Meridian (remember_choices=True) -> paid={pA_X}")
    C.line("audit", f"permission cached by tool name; handler consulted {consultX} time(s) across both runs")
    replay_fired = pB_X and consultX == 1           # Blackwell paid without a fresh consultation
    b_row = next((x for x in auditX if x["beneficiary"] == C.B_ARGS["beneficiary"]), None)
    C.line("replay", f"reused cached approval for run B (Blackwell) -> {b_row}")

    # resistant path: default per-invocation (remember_choices=False)
    auditD, consultD, pA_D, pB_D = await scenario(remember=False)
    resistant_default = (consultD == 2) and (not pB_D)   # re-asked; Blackwell rejected on its own args
    C.line("audit", f"default mode re-asks every invocation: handler consulted {consultD} time(s); Blackwell paid={pB_D}")

    seen = set(); nonce = "n-runA-0017"

    verdict = C.verdict_from_state(replay_fired)
    C.line("verdict", verdict + " via remember_choices standing rule; RESISTANT in default per-invocation mode")
    h = C.emit_evidence("BeeAI", OUT, {
        "shape": "REPLAY",
        "restore_path": "AskPermissionRequirement handler decision cached by tool name (remember_choices), reused across invocations with no args/run binding",
        "exposed_path": "remember_choices=True (standing rule): one approval of pay reused for a different payment",
        "resistant_default": resistant_default,
        "handler_consultations_exposed": consultX, "handler_consultations_default": consultD,
        "replay_fired": replay_fired, "replayed_payment": b_row,
        "audit_ledger": auditX, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)

C.guarded_main('BeeAI', OUT, lambda: asyncio.run(main()))
