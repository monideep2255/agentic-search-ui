#!/usr/bin/env bash
# Setup, not a gate: install frontend dependencies from the lockfile.
set -euo pipefail
npm ci
