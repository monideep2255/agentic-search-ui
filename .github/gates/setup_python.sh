#!/usr/bin/env bash
# Setup, not a gate: install the project and its development tools.
#
# `pip install -e .` was broken for the life of the project until build phase
# 4.14 (F-4.14-CI-01): setuptools auto-detects a `src/` layout only when
# `packages` is not set explicitly, and pyproject.toml sets it.
set -euo pipefail
python -m pip install --upgrade pip && pip install -r requirements.txt && pip install -e ".[dev]"
