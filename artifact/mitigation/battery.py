#!/usr/bin/env python3
"""Adversarial battery for the provenance-bound approval verifier.

Runs the full family of attacks a workflow-state writer can mount against the
resume-time check, plus the genuine control. Every attack must be rejected and
the one genuine approval must be accepted exactly once (including under a
concurrent race). Exit code is non-zero if any case behaves unexpectedly.

Only dependency is `cryptography` (for Ed25519). No network, no Docker.
"""
import concurrent.futures as cf
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apf_provenance import (ApprovalBroker, Approver, WorkflowRef, ExecutionRef,
                            Verifier, ExecutionContext, VerificationError, KeyRing,
                            InMemoryNonceStore, new_keypair, Policy, PolicyRule)

SIGNER = new_keypair("key-1")
POLICY = Policy(id="pay", version="7",
                rules=[PolicyRule(action="payments.transfer", environment="default",
                                  approver_groups=("payments-ops",), maximum_amount=100000)],
                group_membership={"cfo@corp": ["payments-ops"]})


def broker():
    return ApprovalBroker(SIGNER, policy=POLICY)


def ctx(**over):
    d = dict(action_id="payments.transfer", action_fingerprint="fp1",
             args={"recipient": "acct-A", "amount": 1000, "currency": "USD"},
             run_id="run-1", checkpoint_id="cp-1", approval_point_id="pay-approve",
             scope="default", environment="default", audience="payments")
    d.update(over)
    return ExecutionContext(**d)


def issue(**over):
    d = dict(approver=Approver(subject="cfo@corp", assurance_level="mfa"),
             decision="approve", action_id="payments.transfer", action_fingerprint="fp1",
             args={"recipient": "acct-A", "amount": 1000, "currency": "USD"},
             workflow=WorkflowRef(system="example", run_id="run-1", checkpoint_id="cp-1"),
             execution=ExecutionRef(scope="default", environment="default", audience="payments"),
             approval_point_id="pay-approve", amount=1000)
    d.update(over)
    return broker().issue(**d)


def new_verifier():
    ring = KeyRing(); ring.trust(SIGNER.verifier())
    return Verifier(ring, InMemoryNonceStore(), policy=POLICY), ring


def expect_reject(label, fn):
    try:
        fn()
    except (VerificationError, PermissionError) as e:
        print(f"  REJECT  {label:42} ({type(e).__name__})")
        return True
    print(f"  !! ACCEPTED (should have rejected): {label}")
    return False


def expect_accept(label, fn):
    try:
        fn(); print(f"  ACCEPT  {label}"); return True
    except Exception as e:  # noqa
        print(f"  !! REJECTED genuine approval: {label} ({e})")
        return False


def main():
    ok = True
    print("Family: control (genuine approval on the reviewed action)")
    v, _ = new_verifier()
    ok &= expect_accept("genuine approval, exact bindings", lambda: v.verify_and_consume(issue(), ctx()))

    print("\nFamily: Forge (no issued event / a rejection presented as approval)")
    v, _ = new_verifier()
    ok &= expect_reject("decision=deny presented at resume", lambda: v.verify_and_consume(issue(decision="deny"), ctx()))

    print("\nFamily: Rebind (genuine approval, mutated arguments)")
    for over in ({"args": {"recipient": "acct-A", "amount": 999999, "currency": "USD"}},
                 {"args": {"recipient": "EVIL", "amount": 1000, "currency": "USD"}},
                 {"action_id": "db.delete"}):
        v, _ = new_verifier()
        ok &= expect_reject(f"rebound {list(over)[0]}={list(over.values())[0]}",
                            lambda o=over: v.verify_and_consume(issue(), ctx(**o)))

    print("\nFamily: Replay (reuse across run / audience / second use)")
    for over in ({"run_id": "run-2"}, {"scope": "other"}, {"environment": "staging"}, {"audience": "other"}):
        v, _ = new_verifier()
        ok &= expect_reject(f"replay to {list(over)[0]}={list(over.values())[0]}",
                            lambda o=over: v.verify_and_consume(issue(), ctx(**o)))
    v, _ = new_verifier(); ev = issue(); v.verify_and_consume(ev, ctx())
    ok &= expect_reject("second use of a consumed nonce", lambda: v.verify_and_consume(ev, ctx()))
    v, _ = new_verifier()
    ok &= expect_reject("expired artifact (ttl in the past)", lambda: v.verify_and_consume(issue(ttl_seconds=-1), ctx()))

    print("\nFamily: Suppress (policy / key integrity)")
    v, ring = new_verifier(); ev = issue(); ring.revoke("key-1")
    ok &= expect_reject("revoked issuer key", lambda: v.verify_and_consume(ev, ctx()))
    ok &= expect_reject("unauthorized approver refused at issuance",
                        lambda: issue(approver=Approver(subject="intern@corp", assurance_level="mfa")))

    print("\nFamily: Launder (cross-context reuse, checkpoint)")
    v, _ = new_verifier()
    ok &= expect_reject("reuse on a different checkpoint", lambda: v.verify_and_consume(issue(), ctx(checkpoint_id="cp-OTHER")))

    print("\nConcurrent replay: 100 workers race one artifact, exactly one may execute")
    v, _ = new_verifier(); ev = issue()
    def attempt(i):
        try:
            v.verify_and_consume(ev, ctx(execution_id=f"w{i}")); return 1
        except VerificationError:
            return 0
    with cf.ThreadPoolExecutor(max_workers=32) as ex:
        wins = sum(ex.map(attempt, range(100)))
    print(f"  executions = {wins} (expected 1)")
    ok &= (wins == 1)

    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
