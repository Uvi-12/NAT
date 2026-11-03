#!/usr/bin/env python3
"""Local microbenchmark for approval-artifact authentication.

Measures the cryptographic verification cost only (sign/verify of the canonical
payload). It deliberately EXCLUDES durable nonce storage, networking, identity,
and scheduling; those are deployment-specific and are discussed in the paper.
Reports median / p95 / p99 in microseconds. Dependency: cryptography.
"""
import hashlib
import hmac
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apf_provenance import new_keypair, canonicalize

SIGNER = new_keypair("key-1")
VERIFIER = SIGNER.verifier()
PAYLOAD = canonicalize({
    "issuer": "approval-authority", "decision": "approve",
    "action": "payments.transfer",
    "args": {"recipient": "acct-A", "amount": 1000, "currency": "USD"},
    "run": "run-1", "checkpoint": "cp-1", "audience": "payments",
    "policy_version": "7", "nonce": "n-1", "expires_at": 1793335570,
})
if isinstance(PAYLOAD, str):
    PAYLOAD = PAYLOAD.encode()
SIG = SIGNER.sign(PAYLOAD)

# Symmetric baseline: HMAC-SHA-256 over the same canonical payload. Appropriate
# only when every holder of the key is inside the approval-authority boundary;
# included so the three Table XII rows reproduce from one script.
HMAC_KEY = b"approval-authority-shared-key-000"
HMAC_TAG = hmac.new(HMAC_KEY, PAYLOAD, hashlib.sha256).digest()


def hmac_verify():
    return hmac.compare_digest(hmac.new(HMAC_KEY, PAYLOAD, hashlib.sha256).digest(), HMAC_TAG)


def bench(fn, n):
    xs = []
    for _ in range(n):
        t = time.perf_counter_ns(); fn(); xs.append(time.perf_counter_ns() - t)
    xs.sort()
    us = lambda v: round(v / 1000, 3)
    return us(statistics.median(xs)), us(xs[int(n * 0.95)]), us(xs[int(n * 0.99)])


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    print(f"payload = {len(PAYLOAD)} bytes; n = {n}; python {sys.version.split()[0]}")
    print(f"{'operation':24} {'median(us)':>11} {'p95':>8} {'p99':>8}")
    for label, fn, reps in (
        ("HMAC verify", hmac_verify, max(n, 200000)),
        ("Ed25519 sign", lambda: SIGNER.sign(PAYLOAD), min(n, 20000) if n >= 20000 else n),
        ("Ed25519 verify", lambda: VERIFIER.verify(PAYLOAD, SIG), n),
    ):
        m, p95, p99 = bench(fn, reps)
        print(f"{label:24} {m:>11} {p95:>8} {p99:>8}")
    print("\nNote: verification cost is small relative to human-review latency; "
          "end-to-end overhead is deployment-specific (durable nonce, network, identity excluded).")


if __name__ == "__main__":
    main()
