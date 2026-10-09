# Card 54 fix round: fresh verifier report

Verifier of the fix round on `fix/card54-saved-citations` at d6a8e94b (pull request #202), diff `36c7d5d8..HEAD`. Findings are appended as they are established; the verdict comes last.

## Findings

### VF-54-01: the new line fires on a fresh answer whose text holds a bracketed number that is not a citation marker, and then states a false history

- Severity: minor (unsure on frequency; certain on behaviour)
- Regression status: new in this fix round (the web reply and screen line did not exist on develop). Inside a fix made during this phase.
- What: `_markers_without_a_citation` (`src/system_03_search_agent/adapters/web_sse/app.py`, the helper added after `get_v1_history_answer`) counts every match of `_ANSWER_MARKER` (`\[(\d{1,3})\]`, `adapters/mcp/server.py` line 1540) anywhere in `answer_markdown`, with no notion of code spans, table cells holding record data, or biomedical notation. Any such number above the highest stored `display_index` makes `citations_omitted` 1 or more, and the screen then prints `omittedSourcesLine` (`frontend/src/components/screens/SavedAnswerScreen.tsx` lines 104 to 109), which asserts the answer "was saved when only its first N sources were kept". That sentence is about the old 50 ceiling; nothing checks that the row predates the fix.
- Reproduction (scratch probe calling the real helper and the real MCP `_reopened_citations`, 10 stored citations numbered 1 to 10):
  - "HTT expansion CAG[40] or more causes HD [1]." gives rest=1, mcp=1.
  - "NM_002111.8:c.54_116[38] [2]" (HGVS repeat notation) gives rest=1, mcp=1.
  - "use `arr[12]` here [1]" (code span) gives rest=1, mcp=1.
  - "[0] [1]" gives rest=1, mcp=1.
  - The screen would then read "This answer was saved when only its first 10 sources were kept, so markers above [10] have no source listed." on an answer saved today that lost nothing.
- Why it matters: a confident wrong statement about the person's own saved answer, on exactly the variant and repeat-expansion questions where HGVS repeat brackets appear. Table cells come from record data (`feedback/capture.py` `_cell`, which does not escape brackets), not from grounded text, so the grounding pass does not filter them. I did not find a live saved answer carrying such text; frequency is unmeasured.
- NOT FIXED

### VF-54-02: when the missing marker sits below the highest kept number, the line names the wrong cause and the wrong range

- Severity: minor
- Regression status: new in this fix round. Inside a fix made during this phase.
- What: the screen line takes N as the highest stored `display_index` (`SavedAnswerScreen.tsx` line 105, `reduce(... Math.max ...)`) and never reads which markers are missing or how many. A gap below N (marker [7] with no stored citation, citations 1 to 6 and 8 to 10 kept) yields `citations_omitted` 1 and the line "This answer was saved when only its first 10 sources were kept, so markers above [10] have no source listed." Both clauses are false: nothing above [10] exists and [7] is the one with no source.
- How a gap arises on a fresh answer: `core/graph.py` lines 10711 to 10737 number citations from `display_index_by_citation_id(grounding)` and then skip any Layer 2 or Layer 3 citation whose builder returns None (F-3.4-T05-04, "skipped rather than appended"), while the claim text keeps its `[k]` marker. Read, not run live.
- Reproduction: scratch probe, text "[1] [2] ... [10]", stored citations 1 to 10 without 7: rest=1, mcp=1. Feeding that reply to the screen prints the sentence above (the line's text depends only on the highest kept index; see line 107).
- Why it matters: the reader is told to distrust markers above [10] (there are none) and is not told [7] is the one with nothing behind it. A wrong pointer is worse than no line for the one marker that matters.
- NOT FIXED

### VF-54-03: web and MCP disagree on a stored entry that is a dict but not a valid citation, and the web count can say 0 while the screen shows no source

- Severity: minor
- Regression status: new in this fix round (the web count is new; its docstring claims "so web and MCP agree").
- What: `_markers_without_a_citation` treats any dict with an integer `display_index` as stored. MCP's `_reopened_citations` (`adapters/mcp/server.py` lines 1544 to 1578) validates each entry as `CitationPayload` and counts an invalid one as omitted. The client parser `toHistoryAnswerCitation` (`frontend/src/lib/api.ts` lines 540 to 548) drops an entry with no string `source` or `source_url`. So an entry `{"display_index": 2, ...junk}` gives web 0, MCP 1, and the screen shows no source for [2] and no line.
- Reproduction: scratch probe, text "[1] [2]", stored `[valid citation 1, {"display_index": 2, "junk": True}]`: rest=0, mcp=1. Also `display_index: True` counts as stored on web (`isinstance(True, int)`), excluded on MCP; both return 0 there only because MCP's validation coerces nothing.
- Also noted: the web count compares markers against every stored dict, while the reply returns only `citations[:MAX_CITATIONS_PER_ANSWER]` (`app.py`, `get_v1_history_answer`). A row holding more than 100 entries would report 0 for markers whose citations were cut from the reply. Capture caps at 100, so I believe this is unreachable today.
- Why it matters: low; corrupted rows are rare. It does falsify the stated "web and MCP agree".
- NOT FIXED

### VF-54-04: a corrected comment introduces a new inaccuracy about the MCP bound

- Severity: minor (comment only)
- Regression status: new in this fix round (commit d6a8e94b).
- What: `src/system_03_search_agent/adapters/web_sse/app.py` lines 256 to 258 now say the export cap "matches the MCP surface's citation array bound (`MAX_CITATIONS_PER_ANSWER`, 100 since card 54 ...)". The MCP surface's bound is its own constant, `_MAX_CITATIONS = 100` at `adapters/mcp/server.py` line 196, raised from 50 by T-8.10-05 under the owner's decision of 2026-09-26 (server.py lines 176 to 180), not by card 54 and not via `MAX_CITATIONS_PER_ANSWER`. The two numbers agree by coincidence; nothing ties them, so a future change to one will leave this comment asserting a link that does not exist.
- Also: line 1890 of the same file runs to about 110 characters against the configured `line-length = 100`; `ruff check` passes (E501 is not selected), so this is cosmetic only. Pre-existing and outside this round: `tests/system_03_search_agent/adapters/graphql/test_types.py` line 295 still says "the 50-citation cap", and `adapters/mcp/server.py` line 170 still says "`citations` maxItems 50" (fix.md names this one as left open).
- Reproduction: `git grep -n "^_MAX_CITATIONS =" src/system_03_search_agent/adapters/mcp/server.py` gives `196:_MAX_CITATIONS = 100`; `git grep -n MAX_CITATIONS_PER_ANSWER src/system_03_search_agent/adapters/mcp/server.py` gives only a docstring mention at line 1555.
- Why it matters: the comments are what the last two rounds were asked to make true; this one is newly untrue.
- NOT FIXED

### VF-54-05: "its first N sources" counts citation numbers, not the source rows the reader sees

- Severity: minor (wording; unsure whether the owner minds)
- Regression status: new in this fix round.
- What: N in the line is the highest `display_index`, but the Sources list above it is grouped "one row per record page" (`savedSourceRows`, `SavedAnswerScreen.tsx` around line 111). An old answer keeping citations 1 to 50 that share record pages shows fewer than 50 rows under a line that says "its first 50 sources were kept". The fix round's own screen test shows the shape: one stored citation numbered 50 renders one source row under "only its first 50 sources were kept" (`SavedAnswerScreen.card102.test.tsx` lines 139 and 158).
- Also: for a fresh answer that cited more than 100 records (rest=20, mcp=20 in my probe for 120 markers, 100 stored), the past tense "was saved when only its first 100 sources were kept" reads as if a limit no longer applies; it still does.
- Why it matters: a reader counting rows against the sentence finds them disagreeing. Calm and blameless otherwise: the line never mentions the reader or the connection, and it appears only when the count is above 0 (mutating the condition to `>= 0` turns the screen test red).
- NOT FIXED

### VF-54-06: the screen test named for "the backend sends no count" never sends a reply without the field

- Severity: minor (test gap)
- Regression status: new in this fix round.
- What: `SavedAnswerScreen.card102.test.tsx` "shows no line when nothing is omitted or the backend sends no count" calls only `reopenWithOmitted(0)`; the `undefined` branch of its helper is never exercised. A parser that defaulted an absent field to a positive number (while still mapping 0 to 0) would pass every test. The develop-era fixtures in `api.fetchHistoryAnswer.test.ts` lack the field but assert nothing about it.
- Reproduction: read the test (lines 163 to 166). My mutation of the shared default (`: 0` to `: 1`) was caught only because 0 takes the same branch as absent.
- Why it matters: older servers and cached replies send no field; the no-line promise for them is untested.
- NOT FIXED

## Checks against the brief

| Brief item | Result | How |
|---|---|---|
| 1. The count | Right for the main case (50 stored, markers to [61] gives 11). Agrees with MCP on 17 of 18 probe shapes. Repeated markers count once; "[12a]", "[1,2]", "[1-3]", "[1000]" are not counted (the screen does not treat them as markers either, `useRunView.ts` line 778 uses the same `\[(\d{1,3})\]`); no markers gives 0; out-of-order kept numbers give 0. Can false-alarm on a fresh answer (VF-54-01, VF-54-02) and say a wrong N (VF-54-02). Web and MCP differ on an invalid dict entry (VF-54-03). | Own probe calling the real web helper and the real MCP `_reopened_citations` with valid `CitationPayload` dicts |
| 2. The line | Calm, never blames the reader or the connection, shown only when the count is above 0. Wording issues in VF-54-02 and VF-54-05. | Read; condition mutated to `>= 0`, screen test went red |
| 3. Order tests | All three go red under reversal. Capture: `reversed(events)` red, keep-last-100 red. Saved reply: `citations[::-1]` red. Export: `reversed(entry.events)` red. Count forced to 0: red. Each mutation reverted at once; `git status` shows no tracked change. | Own mutations |
| 4. Stale comments | The three named are corrected. One new inaccuracy (VF-54-04). | Read, `git grep` |
| 5. Clients | Additive field. The web parser is not strict (`fetchHistoryAnswer` checks only five keys and ignores extras); MCP builds its own `ReopenedAnswerOutput` from the stored row, not from the REST reply; no CLI module reads `/v1/history/{trace_id}/answer`; no frontend or e2e test asserts the whole reply object. Nothing rejects it. | `git grep` across `src`, `frontend/src`, `frontend/e2e`; read the parser |

## Test runs

| Command | Result | Exit code |
|---|---|---|
| `python3 -m pytest tests/system_03_search_agent/feedback tests/system_03_search_agent/adapters -q -p no:cacheprovider` | 1020 passed, 2 warnings | 0 |
| `npx vitest run src/components/screens/SavedAnswerScreen.card102.test.tsx src/lib/api.fetchHistoryAnswer.test.ts` | 2 files, 13 passed | 0 |
| `npm run build` | built, chunk-size warning only | 0 |
| `ruff check` (whole repository) | All checks passed | 0 |

## Verified by my own probes versus only read

- Verified by running: the count on 18 marker shapes against both web and MCP code; all order and count mutations; the screen line's show and hide condition; that `_cell` keeps "c.54_116[38]" intact in a table cell; the test runs above.
- Only read: that a Layer 2 or Layer 3 citation skipped in `core/graph.py` leaves its `[k]` in the text (VF-54-02's live trigger); that no CLI consumes the reply; that the Sources list groups by record page (VF-54-05). I did not run a live answer or a deployed reopen.

## Verdict

MERGE WITH NAMED ITEMS

Every finding (VF-54-01 to VF-54-06) sits inside the fix made during this phase's fix round, which is this review loop's stop condition: escalate to the product owner rather than run another round. None blocks the card's goal: an answer saved before the fix now says its later markers have no source, and every order and ceiling claim holds under mutation. The named items are VF-54-01 and VF-54-02, where in narrow cases (a bracketed number in record data, or a skipped citation below the top number) the new line tells a person something false about their saved answer.

Worse than develop: no (for the common path; in the narrow cases of VF-54-01 and VF-54-02 develop showed nothing and this branch shows a false sentence)
