# Card 59 fix round: stop replies, stop surfaces and the abandonment timer

The one fix round for pull request #208, answering `judge.md` and `adversary.md` (round 1). Decision D18 holds throughout: an answer that finished before Stop arrived stands, and the screen, history and memory never disagree. No migration, no package, nothing under `.claude/` or `alembic/`.

## Table of contents

- [The fixes, in the reader's words](#the-fixes-in-the-readers-words)
- [Per finding](#per-finding)
- [Left as named items](#left-as-named-items)
- [Gates](#gates)

## The fixes, in the reader's words

- Pressing Stop and then asking a new question never freezes or hides the new question's answer, whatever the first stop request does afterwards.
- Every way of stopping a run tells the truth about a run that had already finished: the GraphQL `stopRun`, the REST stop endpoint and the command line all say it had already finished, never "stopped".
- A finished answer is saved to history and memory even when nobody is watching the run while it saves.
- The 5 second fallback, the frozen reveal while "Stopping…" and the missing failure text under a confirmed stop each now have a test that fails if they go.
- Card 58's Stop timing test no longer fails one run in five.

## Per finding

| Finding | Status | What changed | Test |
|---|---|---|---|
| J-59-04, A-59-02 | Fixed | `stopCurrentRun` in `frontend/src/App.tsx` notes `askSeq` at the press. A failed stop request closes the stream only if no newer question (or sign-out) started since. `askSeq` moves synchronously when a question starts, before any render, so there is no gap in which a late failure reaches the new run. | `App.stopAfterAnswer.test.tsx`, arm "J-59-04": stop A with a held stop request, New search, ask B, then fail A's stop. Red before the change ("A's failed stop closed question B's stream: expected true to be false"), green after; B's answer then lands with its source and no "Search stopped". |
| A-59-01 | Fixed | `RunRegistry.cancel_run` now returns whether it cancelled. GraphQL `stopRun` returns that instead of reading `task.done()` beside it. A run that already sent `done` answers `stopped: false`. | `test_run_registry_stop_after_done.py`, C2, through the real resolver and a real registry, the memory write parked after `done`. Red before (`stopped` was true), green after. A1 now also asserts `cancel_run` returns false after `done`. |
| A-59-03 | Fixed | The REST stop endpoint returns `cancel_run`'s answer instead of a fixed `stopped: true`. The command line already printed "run was already finished" for `stopped: false`; that branch was unreachable and now is reached. | C3, through the real `post_v1_query_stop` handler, red before and green after. `test_streaming_endpoints.py`'s idempotency arm now expects `{"stopped": false}` twice for a finished run, red before and green after. `test_main.py`'s already-finished arm now pins the printed message. |
| J-59-02 | Fixed | `_cancel_if_still_abandoned` goes through the same guard as `cancel_run`, the new module function `_cancel_unless_finished`, so the timer leaves a run alone once `done` is on the read path. | C1: a reader that stops at `done`, a 0.2 second grace, the memory write parked past it. Red before (the timer ended the run mid-save), green after. |
| J-59-06 | Fixed | Tests only. | Three arms in `App.stopAfterAnswer.test.tsx`, each seen red under its one-line mutation and green without it: M1, the fallback effect disabled ("Stopping… never ended without a reply"); M7, `stopped: stopped` in the reveal ("a sentence appeared while Stop was awaiting the server"); M6, `streamError` no longer suppressed ("a confirmed stop showed a failure notice"). The M6 check replaces reliance on the server's wording, which the screen never rendered. |
| J-59-01 | Fixed | The card 58 arm in `App.stopUntilAnswer.test.tsx` installs fake timers before the ask, with `shouldAdvanceTime`, instead of after the run arrived. Before, a timer the screen had already set was left on the real clock, out of reach of the fake walk. Probe: the sentence appeared at 2.8, 2.8 and 6.2 fake seconds in three runs before (8 is the limit), and at 2.6 in all three after. Every check in the arm is unchanged. | 10 whole-file runs in a row, 10 passed. The original passed 10 of 10 on this machine today, so the red was not reproduced as a failure; the probe shows the variance that caused it. |

Shapes: no field was added to either surface. GraphQL `StopRunResult` keeps `runId` and `stopped`; REST `StopRunResponse` keeps `stopped`. `stopped: false` means "it had already finished". The web client does not read the REST body.

## Left as named items

- A-59-04 (a failed stop request shows "Search stopped" while the server keeps the answer): not closed. Item 1 binds the failure to its own run; on that run it still closes the stream and falls back to "Search stopped".
- A-59-05 (Stop cannot end a run whose save after `done` hangs): not closed, and its bound changed. The adversary noted the abandonment timer freed such a run after about 30 seconds. With J-59-02 fixed, the timer no longer cancels after `done` either, so a hung save now holds the run, and its slot under the per-owner cap, until the database call returns or times out. This is the owner's trade to confirm.
- J-59-03, J-59-05, J-59-07 and J-59-08: not in this round's scope, unchanged.
- `frontend/src/lib/api.ts`'s `stopRun` comment still says the endpoint always returns `{stopped: true}`. It is outside this round's file fence; one line to correct next.

## Gates

| Gate | Exit code |
|---|---|
| `ruff check` | 0 |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | 0 |
| `tests/system_03_search_agent/core -k "run_registry or cancel or stop"` | 0, 55 passed |
| GraphQL, REST, command line and capture stop tests (`test_types.py`, `test_streaming_endpoints.py`, `test_main.py`, `test_client.py`, `test_capture_bypasses.py`) | 0, 192 passed |
| `npm run build` | 0 |
| `App.stopAfterAnswer.test.tsx` | 0, 7 passed, and 5 more runs all passed |
| `App.stopUntilAnswer.test.tsx` | 0, 7 passed, and 10 runs in a row all passed |
| `python3 tracker/check_doc_drift.py --check` | 0 |
