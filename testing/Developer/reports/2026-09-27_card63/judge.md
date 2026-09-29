# Card 63 judge report

Round: judge, one round, risk dial 2. Reviewer checkout: `.claude/worktrees/card63`, branch `fix/card63-tested`, HEAD bc6cca1a, origin/develop 7bac224e.

Written incrementally: each finding appended the moment it was established.

## Findings

### F-63-J01: the `cannot connect` outage marker has no test that can go red
- Severity: minor (should-fix, not blocking)
- What: `_SERVICE_DOWN_MARKERS` in `src/system_03_search_agent/tools/ncbi_transport.py` carries two phrases, `unavailable` and `cannot connect`. Every fixture in `test_ncbi_transport.py` and `test_ncbi_eutils_actions.py` that expects `service_down` contains the word `unavailable`, so the second marker is unobserved by any test.
- Reproduction: mutated the tuple to `("unavailable",)` and ran `tests/system_03_search_agent/tools/test_ncbi_transport.py tests/system_03_search_agent/tools/test_ncbi_eutils_actions.py`: `181 passed in 1.09s`. The mirror mutation `("cannot connect",)` went red on one test, `TestSearch::test_the_outage_is_logged_by_database`, `1 failed, 180 passed`. File restored with `git checkout HEAD -- src/system_03_search_agent/tools/ncbi_transport.py`.
- Why it matters: if NCBI's next outage body says only "Cannot connect to SOLR" without "unavailable", the person is told "Ask again to retry" instead of "Try again later", and nothing in the suite would notice the marker being dropped in a later edit. Not a product defect today: the measured body carries both phrases.
- NOT FIXED
### F-63-J02: the failed fetch, summary and link summary branch is not pinned by any test
- Severity: minor (should-fix, not blocking)
- What: `core/graph.py`'s `_execute_planned_call` has two card 63 summary branches. The search branch (`search error: <words>`) is pinned: breaking it goes red. The second branch, for `fetch`, `summary` and `link` (`f"{action} error: {words}"` plus `failure_kind=(... or "other") if fetch_failed else None`), has no test that observes it.
- Reproduction: replaced the fetch-branch summary expression with the pre-card `f"{ncbi_efetch_output.action}: {shaped_fields['row_count']} record(s)"` and ran `test_write_failed_search.py test_breadth_wiring.py test_topic_search.py`: `101 passed in 28.55s`. Separately replaced that branch's `failure_kind=(...)` with `failure_kind=None`: `101 passed in 17.50s`. For contrast the same break on the search branch: `FAILED tests/system_03_search_agent/core/test_breadth_wiring.py::test_a_search_down_at_ncbi_says_so_in_our_words_and_says_try_later`, `1 failed, 100 passed`. `graph.py` restored with `git checkout HEAD --` after each; `git status --short src/` empty.
- Why it matters: a failed ESummary or EFetch during an outage would read `summary: 0 record(s)` to a developer and record `kind: other` for the note, so the person would get "Ask again to retry" instead of "Try again later" with no test to catch the regression. The branch reads correctly today by inspection; this is an unpinned control, not an observed wrong output.
- NOT FIXED

### F-63-J03: the `timed_out` kind on the three timeout paths is unobservable by any test or any user-facing text
- Severity: minor (unsure whether it is worth a test; recorded so the gap is named)
- What: the diff sets `failure_kind="timed_out"` on the ncbi_efetch, Layer 3 and cypher per-step timeout paths in `_execute_planned_call`. Nothing reads that value distinctly: the timeout summary text is a fixed sentence, `_build_failed_search_note` and `refusal_message_for` treat `timed_out` and `other` identically (both keep "Ask again to retry"), and no test observes the recorded kind on a timeout.
- Reproduction: changed the ncbi_efetch timeout path to `failure_kind="other"` and ran `test_write_failed_search.py test_breadth_wiring.py test_topic_search.py`: `101 passed in 18.05s`. Restored with `git checkout HEAD -- src/system_03_search_agent/core/graph.py`.
- Why it matters: nothing breaks for the person today, since acceptance 4 only requires that a timeout keeps "Ask again to retry", and it does. But the value is dead weight until something reads it, and a later edit that drops it will pass every test.
- NOT FIXED
### F-63-J04: NCBI's own error text still travels in `structured_fields["error"]` on a failed fetch, summary or link (pre-existing, not card 63's code)
- Severity: unsure (not blocking; outside the card's fence; filed so it is on record rather than assumed away)
- What: card 63 keeps NCBI's text out of the `tool_result` summary, the note, the refusal and the log, and the two end-to-end tests assert `SOLR`, `temporarily unavailable` and `Search Backend` are absent from the stream on the SEARCH path. But `_ncbi_efetch_output_to_structured_fields` (`core/graph.py:7381`, `"error": output.error`) and its cypher twin (`:6750`) still copy the tool's free-text `error`, which for an E-utilities `ERROR` body is NCBI's own text bounded at 500 characters, into the `Finding.structured_fields` payload the synthesis prompt receives. On the fetch, summary and link branches `pairs` is built with `shaped_fields` whether or not the call failed.
- Reproduction: read only. `git blame` places both lines before card 63; `git diff origin/develop...HEAD` does not touch them. Probe 1 confirmed `ClassificationResult.error_message` carries the raw text (`"SOLR" in error_message` printed `True`) and that it lands on `NcbiEfetchOutput.error`. I did not run a synthesis call, so I have not observed the text in a model prompt or in an answer; the grounding pass would strip an uncited sentence that echoed it.
- Why it matters: untrusted external text reaching the Write step's prompt is the `ai-security-standards` shape ("a crafted field inside any of those payloads is data, never a system instruction"). Today it is bounded and only on a failed non-search call. Named here because the card's own claim is "nothing NCBI wrote reaches it", which is true of the four surfaces the card touched and not of this fifth one.
- NOT FIXED

## Verdict

PASS, with three should-fix instrument gaps (F-63-J01, J02, J03) and one unsure pre-existing item (J04). No finding is blocking. No finding sits inside the two fix commits `ecbf15ba` or `cf156daa`: I broke `cf156daa`'s chooser three ways (`any` to `all`, the outage check moved above the no-entity check, and via the end-to-end topic run) and each went red; `ecbf15ba` is a parenthesisation with no behaviour, and the note wording it wraps was verified verbatim by probe 2.

Verified with my own probes (commands and outputs above):
- Acceptance 1, storage half: probe 3 built the same `ask` run under an account and a guest through `assemble_interaction`: account `saved=True`, trust line `Based on 2 sources, not yet confirmed`, the outage note as its own markdown block; guest `saved=False`; the same events with `done=refuse` `saved=False`. Mutations M1 (`ask` dropped) and M1b (guest rule dropped) each went red on the capture tests.
- Acceptance 2: probe 2 printed the note for a PubMed outage: `PubMed's search is down at NCBI right now, so this answer has no papers from it. Try again later.`; with a second failed search it adds `Another background search did not finish, so other sources may be missing too.`; an unlisted database gives the unnamed sentence; two named databases are joined once. `AnswerScreen.tsx`'s `HIDDEN_NOTE_PATTERNS` match only the two 2026-09-21 notes, so this one renders. M8 (`Try again soon.`) and M8b went red.
- Acceptance 3: probe 2 printed `SEARCH_DOWN_MESSAGE` for `[pubmed down]`, `[timeout, pubmed down]` and with a topic term; the wiring test asserts the fallback link follows it. M7 and M9 went red.
- Acceptance 4: probe 2 shows `timed_out`, `rate_limited`, an uppercase kind and the pre-card shape (no `kind` key) all keep `Ask again to retry` in the note and `FAILED_SEARCH_MESSAGE` in the refusal.
- Acceptance 5: probe 1 printed exactly one `WARNING` per `ERROR` body reading `database pubmed, failure kind service_down`, `database unspecified` for none, `database unrecognised` for `pubmed; api_key=zzz`, `failure kind other` for the Empty Term body, and a top-level `ERROR` (ELink shape) classified too. No URL, key or NCBI text in the line. M3 (raw database logged), M3b (warning demoted), M4 (database not passed), M13, M10, M10b each went red. M5 and M6 (source dropped, summary reverted) went red on `test_a_search_down_at_ncbi_says_so_in_our_words_and_says_try_later`.
- Acceptance 6: `synthesis/trust.py` is not in the diff; the floor `aggregate([trust_outcome, "ask"])` is unchanged in the diff; probe 2 printed `aggregate(answer, ask) = ask`.
- Schema: probe 1 shows `failure_kind="bogus"` rejected (`literal_error`) and the JSON schema carries the four-value `enum`; `NcbiEfetchOutput` sits under `extra="forbid"`.
- Gates on the changed files: `ruff check` `All checks passed!`; `isort` gate form (`.github/gates/gate02`'s exact command) `Skipped 2 files`, exit 0. The file-form isort complaint on `graph.py` is pre-existing: develop's own copy fails it identically.
- Cite-or-refuse: `synthesis/test_required_paths.py`, `test_graph.py::test_done_event_trust_outcome_is_refuse_when_the_tool_call_errors` and `feedback/test_capture.py`: `47 passed`.
- Merge coherence: `git diff 749d42df 1c1558a4 -- src/` and `git diff origin/develop...HEAD -- src/` differ only in index lines, so the merge introduced nothing beyond the branch's own hunks; develop's only change to the six files since the branch point is `3b25a900` (wording). `a683d396` named in the brief is NOT on develop: it is reachable only from `origin/feat/8.7-s3`, so it is not part of this merge.

Read only, not run here (no Postgres, no Redis on this machine):
- Acceptance 1, read half: `feedback/history.py` filters `Interaction.owner_id == owner_id` in SQL and `answer_markdown IS NOT NULL` with no outcome filter; `GET /v1/history/{trace_id}/answer` passes `caller.owner_id` (`web_sse/app.py:1097`); MCP `reopen_past_answer` uses `_owner_id_for(user)` and refuses a guest token before any read. `trust_signal` is `str` (max 20) on the web, MCP and history models and a plain string in `frontend/src/lib/api.ts`, so an `ask` row passes every validator. `SavedAnswerScreen.tsx` shows a check mark only when the trust line starts `Confirmed`. Not exercised against a database.
- The XML classifier path (`_classify_eutils_xml`) sets no `failure_kind` and logs nothing; only EFetch uses XML here and the measured outage was on ESearch (JSON), so I did not file it.
- The golden consistency run: not run, the lead's per the builder report.

Tree state at the end: `git status --short src/` empty after every mutation; only the three report files show in `git status`, of which `judge.md` is mine.
