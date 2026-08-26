#!/usr/bin/env bash
# Section 24 gate 1: Python compiles and imports cleanly.
#
# `compileall` proves the files parse. It says nothing about whether importing
# them works, and a circular import or a missing module is exactly the failure
# that reaches production while every file parses perfectly (F-4.14-A-13).
set -euo pipefail
python -m compileall -q src services tests alembic && python -c "import system_03_search_agent.adapters.web_sse.app, system_03_search_agent.core.graph, system_03_search_agent.adapters.cli.main"
