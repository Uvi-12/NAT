#!/usr/bin/env python3
"""Per-binding ablation: each binding in the verifier is load-bearing.

For every binding we (1) confirm the intact verifier rejects the matching
attack, then (2) remove exactly that one check from a copy of the verifier
source and confirm the same attack now succeeds. A binding is "necessary" iff
removing it reopens an attack. Mirrors Table (per-binding ablation) in the paper.

Dependency: cryptography. No network.
"""
import importlib.util
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apf_provenance as P
from apf_provenance import (ApprovalBroker, Approver, WorkflowRef, ExecutionRef,
                            Verifier, ExecutionContext, VerificationError, KeyRing,
                            InMemoryNonceStore, new_keypair, Policy, PolicyRule)

SIGNER = new_keypair("key-1")
POLICY = Policy(id="pay", version="7",
                rules=[PolicyRule(action="payments.transfer", environment="default",
                                  approver_groups=("payments-ops",), maximum_amount=100000)],
                group_membership={"cfo@corp": ["payments-ops"]})


def issue(**over):
    d = dict(approver=Approver(subject="cfo@corp", assurance_level="mfa"),
             decision="approve", action_id="payments.transfer", action_fingerprint="fp1",
             args={"recipient": "acct-A", "amount": 1000, "currency": "USD"},
             workflow=WorkflowRef(system="example", run_id="run-1", checkpoint_id="cp-1"),
             execution=ExecutionRef(scope="default", environment="default", audience="payments"),
             approval_point_id="pay-approve", amount=1000)
    d.update(over)
    return ApprovalBroker(SIGNER, policy=POLICY).issue(**d)


def ctx(**over):
    d = dict(action_id="payments.transfer", action_fingerprint="fp1",
             args={"recipient": "acct-A", "amount": 1000, "currency": "USD"},
             run_id="run-1", checkpoint_id="cp-1", approval_point_id="pay-approve",
             scope="default", environment="default", audience="payments")
    d.update(over)
    return ExecutionContext(**d)


def make_verifier(verifier_cls):
    ring = KeyRing(); ring.trust(SIGNER.verifier())
    return verifier_cls(ring, InMemoryNonceStore(), policy=POLICY)


def load_ablated(drop_message):
    """Load a copy of the verifier module with one check (identified by its
    error message) neutralised by turning its `raise` into `pass`."""
    src_path = HERE / "apf_provenance" / "verifier.py"
    src = src_path.read_text()
    needle = f'raise VerificationError("{drop_message}")'
    if needle not in src:
        return None
    patched = src.replace(needle, "pass  # [ablated]")
    mod = types.ModuleType("verifier_ablated")
    # resolve the module's relative imports against the real package
    mod.__dict__.update({
        "arguments_commitment": P.arguments_commitment,
        "ApprovalEvent": P.ApprovalEvent, "KeyRing": P.KeyRing,
        "NonceStore": P.NonceStore, "Policy": P.Policy,
    })
    body = "\n".join(l for l in patched.splitlines()
                     if not l.lstrip().startswith(("from ", "import ")))
    body = "import time\nfrom dataclasses import dataclass, field\nfrom typing import Optional\n" + body
    exec(compile(body, str(src_path), "exec"), mod.__dict__)
    return mod.Verifier


# (error message in verifier, family reopened, attack context override)
CASES = [
    ("arguments commitment mismatch", "Rebind", {"args": {"recipient": "EVIL", "amount": 1000, "currency": "USD"}}),
    ("run id mismatch", "Replay (cross-run)", {"run_id": "run-2"}),
    ("checkpoint id mismatch", "Replay (forking)", {"checkpoint_id": "cp-OTHER"}),
    ("audience mismatch", "Cross-domain reuse", {"audience": "other"}),
    ("environment mismatch", "Cross-environment reuse", {"environment": "staging"}),
    ("nonce already consumed (replay)", "Temporal/concurrent replay", "SECOND_USE"),
]


def attack(verifier, over):
    v = make_verifier(verifier)
    if over == "SECOND_USE":
        ev = issue(); v.verify_and_consume(ev, ctx()); v.verify_and_consume(ev, ctx()); return
    v.verify_and_consume(issue(), ctx(**over))


def main():
    ok = True
    print(f"{'binding':34} {'family reopened':26} intact  ablated")
    for msg, family, over in CASES:
        # intact verifier must reject
        try:
            attack(Verifier, over); intact = "ACCEPT"
        except (VerificationError, Exception):
            intact = "reject"
        AV = load_ablated(msg)
        if AV is None:
            print(f"{msg:34} {family:26} {intact:7} (check not found)"); ok = False; continue
        try:
            attack(AV, over); ablated = "ACCEPT"
        except Exception:
            ablated = "reject"
        necessary = (intact == "reject" and ablated == "ACCEPT")
        print(f"{msg:34} {family:26} {intact:7} {ablated:7} {'necessary' if necessary else 'UNEXPECTED'}")
        ok &= necessary
    print("\nRESULT:", "PASS (every binding is load-bearing)" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
