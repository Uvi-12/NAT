#!/usr/bin/env python3
"""Internal-consistency check for the unified corpus spine.

Verifies: one row per id (unique), exactly one non-empty pinned version per
system, every verdict in the allowed set, the two layers have the expected sizes,
and the mutually-exclusive outcome totals per layer are exactly as reported in
RECONCILIATION.md. Stdlib only."""
import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSVP = os.path.join(ROOT, "artifact", "corpus", "UNIFIED_CORPUS.csv")
VERDICTS = {"Exposed", "Conditional", "Transitive", "Resistant", "N/A"}
EXPECT = {
    "total": 79,
    "L1 substrate": {"n": 43, "v": {"Exposed": 26, "Conditional": 3,
                                    "Transitive": 1, "Resistant": 11, "N/A": 2}},
    "L2 deployed app": {"n": 36, "v": {"Exposed": 28, "Resistant": 8}},
}


def main():
    rows = list(csv.DictReader(open(CSVP, encoding="utf-8")))
    ok = True

    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        print("FAIL duplicate ids"); ok = False
    if len(rows) != EXPECT["total"]:
        print(f"FAIL total {len(rows)} != {EXPECT['total']}"); ok = False

    for r in rows:
        if not r["pinned_version"].strip():
            print("FAIL missing pin:", r["system"]); ok = False
        if r["verdict"] not in VERDICTS:
            print("FAIL bad verdict:", r["system"], r["verdict"]); ok = False

    # one pin per system name
    by_sys = {}
    for r in rows:
        by_sys.setdefault(r["system"], set()).add(r["pinned_version"])
    for s, pins in by_sys.items():
        if len(pins) != 1:
            print("FAIL multiple pins for", s, pins); ok = False

    for layer, exp in (("L1 substrate", EXPECT["L1 substrate"]),
                       ("L2 deployed app", EXPECT["L2 deployed app"])):
        sub = [r for r in rows if r["layer"] == layer]
        v = Counter(r["verdict"] for r in sub)
        print(f"{layer}: n={len(sub)} verdicts={dict(v)}")
        if len(sub) != exp["n"] or dict(v) != exp["v"]:
            print(f"  FAIL layer {layer} mismatch (expected n={exp['n']} {exp['v']})"); ok = False

    print("\nRESULT:", "PASS (unified corpus is internally consistent)" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
