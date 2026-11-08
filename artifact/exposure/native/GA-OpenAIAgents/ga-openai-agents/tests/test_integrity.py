"""Integrity tests for the OpenAI Agents SDK tool-approval state.

These tests assert a binary property: with no recorded approval a flagged transfer
stays blocked; a single approval written into the serialized run state causes execution
on restore.
"""
import os
import tempfile
import uuid

import pytest

from ga_openai_agents.forge import inject_approval
from ga_openai_agents.store import open_store
from ga_openai_agents.workflow import resume, start_transfer



def _store():
    path = os.path.join(tempfile.gettempdir(), f"ga_oai_test_{uuid.uuid4().hex}.json")
    return open_store(path), path


def test_control_no_approval_stays_blocked():
    store, path = _store()
    try:
        start_transfer(store)
        result = resume(store)
        assert result["executed"] is False
        assert result["status"] == "REJECTED"
    finally:
        os.path.exists(path) and os.remove(path)


def test_forged_approval_executes():
    store, path = _store()
    try:
        start_transfer(store)
        inject_approval(store, approver="Anjali D.")
        result = resume(store)
        assert result["approved"] is True
        assert result["executed"] is True
    finally:
        os.path.exists(path) and os.remove(path)


def test_forged_approver_is_recorded():
    store, path = _store()
    try:
        start_transfer(store)
        name = "Pooja J. (Senior Compliance Officer) [14:32:01]"
        inject_approval(store, approver=name)
        result = resume(store)
        assert result["approver"] == name
        assert name in result["message"]
    finally:
        os.path.exists(path) and os.remove(path)


@pytest.mark.parametrize("run", range(5))
def test_forge_is_deterministic(run):
    store, path = _store()
    try:
        start_transfer(store)
        inject_approval(store, approver="Neha L.")
        assert resume(store)["executed"] is True
    finally:
        os.path.exists(path) and os.remove(path)

