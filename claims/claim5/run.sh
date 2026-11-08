#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
cd artifact/audit/e3 && python3 run_e3.py
