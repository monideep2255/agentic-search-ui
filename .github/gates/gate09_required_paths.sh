#!/usr/bin/env bash
# Section 24 gate 9: the required paths, never skippable.
#
# Section 24 names `test_cite_or_refuse_compliance` and
# `test_zero_retrieval_refusal`; neither exists as a function (F-4.14-02). Both
# are sections of the file below. The assertion script is what turns a pytest
# exit code, which is 0 on an empty collection, into a real verdict.
set -euo pipefail
pytest tests/system_03_search_agent/synthesis/test_required_paths.py -q --no-header -p no:cacheprovider -rs --junitxml=required-paths.xml && python .github/scripts/assert_required_paths_ran.py required-paths.xml
