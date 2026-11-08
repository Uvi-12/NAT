#!/usr/bin/env bash
# APF native reproduction - step-ca certificate issuance (L2-27, Resistant).
# The issuance decision is bound to the CA's signature. A state-only write that
# mints a certificate for the same identity without the CA key does not chain to
# the issuing CA and fails verification.
#
# Requires: smallstep `step` CLI on PATH (or ./step_*/bin/step).
# Install the official Smallstep `step` CLI v0.28.2 release and put it on PATH.
set -u
STEP="${STEP:-$(command -v step || ls ./step_*/bin/step 2>/dev/null | head -1)}"
cd "$(dirname "$0")"; WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT; cd "$WORK"
"$STEP" certificate create "Example Root CA" root.crt root.key --profile root-ca --no-password --insecure --force >/dev/null 2>&1
"$STEP" certificate create "Example Intermediate CA" ica.crt ica.key --profile intermediate-ca --ca root.crt --ca-key root.key --no-password --insecure --force >/dev/null 2>&1
cat ica.crt root.crt > bundle.crt
echo "== genuine issuance: the CA signs a leaf certificate =="
"$STEP" certificate create "svc.example.com" leaf.crt leaf.key --profile leaf --ca ica.crt --ca-key ica.key --no-password --insecure --force >/dev/null 2>&1
if "$STEP" certificate verify leaf.crt --roots bundle.crt >/dev/null 2>&1; then echo "  CA-issued cert -> VERIFIED"; OK=1; else echo "  CA-issued cert -> FAIL"; OK=0; fi
echo "== state-only forge: attacker mints a cert for the same identity, no CA key =="
"$STEP" certificate create "svc.example.com" forged.crt forged.key --profile self-signed --subtle --no-password --insecure --force >/dev/null 2>&1
if "$STEP" certificate verify forged.crt --roots bundle.crt >/dev/null 2>&1; then echo "  forged cert -> VERIFIED (UNEXPECTED)"; BAD=1; else echo "  forged cert -> REJECTED (not chained to the issuing CA)"; fi
echo
echo "VERDICT: Resistant (native) - issuance is bound to the CA signature; a"
echo "state-only write cannot mint a cert that verifies against the CA root."
[ "${OK:-0}" = 1 ] && [ -z "${BAD:-}" ] && { echo "RESULT: PASS"; exit 0; } || { echo "RESULT: FAIL"; exit 1; }
