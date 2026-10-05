# w2-fallback: no silent fallback (card 46 and owner decision D1)

## Change

- The structured fallback note now reads: "Note: no written summary could be checked against the records, so the records found are listed below with their sources". The web app no longer hides it (`AnswerScreen.tsx` `HIDDEN_NOTE_PATTERNS`), the run view still classes it as a note, and the saved answer carries the same text because it is built from the same note token.
- Card 46: a run that hits its cost or call limit after findings were gathered no longer returns only the limit note. `write_node` skips its own model call, lists the gathered findings through the structured fallback (same grounding pass, one citation each, trust floored at ask), and shows a new true note: "Note: this question reached its resource limit before it finished, so this answer lists the records gathered so far". A limit hit with nothing gathered, or nothing that grounds, still ships the old limit note (`_partial_result_for_cap`).
- The repair call is skipped on a limit hit. A limit hit inside Write's own call still routes to the same path.

## Tests

- `test_write_completeness.py`: the fallback note text (red on old code), a limit-hit run lists its findings with citations and makes no model call (red on old code), and a limit hit with nothing gathered keeps the limit note.
- `frontend/src/answerNotesHidden.test.tsx`: the note is not hidden (new and earlier wording) and renders in `AnswerScreen`. Red proof for the frontend was by construction: the old pattern hides the earlier wording.
- Updated three existing tests to the new wording.
- Python red proof: `graph.py` swapped for `origin/develop`'s copy, 2 failed, restored.

## Gates

- gate02 and gate03 green. gate04: 6531 passed, 6 failed, all `psycopg2` connection refused to localhost Postgres (graphql no-cost and think-retry tests), unrelated and environmental.
- Frontend: `vitest run` 486 of 486 passed, `npm run build` ok.

## Not covered

- No live run. The limit path was tested with `cap_exceeded` in state; a cap raised inside a later node was not run end to end. The saved-answer screen was not rendered; it shows the note because the note is a token in the saved markdown.
- `frontend/node_modules` in the worktree is an untracked symlink to the main checkout's; not committed.
