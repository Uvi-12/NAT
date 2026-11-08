#!/usr/bin/env python3
"""APF native reproduction against the real Temporal SDK (temporalio), history
layer, no external server required.

This runs the REAL Temporal Python workflow code through the SDK's own
`Replayer` -- the exact deterministic resume path a Temporal worker executes
when it rebuilds a workflow from persisted event history. We construct the event
history with the SDK's own protobuf types (temporalio.api.history.v1), i.e. the
documented persistence format, and ask: can a state-writer who can write history
but holds no secret, key, or signature release a human-gated action on resume?

Three histories are replayed against one unmodified workflow:

  1. control        -- paused workflow, no approval signal in history.
  2. forged-signal  -- the state-writer appends a well-formed
                       WorkflowExecutionSignaled('approve') event (plain history
                       data; no secret/key/signature) and the following task.
  3. forged-done    -- the state-writer instead jumps the workflow straight to
                       WorkflowExecutionCompleted WITHOUT an approving signal.

Expected (and asserted):
  1. replays cleanly, workflow does NOT complete  -> protected action blocked.
  2. replays cleanly, workflow COMPLETES("PAYMENT_RELEASED") -> forge succeeds.
  3. FAILS the SDK's nondeterminism check -> you cannot reach completion without
     authoring the signal event; a lone "mark it done" write is rejected.

Honest verdict: native evidence for the C9 two-reach sensitivity test. The corpus
verdict is Resistant at the stated reach (application persistence cannot reach
Temporal's own history store). Temporal does not cryptographically sign history,
so under engine-datastore reach (Reach 2) case 2 shows a full write that
reconstructs the signal event forges approval, while case 1 vs 3 shows a naive
flip-to-done does not (the full event envelope is required). Resistance therefore
rests on the history store staying outside the writer's scope, not on an authoring
authority the state-writer lacks -- i.e. engine-store dependent.

Requires: pip install temporalio    Run: python3 run.py
"""
import asyncio, datetime, json, sys
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer
from temporalio.api.history.v1 import (
    History, HistoryEvent,
    WorkflowExecutionStartedEventAttributes as Started,
    WorkflowTaskScheduledEventAttributes as TaskSched,
    WorkflowTaskStartedEventAttributes as TaskStart,
    WorkflowTaskCompletedEventAttributes as TaskDone,
    WorkflowExecutionSignaledEventAttributes as Signaled,
    WorkflowExecutionCompletedEventAttributes as Completed,
)
from temporalio.api.common.v1 import WorkflowType, Payloads, Payload
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.enums.v1 import EventType as ET
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.duration_pb2 import Duration


@workflow.defn
class ApprovalWorkflow:
    """A paused, human-gated workflow: the protected action (returning
    PAYMENT_RELEASED) runs only after an `approve` signal is received."""
    def __init__(self):
        self._approved = False

    @workflow.run
    async def run(self) -> str:
        await workflow.wait_condition(lambda: self._approved)
        return "PAYMENT_RELEASED"   # the protected action

    @workflow.signal
    def approve(self):
        self._approved = True


def ts(i):
    t = Timestamp(); t.FromDatetime(datetime.datetime(2026, 1, 1, 0, 0, i)); return t

def payloads(val):
    return Payloads(payloads=[Payload(metadata={"encoding": b"json/plain"},
                                      data=json.dumps(val).encode())])

def ev(eid, etype, field, attr):
    e = HistoryEvent(event_id=eid, event_time=ts(eid), event_type=etype)
    getattr(e, field).CopyFrom(attr); return e

def base():
    return [
        ev(1, ET.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED,
           "workflow_execution_started_event_attributes",
           Started(workflow_type=WorkflowType(name="ApprovalWorkflow"),
                   task_queue=TaskQueue(name="q"),
                   workflow_task_timeout=Duration(seconds=10),
                   original_execution_run_id="run1",
                   first_execution_run_id="run1", attempt=1)),
        ev(2, ET.EVENT_TYPE_WORKFLOW_TASK_SCHEDULED,
           "workflow_task_scheduled_event_attributes",
           TaskSched(task_queue=TaskQueue(name="q"),
                     start_to_close_timeout=Duration(seconds=10), attempt=1)),
        ev(3, ET.EVENT_TYPE_WORKFLOW_TASK_STARTED,
           "workflow_task_started_event_attributes", TaskStart(scheduled_event_id=2)),
        ev(4, ET.EVENT_TYPE_WORKFLOW_TASK_COMPLETED,
           "workflow_task_completed_event_attributes",
           TaskDone(scheduled_event_id=2, started_event_id=3)),
    ]

def signal_tail():
    return [
        ev(5, ET.EVENT_TYPE_WORKFLOW_EXECUTION_SIGNALED,
           "workflow_execution_signaled_event_attributes",
           Signaled(signal_name="approve", input=payloads(None))),
        ev(6, ET.EVENT_TYPE_WORKFLOW_TASK_SCHEDULED,
           "workflow_task_scheduled_event_attributes",
           TaskSched(task_queue=TaskQueue(name="q"),
                     start_to_close_timeout=Duration(seconds=10), attempt=1)),
        ev(7, ET.EVENT_TYPE_WORKFLOW_TASK_STARTED,
           "workflow_task_started_event_attributes", TaskStart(scheduled_event_id=6)),
        ev(8, ET.EVENT_TYPE_WORKFLOW_TASK_COMPLETED,
           "workflow_task_completed_event_attributes",
           TaskDone(scheduled_event_id=6, started_event_id=7)),
        ev(9, ET.EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED,
           "workflow_execution_completed_event_attributes",
           Completed(result=payloads("PAYMENT_RELEASED"),
                     workflow_task_completed_event_id=8)),
    ]

def completed_without_signal():
    # state-writer jumps straight to "completed" with no approving signal event
    return [ev(5, ET.EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED,
               "workflow_execution_completed_event_attributes",
               Completed(result=payloads("PAYMENT_RELEASED"),
                         workflow_task_completed_event_id=4))]

CASES = {
    "control (no signal)":          base(),
    "forged-signal (state write)":  base() + signal_tail(),
    "forged-done (no signal event)": base() + completed_without_signal(),
}


async def replay(name, events):
    completed = any(e.event_type == ET.EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED
                    for e in events)
    try:
        await Replayer(workflows=[ApprovalWorkflow]).replay_workflow(
            WorkflowHistory("wf1", events))
        return ("OK", completed, None)
    except Exception as e:
        msg = repr(getattr(e, "__cause__", None)) or repr(e)
        return ("REJECTED", completed, msg[:120])


async def main():
    print("Temporal native replay (real temporalio SDK, history layer)\n")
    ok = True
    for name, events in CASES.items():
        status, completed, err = await replay(name, events)
        if name.startswith("control"):
            good = (status == "OK" and not completed)
            verdict = "blocked (workflow still paused, protected action NOT run)"
        elif name.startswith("forged-signal"):
            good = (status == "OK" and completed)
            verdict = "FORGE SUCCEEDS (protected action executed on resume)"
        else:
            good = (status == "REJECTED")
            verdict = "rejected by SDK nondeterminism (cannot complete w/o signal)"
        ok &= good
        print(f"  {name:32} {status:9} -> {verdict}"
              + (f"\n      [{err}]" if err else ""))
    print("\nFinding: a well-formed WorkflowExecutionSignaled event (no secret,")
    print("key, or signature) drives the real workflow to the protected action;")
    print("a naive flip-to-completed is rejected. Native evidence for the C9")
    print("engine-datastore (Reach-2) degradation; corpus verdict is Resistant")
    print("at the stated application-persistence reach.")
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
