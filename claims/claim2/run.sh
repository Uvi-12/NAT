#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
python3 artifact/exposure/offline/run_offline.py
