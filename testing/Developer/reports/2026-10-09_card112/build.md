# Card 112 build: earlier searches stay in "Your searches" after a Stop

Diagnosis: `diagnosis.md` beside this file. In short, `ask` dropped every row with the same question text the moment the question was asked again, and a stopped row had no second line because only a landed run ever wrote one.

## Table of contents

- [What changed](#what-changed)
- [Before and after, in the user's words](#before-and-after-in-the-users-words)
- [Tests](#tests)
- [Left as it is](#left-as-it-is)

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
