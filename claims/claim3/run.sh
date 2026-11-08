#!/bin/bash
set -eu
cd "$(dirname "$0")/../.."
python3 artifact/mitigation/battery.py
