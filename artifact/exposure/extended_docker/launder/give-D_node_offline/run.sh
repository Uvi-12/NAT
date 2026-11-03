#!/usr/bin/env bash
# give-D (Node + offline): BeeAI (offline), Inngest (dev server), n8n (Docker).
# Every harness ALWAYS writes evidence (verdict or INCONCLUSIVE+error). Log in run.log.
set -u
cd "$(dirname "$0")"
exec > >(tee run.log) 2>&1
export APF_EVIDENCE_BASE="$(pwd)/evidence"
mkdir -p "$APF_EVIDENCE_BASE"
PY="${PYTHON:-python3}"

echo ""; echo "########## BeeAI (offline) ##########"
$PY -c "import beeai_framework" 2>/dev/null || $PY -m pip install --quiet beeai-framework
( cd beeai && $PY harness.py ) || echo "BeeAI: harness exited nonzero"

echo ""; echo "########## Inngest (dev server) ##########"
(
  cd inngest
  npm install --silent || echo "npm install nonzero (continuing)"
  node functions.mjs & FN_PID=$!
  sleep 3
  npx --yes inngest-cli@latest dev -u http://localhost:3000/api/inngest --no-discovery >/tmp/apf_inngest_dev.log 2>&1 & DEV_PID=$!
  echo "waiting 12s for Inngest dev server to sync"; sleep 12
  node harness.mjs || echo "Inngest: harness exited nonzero"
  kill "$FN_PID" "$DEV_PID" 2>/dev/null || true
)

echo ""; echo "########## n8n (Docker) ##########"
$PY -c "import requests" 2>/dev/null || $PY -m pip install --quiet requests
( cd n8n && docker compose up -d ) || echo "n8n: compose up nonzero (continuing)"
echo "waiting 75s for n8n"; sleep 75
( cd n8n && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness.py ) || echo "n8n: harness exited nonzero"
( cd n8n && docker compose down -v ) >/dev/null 2>&1

echo ""; echo "==== give-D evidence summary ===="
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
