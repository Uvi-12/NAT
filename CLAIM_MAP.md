# CLAIM_MAP, artifact claims ↔ paper claims

A reviewer-facing crosswalk from the artifact's reproducible claims (C1–C10) to the
paper's claim statements and tables. The paper's claim IDs follow the categories
Background (BG), Definition (DEF), Empirical (EMP), Attack (ATT), Audit (AUD), and
Mitigation (MIT). The lineage column notes the experiment number this evidence
carried in the earlier working repository, for anyone cross-referencing it.

| Artifact claim | Paper claim IDs supported | Paper location | Lineage |
| --- | --- | --- | --- |
| **C1**, 43-system corpus, outcomes 26/3/1/11/2, evidence tiers | EMP-01…06, ATT-01 | §4 Results, Table VI (tiers), Table VII (outcomes) | E1/E2/E8/E9 |
| **C2**, exposure is real and state-only (control blocks, a single state write executes the action, a forged approver is recorded) | ATT-01, ATT-02, ATT-05, DEF-01 | §3–§5, Table II, Table V | E1/E2 |
| **C3**, provenance verifier rejects Forge/Rebind/Replay/Suppress/Launder + 100-worker concurrent replay (13-case battery) | MIT-02, MIT-03 | §6, Table X | E4 |
| **C4**, every binding is necessary (per-binding ablation reopens a specific attack) | MIT-01, MIT-03 | §6, Table XI | E4 (ablation) |
| **C5**, native audit records byte-identical within each pair (the native projection cannot separate forged from genuine), provenance separation holds by the structural identity | AUD-01…05, ATT-06, AUD-06 | §5.4 | E3 |
| **C6**, verification cost (HMAC, Ed25519 sign/verify) negligible vs human-review latency | MIT (cost) | §6.7, Table XII | E5/E6 |
| **C7**, evidence ledgers verify offline (RFC 6962 Merkle root + Ed25519 signed tree head) | downstream attestation | §6.3 | ledger experiment |
| **C8**, unified 79-system spine (43 substrates + 36 deployed apps) internally consistent | EMP (expanded corpus) | §4 (expanded spine), `RECONCILIATION.md` | expansion |
| **C9**, two-reach sensitivity analysis (contract-level model, native for Temporal and Gerrit) separates engine-store-dependent from capability-anchored resistance | DEF-02, ATT-07, EMP-05 | §3.1, §4.4, Table VIII, Figure 2 | E11-adjacent |
| **C10**, the exposed default in public code: A 88.4% of corpus stars on exposed systems, B 116,046 keyword-search hits, C 201/209 sampled files, D (primary) 181/310 repositories (58.4%, Wilson 95% [52.8, 63.7]) with no detected provenance-verification token near their approval code (a detected-signal rate for the sample, not a measure of true absence) | EMP (external validity) | §4.5, Figs. 3–5, `measurement/prevalence` (D = `analyze.py`, `repo_scan.py`) | new |

## Notes on lineage

- The earlier working repository measured an 18-framework subset (13 exposed / 3
  resistant / 2 N/A) and numbered its experiments E1–E11. The present artifact is
  the expansion to the 43-system substrate corpus and the 79-system unified spine. 
  C1–C9 supersede the E-numbering but reproduce the same claims plus the expanded
  corpus (C8) and the authoring-topology sensitivity test (C9). C10 is new to this
  artifact: a deployment-level prevalence study with no counterpart in the earlier
  repository.
- Claims the paper states from external citations or the threat-model definition
  (BG-01…03, DEF-03…04) are argued in the text, not reproduced by a script. They
  are not gated here and are not counted among C1–C10.
- The resistant and non-applicable rows (EMP-05, EMP-06) are first-class controls
  in the corpus (`artifact/evidence/resistant-controls/`, `.../non-applicable/`)
  and are exercised by C1/C8/C9, not only asserted.
