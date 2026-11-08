#!/usr/bin/env python3
"""L2-30 Galaxy, native APF reproduction (EXPOSED), model/ORM tier.

Decisive surface (corpus): managers/sharable.py:106,158 and model/__init__.py:3656 -
a History/dataset becomes world-visible when its persisted `published` boolean is
true. The authorized path is the owner's publish action through the sharable
manager; the APF forge is a single state-only write to the `published` column, with
no publish action and by no owner.

This harness boots Galaxy's REAL model layer (galaxy.model) and REAL schema
(galaxy.model.mapping.init creates the tables), creates a private History through
the real ORM, applies the documented read-path predicate (`History.published ==
True`, the filter the published-histories index uses), forges the column with one
raw UPDATE, and re-reads through the real ORM session. galaxy.managers (the thin
controller wrapper over this predicate) is not in the galaxy-data distribution, so
this run is model/ORM tier: it drives the real persistence and model, not the HTTP
controller. Honest by construction: any failure is recorded INCONCLUSIVE.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from apf_ev import Evidence, guard, EXPOSED, RESISTANT

OUT = os.path.join(HERE, "evidence", "L2-30_galaxy")
DB = os.path.join(HERE, "galaxy_apf.sqlite")

ev = Evidence(
    app_id="L2-30", system="Galaxy", expected_verdict=EXPOSED,
    decisive_surface="History.published (model/__init__.py:3656; managers/sharable.py:106,158)",
    mechanism="PFV (public-flag value in a writable relational row)",
)

with guard(ev, OUT):
    import galaxy.model as m
    import galaxy.model.mapping as mp
    from galaxy.version import VERSION as GV  # type: ignore
    ev.runtime = "pip galaxy-data, galaxy.model from site-packages/galaxy/model/__init__.py"
    ev.version = f"galaxy-data {GV}"
    from sqlalchemy import select, text

    if os.path.exists(DB):
        os.remove(DB)
    mapping = mp.init("/tmp", f"sqlite:///{DB}", create_tables=True)
    session = mapping.session() if callable(getattr(mapping, "session", None)) else mapping.session
    ev.step("runtime", f"real schema created by galaxy.model.mapping.init; {ev.version}")

    owner = m.User(email="owner@example.com", password="x", username="owner")
    other = m.User(email="other@example.com", password="x", username="other")
    h = m.History(name="unpublished-analysis", user=owner)
    assert h.published is False, "fresh History must default published=False"
    session.add_all([owner, other, h]); session.commit()
    hid = h.id
    ev.step("legitimate_state",
            f"History id={hid} owned by '{owner.username}', published={h.published} (private)")

    # Read-path predicate used by the published-histories index (sharable.py:158).
    published_q = select(m.History).where(m.History.published == True)  # noqa: E712
    visible = session.execute(published_q).scalars().all()
    control_hidden = hid not in [x.id for x in visible]
    ev.step("control",
            f"published-index query returns {len(visible)} rows; target world-visible: "
            f"{not control_hidden}. Authorized path to flip this is the owner's publish "
            f"action via the sharable manager.")
    assert control_hidden, "control failed: history visible before any publish"

    # FORGE: single state-only write. No publish action, no owner, no manager call.
    session.execute(text("UPDATE history SET published = 1 WHERE id = :i"), {"i": hid})
    session.commit(); session.expire_all()
    ev.step("forge", "UPDATE history SET published=1 (one column; no publish action, no owner)")

    # Re-read through the REAL ORM / model.
    h2 = session.get(m.History, hid)
    visible2 = session.execute(published_q).scalars().all()
    now_visible = hid in [x.id for x in visible2]
    ev.step("resume_readback",
            f"real ORM reload: History.published={h2.published}; published-index query now "
            f"returns {len(visible2)} rows; target world-visible: {now_visible}")

    if h2.published is True and now_visible and control_hidden:
        ev.verdict = EXPOSED
        ev.step("verdict", "EXPOSED, a state-only write to `published` makes the record "
                            "world-visible through the real model read path, with no publish "
                            "action, no owner, and no provenance check on the column.")
    else:
        ev.verdict = RESISTANT
        ev.step("verdict", "model re-read did not treat the forged column as published")
