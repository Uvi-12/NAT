from ga_pydanticai.workflow import build_agent, Ledger, start, resume
from ga_pydanticai.store import ApprovalStore
from ga_pydanticai.forge import forge_inject_return

APPROVER = "Rahul S. (Senior Compliance Officer)"


def _started():
    agent = build_agent()
    led = Ledger()
    history, call_id = start(agent, led)
    return agent, history, call_id


def test_start_defers_without_executing():
    agent, history, call_id = _started()
    led = Ledger()
    _, redeferred = resume(agent, led, history)
    assert led.executed is False
    assert redeferred is True


def test_control_no_approval_stays_blocked():
    agent, history, call_id = _started()
    led = Ledger()
    resume(agent, led, history)
    assert led.executed is False


def test_history_forge_does_not_execute_real_tool():
    agent, history, call_id = _started()
    forged = forge_inject_return(history, call_id, APPROVER)
    led = Ledger()
    resume(agent, led, forged)
    # the fabricated return may end the narration, but the guarded side effect never runs
    assert led.executed is False


def test_deferred_approval_executes():
    agent, history, call_id = _started()
    led = Ledger()
    resume(agent, led, history, approve_call_id=call_id, approver=APPROVER)
    assert led.executed is True
    assert led.approver == APPROVER


def test_forge_is_deterministic():
    for _ in range(5):
        agent, history, call_id = _started()
        forged = forge_inject_return(history, call_id, APPROVER)
        led = Ledger()
        resume(agent, led, forged)
        assert led.executed is False
