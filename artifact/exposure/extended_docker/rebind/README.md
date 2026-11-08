# APF / "APF" - REBIND: conclude package

This package runs every framework that **could not be executed natively** in the build sandbox
because it needs Docker or a live dev-server. Running it on your laptop produces the live
evidence hashes that close the REBIND shape.

**REBIND** = a single genuine approval is obtained for argument values **A**, then the argument
is mutated to **B** and the gated action executes **B** under A's one approval. In every harness:
- genuine approver = **Priya**
- approved (A) = pay **50,000** to **Meridian Supplies Ltd**
- mutated (B) = pay **250,000** to **Blackwell Trading LLC**

Each harness runs a **control** arm (genuine approval of A pays Meridian) and a **rebind** arm
(argument mutated to B under the one approval). The provenance-bound defense is evaluated centrally against the full attack battery (C3) and the independently-verifiable signed ledgers (C7), not re-litigated per harness.

## What's included (11 frameworks)

| dir | framework | tier | expected verdict | REBIND mechanic |
| --- | --- | --- | --- | --- |
| `34_kestra` | Kestra | REST give-code | EXPOSED\* | payment reads args from the KV store, `onResume` is decision-only. Mutate the KV over REST |
| `35_flowable` | Flowable | REST give-code | EXPOSED | `${approved}` gate is not arg-bound. Mutate the amount/beneficiary process variable via REST |
| `36_conductor` | Conductor | REST give-code | EXPOSED | `SET_VARIABLE` seeds workflow variables. `pay` reads them. Mutate via the variables API |
| `41_gitea` | Gitea | VCS give-code | EXPOSED\* | approve the Meridian diff, swap the PR head to Blackwell, merge under the stale approval |
| `38_atlantis` | Atlantis | VCS give-code | EXPOSED\* | plan-swap under a stale VCS approval, `apply` trusts the approval |
| `temporal` | Temporal | durable | RESISTANT | workflow input in engine-owned append-only history, approve signal is decision-only |
| `stepfunctions` | AWS Step Functions | durable | RESISTANT | execution input is service-managed, token callback output is the approver's, not a state writer's |
| `restate` | Restate | durable | RESISTANT | invocation input in append-only journal, awakeable is decision-only |
| `dapr` | Dapr Workflow | durable | EXPOSED | payment re-reads args from the Dapr **state store**, a state writer mutates the key via `/mutate` |
| `inngest` | Inngest | node | RESISTANT | payment reads args from the **frozen trigger event**, approval is decision-only (`match data.runId`) |
| `n8n` | n8n | node | EXPOSED (best-effort) | payment re-reads args from an external mutable source, the Wait-node resume is decision-only |

\* **config-dependent.** Kestra flips RESISTANT if the flow freezes its inputs at approval time
instead of re-reading the KV store. Gitea flips RESISTANT with `dismiss_stale_approvals=true`
(that setting **is** the argsHash-binding fix for the VCS gate). Atlantis then follows, because
its `apply` no longer sees a live approval after the head swap.

## Requirements

- **Docker** with Compose v2 (`docker compose ...`) - Docker Desktop on macOS is fine.
- **python3** (the runner installs `requests temporalio boto3 restate-sdk hypercorn` into your
  active environment. Use a venv if you prefer).
- **node + npm** (only for `inngest`, which uses `npx inngest-cli`).
- The durable/n8n engines assume `host.docker.internal` resolves from inside containers (default
  on Docker Desktop. On Linux add `--add-host=host.docker.internal:host-gateway` or an
  `extra_hosts` entry).

## Run it

```bash
cd conclude
./run.sh                 # run all 11, tear each stack down afterward
./run.sh kestra dapr     # run a subset by name (names are the dir stems above)
```

Everything writes to a **single evidence root**: `./evidence/<NN_framework>/evidence.json` (+ a
matching `.sha256`). The runner tees a full transcript to `./run.log` and finishes by calling
`./verify.sh`, which checks each file's sha256, confirms `shape == REBIND`, and prints a verdict
table. You can re-run `./verify.sh` any time.

Expected tally when everything drives cleanly: **7 EXPOSED** (Kestra, Flowable, Conductor, Gitea,
Atlantis, Dapr, n8n) and **4 RESISTANT** (Temporal, Step Functions, Restate, Inngest).

## Honesty notes

- **n8n is the least-certain live case.** The n8n live run was INCONCLUSIVE in the earlier REPLAY
  work (webhook/version sensitivity). This harness re-fetches the payment args from a small sink
  the harness controls and mutates that sink while the run is paused. If any version-sensitive
  step cannot be driven, the harness emits **INCONCLUSIVE** with diagnostics rather than a wrong
  verdict. Treat its EXPOSED result as best-effort confirmation of the modeled finding.
- **Conductor** exposes its `variables` mutation API in `conductor-oss` 3.x. On a build that
  lacks it the harness emits INCONCLUSIVE rather than guessing.
- **Gitea / Atlantis** are a genuine first live run for this project (the VCS give-code was never
  executed before), so their hashes are produced entirely by your run.
- The three **RESISTANT durable** engines demonstrate resistance the honest way: the harness
  *attempts* the mutation through the engine's own API (a crafted approval carrying B args) and
  shows the frozen, engine-owned argument is used anyway, so `rebind_fired = false`.
- Reference copies of the earlier REPLAY harnesses are **not** shipped here. Each directory
  contains only the REBIND harness (`harness_rebind.py` / `.mjs`).
