# APF - E3: Machine-Checkable Audit-Indistinguishability

This package proves, reproducibly, that a forged APF record is
indistinguishable from a genuine human approval under **native** audit evidence
and is **accepted** by ordinary approval-completeness validation, while a
**provenance-aware** check separates the two perfectly.

It replaces a human-subjects audit study with a deterministic, re-runnable test.

## Run

```bash
pip install jsonschema
python run_e3.py              # rebuild records, then evaluate
python run_e3.py --eval-only  # evaluate the committed records only
```

Output: `APF-e3-results.json`.

## Layout

```
run_e3.py                              reproducible runner (builds + evaluates)
schemas/native_approval.schema.json    ordinary completeness schema (additionalProperties:false)
schemas/provenance_approval.schema.json what provenance-aware validation requires
policies/native_approval.rego          weak/native approval policy (accepts the forge)
policies/provenance_approval.rego      provenance-aware policy (rejects the forge)
records/<fw>_genuine.json              genuine approval record (5 families)
records/<fw>_forged.json               forged approval record (identical native fields)
records/separability_pairs.jsonl       500 genuine/forged pairs for the separability test
APF-e3-results.json        regenerated results
```

Families: TCA/Haystack, CRV/MAF, SRS/AutoGen, WED/Dify, ALS/Agno.

## Policy evaluation (important)

The two `.rego` files are the canonical, auditable policies. **This runner does
not invoke an OPA engine**. It evaluates Rego-EQUIVALENT logic in Python
(`rego_native_allow` / `rego_provenance_allow`), with the `.rego` files included
for auditability. Cryptographic checks (HMAC signature, nonce, expiry) are
performed by the runner. In a real OPA deployment those would be verified out of
band and passed into the policy as input booleans, which is standard practice.
In other words: we evaluate Rego-equivalent policies implemented in the runner,
with the corresponding Rego policies included for auditability. We do not claim
to have executed OPA.

## How a record is built

A genuine record (human approved via the trusted path) and a forged record
(state-write forge) are **identical on every native field**, because the audit
log is derived from the same persisted state the forge controls. They differ
only in a provenance artifact that native logging never captures:

- genuine: a context-bound `approval_artifact` (HMAC over
  `{run_id, action, args_hash, approver, nonce, context_hash, issued_at, expiry}`),
  a `trusted_approval_path_event`, and `state_writer = "approval-service"`.
- forged: `approval_artifact = null`, `trusted_approval_path_event = null`, and
  `state_writer = "logging-sidecar"` (only knowable WITH provenance).

`native_view()` strips the provenance fields to model exactly what native audit
logging exposes to a validator.

## Checks

1. **Field-level diff** over 7 forensic fields
   (`approver, timestamp, action_status, state_transition, action_arguments,
   trusted_approval_path_event, state_writer_evidence`). Native evidence yields
   zero distinguishing fields. Provenance evidence distinguishes via
   `trusted_approval_path_event` and `state_writer_evidence`.
2. **Validator acceptance** of the forged record: JSON Schema (accept), SIEM
   ingestion rules (no alert), native policy (allow). Provenance policy (deny).
3. **Indistinguishability** over 500 pairs, a *structural identity*, not a
   learned classifier. The primary number is that the native records are
   **byte-identical** (exact-match 100%): because they are identical, the
   Bayes-optimal detector is at chance, so no feature or model can separate them.
   The two AUC numbers are reported only as the endpoints this identity forces:
   native AUC = 0.5 is the trivial consequence, and provenance AUC = 1.0 is
   **true by construction**, the provenance policy checks a signed field we build
   to be present iff genuine, so the 1.0 shows the field is *checkable*, not that
   a detector was trained. Read it that way. It is not empirical classifier
   performance.

## The 500-pair dataset

We generated 500 genuine/forged pairs by varying **scenario fields across pairs**
(run id, timestamp, approver label, and transfer amount) while keeping the native
audit evidence **identical within each genuine/forged pair**. This makes the
byte-identity measurable across varied scenarios rather than a single hand-picked
example. Generation is deterministic (`seed = 7`) and lives in `build_records()`.

## Test key

The HMAC key in `run_e3.py` is a published TEST key for reproducibility. It
models a secret that, in deployment, lives only inside the trusted approval
service. Publishing it does not weaken the result: *without* provenance the
records are indistinguishable (a structural identity, independent of any key), and
*with* provenance they separate true-by-construction. The published key cannot
help an attacker forge, because the result does not rest on the key's secrecy, it
rests on the native records being identical.

## Expected result

```
aggregate native distinguishing fields : []  (indistinguishable)
forged record: schema accept, SIEM none, native policy allow, provenance policy deny
(3) INDISTINGUISHABILITY  (structural, not a learned classifier)
   PRIMARY: native records byte-identical in 100% of 500 pairs -> no detector can separate them
   endpoints forced by that identity:
     native_auc=0.5  (trivial consequence of the identity)
     provenance_auc=1.0  (TRUE BY CONSTRUCTION: a signed field present iff genuine)
```
