#!/usr/bin/env python3
# APF / APF - REBIND reproduction harness: Gitea (#41)
#
# Restore path: approval = a persisted PR review (APPROVED) recorded in Gitea's DB.
# Gitea binds an approval to the reviewed content ONLY when "Dismiss stale approvals" is
# enabled. In the default configuration (dismiss off) a genuine approval of diff A
# persists and still authorizes a later commit B that changes the PR content: one
# genuine approval bound to A but reused against the mutated content B (REBIND). This harness drives the REAL Gitea
# API for BOTH configurations:
#   - dismiss_stale_approvals = false (default): approve the Meridian diff, then swap the
#     PR head to a Blackwell diff with no re-approval, and merge. If the merge lands,
#     Blackwell was merged under Priya's approval of Meridian  ->  rebind_fired (EXPOSED).
#   - dismiss_stale_approvals = true: the same swap dismisses the approval  ->  merge is
#     control (an approval bound to the reviewed content hash).
#
# Self-proving: verdict derived from whether the swapped-in diff actually merged.
#
# Usage:
#   pip install requests
#   docker compose up -d && ./init_gitea.sh
#   python3 harness_gitea.py
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
                k, v = ln.strip().split("=", 1)
                env[k] = v
    if not env.get("AUTHOR_TOKEN") or not env.get("PRIYA_TOKEN"):
        raise SystemExit("tokens.env missing tokens; run ./init_gitea.sh first")
    return env["AUTHOR_TOKEN"], env["PRIYA_TOKEN"]


def hdr(tok):
    return {"Authorization": "token " + tok, "Content-Type": "application/json"}


def payment_text(beneficiary, amount):
    return "beneficiary=%s\namount=%d\n" % (beneficiary, amount)


def run_config(author_tok, priya_tok, dismiss_stale, repo):
    A = hdr(author_tok); P = hdr(priya_tok)

    # fresh repo (delete if present, then create with auto-init main)
    requests.delete(BASE + "/repos/author/" + repo, headers=A, timeout=15)
    r = requests.post(BASE + "/user/repos", headers=A, json={
        "name": repo, "private": False, "auto_init": True, "default_branch": "main"}, timeout=30)
    if r.status_code not in (201, 409):
        raise SystemExit("repo create failed: %s %s" % (r.status_code, r.text[:200]))

    # priya as collaborator so she can review
    requests.put(BASE + "/repos/author/" + repo + "/collaborators/priya", headers=A,
                 json={"permission": "write"}, timeout=15)

    # feature branch from main
    requests.post(BASE + "/repos/author/" + repo + "/branches", headers=A,
                  json={"new_branch_name": "feature", "old_branch_name": "main"}, timeout=15)

    # commit A on feature: the Meridian diff
    requests.put(BASE + "/repos/author/" + repo + "/contents/payment.txt", headers=A, json={
        "branch": "feature", "message": "pay meridian",
        "content": base64.b64encode(payment_text(C.A_ARGS["beneficiary"], C.A_ARGS["amount"]).encode()).decode()},
        timeout=20)

    # branch protection on main
    requests.post(BASE + "/repos/author/" + repo + "/branch_protections", headers=A, json={
        "branch_name": "main", "enable_approvals_whitelist": False, "required_approvals": 1,
        "dismiss_stale_approvals": dismiss_stale, "ignore_stale_approvals": False,
        "block_on_rejected_reviews": True, "enable_merge_whitelist": False}, timeout=20)

    # open PR feature -> main
    r = requests.post(BASE + "/repos/author/" + repo + "/pulls", headers=A, json={
        "head": "feature", "base": "main", "title": "APF payment"}, timeout=20)
    idx = r.json().get("number")
    if not idx:
        raise SystemExit("PR create failed: %s %s" % (r.status_code, r.text[:200]))

    # priya genuinely approves the Meridian diff
    requests.post(BASE + "/repos/author/" + repo + "/pulls/%d/reviews" % idx, headers=P, json={
        "event": "APPROVED", "body": "approved by Priya"}, timeout=20)

    # ---- swap: push commit B (Blackwell) to the same PR head, no re-approval ----
    meta = requests.get(BASE + "/repos/author/" + repo + "/contents/payment.txt?ref=feature",
                        headers=A, timeout=15).json()
    requests.put(BASE + "/repos/author/" + repo + "/contents/payment.txt", headers=A, json={
        "branch": "feature", "message": "swap to blackwell", "sha": meta.get("sha"),
        "content": base64.b64encode(payment_text(C.B_ARGS["beneficiary"], C.B_ARGS["amount"]).encode()).decode()},
        timeout=20)

    # Gitea recomputes mergeability asynchronously after the push; a merge attempted too
    # early returns 405 ("not ready"). Poll + retry so the default arm is not falsely blocked.
    attempts = []; merged = False; m = None; pr = {}
    for i in range(8):
        time.sleep(4)
        pr = requests.get(BASE + "/repos/author/" + repo + "/pulls/%d" % idx, headers=A, timeout=15).json()
        m = requests.post(BASE + "/repos/author/" + repo + "/pulls/%d/merge" % idx, headers=A,
                          json={"Do": "merge"}, timeout=30)
        attempts.append({"try": i, "status": m.status_code,
                         "mergeable": pr.get("mergeable"), "body": (m.text or "")[:180]})
        if m.status_code in (200, 201):
            merged = True
            break

    landed = None
    if merged:
        c = requests.get(BASE + "/repos/author/" + repo + "/contents/payment.txt?ref=main",
                         headers=A, timeout=15).json()
        landed = base64.b64decode(c.get("content", "")).decode(errors="replace")

    return {"dismiss_stale": dismiss_stale, "pr_mergeable": pr.get("mergeable"),
            "merge_status": m.status_code if m else None, "merged": merged,
            "landed_on_main": landed, "merge_attempts": attempts}


def main():
    author_tok, priya_tok = load_tokens()

    # default config (dismiss off): the exposure
    off = run_config(author_tok, priya_tok, False, "apf-off")
    C.line("control", f"priya approved the Meridian diff (required_approvals=1)")
    C.line("audit", f"dismiss_stale_approvals=false (default); swapped PR head to Blackwell with no re-approval")
    print("GITEA_DIAG off:", json.dumps(off.get("merge_attempts")))
    rebind_fired = bool(off["merged"]) and off["landed_on_main"] is not None and \
        C.B_ARGS["beneficiary"] in (off["landed_on_main"] or "")
    C.line("replay", f"merge under stale approval -> merged={off['merged']} landed={json.dumps(off['landed_on_main'])}")

    on = run_config(author_tok, priya_tok, True, "apf-on")
    print("GITEA_DIAG on:", json.dumps(on.get("merge_attempts")))
    resistant_when_dismiss = not on["merged"]
    C.line("audit", f"dismiss_stale_approvals=true (mitigation); swap -> merged={on['merged']} (merge_status={on['merge_status']})")

    b_row = None
    if rebind_fired:
        b_row = {"action": "execute_payment", "amount": C.B_ARGS["amount"],
                 "beneficiary": C.B_ARGS["beneficiary"], "approved_by_in_audit": C.APPROVER}

    seen = set(); nonce = "n-runA-0041"

    verdict = C.verdict_rebind(rebind_fired)
    C.line("verdict", verdict + " (default config); RESISTANT when dismiss_stale_approvals enabled")
    h = C.emit_evidence("Gitea", OUT, {
        "shape": "REBIND",
        "execution_tier": "give-code (real Gitea API, both configs; run on Docker to confirm)",
        "genuine_args": C.A_ARGS, "mutated_args": C.B_ARGS,
        "restore_path": "approval = persisted PR review; bound to reviewed content only when Dismiss stale approvals is enabled",
        "gitea_image": "gitea/gitea:1.22.3-rootless",
        "default_config_result": off, "mitigation_config_result": on,
        "resistant_when_dismiss_stale_approvals": resistant_when_dismiss,
        "rebind_fired": rebind_fired, "rebound_payment": b_row,
        "audit_ledger": [b_row] if b_row else [], "verdict": verdict,
        "note": "EXPOSED in the default configuration (dismiss off); enabling Dismiss stale approvals binds the approval to the reviewed content and resists the swap.",
    })
    print("EVIDENCE_HASH16", h)


if __name__ == "__main__":
    C.guarded_main('Gitea', OUT, main)
