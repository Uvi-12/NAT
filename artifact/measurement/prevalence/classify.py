#!/usr/bin/env python3
"""Lexical, file-level APF classifier for a fetched file.

Given the text of a file that uses an exposed framework's human-in-the-loop API,
decide whether the file itself contains an explicit provenance-verification signal
(cryptographic verification, a key, a nonce, or fresh re-authorization) or not.

Returns VERIFIED, TRUSTS_STATE (gate keyword present, no such signal), or NO_GATE.
It reads one file and traces no data flow, so errors run in both directions: a
loose token can mislabel a file VERIFIED (lowering the estimate), and a verifier
kept in a different file is missed (raising it). See RESULTS.md.
"""
import re, sys

# Provenance-verification tokens. An earlier draft also matched the bare tokens
# `signature`, `verify(` (without a receiver), and `sign(`; hand reading showed they
# matched Python function signatures, generic test helpers, and words such as
# `design(`/`assign(`, so they were removed. The method-call form `.verify(` (as in
# `public_key.verify(...)`) is kept. Hand judgments are in data/validation.csv.
VERIFY = [
    r"\bhmac\b", r"verify_signature", r"check_signature", r"signature[._]verify",
    r"\bverify_sig\b", r"\bsig_verify\b", r"\bed25519\b", r"\becdsa\b",
    r"rsa\.verify", r"\.verify\(", r"jwt\.decode", r"verify_jwt", r"decode_jwt",
    r"\bnonce\b", r"re-?authoriz", r"\breauth\b", r"verify_approval",
    r"approval_token", r"approval_signature", r"constant_time", r"compare_digest",
    r"\bx509\b", r"public_key", r"\bpubkey\b", r"private_key", r"\bgpg\b", r"\bpgp\b",
    r"sigstore", r"\bcosign\b", r"\bin-toto\b", r"cryptograph", r"detached.?sig",
]
# signals that an approval/resume gate is present at all
GATE = [
    r"interrupt\(", r"Command\(resume", r"needs_approval", r"human_input",
    r"HumanResponseEvent", r"InputRequiredEvent", r"human_input_mode",
    r"pause_flow_run", r"resume_flow_run", r"DeferredTool", r"wait_condition",
    r"approve", r"approval", r"resume", r"\bWait\b",
]

def classify(text):
    t = text.lower()
    has_gate = any(re.search(p, text, re.I) for p in GATE)
    if not has_gate:
        return "NO_GATE"
    has_verify = any(re.search(p, text, re.I) for p in VERIFY)
    return "VERIFIED" if has_verify else "TRUSTS_STATE"

if __name__ == "__main__":
    print(classify(open(sys.argv[1]).read()))
