#!/usr/bin/env bash
set -uo pipefail
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
cd "$WORKSPACE"
SMOKE_OUT="$WORKSPACE/smoke-out" ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  "$WORKSPACE/.venv/bin/python" "$WORKSPACE/smoke/ui_smoke.py" 2>&1 | tee "$WORKSPACE/smoke-out/ui_smoke.txt"
exit "${PIPESTATUS[0]}"
