#!/usr/bin/env bash
set -euo pipefail
WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
cd "$WORKSPACE"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q "playwright==${PLAYWRIGHT_VERSION}"
.venv/bin/python -m playwright install --with-deps chromium
echo "playwright_version=$(.venv/bin/playwright --version 2>&1 | head -1)" >> "$WORKSPACE/smoke-out/manifest.env"
echo "python_version=$(python3 --version 2>&1)" >> "$WORKSPACE/smoke-out/manifest.env"
