# MANIFEST, exactly what is in this artifact

This is the authoritative index of the artifact. Every top-level area is listed
with what it contains. The paper's Appendix A (Open Science) describes the same
directories by name. Nothing in the paper's evidence story is omitted, and nothing
here is a stub.

## Reproducible claims (run these)

`claims/claim1 … claim10/`, each is `{claim, expected, run.sh}`. Run all with
`for c in claims/claim*; do bash "$c/run.sh"; done`. Standard library only, except
C3/C4/C6/C7 which need `cryptography` (`./install.sh`). Total ≈ 2 minutes.

| Claim | Reproduces | Command target | Paper |
| --- | --- | --- | --- |
| C1 | 43-system corpus and outcome accounting (26/3/1/11/2) | `scripts/validate_counts.py` | §4, Table VII, Table VI tiers |
| C2 | exposure is real and state-only (control blocks, forge executes) | `artifact/exposure/offline/run_offline.py` | §3–5, Table II/V |
| C3 | provenance verifier rejects all five families + concurrent replay (13-case battery) | `artifact/mitigation/battery.py` | §6, Table X |
| C4 | every binding is necessary (per-binding ablation) | `artifact/mitigation/ablation.py` | §6, Table XI |
| C5 | audit indistinguishability (native byte-identical, provenance true-by-construction) | `artifact/audit/e3/run_e3.py` | §5.4, Table III |
| C6 | verification cost (HMAC, Ed25519 sign/verify) | `artifact/mitigation/overhead_bench.py` | §6.7, Table XII |
| C7 | evidence ledgers verify offline (RFC 6962 + Ed25519) | `scripts/verify_ledger.py` | §6.3 downstream attestation |
| C8 | unified 79-system corpus is internally consistent | `scripts/validate_unified.py` | §4 (expanded spine) |
| C9 | authoring topology is not a setup artifact (two-reach test) | `artifact/exposure/symmetric/run_symmetric.py` | §3.1, §4.4 |
| C10 | exposed default in public code: 88.4% of corpus stars on exposed systems, 116,046 keyword hits, 96.2% of 209 sampled files (97.3% of 111 code files) with no provenance signal | `artifact/measurement/prevalence/analyze.py` | §4.5 |

See `CLAIM_MAP.md` for the full claim-ID crosswalk to the paper.

## What ships, by area

| Path | Contents |
| --- | --- |
| `README.md` | the artifact appendix: requirements, install, per-claim evaluation, scope/tier honesty notes |
| `MANIFEST.md`, `CLAIM_MAP.md` | this index and the claim→paper crosswalk |
| `install.sh`, `requirements.txt` | create `.venv`, install `cryptography` (+ optional `jsonschema`) |
| `use.txt`, `destructive.txt`, `citation.txt`, `license.*`, `infrastructure/` | usage, (non-)destructiveness, citation, license, single-node provisioning note |
| `artifact/corpus/` (15 files) | canonical matrix (`corpus.csv`, `UNIFIED_CORPUS.csv`), verdict defs (`verdicts.csv`), mechanism codes + attack matrix (`attack-matrix.csv`), evidence classes (`evidence-tiers.csv`), deployment shapes (`deployment-shapes.csv`), laundering chains (`laundering-chains.csv`), disclosure maps (`disclosure-status.csv` for substrates, `disclosure-deployed-apps.csv` for deployed applications), selection protocol + reconciliation + symmetric-test + related-work writeups |
| `artifact/exposure/offline/` (12 harnesses) | standard-library resume-contract reconstructions (N2), each: control-blocked then state-only forge executes, **exposure only** |
| `artifact/exposure/native/` | native reproductions that run the real vendor code (need the framework/tool). Substrates: Temporal (history layer), Gerrit NoteDb (git layer), OpenAI Agents / Semantic Kernel / n8n, LangGraph fixture. **Layer-2 deployed applications (10, promoted N2→native):** Tryton ERP (`L2-Tryton`, exposed), Dolibarr ERP (`L2-Dolibarr`, exposed), TUF (`L2-TUF`), in-toto (`L2-in-toto`), Sigstore via cosign (`L2-Sigstore-cosign`), step-ca (`L2-stepca`), Odoo ERP (`L2-Odoo`, exposed), OpenEMR EHR (`L2-OpenEMR`, exposed), LibreSign e-sign (`L2-LibreSign`, resistant), each runs the real tool/app. A bundled resumable kit (`l2-native-kit/`, `./run.sh`) reproduces the remaining Layer-2 rows natively on any Docker host, recording a real verdict or INCONCLUSIVE+reason per app and confirms its corpus verdict at native tier |
| `artifact/exposure/resistant/` | resistant-by-design controls (need the framework) |
| `artifact/exposure/symmetric/` | the two-reach state-writer sensitivity test (C9) |
| `artifact/exposure/extended_docker/` | optional durable-engine / VCS reproductions (rebind, replay, launder) across real services, need Docker, **exposure only** |
| `artifact/evidence/` (43 records) | per-system evidence records filed by tier (native-runtime, contract-verified, vendor-confirmed, resistant-controls, non-applicable) |
| `artifact/reachability/` | default-deployment reachability of the authoritative approval field: `METHODOLOGY.md`, `vectors.md`, `collect.py` (re-fetches each vendor's shipped default manifest and re-verifies the signal), `reachability.csv` (6 systems, the non-approval writer admitted by the default deployment, with the decisive field, native backing, and a verbatim locator), `cve_precedent.csv` and `DISCLOSURE_CANDIDATES.md` (related third-party authorization CVEs as context, direct analogues separated from adjacent), and `restricted_identity_demo/` (an offline, database-enforced, end-to-end restricted-identity experiment, `./run.sh`) |
| `artifact/audit/e3/` | genuine/forged record captures, field diffs, native + provenance validators (schemas + rego-equivalent), 5000-pair indistinguishability |
| `artifact/mitigation/` | the provenance-bound approval **reference implementation** (`apf_provenance/`), the adversarial battery (C3), per-binding ablation (C4), overhead benchmark (C6), recorded `ablation.csv` / `overhead.csv` |
| `artifact/ledger/` (7 signed ledgers + public key) | signed, offline-verifiable RFC 6962 evidence ledgers |
| `artifact/measurement/prevalence/` | measurement of APF in public code (C10): `METHODOLOGY.md`, `RESULTS.md`, the lexical file-level classifier (`classify.py`), the stdlib Wilson-interval aggregator (`analyze.py`), the GitHub collectors (`collect.py`, `collect_bc.py`), `figures/make_figures.py` (redraws the paper's Figures 3–5), and `data/` (adoption metrics, search counts, the pseudonymous classified sample, and all hand judgments). `analyze.py` recomputes the three headline figures offline from the shipped data |
| `scripts/` | `validate_counts.py`, `validate_unified.py`, `validate_anonymity.py`, `verify_ledger.py` |
| `SHA256SUMS` | checksums over every shipped file |

## Integrity & provenance of this artifact

- Every file is listed in `SHA256SUMS`. `sha256sum -c SHA256SUMS` verifies the tree.
- The defense is an open-source **reference implementation of the mechanism**, not a
  product or service: no control plane, no service-side coupling, no state beyond
  the caller's nonce store.
- The artifact is double-blind: it contains no author identity, no code-host URLs,
  and no product name. `scripts/validate_anonymity.py` enforces this.

## Not included (stated honestly)

- Live third-party services are not bundled. `extended_docker/` brings up real
  engines via Docker when the reviewer chooses to run it.
- High-risk end-to-end exploit recordings are withheld pending coordinated
  disclosure (`artifact/corpus/disclosure-status.csv`, `artifact/corpus/disclosure-deployed-apps.csv`), per the paper's ethics §.
