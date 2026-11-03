#!/usr/bin/env bash
# give-A (orchestration REST servers): Kestra, Flowable, Conductor.
# Robust: the harness ALWAYS runs (even if compose warns) and ALWAYS writes evidence
# (a verdict, or INCONCLUSIVE with the error). Full log in run.log.
set -u
cd "$(dirname "$0")"
exec > >(tee run.log) 2>&1
export APF_EVIDENCE_BASE="$(pwd)/evidence"
mkdir -p "$APF_EVIDENCE_BASE"
PY="${PYTHON:-python3}"
$PY -c "import requests" 2>/dev/null || $PY -m pip install --quiet requests

run_fw () {
  local name="$1" dir="$2" wait_s="${3:-40}"
  echo ""; echo "########## $name ##########"
  ( cd "$dir" && docker compose up -d ) || echo "$name: compose up returned nonzero (continuing)"
  echo "$name: waiting ${wait_s}s for services (harness also polls)"
  sleep "$wait_s"
  ( cd "$dir" && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness.py ) || echo "$name: harness exited nonzero"
  ( cd "$dir" && docker compose down -v ) >/dev/null 2>&1
  echo "$name: torn down"
}

run_fw "Kestra"    kestra    60
run_fw "Flowable"  flowable  40
run_fw "Conductor" conductor 60

echo ""; echo "==== give-A evidence summary ===="
$PY - <<'PYEOF'
import json, glob, os, hashlib
base = os.environ["APF_EVIDENCE_BASE"]
rows = []
for ej in sorted(glob.glob(os.path.join(base, "*", "evidence.json"))):
    rec = json.load(open(ej)); h = hashlib.sha256(open(ej).read().encode()).hexdigest()[:16]
    rows.append((rec.get("system","?"), rec.get("verdict","?"), h, rec.get("error","")))
if not rows: print("no evidence files found; check run.log")
for s,v,h,e in rows: print(f"{s:16} {v:12} {h}  {('' if not e else '<< '+e)}")
PYEOF
echo "evidence in: $APF_EVIDENCE_BASE ; full log: $(pwd)/run.log"
