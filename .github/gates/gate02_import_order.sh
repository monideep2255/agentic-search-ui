#!/usr/bin/env bash
# Section 24 gate 2: import order.
#
# `--check-only` is load-bearing. Without it isort REWRITES the files and exits
# 0, so the gate silently formats instead of checking.
set -euo pipefail
isort --check-only --diff src tests services tracker alembic .claude .github
