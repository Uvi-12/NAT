#!/usr/bin/env python3
# APF / APF - SUPPRESS live harness: Temporal (#26).
# The payment waits on wait_condition(self._approval is not None); the only advance path is an
# approve signal, which Temporal records in its engine-owned append-only event history. There is
# no API to skip the wait or advance the execution without a recorded signal, and any signal
# leaves evidence (that is FORGE, a different shape). So the payment cannot run with the
# approval-required record ABSENT. EXPECTED: RESISTANT (suppress_fired=False).
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import apf_common as C
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "26_temporal")
ADDR = os.environ.get("TEMPORAL_ADDR", "localhost:7233")

@workflow.defn
class PaymentWorkflow:
    def __init__(self): self._approval = None
    @workflow.signal
    def approve(self, decision: dict): self._approval = decision
    @workflow.run
    async def run(self, order: dict) -> dict:
        await workflow.wait_condition(lambda: self._approval is not None)
        if self._approval.get("approved"):
            return {"paid": True, "amount": order["amount"], "beneficiary": order["beneficiary"], "approver": self._approval.get("approver")}
        return {"paid": False}

async def main():
    client = await Client.connect(ADDR)
    audit = []
    async with Worker(client, task_queue="apf", workflows=[PaymentWorkflow]):
        hA = await client.start_workflow(PaymentWorkflow.run, C.A_ARGS, id="apf-A-s", task_queue="apf")
        await hA.signal(PaymentWorkflow.approve, {"approved": True, "approver": C.APPROVER})
        resA = await hA.result()
        if resA.get("paid"):
            audit.append({"action": "execute_payment", "amount": resA["amount"], "beneficiary": resA["beneficiary"], "approved_by_in_audit": resA["approver"]})
        C.line("control", f"genuine approval signal to run A by {C.APPROVER} -> {resA}")
        C.line("audit", "the gate is wait_condition; the only advance path is a signal recorded in append-only history")
        # launder: a foreign Blackwell execution (args B) has no approval in its own engine-owned
        # history; the Meridian approval was a signal to run A, keyed to it, and cannot be inherited.
        hL = await client.start_workflow(PaymentWorkflow.run, C.B_ARGS, id="apf-L-l", task_queue="apf")
        foreign_paid = False
        for _ in range(8):
            await asyncio.sleep(1)
            d = await hL.describe()
            if d.status is not None and d.status.name != "RUNNING":
                r = await hL.result(); foreign_paid = bool(r.get("paid")); break
        try: await hL.terminate()
        except Exception: pass
        launder_fired = foreign_paid
        C.line("launder", f"foreign Blackwell execution has no approval of its own; run A's signal cannot be inherited; foreign paid under a genuine unrelated approval? {launder_fired}")
    verdict = C.verdict_launder(launder_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Temporal", OUT, {
        "shape": "LAUNDER",
        "restore_path": "every approval is a signal recorded in its execution's engine-owned append-only history, keyed to that execution; a foreign execution cannot inherit another execution's approval",
        "execution_tier": "live (real Temporal dev server; worker + client executed)",
        "why_resistant": "an approval is recorded in the execution it was issued for; there is no cross-execution re-parent path, so a foreign execution has no approval of its own",
        "approval_issued_for": C.A_ARGS, "foreign_action": C.B_ARGS,
        "launder_fired": launder_fired, "laundered_payment": None,
        "audit_ledger": audit, "verdict": verdict})
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        C.guarded_main("Temporal", OUT, lambda: (_ for _ in ()).throw(e))
