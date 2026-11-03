#!/usr/bin/env bash
# APF native reproduction, Tryton purchase-requisition approval.
# Sets up a throwaway SQLite Tryton database, activates the real
# purchase_requisition module (+ dependencies), and runs the forge demo.
#
# Requirements (pip): trytond==8.2.* and the module chain:
#   pip install trytond trytond_purchase_requisition trytond_purchase \
#               trytond_purchase_request trytond_company trytond_currency \
#               trytond_product trytond_party
set -eu
cd "$(dirname "$0")"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

cat > "$WORK/trytond.conf" <<EOF
[database]
uri = sqlite://
path = $WORK/db
EOF
mkdir -p "$WORK/db"
: > "$WORK/db/test.sqlite"
export TRYTOND_CONFIG="$WORK/trytond.conf"

echo "[setup] activating purchase_requisition (+dependencies) on a fresh SQLite db..."
printf 'admin\nadmin\n' | trytond-admin -d test -u purchase_requisition \
    --activate-dependencies --email admin@example.com >/dev/null 2>&1

echo "[run] driving the real Tryton workflow..."
exec python3 run.py
