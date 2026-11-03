# ga-n8n

Integrity analysis for n8n's persisted execution-data (resume) surface.

## Summary

n8n persists each node's output in the execution record
(`execution_entity.data.resultData.runData`). On resume, the engine restores that data
and feeds a node's persisted output to its children. This package shows that a node
output which gates a downstream action is trusted on resume **without any integrity
verification**.

A `Gate` node's output records the approval decision. A downstream `Execute` node runs
the transfer only if the gate output says `approved`. Editing the persisted gate output
to `approved=true` is sufficient for the engine to run the Execute node as approved.

The property demonstrated is binary:

- **Persisted gate output `approved=false`** → the Execute node rejects. The transfer
  stays blocked.
- **Persisted gate output `approved=true`** (forged) → the Execute node executes the
  transfer, attributed to an attacker-chosen approver.

The resume path is the real `WorkflowExecute.runPartialWorkflow2` engine call, which
consumes the persisted `runData` as downstream input. No integrity check is performed on
the loaded execution data.

## Scope (important)

n8n has two resume surfaces, and this package targets the vulnerable one:

- **Resistant:** the canonical Wait-node + resume-webhook pattern derives the decision
  from the live webhook body at resume time, not from persisted state.
- **Vulnerable (this package):** when the decision is a node output **persisted upstream
  of the pause**, that restored output is trusted on resume with no integrity check.

The finding is scoped to the persisted-upstream-output surface.

## Install & run

```bash
npm install
npm run demo     # start, control resume, forge, resume
npm test         # integrity tests (node --test)
```

Requires Node 18+, `n8n-core`, `n8n-workflow`.

## Expected demo output

```
== start ==
started transfer amount=$100,000.00 status=unapproved (awaiting approval)
== resume (control) ==
resumed status=REJECTED approved=false executed=false approver=""
  [BLOCKED] Transfer rejected; gate output approved=false.
== forge ==
forged persisted gate output approved=true approver="Rahul S. (Senior Compliance Officer) [14:32:01]"
== resume ==
resumed status=EXECUTED approved=true executed=true approver="Rahul S. (Senior Compliance Officer) [14:32:01]"
  [EXECUTED] Wire transfer of $100,000.00 to ACME-CORP; approved by Rahul S. (Senior Compliance Officer) [14:32:01].
```

## How it works

`ga-n8n/src/forge.cjs` edits the persisted gate output in the execution data:

```js
runData["Gate"][0].data.main[0][0].json.approved = true;
```

On resume the real engine consumes it:

```js
new WorkflowExecute(additionalData, 'manual')
  .runPartialWorkflow2(workflow, runData, {}, [], { nodeName: 'Execute', mode: 'inclusive' });
```

`runPartialWorkflow2` locates the node whose output is in `runData` and feeds it to its
children, so the Execute node receives the forged gate output.

## Defense

The provenance-bound defense is not re-litigated in this per-system PoC. It is evaluated centrally against the full attack battery (Forge / Rebind / Replay / Suppress / Launder, plus a concurrent race) and the independently-verifiable signed ledgers, claims C3 and C7 of the artifact.

## Layout

```
src/
  workflow.cjs   node types, workflow, runData helpers, real-engine settle()
  store.cjs      JSON store standing in for execution_entity.data
  forge.cjs      forge the persisted gate output
  cli.cjs        start / status / forge / resume / demo
test/
  integrity.test.cjs
examples/
  run_demo.cjs
```

## Scope

A research artifact for evaluating HITL execution-data integrity. It drives the real
`WorkflowExecute` engine with inline node types and a JSON store standing in for the
execution record. The workflow steps are deterministic so no external services are
needed. The required capability is the ability to write the persisted execution data. 
the finding is that n8n trusts a restored upstream node output on resume with no
integrity check. Use only against systems you are authorized to test.
