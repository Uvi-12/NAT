#!/usr/bin/env python3
# Verify all LAUNDER evidence across the four batches. Run after the batches (or via run_all.sh).
import json, hashlib, os, glob
root = os.path.dirname(os.path.abspath(__file__))
rows = []; ok_all = True
for ev in sorted(glob.glob(os.path.join(root, "give-*", "evidence", "*", "evidence.json"))):
    d = os.path.basename(os.path.dirname(ev))
    blob = open(ev).read(); rec = json.loads(blob)
    shafile = ev.replace("evidence.json", "evidence.sha256")
    integ = os.path.exists(shafile) and hashlib.sha256(blob.encode()).hexdigest() == open(shafile).read().strip()
    shape_ok = (rec.get("shape") or "").upper() == "LAUNDER"
    ok = integ and shape_ok; ok_all &= ok
    rows.append((d, rec.get("verdict", "?"), integ, shape_ok, hashlib.sha256(blob.encode()).hexdigest()[:16]))
if not rows:
    print("no evidence found yet - run the batches first"); raise SystemExit(1)
print(f"{'framework':22} {'verdict':26} {'sha':4} {'shape':5} hash")
for d, v, integ, shp, h in rows:
    print(f"{d:22} {v[:26]:26} {str(integ):4} {str(shp):5} {h}")
print(f"\n{len(rows)} evidence files | ALL OK: {ok_all}")
