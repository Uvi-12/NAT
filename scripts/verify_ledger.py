#!/usr/bin/env python3
"""Independent, offline verification of the tamper-evident evidence ledgers.

Uses only the public key embedded in each ledger. For every ledger it (1)
recomputes the RFC 6962 Merkle root from the entry records and checks it equals
the signed tree head's root, and (2) verifies the Ed25519 signature over the
canonical tree head. No apf/engine code is used or needed. Dependency:
cryptography.

Usage: python scripts/verify_ledger.py artifact/ledger
"""
import base64
import glob
import hashlib
import json
import os
import sys

from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.exceptions import InvalidSignature


def _h(b): return hashlib.sha256(b).digest()
def _leaf(b): return _h(b"\x00" + b)
def _node(l, r): return _h(b"\x01" + l + r)


def _root(leaves):
    if len(leaves) == 1:
        return leaves[0]
    k = 1
    while k < len(leaves):
        k <<= 1
    k >>= 1
    return _node(_root(leaves[:k]), _root(leaves[k:]))


def verify(path):
    d = json.load(open(path))
    sth = d["signed_tree_head"]
    pub = load_pem_public_key(d["ledger_public_key_pem"].encode())
    records = [base64.b64decode(e["record_b64"]) for e in d["entries"]]
    root_ok = _root([_leaf(r) for r in records]).hex() == sth["root_hash"]
    msg = json.dumps({k: sth[k] for k in sth if k != "signature"},
                     sort_keys=True, separators=(",", ":")).encode()
    try:
        pub.verify(bytes.fromhex(sth["signature"]), msg)
        sig_ok = True
    except InvalidSignature:
        sig_ok = False
    return root_ok, sig_ok, sth["tree_size"]


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "artifact/ledger"
    files = sorted([x for x in glob.glob(os.path.join(base, "evidence-*.json")) if "bundle" not in x])
    if not files:
        print("no ledgers found under", base); sys.exit(1)
    all_ok = True
    for f in files:
        root_ok, sig_ok, n = verify(f)
        ok = root_ok and sig_ok
        all_ok &= ok
        print(f"  {os.path.basename(f):34} entries={n:3} "
              f"merkle_root={'OK' if root_ok else 'BAD'} "
              f"tree_head_sig={'OK' if sig_ok else 'BAD'}  "
              f"{'verified' if ok else 'FAILED'}")
    print("\nRESULT:", "PASS (all ledgers verify offline)" if all_ok else "FAIL")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
