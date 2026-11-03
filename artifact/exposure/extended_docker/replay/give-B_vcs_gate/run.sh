#!/usr/bin/env bash
# give-B (VCS approval gate): Gitea, Atlantis. Init scripts run but never block the harness;
# if a token is missing the harness now emits INCONCLUSIVE with the reason. Log in run.log.
set -u
cd "$(dirname "$0")"
exec > >(tee run.log) 2>&1
export APF_EVIDENCE_BASE="$(pwd)/evidence"
mkdir -p "$APF_EVIDENCE_BASE"
PY="${PYTHON:-python3}"
$PY -c "import requests" 2>/dev/null || $PY -m pip install --quiet requests

echo ""; echo "########## Gitea ##########"
( cd gitea && docker compose up -d ) || echo "Gitea: compose up nonzero (continuing)"
echo "Gitea: waiting 30s before init"; sleep 30
( cd gitea && ./init_gitea.sh ) || echo "Gitea: init_gitea.sh returned nonzero (continuing)"
( cd gitea && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness.py ) || echo "Gitea: harness exited nonzero"
( cd gitea && docker compose down -v ) >/dev/null 2>&1; echo "Gitea: torn down"

echo ""; echo "########## Atlantis (+Gitea) ##########"
( cd atlantis && docker compose up -d gitea ) || echo "Atlantis: gitea up nonzero (continuing)"
echo "Atlantis: waiting 30s before init"; sleep 30
( cd atlantis && ./init_atlantis.sh ) || echo "Atlantis: init_atlantis.sh returned nonzero (continuing)"
( cd atlantis && APF_EVIDENCE_BASE="$APF_EVIDENCE_BASE" $PY harness.py ) || echo "Atlantis: harness exited nonzero"
( cd atlantis && docker compose down -v ) >/dev/null 2>&1; echo "Atlantis: torn down"

echo ""; echo "==== give-B evidence summary ===="
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
