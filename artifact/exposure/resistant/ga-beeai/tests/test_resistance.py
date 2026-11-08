"""Resistance tests: BeeAI's approval decision tracks the live handler and there is no
persisted approval artifact to forge. These classify BeeAI as resistant under the
Decision-Provenance Integrity predicate (decision re-derived from a live input on
resume; no persisted authorization surface)."""
import asyncio

import pytest

from ga_beeai.forge import persisted_approval_surface
from ga_beeai.workflow import run_gate, settle


async def deny(tool, tool_input):
    return False


async def allow(tool, tool_input):
    return True


def test_live_deny_blocks():
    assert asyncio.run(settle(deny))["executed"] is False


def test_live_allow_permits():
    assert asyncio.run(settle(allow))["executed"] is True


@pytest.mark.parametrize("run", range(5))
def test_decision_tracks_live_handler(run):
    assert asyncio.run(run_gate(deny)) is False
    assert asyncio.run(run_gate(allow)) is True


def test_no_persisted_approval_artifact():
    surface = persisted_approval_surface()
    assert surface["has_persisted_approval"] is False
    assert surface["requirement_is_serializable"] is False
    assert surface["serialization_methods_found"] == []
