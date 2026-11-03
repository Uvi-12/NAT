package approval.native

# Ordinary approval-completeness check, representative of audit/compliance
# tooling that validates that an approval record is STRUCTURALLY complete.
# It accepts any record that looks like a finished human approval. It has no
# way to tell a genuine approval from a state-write forgery, because both
# produce the same native fields.

default allow := false

allow if {
    input.decision == "approved"
    input.approver != ""
    input.timestamp != ""
    input.action_status == "succeeded"
}
