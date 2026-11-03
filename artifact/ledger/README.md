# Tamper-evident evidence ledgers

Each `evidence-<framework>.json` is an append-only transparency log of approval
and guard events, with an RFC 6962 Merkle tree and an Ed25519 signed tree head.
Verify them offline, using only the embedded public key, with:

    python3 ../../scripts/verify_ledger.py .

The ledger records are preserved from the assessment. The log wrapper is signed
under the key in `ledger_public_key.pem`.
