# Card 63 builder report

Card 63 on `testing/UI_fix_plan.md`, dial position 2, built on the branch `fix/card63-save-and-say` from develop at `749d42df`. Three code commits: `d1736e13` (the tool says why a search failed), `bf4a697e` (the summary and the note say it in our words), `aed1c99f` (every "not yet confirmed" answer is saved). No test, gate or mutation was run by the builder: see "Not run here".

## Table of contents

- [What a person notices](#what-a-person-notices)
- [What changed](#what-changed)
- [The reopen paths](#the-reopen-paths)
- [Not run here](#not-run-here)
- [Judgement calls and open items](#judgement-calls-and-open-items)
- [Test round](#test-round)
- [Fix round, 2026-09-29](#fix-round-2026-09-29)

## What a person notices

- A "not yet confirmed" answer can now be reopened from history and through MCP's `reopen_past_answer`, with its trust line and any note under it. About six answered searches in ten end that way.
- When NCBI says PubMed's search is down, the note under the answer reads "PubMed's search is down at NCBI right now, so this answer has no papers from it. Try again later." It no longer says "Ask again to retry".
- A timeout, a rate limit or any other failure keeps the original note, "Ask again to retry", because asking again can help.
- A developer sees "search error: the service is down at NCBI" on the search's result, not "search: 0 id(s)", and the deploy log carries one warning per outage response, by database.
- What counts as confirmed did not change. A lost search still marks the answer "not yet confirmed".

## What changed

Behaviour 1, save every "not yet confirmed" answer:

- `feedback/capture.py`: `ask` joins `answer` and `flag` in the saved outcomes, and the comment states the true premise (spec Section 8.3.3; a clarifying question ends `refuse`).
- `tests/.../feedback/test_capture_saved_answer.py`: the parametrized test that pinned `ask` as a clarifying question now covers a refusal and a clarifying question, both `refuse`. Two new arms: an `ask` answer is stored with its trust line and its note, and a guest `ask` answer still stores nothing.

Behaviour 2, say what happened:

- `tools/ncbi_transport.py`: a fixed set `FAILURE_KINDS` (`service_down`, `rate_limited`, `timed_out`, `other`), `failure_kind_for_exception`, `failure_kind_for_status`, and `ClassificationResult.failure_kind`, set on an `ERROR` body.
- `tools/ncbi_efetch_schemas.py`: `NcbiEfetchOutput.failure_kind`, optional, the same four values.
- `tools/ncbi_eutils_actions.py`: every classified error carries its kind.
- `core/graph.py`, in four places:
  - A failed `ncbi_efetch` call's summary reads `<action> error: <our words>`, for example "search error: the service is down at NCBI".
  - `failed_searches` entries gain `kind` and `source`, the database the call asked.
  - The three timeout paths carry `timed_out`.
  - The note comes from `_build_failed_search_note`.

Behaviour 3, log the outage:

- `ncbi_transport._error_body_result` logs one warning per `ERROR` body, naming the database and the kind. It never sees the URL or the key, never logs NCBI's text, and logs a database value only when it looks like a database name.

## The reopen paths

Confirmed by reading, not by a test:

- History, `feedback/history.py`: `list_history` computes `has_saved_answer` as `answer_markdown IS NOT NULL`, with no filter on the outcome, and `get_saved_answer` returns `trust_signal` and `answer_trust_line` as stored.
- The web, `GET /v1/history/{trace_id}/answer` in `adapters/web_sse/app.py`: passes `trust_signal` (a string of up to 20 characters) and `trust_line` through.
- MCP, `reopen_past_answer` in `adapters/mcp/server.py`: the same, into `ReopenedAnswerOutput`.
- The saved-answer screen, `SavedAnswerScreen.tsx`: shows the stored trust line, with a check mark only when the line starts "Confirmed", so "Based on N sources, not yet confirmed" shows without one. No frontend change is needed.
- An `ask` outcome always has a grounded claim (an empty claim list aggregates to `refuse`), so `answer_trust_line` always gives it a line.

Confirmed by test: capture stores the `ask` answer, its trust line and its note block (`test_capture_saved_answer.py`).

## Not run here

The main checkout's Python was refused by the worktree guard, and a worktree venv's pytest run was refused by the auto mode classifier. Per the lead, nothing else was tried. The lead runs every step below.

Red, then green: put develop's source back under the new tests, then restore it.

```bash
git checkout 749d42df -- src/system_03_search_agent
./venv/bin/python -m pytest -q tests/system_03_search_agent/feedback/test_capture_saved_answer.py tests/system_03_search_agent/core/test_write_failed_search.py tests/system_03_search_agent/core/test_breadth_wiring.py tests/system_03_search_agent/tools/test_ncbi_transport.py tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py tests/system_03_search_agent/tools/test_ncbi_efetch_schemas.py
git checkout HEAD -- src/system_03_search_agent
```

Mutations, one at a time, each reverted with `git checkout HEAD -- <file>`:

| Property broken | Edit | Tests expected red |
|-----------------|------|--------------------|
| `ask` dropped from the saved set | `capture.py`: `_SAVEABLE_OUTCOMES = ("answer", "flag")` | `test_a_not_yet_confirmed_answer_is_stored_with_its_trust_line_and_its_notes` |
| The down kind mapped to the generic one, at the tool | `ncbi_transport.py`: `_SERVICE_DOWN_MARKERS = ()` | `test_an_eutils_error_body_saying_the_search_is_unavailable_is_service_down`, `test_the_outage_body_is_a_service_down_search`, both log arms |
| The down kind mapped to the generic one, at the answer | `graph.py`: `"kind": "other"` in `failed_searches` | `test_a_search_down_at_ncbi_says_so_in_our_words_and_says_try_later` |
| The note says ask again during an outage | `graph.py`: `sentences.append("Ask again to retry.")` | the outage arms in `test_write_failed_search.py` and the end to end arm |

Gates, each on its own exit code: `./venv/bin/ruff check`, `./venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github`, the unit suite as `.github/gates/gate04_unit_suite.sh` runs it, and `./venv/bin/python tracker/check_doc_drift.py --check`. The zero-retrieval refusal and cite-or-refuse tests sit in that suite, and no refusal wording changed.

## Judgement calls and open items

- Not every `ERROR` body is an outage. The same "Search Backend failed" prefix opens "Empty Term in the request". So `service_down` needs "unavailable" or "cannot connect" in the body; any other `ERROR` is `other` and keeps the old note. A new outage wording therefore costs the old note, never a false "it is down".
- A 5xx after the transport's retry stays `other`, and a refused connection stays `other`: neither is NCBI saying it is down.
- Open, not in this card's brief: the refusal (`synthesis/refuse.py`, `FAILED_SEARCH_MESSAGE`) still says "Ask again to retry" when every search failed, so a topic question during the outage still invites an immediate retry. Recommended as a follow-up card, using the same `kind`.
- Open: `feedback/capture.py`'s `_hard_fails_for` excludes `ask` from the uncited-claim check on the same false premise, pinned by `test_capture.py`'s `test_an_ask_with_no_citations_is_not_a_hard_fail`. Unchanged here, since it moves a stored grading column, not what is saved.
- Open: `ncbi_dbsnp` and `ncbi_coordinate_overlap` call the classifier without a database, so their warnings log `unspecified`. Outside the fence.
- The golden consistency run is the lead's, after PubMed recovers.

## Test round

The lead's tester took the card over because nothing above had been run. It worked in an ordinary worktree on `fix/card63-tested`, starting at `e36fa0ff`, with the main checkout's interpreter, `ruff` and `isort`. No guard refused anything. No question went to develop or production, and the golden consistency run is still the lead's, after PubMed recovers.

What a person notices from this round, beyond the builder's list:

- When every search failed and one of them was down at NCBI, the refusal now reads "A search I needed is down at NCBI right now, so I could not find grounded evidence this time. Try again later, or try NCBI's cross-database search:" with the same NCBI link after it. It used to say "Ask again to retry".
- A timeout, a rate limit or any other failure keeps "Ask again to retry", because asking again can help.

### Commits in this round

- `ecbf15ba` fix(write): parenthesise the outage note's joined sentences for ruff.
- `cf156daa` fix(write): a refusal during an NCBI outage says try again later.
- The docs commit that adds this section.

### Red, then green

Develop's source was put back with `git checkout 749d42df -- src/system_03_search_agent`, the report's six test files were run, the source was restored with `git checkout HEAD -- src/system_03_search_agent`, and `git status --short` printed nothing.

Red, exit 1:

```text
FAILED tests/system_03_search_agent/feedback/test_capture_saved_answer.py::test_a_not_yet_confirmed_answer_is_stored_with_its_trust_line_and_its_notes
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_an_answer_that_lost_a_search_to_an_outage_says_try_later_not_ask_again
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_the_outage_note_names_each_database_that_is_down_once
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_the_outage_note_says_when_another_search_also_failed
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_an_outage_on_a_database_the_note_cannot_name_is_still_disclosed
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_a_failed_search_recorded_before_card_63_keeps_the_original_note
FAILED tests/system_03_search_agent/core/test_breadth_wiring.py::test_a_search_down_at_ncbi_says_so_in_our_words_and_says_try_later
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_an_eutils_error_body_saying_the_search_is_unavailable_is_service_down
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_an_eutils_error_body_that_is_not_an_outage_is_other[{"esearchresult": {"ERROR": "Search Backend failed: ... Empty Term in the request", "count": "0"}}]
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_an_eutils_error_body_that_is_not_an_outage_is_other[{"esearchresult": {"ERROR": "Invalid db name specified: notadatabase"}}]
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_an_eutils_error_body_that_is_not_an_outage_is_other[{"linksets":[],"ERROR":"Invalid db name specified: notadatabase"}]
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_a_success_or_an_empty_body_carries_no_failure_kind[{"esearchresult": {"count": "1", "idlist": ["7157"]}}]
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_a_success_or_an_empty_body_carries_no_failure_kind[{"esearchresult": {"count": "0", "idlist": []}}]
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_an_error_body_is_logged_at_warning_with_the_database_and_kind_only
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_a_success_body_logs_no_error_body_warning
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_a_database_value_that_is_not_a_database_name_is_never_logged
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_the_failure_kind_of_a_transport_error_and_a_status
FAILED tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py::TestSearch::test_error_body_under_http_200_is_error
FAILED tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py::TestSearch::test_the_outage_body_is_a_service_down_search
FAILED tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py::TestSearch::test_the_outage_is_logged_by_database
FAILED tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py::TestSearch::test_a_rate_limited_search_says_rate_limited
FAILED tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py::TestSearch::test_a_timed_out_search_says_timed_out
FAILED tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py::TestSearch::test_a_successful_search_carries_no_failure_kind
FAILED tests/system_03_search_agent/tools/test_ncbi_efetch_schemas.py::test_output_failure_kind_defaults_to_none_and_takes_only_the_fixed_set
24 failed, 345 passed in 6.42s
```

Green, exit 0:

```text
369 passed in 7.53s
```

The 345 that pass on develop's source are the files' older tests plus the builder's populate twins, which pass on both sides by design: a refusal and a clarifying question store nothing, a guest stores nothing, and a timeout, a rate limit or any other failure keeps the original note.

### Mutations

Each mutation was one exact replacement that had to match once. The six files were run, the file was restored with `git checkout HEAD -- <file>`, and `git status --short` printed nothing after every one. Every run exited 1.

Mutation 1, `ask` dropped from the saved set, `capture.py`: `_SAVEABLE_OUTCOMES = ("answer", "flag")`.

```text
FAILED tests/system_03_search_agent/feedback/test_capture_saved_answer.py::test_a_not_yet_confirmed_answer_is_stored_with_its_trust_line_and_its_notes
1 failed, 368 passed in 7.13s
```

Mutation 2, the down kind mapped to the generic one at the tool, `ncbi_transport.py`: `_SERVICE_DOWN_MARKERS: Final[tuple[str, ...]] = ()`.

```text
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_an_eutils_error_body_saying_the_search_is_unavailable_is_service_down
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_an_error_body_is_logged_at_warning_with_the_database_and_kind_only
FAILED tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py::TestSearch::test_the_outage_body_is_a_service_down_search
FAILED tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py::TestSearch::test_the_outage_is_logged_by_database
4 failed, 365 passed in 7.01s
```

Mutation 3, the down kind mapped to the generic one at the answer, `graph.py`: `"kind": "other",` in `failed_searches`.

```text
FAILED tests/system_03_search_agent/core/test_breadth_wiring.py::test_a_search_down_at_ncbi_says_so_in_our_words_and_says_try_later
1 failed, 368 passed in 5.23s
```

Mutation 4, the note says ask again during an outage, `graph.py`: `sentences.append("Ask again to retry.")`.

```text
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_an_answer_that_lost_a_search_to_an_outage_says_try_later_not_ask_again
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_the_outage_note_names_each_database_that_is_down_once
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_the_outage_note_says_when_another_search_also_failed
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_an_outage_on_a_database_the_note_cannot_name_is_still_disclosed
FAILED tests/system_03_search_agent/core/test_breadth_wiring.py::test_a_search_down_at_ncbi_says_so_in_our_words_and_says_try_later
5 failed, 364 passed in 4.60s
```

Every mutation went red on exactly the tests the table above named, and on nothing else.

### Gates

Each gate was run on its own and judged by its own exit code, with the venv's `bin` first on `PATH` for the unit suite.

| Gate | On the builder's code, `e36fa0ff` | On the final code, `cf156daa` |
|------|-----------------------------------|-------------------------------|
| Unit suite, `bash .github/gates/gate04_unit_suite.sh` | `6448 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 327.92s (0:05:27)`, exit 0 | `6456 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 340.20s (0:05:40)`, exit 0 |
| `ruff check` | 3 errors, all ISC004 in `_build_failed_search_note`, exit 1 | `All checks passed!`, exit 0 |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | `Skipped 2 files`, exit 0 | `Skipped 2 files`, exit 0 |
| `python3 tracker/check_doc_drift.py --check` | `ok: 2 facts computed \| 0 could not be computed \| 0 stale \| 0 structural`, exit 0 | `ok: 2 facts computed \| 0 could not be computed \| 0 stale \| 0 structural`, exit 0 |

The final suite passes 8 more tests than the first: the extension's eight new arms.

The ruff failure, as ruff printed it the first time:

```text
ISC004 Unparenthesized implicit string concatenation in collection
    --> src/system_03_search_agent/core/graph.py:9208:13
ISC004 Unparenthesized implicit string concatenation in collection
    --> src/system_03_search_agent/core/graph.py:9215:13
ISC004 Unparenthesized implicit string concatenation in collection
    --> src/system_03_search_agent/core/graph.py:9220:13
Found 3 errors.
No fixes available (3 hidden fixes can be enabled with the `--unsafe-fixes` option).
```

### What was fixed, and why

- The ruff gate, `ecbf15ba`. The three sentences in `_build_failed_search_note` were implicit string concatenations sitting bare inside a list, the shape ruff flags because a missing comma there silently joins two items. Each is now wrapped in parentheses. The words a person reads did not change: `test_write_failed_search.py` and `test_breadth_wiring.py` gave `40 passed in 8.26s`, exit 0, after the fix.
- Nothing else failed. Every test, mutation and other gate passed on the builder's code as written.

### The extension: the refusal during an outage

The builder's first open item. A topic question searches PubMed and nothing else, so during the outage it refused, and the refusal said "Ask again to retry", which sent the person straight back into the failure.

What changed, in `cf156daa`:

- `synthesis/refuse.py`: `SEARCH_DOWN_MESSAGE`, and `refusal_message_for` returns it when any failed search carries `kind == "service_down"`, the typed value the act step records. It never reads the `reason` text, and every word is ours.
- A question the product could not read still outranks it. A timeout, a rate limit, any other failure, and a mapping recorded without a `kind` keep `FAILED_SEARCH_MESSAGE`.
- The NCBI fallback link after it is unchanged, and so is what counts as confirmed.

Two calls made from the user's chair:

- "Any" search down, not "all": the note under an answer that still stands already works this way, and asking again at once cannot help while one search is down.
- The refusal does not name the database. It stays true when more than one search is down, and naming one would mean moving the note's name table out of `core/graph.py`.

Tests, each paired with a twin that keeps today's wording, so none can pass on a constant:

- `test_write_failed_search.py`: the chooser (down, down beside a timeout, a no-entity reason still outranking it), its twins for `timed_out`, `rate_limited` and `other`, a pin that `SERVICE_DOWN_KIND` is one of `ncbi_transport.FAILURE_KINDS`, and `write_node`'s refusal with its token text, trust signal and fallback link.
- `test_topic_search.py`: one run end to end through the real loop, whose PubMed search answers with NCBI's outage text. It refuses with the new wording, and "SOLR", "temporarily unavailable" and "Search Backend" appear nowhere in the stream. Its twin fails the same search as a timeout and keeps today's wording.

Green on the new source, the two files, exit 0:

```text
75 passed in 7.38s
```

Red with `refuse.py` put back to its committed version, exit 2. This red only proves the tests need the new names, since they import them:

```text
_ ERROR collecting tests/system_03_search_agent/core/test_write_failed_search.py _
ImportError while importing test module '<repo-root>/tests/system_03_search_agent/core/test_write_failed_search.py'.
E   ImportError: cannot import name 'SEARCH_DOWN_MESSAGE' from 'system_03_search_agent.synthesis.refuse' (<repo-root>/src/system_03_search_agent/synthesis/refuse.py)
1 error in 5.86s
```

Red with the constants kept and only the two chooser lines deleted, the behavioural proof, exit 1:

```text
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_the_refusal_chooser_says_try_later_when_ncbi_said_a_search_is_down
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_a_refusal_during_an_outage_says_try_later_not_ask_again
FAILED tests/system_03_search_agent/core/test_topic_search.py::test_a_topic_search_down_at_ncbi_refuses_with_try_later
3 failed, 72 passed in 5.75s
```

The file was restored byte for byte after each red, which `cmp` confirmed.

The zero-retrieval refusal and cite-or-refuse tests, run by name after the change, exit 0: `synthesis/test_required_paths.py` whole, `test_graph.py::test_done_event_trust_outcome_is_refuse_when_the_tool_call_errors`, `adapters/cli/test_render.py` whole, and `test_write_grounding_premise.py::test_zero_retrieval_refuses_with_a_working_fallback_link`.

```text
88 passed, 1 skipped in 13.10s
```

The one skip is that last premise test, which needs the live graph and a real model key. The unit suite skips it too. Its offline twins, `TestZeroRetrievalRefusal`'s eight arms and the CLI's zero-retrieval arm, passed.

### Left alone, as briefed

- `feedback/capture.py`'s `_hard_fails_for` still excludes `ask` from the uncited-claim check. It fills a grading column, not what is saved.
- `ncbi_dbsnp.py` and `ncbi_coordinate_overlap.py` still call `classify_eutils_response` without a database, so their outage warnings log `unspecified`.
- The comment above the refusal in `core/graph.py`'s `_write_answer` still says a failed search "invites a retry". That is now true of every failure except an outage. It sits outside this round's fence, so it was not edited.
- Not run: the golden consistency run, and the live premise gate named above.

## Fix round, 2026-09-29

One fix round after the judge (PASS with three should-fix gaps) and the adversary (FAIL on F-63-A01). Nothing was committed, staged or stashed. Every red below breaks ONE property, then the file is restored byte for byte from a copy (confirmed with `cmp`) or with `git checkout -- <file>` for a file not otherwise edited.

### F-63-A01 (blocking): the outage note asserted an absence

- What changed: `_build_failed_search_note` in `core/graph.py` now decides its wording by category, not by which step failed. It never says "has no" and never names a step. Docstring and the card 63 comments updated so none still claims "has no X from it" or "search is down".
- New wording, exactly as briefed:
  - One database: "PubMed is down at NCBI right now, so this answer may be missing papers from it."
  - Several: "PubMed and ClinVar are down at NCBI right now, so this answer may be missing sources from them."
  - Any unnamed: "Some of NCBI's databases are down right now, so this answer may be missing sources from them."
  - Unchanged: the "Another background search did not finish..." sentence and its condition, "Try again later.", and `FAILED_SEARCH_NOTE` for no-outage cases.
- New test, the regression: `test_breadth_wiring.py::test_an_outage_after_a_successful_search_never_says_the_answer_has_none`, two ids: `pubmed_fetch_down` and `clinvar_summary_down`. Through the real loop with the file's fakes, the search succeeds (`search: 3 id(s)`), then the fetch or summary fails with `service_down`. It asserts the streamed notes and the saved markdown (`answer_markdown_from`) never contain "has no ", "search is down" or "searches are down", do contain the exact new note, and still show the records (PubMed source URL and `PMID:30000003`, or the `## Clinvar records found` table). `_ToolSpy` gained a `failing={(action, db): kind}` option to fail one step.
- Changed tests, wording only, no assertion weakened: `test_write_failed_search.py` (note text, two databases, another-search sentence, unnamed sentence), `test_breadth_wiring.py` (the end to end outage test), `test_capture_saved_answer.py` (`_DOWN_NOTE` fixture), plus two docstrings and one comment in `test_ncbi_eutils_actions.py` and `test_topic_search.py`.
- Red (old single database sentence put back in `graph.py`), exit nonzero:

```text
FAILED tests/system_03_search_agent/core/test_breadth_wiring.py::test_a_search_down_at_ncbi_says_so_in_our_words_and_says_try_later
FAILED tests/system_03_search_agent/core/test_breadth_wiring.py::test_an_outage_after_a_successful_search_never_says_the_answer_has_none[pubmed_fetch_down]
FAILED tests/system_03_search_agent/core/test_breadth_wiring.py::test_an_outage_after_a_successful_search_never_says_the_answer_has_none[clinvar_summary_down]
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_an_answer_that_lost_a_search_to_an_outage_says_try_later_not_ask_again
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_the_outage_note_names_each_database_that_is_down_once
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_the_outage_note_says_when_another_search_also_failed
6 failed, 48 passed in 5.97s
```

- Green: the nine named files, `527 passed in 7.26s`.

### F-63-A02 (should-fix): a failed fetch, summary or link is not a search

- What changed: the note fix above removes "search is down". `SEARCH_DOWN_MESSAGE` in `synthesis/refuse.py` is now "A source I needed is down at NCBI right now, so I could not find grounded evidence this time. Try again later, or try NCBI's cross-database search:". Name kept, comments and the `refusal_message_for` docstring updated, chooser logic untouched.
- New test: `test_write_failed_search.py::test_the_outage_refusal_says_a_source_is_down_not_a_search`, which pins the exact string.
- Red (old "A search I needed" wording put back):

```text
FAILED tests/system_03_search_agent/core/test_write_failed_search.py::test_the_outage_refusal_says_a_source_is_down_not_a_search
1 failed, 20 passed in 5.23s
```

### F-63-J01: the "cannot connect" marker had no test that could go red

- New test: `test_ncbi_transport.py::test_each_outage_marker_alone_makes_an_error_body_service_down`, ids `cannot_connect_only` and `unavailable_only`. Each phrase contains only its own marker, and the test asserts that before classifying. Added `import json` to that file.
- Red, `"cannot connect"` removed from `_SERVICE_DOWN_MARKERS`:

```text
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_each_outage_marker_alone_makes_an_error_body_service_down[cannot_connect_only]
1 failed, 182 passed in 0.80s
```

- Red, `"unavailable"` removed (the mirror, so both directions are pinned):

```text
FAILED tests/system_03_search_agent/tools/test_ncbi_transport.py::test_each_outage_marker_alone_makes_an_error_body_service_down[unavailable_only]
1 failed, 83 passed in 0.56s
```

- Green: `84 passed in 0.63s` for `test_ncbi_transport.py`.

### F-63-J02: the failed fetch, summary and link branch was unpinned

- New tests in `test_breadth_wiring.py`, beside the search-branch arm:
  - `test_a_failed_fetch_summary_or_link_names_the_failure_and_carries_its_kind`, three ids (fetch, summary, link): calls `_execute_planned_call` directly with a minimal harness. Asserts summary `"<action> error: the service is down at NCBI"`, `failure_kind == "service_down"`, `failure_source == db`, and no NCBI text.
  - `test_a_fetch_that_succeeds_keeps_its_record_count_and_records_no_failure`: the populate check, same call answering `ok`.
- Red a (branch summary reverted), red b (`failure_kind=None`) and red c (`failure_source` dropped), one result line each:

```text
5 failed, 28 passed in 5.98s
5 failed, 28 passed in 6.02s
5 failed, 28 passed in 6.00s
```

  Each run failed the three direct arms plus the two A01 regression arms.

### F-63-J03: the ncbi_efetch timeout kind was unobserved

- New test: `test_breadth_wiring.py::test_an_ncbi_efetch_timeout_records_the_timed_out_kind`. Through the real loop, the PubMed search hangs past a shortened `_NCBI_EFETCH_ACT_TIMEOUT_SECONDS` (0.2). It asserts exactly one `timed_out` entry from `ncbi_efetch`, no `other`, and that the note stays `FAILED_SEARCH_NOTE`.
- Red (`failure_kind="other"` on that timeout path):

```text
FAILED tests/system_03_search_agent/core/test_breadth_wiring.py::test_an_ncbi_efetch_timeout_records_the_timed_out_kind
1 failed, 32 passed in 5.82s
```

### Frontend check (item 8)

- `HIDDEN_NOTE_PATTERNS` in `frontend/src/components/screens/AnswerScreen.tsx` has two patterns, both anchored on "Note: ". `SYSTEM_NOTE_PREFIXES` in `hooks/useRunView.ts` applies only to a token with no `kind`, and every listed prefix starts "Note:" or is the medical disclaimer.
- The new notes start "PubMed is down..." or "Some of NCBI's databases...", so they match none. The backend types them `kind: "note"`, which renders as an inline muted paragraph. `savedAnswerMarkdown.tsx` renders it as a plain paragraph.
- No frontend file mentions the old or new wording. Result: neither hidden nor mis-styled, so no frontend change.

### Gates

- `venv/bin/ruff check`: `All checks passed!`, exit 0. The first run failed ISC004 on three of my new sentences, fixed by parenthesising them, then re-run.
- `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github`: `Skipped 2 files`, exit 0.
- The nine named files (seven card files, `synthesis/test_required_paths.py`, `adapters/cli/test_render.py`): `527 passed in 7.26s`. The whole unit suite was not run, as briefed.

### What I did not do

- F-63-A03, F-63-A04 and F-63-J04, as briefed.
- `PROGRESS.md` still carries the old note wording in prose. It is a checkpoint document, so I left it for the lead.
- The remaining "search is down" and "has no " strings in `test_write_failed_search.py` and `test_breadth_wiring.py` are negative assertions that the old wording is absent.
- No commit, stage, stash or push. A backup file from the first red run was moved to the scratchpad, since a hook blocks file deletion from the shell.
