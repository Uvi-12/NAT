# ga-openai-agents

Integrity analysis for OpenAI Agents SDK tool-approval state.

## Summary

When a tool is marked `needs_approval`, the OpenAI Agents SDK interrupts the run and
serializes its run state, including the approvals map, so the run can be resumed once
a human approves. On resume the approvals are rebuilt with
`RunContextWrapper._rebuild_approvals(...)`, and the Runner consults `is_tool_approved`
before invoking the tool.

This package shows that the approval decision is trusted on restore **without any
integrity verification**. `_rebuild_approvals` accepts whatever serialized approvals map
is provided, and `is_tool_approved` returns `True` for any tool whose record carries
`approved: true`. Nothing checks that the map reflects a real human decision. Writing
`{tool: {"approved": true}}` into the serialized run state is therefore sufficient for
the restored run to treat the tool as approved.

The property demonstrated is binary:

- **No approval recorded** → `is_tool_approved` returns `None`. The transfer stays blocked.
- **One approval written** into the serialized approvals map → `is_tool_approved`
  returns `True` and the transfer executes, attributed to an attacker-chosen approver.


## Install

```bash
pip install -e .            # add [test] for the test suite: pip install -e ".[test]"
```

Requires Python 3.10+ and `openai-agents>=0.17`.

## Usage

```bash
ga-openai-agents demo                          # start, control resume, forge, resume
ga-openai-agents start                         # persist the initial unapproved run state
ga-openai-agents status                        # report persisted state
ga-openai-agents forge [--approver NAME]       # record a tool approval in the run state
ga-openai-agents resume    # restore run state and settle
```

Expected `demo` output:

```
== start ==
started transfer amount=$100,000.00 recipient=ACME-CORP (awaiting approval)
== resume (control) ==
resumed status=REJECTED approved=False executed=False approver=''
  Transfer rejected; tool not approved.
== forge ==
injected approval approver='Rahul S. (Senior Compliance Officer) [14:32:01]'
== resume ==
resumed status=EXECUTED approved=True executed=True approver='Rahul S. (Senior Compliance Officer) [14:32:01]'
  Executed transfer of $100,000.00 to ACME-CORP; approved by Rahul S. (Senior Compliance Officer) [14:32:01].
```

The forged decision carries an attacker-chosen approver identity that propagates into
the executed transfer's audit line, a named approval that never occurred.

## How it works

Settlement uses the SDK's own restore-and-check path:

```python
context = RunContextWrapper(context=None)
context._rebuild_approvals(state["approvals"])        # the from_json restore path
approved = context.is_tool_approved("wire_transfer", call_id) is True
```

`ga_openai_agents.forge.inject_approval` sets `state["approvals"]["wire_transfer"] =
{"approved": True}` before restore. `_rebuild_approvals` accepts it and `is_tool_approved`
returns `True`, so the tool is treated as approved.

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
src/ga_openai_agents/
  workflow.py   approval workflow, SDK restore-and-check path, settlement
  store.py      JSON run-state store
  forge.py      record a tool approval in the run state
  cli.py        start / status / forge / resume / demo
tests/          integrity test suite
examples/       runnable end-to-end demo
```

## Scope

This is a research artifact for evaluating the integrity of tool-approval state. It
exercises the real `RunContextWrapper._rebuild_approvals` / `is_tool_approved` path. The
tool execution itself is represented by the settlement step so no model API key is
needed. The required capability is the ability to write the serialized run state. The
finding is that the SDK trusts the rebuilt approvals on restore with no integrity check.
Use only against systems you are authorized to test.
