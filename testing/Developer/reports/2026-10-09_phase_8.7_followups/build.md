# Phase 8.7 follow-ups, build

Builder report for the two follow-ups of build phase 8.7 (merged to `develop` as #218) and the verifier's one regression. Branch `fix/8.7-followups-a04-a07`, cut from `origin/develop` at `b01dee92`. Findings: F-8.7-A04 and F-8.7-A07 from `testing/Developer/reports/2026-10-08_phase_8.7/adversary.md`, and F-8.7-V01 from `verifier.md` in the same folder.

## Table of contents

- [Summary](#summary)
- [V01: the token's serialization schema](#v01-the-tokens-serialization-schema)
- [A07: the summary no longer waits on the lead pick](#a07-the-summary-no-longer-waits-on-the-lead-pick)
- [A04: the checked words reach the citation, listed once](#a04-the-checked-words-reach-the-citation-listed-once)
- [Test queries](#test-queries)
- [Test runs](#test-runs)
- [Deviations and open items](#deviations-and-open-items)

## Summary

| Finding | Status | Commit |
|---|---|---|
| F-8.7-V01 | Fixed | `e612bfa9` |
| F-8.7-A07 | Fixed, by a tighter bound (see deviations) | `b85aa16a` |
| F-8.7-A04 | Fixed on the server, MCP, GraphQL, the REST citations export, the command line, the saved answer and the web view; the web screen still renders no chip words (see deviations) | `916b5c37` |
| Test queries | Queries 1 and 91, two rows in the cards table | `d0a0b17a` |

Base: `git rev-parse HEAD` printed `b01dee92b2981afce665ecf5949e693664cea3fe` before any change.

## V01: the token's serialization schema

What was wrong: fix commit `95680687` left `placement` out of a token through a wrap `model_serializer` returning `Any`, so `TokenPayload.model_json_schema(mode="serialization")` read `{}`.

What changed (`contracts/events.py`): the serializer is gone. `placement` now leaves itself out when None through `Field(None, exclude_if=_placement_is_absent)`. The bytes on the wire are unchanged (the existing pinned-bytes test still passes) and the serialization schema is the full object again, identical in its properties to the validation schema.

Test: `test_events.py::TestTokenPayload::test_the_serialization_schema_describes_a_token` pins the type, `additionalProperties: false`, the required field, the six properties, the `placement` enum, and equality with the validation schema's properties.

Mutation: `contracts/events.py` restored to the base, the test file run: `1 failed, 174 passed`. Restored: `175 passed`.

## A07: the summary no longer waits on the lead pick

In the person's words: the written summary no longer waits up to 3.5 s on the classifier's first-sentence pick.

Where it waited: `_write_answer` asks `_lead_sentence_choice` after grounding and before any summary token, and that call waited up to `_LEAD_DECISION_MAX_WAIT_S` (4.0 s), less half a second of budget, so a slow or failing classifier held the summary 3.5 s and then the count line led anyway.

What changed (`core/graph.py`): `_LEAD_DECISION_MAX_WAIT_S` is 1.0 s, the same grace phase 8.6 gives every other decision read late (`_LATE_DECISION_GRACE_S`). Jev answers in 0.3 to 0.8 s, so a pick in that range still leads; a later one is cancelled by `asyncio.wait_for`, is never recorded as made, and leaves today's count line leading. The decision stays the classifier's; code reads no word of the question.

Tests (`core/test_write_answers_sooner.py`):

| Test | What it pins |
|---|---|
| `test_a_slow_pick_never_holds_the_summary_past_jevs_own_answer_time` | With the module's own bound and Jev delayed 10 s, the first summary token leaves within 1.5 s of the writer's draft returning, the count line leads, and no lead decision is recorded |
| `test_a_pick_that_arrives_in_time_still_leads` | Jev answering in 0.7 s still puts its sentence first, the count line second |

Mutations:

| Mutation | Result |
|---|---|
| `_LEAD_DECISION_MAX_WAIT_S` back to 4.0 | `1 failed, 1 passed, 43 deselected`, with `the summary waited 3.50 s on a slow pick` |
| `_LEAD_DECISION_MAX_WAIT_S` at 0.5 | `1 failed, 1 passed, 43 deselected` (the in-time pick no longer leads) |

Restored, the file ran `45 passed` at that commit.

## A04: the checked words reach the citation, listed once

In the person's words: a citation under a summary sentence carries the words that sentence was checked against, as card 57 made it, and no surface lists a citation twice.

What was wrong: with the listing sent early, `_write_answer` replaced every final citation whose id the listing had sent with the early payload and never sent it again. The early payload's `claim_text` holds only the listing row's words, so card 57's join (the row's words plus each summary sentence's checked words) was computed and thrown away.

What changed:

- One rule, in `contracts/token_order.py`: `updates_citation(earlier, later)` is true when every field but `claim_text` is equal; `one_per_citation_id(citations)` keeps one row per id in first-arrival order, the later payload in the earlier one's place, and drops a repeat that changes anything else, since a chip with the first number may already be on screen. `CitationPayload` in `contracts/events.py` documents it.
- Server (`core/graph.py`): after the summary, a listing citation the summary also cites is sent again with the same id, number and record and the grown `claim_text`. Only ids whose payload changed are re-sent. A final payload that differs in anything but `claim_text` keeps the early payload and is not re-sent. Re-sends happen only for a request that reads `placement` (the web bundle, the command line, MCP and GraphQL), so an older client never meets one.
- MCP (`adapters/mcp/server.py`): one row per id, the re-send in place, counted once for the citation cap's disclosure.
- GraphQL (`adapters/graphql/fold.py`): the collector replaces on a re-send that changes `claim_text`, with nothing omitted or disclosed for it; an exact repeat or a conflicting repeat is still a disclosed duplicate (F-4.3-A-07); a re-send of a capped citation is not counted against the cap twice. This covers `ask`, `run` and `citations`.
- REST export (`adapters/web_sse/app.py`, `GET /v1/query/{run_id}/citations`, which `s3 citations` prints): one row per id, and the truncation header counts distinct citations.
- Command line (`adapters/cli/render.py`): the stream renderer takes a re-send without the "redefined" warning (a conflicting repeat still warns and keeps the first); `s3 ask --json` lists one citation per id with the grown words.
- Saved answer capture (`feedback/capture.py`): the stored citations are one per id.
- Web (`frontend/src/hooks/useRunView.ts`): `updatesCitation`, the same rule; a re-send replaces the kept citation by id, any other repeat of an id is ignored, and source cards come from the kept citations. Before, a repeat with another number overwrote the chip's citation and added a second source card.

Tests:

| Surface | Test |
|---|---|
| Server | `test_a_chip_under_a_summary_sentence_shows_the_words_it_was_checked_against`: records 1 to 3 are re-sent after the summary, 4 and 5 are not, and the folded `claim_text` of record 1 is "Disease MedGen:C1, name: disease name number 1 NCBIGene:672 is associated with disease name number 1" |
| Server | `test_the_early_send_ends_with_the_citations_a_request_without_it_gets`: folded one per id, the citations with and without the early send are equal field for field |
| Server | `test_the_answer_keeps_each_early_citations_number_record_and_link` (replaces the J05 arm): a final payload changed in `entity_name` keeps the early payload and is not re-sent |
| Contract | `test_token_order.py`, four arms: replace in place, dicts and models alike, a renumbered or re-recorded repeat is not an update, an unrepeated stream is unchanged |
| MCP | `test_mcp_keeps_one_citation_per_id_with_the_checked_words` |
| GraphQL | `test_graphql_keeps_one_citation_per_id_with_the_checked_words`, `test_graphql_citations_export_keeps_one_citation_per_id` |
| REST export | `test_rest_citations_export_keeps_one_citation_per_id` |
| Command line | `test_cli_stream_takes_the_resent_citation_without_a_warning`, `test_cli_json_answer_lists_one_citation_per_id_with_the_checked_words` |
| Saved answer | `test_capture_placement.py::test_a_citation_sent_again_is_saved_once_with_its_checked_words` |
| Web | `useRunView.placement.test.ts`, three arms: one source per number with chips unchanged after a re-send, a renumbered or re-recorded repeat ignored, and `updatesCitation` itself |

Existing arms that asserted "every citation is sent once" now assert that every repeat is an update (`_assert_resends_are_updates`). The web-modelled tests in `test_write_findings_tail.py` and `test_write_answer_structure.py` fold citations one per id, as every surface does.

Mutations:

| Mutation | Result |
|---|---|
| Server skips every id the listing sent (the code before the fix) | 2 failed, 45 passed: the chip test and the parity test |
| Server keeps the fresh payload whatever differs (guard dropped) | 1 failed, 46 passed: the number-record-and-link test |
| `adapters/mcp/server.py` at the base | 1 failed, 17 passed |
| `adapters/graphql/fold.py` at the base | 2 failed, 16 passed |
| `adapters/web_sse/app.py` at the base | 1 failed, 17 passed |
| `adapters/cli/render.py` at the base | 2 failed, 16 passed |
| `feedback/capture.py` at the base | 1 failed, 17 passed |
| Web: `updatesCitation` check dropped | 1 failed, 7 passed |

Each file was restored by copy and the run went green again.

## Test queries

`testing/Test_queries_and_workflows.md` has no "card 57" query on this branch, so the checks went where a person can see them: query 91 (`s3 ask --json`) checks each citation appears once and that one a summary sentence cites carries the words that sentence was checked against; query 1 checks that choosing the first sentence never holds the summary more than about a second. Two rows in the cards table point to them.

## Test runs

| Run | Result |
|---|---|
| Touched test files (seven) | `307 passed, 2 warnings in 7.36s` |
| `tests/system_03_search_agent/core` | `1483 passed, 56 skipped, 2 warnings in 69.70s` |
| `tests/system_03_search_agent/adapters` | `872 passed, 2 warnings in 32.74s` |
| `tests/system_03_search_agent/contracts` | `219 passed in 0.33s` |
| `tests/system_03_search_agent/feedback` | `240 passed, 2 warnings in 9.79s` |
| `npx vitest run src/hooks src/components/screens` | `Test Files 30 passed (30)`, `Tests 254 passed (254)` |
| `npx tsc --noEmit -p .` | exit 0 |
| `ruff check` (whole repository) | `All checks passed!` |
| `isort --check-only src tests` | exit 0 |

No live model calls. No full suite.

## Deviations and open items

- The web screen shows no chip words. The ticket says the web chip showed the checked words before phase 8.7; it never did. `testing/UI_fixes_done.md` row 23 records card 57 as "seen today in the command line's `s3 --json` and the API's citation events, not yet on the web screen", and the web's `Source` type carries no `claim_text`. Card 57's words are restored where they were visible (the command line, MCP, GraphQL, the REST export, the saved answer). The web view now keeps the re-sent citation by id, so it holds the right words; showing them on a chip is new design work for the owner.
- A07 is a tighter bound, not a pick beside the writer. The pick reads the writer's grounded sentences and the writer does not stream, so it cannot start before the writer returns. I tried asking it the moment the prose was final, beside the trust verdicts and notes; that work is synchronous and took no measurable time (the test showed the count line built before the request even started), so it bought nothing and was reverted. Trade-off: when Jev fails, the guard tier's pick (about 2 s) now usually arrives late and the count line leads.
- The timing test runs on the event loop's real clock with the module's own bound, not a scaled one: patching the bound would let the old code pass too. It takes about 1 s.
- Outside the fence, two more readers join raw citation events and would see a re-sent citation twice: `core/run.py` (session memory stores a second finding for the same id) and `eval/trace_source.py`. Each is a one-line change to `one_per_citation_id`. Not touched. `visualizations/Schema_visualization.md` should state the re-send rule; not touched.
- GraphQL keeps disclosing an exact duplicate citation, as an existing test pins; only a repeat that changes `claim_text` replaces.
- The REST export's truncation header now counts distinct valid citations, not every citation event.
