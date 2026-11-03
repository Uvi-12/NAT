"""Integrity analysis tooling for Semantic Kernel process-state human-in-the-loop.

This package demonstrates that an approval decision serialized into a Semantic Kernel
process step's state is trusted on restore without integrity verification.
"""
from .workflow import START_AMOUNT, ApprovalState, ApprovalStep, resume, start_transfer

__all__ = [
    "START_AMOUNT",
    "ApprovalState",
    "ApprovalStep",
    "resume",
    "start_transfer",
]
__version__ = "1.0.0"
