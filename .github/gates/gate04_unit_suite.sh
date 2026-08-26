#!/usr/bin/env bash
# Section 24 gate 4: the unit test suite.
#
# No path argument: the whole suite. A path silently drops everything else.
set -euo pipefail
pytest -m "not integration" -q -rs --junitxml=unit-results.xml
