# Corpus selection protocol

This is the single protocol behind the whole corpus. Everything in
`UNIFIED_CORPUS.csv` was selected, pinned, and classified by the rules here, and
nothing is counted that does not meet them. It supersedes the three earlier
working corpora (a 43-system substrate study, an 18-framework agent-only subset,
and a sector survey of deployed applications). Those are folded in and
reconciled, not reported side by side. Where they disagreed, see
`RECONCILIATION.md`.

## What we are enumerating

A system is **in scope** when it exhibits the pause/resume pattern the paper is
about: it reaches a point where a human (or an authorizing role) is meant to
approve a protected action, it persists enough state to survive the wait, and a
later resume path consumes that state to decide whether the protected action
runs. If there is no persisted decision that resume consumes, the system is
**non-applicable** and is recorded as such rather than dropped, so the
denominator is honest.

We enumerate two layers, under one predicate:

- **Layer 1, approval substrates.** Reusable building blocks that other
  software gates actions with: agent frameworks, durable-execution engines,
  orchestration/BPMN engines, CI/CD approval gates, code-review systems,
  identity-governance, and infrastructure-composition tools. These are the
  systems a developer adopts to *get* a human-approval gate.
- **Layer 2, deployed applications.** End-user open-source systems that ship a
  human sign-off or approval step as a built-in feature, across healthcare,
  finance, ERP/procurement, e-signature, PKI/certificate issuance, software
  supply chain, research-data, and civic participation. These test whether the
  failure appears in software organisations actually run, independent of the
  agent-framework story.

Layer 1 answers "is the weakness intrinsic to the mechanisms people build gates
from?". Layer 2 answers "does it reach production software and across domains?".
Keeping them as one corpus with a layer label, rather than three overlapping
studies, is the point of this document.

## How each layer was populated

**Layer 1.** We started from the set of widely used frameworks and engines in
each category (by adoption and by presence of a documented human-in-the-loop or
manual-approval primitive) and included every one whose approval/resume contract
we could exercise or read from source. The agent-framework slice is the same set
the earlier workshop subset covered. It is not a separate corpus, only the
agent-framework rows of Layer 1.

**Layer 2.** Within each sector we took actively maintained open-source systems
that have an explicit approval, sign-off, finalization, or publication gate, and
whose consume path we could locate in source. Inclusion required that we could
name the exact field the resume/consume path trusts and cite its source
location. Systems where we could not were left out rather than guessed.

**Exclusions (both layers).** We exclude anything outside the state-writer threat
model: prompt/model compromise, reviewer or approval-service compromise, code or
host compromise, and direct protected-action authority. We also exclude our own
defense gate (the provenance-bound witness) from the surveyed counts, it is the
mitigation, not a system under test.

## The state-writer adversary (the one threat model)

Every verdict is stated against the same adversary: a principal that can read and
write the persisted approval-relevant state, but that cannot approve through the
trusted path, cannot invoke the protected tool, holds no signing or MAC keys,
reads no secrets, changes no code, and does not execute on the host. This models
a backup/restore job, a migration task, a scoped database role, a sidecar, or a
queue/replication consumer. A verdict is meaningful only relative to this
boundary, and the boundary does not change between layers.

## Version pinning (one pin per system)

Each system carries exactly one `pinned_version`, chosen by a fixed rule:

1. Pin to the version exercised at the **highest evidence tier** for that system
   (native runtime over contract over design).
2. When more than one study ran it natively, pin to the **most recent** such
   version, and list the others in `also_tested`.
3. State the **verdict against the pinned version**. If the verdict is not stable
   across versions, that is not hidden, it goes in `version_note` and, for the
   one case where it genuinely flips, in `OPENAI_AGENTS_VERSION_SENSITIVITY.md`.

For Layer 2, the pin is the repository revision exercised in the harness, and the
decisive **consume-path source location** (file and line) is recorded with the
system, so the pin is checkable even where an upstream release tag is not minted.

## Evidence tiers (how a verdict was established)

- **N1, native runtime.** The vendor's shipped code was run against the state
  mutation.
- **N2, contract level.** The documented resume/consume predicate was
  reconstructed against a local store and run. The vendor's full product was not
  executed. All Layer 2 verdicts are N2 by construction.
- **Design-verified.** Established from a trust anchor the state writer cannot
  author (e.g. a server-owned event history), without an end-to-end run.
- **Vendor-confirmed / Runtime-tested-resistant / Scope.** As labelled.

Tiers are not interchangeable and we never silently promote one to another. The
tier travels with every row and every count.

## Verdicts

- **Exposed**, a state-only write releases the protected action with no extra
  condition.
- **Conditional**, exposed only under a stated persistence condition (e.g. a
  writable accepted-history surface), with a matched control that fails without it.
- **Transitive**, a forged upstream decision is accepted by a downstream system
  that performs its own documented check.
- **Resistant**, the same state write is insufficient because resume takes the
  decisive evidence from an authority the writer cannot author.
- **N/A**, no qualifying persisted approval gate.

Outcome classes are mutually exclusive and sum to the corpus size. Mechanism
families (CRV, SRS, WED, TCA, ALS, …) are descriptive labels and may co-occur, so
they do not sum.
