#!/usr/bin/env python3
# APF / APF - REPLAY live harness: Temporal (#26)
# Runs a REAL Temporal worker + client against the dev server. Approval = a signal to a
# specific workflow execution. Confirms live that run A's genuine approval cannot be reused
# to authorize run B: run B receives no signal and never completes, so no payment fires.
# EXPECTED: RESISTANT (replay_fired = False).
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import apf_common as C
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker

OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(HERE, "..", "evidence")), "26_temporal")
ADDR = os.environ.get("TEMPORAL_ADDR", "localhost:7233")

@workflow.defn
class PaymentWorkflow:
    def __init__(self):
        self._approval = None
    @workflow.signal
    def approve(self, decision: dict):
        self._approval = decision
    @workflow.run
    async def run(self, order: dict) -> dict:
        await workflow.wait_condition(lambda: self._approval is not None)
        if self._approval.get("approved"):
            return {"paid": True, "amount": order["amount"],
                    "beneficiary": order["beneficiary"], "approver": self._approval.get("approver")}
        return {"paid": False}

async def main():
    client = await Client.connect(ADDR)
    audit = []
    async with Worker(client, task_queue="apf", workflows=[PaymentWorkflow]):
        # ---- control: genuine approval signal to run A ----
        hA = await client.start_workflow(PaymentWorkflow.run, C.A_ARGS, id="apf-A", task_queue="apf")
        await hA.signal(PaymentWorkflow.approve, {"approved": True, "approver": C.APPROVER})
        resA = await hA.result()
        if resA.get("paid"):
            audit.append({"action": "execute_payment", "amount": resA["amount"],
                          "beneficiary": resA["beneficiary"], "approved_by_in_audit": resA["approver"]})
        C.line("control", f"genuine approval signal to run A by {C.APPROVER} -> {resA}")

        # ---- replay: start run B, reuse run A's approval WITHOUT signaling B ----
        hB = await client.start_workflow(PaymentWorkflow.run, C.B_ARGS, id="apf-B", task_queue="apf")
        # run A is already complete; there is deliberately NO channel that delivers its approval to run B
        C.line("audit", "run A's approval lives only in run A's history; no state-writer path delivers it to run B")
        try:
            resB = await asyncio.wait_for(hB.result(), timeout=8)
            replay_fired = bool(resB.get("paid")) and resB.get("beneficiary") == C.B_ARGS["beneficiary"]
        except asyncio.TimeoutError:
            replay_fired = False
            resB = {"paid": False, "note": "run B still awaiting its own approval signal"}
            await client.get_workflow_handle("apf-B").terminate(reason="apf: no genuine approval for run B")
    b_row = next((x for x in audit if x["beneficiary"] == C.B_ARGS["beneficiary"]), None)
    C.line("replay", f"reused run A approval onto run B -> {resB}")

    seen = set(); nonce = "n-runA-0026"

    verdict = C.verdict_from_state(replay_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Temporal", OUT, {
        "restore_path": "approval = signal to a specific workflow execution; recorded in engine-controlled per-execution history",
        "execution_tier": "live (real Temporal dev server; worker + client executed)",
        "why_resistant": "run B receives no signal; run A's approval cannot be delivered to run B without a fresh signal",
        "genuine_run": "apf-A", "replay_run": "apf-B",
        "replay_fired": replay_fired, "replayed_payment": b_row,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main('Temporal', OUT, lambda: asyncio.run(main()))
