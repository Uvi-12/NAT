#!/usr/bin/env bash
# APF native reproduction - Sigstore signature verification (via cosign).
# Covers the resistant rows whose decision is bound to a Sigstore signature the
# state-writer cannot produce: Sigstore Fulcio (L2-26) and Sigstore
# policy-controller (L2-35). Uses the real cosign client in key-based (offline)
# mode. The genuine approval/attestation is signed by the approval authority's
# key; a state-only edit of the persisted record, or an attacker self-signing
# without that key, fails verification.
#
# Requires: cosign v2.x on PATH (or ./bin/cosign).
# Install the official Sigstore `cosign` v2.4.1 release and put it on PATH.
set -u
COSIGN="${COSIGN:-$(command -v cosign || echo ./bin/cosign)}"
export COSIGN_PASSWORD=""
cd "$(dirname "$0")"; WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT; cd "$WORK"
"$COSIGN" generate-key-pair >/dev/null 2>&1
AUTH_OK=1
echo '{"decision":"approved","action":"promote-release","artifact":"payments-svc@sha256:abcd","approver":"A. Reviewer"}' > approval.json
echo '{"decision":"approved","action":"promote-release","artifact":"evil-svc@sha256:dead","approver":"A. Reviewer"}'    > forged.json
"$COSIGN" sign-blob --key cosign.key --tlog-upload=false --yes approval.json > approval.sig 2>/dev/null
echo "== control: genuine approval signed by the approval authority =="
if "$COSIGN" verify-blob --key cosign.pub --signature approval.sig --insecure-ignore-tlog=true approval.json >/dev/null 2>&1; then echo "  genuine approval -> VERIFIED"; else echo "  genuine approval -> FAIL (env?)"; AUTH_OK=0; fi
echo "== state-only forge 1: reuse the genuine signature over an edited record =="
if "$COSIGN" verify-blob --key cosign.pub --signature approval.sig --insecure-ignore-tlog=true forged.json >/dev/null 2>&1; then echo "  forged record -> VERIFIED (UNEXPECTED)"; BAD=1; else echo "  forged record -> REJECTED (signature does not cover it)"; fi
echo "== state-only forge 2: attacker self-signs the forged record (no authority key) =="
COSIGN_PASSWORD="x" "$COSIGN" generate-key-pair --output-key-prefix attacker >/dev/null 2>&1
COSIGN_PASSWORD="x" "$COSIGN" sign-blob --key attacker.key --tlog-upload=false --yes forged.json > forged.sig 2>/dev/null
if "$COSIGN" verify-blob --key cosign.pub --signature forged.sig --insecure-ignore-tlog=true forged.json >/dev/null 2>&1; then echo "  attacker signature -> VERIFIED (UNEXPECTED)"; BAD=1; else echo "  attacker signature -> REJECTED (attacker key != approval authority)"; fi
echo
echo "VERDICT: Resistant (native) - the decision is bound to a Sigstore signature"
echo "the state-writer cannot produce; a state-only write cannot forge it."
[ "${AUTH_OK}" = 1 ] && [ -z "${BAD:-}" ] && { echo "RESULT: PASS"; exit 0; } || { echo "RESULT: FAIL"; exit 1; }
