"""Integrity analysis for BeeAI ask-permission gating, a resistant case.

BeeAI obtains a tool approval from a live handler at decision time and never persists
the decision to a reloaded store, so there is no persistence-layer artifact to forge.
This package demonstrates that resistance against the real requirement gate.
"""
from .workflow import TOOL_NAME, run_gate, settle
from .forge import persisted_approval_surface

__all__ = ["TOOL_NAME", "run_gate", "settle", "persisted_approval_surface"]
__version__ = "1.0.0"
