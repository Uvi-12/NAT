# APF native reproduction, Sigstore signature verification (cosign)

Covers the resistant Layer-2 rows whose approval/issuance decision is bound to a
Sigstore signature the state-writer cannot produce: **Sigstore Fulcio (L2-26)**
and **Sigstore policy-controller (L2-35)**.

- **Tier:** native (N1) for the signature-verification mechanism.
- **Tool / version:** real `cosign` **v2.4.1** (Sigstore), key-based offline mode.
- **Run:** `bash run.sh` (needs `cosign` on PATH or `./bin/cosign`. Install line in the script).
- **Decisive surface:** a Sigstore signature / attestation over the approval
  record. The consume path verifies the signature against the approval
  authority's public key.
- **What it shows:** the genuine approval, signed by the authority's key, verifies,
  a state-only write that edits the persisted record and reuses the genuine
  signature is **rejected** (the signature does not cover it). An attacker who
  self-signs the forged record without the authority key is **rejected**. Captured
  in `OUTPUT.txt`.
- **Verdict:** Resistant (native), confirms the corpus verdict with the real tool.

**Scope note (honest).** This runs the Sigstore signing/verification core via
cosign with a local key. The full keyless path (Fulcio-issued short-lived certs,
Rekor transparency log, OIDC) and the policy-controller Kubernetes admission
webhook are network-/cluster-bound and are not stood up here. The cryptographic
property they rest on, resume/admission verifies a signature the state-writer
cannot forge, is exactly what is reproduced.
