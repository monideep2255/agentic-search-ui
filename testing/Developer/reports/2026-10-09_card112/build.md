# Card 112 build: earlier searches stay in "Your searches" after a Stop

Diagnosis: `diagnosis.md` beside this file. In short, `ask` dropped every row with the same question text the moment the question was asked again, and a stopped row had no second line because only a landed run ever wrote one.

## Table of contents

- [What changed](#what-changed)
- [Before and after, in the user's words](#before-and-after-in-the-users-words)
- [Tests](#tests)
- [Left as it is](#left-as-it-is)
- [Fix round](#fix-round)

## What changed

- `frontend/src/App.tsx`, `ask`: the new row is put on top and no row is filtered out. The list before a reload now matches the list after one.
- `frontend/src/App.tsx`, `ask`: the trace id from `createRun` is tagged onto this ask's own row by its id, not by question text, since two rows can now share a question.
- `frontend/src/App.tsx`, a new effect: once the server confirms a stop (its fatal `cancelled` reply), this ask's row reads "No answer saved · <date>", built by the same `formatHistoryMeta` a reload uses, with the date of the ask. Its saved-answer flag is set to false, as a reload would set it. A stop whose request failed gets no reply, and the server may still answer, so that row is left as it is.
- `frontend/src/App.historyAfterStop.test.tsx`: new, two arms, through the real `fetchHistory` with only `fetch` stubbed.
- `frontend/src/App.test.tsx`: the F-4.13-A-07 and F-4.13-RV-01 tests pinned the old filter (one row per question). They now pin the new rule: the re-ask is a new row on top, the restored row stays below, and each row still runs its own question.
- `testing/Test_queries_and_workflows.md`: one line under query 56.
- No backend or API change.

## Before and after, in the user's words

- Before: "I stopped a search and my earlier BRCA1 searches disappeared from my list until I refreshed. And the new one does not say it has no answer." The same loss happened after a re-ask that answered.
- After: every earlier search of the question stays in the list. The stopped one sits on top and reads "No answer saved · Oct 9", the same words a reload shows.

## Tests

- Red on develop's code: `npx vitest run src/App.historyAfterStop.test.tsx` gave 2 failed. The Stop arm: the top row read only the question, no "No answer saved". The answered arm: "an earlier row of the same question vanished", 1 row where 4 belong.
- Green after the fix: 2 passed.
- Mutation 1, the text filter put back: 2 failed, both at "an earlier row of the same question vanished" (1 row, expected 4). Restored.
- Mutation 2, the stopped-row effect turned off: 1 failed at "the stopped row has no 'No answer saved' line". Restored, 2 passed.
- Whole frontend suite (`npx vitest run`): 68 files, 613 tests passed.
- `npx tsc --noEmit -p .`: clean.
- `npm run build`: succeeds (the existing chunk size warning only).
- `ruff check` from `<repo-root>`, no path: All checks passed.

## Left as it is

- The rail's highlighted row is found by question text, first match, so with several rows of one question the newest is highlighted. Restored history already held such rows before this change, so nothing new reaches a person.
- Not checked on the deployed app: no live run was made for this card.

## Fix round

Judge: MERGE. Adversary: PASS on the goal. All changes are in the frontend; no backend change.

- J-112-01, A-112-04: the stopped row's date is now taken when the stop is confirmed, not when the question was sent. The server stores its date when it saves the row after the stop, so this is closer to it. The code comment no longer claims the two are one instant; it says a reload shows the server's date.
- J-112-02: `ask` keeps the in-tab list to `HISTORY_LIST_LIMIT` (20, the server's `DEFAULT_LIMIT` in `feedback/history.py`; the frontend had no constant, and `fetchHistory` sends no limit), dropping the oldest.
- J-112-03, A-112-02: the rail highlight is the row's id: this ask's row for a run, the opened row for a saved answer. It no longer matches on question text.
- J-112-04, J-112-05: new tests in `frontend/src/App.historyAfterStop.test.tsx`, through the real `fetchHistory`. Five were added, with the date and limit and highlight ones.

Red and green:

- On c37c5f1f's `App.tsx`: the date, limit and highlight tests fail (3 failed, 4 passed).
- After the fix: 7 passed.
- Failed stop: with `stopConfirmed` reduced to plain `stopped`, the failed-stop test goes red. Restored.
- Tagging: with the tag matched on question text again, the tagging test stays green. A stray run id on an older bare row has no effect on screen (that row has no saved-answer flag and still re-asks), so no UI test can show it red. The test pins what a person sees, and the rule is held by the code comment only.
- Whole suite 68 files, 618 tests passed; `npx tsc --noEmit -p .` clean; `npm run build` succeeds; `ruff check` from `<repo-root>` passes.

Left as they are:

- A-112-01: a failed re-ask keeps its bare row (develop also showed one).
- A-112-03: duplicate trace id inside one server response (before this card).
- A-112-05: a guest's stop before sign-in keeps a bare row until a reload.
- A-112-06: a failed run reads like an answered one (before this card).
- A-112-07: a Stop then a re-ask before the server replies leaves the stopped row bare until a reload.
