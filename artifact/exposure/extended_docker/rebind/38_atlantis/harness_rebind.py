#!/usr/bin/env python3
# APF / APF - REBIND reproduction harness: Atlantis (+ Gitea) (#38)
#
# Restore path: the apply gate. Atlantis requires a VCS approval before `atlantis apply`
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

    # fresh repo
    requests.delete(BASE + "/repos/author/%s" % REPO, headers=A, timeout=15)
    r = requests.post(BASE + "/user/repos", headers=A, json={
        "name": REPO, "private": False, "auto_init": True, "default_branch": "main"}, timeout=30)
    if r.status_code not in (201, 409):
        raise SystemExit("repo create failed: %s %s" % (r.status_code, r.text[:200]))
    requests.put(BASE + "/repos/author/%s/collaborators/priya" % REPO, headers=A,
                 json={"permission": "write"}, timeout=15)

    # webhook -> atlantis (same docker network hostname)
    requests.post(BASE + "/repos/author/%s/hooks" % REPO, headers=A, json={
        "type": "gitea", "active": True,
        "config": {"url": "http://atlantis:4141/events", "content_type": "json", "secret": "apfsecret"},
        "events": ["push", "pull_request", "issue_comment"]}, timeout=15)

    # feature branch + commit A (Meridian) with atlantis.yaml
    requests.post(BASE + "/repos/author/%s/branches" % REPO, headers=A,
                  json={"new_branch_name": "feature", "old_branch_name": "main"}, timeout=15)
    put_file(A, "atlantis.yaml", "feature", "atlantis config",
             open(os.path.join(HERE, "repo_files", "atlantis.yaml")).read())
    put_file(A, "main.tf", "feature", "pay meridian", main_tf(C.A_ARGS["beneficiary"], C.A_ARGS["amount"]))

    # branch protection: default (dismiss stale approvals OFF) = the exposed config
    requests.post(BASE + "/repos/author/%s/branch_protections" % REPO, headers=A, json={
        "branch_name": "main", "enable_approvals_whitelist": False, "required_approvals": 1,
        "dismiss_stale_approvals": False, "ignore_stale_approvals": False,
        "block_on_rejected_reviews": True}, timeout=20)

    up = wait_atlantis_up()
    C.line("audit", f"atlantis health before PR open: {up}")

    # open PR (Atlantis auto-plans plan A)
    r = requests.post(BASE + "/repos/author/%s/pulls" % REPO, headers=A, json={
        "head": "feature", "base": "main", "title": "APF terraform payment"}, timeout=20)
    idx = r.json().get("number")
    if not idx:
        raise SystemExit("PR create failed: %s %s" % (r.status_code, r.text[:200]))
    planned = wait_atlantis_comment(A, idx, "ran Plan")
    C.line("control", f"PR #{idx} opened; atlantis auto-plan seen={planned}")

    # priya approves plan A (Meridian) -- genuine approval
    requests.post(BASE + "/repos/author/%s/pulls/%d/reviews" % (REPO, idx), headers=P,
                  json={"event": "APPROVED", "body": "approved by Priya"}, timeout=20)
    C.line("audit", f"priya approved the Meridian plan; dismiss_stale_approvals=false (default)")

    # ---- swap: commit B (Blackwell), no re-approval; atlantis re-plans plan B ----
    sha = file_sha(A, "main.tf", "feature")
    put_file(A, "main.tf", "feature", "swap to blackwell", main_tf(C.B_ARGS["beneficiary"], C.B_ARGS["amount"]), sha=sha)
    wait_atlantis_comment(A, idx, "ran Plan")  # plan B
    time.sleep(3)

    # apply under the stale approval
    requests.post(BASE + "/repos/author/%s/issues/%d/comments" % (REPO, idx), headers=A,
                  json={"body": "atlantis apply"}, timeout=15)
    applied = wait_atlantis_comment(A, idx, "ran Apply")
    time.sleep(3)
    log = read_paylog()
    rebind_fired = C.B_ARGS["beneficiary"] in (log or "")
    b_row = None
    if rebind_fired:
        b_row = {"action": "execute_payment", "amount": C.B_ARGS["amount"],
                 "beneficiary": C.B_ARGS["beneficiary"], "approved_by_in_audit": C.APPROVER}
    C.line("rebind", f"apply under stale approval -> applied_comment={applied}; payment log tail: {json.dumps((log or '').strip()[-160:])}")

    seen = set(); nonce = "n-runA-0038"

    if not planned and not applied:
        verdict = "INCONCLUSIVE"   # Atlantis never engaged (no plan, no apply); cannot conclude
    else:
        verdict = C.verdict_rebind(rebind_fired)
    suffix = "" if verdict == "INCONCLUSIVE" else " (default config); RESISTANT when Gitea dismiss_stale_approvals enabled"
    C.line("verdict", verdict + suffix)
    h = C.emit_evidence("Atlantis", OUT, {
        "shape": "REBIND",
        "execution_tier": "give-code (real Atlantis+Gitea, default config; run on Docker to confirm)",
        "genuine_args": C.A_ARGS, "mutated_args": C.B_ARGS,
        "restore_path": "apply gate trusts the VCS approval (apply_requirements: approved); binding inherited from Gitea Dismiss stale approvals",
        "atlantis_image": "ghcr.io/runatlantis/atlantis:v0.31.0", "gitea_image": "gitea/gitea:1.22.3-rootless",
        "composed_with": "Gitea approval binding (#41)",
        "pr_number": idx, "auto_plan_seen": planned, "apply_comment_seen": applied,
        "payment_log_tail": (log or "").strip()[-300:],
        "rebind_fired": rebind_fired, "rebound_payment": b_row,
        "audit_ledger": [b_row] if b_row else [], "verdict": verdict,
        "note": "Atlantis is a design-adjacent case: it re-plans on new commits but trusts the VCS approval for apply. EXPOSED when the VCS keeps stale approvals; RESISTANT when Gitea dismisses them (or when a plan-content-bound approval is required).",
    })
    print("EVIDENCE_HASH16", h)


if __name__ == "__main__":
    C.guarded_main('Atlantis', OUT, main)
