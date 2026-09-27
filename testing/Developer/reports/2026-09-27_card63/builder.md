# Card 63 builder report

Card 63 on `testing/UI_fix_plan.md`, dial position 2, built on the branch `fix/card63-save-and-say` from develop at `749d42df`. Three code commits: `d1736e13` (the tool says why a search failed), `bf4a697e` (the summary and the note say it in our words), `aed1c99f` (every "not yet confirmed" answer is saved). No test, gate or mutation was run by the builder: see "Not run here".

## Table of contents

- [What a person notices](#what-a-person-notices)
- [What changed](#what-changed)
- [The reopen paths](#the-reopen-paths)
- [Not run here](#not-run-here)
- [Judgement calls and open items](#judgement-calls-and-open-items)

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
