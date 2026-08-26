#!/usr/bin/env bash
# Section 24 gate 3: lint.
#
# No path argument, deliberately: the whole repository with no exclusions.
# Before build phase 4.14 the habit was `ruff check src`, which passed while
# `tests/` carried 5 errors and the harness scripts carried 30.
set -euo pipefail
ruff check
