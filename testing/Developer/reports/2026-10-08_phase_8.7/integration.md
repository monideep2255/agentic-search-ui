# Integration fixer, phase 8.7

The integration fixer's running record for build phase 8.7: the 14 unit tests that went red once steps 1 to 7 turned the early send on (the record listing reaches the screen before the summary, through `TokenPayload.placement`), and what each one turned out to be.

## Table of contents

- [Base](#base)
- [How each failure was judged](#how-each-failure-was-judged)
- [Per failure](#per-failure)
- [Real defects found](#real-defects-found)
- [Pass counts](#pass-counts)
- [Left for the lead](#left-for-the-lead)

## Base

- Worktree branch `feat/8.7-int`, cut from `phase/8.7-answers-sooner` at ae1b0befb4f80bdd4d03322b42b7e7dad720d826.
- 14 failed, 78 passed across the seven failing files before any change (`pytest -m "not integration"` over those files).

## How each failure was judged

Three kinds, per the lead's brief:

| Kind | Meaning | What changes |
|---|---|---|
| Stale premise | The test assumed nothing of the answer exists before the summary, which the early send intends to change | The test is reshaped to its real subject; its assertion is kept, and an arm pins the new behaviour |
| Reading order | The test read the answer in arrival order, where the listing now arrives first | The order assertion is made on the reading order of `contracts/token_order.py` (summary above listing), as every surface reads it; arrival order keeps its own assertion where the test is about the stream |
| Real defect | The phase's code does something wrong | The smallest fix, with a test that fails on the old code |

## Per failure

### `test_check_every_rewording.py`, the two repair arms

- Kind: stale premise.
- Cause: the fake writer picked the repair by `COMPLETENESS CORRECTION` alone. Option B (card 50) now starts the second draft beside the first, carrying `COMPLETENESS REQUIREMENT`, whenever both drafts fit the cost cap (the arms set the cap to $1.00). The fake answered that second draft as a first draft, so the rewording never reached the check.
- Change: line 264 now reads `if any(marker in joined for marker in completeness._SECOND_DRAFT_MARKERS):`, builder W's line, the same test `test_write_completeness.py` already uses. Checked before use: `_SECOND_DRAFT_MARKERS` is `(_CORRECTION_MARKER, _REQUIREMENT_MARKER)` in that module, and the marker test runs before the `SYNTH_SYSTEM_INSTRUCTION` test, which both drafts carry.
- Evidence: 12 passed. Mutation, grounding the second draft's reply with a plain `run_grounding_pass` in place of `_ground_with_sentence_check` in `core/graph.py`: both arms red (2 failed, 10 passed), so they still prove the second draft goes through the sentence check. `graph.py` restored byte for byte.

### `test_debugging_guide_coverage.py`, two arms

- Kind: stale premise (a new source file with no row).
- Change: a row for `src/system_03_search_agent/contracts/token_order.py` in `docs/build/Debugging_guide.md`, under `contracts/`, written the way its neighbours are (path, job from the docstring, when to read it). The manifest regenerated with the test file's own generator; it gained exactly one line. No other new source file was missing.

### `test_write_answer_structure.py`, the Researcher and Plain language arms

- Kind: reading order.
- Cause: both read the answer in arrival order. The listing ("Disease records found", "Where this answer comes from" and its rows) now arrives first, so the Researcher headings read `['Disease records found', 'Disease associations']`; the Plain language arm's last token is still the medical-advice note, but its payload now carries `placement: "listing"`.
- Change: a `_read_tokens` helper reads the tokens through `in_reading_order` from `contracts/token_order.py`, and both arms assert on it. Each gained a populate-check that the first token on the wire is placed `listing`, so the reading order is doing work. The Plain language arm's expected note now includes `"placement": "listing"`: in reading order the note is the last thing under the records, not part of the summary slot above them. Every other assertion is unchanged.
- Evidence: 51 passed. Mutation, notes sent with `placement` "summary": the Plain language arm red on its last-token assertion. Mutation, summary tokens sent with `placement` "listing": the Researcher arm red on its headings, `['Disease records found', 'Disease associations']`.

### `test_write_answer_structure.py`, the command line merged-row arm

- Kind: reading order.
- Cause: the arm fed the renderer `token` and `citation` events only. The command line now holds listing tokens until `done` or `finish()` so the summary prints above them, so nothing of the listing was printed and the row's `[2]` was missing from the output. The row's own text still carried both numbers.
- Change: the run's `done` is fed in too, as the command line receives it, with a populate-check that the run has one. A new assertion pins the reading order on what the command line prints: "Found 1 gene record" before "Gene record NCBIGene:672 [1]". The A-103-03 assertions are unchanged.
- Evidence: passes. Mutation, the command line not holding listing tokens: red on the new order assertion, with "Gene records found" printed first.

### `test_write_findings_tail.py::test_the_note_precedes_the_tail_and_carries_no_marker`

- Kind: reading order.
- Cause: the arm reads positions (the summary first, the model's prose, then the heading and the rows), in arrival order, where the listing heading now arrives second, after its paragraph break.
- Change: a `_read_tokens` helper in reading order; the positions are asserted on it. A populate-check pins the arrival order: the listing heading is among the first two tokens on the wire.
- Evidence: 8 passed. Mutation, summary tokens sent with `placement` "listing": red, the first token in reading order is `"\n\n"`, not "Found 3 disease records".

### `test_write_streaming_premise.py::test_w3_...`

- Kind: reading order, on an arm about the stream.
- Cause: W3 asserted "every token before the first citation". The listing and its citations now go out before the summary's tokens, on purpose.
- Change: the live versus buffered parity (types, payloads, seq) is unchanged. The order block now asserts, in arrival order: the first token is placed `listing` and a summary token follows (populate-checks); a citation never arrives before a token that carries its marker, so no chip is shown for a row or sentence not yet on screen; every citation before the first trust signal and the answer-scope verdict last, as before. The reading order itself is pinned by `contracts/test_token_order.py` and `adapters/test_token_placement_surfaces.py`, named in the comment, not restated here.
- Evidence: 4 passed. Mutation, the listing's citations sent before its tokens: red, "citation cq-408908faa83a-1 arrived before any token that carries its marker".

### `test_run_registry_stop_mid_write.py`, S1 to S4

- Kind: stale premise.
- Cause: every arm failed at the shared helper's populate-check, "answer events existed before the stop". The helper stops the run the moment the writing call starts, and the listing and its citations now go out before that call, as the phase intends. Probed on the offline run: at the stop the read path held the `step` event, four listing tokens (paragraph break, heading, table header, one row, each `placement` "listing") and one citation; nothing else of the answer.
- Change: S1 to S4 keep stopping during the writing call, which is their subject (a cancelled writing call, its cost, charged once). The populate-check now says what is true at that moment: the listing and a citation are on the read path, and no summary token, trust signal or `done` is. S2 pins the owner's rule of 2026-09-27 on the server: exactly one `cancelled` error after the stop; the answer events in the replay and in the live queue are exactly those on the read path at the stop, so the records stay; no summary token, trust signal or `done` exists anywhere. S3: still one row, still `refuse`, no summary token or verdict in it, every answer event in it was on screen before the stop, and the cost still includes the cancelled writing call. S1 and S4 unchanged apart from the helper.
- Added S5 to S7, card 58's original premise kept: the stop lands in Write before the listing, by parking Write's one wait before the listing is built, the read of the `think.asks_features` decision (`_clinical_features_asked`, made slow, not endless, like `_SlowSynth`). Populate-checks: Write announced itself, no answer event exists, the writing call has not started. S5: the wait is cancelled, the writing call never starts, no task left running. S6: card 58's S2 assertions word for word, no answer event in any read path. S7: one `refuse` row, no answer event, the harness total charged once.
- Added S8, "no writing task keeps running" under option B: the second draft started beside the first (the offline listing cites every finding, so `_listing_uncitable` and `_two_drafts_fit_cap` are set to start it). Both writing calls are cancelled, none finishes, no task is left running, one `cancelled` error, one `refuse` row at the harness total.
- Evidence: 8 passed. Mutations, each restored after: `cancel_run` a no-op, all of S1 to S7 red; `_terminal_events_for_capture` adding the two costs (F-58-J01), S4 and S7 red; the registry clearing tokens and citations when it appends the `cancelled` error, S2 and S3 red; `write_node`'s `finally` skipping `_drop_second_draft`, S8 red with the second draft's `Harness.call_tier` task still pending.

### `test_run_registry_stop_after_done.py::test_b_...`

- Kind: stale premise.
- Cause: B reused `_stop_mid_write`, so it failed at the same populate-check.
- Change: B now stops in Write before the listing (`_stop_before_listing`), keeping every assertion: no `done`, the `cancelled` error last, the run marked cancelled, no memory write, one `refuse` row. Added B2, the stop after the listing: the same assertions, plus the records on the read path at the stop are still there and the `cancelled` error is the only event after them.
- Evidence: 7 passed. Mutation, `cancel_run` a no-op: B and B2 red.

## Real defects found

None. Every one of the 14 failures was a test premise the early send made stale, or an order assertion that now holds in reading order. No source file changed: `core/graph.py`, `core/run_registry.py` and `core/run.py` were only mutated for the checks above and restored byte for byte (`git status` clean under `src/` after each).

Three behaviours were probed for a defect and held, each now pinned by an arm:

| Behaviour | Arm |
|---|---|
| A stop after the records keeps them on both read paths and adds nothing after the `cancelled` error | S2, B2 |
| A stopped run is recorded as `refuse`, never answered, with the cancelled writing call's cost, charged once | S3, S4, S7 |
| No writing call outlives a stop, including a second draft started beside the first | S1, S5, S8 |

## Pass counts

Pasted from output.

| Run | Result |
|---|---|
| The seven failing files, before any change | 14 failed, 78 passed |
| The 14 originally failing tests, by id | 14 passed, 2 warnings in 5.51s |
| `tests/system_03_search_agent/core` | 1436 passed, 56 skipped, 1 deselected, 2 warnings in 69.94s |
| `tests/system_03_search_agent/synthesis` | 745 passed, 10 skipped, 1 xfailed in 4.48s |
| `tests/system_03_search_agent/test_debugging_guide_coverage.py` | 7 passed in 0.57s |
| Full unit suite, `pytest -m "not integration" -q -p no:cacheprovider`, once | 7369 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 357.82s (0:05:57) |
| `ruff check`, whole repository | All checks passed! |
| `isort --check-only src tests` | exit 0, skipped 2 files |

## Left for the lead

- A stop after the records leaves a `refuse` row whose `citations` and `coverage_tags` carry the listing's citations, the records the person saw. No answer text is saved (`refuse` is not in `_SAVEABLE_OUTCOMES`), and `refuse` reads as abstain. I judged this correct, not a defect, and pinned it in S3 (only events on screen before the stop); the lead may want the owner to confirm history should count those records.
- The command line holds the listing until `done` or `finish()`, so on the command line the records no longer print sooner, only in the right order. Correct for reading order; the speed gain is the web screen's.
- `docs/build/Debugging_guide.md`'s per-folder test-file counts were already out of step with the tree before this phase (for example `core/` reads 22); this phase adds test files to `contracts/`, `eval/`, `feedback/`, `adapters/`, `core/` and `synthesis/`. Not touched here: no gate reads that table, and a recount is its own change.
