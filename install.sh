#!/bin/bash
# Create a local virtual environment and install the one required dependency.
set -eu
here="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$here"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt
echo
echo "Done. Activate with:  . .venv/bin/activate"
echo "Then run all claims:  for c in claims/claim*; do bash \"\$c/run.sh\"; done"
