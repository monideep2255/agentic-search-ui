# Builder Q report, build phase 8.10

Builder Q's report for two tickets of `tracker/phase_8.10.md`. Both meet every acceptance line.

- T-8.10-05: "MCP does what the web does".
- T-8.10-06: "GraphQL keeps every citation and the clarifying options".
- Branch: `feat/8.10-q`, cut from the pushed phase branch at 8cd197d.
- Numbers: every one below is pasted from command output.
- Paths: repository-relative. `<scratchpad>` is the session's scratch folder, not committed.

## Table of contents

- [Commits](#commits)
- [T-8.10-05: MCP does what the web does](#t-810-05-mcp-does-what-the-web-does)
- [T-8.10-06: GraphQL keeps every citation and the clarifying options](#t-810-06-graphql-keeps-every-citation-and-the-clarifying-options)
- [The allowlist keys added](#the-allowlist-keys-added)
- [The ownership tests](#the-ownership-tests)
- [Every new test can fail](#every-new-test-can-fail)
- [Gates](#gates)
- [What the lead must decide](#what-the-lead-must-decide)
- [Left undone, and why](#left-undone-and-why)
- [Where the brief or the ledger did not match the code](#where-the-brief-or-the-ledger-did-not-match-the-code)
- [What cost time](#what-cost-time)

## Commits

| Commit | Subject |
|---|---|
| `63e28abc` | feat(mcp): give the MCP server the web app's answers, history, reopen and feedback |
| `5510cc5c` | feat(graphql): keep every citation and carry the trust line and clarifying options |
| `8d6681c7` | test(mcp): prove a guest token is refused by every parity tool |
| this report's commit | docs(tracker): builder Q's report for phase 8.10 |

Files changed, all inside the fence:

- `src/system_03_search_agent/adapters/mcp/server.py`
- `src/system_03_search_agent/adapters/graphql/types.py`
- `src/system_03_search_agent/adapters/graphql/fold.py`
- `tests/system_03_search_agent/adapters/mcp/test_parity_tools.py` (new)
- `tests/system_03_search_agent/adapters/mcp/test_no_cost_and_auth.py`
- `tests/system_03_search_agent/adapters/graphql/test_parity_fields.py` (new)
- `tests/system_03_search_agent/adapters/graphql/test_types.py`
- `tests/system_03_search_agent/adapters/graphql/test_fold.py`
- `tests/system_03_search_agent/adapters/test_audience_depth_values.py`
- this report

No file was added under `src/`, and the first line of every changed module docstring is unchanged, so `docs/build/Debugging_guide.md` and its manifest need no change for these commits and no manifest was regenerated.

## T-8.10-05: MCP does what the web does

| Acceptance line | Status | Evidence |
|---|---|---|
| "An AI agent can ask for Plain language." `audience_depth` accepts every web depth, the default stays Researcher, and the depth test cites the decision row | Met | `server.AudienceDepth` lists `plain_language`, `researcher`, `clinical_brief`, `deep_technical`; `_DEFAULT_AUDIENCE_DEPTH` is `researcher`. `test_audience_depth_values.py::test_mcp_tool_accepts_every_depth_and_keeps_researcher_as_its_default` quotes the `DECISIONS.md` row of 2026-09-26 and checks the annotation, the default and the published schema's `enum`. `test_parity_tools.py::TestAConversationCanContinue::test_plain_language_reaches_the_core` proves `plain_language` reaches the core's `Query` and that no depth still means `researcher` |
| "A long answer keeps every citation it points at." The cap of 50 rises to the run's bound, and a bound remains | Met | `_MAX_CITATIONS = 100`. `TestEveryMarkerKeepsItsCitation::test_a_ninety_three_citation_answer_keeps_all_ninety_three` checks every `[n]` marker in the answer resolves to a returned citation. `test_a_bound_remains_and_what_it_cuts_is_disclosed` checks the cut at the cap, its disclosure and `maxItems: 100` in the output schema. `test_the_citation_cap_is_the_runs_own_bound` pins it to `core/graph.py`'s `_MAX_FINDINGS_FOR_DISPLAY` |
| "An agent knows how to continue a conversation." The input schema describes `session_id` and `audience_depth`, and the result returns the session id | Met | Both parameters and the new output field carry `description` text; the tool description and the server `instructions` say to pass `session_id` back. `TestTheSchemaTellsAnAgentHowToContinue` reads them from `list_tools()`. `TestAConversationCanContinue::test_the_session_id_comes_back_and_carries_the_follow_up` asks twice through the real tool and checks the second `Query` carries the returned session id |
| "A bare topic gives the agent the clarifying options, and it is not labelled a refusal." | Met | The result carries `clarifying_options` and `clarifying_question`; an ask-back's `trust_signal.outcome` is `ask`. `TestAskBackIsNotARefusal` replays the GERD run exactly as develop emitted it (`rest_05_gerd.json` in the audit's evidence) and checks four limits: a guardrail refusal, a run that cited anything, and a crashed run are never relabelled, and an answer carries no clarifying fields |
| "The agent gets the same trust line the web shows." | Met | `trust_line` is `DonePayload.trust_line`, trimmed, blank read as none, the way `useRunView.ts` reads it. `TestTrustLine` covers both |
| "An agent can list my past searches, reopen an answer, and send feedback." Same service functions as the REST routes, same ownership checks, a test per tool | Met | `list_past_searches` calls `list_history`, `reopen_past_answer` calls `get_saved_answer`, `send_answer_feedback` calls `RunRegistry.resolve_owned_run` then `record_feedback` then `capture_event`, each keyed on `user:<id>` from the bearer token. See [the ownership tests](#the-ownership-tests) |
| The response allowlist gains exactly the keys this ticket adds, each named | Met | See [the allowlist keys added](#the-allowlist-keys-added). The ledger's History is outside my fence, so the lead records them there |

What a person gets, in their words. An AI agent working for them can now:

- ask for the everyday wording the web uses;
- keep a conversation going;
- see every source a long answer cites;
- hear a bare topic as a question with four ready-made follow-ups, rather than as "cannot answer";
- list, reopen and rate their own past searches, and nobody else's.

## T-8.10-06: GraphQL keeps every citation and the clarifying options

| Acceptance line | Status | Evidence |
|---|---|---|
| "A long answer keeps every citation it points at." | Met | `types.MAX_CITATIONS = 100`. `test_parity_fields.py::TestEveryMarkerKeepsItsCitation` checks every marker of an 84-citation answer resolves on both `ask` and `run`, and pins the cap to the run's bound. `TestThroughTheRealSchema` sends a real `ask` document over HTTP with a real account and gets all 84 |
| "A bare topic gives the clarifying options": the `ask` result carries them | Met | `AskResult` and `RunResult` gain `clarifyingQuestion` and `clarifyingOptions`. `TestClarifyingOptions` covers the GERD run on `ask` and `run` and the same four limits as MCP |
| "The same trust line the web shows." | Met | Both results gain `trustLine`. `TestTrustLine` checks it arrives, blank is null, and it is withheld when the fold reported a lower verdict than the run's own or dropped a citation, so it never reads more confident than the result |
| All additive. No existing field changes name or type | Met | The three fields are nullable and default to null. `TestAllAdditive` reads the real printed schema and checks every existing `AskResult` and `RunResult` line, name and type, is unchanged and the new ones are nullable. `test_types.py`'s exact field-set pin on `RunResult` gained the three names and still refuses `personaName` |

One difference from MCP, on purpose: GraphQL keeps an ask-back's `trustSignal.outcome` as the run reported it, `refuse`. This fold's own stated invariant is that it only ever lowers a verdict, and the ticket did not ask for the label. A client tells a question back from a refusal by `clarifyingQuestion`, the same field the web uses. The lead may want the label to match MCP; see [what the lead must decide](#what-the-lead-must-decide).

## The allowlist keys added

The allowlist lives in `tests/system_03_search_agent/adapters/mcp/test_no_cost_and_auth.py`, not in `server.py`.

On `ask_biomedical_question`'s response (`_ALLOWED_RESPONSE_KEYS`), four keys:

- `session_id`: the caller's own conversation id, to ask a follow-up.
- `trust_line`: the one plain trust sentence the web shows.
- `clarifying_question`: the question back, set only on an ask-back.
- `clarifying_options`: its up to four one-click questions.

For the three new tools, one pinned set each (`_ALLOWED_RESPONSE_KEYS_BY_TOOL`), so a key one tool may return cannot ride out through another. A union would have let a saved `answer_markdown` pass on the ask tool's response.

- `list_past_searches`: `items`, `count`, `omitted_count`, `trace_id`, `question`, `asked_at`, `trust_signal`, `citation_count`, `has_saved_answer`. All are `GET /v1/history`'s own fields.
- `reopen_past_answer`: `trace_id`, `question`, `asked_at`, `audience_depth`, `answer_markdown`, `citations`, `citations_omitted`, `trust_signal`, `trust_line`, plus the fourteen citation keys already in `_ALLOWED_RESPONSE_KEYS`. New names against REST: `audience_depth` (REST calls it `depth` and folds three depths to `researcher`) and `citations_omitted`.
- `send_answer_feedback`: `run_id`, `recorded`. REST answers 204 with no body.

None is a cost, a credential or another account's data. `TestNeverCost::test_the_three_parity_tools_return_only_their_pinned_keys` calls each new tool as an operator-allowlisted account and checks no cost key and nothing outside its set.

## The ownership tests

All in `tests/system_03_search_agent/adapters/mcp/test_parity_tools.py`, each through a real MCP client session against the mounted server, with accounts made through the real `/auth/signup` and `/auth/login`. They ran here against a local Postgres; CI provides one and fails on a database skip.

| Tool | Test | What it proves |
|---|---|---|
| `list_past_searches` | `TestPastSearchesAreYoursAlone::test_one_account_never_sees_anothers_searches` | Accounts A and B each have a stored search; each sees only its own |
| `reopen_past_answer` | `TestReopeningIsYoursAlone::test_another_account_cannot_reopen_it_and_learns_nothing` | B cannot reopen A's saved answer, and B's refusal is word for word the refusal for a search that does not exist, so B learns nothing about A's trace id |
| `send_answer_feedback` | `TestFeedbackIsYoursAlone::test_another_account_cannot_rate_your_run_and_nothing_is_written` | B cannot rate A's run, asserted on the stored `user_feedback`, which stays null |
| `send_answer_feedback` | `TestFeedbackIsYoursAlone::test_the_stored_rows_own_owner_is_checked_too` | REST's second check: when the registry says A owns the run but the stored row names another account, nothing is written |
| All three | `TestGuestsGetNoMoreThanRest::test_a_real_guest_token_is_refused_by_every_parity_tool` | A real guest token from `/auth/guest` is refused by every new tool |
| All four | `TestTheSchemaTellsAnAgentHowToContinue::test_no_new_tool_takes_an_owner_from_its_arguments` | No tool takes an owner, user id, account or email argument |
| `send_answer_feedback` | `TestFeedbackIsYoursAlone::test_an_argument_the_tool_does_not_declare_is_refused` | An `owner_id` argument is refused by name, not silently dropped |

Guests: MCP authenticates registered accounts only, so a guest gets less here than on REST (which lets a guest list and rate its own runs), never more.

## Every new test can fail

How each mutation ran, with `<scratchpad>/mutate_q.py`:

1. Apply it alone to the committed source.
2. Run the tests it names.
3. Restore the file with `git checkout --`.

Result lines pasted from its output:

T-8.10-05, 16 mutations of `adapters/mcp/server.py`:

```text
M1 citation cap back to 50: exit 1: 2 failed, 1 passed in 23.69s
M2 ask-back relabel removed: exit 1: 1 failed in 8.20s
M3 guard clause dropped from _is_ask_back: exit 1: 1 failed in 16.88s
M4 zero-citation clause dropped from _is_ask_back: exit 1: 1 failed in 14.44s
M5 fatal clause dropped from _is_ask_back: exit 1: 1 failed in 17.03s
M6 trust line not read from done: exit 1: 1 failed in 10.19s
M7 plain_language dropped from AudienceDepth: exit 1: 2 failed in 10.21s
M8 session_id not returned: exit 1: 1 failed in 15.08s
M9 session_id description removed: exit 1: 1 failed in 7.14s
M10 history listed without the owner filter: exit 1: 1 failed in 17.07s
M11 saved answer fetched by trace id alone: exit 1: 1 failed in 9.14s
M12 feedback skips the registry ownership rule and writes as the run's owner: exit 1: 1 failed in 21.30s
M13 row-level FeedbackOwnershipError swallowed: exit 1: 1 failed in 9.25s
M14 feedback tool accepts an owner_id argument: exit 1: 1 failed in 7.95s
M15 an unpinned key added to a new tool's output: exit 1: 1 failed in 7.75s
M16 a token that resolves to no account is let through: exit 1: 1 failed in 10.32s
git status after restore: (clean)
```

Each mutation's first failing line, to show it failed on the intended assertion and not incidentally. The runner cuts each line at 220 characters, and pytest shortens long sets with `...`. The MCP ownership mutations and M1, from a second run of the same runner:

```text
M1 citation cap back to 50: exit 1: 2 failed, 1 passed in 8.35s
     E       AssertionError: markers with no citation: [51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 9
M10 history listed without the owner filter: exit 1: 1 failed in 7.87s
     E       AssertionError: assert 'paritytest-2d8a53bbf65c4d6cb6e69d2aff637a75' not in {'17d34d0d-bed9-4f5a-9e6d-2c0fb84fc265', '41b5d4a2-cfa7-4fd1-84c4-a38077320cc6', '528a904a-3f33-45bf-b509-f09cd8b56c49...3e66-5186-4175-
M11 saved answer fetched by trace id alone: exit 1: 1 failed in 8.63s
     >       raise AssertionError(f"expected {name} to refuse, it returned {result.structured_content!r}")
M12 feedback skips the registry ownership rule and writes as the run's owner: exit 1: 1 failed in 9.16s
     >       raise AssertionError(f"expected {name} to refuse, it returned {result.structured_content!r}")
M13 row-level FeedbackOwnershipError swallowed: exit 1: 1 failed in 7.15s
     >       raise AssertionError(f"expected {name} to refuse, it returned {result.structured_content!r}")
git status after restore: (clean)
```

T-8.10-06, all 10 mutations of `adapters/graphql/fold.py` and `types.py`, each with its first failing line:

```text
G1 citation cap back to 50: exit 1: 3 failed in 7.50s
     E           AssertionError: markers with no citation: [51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84]
G2 think no longer read: exit 1: 1 failed in 5.07s
     E           AssertionError: assert None == 'What would you like to know about GERD?'
G3 guard clause dropped from _parity_fields: exit 1: 1 failed in 4.67s
     E       AssertionError: assert 'What would you like to know about GERD?' is None
G4 citation clauses dropped from _parity_fields: exit 1: 1 failed in 5.35s
     E       AssertionError: assert 'What would you like to know about GERD?' is None
G5 fatal clause dropped from _parity_fields ask-back: exit 1: 1 failed in 3.78s
     E       AssertionError: assert 'What would you like to know about GERD?' is None
G6 trust line not read from done: exit 1: 1 failed in 4.44s
     E       AssertionError: assert None == 'Based on 3 sources, not yet confirmed'
G7 trust line returned without comparing the final outcome: exit 1: 1 failed in 5.23s
     E       AssertionError: assert 'Based on 3 sources, not yet confirmed' is None
G8 trust line returned although a citation was dropped: exit 1: 1 failed in 4.57s
     E       assert 'Based on 3 sources, not yet confirmed' is None
G9 a new field made non-null: exit 1: 1 failed in 3.69s
     E           AssertionError: AskResult
G10 a rejected citation also blamed on the cap: exit 1: 1 failed in 4.57s
     E       AssertionError: assert '100-citation limit' not in '1 citation(...ed citation.'
git status after restore: (clean)
```

Two existing tests also went red on the change itself before I updated them, which is each control working: the allowlist test (`test_an_operator_allowlisted_caller_still_gets_no_cost_field`) on the four new ask keys, and the old depth pin (`test_mcp_tool_signature_keeps_the_section_13_2_values`) on `plain_language`:

```text
FAILED tests/system_03_search_agent/adapters/mcp/test_no_cost_and_auth.py::TestNeverCost::test_an_operator_allowlisted_caller_still_gets_no_cost_field
FAILED tests/system_03_search_agent/adapters/test_audience_depth_values.py::test_mcp_tool_signature_keeps_the_section_13_2_values
2 failed, 40 passed, 2 warnings in 37.51s
```

On GraphQL the exact field-set pin on `RunResult` went red the same way:

```text
FAILED tests/system_03_search_agent/adapters/graphql/test_types.py::TestRemainingTypesConstruct::test_run_result_has_no_persona_name_field
1 failed, 240 passed in 13.08s
```

One existing assertion would have gone vacuous: `test_fold.py`'s rejected-citation arm checked `"50-citation limit" not in notes`, which passes whatever happens once the cap is 100. It now reads the constant; mutation G10 shows it goes red.

## Gates

Run from the worktree with CI's placeholder environment and a local Postgres (`<scratchpad>/q_env.sh`).

| Gate | Command | Result |
|---|---|---|
| Lint | `ruff check` | `All checks passed!`, exit 0 |
| Import order | `isort --check-only --diff src tests services tracker alembic .claude .github` | `Skipped 2 files`, exit 0 |
| Unit suite | `bash .github/gates/gate04_unit_suite.sh` | `6190 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 307.44s (0:05:07)`, exit 0. CI's companion check, `python .github/scripts/assert_no_db_skips.py unit-results.xml`: `ok: 6334 test cases, every skip sanctioned (1 a known open finding, deliberately skipped and tracked, 28 a live Layer 1 graph or model credential CI does not hold, 115 the live premise-gate opt-in)`, exit 0, so every database-backed test here ran |

Ticket test commands:

| Ticket | Command | Result |
|---|---|---|
| Baseline, before any change | `python -m pytest tests/system_03_search_agent/adapters/mcp tests/system_03_search_agent/adapters/graphql tests/system_03_search_agent/adapters/test_audience_depth_values.py -q` | `283 passed, 2 warnings in 34.12s` |
| T-8.10-05 | `python -m pytest tests/system_03_search_agent/adapters/mcp tests/system_03_search_agent/adapters/test_audience_depth_values.py -q` | `69 passed, 2 warnings in 37.58s` |
| T-8.10-06 | `python -m pytest tests/system_03_search_agent/adapters/graphql -q` | `254 passed, 2 warnings in 10.66s` |

No live question was sent to develop. Develop runs the old code, so a live check could only repeat what the audit's evidence already records (`runs/rest_05_gerd.json`, `runs/mcp_13_what.json`); the smoke run after the merge is the live proof.

## What the lead must decide

1. `clarifying_question` is one key beyond the ledger's words, which name `clarifying_options`. I added it because `ask` alone is ambiguous: the trust table also uses `ask` for a hedged answer (`synthesis.trust.DECISION_TABLE`), and the web keeps the two apart by exactly this field. If the owner's approval is read as covering `clarifying_options` only, dropping it is a small change, and `answer` still carries the question.
2. GraphQL labels an ask-back `refuse`, MCP labels it `ask`. Recommendation: leave GraphQL as it is for this phase, since its fold promises never to raise a verdict and `clarifyingQuestion` already tells a client; if the owner wants one label everywhere, it is one rule in `_finalize`.
3. The page (builder R) now has more to say than the audit listed: four MCP tools rather than one, `plain_language` accepted, `session_id` returned, `clarifying_question` and `clarifying_options`, `trust_line`, and on GraphQL `trustLine`, `clarifyingQuestion` and `clarifyingOptions`. "One advertised tool, ask_biomedical_question" and "MCP answers only at Researcher depth or deeper" are now false.

## Left undone, and why

All outside my fence, each a place where a person still loses something:

- The REST citations export, `GET /v1/query/{run_id}/citations`, still cuts at 50 (`adapters/web_sse/app.py`, `_MAX_CITATIONS_PER_RUN`), and says so in a header. The web's own answer screen reads the stream, not this export.
- A reopened answer keeps at most 50 citations on every surface, because capture stores at most 50 (`feedback/capture.py`'s `_MAX_CITATIONS`, `InteractionRow.citations` `max_length=50`). A reopened Marfan answer can still point at [77] with nothing behind it, on REST and on MCP. MCP's `citations_omitted` counts only stored entries that fail validation; it cannot see what capture never stored.
- Feedback on a run the server no longer holds (a finished run is kept for its retention window) is refused as "no such run" on MCP as on REST. That is REST's recorded known gap, and the brief asked for REST's checks. The MCP message says what the tool can rate, so an agent is not left guessing.
- `docs/build/Debugging_guide.md`'s row for `adapters/mcp/server.py` still says it "Exposes exactly one MCP tool". The coverage test hashes only each docstring's first line, which I kept, so it stays green while the row's prose is stale.
- History, reopen and feedback on GraphQL and `s3`: out of scope in the ledger.

## Where the brief or the ledger did not match the code

- The brief placed `_ALLOWED_RESPONSE_KEYS` in `adapters/mcp/server.py`. It is in `tests/system_03_search_agent/adapters/mcp/test_no_cost_and_auth.py`; `server.py` only mentions it in a comment.
- The old depth pin pointed at `test_phase_4_1_premise.py::test_input_schema_matches_section_13_2`. That file was deleted in build phase 4.14; the only pin left was `test_audience_depth_values.py`.
- The ledger asked to raise the cap "to the bound the event contract already puts on one answer's citations". The event contract sets none: each citation is its own event and `contracts/events.py` bounds fields, not counts. The run does bound them, at `core/graph.py`'s `_MAX_FINDINGS_FOR_DISPLAY`, 100, and that is the number used.
- The audit says GraphQL's fold ignores `think`; it still did, and now reads its clarifying question and options only.

## What cost time

Nothing took more than five minutes, so there is no `LEARNINGS.md` row. The small things:

- An off-host citation built for a GraphQL test failed inside `Event`'s own validator, which ended the fake run early. Built with `Event.model_construct`, as `test_fold.py` does.
- I stopped the first full-suite run a few minutes in to add the guest-token test, so the gate result covers the final tree.
- A garbled placeholder line slipped into one test while writing it; removed before the first commit.
