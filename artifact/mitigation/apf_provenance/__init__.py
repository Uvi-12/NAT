"""Provenance-bound approval protocol (reference implementation, v2).

A dependency-light reference implementation of the APF defense mechanism: a
signed, execution-bound approval event and its verifier, which anyone can run
against their own paused-workflow resume path. The event binds the decision, the
authenticated approver, the exact action and an arguments commitment, the
workflow run and checkpoint, the approval point, the execution scope, the
environment, the audience, the policy version, the timing, and a single-use
nonce. Verification is fail-closed: every bound field must match the actual
execution context, the decision must be approve, and the nonce is consumed
atomically. The mechanism is transport-, store-, and framework-agnostic; it is
not a service and keeps no state beyond the nonce store the caller supplies.
"""

from .canonical import canonicalize, sha256_hex, arguments_commitment
from .event import ApprovalEvent, Approver, ActionRef, WorkflowRef, ExecutionRef, PolicyRef
from .keys import Ed25519Signer, Ed25519Verifier, KeyRing, new_keypair
from .nonce import NonceStore, InMemoryNonceStore
from .policy import Policy, PolicyRule, PolicyDecision
from .issuer import ApprovalBroker
from .verifier import Verifier, VerificationError, ExecutionContext

__all__ = [
    "canonicalize", "sha256_hex", "arguments_commitment",
    "ApprovalEvent", "Approver", "ActionRef", "WorkflowRef", "ExecutionRef", "PolicyRef",
    "Ed25519Signer", "Ed25519Verifier", "KeyRing", "new_keypair",
    "NonceStore", "InMemoryNonceStore",
    "Policy", "PolicyRule", "PolicyDecision",
    "ApprovalBroker", "Verifier", "VerificationError", "ExecutionContext",
]
