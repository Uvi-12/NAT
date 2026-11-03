# Resistance is not a setup artifact: the symmetric two-reach test

The paper's central claim is that exposure is decided by **authoring topology** , 
who is allowed to author the evidence the resume path trusts, not by which
storage layer we happened to attack. The sharpest objection a reviewer can raise
is that this is circular: we forged the *exposed* systems at their persistence
layer and merely *argued* that the *resistant* ones hold, so "resistant" might
just mean "attacked more gently." This test answers that objection head-on, and
it does so **without moving any of the paper's verdicts**. It is reproduced by
**claim 9** (`bash claims/claim9/run.sh`, source in `artifact/exposure/symmetric/`).

## The design

We attack the whole durable / orchestration / CI-CD / code-review tail, the 9
exposed systems, the 2 conditional ones, and **all 11 resistant ones**, with one
write primitive and one success predicate (does the protected action execute on
resume?). The only thing that varies between systems is the documented consume
predicate. We hold the adversary's *reach* constant and sweep it across exactly
two values that bracket the threat model:

- **Reach 1, application persistence (the paper's stated state-writer).** The
  writer holds application-persistence and recovery/integration roles: checkpoint
  rows, session fields, execution JSON, review values, lifecycle status,
  confirmation rules, and the *app-configured* workflow stores (Dapr's app-owned
  Redis, Airflow's metadata DB). It does **not** hold the workflow engine's own
  internal datastore credentials, nor server-filesystem write, nor any secret,
  key, signature, live authentication, or host code execution.
- **Reach 2, engine datastore (a strictly stronger sensitivity adversary).**
  Everything in Reach 1, plus write access to the engine's own datastore /
  server-managed log / server filesystem (Temporal's history DB, a NoteDb ref on
  the Gerrit server, Jenkins' CPS program state). Still no secret, key,
  signature, live auth, or host exec.

The verdict under each reach is **computed**, not asserted.

## Result 1, the paper's verdicts are not a setup artifact

Under **Reach 1, the adversary the paper actually defines, every one of the 22
systems reproduces its published verdict**:

| Decisive-evidence class | Reach 1 | Verdict | Systems |
| --- | --- | --- | --- |
| app read-back value | fires | **Exposed** (9) | Airflow, Flowable, Conductor, Kogito, SpiffWorkflow, Kestra, DBOS, midPoint, Gitea |
| app store, under the stated persistence condition | fires | **Conditional** (2) | Dapr Workflow, Azure Durable Functions |
| engine-mediated (behind the engine's own store, unsigned) | blocked | **Resistant** (6) | Temporal, Restate, Inngest, Gerrit, Jenkins, GoCD |
| capability-anchored (secret / live-revalidated) | blocked | **Resistant** (5) | AWS Step Functions, Prefect, PydanticAI, BeeAI, Mastra |

The point is that the **same application-persistence write** that forges all 9
exposed systems is applied, unchanged, to all 11 resistant ones, and fails on
every one. The attack surface is provably identical at the stated reach. The only
variable is the consume predicate. So the difference in outcome *is* authoring
topology, by construction. The battery asserts this directly: if any system's
Reach-1 verdict disagreed with its published corpus verdict, it prints `MISMATCH`
and exits non-zero. It does not.

## Result 2, exactly which resistant verdicts depend on what

Sweeping to **Reach 2** does not change any headline count. It *characterises* the
11 resistant verdicts by the capability each one actually depends on:

- **Engine-store dependent (6): Temporal, Restate, Inngest, Gerrit, Jenkins,
  GoCD.** These hold under the stated adversary because their decisive evidence
  lives behind the engine's own datastore or server filesystem, which Reach 1
  cannot write. They are **not** cryptographically bound, a server-sequenced
  event or an identity-labelled commit is integrity-checked by bookkeeping, not a
  signature, so under Reach 2 a full write to the engine store forges them, and
  they degrade to Conditional. This is the honest ceiling of their resistance:
  it rests on the engine datastore staying outside the writer's scope.
- **Capability-anchored (5): AWS Step Functions, Prefect, PydanticAI, BeeAI,
  Mastra.** These hold under **both** reaches, because their decisive evidence is
  not a stored value at all: a per-execution task token re-checked on a live call
  (SFN), or fresh input supplied and revalidated at resume rather than read back
  from any snapshot (the other four). No amount of store write, application or
  engine, manufactures it.

## Native corroboration

Two of the engine-store-dependent verdicts are backed by native runs under
`artifact/exposure/native/` (framework-requiring, not part of the gated
crypto-only suite):

- **Temporal** (`APF-Temporal-native/`, real `temporalio` SDK): a forged
  `WorkflowExecutionSignaled('approve')` event, plain history data, no secret or
  key, drives the real workflow to release the protected action on replay, while
  a naive jump straight to `WorkflowExecutionCompleted` is rejected by Temporal's
  own core as a nondeterminism error. This is the Reach-2 degradation, natively.
- **Gerrit NoteDb** (`APF-Gerrit-NoteDb-native/`, real `git` objects): a keyless
  state-writer authors a real `refs/changes/.../meta` commit carrying
  `Code-Review+2`. Under default (unsigned) NoteDb the submit path reads it and
  the forge succeeds, while under signed NoteDb the keyless forge fails
  verification. This is the Reach-2 result plus the documented resistant
  condition (signed-push) on the same row.

## What this means for the paper

The headline **26 exposed / 3 conditional / 1 transitive / 11 resistant / 2 N/A**
is unchanged, it is the Reach-1 column. The test adds two things: a direct
refutation of the "setup artifact" objection (identical attack surface at the
stated reach), and a precise, falsifiable map of what each resistant verdict
costs an attacker. It also motivates a one-sentence clarification to the threat
model (§3.1): state explicitly that the writer holds application-persistence and
recovery/integration roles but not the workflow engine's own datastore
credentials or host execution. With that sentence, the Dapr-vs-Temporal split
(conditional vs resistant) is manifestly consistent, both are judged at the same
reach, rather than resting on an unstated scoping assumption.
