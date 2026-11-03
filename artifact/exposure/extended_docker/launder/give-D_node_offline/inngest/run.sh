#!/usr/bin/env bash
# Inngest LAUNDER live: start the served function + inngest dev server, then run the harness.
set -e
npm install
node functions.mjs & FUNC=$!
sleep 3
npx inngest-cli@latest dev -u http://localhost:3000/api/inngest --no-discovery & DEV=$!
sleep 5
APF_EVIDENCE_BASE="${APF_EVIDENCE_BASE:-../evidence}" node harness_launder.mjs
kill $FUNC $DEV 2>/dev/null || true
