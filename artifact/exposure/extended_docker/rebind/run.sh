#!/usr/bin/env bash
# APF / APF - REBIND "conclude" runner.
# Runs every framework that could not be executed natively in the build sandbox (Docker /
# dev-server required). ALL evidence lands in ONE root: ./evidence/<NN_framework>/evidence.json
# (+ .sha256). Every harness ALWAYS writes evidence (a verdict or INCONCLUSIVE+error).
# Usage:
#   ./run.sh                 # run all 11
#   ./run.sh kestra dapr     # run a subset by name
# Requirements: Docker (compose v2), python3, node+npm (for inngest). Full log in run.log.
set -u
cd "$(dirname "$0")"
exec > >(tee run.log) 2>&1
export APF_EVIDENCE_BASE="$(pwd)/evidence"
mkdir -p "$APF_EVIDENCE_BASE"
PY="${PYTHON:-python3}"
DC="docker compose"

ALL="kestra flowable conductor gitea atlantis temporal stepfunctions restate dapr inngest n8n"
WANT="${*:-$ALL}"
want(){ for w in $WANT; do [ "$w" = "$1" ] && return 0; done; return 1; }

echo "installing host python deps (best-effort)..."
$PY -m pip install --quiet requests temporalio boto3 restate-sdk hypercorn 2>/dev/null || \
  echo "warning: some pip installs failed; import errors (if any) will show in run.log"

# ---------- REST orchestration engines (variable/KV mutation over REST) ----------
run_rest(){  # $1=dir $2=name $3=wait_seconds [$4=init_cmd]
  echo ""; echo "########## $2 ##########"
  ( cd "$1" && $DC up -d ) || echo "$2: compose up nonzero (continuing)"
  [ -n "${4:-}" ] && ( cd "$1" && bash -c "$4" ) || true
  echo "waiting ${3}s for $2"; sleep "$3"
  ( cd "$1" && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness_rebind.py ) || echo "$2: harness exited nonzero"
  ( cd "$1" && $DC down -v ) >/dev/null 2>&1
}
want kestra    && run_rest 34_kestra    "Kestra"    25
want flowable  && run_rest 35_flowable  "Flowable"  25
want conductor && run_rest 36_conductor "Conductor" 90
want gitea     && run_rest 41_gitea     "Gitea"     15 "./init_gitea.sh"
want atlantis  && run_rest 38_atlantis  "Atlantis"  15 "./init_atlantis.sh"

# ---------- durable / managed engines ----------
if want temporal; then
  echo ""; echo "########## Temporal ##########"
  ( cd temporal && $DC up -d ) || echo "temporal: compose up nonzero (continuing)"
  echo "waiting 45s for Temporal"; sleep 45
  ( cd temporal && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness_rebind.py ) || echo "Temporal: harness nonzero"
  ( cd temporal && $DC down -v ) >/dev/null 2>&1
fi
if want stepfunctions; then
  echo ""; echo "########## AWS Step Functions ##########"
  ( cd stepfunctions && $DC up -d ) || echo "sfn: compose up nonzero (continuing)"
  sleep 12
  ( cd stepfunctions && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness_rebind.py ) || echo "Step Functions: harness nonzero"
  ( cd stepfunctions && $DC down -v ) >/dev/null 2>&1
fi
if want restate; then
  echo ""; echo "########## Restate ##########"
  ( cd restate && $DC up -d ) || echo "restate: compose up nonzero (continuing)"
  sleep 8
  ( cd restate && exec hypercorn service:app --bind 0.0.0.0:9080 ) >/tmp/apf_restate_svc.log 2>&1 & SVC=$!
  sleep 5
  curl -s -X POST http://localhost:9070/deployments -H 'content-type: application/json' \
    -d '{"uri":"http://host.docker.internal:9080","use_http_11":true,"force":true}' >/dev/null 2>&1 || true
  sleep 2
  ( cd restate && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness_rebind.py ) || echo "Restate: harness nonzero"
  kill "$SVC" 2>/dev/null || true
  ( cd restate && $DC down -v ) >/dev/null 2>&1
fi
if want dapr; then
  echo ""; echo "########## Dapr ##########"
  ( cd dapr && $DC up -d --build ) || echo "dapr: compose up nonzero (continuing)"
  echo "waiting 35s for Dapr sidecar + app"; sleep 35
  ( cd dapr && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness_rebind.py ) || echo "Dapr: harness nonzero"
  ( cd dapr && $DC down -v ) >/dev/null 2>&1
fi

# ---------- Inngest (Node dev server) + n8n (Docker) ----------
if want inngest; then
  echo ""; echo "########## Inngest ##########"
  (
    cd inngest
    npm install --silent || echo "npm install nonzero (continuing)"
    node functions.mjs & FN=$!
    sleep 3
    npx --yes inngest-cli@latest dev -u http://localhost:3000/api/inngest --no-discovery >/tmp/apf_inngest_dev.log 2>&1 & DEV=$!
    echo "waiting 12s for Inngest dev server"; sleep 12
    APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" node harness_rebind.mjs || echo "Inngest: harness nonzero"
    kill "$FN" "$DEV" 2>/dev/null || true
  )
fi
if want n8n; then
  echo ""; echo "########## n8n ##########"
  $PY -c "import requests" 2>/dev/null || $PY -m pip install --quiet requests
  ( cd n8n && $DC up -d ) || echo "n8n: compose up nonzero (continuing)"
  echo "waiting 35s for n8n"; sleep 35
  ( cd n8n && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness_rebind.py ) || echo "n8n: harness nonzero"
  ( cd n8n && $DC down -v ) >/dev/null 2>&1
fi

echo ""; echo "==================== REBIND conclude summary ===================="
./verify.sh
echo "evidence root: $APF_EVIDENCE_BASE ; full log: $(pwd)/run.log"
