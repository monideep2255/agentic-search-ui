#!/usr/bin/env bash
# Section 24 gate 4, the half that makes gate 4 mean something (F-4.14-03).
#
# Gate 4 passes whether a database-backed test RAN or merely SKIPPED, and those
# two outcomes are indistinguishable in its summary line. Proven necessary on
# CI run 4: gate 4 reported `4019 passed, 0 failed` while 25 tests could not
# reach the database at all.
set -euo pipefail
python .github/scripts/assert_no_db_skips.py unit-results.xml
