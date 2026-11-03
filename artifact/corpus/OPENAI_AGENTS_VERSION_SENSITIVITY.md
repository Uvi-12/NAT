# OpenAI Agents SDK: why the verdict moves with the version

This is the one framework in the corpus whose verdict is not stable across the
versions we touched, so it deserves its own explanation rather than a footnote.
Read carelessly it looks like a contradiction ("you call it exposed but your own
later run calls it resisted"). Read correctly it is a longitudinal data point
that supports the paper's thesis.

## The three observations

| Version | What was exercised | Forge / Rebind / Replay | Suppress / Launder |
| --- | --- | --- | --- |
| 0.17.4 | 43-study, native | Exposed | Exposed |
| 0.17.7 | workshop subset, native (the pinned version) | Exposed | Exposed |
| 0.24.0 | later assessment, native | **Resisted natively** | Exposed |

The pin is **0.17.7, Exposed**, because that is the version measured in the
corpus. The 0.24.0 result is recorded as version sensitivity.

## What changed in the SDK

At 0.17.x the approval decision lived in the serialized run state as a plain
map, `context.approvals.<tool>.approved`, that the resume path rebuilt and
trusted. A state writer who could edit the serialized `RunState` set
`approved: true` (or changed the arguments the approved call carried) and the
tool executed on resume. That is the SRS (serialized run-state) mechanism, and it
is a textbook instance of approval-provenance failure: the resume path treated a
writable value as the decision.

By 0.24.0 the SDK had hardened the resume path so that the *state-only* families
no longer work: editing the serialized approvals map is not sufficient to
authorize the call, because the decision is re-established at resume rather than
read back verbatim from the snapshot. In our terms, the authoring authority of
the evidence the resume path trusts moved (at least partly) outside the state
writer. So Forge, Rebind, and Replay, the three attacks that are *nothing but* a
write to persisted state, become inert.

## Why it is still exposed at 0.24.0

Two families are not state-only, and they still land:

- **Suppress** removes the *requirement* to approve (it edits the operator-side
  policy/threshold that decides whether the gate fires at all). No amount of
  binding the approval value helps if no approval is required.
- **Launder** carries an approval that is genuine for a *different, lower-risk*
  action into payment authority across a trust boundary. The SDK's intra-run
  binding does not reach a cross-system clearance.

Both live outside the SDK's state-binding, which is exactly the paper's point:
binding the approval artifact to the action defeats Forge/Rebind/Replay, but
Suppress needs **policy integrity** and Launder needs **downstream attestation** , 
separate controls that a per-call signature does not provide.

## How this strengthens the paper

This is the strongest single piece of evidence that APF is a real,
mechanism-level property and not an artifact of old versions:

1. A major SDK, with no prompting from us, moved to bind the approval at resume
   between two releases, independent confirmation that the state-only vector is
   real and worth fixing.
2. The fix it shipped closes exactly the three families our argument predicts a
   per-action binding closes, and leaves exactly the two families our argument
   says need policy integrity and downstream attestation. The theory predicts the
   shape of a real vendor's fix.
3. It converts a version mismatch into a trend line: frameworks are starting to
   bind the state-forge vector. The operator-side vectors remain open across the
   board.

## How we state it in the paper

Pin OpenAI Agents SDK at 0.17.7 (Exposed, SRS) in the corpus table, with a single
sentence of body text:

> Between 0.17 and 0.24 the OpenAI Agents SDK began re-establishing the approval
> decision at resume rather than trusting the serialized approvals map. At 0.24.0
> the three state-only families (Forge, Rebind, Replay) no longer succeed, while
> the operator-side families (Suppress, Launder) still do, independent evidence
> that a per-action binding closes the state-forge vector but not the
> policy-integrity and downstream-attestation gaps the design also addresses.

Do not present 0.17.7 and 0.24.0 as a contradiction. Present them as the fix
landing exactly where the model says it should.
