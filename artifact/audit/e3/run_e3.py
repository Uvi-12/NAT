#!/usr/bin/env python3
"""
run_e3.py - Reproducible runner for E3 (machine-checkable audit-indistinguishability).

Usage:
    python run_e3.py              # (re)build records, then evaluate
    python run_e3.py --eval-only  # evaluate the committed records without rebuilding

Pipeline:
    1. build_records()  -> writes records/<fw>_{genuine,forged}.json and
                           records/separability_pairs.jsonl (deterministic; seed=7).
    2. load + evaluate:
         (a) JSON-Schema validation (schemas/native_approval.schema.json)
         (b) native approval policy     (Rego-equivalent logic; policies/native_approval.rego)
         (c) provenance approval policy (Rego-equivalent logic; policies/provenance_approval.rego)
         (d) field-level diff over the 7 forensic fields
         (e) indistinguishability: show the native records are byte-identical
             (so NO detector can separate them), and that the provenance field
             separates them true-by-construction
       -> writes APF-e3-results.json

HONESTY NOTE (read this before the AUC numbers). The headline result here is a
STRUCTURAL identity, not a learned classifier. Within each genuine/forged pair
every native audit field is byte-identical (the audit log is derived from the
same persisted state the forge controls), so the exact-match fraction over the
native projection is 1.0. That is the real, non-circular finding: because the
records are identical, the Bayes-optimal detector is at chance -- no feature, no
model, no amount of training separates them. The two AUC numbers are reported
only as the endpoints this identity forces: native AUC = 0.5 is the trivial
consequence of the identity, and provenance AUC = 1.0 is TRUE BY CONSTRUCTION --
the provenance policy checks a signed field that we build to be present iff
genuine and unforgeable without the key, so of course it separates perfectly. The
1.0 therefore demonstrates only that the provenance field is CHECKABLE, not that
any detector was learned. Do not read it as empirical classifier performance.

Policy note. The .rego files are the canonical, auditable policies. This runner
evaluates Rego-EQUIVALENT logic in Python (rego_native_allow / rego_provenance_allow);
it does NOT invoke an OPA engine. Cryptographic checks (HMAC / nonce / expiry) are
performed by the runner and, in a real OPA deployment, would be passed into the
policy as input booleans.

Threat-model note. A genuine record (human approved via the trusted path) and a
forged record (state-write forge) are IDENTICAL on every native field, because
the audit log is derived from the same persisted state the forge controls. They
differ only in a provenance artifact that native logging never captures. The
representative records make this concrete; the 500-pair dataset quantifies it.

TEST KEY ONLY. The HMAC key below is a published test key for reproducibility.
It models a secret that, in deployment, lives only inside the trusted approval
service. Its publication does not weaken the result: the result is that WITHOUT
provenance the records are indistinguishable (a structural identity), and WITH
provenance they are separable true-by-construction (see the honesty note above).
"""
import argparse, json, hmac, hashlib, os, random

ROOT = os.path.dirname(os.path.abspath(__file__))
RECORDS = os.path.join(ROOT, "records")
SCHEMAS = os.path.join(ROOT, "schemas")
RESULTS = os.path.join(ROOT, "APF-e3-results.json")

KEY = b"APF-E3-TEST-KEY-do-not-use-in-prod"

FORENSIC_FIELDS = ["approver", "timestamp", "action_status", "state_transition",
                   "action_arguments", "trusted_approval_path_event",
                   "state_writer_evidence"]

# Native (provenance-free) fields. Everything a validator can see.
NATIVE_FIELDS = ["run_id", "framework", "family", "action", "arguments", "decision",
                 "approver", "timestamp", "action_status", "state_transition",
                 "approval_source"]

APPROVERS = ["J. Smith (Senior Compliance Officer)", "A. Gupta (Treasury Lead)",
             "M. Okafor (Risk Officer)", "L. Chen (Finance Controller)"]

FAMILIES = [
    ("Haystack", "TCA", "human_approval_gate"),
    ("MAF",      "CRV", "checkpoint_human_gate"),
    ("AutoGen",  "SRS", "groupchat_human_approver"),
    ("Dify",     "WED", "human_input_node"),
    ("Agno",     "ALS", "approval_lifecycle"),
]


def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()


def args_hash(arguments):
    return sha256(json.dumps(arguments, sort_keys=True))


def artifact_signature(art):
    """HMAC over the binding fields of the approval artifact."""
    body = json.dumps({k: art[k] for k in
                       ["run_id", "action", "args_hash", "approver", "nonce",
                        "context_hash", "issued_at", "expiry"]}, sort_keys=True)
    return hmac.new(KEY, body.encode(), hashlib.sha256).hexdigest()


def make_record(framework, family, source, run_id, approver, arguments, ts,
                *, genuine):
    """Build a full ground-truth record. Native fields are identical for genuine
    and forged; only the provenance artifact + state_writer differ."""
    native = {
        "run_id": run_id, "framework": framework, "family": family,
        "action": "wire_transfer", "arguments": arguments,
        "decision": "approved", "approver": approver, "timestamp": ts,
        "action_status": "succeeded",
        "state_transition": "paused->approved->executed",
        "approval_source": source,
    }
    rec = dict(native)
    if genuine:
        art = {
            "run_id": run_id, "action": "wire_transfer",
            "args_hash": args_hash(arguments), "approver": approver,
            "nonce": sha256(run_id + "nonce")[:16],
            "context_hash": sha256(run_id + "ctx")[:32],
            "issued_at": ts, "expiry": ts.replace("T14", "T15"),
        }
        art["signature"] = artifact_signature(art)
        rec["approval_artifact"] = art
        rec["state_writer"] = "approval-service"
        rec["trusted_approval_path_event"] = f"approval-svc:{run_id}"
    else:
        # Attacker has no key: no valid artifact, no trusted-path event.
        rec["approval_artifact"] = None
        rec["state_writer"] = "logging-sidecar"   # only knowable WITH provenance
        rec["trusted_approval_path_event"] = None
    return rec


def build_records():
    os.makedirs(RECORDS, exist_ok=True)
    # representative records (one genuine + one forged per family)
    for fw, fam, src in FAMILIES:
        run_id = f"run-{fw.lower()}-001"
        args = {"amount": 100000, "recipient": "ACME-CORP-TW"}
        ts = "2026-06-26T14:32:01Z"
        for kind in ("genuine", "forged"):
            rec = make_record(fw, fam, src, run_id, APPROVERS[0], args, ts,
                              genuine=(kind == "genuine"))
            with open(os.path.join(RECORDS, f"{fw.lower()}_{kind}.json"), "w") as fh:
                json.dump(rec, fh, indent=2)
    # separability dataset: 500 genuine/forged pairs.
    # We vary SCENARIO fields across pairs (run id, timestamp, approver label,
    # amount) while keeping the native audit evidence IDENTICAL within each
    # genuine/forged pair. This tests whether native audit evidence contains any
    # distinguishing signal between genuine and forged approvals.
    random.seed(7)
    path = os.path.join(RECORDS, "separability_pairs.jsonl")
    with open(path, "w") as fh:
        for i in range(500):
            approver = random.choice(APPROVERS)
            amount = random.choice([100000, 50000, 250000, 999000])
            ts = f"2026-06-26T{random.randint(9,17):02d}:{random.randint(0,59):02d}:00Z"
            args = {"amount": amount, "recipient": "ACME-CORP-TW"}
            for kind in ("genuine", "forged"):
                rec = make_record("MAF", "CRV", "checkpoint_human_gate",
                                  f"run-sep-{i}", approver, args, ts,
                                  genuine=(kind == "genuine"))
                fh.write(json.dumps({"label": kind, "record": rec}) + "\n")
    print(f"[build] wrote {len(FAMILIES)*2} representative records + "
          f"500 pairs -> {RECORDS}/")


# ---------- evidence views ----------
def native_view(rec):
    return {k: rec[k] for k in NATIVE_FIELDS}


def forensic_vector(rec, *, with_provenance):
    return {
        "approver": rec["approver"],
        "timestamp": rec["timestamp"],
        "action_status": rec["action_status"],
        "state_transition": rec["state_transition"],
        "action_arguments": json.dumps(rec["arguments"], sort_keys=True),
        "trusted_approval_path_event":
            rec.get("trusted_approval_path_event") if with_provenance else None,
        "state_writer_evidence": rec.get("state_writer") if with_provenance else None,
    }


def field_diff(a, b):
    return [f for f in FORENSIC_FIELDS if a[f] != b[f]]


# ---------- validators ----------
def load_native_validator():
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        # jsonschema is optional. The native approval schema is permissive by
        # design (it carries no origin signal), so without the library we model
        # its documented behaviour: it accepts the record. The separability
        # result (AUC) does not depend on this check.
        class _Accept:
            def is_valid(self, _rec):
                return True
        return _Accept()
    with open(os.path.join(SCHEMAS, "native_approval.schema.json")) as fh:
        schema = json.load(fh)
    return Draft202012Validator(schema)


def verify_artifact(rec):
    """Out-of-band verification the runner performs before OPA evaluation.
    Returns the booleans the provenance Rego consumes."""
    art = rec.get("approval_artifact")
    if not art:
        return {"present": False, "signature_valid": False, "nonce_valid": False,
                "not_expired": False, "args_hash": args_hash(rec["arguments"])}
    expected = artifact_signature({k: art[k] for k in
                                   ["run_id", "action", "args_hash", "approver",
                                    "nonce", "context_hash", "issued_at", "expiry"]})
    sig_ok = hmac.compare_digest(art.get("signature", ""), expected)
    return {
        "present": True,
        "signature_valid": sig_ok,
        "nonce_valid": bool(art.get("nonce")),
        "not_expired": rec["timestamp"] <= art.get("expiry", ""),
        "args_hash": args_hash(rec["arguments"]),
    }


def rego_native_allow(native):
    """Rego-equivalent logic mirroring policies/native_approval.rego (not OPA-executed)."""
    return (native.get("decision") == "approved"
            and native.get("approver", "") != ""
            and native.get("timestamp", "") != ""
            and native.get("action_status") == "succeeded")


def rego_provenance_allow(rec):
    """Rego-equivalent logic mirroring policies/provenance_approval.rego (not OPA-executed).
    input = record + out-of-band verified booleans."""
    v = verify_artifact(rec)
    art = rec.get("approval_artifact")
    if not art:
        return False
    return (v["signature_valid"] and v["nonce_valid"] and v["not_expired"]
            and art["run_id"] == rec["run_id"]
            and art["args_hash"] == v["args_hash"]
            and art["approver"] == rec["approver"]
            and rec.get("trusted_approval_path_event") is not None)  # trusted-path event present


def siem_alerts(native):
    fired = []
    if not native.get("approver") or not native.get("timestamp"):
        fired.append("R1_missing_approver_or_timestamp")
    # R2/R3 require a state_writer field / trusted-path event that native logs do
    # not emit, so they have no input to fire on.
    if "state_writer" in native and native["state_writer"] not in (None, native.get("approver")):
        fired.append("R2_writer_approver_mismatch")
    return fired


# ---------- separability ----------
def auc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return float("nan")
    wins = ties = 0
    for p in pos:
        for n in neg:
            wins += (p > n)
            ties += (p == n)
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


def evaluate():
    nv = load_native_validator()

    # (1) field diff + (2) validators on the representative records
    fam_results = {}
    agg_native = set()
    for fw, fam, _ in FAMILIES:
        g = json.load(open(os.path.join(RECORDS, f"{fw.lower()}_genuine.json")))
        f = json.load(open(os.path.join(RECORDS, f"{fw.lower()}_forged.json")))
        d_native = field_diff(forensic_vector(g, with_provenance=False),
                              forensic_vector(f, with_provenance=False))
        d_prov = field_diff(forensic_vector(g, with_provenance=True),
                            forensic_vector(f, with_provenance=True))
        agg_native |= set(d_native)
        nv_f = native_view(f)
        fam_results[f"{fam}/{fw}"] = {
            "native_distinguishing": d_native,
            "with_provenance_distinguishing": d_prov,
            "json_schema_native": "accept" if nv.is_valid(nv_f) else "reject",
            "siem_alerts": siem_alerts(nv_f),
            "rego_native": "allow" if rego_native_allow(nv_f) else "deny",
            "rego_provenance": "allow" if rego_provenance_allow(f) else "deny",
        }
        # sanity: genuine must pass provenance policy
        assert rego_provenance_allow(g), f"genuine {fw} failed provenance policy"

    # (3) separability over the committed 500-pair dataset
    recs, labels = [], []
    for line in open(os.path.join(RECORDS, "separability_pairs.jsonl")):
        obj = json.loads(line)
        recs.append(obj["record"])
        labels.append(1 if obj["label"] == "genuine" else 0)
    native_scores = [r["arguments"]["amount"] for r in recs]  # best native feature
    def nkey(r):
        v = native_view(r)
        return json.dumps({k: v[k] for k in NATIVE_FIELDS if k != "run_id"}, sort_keys=True)
    genuine_keys = {nkey(r) for r, l in zip(recs, labels) if l == 1}
    forged_keys = [nkey(r) for r, l in zip(recs, labels) if l == 0]
    exact_match = sum(k in genuine_keys for k in forged_keys) / len(forged_keys)
    prov_scores = [1 if rego_provenance_allow(r) else 0 for r in recs]
    separability = {
        "n_pairs": 500,
        "generation": ("500 genuine/forged pairs generated by varying scenario fields "
                       "across pairs (run_id, timestamp, approver label, amount) while keeping "
                       "the native audit evidence identical within each genuine/forged pair; "
                       "this tests whether native audit evidence contains any distinguishing "
                       "signal between genuine and forged approvals"),
        # PRIMARY (non-circular) result: the native records are byte-identical,
        # so no detector of any kind can separate them.
        "native_records_byte_identical_frac": round(exact_match, 3),
        "primary_finding": ("native audit records are byte-identical between genuine and "
                            "forged within every pair; the Bayes-optimal detector is therefore "
                            "at chance -- this is a structural identity, not a classifier result"),
        # Derived endpoints the identity forces (NOT learned classifier scores):
        "native_auc": round(auc(native_scores, labels), 3),
        "native_auc_note": "0.5 is the trivial consequence of the byte-identity above",
        "provenance_auc": round(auc(prov_scores, labels), 3),
        "provenance_auc_note": ("1.0 is TRUE BY CONSTRUCTION: the provenance policy checks a "
                                "signed field built to be present iff genuine; it shows the "
                                "field is checkable, not that a detector was learned"),
        "interpretation": "true_by_construction",
    }

    results = {
        "experiment": "E3 machine-checkable audit-indistinguishability",
        "families": fam_results,
        "aggregate_native_distinguishing_fields": sorted(agg_native),
        "separability": separability,
        "artifacts": {
            "native_schema": "schemas/native_approval.schema.json",
            "provenance_schema": "schemas/provenance_approval.schema.json",
            "native_policy": "policies/native_approval.rego",
            "provenance_policy": "policies/provenance_approval.rego",
            "records": "records/",
        },
    }
    with open(RESULTS, "w") as fh:
        json.dump(results, fh, indent=2)

    # console summary
    print("\n(1) FIELD DIFF  (native | with-provenance)")
    for k, v in fam_results.items():
        print(f"   {k:<14} native: {v['native_distinguishing'] or '[] identical'}"
              f"   prov: {v['with_provenance_distinguishing']}")
    print(f"   aggregate native distinguishing fields: "
          f"{sorted(agg_native) or '[] -> INDISTINGUISHABLE'}")
    print("\n(2) VALIDATOR ACCEPTANCE of forged record")
    for k, v in fam_results.items():
        print(f"   {k:<14} schema:{v['json_schema_native']:<7} "
              f"siem:{(','.join(v['siem_alerts']) or 'none'):<10} "
              f"rego_native:{v['rego_native']:<6} rego_prov:{v['rego_provenance']}")
    s = separability
    print("\n(3) INDISTINGUISHABILITY  (structural, not a learned classifier)")
    print(f"   PRIMARY: native records byte-identical in {s['native_records_byte_identical_frac']*100:.0f}% "
          f"of {s['n_pairs']} pairs -> no detector can separate them")
    print(f"   endpoints forced by that identity:")
    print(f"     native_auc={s['native_auc']}  (trivial consequence of the identity)")
    print(f"     provenance_auc={s['provenance_auc']}  (TRUE BY CONSTRUCTION: a signed field "
          f"present iff genuine; shows it is checkable, not learned)")
    print(f"\n[wrote {os.path.relpath(RESULTS, ROOT)}]")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-only", action="store_true",
                    help="evaluate committed records without rebuilding")
    args = ap.parse_args()
    if not args.eval_only:
        build_records()
    evaluate()
