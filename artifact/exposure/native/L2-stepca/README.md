# APF native reproduction, step-ca certificate issuance (L2-27)

- **Tier:** native (N1).
- **Tool / version:** real Smallstep **`step` CLI 0.28.2** (and `step-ca` 0.28.3 available).
- **Run:** `bash run.sh` (needs `step` on PATH or `./step_*/bin/step`. Install line in the script).
- **Decisive surface:** certificate issuance bound to the CA's signature, a
  relying party verifies the chain to the issuing CA root.
- **What it shows:** a genuine leaf signed by the CA verifies against the CA
  bundle. A state-only write that mints a certificate for the same identity
  without the CA key is **rejected**, it does not chain to the issuing CA.
  Captured in `OUTPUT.txt`.
- **Verdict:** Resistant (native), confirms the corpus verdict with the real tool.
