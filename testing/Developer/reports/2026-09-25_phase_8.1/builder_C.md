# Builder C report, phase 8.1

Branch: `worktree-agent-a8663f2264dc9e8c8` (fast-forwarded onto `0e273fa`, the phase-open commit).

Status: in progress. This file is updated the moment a finding is established.

## T-8.1-06: a phenotype question names phenotypes

Status: investigating.

## T-8.1-07: the same question returns the same papers each time

Status: done.

Investigation: `core/breadth_plan.py`'s `build_pubmed_term`/`disease_search_text`
are pure functions of an already-resolved disease title, and PubMed's ESearch
already defaults to `sort=relevance` (fixed 2026-09-20, `70a6c4e`), so the
term itself is stable given a stable resolved entity. Three live probes
against real NCBI E-utilities (immediate repeat, ~72s apart, and
unauthenticated) all showed the exact term
`"gastroesophageal reflux"[Title/Abstract]` returning the identical top-5
idlist every time today, so the ESearch backend is not currently
nondeterministic for this term. The real gap is architectural rather than
a live NCBI flake: the search call's own `retmax` WAS `PUBMED_RESULT_CAP`
(5), so `plan_literature_follow_up`'s deterministic reselection
(`select_ids`, highest PMID first, already order-independent) had nothing
to re-sort. It received at most five raw ids, exactly whichever five
NCBI's relevance ranking happened to place in that window on a given call,
and could only reorder that same five. The module's own docstring already
states the design intent ("the planner never re-sorts by relevance"), but
the code never gave that reselection a wider pool to work from, so a
narrow, transient shift in NCBI's own top-5-by-relevance boundary (the kind
the 2026-09-23 measurement caught, and the kind this module's own comments
already name as a known ESearch property) passed straight through to the
final citation set with nothing to absorb it.

Cause named: no hardcoded decision or model call is involved (ruled out:
entity resolution is not what varies for the bare `GERD` question, since it
resolves to the fixed CURIE `MedGen:C5563728` and the same normalised
title every time); the instability is in the zero-buffer gap between the
ESearch call's `retmax` and the follow-up's own final cap.

Fix: added `PUBMED_SEARCH_OVERFETCH` (30) in `core/breadth_plan.py`, used
as the ESearch `retmax` for the `pubmed_search` purpose in
`plan_first_stage` and `plan_topic_search`, while `PUBMED_RESULT_CAP` (5)
stays the final cap `plan_literature_follow_up`'s `select_ids` applies. A
wider candidate pool, deterministically narrowed by a fixed rule (highest
PMID), is far less sensitive to a narrow ranking shift at the old
five-result cutoff. `core/graph.py`'s own displayed summary for the search
step reads ESearch's `total_available` (the true hit count), never
`retmax`, so this is invisible to the reader except in which five papers
are consistently cited (verified by reading `_search()` in
`tools/ncbi_eutils_actions.py` and the summary line in `core/graph.py`,
both out of my fence, read-only).

Evidence:
- Live direct-probe scripts (kept in scratchpad, not committed):
  6 identical ESearch calls to real NCBI, sub-second apart, keyed:
  1 distinct set. 6 more, ~72s apart, keyed, retmax=5 and retmax=50 both:
  1 distinct set each. 6 more, unauthenticated, 1.1s apart: 1 distinct set.
  All confirm today's live ESearch is deterministic for this term; the
  architectural gap is the defect this fix closes regardless.
- Full local pipeline, BEFORE the fix, question "What causes GERD?" at
  `plain_language` depth, 6 runs: 1 distinct PubMed citation set already
  (the acceptance criterion technically already held on this exact
  question at this exact moment; the gap is real but not currently
  manifesting on this term).
- Full local pipeline, AFTER the fix, same question, 6 runs: 1 distinct
  PubMed citation set, all 6 outcome=answer. The selected set changed
  (from the old top-5-by-relevance derived set to the highest-PMID-of-30
  set), which is expected: the final five are now chosen by the module's
  own documented rule from a real pool instead of degenerating to "the
  only five ids the search call ever saw."
- `python -m pytest tests/system_03_search_agent/core/test_breadth_plan.py
  tests/system_03_search_agent/core/test_topic_search.py -q`: 109 passed
  (two existing assertions updated to reflect the new retmax split, plus
  one new test, `test_pubmed_search_overfetches_a_candidate_pool_wider_than_the_final_cap`,
  that pins the T-8.1-07 finding).
- `tests/system_03_search_agent/core/test_disease_breadth.py` (core/graph.py's
  test surface, out of my fence, read-only check): 33 passed, unaffected.
- `ruff check` and `isort --check-only` pass on all changed files.

No hardcoded decision: the overfetch buffer is a numeric robustness
constant, not a routing or classification choice: it changes how wide a
pool a fixed, already-existing rule (highest PMID) chooses from, never
which path a question takes.

Out of scope, not fixed here, and not required by this ticket's acceptance:
`reflux disease` resolving to zero results on one run in six
("Notes carried over from the old tracker", `testing/UI_fixes_done.md`)
is a routing/classifier sampling question (which entity-resolution or
clarify path a run takes), not a PubMed-search-determinism question, and
it lives upstream in `core/graph.py`/`core/clarify.py`, out of this
builder's fence.

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
