#!/usr/bin/env python3
# APF / APF - REBIND reproduction harness: Kestra OSS (#34)
#
# REBIND shape: ONE genuine human approval of the payment as reviewed (args A = Meridian),
# but before the gated post-pause task executes a state writer mutates the argument to B.
# The flow's payment reads the amount/beneficiary from Kestra's KV Store (a namespaced,
# mutable store exposed over REST); the Pause task's onResume approval carries only the
# decision {approved, approver} and is bound to neither the argument values nor a nonce.
# A state writer with KV access mutates amt_/ben_ A->B while the execution is PAUSED; the
# genuine approver then resumes, and the post-pause task fires with the MUTATED args,
# paying Blackwell under Priya. (KV mutation over REST stands in for the storage-trust write;
# a flow that binds the payment strictly to frozen execution inputs resists REST mutation, but
# the execution record itself remains mutable via direct DB access - the Airflow-style caveat.)
#
# Self-proving: verdict derived from Kestra's own pay-task output on the rebind run.
#
# Usage:
#   pip install requests
#   docker compose up -d      # wait until the API answers
#   python3 harness_rebind.py
import sys, os, time
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apf_common as C

BASE = os.environ.get("KESTRA_BASE", "http://localhost:8080")
NS = "apf"
FLOW_ID = "apf_payment"
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence")), "34_kestra")

# payment reads amount/beneficiary from KV (execution-id scoped); onResume carries decision only
FLOW_YAML = f"""
id: {FLOW_ID}
namespace: {NS}
inputs:
  - id: amount
    type: INT
  - id: beneficiary
    type: STRING
tasks:
  - id: seed_amount
    type: io.kestra.plugin.core.kv.Set
    key: "amt_{{{{ execution.id }}}}"
    value: "{{{{ inputs.amount }}}}"
  - id: seed_beneficiary
    type: io.kestra.plugin.core.kv.Set
    key: "ben_{{{{ execution.id }}}}"
    value: "{{{{ inputs.beneficiary }}}}"
  - id: wait_for_approval
    type: io.kestra.plugin.core.flow.Pause
    onResume:
      - id: approved
        type: BOOLEAN
      - id: approver
        type: STRING
  - id: execute_payment
    type: io.kestra.plugin.core.debug.Return
    format: "paid|{{{{ kv('amt_' ~ execution.id) }}}}|{{{{ kv('ben_' ~ execution.id) }}}}|{{{{ outputs.wait_for_approval.onResume.approver }}}}|{{{{ outputs.wait_for_approval.onResume.approved }}}}"
"""


def detect_prefix():
    for p in ("/api/v1/main", "/api/v1"):
        try:
            if requests.get(BASE + p + "/flows/search?size=1", timeout=10).status_code == 200:
                return p
        except requests.RequestException:
            pass
    return "/api/v1"


def wait_health(tries=180):
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
    st = None
    for _ in range(tries):
        st = get_exec(P, eid).get("state", {}).get("current")
        if st in states:
            return get_exec(P, eid)
        time.sleep(1)
    raise SystemExit("execution %s did not reach %s (last=%s)" % (eid, states, st))


def resume(P, eid, approved, approver):
    r = requests.post(BASE + P + "/executions/" + eid + "/resume",
                      files={"approved": (None, "true" if approved else "false"),
                             "approver": (None, approver)}, timeout=30)
    return r.status_code, r.text[:200]


def kv_set(P, key, value):
    # state-writer mutation of the KV Store over REST (storage-trust write)
    for body, hdr in ((value, "text/plain"), ('"%s"' % value, "application/json")):
        r = requests.put(BASE + P + "/namespaces/" + NS + "/kv/" + key,
                         data=body.encode(), headers={"Content-Type": hdr}, timeout=20)
        if r.ok:
            return r.status_code
    return r.status_code


def pay_output(ex):
    for tr in ex.get("taskRunList", []):
        if tr.get("taskId") == "execute_payment":
            return (tr.get("outputs") or {}).get("value")
    return None


def main():
    wait_health()
    P = detect_prefix()
    upsert_flow(P)
    audit = []

    # ---- control: genuine approval of args A (Meridian) ----
    eidA = trigger(P, C.A_ARGS["amount"], C.A_ARGS["beneficiary"])
    wait_state(P, eidA, {"PAUSED"})
    resume(P, eidA, True, C.APPROVER)                     # genuine approver acts
    exA = wait_state(P, eidA, {"SUCCESS", "FAILED"})
    outA = pay_output(exA)
    if outA:
        parts = outA.split("|")  # paid|amount|beneficiary|approver|approved
        audit.append({"action": "execute_payment", "amount": int(parts[1]),
                      "beneficiary": parts[2], "approved_by_in_audit": parts[3]})
    C.line("control", f"genuine approval by {C.APPROVER} -> pay task output: {outA}")
    C.line("audit", "onResume approval carries decision only; payment reads args from the mutable KV Store")

    # ---- rebind: state writer mutates the approved args A->B in KV, then the genuine approver resumes ----
    eidB = trigger(P, C.A_ARGS["amount"], C.A_ARGS["beneficiary"])   # Priya reviews Meridian
    wait_state(P, eidB, {"PAUSED"})
    kv_set(P, "amt_" + eidB, str(C.B_ARGS["amount"]))               # mutate args A->B
    kv_set(P, "ben_" + eidB, C.B_ARGS["beneficiary"])
    resume(P, eidB, True, C.APPROVER)                     # genuine approver approves what they reviewed
    exB = wait_state(P, eidB, {"SUCCESS", "FAILED"})
    outB = pay_output(exB)
    rebind_fired = False
    b_row = None
    if outB:
        parts = outB.split("|")
        if parts[2] == C.B_ARGS["beneficiary"] and parts[3] == C.APPROVER and parts[4] in ("true", "True"):
            rebind_fired = True
            b_row = {"action": "execute_payment", "amount": int(parts[1]),
                     "beneficiary": parts[2], "approved_by_in_audit": parts[3]}
            audit.append(b_row)
    C.line("rebind", f"args mutated A->B in KV before pay -> pay task output: {outB}")

    nonce = "n-rebind-0034"

    verdict = C.verdict_rebind(rebind_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Kestra", OUT, {
        "shape": "REBIND",
        "restore_path": "payment reads amount/beneficiary from the mutable KV Store; onResume approval is decision-only",
        "execution_tier": "give-code (real Kestra Pause/resume + KV REST; run on Docker to confirm)",
        "kestra_image": "kestra/kestra:v0.21.5", "api_prefix": P,
        "genuine_run": eidA, "rebind_run": eidB,
        "genuine_args": C.A_ARGS, "mutated_args": C.B_ARGS,
        "rebind_fired": rebind_fired, "rebound_payment": b_row,
        "pay_output_runA": outA, "pay_output_runB": outB,
        "caveat": "EXPOSED when the payment reads args from a mutable store (KV shown). Binding strictly to frozen execution inputs resists REST mutation, but the execution record stays mutable via direct DB access (storage-trust caveat).",
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)


if __name__ == "__main__":
    C.guarded_main("Kestra", OUT, main)
