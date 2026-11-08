#!/usr/bin/env bash
# Create the two actors and their API tokens for the Gitea REPLAY harness.
#   author  - opens the PR and pushes commits (state-writer role for the swap)
#   priya   - the reviewer who genuinely approves the original diff
# Writes tokens.env consumed by harness_gitea.py.
set -uo pipefail   # do not abort: always attempt to write tokens.env
C=apf-gitea

echo "waiting for gitea..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:3000/api/healthz >/dev/null; then break; fi
  sleep 2
done

# create users (ignore errors if they already exist)
docker exec "$C" gitea --config /etc/gitea/app.ini admin user create --username author --password Author12345! \
  --email author@example.com --must-change-password=false 2>/dev/null || true
docker exec "$C" gitea --config /etc/gitea/app.ini admin user create --username priya --password Priya12345! \
  --email priya@example.com --must-change-password=false 2>/dev/null || true

# generate scoped access tokens (raw)
AUTHOR_TOKEN=$(docker exec "$C" gitea --config /etc/gitea/app.ini admin user generate-access-token \
  --username author --scopes all --raw 2>/dev/null | tail -n1)
PRIYA_TOKEN=$(docker exec "$C" gitea --config /etc/gitea/app.ini admin user generate-access-token \
  --username priya --scopes all --raw 2>/dev/null | tail -n1)

cat > tokens.env <<EOF
AUTHOR_TOKEN=$AUTHOR_TOKEN
PRIYA_TOKEN=$PRIYA_TOKEN
EOF
echo "wrote tokens.env"
