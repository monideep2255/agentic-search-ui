# Builder C report, phase 8.1

Branch: `worktree-agent-a8663f2264dc9e8c8` (fast-forwarded onto `0e273fa`, the phase-open commit).

Status: in progress. This file is updated the moment a finding is established.

## T-8.1-06: a phenotype question names phenotypes

Status: investigating.

## T-8.1-07: the same question returns the same papers each time

Status: investigating.

## T-8.1-08: an NCBI outage no longer turns the build red

Status: done.

Cause: `test_a6_pinned_ground_truth_still_matches_live_medgen` in
`tests/system_03_search_agent/core/test_answer_readability_premise.py`
calls `_live_medgen_title`, which calls `_get_json`, which calls
`urllib.request.urlopen` directly against live NCBI E-utilities. The test
carried no `@premise_gate` (unlike A1, A2, A3, A6bis in this file) and no
`integration` marker, so it ran unconditionally under the unit gate's
`pytest -m "not integration"` selection (`.github/gates/gate04_unit_suite.sh`),
bypassing the hermetic guard in `tests/conftest.py`. A bare NCBI HTTP
error, unrelated to the product, would turn CI red (LEARNINGS.md,
2026-09-24, named exactly this failure mode).

Fix: added `@pytest.mark.integration` to the test. The check it performs
is unchanged, only where it runs moved, to gate 5
(`.github/gates/gate05_integration.sh`, which already runs
`pytest -m integration`).

Evidence:
- `python -m pytest -m "not integration" -q --collect-only tests/system_03_search_agent/core/test_answer_readability_premise.py`
  -> 5/6 collected, 1 deselected (test_a6 deselected).
- `python -m pytest -m "integration" -q --collect-only tests/system_03_search_agent/core/test_answer_readability_premise.py`
  -> 1/6 collected (test_a6 only), 5 deselected.
- `ruff check` and `isort --check-only` pass on the changed file.

Reconciliation: none needed, no field beyond spec touched.
