# APF native reproduction, in-toto

Native-tier (N1) reproduction against the **real `in-toto` 3.1.0** library. Promotes
the Layer-2 in-toto row (L2-34) from N2 to native.

- **System / version:** in-toto **3.1.0** (`pip install in-toto==3.1.0`).
- **Decisive surface:** the signed step attestation ("link"), and the policy
  ("layout"), that attest which artifacts a supply-chain step produced. Bound to the
  functionary's Ed25519 signature.
- **Dependency:** `in-toto`, `securesystemslib`. Run: `python run.py`.

## What it shows (captured in `run_output.txt`)

A functionary signs a `build` link attesting the approved product artifact. It is
persisted. **Control:** the genuine link verifies against the functionary key.
**Forge (state-only):** a state-writer edits the persisted link JSON to swap the
attested product hash to a malicious artifact, keeping the old signature (no key).
**Resume:** verifying the tampered link is **rejected**
(`SignatureVerificationError`).

Verdict: **RESISTANT**, the step attestation is bound to the functionary's
signature, so a state-only edit of the persisted link is caught at verification and
the writer cannot re-sign without the key. Native confirmation of the Layer-2 in-toto
row. Not a gated crypto-only claim. It is the native-tier upgrade of the in-toto row.
