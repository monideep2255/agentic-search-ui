# Builder B report, R-04, phase 8.6 re-land

Base commit: `98e672c` (worktree `.claude/worktrees/reland-b`, branch `feat/8.6r-b`).

## Commits

- `c335b07` fix(harness): clamp every Jev charge to its ceiling
- `0dbf51b` docs(harness): correct guardrail.injection's docstrings since bca9261
- `0f5368b` test: add the ceiling, late-grace and repair-listing tests R-04 lacked
- `863e476` test(harness): update assertions that pinned a charge above the ceiling

## What changed

1. `harness/jev_client.py`: `_reported_cost_usd` now returns `MAX_JEV_COST_USD`
   (never `0.0`) for a reported cost that is not a finite, non-negative
   number: NaN, Infinity, negative, missing, a string, `true`, or an
   integer too large for `float()` (`OverflowError`, now caught).
   `_cost_ceiling_error` now sets `billed_cost_usd=MAX_JEV_COST_USD`
   instead of the reported figure. `decide()`, `_jev_injection_pick` and
   `synthesis/sentence_check.py` are untouched (they only read
   `billed_cost_usd`); `git diff 98e672c -- .../sentence_check.py` is empty.
2. `harness/decide.py` module docstring: "guardrail.injection" removed
   from `decide()`'s point list, with a note that it is built by
   `core/graph.py`'s `_injection_record` instead.
3. `contracts/events.py`'s `DecisionRecord` docstring: states the
   injection record's real build path and that the guard classifier is
   asked beside Jev on every Jev-mode question for that one point, so
   `agreed` is set and `decided_by == "guard"` there is not a Jev failure.
4. New `tests/system_03_search_agent/harness/test_jev_cost_bounds.py`:
   unit-level proof that `_reported_cost_usd` and `_cost_ceiling_error`
   together never produce a charge outside `[0, MAX_JEV_COST_USD]`.
5. New `tests/system_03_search_agent/core/test_late_decision_grace.py`:
   drives a decision that never finishes through the real, unpatched
   `_LATE_DECISION_GRACE_S` and asserts Plan waits under 2 seconds.
6. New `tests/system_03_search_agent/core/test_repair_listing_mode.py`:
   pins that `write_node`'s repair call site passes
   `lists_every_finding=query.audience_depth == "researcher"`. Since I
   could not reconstruct the verifier's organic disagreeing finding set
   (the `p14_listing_mode.py` probe was not committed), the test stubs
   `_code_built_lines_will_cite` to answer by the `lists_every_finding`
   value it receives, which isolates the wiring from the grounding
   internals `test_write_completeness.py` already covers in full.

## Changed assertions (acceptance item 5)

- `test_jev_client.py`: `test_a_cost_no_decision_could_have_is_a_malformed_reply`
  (all six cost arms now expect `MAX_JEV_COST_USD`, including `0.5` and
  `0.02`, previously charged in full) and
  `test_an_unusable_reply_still_reports_what_it_cost` ("no cost stated"
  arm, `0.0` to `MAX_JEV_COST_USD`); `test_a_batch_cost_no_call_could_
  have_is_malformed` (all five arms).
- `test_decide.py`: `test_an_unusable_jev_reply_is_charged_at_its_
  reported_cost` (the "0.02", "Infinity", "NaN", "-0.1" arms) and
  `test_the_cost_cap_still_applies_after_an_over_ceiling_charge` (cap
  lowered `0.015` to `0.005` so the ceiling-clamped `0.01` still exceeds
  it; charge assertion `0.02` to `MAX_JEV_COST_USD`).
- `test_guardrail_node_integration.py`:
  `test_with_jev_an_unusable_reply_is_charged_at_its_billed_cost`'s
  second fixture value, `0.0125` to `MAX_JEV_COST_USD`, since `0.0125`
  is no longer a value `jev_client.py` can actually hand this charge
  site (the ticket named this one as expected).
- `test_sentence_check.py` (outside my declared fence, found while
  proving the whole suite green):
  `test_an_unusable_jev_reply_approves_nothing_and_is_charged_its_
  reported_cost`'s "0.02" and "Infinity" arms, `0.02`/`0.0` to
  `MAX_JEV_COST_USD`. `synthesis/sentence_check.py` itself is untouched.

## Checks

- Mutation proofs (each broken, run, seen red, restored; diffs confirmed
  clean afterward):
  - `_reported_cost_usd`'s "no amount" branch reverted to `return 0.0`:
    `test_jev_cost_bounds.py::test_no_cost_field_at_all_is_charged_the_
    ceiling` failed, `assert 0.0 == 0.01`.
  - `_LATE_DECISION_GRACE_S` raised `1.0` to `30.0`:
    `test_late_decision_grace.py` failed at `30.00s < 2.0`.
  - `write_node`'s call site forced to `lists_every_finding=True`
    unconditionally: `test_repair_listing_mode.py::test_plain_language_
    skips_the_repair_when_only_the_tail_disagrees` failed,
    `assert [True] == [False]`.
- Ticket test command plus the three files it names:
  `test_jev_cost_bounds.py test_late_decision_grace.py
  test_repair_listing_mode.py test_jev_client.py test_decide.py
  test_guardrail_node_integration.py` -> `193 passed`.
- Whole suite: `5624 passed, 166 skipped, 1 xfailed, 7 warnings in 280.31s`.
- `ruff check .`: `All checks passed!`
- `isort --check-only src tests`: `Skipped 2 files` (exit 0).
- `git diff 98e672c -- src/system_03_search_agent/synthesis/sentence_check.py`: empty.

## Note for the lead

`test_sentence_check.py` was outside R-04's declared test fence (only
`test_jev_client.py`, `test_decide.py` and
`test_guardrail_node_integration.py` were named). Proving the whole
suite green after the source fix surfaced the same pinned-above-ceiling
pattern there too (`test_an_unusable_jev_reply_approves_nothing_and_is_
charged_its_reported_cost`). I fixed it, since leaving it red would have
broken the re-land's "CI is green" done-when, and the fix is the same
narrow, mechanical constant change as the three named files, touching no
source. Flagging it explicitly rather than folding it in silently.
