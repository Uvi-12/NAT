# Disclosure candidates and precedent register

This register separates two very different things, so a reader never mistakes one for
the other.

## Section 1. Published CVEs cited as precedent (already fixed, nothing to disclose)

These are third-party vulnerabilities in the public record. They are listed in
`cve_precedent.csv` as evidence that the reachability vectors in `vectors.md` Layer B
are real and recurrent. They are already disclosed and fixed upstream. We claim no
credit and there is nothing for us to report. They are here only for the record and
for the paper's independent-corroboration argument.

| tag | system | CVE | relation to APF | status |
|---|---|---|---|---|
| C8 | Documenso | CVE-2026-71247 | direct analogue (forge) | fixed upstream |
| C4 | ERPNext (Frappe) | CVE-2026-109615 | direct analogue (missing authz) | fixed upstream |
| C1 | Jenkins (workflow-cps) | CVE-2024-52550 | adjacent (stale approval) | fixed upstream |
| C2 | Jenkins (pipeline-model-definition) | CVE-2024-52551 | adjacent (stale approval) | fixed upstream |
| C3 | Jenkins (shared-library-override) | CVE-2024-52554 | adjacent (sandbox bypass) | fixed upstream |
| C5 | Apache OFBiz | CVE-2024-45195 | adjacent (forced browsing) | fixed upstream |
| C6 | Apache OFBiz | CVE-2023-51467 | adjacent (authn bypass) | fixed upstream |
| C7 | Dolibarr | CVE-2021-3991 | adjacent (improper authz) | fixed upstream |
| C9 | Apache Airflow | CVE-2026-32228 | adjacent (cross-scope) | fixed upstream |
| C10 | Apache Airflow | CVE-2023-50944 | adjacent (broken access) | fixed upstream |
| C11 | Argo Workflows | CVE-2024-53862 | adjacent (authn bypass) | fixed upstream |

## Section 2. Candidate findings for the authors to verify, then disclose

These are **leads, not findings**. They were derived from public default deployments
and the public CVE record. None has been confirmed. Each must be reproduced in a
controlled lab against a self-hosted instance the authors control, and only then, if
confirmed, reported through the vendor's coordinated-disclosure channel. This file
gives the pattern and where to look, at the capability level. It contains no
weaponized exploit, and no live third-party system was attacked to produce it.

For each candidate: the system, the class from `vectors.md`, the observable to check,
the expected signal if the lead holds, and the disclosure note.

1. **Workflow resume or callback webhook without the approval credential (C1).**
   - Look: in each workflow or BPMN engine with a suspend or wait node, whether the
     resume, callback, or signal endpoint in the default deployment requires the
     approval credential, or only a URL or a worker token.
   - Signal if it holds: a principal with the worker or callback token advances a
     suspended node without the approval credential.
   - Disclose to: the engine maintainer, as a missing-authorization issue on the
     resume path, not as a default-credential note.

2. **Default or committed signing key for approval tokens (C2).**
   - Look: whether a quickstart ships a fixed HMAC or JWT secret used to sign approval
     or session tokens, and whether production defaults inherit it.
   - Signal if it holds: a non-authority mints a token the runtime accepts as an
     approval, using only the shipped key.
   - Disclose to: the vendor, as a predictable-secret issue (CWE-321), with the
     default manifest locator.

3. **Approval payload on an unauthenticated broker or object store (C3).**
   - Look: whether the default deployment routes the approval or human-task payload
     through a message broker or object store that ships without authentication.
   - Signal if it holds: a network-adjacent principal reads or writes the approval
     payload in transit without the application credential.
   - Disclose to: the vendor, with the default manifest locator.

4. **Re-execution paths that skip approval revalidation (B4 generalization).**
   - Look: beyond Jenkins, whether other CI/CD and workflow engines revalidate the
     approval on rebuild, retry, stage restart, or resume, or trust the stored prior
     state.
   - Signal if it holds: a retry or resume runs a protected action on an approval that
     was revoked or never re-checked.
   - Disclose to: the engine maintainer, with a minimal reproduction.

## Standing rules

- Verify in a lab on an instance the authors own. Do not probe third-party or hosted
  installations.
- One coordinated-disclosure contact per vendor. Honor the embargo window.
- A candidate stays in Section 2 until it is confirmed. A confirmed and assigned CVE
  moves to Section 1 with its identifier.
