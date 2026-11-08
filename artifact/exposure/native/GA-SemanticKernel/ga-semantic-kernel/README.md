# ga-semantic-kernel

Integrity analysis for Semantic Kernel process-state human-in-the-loop (HITL).

## Summary

Semantic Kernel models a workflow as a process composed of steps, each with typed
state. There is no built-in HITL persistence layer, so an application that pauses a
process for approval serializes the step state itself and restores it later. On restore
the state is rebuilt with `ApprovalState.model_validate(...)` and handed to the step via
`activate(...)`.

This package shows that the approval decision is trusted on restore **without any
integrity verification**. `model_validate` and `activate` accept whatever serialized
state is provided. There is no check that it reflects a real human decision. Writing
`transfer_approved=True` into the persisted state is therefore sufficient for the
restored step to report approval.

The property demonstrated is binary:

- **No approval recorded** → the flagged transfer stays blocked.
- **One approval written** into the serialized state → the restored step reports
  approval and the transfer executes, attributed to an attacker-chosen approver.


## Install

```bash
pip install -e .            # add [test] for the test suite: pip install -e ".[test]"
```

Requires Python 3.10+ and `semantic-kernel>=1.0`.

## Usage

```bash
ga-sk demo                            # start, control resume, forge, resume
ga-sk start                           # persist the initial unapproved state
ga-sk status                          # report persisted state
ga-sk forge [--approver NAME]         # record an approval in the persisted state
ga-sk resume      # restore state and settle
```

Expected `demo` output:

```
== start ==
started transfer amount=$100,000.00 recipient=ACME-CORP (awaiting approval)
== resume (control) ==
resumed status=REJECTED approved=False executed=False approver=''
  Transfer rejected; no valid approval recorded.
== forge ==
injected approval approver='Rahul S. (Senior Compliance Officer) [14:32:01]'
== resume ==
resumed status=EXECUTED approved=True executed=True approver='Rahul S. (Senior Compliance Officer) [14:32:01]'
  Executed transfer of $100,000.00 to ACME-CORP; approved by Rahul S. (Senior Compliance Officer) [14:32:01].
```

The forged decision carries an attacker-chosen approver identity that propagates into
the executed transfer's audit line, a named approval that never occurred.

## How it works

On restore, the step state is rebuilt and trusted through the Semantic Kernel path:

```python
approval_state = ApprovalState.model_validate(persisted_state)   # SK / pydantic
step = ApprovalStep()
await step.activate(KernelProcessStepState(name="ApprovalStep", id="ApprovalStep",
                                           version="1.0", state=approval_state))
```

`ga_sk.forge.inject_approval` sets `transfer_approved=True` in the serialized state
before restore. `model_validate`/`activate` accept it unchanged, so the settlement step
reads an approved decision.

## Defense

The provenance-bound defense is not re-litigated in this per-system PoC. It is evaluated centrally against the full attack battery (Forge / Rebind / Replay / Suppress / Launder, plus a concurrent race) and the independently-verifiable signed ledgers, claims C3 and C7 of the artifact.

## Tests

```bash
pytest
```

Covers the negative control, forged-approval execution, approver-identity propagation,
determinism across repeated runs.

## Layout

```
├── src/ga_sk/
│   ├── workflow.py approval process step, restore path, and settlement logic
│   ├── store.py    application-provided JSON state store
│   ├── forge.py    record an approval in the serialized state
│   └── cli.py      start / status / forge / resume / demo
├── tests/          integrity test suite
└── examples/       runnable end-to-end demo
```

## Scope

This is a research artifact for evaluating the integrity of HITL process state. Semantic
Kernel ships no HITL persistence, so the serialized-state store here stands in for the
application-provided layer. The restore path uses the real `model_validate`/`activate`
sequence. The workflow steps are deterministic and offline. No model API key is needed.
The required capability is the ability to write the serialized step state. The finding
is that Semantic Kernel trusts it on restore with no integrity check. Use only against
systems you are authorized to test.
