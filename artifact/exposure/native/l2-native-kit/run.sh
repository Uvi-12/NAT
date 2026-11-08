#!/usr/bin/env bash
# Layer-2 native-promotion kit, one command to set everything up and run it.
#
#   ./run.sh                 # create venv, install deps, run ALL apps (resumable)
#   ./run.sh --only L2-15    # run a single app
#   ./run.sh --list          # list apps and their status
#   ./run.sh --force         # re-run everything, ignoring saved progress
#
# It creates a .venv, installs requirements, and runs the resumable orchestrator.
# Re-running continues where it left off: apps with a real verdict are skipped,
# inconclusive ones are retried. Requires Docker (with compose v2) on PATH.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  echo "[setup] creating virtual environment (.venv)..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

echo "[setup] installing requirements..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

echo "[preflight] checking Docker..."
if ! docker version >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "  Docker (with the compose v2 plugin) is required and was not found on PATH."
  echo "  Install Docker Engine/Desktop + compose, start the daemon, then re-run ./run.sh"
  exit 2
fi
echo "  Docker OK: $(docker --version)"

echo "[run] starting orchestrator..."
exec python orchestrate.py "$@"
