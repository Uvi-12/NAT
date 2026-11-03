#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
python3 scripts/verify_ledger.py artifact/ledger
