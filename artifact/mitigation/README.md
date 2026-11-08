# Provenance-bound approval, reference implementation of the mechanism

`apf_provenance/` is an open-source reference implementation of the APF defense,
not a product or a service: a library a developer drops in front of their own
paused-workflow resume path. It is the mechanism, described at the level of the
wire artifact it produces and the checks it enforces, a signed, execution-bound
approval artifact, a canonical encoding (RFC 8785 JCS), a versioned and hashed
policy, an atomic single-use nonce store, and a fail-closed verifier that checks
issuer, decision, action, argument commitment, run, checkpoint, audience,
environment, execution scope, policy hash, freshness, and nonce before releasing
the action. It has no control plane and no service-side coupling, and holds no
state beyond the nonce store the caller provides. Keys, transport, and the store
are the integrator's choice.

- `battery.py`  , the adversarial battery (claim C3)
- `ablation.py` , per-binding ablation (claim C4)
- `overhead_bench.py`, verification microbenchmark (claim C6)
- `ablation.csv`, `overhead.csv`, recorded reference outputs
