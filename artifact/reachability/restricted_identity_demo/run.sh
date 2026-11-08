#!/usr/bin/env bash
# Self-contained, offline, end-to-end restricted-identity APF demonstration.
# Spins up a throwaway PostgreSQL cluster, runs demo.sql, asserts the outcome,
# and tears everything down. Needs only a PostgreSQL install (initdb, pg_ctl,
# psql) and a non-root user. Nothing leaves the machine. Exit 0 on PASS.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
KEY="APPROVAL-SERVICE-HMAC-KEY"

if [ "$(id -u)" = "0" ]; then
  echo "Run as a non-root user (initdb refuses root). Try: su <user> -c '$0'"; exit 2
fi

BIN=""
for c in "$(pg_config --bindir 2>/dev/null)" /usr/lib/postgresql/*/bin /usr/pgsql-*/bin /usr/local/bin /usr/bin; do
  [ -x "$c/initdb" ] && BIN="$c" && break
done
[ -z "$BIN" ] && { echo "PostgreSQL binaries (initdb/pg_ctl/psql) not found on PATH."; exit 2; }

PGDATA="$(mktemp -d)/pgdata"; SOCK="$(mktemp -d)"; PORT=5466
cleanup(){ "$BIN/pg_ctl" -D "$PGDATA" -mimmediate stop >/dev/null 2>&1 || true; rm -rf "$PGDATA" "$SOCK"; }
trap cleanup EXIT

"$BIN/initdb" -D "$PGDATA" -A trust -U postgres >/tmp/_apf_initdb.log 2>&1 \
  || { echo "initdb failed"; cat /tmp/_apf_initdb.log; exit 2; }
"$BIN/pg_ctl" -D "$PGDATA" -o "-p $PORT -k $SOCK -c listen_addresses=''" -l /tmp/_apf_pg.log start >/dev/null 2>&1
for i in $(seq 1 20); do "$BIN/psql" -h "$SOCK" -p "$PORT" -U postgres -tAc "select 1" >/dev/null 2>&1 && break; sleep 0.5; done
"$BIN/psql" -h "$SOCK" -p "$PORT" -U postgres -tAc "CREATE DATABASE apf_demo" >/dev/null 2>&1

OUT="$("$BIN/psql" -h "$SOCK" -p "$PORT" -U postgres -d apf_demo -v key="$KEY" -f "$HERE/demo.sql" 2>&1)"
echo "$OUT"

echo
echo "================= ASSERTIONS ================="
pass=1
chk(){ if printf '%s\n' "$OUT" | grep -qF "$1"; then echo "  PASS  $2"; else echo "  FAIL  $2"; pass=0; fi; }
# negative controls: operator is denied secrets and direct execution
chk "permission denied for table secrets"          "operator cannot read application secrets"
chk "permission denied for table released_actions" "operator cannot execute the protected action directly"
# part 1: the forge releases the protected action through the vulnerable workflow
r1=$(printf '%s\n' "$OUT" | awk '/RESULT-1/{getline; print; exit}')
[ "$r1" = "1" ] && echo "  PASS  vulnerable workflow released the forged action (RESULT-1=1)" || { echo "  FAIL  RESULT-1=$r1 (expected 1)"; pass=0; }
# part 2: hardened workflow releases the genuine one and rejects the forge
r2a=$(printf '%s\n' "$OUT" | awk '/RESULT-2a/{getline; print; exit}')
r2b=$(printf '%s\n' "$OUT" | awk '/RESULT-2b/{getline; print; exit}')
[ "$r2a" = "1" ] && echo "  PASS  hardened workflow released the genuine approval (RESULT-2a=1)" || { echo "  FAIL  RESULT-2a=$r2a (expected 1)"; pass=0; }
[ "$r2b" = "0" ] && echo "  PASS  hardened workflow rejected the forge (RESULT-2b=0)" || { echo "  FAIL  RESULT-2b=$r2b (expected 0)"; pass=0; }

echo
if [ "$pass" = "1" ]; then echo "RESTRICTED-IDENTITY DEMO: PASS"; exit 0
else echo "RESTRICTED-IDENTITY DEMO: FAIL"; exit 1; fi
