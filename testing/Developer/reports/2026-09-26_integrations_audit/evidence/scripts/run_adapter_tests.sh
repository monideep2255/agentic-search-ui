#!/usr/bin/env bash
# Run the adapter and export test files the way CI gate 4 runs the unit suite,
# with CI's placeholder environment (every value below is a fake CI value).
# Runs from the read-only develop worktree; junit output goes to the scratchpad.
set -u
S=<scratch>
R="<repo-root>"
cd "$S/int_tree" || exit 99
export PYTHONPATH=src:.
export USER_DB_URL=postgresql://postgres:postgres@localhost:5432/search_agent_users
export REDIS_URL=redis://localhost:6379/0
export AUTH_SECRET=ci-not-a-real-secret-ci-not-a-real-secret
export PER_QUERY_COST_CAP_USD=1.00
export PER_USER_DAILY_QUERY_CAP=1000
export SYSTEM_DAILY_CAP_USD=1000000
export PER_STEP_TIMEOUT_SECONDS=30
export ANON_DAILY_RUN_CAP=1000
export GUARD_MODEL=ci/placeholder-guard
export PLAN_MODEL=ci/placeholder-plan
export SYNTH_MODEL=ci/placeholder-synth
export OPENROUTER_API_KEY=ci-placeholder-not-a-real-key
export NCBI_EMAIL=ci@example.invalid
export APP_ENV=test
export LOG_LEVEL=warning
for group in cli graphql mcp web_sse export depth; do
  case $group in
    export) path=tests/system_03_search_agent/export ;;
    depth) path=tests/system_03_search_agent/adapters/test_audience_depth_values.py ;;
    *) path=tests/system_03_search_agent/adapters/$group ;;
  esac
  echo "== $group ($path)"
  "$R/venv/bin/python" -m pytest "$path" -p no:cacheprovider -q -rs \
    --junitxml="$S/int_ev/junit_$group.xml" 2>&1 | tail -25
  echo "exit: ${PIPESTATUS[0]}"
done
