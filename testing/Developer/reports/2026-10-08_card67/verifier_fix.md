# Card 67 fix round verifier

Fresh verifier of the fix round for pull request 207, branch `fix/card67-dated-outage-note` at cae7a4ef against `origin/develop`. Findings are appended as they are established; the verdict is at the end.

## Table of contents

- [Findings](#findings)
- [Per finding the round claims fixed](#per-finding-the-round-claims-fixed)
- [Nothing worse than develop](#nothing-worse-than-develop)
- [The reworded sentence](#the-reworded-sentence)
- [Test counts](#test-counts)
- [Verified versus read](#verified-versus-read)
- [Verdict](#verdict)

## Findings

### VF-67-01: the length guard's boundary is not pinned; a guard up to 52 characters too loose stays green

- Severity: minor
- Regression: no (test gap inside this round's fix for J-67-03 and A-67-02; the code as shipped is correct)
- What: `outage_note.py` line 152 compares `len(result) > MAX_ANSWER_MARKDOWN`. The tests check a stored answer at exactly 32000 (rewrite would be 32053) and a rewrite of exactly 32000. Nothing checks a rewrite of 32001 to 32052.
- Reproduction: on an untracked copy of HEAD, line 152 changed to `> MAX_ANSWER_MARKDOWN + 52`: `test_outage_note_dated.py` 48 passed. `+ 53`: 3 failed. `+ 1`: 48 passed. With `+ 52`, a stored answer of 31999 characters ending in the PubMed note would come back at 32052 and fail `SavedAnswerResponse` and `ReopenedAnswerOutput` validation, the exact J-67-03 failure.
- Why it matters: the guard that stops a saved answer becoming unopenable is protected only against its removal, not against drift (for example someone adding a margin, or the response models' cap and `MAX_ANSWER_MARKDOWN` parting). A one-character-over case (`_padded(NOTE, MAX - growth + 1)` returned unchanged) would pin it.
- NOT FIXED

### VF-67-02: the "whole paragraph only" rule is tested for the one-database note alone; `search` in place of `fullmatch` in the plural and generic branches stays green

- Severity: minor
- Regression: no (test gap inside this round's fix for A-67-04, J-67-05 and J-67-06; the code as shipped uses `fullmatch` in all three branches, lines 107, 115 and 122)
- What: every case in `test_text_that_is_not_the_note_paragraph_is_never_touched` (test file lines 195 to 224) wraps `NOTE`, the PubMed one-database note. No case wraps a several-databases or unnamed note in a table row, list item, quote or longer paragraph.
- Reproduction: on an untracked copy, line 115 `pattern.fullmatch(paragraph)` changed to `pattern.search(paragraph)`: 48 passed. Line 122 `_GENERIC.fullmatch` changed to `_GENERIC.search`: 48 passed. The same change on line 107 (single branch): 1 failed. Under the surviving mutation a paragraph such as "Variant X is pathogenic [1]. PubMed and ClinVar are down at NCBI right now, ... Try again later." would be replaced wholesale by the note, deleting the claim and its marker.
- Why it matters: the property the round claims for A-67-04 ("a table row, list item, quote, a paragraph with anything before or after the note ... are all left alone") is enforced by the code but guarded by a test for one of its three branches only.
- NOT FIXED

### VF-67-03: the branch now does neither half of owner decision D17, and no decision row records the change

- Severity: major (process; owner's call, not a code defect)
- Regression: not applicable
- What: `testing/Board_plan.md` line 222 records D17, answered Yes: "Card 67: the outage note is dated when the answer is saved". `testing/UI_fix_plan.md` line 71 framed the question as "dated or reworded". After this round the note is reworded with no date, on reading (`outage_note.py` lines 9 to 21). `fix.md` calls the no-date wording "the lead's decision for this round". `grep -n "D17\|[Cc]ard 67" DECISIONS.md` finds nothing on the branch.
- Reproduction: the grep above; `testing/Board_plan.md` line 222 as quoted.
- Why it matters: the decision-logging rule needs a `DECISIONS.md` row for the choice, and the owner answered "dated" to a dated-or-reworded question. The reasons given (one time on the screen, in the reader's own zone, so the note can never disagree with the header) are sound from the user's chair, and I would make the same call. But it reverses an owner answer, so the owner should confirm it before or at merge, and a row should record it.
- NOT FIXED

### VF-67-04: "was not answering" is looser than what NCBI did; NCBI answered, saying its search was unavailable

- Severity: unsure (wording; nothing a reader would act on wrongly)
- Regression: no (the live note "is down at NCBI" is unchanged)
- What: `kind == "service_down"` is set only when E-utilities "answered with a success status and an `ERROR` body saying its own search is unavailable" (`tools/ncbi_transport.py` lines 266 to 270, decided at line 570). The reopened note says "NCBI's PubMed was not answering" (`outage_note.py` lines 110, 118, 126).
- Reproduction: `past_tense_outage_notes(_build_failed_search_note([{"source": "pubmed", "kind": "service_down"}]), datetime(2026, 10, 7, 23, 30, tzinfo=UTC))` returned "When this answer was written, NCBI's PubMed was not answering, so this answer may be missing papers from it. Ask the question again to search afresh."
- Why it matters: card 63 chose its words to "say what NCBI said" (`core/graph.py`, `_build_failed_search_note` docstring). Strictly, NCBI did answer, with an error. "was down" would be the past tense of the live note and exactly true. To a reader the two mean the same thing, so this is filed as unsure, not as a false statement.
- NOT FIXED

### VF-67-05: an answer within about 55 characters of the limit keeps "right now ... Try again later" when reopened

- Severity: minor
- Regression: no (develop shows the present-tense note for every saved answer; this keeps it for a few)
- What: `outage_note.py` lines 151 to 153 return the stored text unchanged when the rewrite would pass 32000 characters. That is the right trade (an answer that opens beats one that does not) and it is documented, but those answers reopen with the stale present-tense warning the card exists to remove.
- Reproduction: my sweep, `_padded(note, total)` for every live and older note shape, `total` from 31780 to 32000, served through `get_saved_answer` into the web endpoint (`TestClient`, `GET /v1/history/t1/answer`) and the MCP `reopen_past_answer` function: no failure in 7136 opens; every stored length above 32000 minus the growth (51 to 55 characters, by shape) came back unchanged, present tense included.
- Why it matters: rare (a near-cap answer that also lost an NCBI search), and the header's date is still there. Listed so it is a known, named limit rather than a surprise.
- NOT FIXED

## Per finding the round claims fixed

Each mutation was made on an untracked copy of HEAD (`git archive`), never in the worktree, and restored after its run. "Red" means `test_outage_note_dated.py` failed with the mutation.

| Finding | Fixed in code | Mutation that removes the fix | Result |
|---|---|---|---|
| J-67-03, A-67-02 (near-cap answer will not open) | Yes, `outage_note.py` lines 151 to 153 | guard removed; guard `>=` | Red; red. But a guard up to 52 too loose is green (VF-67-01) |
| J-67-01, A-67-03 (UTC day under a local header) | Yes, no date in the sentence (lines 100, 110 to 128) | a date put back into `_WHEN`, as words or digits | Red; red |
| A-67-01, A-67-05, J-67-02 (older wordings) | Yes, lines 80 to 97 | each older pattern disabled; older note keeps "has no" | Red in all four |
| A-67-09, J-67-04 (tests blind to a garble) | Mostly | plural back to "are down at NCBI"; "NCBI's" dropped; "also" sentence dropped; lowercase "some" lost | Red in all four. `search` in place of `fullmatch` in two of three branches is green (VF-67-02) |
| A-67-04, J-67-05, J-67-06 (text that is not the note) | Yes, `fullmatch` on whole paragraphs, names from the builder's list, name and missing-words pair | name loosened to any text; pair check removed; split per line; `fullmatch` to `match` or `search` in the single branch | Red in all. Plural and generic branches unguarded by tests (VF-67-02) |
| J-67-07 (no `created_at` crashes) | Yes, line 140 | guard removed | Red |
| A-67-08, J-67-09 (docstring names a missing test) | Yes, line 43 names `tests/system_03_search_agent/feedback/test_outage_note_dated.py`, which exists | not applicable | Read and `ls` |
| History wiring | Yes, `history.py` line 418 | back to `row.answer_markdown` | Red |

Left as decided by the round: A-67-06 (the "Ask the question again" advice) and A-67-07, J-67-08 (rewrite on reading). See VF-67-03.

## Nothing worse than develop

- Sizes, both surfaces: 7136 opens through the real `get_saved_answer` (stubbed session only), the real web endpoint and the real MCP `reopen_past_answer` function, for 14 note shapes plus a plain answer and the non-outage note, at every stored length from 31780 to 32000 plus 500 and 5000, with ASCII and with multibyte and astral padding: 0 failures, web and MCP text identical every time, never over 32000. Develop opens all of these too.
- Only the note changes: a real capture (`answer_markdown_from`) carrying a heading, a claim with "down at NCBI right now" in it, a table row, a list item and a quote each holding the full note, the note itself and the medical-advice note: only the note paragraph changed; markers `[1]` and `[2]` kept in count and place. A 20000-answer random fuzz of paragraphs built from notes, markers, table, list and quote fragments: 0 cases where anything but an exact note paragraph changed, 0 marker differences.
- No-note answers come back as the same string; the trust line is a separate field passed through unchanged (`history.py`).
- Boundary: for every shape, an answer whose rewrite exactly fits is rewritten and one character more returns the stored text.

## The reworded sentence

- Past tense throughout ("was" or "were not answering"); no "right now", "is down", "are down" or "Try again later" survives in any live or older shape.
- The right database: the name is copied from the matched note and must be one of `_DOWN_SOURCE_WORDS`, with its own missing words (pair check, line 108).
- No date: none of the rewritten notes contains a month or digits. The web header shows `asked_at` in local time (`SavedAnswerScreen.tsx` lines 72 to 83 and 256); MCP's `asked_at` serialised as `2026-10-07T23:30:00Z` in my probe.
- One looseness, VF-67-04.

## Test counts

- `tests/system_03_search_agent/feedback/test_outage_note_dated.py`: 48 passed.
- `tests/system_03_search_agent/feedback`: 218 passed.
- `tests/system_03_search_agent/adapters/mcp`: 75 passed.
- `adapters/web_sse/test_saved_answer_endpoint.py` and `core/test_write_failed_search.py`: 39 passed.
- `ruff check` on the three changed Python files: all checks passed.

## Verified versus read

- Verified with my own probes: every row of the per-finding table except the docstring row, the size sweep on both surfaces, the capture-to-reopen run, the fuzz, the boundary checks, the reworded sentences, MCP `asked_at`, VF-67-01, VF-67-02, VF-67-05, and the test counts.
- Read only: VF-67-03 (board, fix plan and `DECISIONS.md` text), VF-67-04's meaning of `service_down` (`ncbi_transport.py` docstring), the frontend header code (not rendered), and that `get_saved_answer` is the only reader of saved markdown (grep of `src`).

## Verdict

MERGE WITH NAMED ITEMS.

- VF-67-03: the owner confirms the no-date, on-read rewording in place of D17's "dated when saved", and a `DECISIONS.md` row records it.
- VF-67-01 and VF-67-02 are test gaps that sit inside this round's own fixes (the length guard and the whole-paragraph rule). The code is correct today; the tests protect it only partly. They are minor and do not block, but they are inside a fix made during this card, which the review loop's stop condition names.

Every judge and adversary finding the round claims fixed is fixed in code, and each fix goes red when removed, with the two partial exceptions above.

Worse than develop: no
