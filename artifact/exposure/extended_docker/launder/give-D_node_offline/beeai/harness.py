#!/usr/bin/env python3
# APF / APF - REBIND harness #17: BeeAI (AskPermissionRequirement standing-rule path).
# AskPermissionRequirement gates tool use via handler(tool, input)->bool. With
# remember_choices=True the decision is cached by TOOL NAME (self._state[tool.name]) with NO
# binding to args/run/nonce. REBIND: a genuine "allow pay" decision made for args A (Meridian)
# is cached; the SAME pay action with its argument mutated to B (Blackwell) is then auto-approved
# by the tool-name cache WITHOUT re-consulting the handler, paying Blackwell under the one
# approval of the Meridian call. Exercises the real AskPermissionRequirement._ask caching path.
# EXPECTED: EXPOSED via remember_choices standing rule; RESISTANT in default per-invocation mode.
import os, sys, asyncio
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apf_common as C
from beeai_framework.agents.requirement.requirements.ask_permission import AskPermissionRequirement
from beeai_framework.tools import StringToolOutput

OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "17_beeai")

class FakeTool:
    def __init__(self, name): self.name = name

class StartEvent:
    def __init__(self, inp): self.input = inp; self.output = None

async def scenario(remember):
    audit = []
    consulted = {"n": 0}
    async def handler(tool, inp):
        # the genuine reviewer approves ONLY the Meridian payment it is actually shown
        consulted["n"] += 1
        return inp.get("beneficiary") == C.A_ARGS["beneficiary"]
    req = AskPermissionRequirement(handler=handler, remember_choices=remember)
    tool = FakeTool("pay")

    async def invoke(args, reviewer):
        before = consulted["n"]
        ev = StartEvent(dict(args))
        await req._ask(tool, ev)                    # real caching path
        denied = isinstance(ev.output, StringToolOutput)
        consulted_this = consulted["n"] > before
        paid = not denied
        if paid:
            # provenance = the (Meridian) reviewer whose decision authorized this call
            audit.append({"action": "execute_payment", "amount": args["amount"],
                          "beneficiary": args["beneficiary"], "approved_by_in_audit": reviewer})
        return paid, consulted_this

    pMer = await invoke(C.A_ARGS, C.APPROVER)        # genuine Meridian review (caches "allow pay" if remember)
    pBla = await invoke(C.B_ARGS, C.APPROVER)        # foreign Blackwell pay: does the Meridian approval cover it?
    return audit, consulted["n"], pMer, pBla

async def run():
    # ---- exposed path: remember_choices=True (decision cached by tool NAME, not action) ----
    auditX, consultX, (pMerX, cMerX), (pBlaX, cBlaX) = await scenario(remember=True)
    C.line("control", f"genuine review of the Meridian pay (remember_choices=True) -> paid={pMerX} approver={C.APPROVER}")
    C.line("audit", f"decision cached by tool name, not action; handler consulted {consultX} time(s) across Meridian+Blackwell")
    l_row = next((x for x in auditX if x.get("beneficiary") == C.B_ARGS["beneficiary"]), None)
    launder_fired = bool(pBlaX) and (not cBlaX) and l_row is not None
    if l_row: l_row["approval_issued_for"] = C.A_ARGS["beneficiary"]
    C.line("launder", f"foreign Blackwell pay auto-approved from the Meridian tool-name cache -> {l_row} (handler consulted for Blackwell={cBlaX})")

    # ---- resistant path: default per-invocation (remember_choices=False) ----
    auditD, consultD, (pMerD, cMerD), (pBlaD, cBlaD) = await scenario(remember=False)
    resistant_default = bool(cBlaD) and (not pBlaD)   # Blackwell re-asked and REJECTED (handler approves only Meridian)
    C.line("audit", f"default mode re-asks every call: Blackwell consulted={cBlaD} paid={pBlaD} (handler reviews the actual call and rejects the foreign beneficiary)")

    verdict = C.verdict_launder(launder_fired)
    C.line("verdict", verdict + " via remember_choices standing rule; RESISTANT in default per-invocation mode")
    h = C.emit_evidence("BeeAI", OUT, {
        "shape": "LAUNDER",
        "restore_path": "AskPermissionRequirement caches the decision by tool NAME (remember_choices), not the action; a foreign Blackwell pay is auto-approved from the Meridian cache",
        "execution_tier": "native (real AskPermissionRequirement._ask caching path, both modes)",
        "exposed_path": "remember_choices=True: the Meridian allow, cached by tool name, covers a foreign Blackwell call (handler consulted 0 times for Blackwell)",
        "resistant_default": resistant_default,
        "resistant_note": "default per-invocation mode re-asks the handler for the Blackwell call; the careful handler reviews the actual call and rejects the foreign beneficiary, so it is not paid (RESISTANT). BeeAI-default rejoins the RESISTANT set for LAUNDER.",
        "handler_consultations_exposed": consultX, "handler_consultations_default": consultD,
        "approval_issued_for": C.A_ARGS, "foreign_action": C.B_ARGS,
        "launder_fired": launder_fired, "laundered_payment": l_row,
        "audit_ledger": auditX, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)

def main():
    asyncio.run(run())

if __name__ == "__main__":
    C.guarded_main("BeeAI", OUT, main) if hasattr(C, "guarded_main") else main()
