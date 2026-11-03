# Reconciliation: three working corpora into one spine

The work produced three overlapping corpora at different times. A reviewer who
finds more than one of them will see different version numbers, and in one case a
different verdict, for the same framework. This document states exactly how they
were merged so the published corpus is a single, internally consistent spine.

## The three sources

- **S**, the 43-system substrate study (agent frameworks through
  infrastructure composition).
- **W**, the earlier 18-framework agent-only subset. **W is a subset of S**: its
  18 frameworks are precisely the agent-framework rows of S. It is not a separate
  population. Folding it in means reconciling its version pins and keeping one.
- **D**, the deployed-application sector survey (Layer 2 here). **D is
  additive**: its systems are end-user applications, disjoint from S and W.

So the unified corpus is `S ∪ D` with per-system version/verdict reconciled
against `W` (and against a later assessment, "P", that ran seven of the
agent frameworks at newer versions). Total: **79 systems = 43 substrates (Layer
1) + 36 deployed applications (Layer 2)**. The defense gate used in the sector
work is excluded from the counts. It is the mitigation, not a system under test.

## Aggregate of the unified corpus

| | Exposed | Conditional | Transitive | Resistant | N/A | Total |
| --- | --- | --- | --- | --- | --- | --- |
| Layer 1, substrates | 26 | 3 | 1 | 11 | 2 | 43 |
| Layer 2, deployed apps | 28 | 0 | 0 | 8 | 0 | 36 |
| **Unified** | **54** | **3** | **1** | **19** | **2** | **79** |

Applicable systems (excluding the 2 N/A): 77, of which 58 are exposed in some
form (54 direct + 3 conditional + 1 transitive) and 19 are resistant. Verdicts
are stated against the paper's state-writer (application-persistence reach). The
symmetric two-reach test (`SYMMETRIC_STATEWRITER_TEST.md`, claim 9) reproduces
every verdict under that reach and then characterises, as a sensitivity analysis,
which resistant verdicts are engine-store dependent (six, Temporal, Restate,
Inngest, Gerrit, Jenkins, GoCD, degrade to conditional only if the adversary
also reaches the engine's own datastore) and which are capability-anchored (five
,  AWS Step Functions, Prefect, PydanticAI, BeeAI, Mastra, hold even then).

## Version pins where the sources disagreed

Rule (from `SELECTION_PROTOCOL.md`): pin to the most recent version run at the
highest tier. Record the rest in `also_tested`. State the verdict against the pin.

| Framework | S (43-study) | W (workshop) | P (later assessment) | **Pinned** | Verdict at pin |
| --- | --- | --- | --- | --- | --- |
| LangGraph | 1.2.5 | 1.2.6 | 1.2.18 | **1.2.6** | Exposed |
| OpenAI Agents SDK | 0.17.4 | 0.17.7 | 0.24.0 | **0.17.7** | Exposed, *version-sensitive, see below* |
| Microsoft Agent Framework | "semantic-kernel 1.43.0 line" (mislabelled) | agent-framework-core 1.9.0 | 1.23.0 | **agent-framework-core 1.9.0** | Exposed |
| Semantic Kernel | 1.43.0 | 1.43.1 | | **1.43.1** | Exposed |
| Haystack | 2.30.0 | 2.30.2 | 3.4.1 | **2.30.2** | Exposed |
| CrewAI | 1.14.6 | 1.15.0 | 1.15.33 | **1.15.0** | Exposed |
| Google ADK | 2.2.0 | 2.3.0 | 2.13.0 | **2.3.0** | Exposed |
| Agno | 2.6.11 | 2.6.20 | | **2.6.20** | Exposed |
| LlamaIndex | run-llama pin | llama-index-workflows 2.22.1 | 0.14.25 (core) | **llama-index-workflows 2.22.1** | Exposed |
| PydanticAI | 1.107.0 | 2.0.0 | | **2.0.0** | Resistant |
| BeeAI | 0.181 | 0.1.81 | | **0.1.81** | Resistant |
| Mastra | 1.45.0 | 1.46.0 / 1.47.0 | | **1.46.0** | Resistant |

Frameworks present in only one source (Burr, Strands, OpenHands, Vercel AI SDK,
Genkit, and the whole durable/orchestration/CI-CD/code-review/identity tail) keep
that source's pin unchanged.

## Conflicts resolved, not papered over

1. **Verdict conflict, OpenAI Agents SDK (Exposed in S/W, "resisted" in P).**
   This is the only genuine verdict disagreement and it is real: the SDK changed
   between 0.17 and 0.24. We pin the measured 0.17.7 (Exposed) and document the
   0.24.0 behaviour as version sensitivity, not as a contradiction. Full
   mechanism in `OPENAI_AGENTS_VERSION_SENSITIVITY.md`.

2. **Mislabelled basis, Microsoft Agent Framework.** The 43-study listed its
   basis as the "semantic-kernel 1.43.0 line," conflating two distinct packages
   (Semantic Kernel and the Microsoft Agent Framework). Corrected: MAF is pinned
   to `agent-framework-core 1.9.0`. Semantic Kernel is a separate row at 1.43.1.

3. **Tier drift.** Some systems appear at N1 in one source and N2 in another
   depending on whether the native product or the documented contract was run.
   We keep the **highest** tier achieved for the pinned version and never average
   or upgrade tiers. The tier label travels with the row.

4. **Newer versions in the later assessment (P).** P exercised seven frameworks at
   much later versions (e.g. LangGraph 1.2.18, Haystack 3.4.1) inside a synthetic
   payment deployment. Those are recorded in `also_tested` but are **not** the
   pin and are **not** counted as independent systems, because P is a later
   assessment, not part of the measurement corpus. Its only effect on the corpus
   is the OpenAI version-sensitivity note.

5. **Double-counting avoided.** Because W ⊂ S, the 18 workshop frameworks are
   counted once (as Layer-1 agent-framework rows), never added to the 43.

## What a reader should take from this

The corpus is one spine of 79 systems under one threat model and one selection
protocol, with exactly one pinned version per system and every source conflict
resolved in the open. The agent-framework subset and the deployed-application
survey are strata of this spine, not competing studies.
