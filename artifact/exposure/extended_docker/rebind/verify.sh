#!/usr/bin/env bash
# Verify every evidence file under the single root: sha256 integrity + shape + verdict summary.
cd "$(dirname "$0")"
BASE="${APF_EVIDENCE_BASE:-$(pwd)/evidence}"
PY="${PYTHON:-python3}"
$PY - "$BASE" <<'PYEOF'
import json, glob, os, hashlib, sys
base = sys.argv[1]
rows = []; bad = 0
for ej in sorted(glob.glob(os.path.join(base, "*", "evidence.json"))):
    blob = open(ej, "rb").read(); rec = json.loads(blob)
    comp = hashlib.sha256(blob).hexdigest()
    shafile = ej[:-5] + ".sha256"
    sha_ok = os.path.exists(shafile) and open(shafile).read().strip() == comp
    shape_ok = rec.get("shape") == "REBIND"
    if not (sha_ok and shape_ok): bad += 1
    rows.append((rec.get("system","?"), rec.get("verdict","?"), comp[:16],
                 "ok" if sha_ok else "SHA?", "REBIND" if shape_ok else rec.get("shape","?"),
                 rec.get("error","")))
if not rows:
    print("no evidence files found under", base); sys.exit(0)
print(f"{'framework':22} {'verdict':16} {'hash16':16} {'sha':5} {'shape':7} note")
for s,v,h,sha,sh,e in rows:
    print(f"{s:22} {v:16} {h:16} {sha:5} {sh:7} {('' if not e else '<< '+e[:60])}")
exp = sum(1 for r in rows if r[1].startswith("EXPOSED"))
res = sum(1 for r in rows if r[1]=="RESISTANT")
inc = sum(1 for r in rows if r[1]=="INCONCLUSIVE")
print(f"\n{len(rows)} evidence files: {exp} EXPOSED, {res} RESISTANT, {inc} INCONCLUSIVE; integrity/shape issues: {bad}")
PYEOF
