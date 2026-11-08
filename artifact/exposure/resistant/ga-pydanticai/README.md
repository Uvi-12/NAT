# ga-pydanticai

Integrity analysis for PydanticAI human-in-the-loop approval (resistant case).

## Summary

PydanticAI gates a tool with `requires_approval=True`. On run, the call is
**deferred**: the agent returns a `DeferredToolRequests` instead of executing the
tool. The decision is supplied on resume through the `DeferredToolResults` API
(`ToolApproved` / `ToolDenied`), keyed by the tool-call id. The decision is not
read back from the persisted message history.

This package shows that an attacker who can write the persisted message-history
store **cannot** force the guarded action:

- **control** (resume on the persisted history, no approval supplied): the run
  re-defers. The guarded tool does not execute.
- **forge** (inject a fabricated approved tool-return into the persisted
  history): the model may narrate completion, but the real guarded tool never
  executes.
- **legitimate** (approval supplied through the `DeferredToolResults` API): the
  guarded tool executes.

PydanticAI therefore resists the Decision-Provenance Integrity forge: execution
requires the deferred approval result on resume, which a state-writer does not
control.

## Install

```bash
pip install -e ".[test]"     # requires pydantic-ai>=1.0, Python 3.10+
```

## Usage

```bash
ga-pydanticai demo
python -m pytest tests/ -v
```
