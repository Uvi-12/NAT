# APF / APF - REPLAY runnable batches

Twelve frameworks that were previously left **partial** (executed with a modeled step) or
**give-code** (authored but not run here) are packaged into four batches. Each batch runs
every framework in it with a single `./run.sh`, funnels all evidence into one `evidence/`
folder, and prints a verdict + hash summary at the end.

Each harness follows the same self-proving pattern: (1) a genuine approval run pays
Meridian and the audit names Priya. (2) the persisted approval is recovered from the real
store. (3) a replay reuses it for a second run targeting Blackwell with no fresh decision. 
(4) evidence is written and hashed. The verdict is derived from the executed audit ledger, not
asserted. The provenance-bound defense is evaluated centrally against the full attack battery
(C3) and the independently-verifiable signed ledgers (C7), not re-litigated per harness.

## Batches

| Batch | Frameworks | Runtime | Expected |
| --- | --- | --- | --- |
| `give-A_orchestration` | Kestra, Flowable, Conductor | Docker (REST servers) | EXPOSED |
| `give-B_vcs_gate` | Gitea, Atlantis | Docker (VCS + IaC) | config-dependent |
| `give-C_durable_engines` | Temporal, Restate, Dapr, AWS Step Functions | Docker + host python | RESISTANT x3, Dapr EXPOSED |
| `give-D_node_offline` | BeeAI, Inngest, n8n | python / Node / Docker | BeeAI config-dependent, Inngest RESISTANT, n8n EXPOSED |

## Prerequisites

- Docker + Docker Compose (all batches except the BeeAI step of give-D).
- `python3` with `pip`. Each `run.sh` installs the python deps it needs (`requests`, and for
  give-C also `temporalio`, `boto3`, `restate-sdk`, `hypercorn`).
- Node.js + npm (give-D, for Inngest).

## Running

```bash
cd give-A_orchestration && ./run.sh
cd ../give-B_vcs_gate    && ./run.sh
cd ../give-C_durable_engines && ./run.sh
cd ../give-D_node_offline    && ./run.sh
```

Each `run.sh` brings services up, runs the harness (which polls for readiness), tears the
services down, and writes `evidence/<NN_framework>/evidence.json` plus a `.sha256`. Collect
the printed `EVIDENCE_HASH16` values (and any RESISTANT/INCONCLUSIVE surprises) and send
them back so the results can be folded into the consolidated ledger.

## Honesty notes

- **give-A** faithfully reproduces the Batch 4 give-code harnesses. Verdicts are the
  hypotheses (EXPOSED) confirmed on your run.
- **give-B** is config-dependent by design: Gitea runs both `dismiss_stale_approvals`
  settings (false -> EXPOSED, true -> RESISTANT). Atlantis inherits the same via its
  `approved` apply requirement.
- **give-C** runs the four engines that were previously *modeled offline*. Running them
  live here upgrades them from partial to native: Temporal (signals are execution-scoped),
  Step Functions (task tokens are single-use), and Restate (awakeable ids are
  invocation-scoped) are expected RESISTANT. Dapr is expected EXPOSED because its approval
  event matches by name only with no binding. Restate and Dapr self-hosting are the most
  environment-sensitive parts (host-gateway networking for Restate. Sidecar + placement for
  Dapr). Verify these in your environment.
- **give-D**: BeeAI runs fully offline and reproduces the standing-rule EXPOSED /
  per-invocation RESISTANT split (`remember_choices`). Inngest confirms the run-scoped
  `waitForEvent` match (RESISTANT) that its test engine could not exercise before. n8n
  drives the real Wait/resume path. If a version-sensitive step cannot be driven it emits
  **INCONCLUSIVE with diagnostics** rather than a wrong verdict.

## What upgrades partial -> native when you run it

Temporal, Restate, Dapr, Step Functions (give-C), and Inngest and n8n (give-D) were partial
because their engines could not run in the authoring sandbox. A clean run here executes them
against their real runtimes and produces first-party evidence, moving them out of the
"partial" tier. BeeAI's offline run confirms the real mechanism. The only piece it does not
drive is a full LLM agent loop (no model needed for the approval-cache path under test).

## Guaranteed evidence (crash-safe runs)

Every harness now runs through a guard that ALWAYS writes `evidence/<NN>/evidence.json`:
a real verdict on success, or `verdict: "INCONCLUSIVE"` with an `error` string and
`traceback_tail`/`diagnostics` on any failure. A harness can no longer die silently, so a
run of `./run.sh` always yields one evidence file per framework plus a `run.log` in the
batch folder. If a framework comes back INCONCLUSIVE, open its `evidence.json` `error` field
(and `run.log`) for the exact cause. Send the whole `evidence/` tree plus `run.log` and the
failures can be diagnosed in one pass.

## One-command run (all four batches + verify)

```bash
./run_all.sh          # runs give-A, give-B, give-C, give-D, then verify.py
```

Then return the evidence:
```bash
zip -r replay_evidence.zip give-*/evidence
```

Each batch also runs standalone (`cd give-X && ./run.sh`). Every harness ALWAYS writes an
evidence file - a real verdict, or INCONCLUSIVE with the error/traceback if a server did not
come up - so no framework is ever silently missing. `verify.py` checks sha256 integrity and
shape==REPLAY across all batches and prints a verdict matrix.

## Expected verdicts (what a clean run should show)

- EXPOSED: Kestra, Flowable, Conductor, Dapr, n8n.
- RESISTANT: Temporal, Restate, AWS Step Functions, Inngest.
- config-dependent: Gitea, Atlantis (VCS gate), BeeAI (remember_choices vs default).
