#!/usr/bin/env bash
# Setup, not a gate: everything gate 10 needs, Python and Node and a browser.
set -euo pipefail
python -m pip install --upgrade pip && pip install -r requirements.txt && pip install -e ".[dev]" && npm ci --prefix frontend && npx --prefix frontend playwright install --with-deps chromium
