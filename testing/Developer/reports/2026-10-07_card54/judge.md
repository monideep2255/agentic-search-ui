# Card 54 judge report

Fresh judge for pull request #202, branch `fix/card54-saved-citations`, base `origin/develop` 2182aff3. Findings are appended as they are established.

## Table of contents

- [Findings](#findings)
- [What I checked and how](#what-i-checked-and-how)
- [Verdict](#verdict)

## Findings

### J-54-01: An answer saved before this fix still reopens with 50 citations and no disclosure on the web
- Severity: major (unsure whether it is in the card's scope; it decides whether the owner's own retest passes)
- What: the fix is forward only. A row written before deploy holds at most 50 citations in `interactions.citations`, and nothing can restore the rest. The web reopened screen (`frontend/src/components/screens/SavedAnswerScreen.tsx` lines 345 to 365) renders `savedSourceRows(answer.citations)` with no count of markers that point at nothing, and the saved-answer reply (`src/system_03_search_agent/adapters/web_sse/app.py` lines 1110 to 1132) has no omitted field. MCP has one (`adapters/mcp/server.py` `_reopened_citations`, `citations_omitted`); the web does not.
- Reproduction: read only, not run against a live database. The card's own HNF1A answer (61 cited, 50 stored) will still read "Based on 61 sources cited" above 49 rows after this deploys, because the stored row is unchanged. `build.md` says "Now the reopened answer lists every source the live answer showed", which is true only for answers saved after deploy.
- Why it matters: the person who reported the card reopens the same saved answer and sees the same defect. A marker such as [55] still points at nothing with no sentence saying why. The product check needs a fresh answer, and the old rows need a disclosure, or the card should say plainly that old rows stay as they are.
- NOT FIXED

### J-54-02: The history list reads twice the citation data per page for long answers
- Severity: minor (a measured slowdown on a page every signed-in visitor loads, not a failure)
- What: `feedback/history.py` `list_history` (line 302) selects the whole `interactions.citations` JSONB column for every row on the page only to count distinct record pages (`_citation_count`, line 149). With the ceiling at 100 (`feedback/contracts.py` line 63) a page of 50 long answers reads twice as much as before. The response body is unchanged; the database read and decode are not.
- Reproduction: judge probe `probe_history_cost.py` (scratchpad, not committed), local PostgreSQL, one throwaway account, 50 rows written through the real `assemble_interaction` and `write_interaction`, each citation with a realistic 960 character `claim_text`, then `list_history(owner, limit=50)` timed 15 times. Output: `N=50 rows=50 counts={50} median_ms=100.4`; `N=100 rows=50 counts={100} median_ms=199.7`. The same probe wrote a single 100 citation row at 140,584 bytes of citation JSON (`probe_e2e.py`, "stored row citations: 100 json bytes: 140584"), against about 70 KB at the old 50.
- Why it matters: only people with many long answers pay it, and locally it is 100 ms more per history page. Over the network to the deployed database the transfer doubles too (about 7 MB per page at worst against 3.5 MB). `diagnosis.md` names this cost; it is filed so the owner sees a number, not only the sentence. Counting pages in SQL would remove it, and is outside this card.
- NOT FIXED

### J-54-03: Comments and a test docstring still say the REST export and the stored row stop at 50
- Severity: minor (documentation drift in code the next reader trusts)
- What: four places now state something false.
  - `src/system_03_search_agent/adapters/graphql/types.py` lines 186 to 187: "`adapters/web_sse/app.py`'s `_MAX_CITATIONS_PER_RUN` (the REST citations export) is still 50".
  - `src/system_03_search_agent/adapters/web_sse/app.py` lines 251 to 256: the cap "matches Section 13.2's own `maxItems: 50`", directly above `_MAX_CITATIONS_PER_RUN = MAX_CITATIONS_PER_ANSWER` (line 272), which is 100.
  - `src/system_03_search_agent/adapters/web_sse/app.py` lines 1866 to 1869: "Whether `_MAX_CITATIONS_PER_RUN` and Section 13.2's `maxItems: 50` should themselves move ... is left open", which this change has just decided.
  - `tests/system_03_search_agent/feedback/test_contracts.py` lines 452 to 459: the renamed test `test_a_full_ceiling_of_citations_at_claim_texts_max_still_validate` keeps a docstring about "50 citations" and "`feedback.capture._MAX_CITATIONS` is 50".
- Reproduction: `grep -n "still 50" src/system_03_search_agent/adapters/graphql/types.py` prints line 186; `sed -n 251,256p src/system_03_search_agent/adapters/web_sse/app.py` prints the `maxItems: 50` sentence.
- Why it matters: this repository has a recorded history (F-6.0-01, quoted in the same comment block) of comments justifying a bound with a number that is not there. The next reader of the export sees 50 in prose and 100 in code.
- NOT FIXED

### J-54-04: Two constants with nearly one name now mean 30 and 100
- Severity: minor
- What: the new `MAX_CITATIONS_PER_ANSWER = 100` (`src/system_03_search_agent/feedback/contracts.py` line 63) sits beside the older `_MAX_CITATIONS_PER_ANSWER = 30` in `src/system_03_search_agent/core/graph.py` line 8785, which is dormant on the live path. `app.py` line 1813 still mentions `_MAX_CITATIONS_PER_ANSWER` in a comment a few lines from code that uses the new one.
- Reproduction: `grep -rn "MAX_CITATIONS_PER_ANSWER =" src/` prints both lines, `= 30` and `= 100`.
- Why it matters: a reader or a later change that greps one name finds the other, and the two values differ by more than three times. A distinct name such as `MAX_STORED_CITATIONS` would avoid that.
- NOT FIXED

### J-54-05: The analytics event's citation_count stops topping out at 50
- Severity: unsure (a change of meaning in a number, arguably a correction)
- What: `src/system_03_search_agent/core/run.py` line 499 sends `"citation_count": len(interaction.citations)` on the `QUERY_COMPLETED` analytics event. That list is the capture-truncated one (`feedback/capture.py` lines 414 to 416), so before this change the property could never exceed 50 and now it reaches 100.
- Reproduction: read only. `assemble_interaction` with 77 citation events returns a row with 77 citations (judge probe `probe_e2e.py`: "stored row citations: 77"), which is the value this property now carries; on develop the same input gives 50 (`test_citations_are_capped_at_fifty` on develop asserted exactly that).
- Why it matters: any analytics chart of citations per answer shows a step on the deploy date that is a measurement change, not a behaviour change. Nobody using the product sees it. Filed so whoever reads that chart knows why.
- NOT FIXED

### J-54-06: A reader can still flag at most 50 citations on an answer that now shows up to 100
- Severity: unsure (existed before this change; the reopened screen has no flag control, so this card does not make it reachable in a new place)
- What: `FeedbackPayload.citation_flags` keeps `max_length=50` (`src/system_03_search_agent/feedback/contracts.py` line 533), as does the MCP `rate_answer` tool (`src/system_03_search_agent/adapters/mcp/server.py` line 1688). The live answer screen already showed up to 100 citations before this change.
- Reproduction: read only. `frontend/src/components/feedback/FeedbackSurface.tsx` line 198 sends one flag per flagged source with no cap of its own, so the 51st flag would produce a 422.
- Why it matters: almost nobody flags 51 sources. Filed because the brief asked for every other 50 on the citation path, and this is the one left.
- NOT FIXED

### J-54-07: The ceiling choice has no DECISIONS.md row
- Severity: minor (process)
- What: `build.md` records a choice between alternatives (100 against 200 or no cap, one constant against five literals, code against a migration). `.claude/rules/decision-logging.md` and the production standards hardening gate ask for a `DECISIONS.md` row when a choice affects future work. `git diff origin/develop...HEAD --name-only` does not include `DECISIONS.md`, and `grep -n "card 54" DECISIONS.md` finds nothing.
- Reproduction: the two commands above.
- Why it matters: the stored shape of `interactions.citations` moved, and that bound also decides the size of every saved answer (J-54-02). The next person to change it should find why it is 100.
- NOT FIXED

## What I checked and how

### Correctness of every bound (brief item 1)

All five bounds on the path now read one constant, `MAX_CITATIONS_PER_ANSWER = 100` (`src/system_03_search_agent/feedback/contracts.py` line 63).

| Place | File and line | Now |
|---|---|---|
| Capture truncation | `feedback/capture.py` line 53, applied at lines 414 to 416 | 100 |
| Stored row model | `feedback/contracts.py` lines 211 to 213 | 100 |
| Saved-answer reply model | `adapters/web_sse/app.py` lines 892 to 894 | 100 |
| Saved-answer slice | `adapters/web_sse/app.py` line 1127 | 100 |
| REST export cap, break and header | `adapters/web_sse/app.py` lines 272, 1764, 1844 and 1870 | 100 |
| MCP | `adapters/mcp/server.py` line 196, own literal | 100, unchanged |
| GraphQL | `adapters/graphql/types.py` line 188, own literal | 100, unchanged |
| History count | `feedback/history.py` line 149, counts what is stored | no cap |
| Frontend parser and screen | `frontend/src/lib/api.ts` lines 540 to 562, `SavedAnswerScreen.tsx` line 358 | no cap, no slice |
| CLI export reader | `adapters/cli/client.py` lines 1088 to 1116 | no cap |
| Database column | `alembic/versions/0001_user_data_schema.py` lines 155 to 160; no check constraint on it in the local database's `\d interactions`; index 0009 has no `INCLUDE` of `citations` | none |

A search of `src/` and `frontend/src/` for `[:50]`, `max_length=50`, `le=50` and `= 50` found no other cap on the citation path. The remaining 50s are tool row caps, entity caps, the history page size and the citation flag list (J-54-06).

The claim that one live answer can never cite more than 100 rests on `core/graph.py`: `_MAX_FINDINGS_FOR_DISPLAY = _PLAN_TOOL_CALL_ROW_LIMIT` (lines 5369 and 8832), `build_synth_findings(..., max_findings=_MAX_FINDINGS_FOR_DISPLAY)` (line 12730), one display slot per distinct `citation_id` (`synthesis/grounding.py` lines 1833 to 1847), and one citation per slot (`core/graph.py` lines 10711 to 10788). I read that; I did not drive a live run past 100. The highest `display_index` in any recorded run under `testing/` is 91.

### Own probes, run

- End to end through the real capture, the real writer, the local PostgreSQL user database, the real history list and the real `GET /v1/history/{trace_id}/answer` with a real signed-up account (`probe_e2e.py`, scratchpad, 1000 character claims):
  - 77 events: stored 77, history `citation_count` 77, saved-answer reply 77, highest `display_index` 77.
  - 100 events: stored 100, count 100, reply 100.
  - 130 events: stored 100, count 100, reply 100.
- REST export at the boundary (`probe_export.py`, own events, not the author's helper): 49, 50, 51, 99 and 100 events return every one with no truncation header; 101 returns 100 with `x-citations-export-truncated: true`.
- History list cost (`probe_history_cost.py`): J-54-02.

### Regression against develop (brief item 2)

- Nothing a person sees gets worse. A long answer saved after deploy shows more rows, not fewer, and an answer with 50 or fewer citations is byte for byte the same path.
- Bigger payloads, only for answers citing more than 50: a stored row up to about 140 KB of citation JSON at 1000 character claims (was about 70 KB), a saved-answer reply up to 140,158 bytes measured (was about 70 KB), a REST export up to 137,369 bytes measured (was about 68,665).
- The history list's database read doubles for long answers: 100 ms to 200 ms median locally for a page of 50 such rows (J-54-02).
- No request model accepts more than before. Two response models (`SavedAnswerResponse`, the export's `response_model`) and one stored model now allow 100. Every downstream reader I found (frontend parser, CLI, MCP reopen, eval trace source) has no smaller cap.

### Migration and fenced paths (brief item 3)

`git diff origin/develop...HEAD --name-only` lists four files under `src/`, five under `tests/` and two reports. Nothing under `alembic/` or `.claude/`, no `DECISIONS.md`, no schema change. Verified by command.

### Tests (brief item 4)

- `python3 -m pytest tests/system_03_search_agent/feedback tests/system_03_search_agent/adapters -q -p no:cacheprovider`: 1016 passed, 0 failed, 0 skipped, 2 warnings, 232.84 s. The database-backed MCP test ran (passed by name with `-k 110_marker`).
- `tests/system_03_search_agent/core/test_run_capture.py`: 13 passed.
- Constant set back to 50: 8 tests went red across capture, contracts, saved-answer endpoint, export and MCP.
- Each site mutated alone with the constant left at 100, every one went red: capture cap at 50 (2 red), stored model at 50 (4 red), saved-answer model at 50 (3 red), saved-answer slice at 50 (2 red), saved-answer slice removed (1 red), export cap at 50 (2 red), capture cap removed (1 red). Each was reverted with `git checkout`, and `git diff` on source was clean after every one.
- `ruff check` over the whole repository: all checks passed. CI on the pull request head `ba32b96d`: all four jobs pass.

### Production standards (brief item 5)

- Every array keeps a `maxItems`: met, at 100.
- Parameterised SQL, no new endpoint, no new dependency, no secret: nothing changed there.
- No migration without rollback: no migration.
- DECISIONS.md for a decision affecting future work: missing (J-54-07).
- Tests for a changed endpoint: the saved-answer endpoint and export both gained above-ceiling and at-ceiling tests; the valid, invalid and null cases already existed in `test_saved_answer_endpoint.py`.

### Verified by my own probes versus only read

- Verified by running: the 100 ceiling end to end through capture, the real database, the history count and the saved-answer reply; the export boundary at 49 to 101; the history list cost; that every new test goes red when its site is broken; the suite counts; no migration file.
- Only read: that a live answer can never cite more than 100 (graph code and the recorded maximum of 91); that the frontend, CLI and eval readers have no cap of their own; that the reopened web screen has no omission disclosure (J-54-01).

### Note for the lead

An untracked `testing/Developer/reports/2026-10-07_card54/adversary.md` appeared in this worktree during my run. I did not write it. My only file is `judge.md`.

## Verdict

PASS against the card for every answer saved after this deploys. A reopened answer and the REST export now return every citation the live answer showed, up to 100, with no migration, and every new test is shown to go red when its site is broken.

Conditions the owner should see:

- J-54-01 (major): answers already saved before deploy stay at 50 citations, and the web screen does not say so. The owner's own HNF1A retest will look unfixed unless it uses a freshly asked answer.
- J-54-02 (minor): the one thing worse than develop is cost, not what a person sees. The history list's database read for long answers doubles, measured at 100 ms to 200 ms locally for a full page.

No finding sits inside a fix made earlier in this card's review loop.
