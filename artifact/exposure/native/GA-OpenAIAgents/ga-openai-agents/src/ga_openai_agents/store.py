"""A JSON-file store for serialized OpenAI Agents SDK run state."""
from __future__ import annotations

import json
import os
from typing import Optional


class RunStateStore:
    """Persist and load a serialized run state as JSON."""

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


def open_store(path: str) -> RunStateStore:
    return RunStateStore(path)


def read_state(path: str) -> Optional[dict]:
    store = RunStateStore(path)
    return store.load() if store.exists() else None
