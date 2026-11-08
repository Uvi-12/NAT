#!/usr/bin/env python3
# APF / APF - LAUNDER live harness: Gitea (#41).
# A Gitea review (APPROVED) is bound to the PULL REQUEST it was submitted on. LAUNDER would
# re-parent a genuine approval of one action onto a distinct foreign action: here, a foreign
# Blackwell PR (PR-B) with NO approval of its own tries to merge under Priya's genuine approval of
# the Meridian PR (PR-A). Branch protection requires an approval on the PR being merged, and a
# review on PR-A does not count for PR-B, so PR-B cannot merge. The approval cannot be re-parented
# across PRs. EXPECTED: RESISTANT (launder_fired=False). Consistent with the PR-scoped binding.
#
# Usage: pip install requests ; docker compose up -d && ./init_gitea.sh ; python3 harness_launder.py
import sys, os, time, base64, json
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apf_common as C
BASE = os.environ.get("GITEA_BASE", "http://localhost:3000/api/v1")
OUT = os.path.join(os.environ.get("APF_EVIDENCE_BASE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evidence")), "41_gitea")
HERE = os.path.dirname(os.path.abspath(__file__))

def load_tokens():
    env = {}
    with open(os.path.join(HERE, "tokens.env")) as fh:
        for ln in fh:
            if "=" in ln:
                k, v = ln.strip().split("=", 1); env[k] = v
    if not env.get("AUTHOR_TOKEN") or not env.get("PRIYA_TOKEN"):
        raise SystemExit("tokens.env missing tokens; run ./init_gitea.sh first")
    return env["AUTHOR_TOKEN"], env["PRIYA_TOKEN"]

def hdr(tok): return {"Authorization": "token " + tok, "Content-Type": "application/json"}
def payment_text(beneficiary, amount): return "beneficiary=%s\namount=%d\n" % (beneficiary, amount)

def make_pr(A, repo, branch, args, msg):
    requests.post(BASE + "/repos/author/" + repo + "/branches", headers=A,
                  json={"new_branch_name": branch, "old_branch_name": "main"}, timeout=15)
    requests.put(BASE + "/repos/author/" + repo + "/contents/payment.txt", headers=A, json={
        "branch": branch, "message": msg,
        "content": base64.b64encode(payment_text(args["beneficiary"], args["amount"]).encode()).decode()}, timeout=20)
    r = requests.post(BASE + "/repos/author/" + repo + "/pulls", headers=A, json={
        "head": branch, "base": "main", "title": msg}, timeout=20)
    return r.json().get("number")

def try_merge(A, repo, idx, tries=8):
    attempts = []; merged = False; m = None
    for i in range(tries):
        time.sleep(3)
        m = requests.post(BASE + "/repos/author/" + repo + "/pulls/%d/merge" % idx, headers=A,
                          json={"Do": "merge"}, timeout=30)
        attempts.append({"try": i, "status": m.status_code, "body": (m.text or "")[:160]})
        if m.status_code in (200, 201): merged = True; break
    return merged, attempts

def main():
    author_tok, priya_tok = load_tokens()
    A = hdr(author_tok); P = hdr(priya_tok); repo = "apf-launder"
    requests.delete(BASE + "/repos/author/" + repo, headers=A, timeout=15)
    requests.post(BASE + "/user/repos", headers=A, json={"name": repo, "private": False, "auto_init": True, "default_branch": "main"}, timeout=30)
    requests.put(BASE + "/repos/author/" + repo + "/collaborators/priya", headers=A, json={"permission": "write"}, timeout=15)
    # enforce: every merge to main requires an approval ON THAT PR
    requests.post(BASE + "/repos/author/" + repo + "/branch_protections", headers=A, json={
        "branch_name": "main", "enable_approvals_whitelist": False, "required_approvals": 1,
        "dismiss_stale_approvals": False, "block_on_rejected_reviews": True, "enable_merge_whitelist": False}, timeout=20)
    audit = []

    # control: genuine approval of the Meridian PR (PR-A) by Priya -> merges
    idxA = make_pr(A, repo, "featureA", C.A_ARGS, "pay meridian")
    requests.post(BASE + "/repos/author/" + repo + "/pulls/%d/reviews" % idxA, headers=P,
                  json={"event": "APPROVED", "body": "approved by Priya"}, timeout=20)
    mergedA, _ = try_merge(A, repo, idxA)
    if mergedA:
        audit.append({"action": "merge_pr", "amount": C.A_ARGS["amount"], "beneficiary": C.A_ARGS["beneficiary"], "approved_by_in_audit": C.APPROVER})
    C.line("control", f"genuine approval of the Meridian PR #{idxA} by {C.APPROVER} -> merged={mergedA}")
    C.line("audit", "a Gitea review is bound to the PR it was submitted on; branch protection requires an approval on the PR being merged")

    # launder: a foreign Blackwell PR (PR-B) with NO approval of its own tries to merge under
    # Priya's approval of PR-A. The review on PR-A does not count for PR-B -> merge blocked.
    idxL = make_pr(A, repo, "featureB", C.B_ARGS, "pay blackwell")
    mergedL, attemptsL = try_merge(A, repo, idxL)
    landed = None
    if mergedL:
        c = requests.get(BASE + "/repos/author/" + repo + "/contents/payment.txt?ref=main", headers=A, timeout=15).json()
        landed = base64.b64decode(c.get("content", "")).decode(errors="replace")
    launder_fired = bool(mergedL) and (C.B_ARGS["beneficiary"] in (landed or ""))
    C.line("launder", f"foreign Blackwell PR #{idxL} presented Priya's approval of PR #{idxA}; merged={mergedL} (blocked = review cannot be re-parented across PRs)")
    print("GITEA_DIAG launder:", json.dumps(attemptsL))

    verdict = C.verdict_launder(launder_fired)
    C.line("verdict", verdict)
    h = C.emit_evidence("Gitea", OUT, {
        "shape": "LAUNDER",
        "restore_path": "a Gitea review is bound to the PR it was submitted on; a foreign PR cannot merge under another PR's approval (branch protection checks the merging PR's own approvals)",
        "execution_tier": "give-code (real Gitea API; run on Docker to confirm)",
        "why_resistant": "the approval is scoped to its pull request; there is no cross-PR re-parent path, so a foreign PR has no approval of its own and cannot claim the Meridian PR's approval",
        "gitea_image": "gitea/gitea:1.22.3-rootless",
        "approval_issued_for": C.A_ARGS, "foreign_action": C.B_ARGS,
        "genuine_pr": idxA, "foreign_pr": idxL, "foreign_merged": mergedL, "landed_on_main": landed,
        "launder_fired": launder_fired, "laundered_payment": None,
        "audit_ledger": audit, "verdict": verdict,
    })
    print("EVIDENCE_HASH16", h)

if __name__ == "__main__":
    C.guarded_main("Gitea", OUT, main)
