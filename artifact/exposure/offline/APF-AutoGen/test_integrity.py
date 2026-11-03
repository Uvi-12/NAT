import os, tempfile, uuid, pytest
import runtime
from store import open_store
def _s():
    p = os.path.join(tempfile.gettempdir(), f"gh_test_{uuid.uuid4().hex}.json"); return open_store(p), p
def test_control_no_approval_blocked():
    s, p = _s()
    try:
        runtime.start_transfer(s); r = runtime.resume(s)
        assert r["executed"] is False and r["status"] == "REJECTED"
    finally: os.path.exists(p) and os.remove(p)
def test_forged_state_executes():
    s, p = _s()
    try:
        runtime.start_transfer(s); runtime.inject_approval(s, "Amit K."); r = runtime.resume(s)
        assert r["approved"] is True and r["executed"] is True
    finally: os.path.exists(p) and os.remove(p)
def test_forged_approver_recorded():
    s, p = _s()
    try:
        runtime.start_transfer(s); n = "Rahul S. (Senior Compliance Officer) [14:32:01]"
        runtime.inject_approval(s, n); r = runtime.resume(s)
        assert r["approver"] == n and n in r["message"]
    finally: os.path.exists(p) and os.remove(p)
@pytest.mark.parametrize("i", range(5))
def test_forge_deterministic(i):
    s, p = _s()
    try:
        runtime.start_transfer(s); runtime.inject_approval(s, "Raj M.")
        assert runtime.resume(s)["executed"] is True
    finally: os.path.exists(p) and os.remove(p)
