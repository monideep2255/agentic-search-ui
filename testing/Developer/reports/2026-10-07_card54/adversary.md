# Card 54 adversary report

Adversary round for card 54 (saved answers and the citations export keep up to 100 citations), branch `fix/card54-saved-citations`, pull request #202. Findings are appended as they are established.

## Findings

### A-54-01: Three code comments and the spec still state the old 50 ceiling as a live fact

- Severity: minor
- What: After the change, these sentences are false and were not touched by the diff:
  - `src/system_03_search_agent/adapters/web_sse/app.py` line 253: `_MAX_CITATIONS_PER_RUN` "matches Section 13.2's own `maxItems: 50`". The constant now equals 100.
  - `src/system_03_search_agent/adapters/web_sse/app.py` around line 1867: "Whether `_MAX_CITATIONS_PER_RUN` and Section 13.2's `maxItems: 50` should themselves move is a separate, cross-surface decision ... left open". The diff moved it.
  - `src/system_03_search_agent/adapters/graphql/types.py` lines 186 to 187: "`adapters/web_sse/app.py`'s `_MAX_CITATIONS_PER_RUN` (the REST citations export) is still 50", and line 420 "dropped at the 50-citation cap".
  - `src/system_03_search_agent/adapters/mcp/server.py` line 170: "Section 13.2's locked output_schema: `citations` maxItems 50" (this one predates card 54; MCP has used 100 since phase 8.10).
  - `requirements/Technical_specification.md` Section 13.2 output schema still reads `"maxItems": 50` for `citations`.
- Reproduction: `git grep -n "maxItems: 50\|is still 50\|50-citation cap" -- src` on `fix/card54-saved-citations` returns the lines above. `PYTHONPATH=src python3 -c "from system_03_search_agent.adapters.web_sse.app import _MAX_CITATIONS_PER_RUN; print(_MAX_CITATIONS_PER_RUN)"` prints 100.
- Why it matters: this repository's own history (F-6.0-01, phase 4.15) records comments that justify a bound by pointing at one that is not there. The next reader of the REST export trusts "matches 13.2's 50" and the spec, and a contract consumer reading Section 13.2 expects at most 50.
- Regression against develop: partly. The app.py and graphql/types.py sentences became false with this change; the MCP comment and the spec were already stale on develop.
- NOT FIXED

### A-54-02: Every long answer saved before this deploy still reopens with markers past [50] pointing at nothing, and the web reply and screen say nothing about it

- Severity: major
- What: The fix raises the bound for rows written from now on. Rows already in `interactions` hold at most 50 citations because capture cut them at write time, and nothing restores them. `GET /v1/history/{trace_id}/answer` returns those 50 with no field and no header saying entries are missing, and `SavedAnswerScreen.tsx` shows the stored trust line ("Based on 61 sources cited") above 49 rows. The MCP surface's `reopen_past_answer` already discloses the same gap through `citations_omitted` (it counts markers in `answer_markdown` with no stored entry); the REST `SavedAnswerResponse` has no equivalent. `build.md` says "Now the reopened answer lists every source the live answer showed, up to 100" without the qualifier "for answers saved after this change".
- Reproduction: probe `p2_saved.py` (kept outside the repository) seeds the real endpoint, through `httpx.ASGITransport` and a monkeypatched `get_saved_answer`, with the diagnosis's shape: 50 stored citations (gene 6927 at display_index 45 and 49), `answer_markdown` carrying markers [1] to [61], `trust_line` "Based on 61 sources cited". Observed: `200 rows 50 max_marker_in_md 61 max_index_returned 50 keys ['answer_markdown', 'asked_at', 'citations', 'depth', 'question', 'trace_id', 'trust_line', 'trust_signal'] omission_headers {} history_count_of_stored 49`. So the history rail says 49, the trust line says 61, 49 rows show, markers [51] to [61] resolve to nothing, and the reply carries no disclosure.
- Why it matters: the owner's own HNF1A reproduction is an already-saved row. Reopening it after deploy shows exactly the defect card 54 was filed for, so a retest of the card's own example reads as "not fixed", or worse a tester concludes the fix works from a fresh query while every existing history item keeps lying. A confident trust line over missing rows is the trust-signal failure the citation rule exists to prevent. Options for the owner, not for me to pick: disclose the omission on the REST reply and the screen (as MCP does), or state in the card that old rows stay short and re-running is the remedy.
- Regression against develop: no. Behaviour for old rows is unchanged; the gap is that the fix and its build note claim more than they deliver, and the screen still gives no signal.
- NOT FIXED

### A-54-03: Above 100, capture and the saved-answer reply cut silently, and the history count then disagrees with the rows shown

- Severity: minor (unsure on reachability)
- What: `assemble_interaction` keeps the first 100 `citation` events and stores no trace that more existed. `get_v1_history_answer` slices `citations[:MAX_CITATIONS_PER_ANSWER]` with no disclosure field or header. `feedback/history.py`'s `_citation_count` counts the whole stored list with no cap. So a stored list longer than 100 reads one number in the history rail and shows fewer rows on reopen, and markers past [100] point at nothing with nothing on screen saying so. The REST citations export, GraphQL and MCP all disclose a cut at the same bound (`X-Citations-Export-Truncated`, `disclosures`, `citations_omitted`); capture and the saved-answer reply are the two places on this path that do not.
- Reproduction:
  - Capture, probe `p1_capture.py`, real `assemble_interaction` with 101, 150 and 200 citation events numbered 1 to N: every case printed `stored 100 first [1, 2, 3] last [99, 100] in_order True max_marker_kept 100`. The row has no field recording the cut.
  - Saved reply, probe `p2_saved.py`, a row seeded with 130 citations and markers [1] to [130]: `over 200 rows 100 max_marker_in_md 130 max_index_returned 100 ... omission_headers {} history_count_of_stored 130`.
- Why it matters: today a live run cannot emit more than 100 citations, because `write_node` numbers one citation per admitted finding and `build_synth_findings` admits at most `_MAX_FINDINGS_FOR_DISPLAY` (100). I only read that bound; I did not drive a live run past it. If the display cap is ever raised without this constant (the pin test would catch a change to `_MAX_FINDINGS_FOR_DISPLAY`'s value, but not a second citation producer), the cut returns as the silent shape card 54 was filed for, at 100 instead of 50.
- Regression against develop: no. The same silent cut existed at 50 and was reachable then; card 54 makes it unreachable in practice but keeps it undisclosed.
- NOT FIXED

### A-54-04: Flagging more than 50 sources of a long answer is refused whole, and the screen blames the connection

- Severity: minor
- What: The one citation path still bounded at 50 after this change is feedback. `FeedbackPayload.citation_flags` (`feedback/contracts.py`, `max_length=50`) and MCP's `send_answer_feedback` `citation_flags` (`adapters/mcp/server.py` line 1688, `max_length=50`) refuse a 51st flag. A live answer has shown up to 100 sources since 2026-09-20, and `FeedbackSurface.tsx` sends every flagged source in one request, so a reader who flags 51 or more loses the whole submission, rating and comment included, with the generic error "Could not send your feedback. Check your connection and try again."
- Reproduction: probe `p4_flags.py` posts to the real `POST /v1/query/{run_id}/feedback` through `httpx.ASGITransport` (run lookup and `record_feedback` stubbed). Observed: `50 flags -> 204 recorded 50`, `51 flags -> 422 {"detail":[{"type":"too_long","loc":["body","citation_flags"],"msg":"List should have at most 50 items after validation, not 51" ...`, and the same 422 for 77.
- Why it matters: the brief asked for any path that still cuts at 50. This one does not cut silently, it refuses, but the reader is told something false (their connection) and loses their rating. Flagging over half of a long answer's sources is unusual, which is why this is minor; it is the most likely moment for a reader to flag many, though: an answer whose sources are mostly wrong.
- Regression against develop: no. Unchanged by this branch; the gap sits beside the five bounds the branch moved.
- NOT FIXED

### A-54-05: The REST export drops a citation it cannot validate without any signal when the run is at or under 100

- Severity: minor (unsure on reachability)
- What: `get_v1_query_citations` skips a `citation` event whose payload fails `CitationPayload`, logs a warning, and sets `X-Citations-Export-Truncated` only when the raw event count exceeds 100. At 100 events with one bad payload, the caller gets 99 rows and no header; the missing row's marker points at nothing. GraphQL's fold discloses the same drop in `disclosures`.
- Reproduction: probe `p3_export.py` (real handler, `_get_owned_run` stubbed with plain namespace events): `100 with #7 malformed 200 rows 99 ordered True last [100] trunc_header None`. For comparison `101 with #7 malformed 200 rows 100 ... trunc_header true` and `100 worst-case 200 rows 100 ... trunc_header None bytes 188769`.
- Why it matters: today `Event` validates a citation payload against the same model at construction, so a real run should never reach this. I did not find a producer that bypasses it. Filed because raising the ceiling to 100 doubles the window in which this branch is the only signal, and the code comment calls it "one citation missing, logged", which is a log line, not a disclosure to the caller.
- Regression against develop: no.
- NOT FIXED

### A-54-06: No test pins which citations survive the ceiling or their order; storing them reversed passes every card 54 test

- Severity: minor
- What: The new ceiling tests count rows and never check which rows. In `test_capture.py` every citation the helper builds has `display_index` 1 and the same URL; the saved-answer test above the ceiling (`test_a_saved_answer_above_the_ceiling_is_still_bounded`) also builds 130 entries at `display_index` 1. So a capture that kept the last 100 citations, or stored them in reverse, is indistinguishable from the correct one.
- Reproduction: in a clean copy of `HEAD` extracted with `git archive` (outside the repository), I changed `capture.py` line 415 from `for event in events` to `for event in reversed(events)` and ran the four files this branch touched (`test_capture.py`, `test_contracts.py`, `test_saved_answer_endpoint.py`, `test_citations_export_ceiling.py`): `76 passed`. The same harness turned red for each of the branch's own bounds put back to 50 (`slice50 -> 1 failed`, `capture50 -> 1 failed`, `export50 -> 1 failed`) and for the constant moved to 150 (`const150 -> 1 failed`, the pin test), so the count checks themselves are not vacuous. The ordering and survivor checks are the missing part.
- Why it matters: the web screen sorts by `display_index` before drawing, so a reversed store would not show on screen at or under 100. Above 100 the wrong survivors would be kept: markers [1] to [20] of a 120-citation answer would point at nothing while [101] to [120] had rows. The MCP reopen and the REST saved reply return stored order unsorted. My own probe `p1_capture.py` confirms the real capture keeps display_index 1 to 100 in order today; nothing keeps it that way.
- Regression against develop: no, the gap predates the branch, but the branch's new tests were written for exactly this path and leave it open.
- NOT FIXED

### A-54-07: Another agent is mutating tracked source files in this shared worktree while reviews run, so any probe run here can be testing a mutated tree

- Severity: unsure (process, not product)
- What: During this round `git status` in the worktree showed tracked source files modified that I did not touch, cycling over time: first `src/system_03_search_agent/feedback/contracts.py`, then `src/system_03_search_agent/adapters/web_sse/app.py` with `SavedAnswerResponse.citations` set back to `max_length=50`. A `judge.md` appeared beside this report. A pytest process over the same four card 54 test files was running from the worktree at the same time. A copy of `src/` I took with `rsync` captured `capture.py` reading `_MAX_CITATIONS = 50`, a state that exists in no commit.
- Reproduction: `git diff` in the worktree at one point returned `-        default_factory=list, max_length=MAX_CITATIONS_PER_ANSWER` / `+        default_factory=list, max_length=50` in `adapters/web_sse/app.py`, with `git log` still at `ba32b96d`.
- Why it matters: a probe or test result taken from this worktree during that window says nothing about the branch. My mutation runs were redone on a clean `git archive HEAD` copy for that reason. My endpoint probes (`p1` to `p4`) ran against the worktree; their outputs (61 and 100 stored, 100 rows returned, no 500 at 100 rows) match the unmutated code and cannot have come from the mutated states seen, but the lead should know the window existed. It also means `git status` at hand-back may show changes that are not this report's.
- Regression against develop: not applicable.
- NOT FIXED

### A-54-08: The diagnosis understates the worst-case stored size by about a fifth, and the history page reads the whole column for up to 50 rows

- Severity: minor
- What: `diagnosis.md` gives "at most about 1.6 KB" per citation and "about 160 KB worst case per row" at 100. With every `CitationPayload` field at its bound, including the optional `entity_name` (256) and `population_ancestry_context` (256) the estimate leaves out, 100 citations serialise to 192,784 bytes. `list_history` selects `Interaction.citations` for each of up to `MAX_LIMIT` (50) rows only to count pages, so the worst-case history page now moves about 9.6 MB of JSONB out of the database instead of about 4.8 MB.
- Reproduction: probe `p1_capture.py` printed `worst-case 100 bytes 192784`; `InteractionRow` construction with that list measured 6.6 ms per row. Through the real saved-answer handler, the same list returned `bytes 188371` in 4.4 ms (`p2_saved.py`) and the REST export `bytes 188769` (`p3_export.py`). The history figure is arithmetic from the select, not measured against a database.
- Why it matters: the speed rule is that every answer arrives within 20 seconds and no surface gets slower. These figures are well inside that for one reopen. The history rail is the one place the doubling multiplies by 50, and only for accounts whose last 50 answers were all long. Worth a measured check on a seeded local database before someone relies on "only long answers pay it".
- Regression against develop: the doubling is a direct effect of this change; whether it is felt is unmeasured.
- NOT FIXED

## Verdict

PASS against the change as specified: an answer saved from now on keeps up to 100 citations through capture, the stored row, the saved-answer reply and the REST export, in live order, with no marker misnumbered. Not a clean pass for the card's own example: A-54-02 means the owner's HNF1A history item, saved before this deploy, still reopens with 49 rows under "Based on 61 sources cited" and no disclosure. Whether card 54 is done without disclosure for old rows is the owner's call.

No finding is a defect inside the five bounds this branch moved. A-54-01 (comments made false by this change) and A-54-06 (the new tests do not pin order or survivors) sit in this branch's own work.

Verified with my own probes, real functions, no database:

- Capture keeps display_index 1 to N in order for N up to 100, and 1 to 100 for 101, 150 and 200, with no error. The duplicate-page case (gene 6927 at 45 and 49) reads 60 pages for 61 citations in the history count (`p1_capture.py`).
- The stored row model accepts 100 worst-case citations (192,784 bytes, 6.6 ms) and refuses 101.
- The saved-answer endpoint returns 61 of 61 and 100 of 100 (worst case 188 KB, 4.4 ms). It returns 100 of 130 with no disclosure, and 50 of a legacy 50 under markers to [61] with no disclosure (`p2_saved.py`).
- The REST export returns 100 with no header at 100, sets the header above 100, and caps 5,000 events at 100 in 4 ms. It drops one malformed event at 100 without a header (`p3_export.py`).
- The feedback endpoint refuses 51 citation flags with a 422 (`p4_flags.py`).
- Mutations on a clean `git archive HEAD` copy: each of the branch's bounds put back to 50 turns a test red, and so does the constant moved to 150. Reversing capture order turns nothing red.

Only read, not probed:

- That a live run cannot emit more than 100 citations (`build_synth_findings` capped at `_MAX_FINDINGS_FOR_DISPLAY`, one citation per distinct `citation_id`).
- That the web screen's `savedSourceRows` count equals the Python page count for these inputs. The frontend is untouched and I did not run it.
- That no GraphQL, MCP or REST input accepts a citations list. I found only `CreateRunRequest` (text, session, depth) and the feedback flags.
- The history page's database cost.

Concurrency caveat: A-54-07. Another agent mutated tracked files in this worktree during the round. My mutation evidence comes from a clean copy of `HEAD`.
