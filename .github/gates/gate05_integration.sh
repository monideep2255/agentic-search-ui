#!/usr/bin/env bash
# Section 24 gate 5: the integration test suite, a network-gated job.
#
# This gate is the one place in the workflow where "passed" and "could not run"
# legitimately meet, so it is the one place they must be kept apart loudly.
#
# Two failure modes, both real, both found during build phase 4.14:
#
#   No credential at all. The suite's arms all skip and `pytest` exits 0. That
#   is reported as NOT RUN, with a `::warning` annotation so it shows on the
#   pull request's checks view rather than only in the log. A green check that
#   means "unverified" is the exact confusion this phase exists to remove.
#
#   A credential present but unreachable (F-4.14-A-03). The arms skip, pytest
#   exits 0 having passed ZERO tests, and the not-run branch is skipped because
#   a credential exists. Adding the secret would have made this gate QUIETER
#   instead of stricter, permanently. `assert_gate_ran.py` is what closes it.
#
# `RUN_PREMISE_GATE=1` is set by the workflow for this job: `tests/conftest.py`
# blocks all outbound HTTP without it, so the arms could not reach the graph
# service whether or not it was up.
set -euo pipefail

if [ -z "${GRAPH_QUERY_URL:-}" ] && [ -z "${GRAPH_PG_HOST:-}" ]; then
  {
    echo "### Gate 5: NOT RUN"
    echo ""
    echo "The integration suite reaches the read-only graph query service."
    echo "Neither \`GRAPH_QUERY_URL\` nor \`GRAPH_PG_HOST\` is available to this"
    echo "run, so every arm would skip. Reported as NOT RUN rather than passed,"
    echo "because a gate that cannot tell those apart is not a gate."
  } >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
  echo "::warning title=Gate 5 NOT RUN::The integration suite did not run: no graph credential is available to this context. It is not passing, it is unverified."
  echo "Gate 5 NOT RUN: no graph credential in this context."
  exit 0
fi

# The credential IS present, so this path must not pass quietly. `set -e` is
# suspended for the pytest call so its exit code can be inspected alongside the
# did-anything-run assertion, and BOTH are propagated below.
set +e
pytest -m integration -q -rs --junitxml=integration-results.xml
pytest_status=$?
python .github/scripts/assert_gate_ran.py integration-results.xml \
  --min-passed 1 --label "Gate 5, the integration suite"
assert_status=$?
set -e

if [ "$pytest_status" -ne 0 ]; then
  exit "$pytest_status"
fi
exit "$assert_status"
