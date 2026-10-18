# Phase 8.7 fix round, fix agent 2

Fix agent 2's work on build phase 8.7's one fix round. Base: `47ab8725` on `phase/8.7-answers-sooner`, branch `feat/8.7-fix2`. Findings from the phase's judge and adversary reports: F-8.7-A01, A14, J04, A06, J05, J07, J09 and A04. F-8.7-J03 (the second draft never starts at the 25-cent cap) was left as it is, by instruction.

## Table of contents

- [Summary](#summary)
- [A01 and A14: placement is opt-in per request](#a01-and-a14-placement-is-opt-in-per-request)
- [J04 and A06: the cost cap is a bound](#j04-and-a06-the-cost-cap-is-a-bound)
- [J05: the two unpinned protections](#j05-the-two-unpinned-protections)
- [J07: the count line is placed with the summary](#j07-the-count-line-is-placed-with-the-summary)
- [J09: the writer-failed note on screen](#j09-the-writer-failed-note-on-screen)
- [A04: left open](#a04-left-open)
- [Test runs](#test-runs)

## Summary

| Finding | Status | Commit |
|---|---|---|
| F-8.7-A01 | Fixed | `95680687` |
| F-8.7-A14 | Fixed | `95680687` |
| F-8.7-J04 | Fixed, with a trade-off the lead decides (below) | `1f965526` |
| F-8.7-A06 | Fixed, same trade-off | `1f965526` |
| F-8.7-J05 | Fixed | `19fc7b45` |
| F-8.7-J07 | Fixed | `95680687` (contract), `217bc90b` (screen comments) |
| F-8.7-J09 | Fixed | `df1bc402` |
| F-8.7-A04 | Open | none |

## A01 and A14: placement is opt-in per request

What a person saw: an `s3` command line installed before this phase failed every answered question, because its contract forbids the new `placement` key; a browser holding an older web bundle showed the records above the summary.

What changed:

- The declaration is a query parameter, `POST /v1/query?reads=placement`. A body field was ruled out because `CreateRunRequest` forbids extra keys, so a new client would fail against an older server. A custom header was ruled out because it needs a CORS preflight an older server refuses. An older server ignores the parameter.
- `RequestContext.reads_placement` (default False) carries it into the run. `core/graph.py` decides per request (`_request_reads_placement`), replacing the per-process `_contract_carries_placement`.
- `TokenPayload.placement` is now optional with no default, and is left out of the serialized payload when absent (`_omit_absent_placement`). A request that did not declare gets no `placement` key on any token and the listing after the summary.
- The web bundle (`createRun` in `frontend/src/lib/api.ts`) and the command line (`CliClient.create_run`) declare it. MCP and GraphQL set `reads_placement=True` on their own runs, since both fold tokens in reading order.
- Documented in `visualizations/Schema_visualization.md` (the `token` row and the `placement` bullets) and `visualizations/System_3_deep_dive.md` (the API surface).

Tests:

| Test | What it pins |
|---|---|
| `test_a_client_that_does_not_ask_gets_the_stream_it_got_before` | No early send, no `placement` key, every token frame valid under a strict pre-8.7 token model |
| `test_a_client_that_asks_gets_placement_and_the_early_listing` | A declaring request gets the early listing and the field |
| `test_a_token_without_placement_serializes_to_the_bytes_it_had_before` | Pinned JSON bytes of a token with no placement |
| `TestCreateRun::test_only_a_client_that_asks_reads_placement` (5 cases) | The REST parameter sets the context, and nothing else does |
| `test_declares_that_it_reads_placement_on_the_url_not_the_body` | The command line declares on the URL |
| `test_an_mcp_run_reads_placement`, `test_a_graphql_run_reads_placement` | The in-process surfaces opt in |
| `api.createRun.test.ts` | The web bundle declares on the URL |

Probe, not committed: develop's own `contracts/events.py` (from `origin/develop`) validated every frame of the offline write step. Not declared: 26 of 26 frames accepted (Researcher), 27 of 27 (Plain language). Declared: 12 of 26 and 13 of 27 rejected, every token frame.

Mutation results: per-process decision put back, 1 failed; `placement` serialized when None, 12 failed; REST context always True, 3 failed; command-line parameter removed, 1 failed; MCP opt-in removed, 1 failed; GraphQL opt-in removed, 1 failed; web bundle URL without the parameter, 1 failed. Each file restored byte for byte (checksums compared).

Four test files that model the web bundle built with this phase now build their run with `reads_placement=True`: the stop-mid-write arms, W3 of the streaming gate, the answer-structure states and the findings-tail state.

## J04 and A06: the cost cap is a bound

What a person saw: nothing; the owner saw a 27-cent question under a 25-cent cap.

What changed:

- `Harness.call_cost_bound_usd` prices one call before it is sent: the prompt it will send, stable prefix included, plus its `max_tokens` (the tier's ceiling, 4,000 for the writer) at the output price, at the answering model's price.
- `core.graph._dispatch_tier_call` passes the call's prompt, prefix and `max_tokens` to `check_per_query_cap`, so every model call sent through it (Write's drafts among them) is checked on its own bound. Calls checked elsewhere without a prompt (`harness.decide`, the coordinator reader, Cypher generation) get the tier estimate below. `_two_drafts_fit_cap` prices both drafts the same way.
- `call_tier` holds each call's bound as in flight until it is metered; `check_per_query_cap` adds it, so two calls running at once cannot each be admitted against a total that leaves out the other.
- Without a prompt in hand, the estimate now prices output at the tier ceiling (synth at Opus: $0.172 in place of $0.132), and a guard-tier estimate is never below `MAX_JEV_COST_USD` ($0.01), since `harness.decide` checks Jev calls under the guard tier.
- When the cap stops a call, the existing notes show: the repair cap note for a repair, card 46's note for a first writer call after the listing.

The input side is the one estimate left. No tokenizer for the answering model is installed (`litellm` counts every model with its default encoder), so the prompt count is the larger of the default encoder's count plus 35 percent and one token per three characters. The output side is exact.

Tests:

| Test | What it pins |
|---|---|
| `test_a_call_that_could_pass_the_cap_is_never_sent_and_the_note_shows` | The adversary's question, made to fail the old estimate: the repair is not sent, the question ends under 25 cents, the repair cap note shows. Under the old estimate it ended at $0.256 |
| `test_a_call_is_checked_on_the_prompt_it_actually_sends` | A prompt above the 23,000-token profile is refused before it is sent |
| `test_a_call_still_in_flight_counts_against_the_cap` | An in-flight call is held at its bound and released after |
| `test_a_guard_estimate_bounds_a_jev_call` | The guard estimate is at least the Jev ceiling |
| `test_opus_writer.py` arms | Updated figures: $0.172 without a prompt; a repair after a median first call no longer fits on the profile alone |
| `test_decide.py::test_the_cost_cap_still_applies_after_an_over_ceiling_charge` | Cap raised from $0.005 to $0.015: at $0.005 the Jev call itself is now refused, which is the bound holding |

Mutation results: output priced at 2,000 tokens, 3 failed; the graph check without the prompt, 1 failed; in-flight not added, 1 failed; Jev floor removed, 2 failed.

The trade-off, for the lead. Replayed on writer bench 3's 54 Opus questions at 25 cents with each call's provider-reported prompt: no first writer call refused and no question over the cap, but the completeness repair (24 fired) is refused on 3 of 24 if my prompt count equals the provider's and on 19 of 24 if it runs 25 percent high; a refused repair shows "Note: this answer's completeness check could not run to the end because the query reached its cost limit". With the writer's output ceiling at 2,000 tokens (the bench's largest output was 1,869), all 24 are admitted at either ratio. The ceiling is a writer setting, not the cap check, so I did not change it.

## J05: the two unpinned protections

| Test | Mutation | Result |
|---|---|---|
| `test_the_answer_keeps_each_early_citation_exactly_as_it_was_sent` | Remove `citations = [sent_by_id.get(c.citation_id, c) for c in citations]` | 1 failed |
| `test_a_sentence_without_a_marker_is_never_offered_to_lead` | Remove the `_MARKER_PATTERN.search(sentence)` filter in `_lead_candidates` | 1 failed |

The first spies on the citations `_apply_conflict_flags_to_claim_trusts` receives and compares them with the payloads sent before the writer call. It can see the swap because a freshly built payload for a record the prose also cites differs from the early one in `claim_text`, which is F-8.7-A04.

## J07: the count line is placed with the summary

`contracts/events.py`, `visualizations/Schema_visualization.md`, `frontend/src/lib/events.ts`, `useRunView.ts` and `AnswerScreen.tsx` now say what the code does: "listing" is the record listing and the notes under it; "summary" is the count line and the written answer. A comment-only change; no test.

## J09: the writer-failed note on screen

`AnswerScreen.listingFirst.test.tsx` gains an arm that feeds the server's own order for a writer failure after the early listing (listing break, heading, two list items, two citations, the count line placed "summary", a listing break, the note with `kind: "note"`, `done`). It checks the note shows, the records stay, and the count line sits above the first listing row. The fixtures now send the count line placed "summary" with the written summary, as the server does.

Mutation result: the note added to `HIDDEN_NOTE_PATTERNS`, 1 failed.

## A04: left open

A citation sent early keeps the listing row's words on its chip; the words the summary sentence was checked against (card 57) never reach it. A fix would send an updated citation with the same id after the writer. The screen does not replace a citation by id: `useRunView` keeps the first citation event for each number and skips later ones, and the MCP fold and the saved-answer capture both list every citation event, so a second one would appear twice. A re-send would be ignored on the screen and duplicated elsewhere, so it is not safe without a change to each surface's fold. Left open.

## Test runs

| Run | Result |
|---|---|
| `tests/system_03_search_agent/core` | 1444 passed, 56 skipped |
| `tests/system_03_search_agent/adapters` | 865 passed |
| `tests/system_03_search_agent/contracts` | 214 passed |
| `tests/system_03_search_agent/harness` | 448 passed |
| `npx vitest run src/hooks src/components/screens src/lib` | 38 files, 305 tests passed |
| `npx tsc --noEmit -p .` | exit 0 |
| `pytest -m "not integration" -q -p no:cacheprovider` | 7386 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 380.66s |
| `isort --check-only src tests` | clean |
| `ruff check` (whole repository) | 4 errors, all in `testing/Developer/reports/2026-10-08_phase_8.7/live/runner.py`, committed at the base (`fc271174`) and outside this fence: three unused `noqa: E402` and one blind `except Exception` |

The core run came before the last two harness arms and the prompt-size arm were added; those passed in their own files and in the full suite.
