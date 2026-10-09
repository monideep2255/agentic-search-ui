# Card 71 build: tables in a reopened answer

Items 1 and 5 of `diagnosis.md`. Frontend only. The words and rows of an answer are unchanged.

## Table of contents

- [The change](#the-change)
- [Choices](#choices)
- [Tests](#tests)

## The change

- A reopened answer's table now shows ten rows at a time, with the same "Showing 1–10 of 20" bar and Previous and Next controls the live answer shows.
- On a phone (720 px and narrower, the live breakpoint) a reopened table never runs past the screen edge. Each row stacks: the first cell on top, the other cells beneath in a muted line, as the live phone view does.
- On a desktop the table looks as it did, plus the bar when there are more than ten rows.

## Choices

- Shared bar: the pagination bar moved out of `AnswerScreen.tsx` into `frontend/src/components/answer/RecordsPaginationBar.tsx`, markup and test ids unchanged, and both screens use it. Rejected: copying the bar into the saved renderer, because that is how the two drifted apart.
- Shared rows: not reused. The live rows are built inside `AnswerScreen` from claims, citation chips and per-claim styling that a stored markdown table does not have. Rejected: faking claims from markdown cells, which risks changing the live screen. The saved stacked row copies the live phone layout (same spacing, sizes and colours) without the identifier styling.
- Phone breakpoint: the saved table imports `PHONE_LAYOUT_QUERY` from the live screen, so the two switch at the same width.
- Rejected for phones: wrapping long cells inside a scroll box. It still scrolls sideways, which is the complaint.

## Tests

- New `frontend/src/components/screens/savedAnswerMarkdown.card71.test.tsx`, three tests.
- Seen red before the change: the 20-row paging test and the phone stacking test failed against the old renderer. Green after.
- The no-bar-for-small-tables test passed both before and after, as a guard.
- Existing live and saved screen tests stay green (full suite in the report to the lead).
- No Playwright spec added: the repository's e2e specs run against a live target, and the unit test covers the markup.
