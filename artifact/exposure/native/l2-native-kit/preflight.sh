#!/usr/bin/env bash
# Report host capabilities for the Layer-2 native-promotion kit (read-only).
echo "== Layer-2 kit preflight =="
command -v docker >/dev/null 2>&1 && echo "docker:  $(docker --version)" || echo "docker:  MISSING (required)"
docker compose version >/dev/null 2>&1 && echo "compose: $(docker compose version | head -1)" || echo "compose: MISSING (required)"
docker info >/dev/null 2>&1 && echo "daemon:  running" || echo "daemon:  NOT running (start Docker)"
echo "python:  $(python3 --version 2>&1)"
echo "disk:    $(df -h . | awk 'NR==2{print $4" free"}')"
echo "memory:  $(free -h 2>/dev/null | awk '/Mem:/{print $2" total"}' || echo n/a)"
echo
echo "App roster:"
ls -d apps/L2-* 2>/dev/null | sed 's#apps/#  #'
