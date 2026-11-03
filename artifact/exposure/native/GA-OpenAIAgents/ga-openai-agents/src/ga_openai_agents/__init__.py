"""Integrity analysis tooling for OpenAI Agents SDK tool-approval state.

This package demonstrates that a tool-approval decision serialized in the SDK's run
state is trusted on restore without integrity verification.
"""
from .workflow import START_AMOUNT, TOOL_NAME, initial_state, resume, settle, start_transfer

__all__ = [
    "START_AMOUNT",
    "TOOL_NAME",
    "initial_state",
    "resume",
    "settle",
    "start_transfer",
]
__version__ = "1.0.0"
