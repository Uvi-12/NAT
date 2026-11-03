"""Persisted message-history store (the artifact an attacker can write).

Real deployments persist PydanticAI message history to continue a run later.
This store serializes it to JSON with the framework's own type adapter, exactly
as a durable store would, so the forge operates on a realistic persisted blob.
"""
from __future__ import annotations
import json

from pydantic_ai.messages import ModelMessagesTypeAdapter


class ApprovalStore:
    def __init__(self) -> None:
        self._blob: bytes | None = None

    def save(self, history) -> None:
        self._blob = ModelMessagesTypeAdapter.dump_json(history)

    def load(self):
        if self._blob is None:
            raise RuntimeError("nothing persisted")
        return ModelMessagesTypeAdapter.validate_json(self._blob)

    # raw access, the capability a state-writer holds
    def load_raw(self) -> list:
        return json.loads(self._blob.decode())

    def save_raw(self, obj: list) -> None:
        self._blob = json.dumps(obj).encode()
