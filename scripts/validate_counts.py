#!/usr/bin/env python3
"""Validate the frozen corpus: row count, mutually-exclusive outcome totals, and
that every system has a matching evidence record under the stated tier folder.
Stdlib only."""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, "artifact", "corpus", "corpus.csv")
EVID = os.path.join(ROOT, "artifact", "evidence")
EXPECT = {"Direct exposed": 26, "Conditional exposed": 3,
          "Transitive exposed": 1, "Resistant": 11, "N/A": 2}
TIER_DIR = {"N1": "native-runtime", "N2": "contract-verified",
            "V": "vendor-confirmed", "Scope": "non-applicable"}


def main():
    rows = list(csv.DictReader(open(CORPUS, encoding="utf-8")))
    got = {k: sum(r["verdict"] == k for r in rows) for k in EXPECT}
    print("corpus rows:", len(rows))
    print("outcome totals:", got)
    ok = (len(rows) == 43 and got == EXPECT)
    missing = 0
    for r in rows:
        folder = TIER_DIR.get(r["evidence_class"], "resistant-controls")
        slug = "".join(c.lower() if c.isalnum() else "_" for c in r["system"]).strip("_")
        p = os.path.join(EVID, folder, r["id"] + "_" + slug + ".json")
        if not os.path.exists(p):
            missing += 1
            continue
        x = json.load(open(p))
        if x.get("system") != r["system"] or x.get("verdict") != r["verdict"]:
            missing += 1
    print("evidence records matched:", len(rows) - missing, "/", len(rows))
    ok = ok and missing == 0
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
