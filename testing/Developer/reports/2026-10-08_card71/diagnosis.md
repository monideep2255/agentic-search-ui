# Card 71 diagnosis: a reopened answer does not look like the answer you read

Diagnosis only. No source or test file was changed. Read at develop 2182aff3, paths relative to `<repo-root>`. No probe scripts were needed; every finding is from reading code, the 2026-09-29 evidence files and the card 102 product review.

## Table of contents

- [Summary](#summary)
- [Item 1: paging](#item-1-paging)
- [Item 2: the verification note](#item-2-the-verification-note)
- [Item 3: Sources and the High-risk claim tag](#item-3-sources-and-the-high-risk-claim-tag)
- [Item 4: a question asked twice](#item-4-a-question-asked-twice)
- [Item 5: tables on a phone](#item-5-tables-on-a-phone)

## Summary

| Item | Still on develop | Layer | Touches what an answer says |
|---|---|---|---|
| 1 Paging | Yes | Frontend only | No |
| 2 Verification note | Already fixed live (D1, 2026-10-05); wording differs | None needed | No |
| 3a Sources | Fixed by card 102 | Done | No |
| 3b High-risk claim tag | Yes | Backend plus frontend (new stored field, migration) | No, it is a trust label |
| 4 Asked twice | Intended in a session; the reload case is unexplained | Frontend if changed | No |
| 5 Phone tables | Yes | Frontend only | No |

## Item 1: paging

- Cause: the live renderer pages tables at ten rows (`frontend/src/components/screens/AnswerScreen.tsx` lines 1280 and 1381 to 1385, bar at 1294 to 1347). The saved renderer `frontend/src/components/screens/savedAnswerMarkdown.tsx` (table branch, about lines 233 to 262) maps every `block.rows` row with no paging.
- On develop: yes.
- Smallest fix, in the reader's words: a reopened table of more than ten rows shows ten at a time with the same "Showing 1 to 10 of 20" bar. Alternative: keep one page and say so. The reader's complaint favours the first.
- Fence: frontend only. The words and rows are unchanged.

## Item 2: the verification note

- The saved note is the old wording from `core/graph.py` before commit 178c6bac. The current backend line is "Note: no written summary could be checked against the records, so the records found are listed below with their sources" (`core/graph.py` line 10160).
- Why the live answer omitted it: not a dropped event and not a different path. The note arrived as a `note` token, `useRunView.ts` put it in `systemNotes` (lines 799 to 802), and `AnswerScreen.tsx` line 1598 filtered it with `isHiddenNote`. The 2026-09-21 commit d044969d ("remove the Notes section") hid both wordings. The saved renderer has no filter, so it printed the stored paragraph (`feedback/capture.py` lines 193 to 197).
- On develop: the live side is already fixed. Owner decision D1 (2026-10-05) un-hid it, and `answerNotesHidden.test.tsx` asserts both wordings are visible. The 2026-09-29 run predates that. Not re-run live, so the screen is unproven; the code and test say it shows.
- Fix: none for the live side. Open question: old saved rows keep the old wording ("could not be verified"). That is the stored text, so leave it, or rewrite old rows (a data change, owner's call). Frontend only; no change to what an answer says.

## Item 3: Sources and the High-risk claim tag

- Sources: card 102 added the Sources list to `SavedAnswerScreen.tsx` (lines 331 to 351). Done.
- Tag: still missing. The live tag is built in `useRunView.ts` lines 937 to 944 from the answer-level `trust_signal` event's `risk_tier`. The stored row keeps only `trust_signal`, `answer_trust_line` and citations (`feedback/capture.py` lines 411 to 490, `feedback/history.py` lines 396 to 423); `risk_tier` is not stored anywhere.
- Smallest fix: store the tier with the answer (new nullable column, migration, one more field in `HistoryAnswerResponse`), then show the same tag on the saved screen. Alternative: do not show it on saved copies and say "risk label not kept" (honest, no backend).
- Fence: backend plus frontend; the migration needs a human approval. Does not change answer text.

## Item 4: a question asked twice

- Client, intended: `App.tsx` lines 1255 to 1330 remove any rail row with the same question text and put the new one on top, copied from the prototype's `start()`. The comment at lines 1275 to 1283 says text de-duplication is only among rows present at ask time.
- Server: `list_history` (`feedback/history.py` lines 243 to 323) returns one row per stored run with no grouping, and `mergeServerHistory` (`App.tsx` line 307) keys on `trace_id`. So after a fresh sign-in both BRCA1 asks should list.
- Why only one appeared on 2026-09-29: unexplained by the code. Likely one ask was not stored under that account (for example asked as a guest). Not reproduced; needs a live probe.
- Fix: none until reproduced. If the owner wants one row per question, make it a server or client rule on purpose; as built, in a session it is one row and after reload it is one row per run.

## Item 5: tables on a phone

- Cause: `savedAnswerMarkdown.tsx` table branch wraps the table in `overflowX: auto` with `width: 100%`, so the table scrolls inside its box; the page does not. Cells have no wrapping rule and no scroll cue, so "COMPLETE" is cut at the edge. The live phone view uses a stacked list instead (`AnswerScreen.tsx` `if (phone)` branch in `renderRecords`).
- On develop: yes (card 102 product review, PR-card102-02).
- Smallest fix: on a phone, show each row as a short stack of "label: value", as the live answer does. Alternative: let long cells wrap (`overflowWrap: anywhere`) and add a visible "scroll for more" edge.
- Fence: frontend only.
