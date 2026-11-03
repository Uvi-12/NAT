#!/usr/bin/env bash
# APF / APF - REPLAY: run every batch, then verify all evidence.
# Each batch is independent; a failure in one does not stop the others.
set -u
cd "$(dirname "$0")"
for b in give-A_orchestration give-B_vcs_gate give-C_durable_engines give-D_node_offline; do
  echo ""; echo "==================== $b ===================="
  ( cd "$b" && ./run.sh ) || echo "$b: run.sh exited nonzero (continuing)"
done
echo ""; echo "==================== VERIFY ===================="
python3 verify.py
echo ""
echo "Done. To return results:  zip -r replay_evidence.zip give-*/evidence"
