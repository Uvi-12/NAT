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
    record["shape"] = "replay"
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


def guarded_main(system, outdir, main_fn, diag_getter=None):
    """Always writes an evidence file. On any exception (or nonzero SystemExit), emits
    INCONCLUSIVE with the error and traceback so a failed setup step yields a reason,
    never silence."""
    import traceback

    def _emit_incon(err):
        rec = {
            "execution_tier": "live (failed before verdict)",
            "verdict": "INCONCLUSIVE",
            "error": err,
            "traceback_tail": traceback.format_exc().splitlines()[-15:],
            "replay_fired": False,
            "audit_ledger": [],
        }
        if diag_getter is not None:
            try:
                rec["diagnostics"] = diag_getter()
            except Exception:
                pass
        try:
            h = emit_evidence(system, outdir, rec)
            print("EVIDENCE_HASH16", h)
            print("GUARD: wrote INCONCLUSIVE evidence after error:", err)
        except Exception as e2:
            print("GUARD: failed to write evidence:", e2)

    try:
        main_fn()
    except SystemExit as e:
        if e.code in (0, None):
            return
        _emit_incon("SystemExit: %s" % e.code)
    except Exception as e:
        _emit_incon("%s: %s" % (type(e).__name__, e))
