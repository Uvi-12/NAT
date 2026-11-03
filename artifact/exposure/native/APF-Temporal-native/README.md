# APF native reproduction, Temporal (history layer)

Native-tier (N1) reproduction against the real Temporal SDK (`temporalio`). It
runs the real workflow code through the SDK's own `Replayer`, the deterministic
resume path a worker executes when it rebuilds a workflow from persisted event
history, against histories we build with the SDK's own protobuf types
(`temporalio.api.history.v1`), i.e. the documented persistence format.

- **Dependency:** `pip install temporalio` (no external server. No network).
- **Run:** `python3 run.py`
- **What it shows:** a paused workflow's protected action stays blocked with no
  approval event. A state-writer who appends a well-formed
  `WorkflowExecutionSignaled('approve')` event (plain history data, no secret,
  key, or signature) drives the real workflow to the protected action on resume. 
  and a naive jump to `WorkflowExecutionCompleted` without an approving signal is
  rejected by the SDK's own nondeterminism check (`[TMPRL1100]`, printed by the
  Rust core as a WARN, that line is the rejection, not a failure of the run).
- **Verdict:** native evidence for the **Reach-2 (engine-datastore) degradation**
  in the two-reach sensitivity test (C9). The corpus verdict for Temporal is
  **Resistant at the stated reach** (application persistence, the state-writer
  cannot reach Temporal's own history store). This run shows that **if** the
  adversary additionally reaches the engine's history store, the verdict degrades
  to Conditional, because Temporal does not cryptographically sign history, a
  reconstructed signal event (no secret, key, or signature) forges approval. The
  naive jump-to-done is rejected by Temporal's own core. Resistance therefore
  rests on the history store staying outside the writer's scope, exactly as the
  sensitivity analysis states.

This is not a gated crypto-only claim (it needs `temporalio`). It is native
corroboration of the C9 engine-reach column for the Temporal row.
