"""Shared APF replay-harness helpers (Batch 1, agentic Python).

Fixed test data is identical across every harness so evidence stays comparable
(HANDOFF section 6.4). The replay shape: obtain ONE genuine approval, persist it,
then apply that SAME approval record to a SECOND run / different target without
re-approving. Assert the gated action fires twice or on the new target. A
single-use nonce or server-owned token that blocks reuse => RESISTS.
"""
import hashlib
import json
import os

# ---- fixed test data (do not vary; keeps evidence comparable) ----
APPROVER = "Priya"
A_ARGS = {"amount": 50000, "beneficiary": "Meridian Supplies Ltd"}
B_ARGS = {"amount": 250000, "beneficiary": "Blackwell Trading LLC"}


def canon(obj) -> str:
    """Canonical JSON: sorted keys, compact, stable."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def args_hash(args: dict) -> str:
    return hashlib.sha256(canon(args).encode()).hexdigest()






def line(label: str, value) -> None:
    """Labeled evidence line (control / forge / replay / hardened / audit / verdict)."""
    print(f"{label:>10} | {value}")


def emit_evidence(system: str, outdir: str, record: dict) -> str:
    """Write canonical evidence.json + evidence.sha256. Returns the 16-char hash."""
    os.makedirs(outdir, exist_ok=True)
    record = dict(record)
    record["system"] = system
    record["shape"] = record.get("shape", "REBIND")
    record["approver"] = APPROVER
    record["a_args"] = A_ARGS
    record["b_args"] = B_ARGS
    path = os.path.join(outdir, "evidence.json")
    blob = json.dumps(record, sort_keys=True, indent=2)
    with open(path, "w") as fh:
        fh.write(blob)
    digest = hashlib.sha256(blob.encode()).hexdigest()
    with open(os.path.join(outdir, "evidence.sha256"), "w") as fh:
        fh.write(digest + "\n")
    return digest[:16]


def verdict_from_state(replay_fired, hardened_blocked=None):
    """Verdict from observed executed state: native replay/rebind fired => EXPOSED, else RESISTANT."""
    return "EXPOSED" if replay_fired else "RESISTANT"


# REBIND uses the same primitives as REPLAY (argsHash binding is what defeats it).
# rebind_fired = the gated action executed with mutated args B under run A's single approval.
def verdict_rebind(rebind_fired, hardened_blocked=None):
    return verdict_from_state(rebind_fired)


# ---- SUPPRESS ----
# SUPPRESS = the gated action executes WITHOUT a genuine approval because an in-scope actor
# suppresses the approval gate (or a denial) and leaves no approval-required record. Uses the
# suppress_fired = the action produced its effect with no genuine approval obtained.
def verdict_suppress(suppress_fired, hardened_blocked=None):
    return verdict_from_state(suppress_fired)




def guarded_main(system, outdir, mainfn):
    """Run mainfn(); on ANY exception still write INCONCLUSIVE evidence so no framework is
    ever left without an evidence file. Returns mainfn()'s value on success, else the hash."""
    import traceback
    try:
        return mainfn()
    except (Exception, SystemExit) as e:
        try:
            line("verdict", "INCONCLUSIVE")
        except Exception:
            pass
        try:
            h = emit_evidence(system, outdir, {
                "shape": "LAUNDER",
                "verdict": "INCONCLUSIVE",
                "launder_fired": False,
                "error": "{}: {}".format(type(e).__name__, e),
                "traceback": traceback.format_exc()[-1500:],
            })
            print("EVIDENCE_HASH16", h)
            return h
        except Exception as e2:
            print("EVIDENCE_EMIT_FAILED", type(e2).__name__, str(e2))

def verdict_launder(launder_fired, hardened_blocked=None):
    return verdict_from_state(launder_fired)

