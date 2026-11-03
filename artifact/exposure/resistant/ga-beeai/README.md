# ga-beeai

Integrity analysis for BeeAI ask-permission gating, **a resistant case**.

## Summary

This is the second falsifiability anchor for the Decision-Provenance Integrity (DPI)
study. BeeAI's human-in-the-loop control is the `AskPermissionRequirement`. When a
guarded tool is about to run, the requirement calls a **live handler**
(`self._handler(tool, input)`, default an interactive confirm) and blocks the tool if it
returns False. The decision is held only in an in-memory `_state` cache and is **never
serialized to a store that is reloaded on resume**.

Under the DPI predicate, *is the decision persisted as trusted state, or re-derived
from a live input on resume?*, BeeAI falls on the **re-derived** side, and resists.
There is no persisted approval artifact for a persistence-layer attacker to forge.

Observed behaviour (against the real `AskPermissionRequirement._ask` gate):

- **Live handler denies** → the tool is blocked.
- **Live handler allows** → the tool is permitted.
- **Persistence-layer forge attempt** → there is nothing to write: the requirement is
  not serializable, exposes no `to_dict`/`from_dict`/snapshot, and the agent persists
  only conversation memory, not the approval decision.

## Why it resists

The approval is obtained from a live handler at decision time and is never written to a
reloaded persistence layer. The structural reason matches Mastra (decision re-derived
from live input), via a different concrete mechanism (a confirmation handler rather than
a schema-validated resume payload). The persistence boundary is therefore not an
authorization surface.

### Honest nuance

The in-memory `_state` cache *is* trusted if mutated in-process, but that is not the
DPI threat. DPI concerns the **persistence boundary**: an attacker who can write the
checkpoint/session/approval store. BeeAI exposes no such persisted approval artifact, so
the DPI forge has no surface. An in-process attacker already has full control and is out
of scope for this property.

## Install & run

```bash
pip install -e .            # add [test] for the test suite: pip install -e ".[test]"
ga-beeai demo               # deny (blocked), forge attempt (nothing to forge), allow (permitted)
ga-beeai surface            # report the absent persisted approval surface
pytest
```

Requires Python 3.10+ and `beeai-framework>=0.1`.

## Expected demo output

```
== gate with a live DENY decision ==
  status=REJECTED executed=False
  Transfer rejected; tool not permitted by the live handler.
== attempt a persistence-layer forge ==
  persisted approval artifact present: False
  decision source: live handler callback (AskPermissionRequirement._handler)
  nothing to forge: the decision never reaches a reloaded store.
== gate with a live ALLOW decision (legitimate) ==
  status=EXECUTED executed=True
  Executed transfer of $100,000.00 to ACME-CORP; approved by Rahul S. (Senior Compliance Officer) [14:32:01].
```

## Layout

```
src/ga_beeai/
  workflow.py   drive the real AskPermissionRequirement gate
  forge.py      report the (absent) persisted approval surface
  cli.py        demo / deny / allow / surface
tests/          resistance test suite
examples/       runnable demo
```

## Scope

A research artifact for evaluating HITL state integrity. It drives the real
`AskPermissionRequirement` gate with deterministic handlers. No model API key is needed.
The point is the negative result: BeeAI's approval decision is not persisted to a
reloaded store, so the DPI forge that succeeds against checkpoint-trusting frameworks
has no surface here. Use only against systems you are authorized to test.
