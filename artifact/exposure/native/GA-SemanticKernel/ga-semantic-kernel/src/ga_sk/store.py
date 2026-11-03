"""A JSON-file state store for serialized Semantic Kernel process state.

Semantic Kernel provides no built-in human-in-the-loop persistence, so an application
supplies its own. This minimal store stands in for that application-provided layer.
"""
from __future__ import annotations

import json
import os
from typing import Optional


class StateStore:
    """Persist and load a single process step's serialized state as JSON."""

    def __init__(self, path: str) -> None:
        self.path = path

    def save(self, state: dict) -> None:
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, separators=(",", ":"))

    def load(self) -> dict:
        with open(self.path, encoding="utf-8") as handle:
            return json.load(handle)

    def exists(self) -> bool:
        return os.path.exists(self.path)


def open_store(path: str) -> StateStore:
    return StateStore(path)


def read_state(path: str) -> Optional[dict]:
    store = StateStore(path)
    return store.load() if store.exists() else None
