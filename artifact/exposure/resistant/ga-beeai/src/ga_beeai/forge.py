"""Show that BeeAI exposes no persisted approval artifact to forge.

The Decision-Provenance Integrity forge requires a persisted decision that is reloaded
and trusted on resume. BeeAI's ``AskPermissionRequirement`` holds its decision in a live
handler result and an in-memory cache (``_state``) that is never serialized to a store
or restored on resume, the requirement is not serializable and the agent persists only
conversation memory. This module reports that absence: there is nothing for a
persistence-layer attacker to write.
"""
from __future__ import annotations

from beeai_framework.agents.requirement.requirements.requirement import Requirement
from beeai_framework.agents.requirement.requirements.ask_permission import AskPermissionRequirement


def persisted_approval_surface() -> dict:
    """Return a description of any persisted approval artifact (there is none)."""
    serialization_methods = [m for m in ("to_dict", "from_dict", "serialize", "deserialize",
                                          "create_snapshot", "load_snapshot")
                             if hasattr(Requirement, m) or hasattr(AskPermissionRequirement, m)]
    return {
        "has_persisted_approval": False,
        "requirement_is_serializable": bool(serialization_methods),
        "serialization_methods_found": serialization_methods,
        "decision_source": "live handler callback (AskPermissionRequirement._handler)",
        "note": (
            "The approval decision is obtained from a live handler and cached only in an "
            "in-memory _state dict; it is never persisted to a reloaded store. There is no "
            "persistence-layer artifact to forge."
        ),
    }
