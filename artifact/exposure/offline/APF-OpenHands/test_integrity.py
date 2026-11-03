import os, tempfile, uuid, pytest
import workflow as w
from store import open_store
def _s():
    p = os.path.join(tempfile.gettempdir(), f"gh_oh_{uuid.uuid4().hex}.json"); return open_store(p), p
def test_control_policy_always_blocks():
    s, p = _s()
    try:
        w.start_transfer(s); r = w.resume(s)
        assert r["executed"] is False and r["status"] == "BLOCKED"
    finally: os.path.exists(p) and os.remove(p)
def test_policy_downgrade_executes():
    s, p = _s()
    try:
        w.start_transfer(s); w.forge_policy_downgrade(s); r = w.resume(s)
        assert r["executed"] is True
    finally: os.path.exists(p) and os.remove(p)
def test_policy_downgrade_leaves_NO_approval_record():   # evasion by absence
    s, p = _s()
    try:
        w.start_transfer(s); w.forge_policy_downgrade(s); r = w.resume(s)
        assert r["executed"] is True and r["approval_record_present"] is False and r["approver"] == ""
    finally: os.path.exists(p) and os.remove(p)
@pytest.mark.parametrize("i", range(5))
def test_policy_downgrade_deterministic(i):
    s, p = _s()
    try:
        w.start_transfer(s); w.forge_policy_downgrade(s)
        assert w.resume(s)["executed"] is True
    finally: os.path.exists(p) and os.remove(p)
def test_decision_forge_executes_WITH_record():          # contrast: SRS forge leaves a forged record
    s, p = _s()
    try:
        w.start_transfer(s); n = "Rahul S. (Senior Compliance Officer) [14:32:01]"
        w.forge_decision_event(s, n); r = w.resume(s)
        assert r["executed"] is True and r["approval_record_present"] is True and r["approver"] == n
    finally: os.path.exists(p) and os.remove(p)
