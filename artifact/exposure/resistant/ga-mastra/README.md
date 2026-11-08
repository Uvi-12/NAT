# ga-mastra

Integrity analysis for Mastra workflow suspend/resume state, **a resistant case**.

## Summary

This package is the falsifiability anchor for the Decision-Provenance Integrity (DPI)
study. It applies the same forge that succeeds against checkpoint-trusting frameworks , 
load the persisted snapshot, set the approval step's persisted output to
`approved=true`, write it back through the storage API, and shows that **Mastra does
not honour it**.

Mastra pauses a workflow with `suspend()` and resumes it with `run.resume({ step,
resumeData })`. The decision is taken from the live `resumeData`, validated against the
step's `resumeSchema`, at resume time. The persisted snapshot holds a `suspendOutput`
placeholder, but it is never consulted as the decision. Under the DPI predicate , 
*is the decision persisted as trusted state, or re-derived from a validated live input
on resume?*, Mastra falls on the **re-derived** side, and resists.

Observed behaviour:

- **Forge the persisted output, then resume with no live decision** → resume is
  rejected (`Invalid resume data`). The forged output is ignored.
- **Forge the persisted output `approved=true`, then resume with a live decision of
  `approved=false`** → the transfer is **blocked**. The live decision wins.
- **Resume with a legitimate live `approved=true`** → executes (the workflow is
  functional. Only the forge is ineffective).

## Why it resists

The resume contract re-derives the decision from validated live input rather than
trusting persisted state. This is the structural property that distinguishes resistant
frameworks from vulnerable ones: the persisted snapshot is not an authorization surface
because nothing downstream treats it as the decision of record.

## Install & run

```bash
npm install
npm run demo     # attempt the forge; observe it fail
npm test         # resistance tests (node --test)
```

Requires Node 18+, `@mastra/core ^1.41.0`, `@mastra/libsql ^1.12.1`.

## Expected demo output

```
== start ==
started run=........ status=suspended
== forge snapshot (set persisted output approved=true) ==
persisted output now: approved=true approver="Rahul S. (Senior Compliance Officer) [14:32:01]"
== resume relying on the forged snapshot (no live decision) ==
  status=REJECTED executed=false
  resume rejected: Invalid resume data: ...
== resume with a live decision = REJECT (forged output present) ==
  status=success executed=false
  [BLOCKED] Transfer rejected; no approval.
```

## Layout

```
├── src/
│   ├── workflow.mjs        suspend/resume approval workflow + Mastra factory
│   ├── forge.mjs           attempts the snapshot forge (ineffective against Mastra)
│   └── resume.mjs          resume with / without a live decision
├── test/
│   └── resistance.test.mjs forge-fails and live-decision-wins assertions
└── examples/
    └── run_demo.mjs
```

## Scope

A research artifact for evaluating HITL state integrity. It uses a local LibSQL store
and deterministic, offline steps. No model API key is needed. The point of this package
is the negative result: it demonstrates, against the real framework, that the forge does
not transfer to a framework whose resume contract validates live input. Use only against
systems you are authorized to test.
