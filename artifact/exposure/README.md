# Exposure reproductions

- `offline/`, 12 standard-library harnesses that reconstruct each system's
  documented resume/consume path against a local store (the N2 tier). Run them
  all with `python3 offline/run_offline.py`. Control blocks. A state-only forge
  of the persisted approval executes the gated action.
- `native/`, single-framework proofs of concept that drive the real framework
  (install that framework first. See each folder's README).
- `resistant/`, resistant-by-design controls: the same state-only forge is
  inert because the resume path re-derives authority from a live or issuer-held
  decision, not from the snapshot.
- `extended_docker/`, optional durable-engine and VCS-chain reproductions that
  need Docker and live services. Not part of the gated claims.
