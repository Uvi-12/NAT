# GA-OpenHands (policy-downgrade / APS)

Distinct from the decision-forge harnesses. OpenHands' event log resists *decision*
forgery, but its persisted confirmation policy (in ConversationState / state.json) does
not. Flipping the policy AlwaysConfirm -> NeverConfirm makes the gate stop firing and
**no approval record is written** (evasion by absence). Contrasted with an ordinary
decision-forge (which leaves a forged record). The provenance-bound defense is evaluated centrally against the full attack battery (C3) and the signed ledgers (C7), not re-litigated per harness. `python cli.py demo`. `python -m pytest test_integrity.py`.
