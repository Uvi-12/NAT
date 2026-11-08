# Unified corpus, paper-ready summary

One corpus, one threat model (the state-writer adversary), one selection protocol
(`SELECTION_PROTOCOL.md`), one pinned version per system. 79 systems in two
strata. Source conflicts are resolved in `RECONCILIATION.md`. The one
version-sensitive verdict is explained in `OPENAI_AGENTS_VERSION_SENSITIVITY.md`.

## Outcome table (drop-in for the paper)

| Layer | Exposed | Conditional | Transitive | Resistant | N/A | Total |
| --- | --- | --- | --- | --- | --- | --- |
| L1, approval substrates (agent frameworks, durable execution, orchestration/BPMN, CI/CD, code review, identity, infra) | 26 | 3 | 1 | 11 | 2 | **43** |
| L2, deployed applications (healthcare, finance, ERP, e-sign, PKI, supply chain, research data, civic, CI/CD) | 28 | | | 8 | | **36** |
| **Unified** | **54** | **3** | **1** | **19** | **2** | **79** |

Applicable systems (excluding 2 N/A): **77**. Exposed in some form: **58/77**.
Resistant: **19/77**. The resistant set is the control that makes the
discriminator (who may author the evidence resume trusts) falsifiable, and it is
a fifth of the applicable corpus. These verdicts are stated against the paper's
state-writer (application persistence). The symmetric two-reach test
(`SYMMETRIC_STATEWRITER_TEST.md`, claim 9) attacks the resistant durable /
orchestration / CI-CD / code-review tail at the same reach as the exposed systems
and reproduces every verdict. It then characterises, as a sensitivity analysis,
which resistant verdicts are *engine-store dependent* (six, Temporal, Restate,
Inngest, Gerrit, Jenkins, GoCD, degrade to conditional if the adversary also
reaches the engine's own datastore) and which are *capability-anchored* (five , 
AWS Step Functions, Prefect, PydanticAI, BeeAI, Mastra, hold even then, because
their decisive evidence is a secret re-checked live or fresh input revalidated at
resume).

## One-paragraph description

> We evaluate 79 systems under a single state-writer threat model and selection
> protocol, in two strata: 43 approval *substrates*, the agent frameworks,
> durable-execution engines, orchestration/BPMN engines, CI/CD gates,
> code-review, identity-governance, and infrastructure-composition tools that
> developers build human-approval gates from, and 36 deployed open-source
> *applications* that ship an approval or sign-off step across healthcare,
> finance, ERP, e-signature, PKI, software supply chain, research data, and civic
> participation. Each system is pinned to one version and classified by whether a
> write to persisted approval-relevant state, and nothing else, releases the
> protected action on resume. 54 systems are exposed (26 substrates directly, 28 deployed applications), 3
> conditionally, 1 transitively. 19 resist because the resume path takes its decisive evidence
> from an authority the state writer cannot author. 2 have no qualifying gate.
> The weakness is therefore not a property of one framework generation or one
> domain: it recurs in the substrates people build on and in the applications
> they run.

## Crosswalk to the earlier working corpora

- The 43-system substrate study **is** Layer 1, unchanged in membership. Only
  version pins and the one mislabelled basis (Microsoft Agent Framework) were
  corrected.
- The 18-framework agent-only subset is the agent-framework rows of Layer 1
  (W ⊂ L1). It adds no new systems and is not counted separately.
- The sector survey **is** Layer 2 (36 deployed applications), additive and
  disjoint from Layer 1.
- The later assessment (7 frameworks at newer versions, synthetic
  payment deployment) is **not** part of the corpus. Its only bearing is the
  OpenAI Agents SDK version-sensitivity note.

## Caveats carried on every row (so counts are not over-read)

- `evidence_tier` travels with each system. Most of Layer 2 is N2 (documented
  consume predicate reconstructed against a local store), but **ten Layer-2 rows
  rest on native (N1) runs** of the real vendor code: Odoo, Dolibarr and Tryton
  (exposed ERPs), OpenEMR (exposed EHR), LibreSign (resistant e-signature), and
  TUF, in-toto, step-ca, Sigstore Fulcio and Sigstore policy-controller (resistant
  supply-chain / PKI tools. One cosign 2.4.1 run underlies both Sigstore rows). Their harnesses are under
  `artifact/exposure/native/L2-*`. Promotion raised the tier. It did not change any
  verdict. Natively validating more of the N2 remainder is the recommended next step.
- `mechanism_family` labels are descriptive and may co-occur. Only the outcome
  classes are mutually exclusive and sum to 79.
- Resistant verdicts in Layer 1's durable/CI-CD tail are design-verified (trust
  anchor the writer cannot author), not exhaustive runtime tests. This is stated
  per row.
