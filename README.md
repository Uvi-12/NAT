# Artifact: *Nobody Approved This, Approval-Provenance Failure across Agentic AI, Workflows, and CI/CD*

This is the artifact for the IEEE S&P 2026 submission *"Nobody Approved This:
Approval-Provenance Failure across Agentic AI, Workflows, and CI/CD."* It lets a
reviewer reproduce the paper's central results on a commodity laptop, without
Docker and without any third-party service, in a few minutes.

The paper studies **Approval-Provenance Failure (APF)**: a resume-time
confused-deputy weakness in which a paused, human-gated workflow treats
approval-shaped *operational state* as proof that an authorized reviewer
approved the exact action about to run. An adversary who can write that state , 
a backup or migration job, a scoped database role, a sidecar, a queue consumer , 
but who cannot approve, cannot call the protected tool, holds no keys, and runs
no code, can make the workflow release a protected action under its own, more
privileged identity. The paper measures this across 43 version-pinned systems,
shows it is an architectural property (who is allowed to *author* the evidence
the resume path trusts), and gives a provenance-bound defense that we evaluate
with an adversarial battery and a per-binding ablation.

The artifact is organised so you can start with a 30-second offline check and go
as deep as you like from there. Nothing here attacks a real system: every
experiment runs against local, synthetic, in-process state.

## A.1 Description & Requirements

### What the artifact supports

Two results stand on their own and are the ones to check first, because they
*verify* rather than merely demonstrate:

* **The provenance-bound verifier (C3, C4).** The real verifier, the same code,
  not a mock, accepts exactly one genuine approval and rejects all five attack
  families (Forge, Rebind, Replay, Suppress, Launder) plus a 100-worker
  concurrent replay, and a per-binding ablation shows every one of its six
  bindings is necessary (removing any one reopens a specific attack). This is the
  defense, evaluated once, centrally, against the whole attack surface.
* **The signed evidence ledgers (C7).** The exported approval/guard ledgers verify
  offline from the embedded public key alone: the RFC 6962 Merkle root recomputes
  and the Ed25519 signed tree head checks out. An independent script
  (`scripts/verify_ledger.py`) re-derives both. Nothing is taken on trust.

The remaining results give the measurement and its honest caveats:

* the frozen 43-system corpus and its outcome accounting (Table in §4). 
* that an exposed resume path releases a protected action after a *state-only*
  forge while the same gate blocks beforehand (the exposure mechanism, §3–5) , 
  these per-system harnesses demonstrate *exposure only*. The defense is not
  re-litigated per harness, it is the central verifier above. 
* the audit result (C5), stated plainly as a structural identity (native records
  are byte-identical. The provenance separation is true-by-construction), and the
  local verification cost (C6).

### Security, privacy, and ethical concerns
None. The artifact contains no exploit against any third party, no credentials,
no personal data, and nothing that reaches the network. The "attacks" are writes
to a local, synthetic approval store that the harness itself creates in memory or
in a temp file. See `destructive.txt` and `use.txt`.

### How to access
The artifact is a self-contained directory tree (this repository). No external
download is required to run the core claims.

### Hardware dependencies
None special. Any x86-64 or arm64 machine with ~2 GB RAM. No GPU, no specific
CPU, no testbed. See `infrastructure/`, the "testbed" is a single commodity node.

### Software dependencies
* Python 3.9 or newer.
* For the mitigation and ledger claims (C3, C4, C6, C7): the `cryptography`
  package (`pip install cryptography`). This is the only hard dependency.
* Optional: `jsonschema` makes the audit experiment (C5) also exercise JSON-Schema
  acceptance. It degrades gracefully if absent.
* The offline exposure harnesses (C1, C2) and the audit experiment (C5) use only
  the Python standard library.

### Benchmarks / data
The frozen corpus (`artifact/corpus/`), the per-system evidence records
(`artifact/evidence/`), the 500 genuine/forged audit pairs
(`artifact/audit/e3/`), and the signed evidence ledgers (`artifact/ledger/`) all
ship with the artifact. No data needs to be fetched.

## A.2 Installation and configuration

```
./install.sh          # creates .venv and installs cryptography (+ optional extras)
. .venv/bin/activate
```

If you prefer to use your system Python, `pip install cryptography` is sufficient
for every claim. The standard-library-only claims need nothing at all.

## A.3 Experiment workflow

Every claim is a directory under `claims/` with three files, following the S&P
artifact format: `claim` (the statement), `expected` (what you should see), and
`run.sh` (the command). Run them in order, or run them individually:

```
for c in claims/claim*; do echo "== $c =="; bash "$c/run.sh"; done
```

Each `run.sh` is a few seconds except the overhead microbenchmark (C6), which is
tens of seconds, and the audit experiment (C5), a few seconds to rebuild 500
pairs. Total wall-clock for all nine is about two minutes on a laptop.

## A.4 Major claims

* **C1, Corpus and outcomes.** The study covers 43 version-pinned systems with
  mutually-exclusive outcomes: 26 directly exposed, 3 conditionally exposed, 1
  transitively exposed, 11 resistant, 2 with no qualifying persisted gate. Each
  system carries an evidence record at its stated tier. *(Paper §4, outcome
  table.)* Reproduced by **E1**.
* **C2, Exposure is real and state-only.** For an exposed resume contract, the
  gate blocks with no decision, and a single write to the persisted
  approval-relevant value, nothing else, makes the protected action execute on
  resume. We reproduce this offline for 12 systems at contract level (the N2
  tier). Native single-framework reproductions are included under
  `artifact/exposure/native` and `artifact/exposure/resistant`. *(Paper §3, §5.)*
  Reproduced by **E2**.
* **C3, The defense holds against all five families.** The provenance-bound
  verifier accepts exactly one genuine approval and rejects Forge, Rebind,
  Replay, Suppress, and Launder, including a 100-worker concurrent replay in
  which exactly one execution is admitted. *(Paper §6, adversarial battery.)*
  Reproduced by **E3**.
* **C4, Every binding is necessary.** Removing any single binding from the
  verifier reopens a specific attack. With the binding present the attack is
  blocked. *(Paper §6, per-binding ablation.)* Reproduced by **E4**.
* **C5, Audit indistinguishability (a structural identity, stated plainly).**
  Native audit records for a genuine vs forged approval are *byte-identical* under
  the audit projection (exact-match 100% over 500 pairs), because the audit log is
  derived from the same persisted state the forge controls. So no detector of any
  kind can separate them, native AUC 0.5 is the trivial consequence, not a
  classifier result. The provenance AUC 1.0 is reported as *true-by-construction*:
  the provenance policy checks a signed field built to be present iff genuine, so
  it shows the field is *checkable*, not that a detector was learned. *(Paper
  §5.4.)* Reproduced by **E5**.
* **C6, Verification is cheap.** Authenticating the approval artifact costs on
  the order of tens to a few hundred microseconds on commodity hardware,
  negligible against human-review latency. The figure excludes durable nonce
  storage, networking, and identity, which are deployment-specific. *(Paper §6.)*
  Reproduced by **E6**.
* **C7, Evidence is tamper-evident and independently verifiable.** The exported
  approval/guard ledgers verify offline from the embedded public key alone: the
  RFC 6962 Merkle root recomputes and the Ed25519 signed tree head checks out.
  *(Paper §6, downstream attestation.)* Reproduced by **E7**.
* **C8, One corpus, reconciled.** The corpus is a single spine of 79
  version-pinned systems (43 approval substrates + 36 deployed applications)
  under one threat model and one selection protocol, 54 exposed, 3 conditional,
  1 transitive, 19 resistant, 2 non-applicable, folding in the three earlier
  working corpora with every version/verdict conflict resolved and the one
  version-sensitive case (OpenAI Agents SDK) explained in `artifact/corpus/`.
  *(Paper §4.)* Reproduced by **E8**.
* **C9, Two-reach sensitivity analysis.** A contract-level model of each of the
  22 durable / orchestration / CI-CD / code-review comparison systems' documented
  consume predicate, under one write primitive and one success predicate. At the
  stated reach (application persistence) the model reproduces each published
  verdict, as expected by construction. Extending the writer to the engine's or
  server's own datastore separates resistant verdicts that are engine-store
  dependent (6 degrade to conditional) from those anchored to a capability the
  threat model denies (5 hold). Temporal and Gerrit also have native runs at the
  stronger reach under `artifact/exposure/native/`. See
  `artifact/corpus/SYMMETRIC_STATEWRITER_TEST.md`. *(Paper §3.1, §4.4.)*
  Reproduced by **E9**.
* **C10, The exposed default extends into public code (measured).** From public
  GitHub, snapshot 2026-11-02: (A) within the audited corpus, exposed systems are
  72.6% of the 73 resolved repositories but **88.4%** of their GitHub stars. 
  (B) keyword searches for eight exposed frameworks' human-in-the-loop APIs return
  116,046 hits (approximate. Include docs and copies). (C) of 209 search-ranked
  files using those APIs, 201 (**96.2%**) contain no provenance-verification
  signal, and of the 111 source-code files 108 (**97.3%**). The predicate is
  lexical and file-level. The Wilson intervals describe the sample, not all public
  code. Every "verified" label and a seeded sample of "trusts-state" labels were
  read by hand. See `artifact/measurement/prevalence/RESULTS.md` for what the
  numbers do and do not support. Reproduced **offline** by **E10**.

## A.5 Evaluation

| Exp | Claim | Command | Needs | ~Time | Expected |
| --- | --- | --- | --- | --- | --- |
| E1 | C1 | `bash claims/claim1/run.sh` | stdlib | 1 s | 43 rows, 26/3/1/11/2, 43/43 evidence matched, PASS |
| E2 | C2 | `bash claims/claim2/run.sh` | stdlib | 5 s | 12 harnesses, each control blocked / forge executed, PASS |
| E3 | C3 | `bash claims/claim3/run.sh` | cryptography | 2 s | every family REJECT, genuine ACCEPT, concurrent executions=1, PASS |
| E4 | C4 | `bash claims/claim4/run.sh` | cryptography | 2 s | each binding intact=reject, ablated=ACCEPT, necessary, PASS |
| E5 | C5 | `bash claims/claim5/run.sh` | stdlib | 3 s | native records byte-identical 100%/500, native_auc=0.5 (consequence), provenance_auc=1.0 (true-by-construction) |
| E6 | C6 | `bash claims/claim6/run.sh` | cryptography | 20 s | median/p95/p99 for HMAC verify, Ed25519 sign & verify (Table XII) |
| E7 | C7 | `bash claims/claim7/run.sh` | cryptography | 1 s | 7 ledgers, merkle_root=OK, tree_head_sig=OK, PASS |
| E8 | C8 | `bash claims/claim8/run.sh` | stdlib | 1 s | unified spine 79 systems, L1 43 (26/3/1/11/2), L2 36 (28/8), PASS |
| E9 | C9 | `bash claims/claim9/run.sh` | stdlib | 1 s | 22 systems one reach, REACH1 Exposed=9/Cond=2/Resist=11 reproduces paper, 6 engine-dependent, 5 anchored, PASS |
| E10 | C10 | `bash claims/claim10/run.sh` | stdlib | 1 s | A: 72.6% repos / 88.4% stars exposed, B: 116,046 hits, C: 201/209 = 96.2%, code only 108/111 = 97.3% |

Each `run.sh` prints a final `RESULT: PASS` (or the stated numbers) and exits
non-zero on any deviation, so the set can be run in CI.

## A.6 Scope, tiers, and honesty notes

The paper is careful about *how* each verdict was established, and so is the
artifact. Three things are worth stating plainly:

* **Evidence tiers are not all equal, and we do not pretend they are.** The
  corpus marks each system N1 (native-runtime), N2 (documented resume contract
  reproduced against a local store), vendor-confirmed, or design-verified. The
  offline harnesses behind C2 are N2 by construction: they reconstruct the
  documented consume path, they do not run the vendor's full product. Native
  reproductions that run the real vendor code live under `artifact/exposure/native`
  and `artifact/exposure/resistant` and require the framework/tool to be installed.
  Seven Layer-2 deployed-application rows have been promoted N2→native this way , 
  the exposed ERPs Tryton and Dolibarr (a state-only write to the persisted
  approval status releases the gated action in the real app), and the
  signature-anchored supply-chain / PKI tools TUF, in-toto, Sigstore (cosign) and
  step-ca (a state-only write cannot forge the signed decision), each confirming
  its corpus verdict at native tier (`artifact/exposure/native/L2-*`, with the
  exact version pins in `artifact/corpus/UNIFIED_CORPUS.csv`). Ten of the 36 Layer-2 rows are now native (seven promoted in-build, three, Odoo, OpenEMR, LibreSign, from the included kit, each with a captured run under `artifact/exposure/native/L2-{Odoo,OpenEMR,LibreSign}/`). The remaining rows can be reproduced on any Docker host with the bundled, resumable kit at `artifact/exposure/native/l2-native-kit/` (`./run.sh`). It records a real verdict or INCONCLUSIVE+reason per app and never forces a pass. The kit needs Docker and its own dependencies, so it is not part of the gated crypto-only claim suite.
* **The audit result is a structural identity, and we say so plainly.** The real
  finding is that native audit records for a genuine and a forged approval are
  byte-identical (exact-match 100% over 500 pairs), so *no* detector can separate
  them, native AUC 0.5 is the trivial consequence, not a classifier score. The
  provenance AUC 1.0 is true-by-construction: the provenance policy checks a
  signed field built to be present iff genuine, so it demonstrates the field is
  *checkable*, nothing more. C5 prints both and labels them so, so there is no
  circular "we trained a detector and it scored 1.0" claim to mistake it for.
* **The overhead number is the cryptographic core only.** Durable nonce storage,
  the network hop to an approval service, and identity are excluded and are
  deployment-specific.

An optional `artifact/exposure/extended_docker/` tree contains the durable-engine
and VCS-chain reproductions that require Docker and live services. They are not
part of the gated claims and are provided for completeness.

## Layout

For a one-page index of exactly what ships and where, see `MANIFEST.md`. For the
claim-by-claim crosswalk to the paper, see `CLAIM_MAP.md`.

```
README.md                 this file (artifact appendix)
MANIFEST.md               authoritative index of everything in the artifact
CLAIM_MAP.md              artifact claims (C1-C10) mapped to paper claims
install.sh                create .venv, install dependencies
requirements.txt          cryptography (+ optional jsonschema)
use.txt destructive.txt   usage and (non-)destructiveness statements
citation.txt license.*    citation and license
infrastructure/           provisioning notes (a single commodity node)
claims/claim1..10/        {claim, expected, run.sh} per major claim
scripts/                  validators: counts, anonymity, ledger verification
artifact/
  corpus/                 the unified 79-system corpus and its reconciliation
                          UNIFIED_CORPUS.csv, SELECTION_PROTOCOL.md,
                          RECONCILIATION.md, UNIFIED_CORPUS_SUMMARY.md,
                          OPENAI_AGENTS_VERSION_SENSITIVITY.md,
                          SYMMETRIC_STATEWRITER_TEST.md,
                          RELATED_WORK_POSITIONING.md, and the
                          43-substrate corpus.csv it is built on
  evidence/               per-system evidence records, by tier
  exposure/
    offline/              12 standard-library contract harnesses (N2)
    symmetric/            two-reach state-writer sensitivity test (C9)
    native/              native reproductions (need the framework/tool)
      l2-native-kit/     resumable one-command kit to reproduce the
                         remaining Layer-2 rows natively on a Docker host
    resistant/           resistant-by-design controls (need the framework)
    extended_docker/      optional durable/VCS reproductions (need Docker)
  mitigation/
    apf_provenance/       the provenance-bound approval protocol + verifier
    battery.py            adversarial battery (C3)
    ablation.py           per-binding ablation (C4)
    overhead_bench.py     verification microbenchmark (C6)
    ablation.csv overhead.csv   recorded reference outputs
  audit/e3/               audit-indistinguishability experiment (C5)
  ledger/                 signed, offline-verifiable evidence ledgers (C7)
  measurement/
    prevalence/           APF in public code (C10): METHODOLOGY.md,
                          RESULTS.md, classify.py, analyze.py, collect*.py,
                          and data/ (repo_metrics, frame_counts,
                          sample_classified, validation)
```
