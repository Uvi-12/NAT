# Default-deployment reachability of the approval state

This study answers one objection directly. The objection is that a state-writer attack
only shows the consequence of a compromised database. It does not. We show that in each
listed vendor's **own default or quickstart deployment**, a principal that is **not** the
approval authority can already reach the store that holds the decisive approval field,
using nothing but the configuration the vendor ships.

The claim is deliberately narrow, and it is tied to the authoritative approval object,
not to a string. For every row, the decisive field (`approval_field`) is the exact one
the native reproduction in `artifact/exposure/native/` identifies as the field the
runtime trusts to release the protected action. Reaching a secondary index or a
visibility store is **not** reachability of the approval state, and such rows are
excluded. See "What was removed and why" below.

## The reachability predicate

For a system S with approval field F in store D, a principal W is a **default-reachable
non-approval writer** when, in S's official default deployment:

1. **Write.** W can write F in D, where F is the field the native reproduction shows the
   runtime trusts (not a secondary index, not a visibility projection).
2. **Not the authority.** W is not the human reviewer or the approval service, and gains
   nothing from the trusted approval path.
3. **No stronger capability.** W is not assumed to hold the protected-tool credential,
   application secrets, host execution, or the workflow service credential. It has only
   what the default deployment already grants it.

## How a non-approval principal reaches the store (three classes)

- **R1 shipped shared or superuser credential.** The default connects the app and every
  co-located container to D as a database superuser or one shared role, under a
  documented, often trivial password. Any co-located principal that holds it writes F.
- **R2 co-located non-approval worker shares one all-DML role.** The vendor ships extra
  containers, background-job workers, schedulers, admin UIs, that use the same single
  database role, which has full write on the approval table. A worker is not the approval
  authority but can write F.
- **R3 the permission model conflates manage and approve.** The platform's own
  access-control grant that lets a principal operate a workflow is the same grant that
  writes the approval or resume state. No finer permission separates resume-this-gate
  from write-this-status.

R1 closes under credential hygiene. R2 and R3 persist under correct credentials, because
they follow from the shipped architecture (one DB role shared by non-approval workers)
and the platform's RBAC. Those two are the load-bearing classes.

## Evidence, backing, and reproduction

`reachability.csv` records, per system: the decisive approval field, the
default-reachable non-approval writer, the class, the **native backing**, the
signal status, the vendor default-manifest URL, and a verbatim locator in that file.
`collect.py` re-fetches each vendor default manifest and re-extracts the shipped
credential or grant, so the configuration half of every row is checkable against the
upstream source. The script reports `SIGNAL_PRESENT`, not `CONFIRMED`, precisely because
a present string is only the configuration half. The other half, that the runtime trusts
F, is shown by the native reproduction named in `native_backing`: OpenEMR carries an
obtained native verdict (EXPOSED, L2-22), the other four have the decisive field
confirmed in source against their native harness, and Argo's decisive field is the
suspend-node status (L2-01), reached state-only. `writer_scope` records the second
honesty point: the five database-backed systems ship a broad role that owns every
table, including identity and secrets, so the principal there is not narrower than the
application, while Argo's `update workflows` grant is scoped and does not reach secrets.

The six systems and their decisive fields are OpenEMR (`billing.authorized`), ERPNext
(`docstatus`), DocuSeal (`submitters.completed_at`), Documenso (`Document.status`),
LedgerSMB (`transactions.approved`), and Argo Workflows (suspend-node `.status`). A fully
controlled, offline, end-to-end restricted-identity demonstration of the same predicate,
with a database that enforces the privilege separation, is in
`restricted_identity_demo/`.

## What was removed and why

An earlier version of this audit listed ten systems. Four were removed after review
because the reached store was not the authoritative approval state, or the writer was
mischaracterized. Recording the removal is part of being honest by construction.

- **Temporal (removed).** The earlier row treated unauthenticated Elasticsearch as
  approval-state reachability. Temporal's Elasticsearch is a visibility index, not the
  authoritative workflow execution history. Writing the visibility index does not rewrite
  accepted history. Temporal is also classified Resistant in the substrate ledger, so
  listing it as exposed was an internal contradiction.
- **Conductor (removed).** Its Elasticsearch is an indexing backend for workflow and task
  search. State persistence can be PostgreSQL or another database, so unauthenticated
  Elasticsearch does not establish writable human-task authorization state. Conductor's
  exposure verdict in the main corpus stands on its own evidence. This default-deployment
  reachability row did not, and was removed.
- **n8n (removed).** The earlier row said the `n8n-runner` container shares the
  application database role. The official Compose passes the runner an authentication
  token and broker address, not database credentials. The separate queue-mode worker does
  receive database credentials, but it also receives the application encryption key, which
  breaks this study's restricted-attacker model (no application secrets). Either way the
  clean claim did not hold, so the row was removed.
- **Dify (removed).** Dify has no native forge target in the reproduction kit, so its
  decisive field is not independently pinned here. The row was configuration-only and was
  removed rather than carried at a weaker standard than the rest.

## Scope and honesty

- This establishes that the capability exists in the default posture. It does not claim a
  remote, unauthenticated internet attacker. The writer is a co-located principal the
  default already admits.
- A hardened operator can close R1 (set credentials), R2 (split roles, isolate workers),
  and R3 (custom RBAC). The finding is that the shipped default does not.
- Default trivial credentials are not reported as vulnerabilities. They are the documented
  quickstart posture. The R3 permission-model observation is the one a maintainer may treat
  as a design question. It is raised with them, not asserted as a product defect.
