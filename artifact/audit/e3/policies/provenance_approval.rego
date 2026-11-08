package approval.provenance

# Provenance-aware check. Accepts an approval ONLY if it carries a verifiable,
# context-bound approval artifact issued by the trusted approval service.
#
# NOTE: this .rego file is the canonical, auditable policy; the E3 runner evaluates
# Rego-EQUIVALENT logic and does not invoke OPA. OPA itself does not compute HMACs;
# following standard practice, a deployment verifies
# the signature/nonce/expiry out of band and passes the boolean results plus the
# recomputed args_hash into the evaluation `input`. The cryptographic binding is
# what a state-write adversary cannot satisfy.

default allow := false

allow if {
    art := input.approval_artifact
    art != null
    art.signature_valid == true        # HMAC over {run_id, action, args_hash, approver, nonce, context_hash, expiry}
    art.nonce_valid == true            # nonce present and unused (replay protection)
    art.not_expired == true            # freshness window
    art.run_id == input.run_id         # bound to THIS run
    art.args_hash == input.args_hash   # bound to THESE arguments
    art.approver == input.approver     # bound to THIS approver
    input.trusted_approval_path_event != null
}
