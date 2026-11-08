# APF native reproduction, TUF (The Update Framework, python-tuf)

Native-tier (N1) reproduction against the **real `tuf` 7.0.1** API and
`securesystemslib` signer. Promotes the Layer-2 TUF row (L2-36) from N2 to native.

- **System / version:** python-tuf **7.0.1** (`pip install tuf==7.0.1`).
- **Decisive surface:** the signed `targets` metadata, the authoritative record of
  which artifacts are approved for use. The decision is bound to an Ed25519 signature.
- **Dependency:** `tuf`, `securesystemslib`. Run: `python run.py`.

## What it shows (captured in `run_output.txt`)

A genuine `targets` metadata listing one approved artifact is signed by the approval
authority and persisted. **Control:** the genuine metadata verifies against the
trusted key. **Forge (state-only):** a state-writer edits the persisted metadata JSON
to inject a malicious target (`backdoor.tgz`) and re-serializes it, keeping the old
signature (it holds no key). **Resume:** verifying the tampered metadata against the
trusted key is **rejected** (`UnverifiedSignatureError`). re-signing with the
attacker's own key is also rejected (untrusted key).

Verdict: **RESISTANT**, the authorized set of artifacts is authored by a signature
the state-writer cannot produce, so a state-only write to the persisted metadata is
caught at verification. This is the native confirmation of the Layer-2 TUF row: the
decisive evidence the resume path trusts is cryptographically bound, not merely
stored. Not a gated crypto-only claim. It is the native-tier upgrade of the TUF row.
