# Why APF is new: positioning against its nearest neighbours

A reviewer's first instinct is to ask whether Approval-Provenance Failure is just
a known class under a new name. It is not, and the distinction is sharp. APF is
about *who is permitted to author the evidence a resume path accepts as proof of
human approval*, at the one moment a paused workflow rebuilds its decision from
persisted state. Its four nearest neighbours each differ on a specific axis.

Paste-ready paragraph (≈150 words):

> APF extends the confused-deputy lineage rather than the prompt-injection or
> agent-safety one. The classic confused deputy [Hardy. Saltzer–Schroeder]
> concerns a privileged program tricked into misusing *its own* authority on a
> caller's behalf. APF identifies the dual failure at a *pause–resume* boundary,
> where the deputy is the resume path and the "caller" is operational state an
> infrastructure principal wrote. Unlike CSRF, no victim session or ambient
> credential is ridden: the state writer never uses the approval channel at all.
> Unlike a TOCTOU race, there is no timing window to win. The forged value is
> accepted on the normal, unraced resume path because nothing binds it to an
> approver. Unlike replay, the attack needs no genuine prior approval to
> capture, Forge and Suppress manufacture or delete the decision outright. The
> unifying property APF names is *authoring topology*: resistance holds only when
> the evidence accepted at resume comes from an authority the state writer cannot
> author, a property we measure across 43 systems and bind in a provenance-based
> defense.

## Comparison table (drop-in)

| Property | Confused deputy | CSRF | TOCTOU | Replay | **APF (this work)** |
| --- | --- | --- | --- | --- | --- |
| Who acts | privileged deputy misusing its authority | victim's browser/session | racing threads/processes | attacker re-sending captured evidence | **infrastructure principal that can write state but cannot approve** |
| What is abused | the deputy's ambient authority | the victim's ambient credential | a check-to-use time gap | a genuine prior approval | **the resume path's trust in approval-shaped persisted state** |
| Needs a genuine prior approval? | no | no (rides live credential) | no | **yes** | no (Forge/Suppress manufacture or delete it) |
| Uses the real approval channel? | n/a | yes (victim's) | n/a | yes (captured) | **no, never touches the approval channel** |
| Timing-dependent? | no | no | **yes** | no | no (accepted on the normal resume path) |
| What defeats it | least privilege / designation | tokens / same-site | atomic check-use | nonce / freshness | **binding the approval artifact to an authority the writer cannot author** |

The rightmost column is the contribution: a named, measured property with a
falsifiable discriminator (the resistant controls and the two-reach sensitivity
test), not a restatement of any neighbour. Replay is the closest single family , 
and APF's defense subsumes replay as one of five families (Forge, Rebind, Replay,
Suppress, Launder), of which replay is the only one that requires a captured
genuine approval.
