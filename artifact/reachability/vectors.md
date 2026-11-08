# Reachability vectors for the approval state

This file is the taxonomy that `reachability.csv` and `cve_precedent.csv` populate.
The question it answers is narrow and practical. For each listed system, is there a
principal that is **not** the approval authority but can still write the decisive
approval field, using only what a realistic deployment already grants. The objection
it closes is that a state-writer attack only shows the consequence of a compromised
database. It does not, and the claim is tied to the authoritative approval object, not
to a configuration string.

## Layer A. Shipped-configuration reachability (audited here)

Evidence is the vendor's own default compose, chart, or quickstart, re-fetched and
re-checked by `collect.py`. The decisive field per system is the exact one the native
reproduction in `artifact/exposure/native/` identifies as the field the runtime trusts
(column `approval_field` in `reachability.csv`). Reaching a secondary index or a
visibility store is not reachability of the approval state and is excluded. Three
classes, six systems.

- **R1 shipped superuser or shared credential.** The default connects the app and every
  co-located container to the store as a superuser or one shared role under a
  documented, often trivial password. (OpenEMR `root:root`, DocuSeal
  `postgres:postgres`, LedgerSMB `abc`.)
- **R2 co-located non-approval worker shares one all-DML role.** The vendor ships extra
  containers, job workers, schedulers, admin UIs, on the same single role with full
  write on the approval table. (ERPNext queue workers, Documenso co-located app role.)
- **R3 permission model conflates manage and approve.** The platform grant that lets a
  principal operate a workflow is the same grant that writes the resume state. (Argo
  `update workflows`.)

R1 closes under credential hygiene. R2 and R3 persist under correct credentials. Those
two are the load-bearing classes. Each row names its decisive field and its native
backing. OpenEMR carries an obtained native verdict (EXPOSED, L2-22), the others carry
a native harness whose end-to-end run is environment-pending, and Argo is state-only at
low confidence. The controlled, offline, database-enforced end-to-end version of the
same predicate is in `restricted_identity_demo/`.

### What was removed and why

An earlier version listed ten systems. Temporal (Elasticsearch is a visibility index,
not the authoritative history, and Temporal is Resistant in the ledger), Conductor
(Elasticsearch is an index, state persistence is a separate database), n8n (the runner
holds no database credentials, and the worker that does also holds the encryption key,
breaking the restricted-attacker model), and Dify (no native forge target to pin the
decisive field) were removed. See `METHODOLOGY.md`.

## Layer B. Related authorization failures in the same systems (public CVE record)

Layer A is about the store beneath the application. Layer B is the public CVE record
for these systems. It is **context, not proof of APF**. Most of these are general
authorization failures that establish authorization gaps recur in these products, not
the specific provenance or authoring-topology mechanism of APF. Two are direct
analogues. `cve_precedent.csv` tags each ([C1] to [C11]) and marks its relation.

- **Direct APF analogues** (a less-trusted principal writes or creates the
  approval-relevant object the app then trusts):
  - [C8] Documenso: a non-signer completes another signer's field and forges the
    signature because the handler checks neither field type nor ownership.
  - [C4] ERPNext: a low-privilege user creates approval-bearing documents through an
    endpoint that omits authorization.
- **Adjacent authorization failures** (same systems, different mechanism, showing
  authorization gaps recur, not APF itself):
  - [C1][C2] Jenkins stale-approval re-execution (a revoked approval re-runs). This is
    an authorization-revalidation flaw in the same user's path, not a separate writer
    forging a human-approval record.
  - [C3] Jenkins sandbox bypass via a manage grant.
  - [C5][C6] Apache OFBiz forced browsing and authentication bypass.
  - [C7] Dolibarr improper authorization.
  - [C9] Airflow cross-scope DAG trigger, [C10] Airflow broken access control.
  - [C11] Argo API authentication bypass under a shipped auth mode.

These are third-party, already-fixed vulnerabilities. They are not disclosures by the
authors. We cite them as related work, with the direct analogues kept separate from the
adjacent cases so the distinction is explicit.

## Candidate classes (not confirmed, for coordinated disclosure)

These follow from the same shipped defaults but are **not** asserted. They are leads for
the authors to verify in a controlled lab and, if confirmed, report through coordinated
disclosure. See `DISCLOSURE_CANDIDATES.md`. No live third-party system was attacked.

- **C-a unauthenticated resume or callback webhook.** A resume or callback endpoint
  reachable without the approval credential.
- **C-b default or committed signing key.** A default HMAC or JWT secret shipped in a
  quickstart that lets a non-authority mint a valid approval token.
- **C-c broker or object store without auth carrying approval payloads.**

## Honesty and scope

- Layer A establishes a capability in the default posture. It does not claim a remote
  unauthenticated internet attacker. The writer is a co-located principal the default
  already admits.
- Layer B cites third-party published CVEs as related work, not as proof of APF. The
  direct analogues are the only ones presented as close analogues.
- Candidate classes are unverified leads only. They require lab confirmation before any
  disclosure, and nothing here is a weaponized exploit.
