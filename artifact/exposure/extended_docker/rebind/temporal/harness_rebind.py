#!/usr/bin/env python3
# APF / APF - REBIND live harness: Temporal (#26).
# The workflow input (order) is recorded in Temporal's engine-owned, append-only event history.
# The approve signal carries only the decision. A state writer has NO API to alter a running
# execution's input, and a crafted signal cannot inject arguments (the workflow reads order from
# its frozen input, not the signal), so the mutated argument cannot run under the one approval.
# EXPECTED: RESISTANT.
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
        # control: genuine approval of args A
        hA = await client.start_workflow(PaymentWorkflow.run, C.A_ARGS, id="apf-A", task_queue="apf")
        await hA.signal(PaymentWorkflow.approve, {"approved": True, "approver": C.APPROVER})
        resA = await hA.result()
        if resA.get("paid"):
            audit.append({"action": "execute_payment", "amount": resA["amount"], "beneficiary": resA["beneficiary"], "approved_by_in_audit": resA["approver"]})
        C.line("control", f"genuine approval signal to run A by {C.APPROVER} -> {resA}")
        C.line("audit", "input recorded in engine-owned history; approve signal is decision-only (cannot carry args)")
        # rebind: Priya reviews Meridian; a state writer crafts a signal carrying B args - the workflow ignores them
        hR = await client.start_workflow(PaymentWorkflow.run, C.A_ARGS, id="apf-R", task_queue="apf")
        await hR.signal(PaymentWorkflow.approve, {"approved": True, "approver": C.APPROVER,
                        "amount": C.B_ARGS["amount"], "beneficiary": C.B_ARGS["beneficiary"]})
        resR = await hR.result()
        rebind_fired = bool(resR.get("paid")) and resR.get("beneficiary") == C.B_ARGS["beneficiary"]
        if rebind_fired:
            audit.append({"action": "execute_payment", "amount": resR["amount"], "beneficiary": resR["beneficiary"], "approved_by_in_audit": resR["approver"]})
        C.line("rebind", f"crafted signal with B args + frozen history input -> {resR}")
    nonce = "n-rebind-0026"
    verdict = C.verdict_rebind(rebind_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Temporal", OUT, {
        "shape": "REBIND",
        "restore_path": "workflow input in engine-owned append-only history; approve signal decision-only; no state-writer arg mutation path",
        "execution_tier": "live (real Temporal dev server; worker + client executed)",
        "genuine_args": C.A_ARGS, "mutated_args": C.B_ARGS,
        "rebind_fired": rebind_fired, "rebound_payment": None,
        "audit_ledger": audit, "verdict": verdict})
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        C.guarded_main("Temporal", OUT, lambda: (_ for _ in ()).throw(e))
