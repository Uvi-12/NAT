"""Honest evidence recorder for in-container native APF reproductions.

Mirrors the Layer-2 native kit's Evidence contract (lib/common.py): every run
ALWAYS writes an evidence.json + .sha256, carrying a real verdict
(EXPOSED / RESISTANT) or INCONCLUSIVE with the exact reason. Nothing is faked.

These runs drive the *real shipped runtime* of each application (its own model
and read-path code, installed from pip/npm, against a real Postgres/Redis/SQLite),
performing the single documented state-only forge named in the corpus's decisive
surface. They differ from the kit only in that they boot the runtime in-process
or from source rather than from a published Docker image (image pulls are blocked
in this build sandbox), so they run where the kit's compose path cannot.
"""
from __future__ import annotations
import hashlib, json, os, sys, traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

EXPOSED = "EXPOSED"; RESISTANT = "RESISTANT"; INCONCLUSIVE = "INCONCLUSIVE"

def _now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@dataclass
class Evidence:
    app_id: str
    system: str
    expected_verdict: str
    verdict: str = INCONCLUSIVE
    tier: str = "native"
    runtime: str = ""          # how the real runtime was obtained (pip pkg + version, source commit)
    version: str = ""
    decisive_surface: str = ""
    mechanism: str = ""
    steps: list = field(default_factory=list)
    error: str = ""
    started_at: str = ""
    finished_at: str = ""

    def step(self, name, detail=""):
        self.steps.append({"t": _now(), "step": name, "detail": str(detail)[:600]})
        print(f"  [{name}] {str(detail)[:200]}", flush=True)

    def write(self, out_dir):
        self.finished_at = _now()
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, "evidence.json")
        body = json.dumps(asdict(self), indent=2)
        open(p, "w").write(body)
        open(p + ".sha256", "w").write(
            hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest() + "\n")
        print(f"VERDICT {self.app_id} {self.system}: {self.verdict} "
              f"(expected {self.expected_verdict}) -> {p}", flush=True)
        return p

class guard:
    """Context manager: any exception becomes INCONCLUSIVE + reason, never a false pass."""
    def __init__(self, ev: Evidence, out_dir: str): self.ev, self.out = ev, out_dir
    def __enter__(self): self.ev.started_at = _now(); return self.ev
    def __exit__(self, et, ev, tb):
        if et is not None:
            self.ev.verdict = INCONCLUSIVE
            self.ev.error = "".join(traceback.format_exception_only(et, ev)).strip()
            self.ev.step("inconclusive", self.ev.error)
        self.ev.write(self.out)
        return True  # swallow; the evidence file is the outcome
