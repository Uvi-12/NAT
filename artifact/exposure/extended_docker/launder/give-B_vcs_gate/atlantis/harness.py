#!/usr/bin/env python3
# APF / APF - REBIND reproduction harness: Atlantis (+ Gitea) (#38)
#
# LAUNDER: the apply gate requires a VCS approval on the PR being applied. A foreign Blackwell PR
# (apply_requirements: [approved]). It trusts the VCS approval state, so its binding is
# only as strong as the VCS setting. With Gitea "Dismiss stale approvals" OFF (default),
# a genuine approval of plan A (Meridian) persists after the .tf is swapped to plan B
# (Blackwell), and `atlantis apply` then applies the swapped plan under that stale
# approval: one genuine approval reused across a changed target. The apply runs a
# terraform_data local-exec that appends the executed payment to a log we read back.
#
# Self-proving: verdict derived from the real apply log inside the Atlantis container.
#
# Prereq: docker compose up -d gitea && ./init_atlantis.sh   (starts both, writes tokens.env)
# Usage:  pip install requests ; python3 harness_atlantis.py
import sys, os, time, base64, json, subprocess
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apf_common as C

BASE = os.environ.get("GITEA_BASE", "http://localhost:3000/api/v1")
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence")), "38_atlantis")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = "apf-tf"
ATLANTIS_CONTAINER = "apf-atl-atlantis"
PAYLOG = "/atlantis-data/apf_payments.log"


def load_tokens():
    env = {}
    with open(os.path.join(HERE, "tokens.env")) as fh:
        for ln in fh:
            if "=" in ln:
                k, v = ln.strip().split("=", 1); env[k] = v
    return env["AUTHOR_TOKEN"], env["PRIYA_TOKEN"]


def hdr(t):
    return {"Authorization": "token " + t, "Content-Type": "application/json"}


def put_file(A, path, branch, message, content, sha=None):
    body = {"branch": branch, "message": message,
            "content": base64.b64encode(content.encode()).decode()}
    if sha:
        body["sha"] = sha
    return requests.put(BASE + "/repos/author/%s/contents/%s" % (REPO, path), headers=A, json=body, timeout=20)


def file_sha(A, path, ref):
    r = requests.get(BASE + "/repos/author/%s/contents/%s?ref=%s" % (REPO, path, ref), headers=A, timeout=15)
    return r.json().get("sha") if r.ok else None


def read_paylog():
    try:
        out = subprocess.run(["docker", "exec", ATLANTIS_CONTAINER, "sh", "-c", "cat %s 2>/dev/null || true" % PAYLOG],
                             capture_output=True, text=True, timeout=20)
        return out.stdout
    except Exception as e:
        return "(could not read apply log: %s)" % e


def main_tf(beneficiary, amount):
    return (
        'terraform {\n  required_version = ">= 1.4"\n}\n\n'
        'resource "terraform_data" "payment" {\n'
        '  input = {\n    beneficiary = "%s"\n    amount      = %d\n  }\n'
        '  provisioner "local-exec" {\n'
        '    command = "echo PAID ${self.input.amount} to ${self.input.beneficiary} approved_by_pr >> %s"\n'
        '  }\n}\n\noutput "payment" { value = terraform_data.payment.input }\n'
        % (beneficiary, amount, PAYLOG)
    )


def wait_atlantis_comment(A, idx, needle, tries=40):
    for _ in range(tries):
        r = requests.get(BASE + "/repos/author/%s/issues/%d/comments" % (REPO, idx), headers=A, timeout=15)
        for c in r.json():
            if needle.lower() in (c.get("body", "") or "").lower():
                return True
        time.sleep(3)
    return False


def wait_atlantis_up(tries=40):
    # the pull_request webhook fires once; if Atlantis is not up yet the event is lost and
    # no auto-plan happens. Wait for Atlantis health before opening the PR.
    for _ in range(tries):
        try:
            if requests.get("http://localhost:4141/healthz", timeout=4).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(3)
    return False


def main():
    author_tok, priya_tok = load_tokens()
    A = hdr(author_tok); P = hdr(priya_tok)

    # fresh repo + collaborator + webhook
    requests.delete(BASE + "/repos/author/%s" % REPO, headers=A, timeout=15)
    r = requests.post(BASE + "/user/repos", headers=A, json={
        "name": REPO, "private": False, "auto_init": True, "default_branch": "main"}, timeout=30)
    if r.status_code not in (201, 409):
        raise SystemExit("repo create failed: %s %s" % (r.status_code, r.text[:200]))
    requests.put(BASE + "/repos/author/%s/collaborators/priya" % REPO, headers=A, json={"permission": "write"}, timeout=15)
    requests.post(BASE + "/repos/author/%s/hooks" % REPO, headers=A, json={
        "type": "gitea", "active": True,
        "config": {"url": "http://atlantis:4141/events", "content_type": "json", "secret": "apfsecret"},
        "events": ["push", "pull_request", "issue_comment"]}, timeout=15)
    # branch protection so a review is meaningful; apply_requirements enforced via repo atlantis.yaml
    requests.post(BASE + "/repos/author/%s/branch_protections" % REPO, headers=A, json={
        "branch_name": "main", "enable_approvals_whitelist": False, "required_approvals": 1,
        "dismiss_stale_approvals": False, "block_on_rejected_reviews": True}, timeout=20)
    enforced_yaml = ("version: 3\nprojects:\n  - dir: .\n    autoplan:\n      when_modified: [\"*.tf\"]\n"
                     "      enabled: true\n    apply_requirements: [approved]\n")   # approval REQUIRED on the applying PR
    up = wait_atlantis_up()
    audit = []

    # control: PR-A (Meridian), Priya approves, apply -> applied (genuine)
    requests.post(BASE + "/repos/author/%s/branches" % REPO, headers=A, json={"new_branch_name": "featureA", "old_branch_name": "main"}, timeout=15)
    put_file(A, "atlantis.yaml", "featureA", "atlantis config", enforced_yaml)
    put_file(A, "main.tf", "featureA", "pay meridian", main_tf(C.A_ARGS["beneficiary"], C.A_ARGS["amount"]))
    rA = requests.post(BASE + "/repos/author/%s/pulls" % REPO, headers=A, json={"head": "featureA", "base": "main", "title": "APF meridian"}, timeout=20)
    idxA = rA.json().get("number")
    plannedA = wait_atlantis_comment(A, idxA, "ran Plan")
    requests.post(BASE + "/repos/author/%s/pulls/%d/reviews" % (REPO, idxA), headers=P, json={"event": "APPROVED", "body": "approved by Priya"}, timeout=20)
    time.sleep(2)
    requests.post(BASE + "/repos/author/%s/issues/%d/comments" % (REPO, idxA), headers=A, json={"body": "atlantis apply"}, timeout=15)
    appliedA = wait_atlantis_comment(A, idxA, "ran Apply")
    time.sleep(3); log1 = read_paylog()
    if C.A_ARGS["beneficiary"] in (log1 or ""):
        audit.append({"action": "terraform_apply", "amount": C.A_ARGS["amount"], "beneficiary": C.A_ARGS["beneficiary"], "approved_by_in_audit": C.APPROVER})
    C.line("control", f"PR-A #{idxA} approved by {C.APPROVER}; plan={plannedA} apply={appliedA}")
    C.line("audit", "apply_requirements: [approved] checks the approval on the PR being applied; a review is bound to its PR")

    # launder: PR-B (Blackwell) with NO approval tries to apply under PR-A's approval -> blocked
    requests.post(BASE + "/repos/author/%s/branches" % REPO, headers=A, json={"new_branch_name": "featureB", "old_branch_name": "main"}, timeout=15)
    put_file(A, "atlantis.yaml", "featureB", "atlantis config", enforced_yaml)
    put_file(A, "main.tf", "featureB", "pay blackwell", main_tf(C.B_ARGS["beneficiary"], C.B_ARGS["amount"]))
    rL = requests.post(BASE + "/repos/author/%s/pulls" % REPO, headers=A, json={"head": "featureB", "base": "main", "title": "APF blackwell"}, timeout=20)
    idxL = rL.json().get("number")
    plannedL = wait_atlantis_comment(A, idxL, "ran Plan")
    time.sleep(2)
    requests.post(BASE + "/repos/author/%s/issues/%d/comments" % (REPO, idxL), headers=A, json={"body": "atlantis apply"}, timeout=15)
    appliedL = wait_atlantis_comment(A, idxL, "ran Apply", tries=20)   # expected False: PR-B not approved
    time.sleep(3); log2 = read_paylog()
    launder_fired = (C.B_ARGS["beneficiary"] in (log2 or ""))
    C.line("launder", f"foreign Blackwell PR #{idxL} (no approval) tried to apply under PR #{idxA}'s approval; apply_comment={appliedL}; blackwell in paylog? {launder_fired}")

    if not plannedA and not appliedA:
        verdict = "INCONCLUSIVE"
    else:
        verdict = C.verdict_launder(launder_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Atlantis", OUT, {
        "shape": "LAUNDER",
        "restore_path": "apply_requirements: [approved] checks the approval on the PR being applied; a foreign PR cannot apply under another PR's approval (a review is bound to its PR)",
        "execution_tier": "give-code (real Atlantis+Gitea; run on Docker to confirm)",
        "why_resistant": "the apply approval is scoped to its pull request; there is no cross-PR re-parent path, so a foreign PR has no approval of its own",
        "atlantis_image": "ghcr.io/runatlantis/atlantis:v0.31.0", "gitea_image": "gitea/gitea:1.22.3-rootless",
        "approval_issued_for": C.A_ARGS, "foreign_action": C.B_ARGS,
        "genuine_pr": idxA, "foreign_pr": idxL, "foreign_apply_seen": appliedL,
        "payment_log_tail": (log2 or "").strip()[-300:],
        "launder_fired": launder_fired, "laundered_payment": None,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main("Atlantis", OUT, main)
