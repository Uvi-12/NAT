#!/usr/bin/env bash
# Ordering note: Atlantis needs the author token at startup, but the token can only be
# created once Gitea is running. So: start Gitea, create users+token, then start Atlantis.
set -uo pipefail   # do not abort: always attempt to write tokens.env
C=apf-atl-gitea

echo "starting gitea only..."
docker compose up -d gitea

echo "waiting for gitea..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:3000/api/healthz >/dev/null; then break; fi
  sleep 2
done

docker exec "$C" gitea --config /etc/gitea/app.ini admin user create --username author --password Author12345! \
  --email author@example.com --must-change-password=false 2>/dev/null || true
docker exec "$C" gitea --config /etc/gitea/app.ini admin user create --username priya --password Priya12345! \
  --email priya@example.com --must-change-password=false 2>/dev/null || true

AUTHOR_TOKEN=$(docker exec "$C" gitea --config /etc/gitea/app.ini admin user generate-access-token \
  --username author --scopes all --raw 2>/dev/null | tail -n1)
PRIYA_TOKEN=$(docker exec "$C" gitea --config /etc/gitea/app.ini admin user generate-access-token \
  --username priya --scopes all --raw 2>/dev/null | tail -n1)

printf 'AUTHOR_TOKEN=%s\n' "$AUTHOR_TOKEN" > .env
cat > tokens.env <<EOF
AUTHOR_TOKEN=$AUTHOR_TOKEN
PRIYA_TOKEN=$PRIYA_TOKEN
EOF

echo "starting atlantis with the author token..."
docker compose up -d atlantis
echo "wrote .env and tokens.env; atlantis starting."
