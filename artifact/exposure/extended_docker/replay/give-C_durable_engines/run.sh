#!/usr/bin/env bash
# give-C (durable/managed engines): Temporal, Step Functions, Restate, Dapr.
# Every harness ALWAYS runs and ALWAYS writes evidence (verdict or INCONCLUSIVE+error).
# Full log in run.log.
set -u
cd "$(dirname "$0")"
exec > >(tee run.log) 2>&1
export APF_EVIDENCE_BASE="$(pwd)/evidence"
mkdir -p "$APF_EVIDENCE_BASE"
PY="${PYTHON:-python3}"
echo "installing host python deps..."
$PY -m pip install --quiet requests temporalio boto3 restate-sdk hypercorn 2>/dev/null || \
  echo "warning: some pip installs failed; harness import errors will show in run.log"

echo ""; echo "########## Temporal ##########"
( cd temporal && docker compose up -d ) || echo "temporal: compose up nonzero (continuing)"
echo "waiting 45s for Temporal (auto-setup runs schema setup)"; sleep 45
( cd temporal && $PY harness.py ) || echo "Temporal: harness exited nonzero"
( cd temporal && docker compose down -v ) >/dev/null 2>&1

echo ""; echo "########## AWS Step Functions ##########"
( cd stepfunctions && docker compose up -d ) || echo "sfn: compose up nonzero (continuing)"
sleep 12
( cd stepfunctions && $PY harness.py ) || echo "Step Functions: harness exited nonzero"
( cd stepfunctions && docker compose down -v ) >/dev/null 2>&1

echo ""; echo "########## Restate ##########"
( cd restate && docker compose up -d ) || echo "restate: compose up nonzero (continuing)"
sleep 8
echo "starting Restate python service on host :9080"
( cd restate && exec hypercorn service:app --bind 0.0.0.0:9080 ) >/tmp/apf_restate_svc.log 2>&1 &
RESTATE_SVC_PID=$!
sleep 5
# harness self-registers the deployment too; this is a best-effort first attempt
curl -s -X POST http://localhost:9070/deployments -H 'content-type: application/json' \
  -d '{"uri":"http://host.docker.internal:9080","use_http_11":true,"force":true}' >/dev/null 2>&1 || true
sleep 2
( cd restate && $PY harness.py ) || echo "Restate: harness exited nonzero"
kill "$RESTATE_SVC_PID" 2>/dev/null || true
( cd restate && docker compose down -v ) >/dev/null 2>&1

echo ""; echo "########## Dapr ##########"
( cd dapr && docker compose up -d --build ) || echo "dapr: compose up nonzero (continuing)"
echo "waiting 35s for Dapr sidecar + app"; sleep 35
( cd dapr && $PY harness.py ) || echo "Dapr: harness exited nonzero"
( cd dapr && docker compose down -v ) >/dev/null 2>&1

echo ""; echo "==== give-C evidence summary ===="
$PY - <<'PYEOF'
import json, glob, os, hashlib
base = os.environ["APF_EVIDENCE_BASE"]
rows = []
for ej in sorted(glob.glob(os.path.join(base, "*", "evidence.json"))):
    rec = json.load(open(ej)); h = hashlib.sha256(open(ej).read().encode()).hexdigest()[:16]
    rows.append((rec.get("system","?"), rec.get("verdict","?"), h, rec.get("error","")))
if not rows: print("no evidence files found; check run.log")
for s,v,h,e in rows: print(f"{s:22} {v:12} {h}  {('' if not e else '<< '+e)}")
PYEOF
echo "evidence in: $APF_EVIDENCE_BASE ; full log: $(pwd)/run.log"
