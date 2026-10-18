# Card 59 judge report

Fresh judge for pull request #208, branch `fix/card59-stop-after-answer` at 90e69895, against `origin/develop`. Findings are appended as they are established.

## Findings

### J-59-01: card 58's Stop-timing arm is flaky on this branch
- Severity: minor (unsure whether pre-existing; see the develop baseline note appended below)
- Regression: unknown at time of filing; the arm itself is not edited by this pull request
- What: `frontend/src/App.stopUntilAnswer.test.tsx`, arm "keeps Stop on through the writing wait, and off once the first sentence is on screen", failed 2 of 10 runs of the file on this branch, at line 352: "populate-check: the answer never reached the screen: expected false to be true".
- Reproduction: `npx vitest run src/App.stopUntilAnswer.test.tsx` from `frontend/`, ten times in a row on a loaded machine: runs 1 and 7 reported "1 failed | 6 passed (7)", the other eight "7 passed (7)".
- Why it matters: a CI gate that fails one run in five gets re-run until green, and a real regression in that arm would then be re-run away too.
- NOT FIXED

Develop baseline for J-59-01: develop's copy of the same file passed 8 of 8 whole-file runs, and the arm alone passed 8 of 8 on both develop and this branch, interleaved. The arm does not press Stop, and with no press the App path reads the same events as develop (`shownEvents` is `events` when `stopPress` is null, App.tsx about line 1045), so this is most likely load and order sensitivity, not this change. Left at minor, unsure.

### J-59-02: the abandonment timer still cancels a run after its done, the path card 59's server fix does not cover
- Severity: minor
- Regression: no. The same behaviour is on develop; it is the sibling of the window card 59 closed in `cancel_run`.
- What: `RunRegistry._cancel_if_still_abandoned` (`src/system_03_search_agent/core/run_registry.py`, about line 783 to 789) calls `entry.task.cancel()` directly, not `cancel_run`, so it ignores the new `done` check at about line 1081. The browser closes its stream the moment `done` arrives (`consumeEventStream` in `frontend/src/hooks/useAgentRun.ts` cancels the reader on `done`), so every finished run is unwatched while its memory write and history row are still to come.
- Reproduction: own probe (`RunRegistry(abandon_grace_seconds=0.3)`, a real offline run, a subscriber that reads to `done` and stops, the memory write parked on a gate for 1 s). Observed: last events `['cost', 'done', 'error']`, memory write finished 0, cancelled True, `entry.cancelled` True. So a `cancelled` error follows `done`, the turn is not remembered, and the run is marked cancelled while the screen shows the answer.
- Why it matters: with the default 30 s grace this needs the post-done writes to stall for about 30 s (a slow database), so it is rare. When it fires it is exactly the disagreement card 59 set out to close: the screen shows the answer, memory and history do not hold it.
- NOT FIXED

### J-59-03: a stop issued before the run's task first runs leaves no terminal event and no capture row
- Severity: minor, unsure (likely unreachable over HTTP)
- Regression: no, develop behaves the same.
- What: `cancel_run` on a run whose `_drain_into_entry` task has not yet had its first step cancels a coroutine that never starts, so the `except CancelledError` and `finally` in `_drain_into_entry` never run: no `cancelled` event, `finished` never set, no capture row. A subscriber waits on `entry.finished` forever.
- Reproduction: own probe, `create_run` then `cancel_run` twice synchronously, then wait on the task. Observed: `entry.events == []`, `_remember_turn` calls 0, `capture_run` calls 0.
- Why it matters: over HTTP the task has almost certainly started before a stop request arrives, so this is likely unreachable. If it were reached, card 59's browser would sit on "Stopping…" until its 5 s fallback.
- NOT FIXED

### J-59-04: a stop request that fails late kills the next question's stream, inside this card's new code
- Severity: major
- Regression: yes, against develop, and inside the fix made in this phase. Develop's catch was `() => undefined`; this branch's is `() => stop()`.
- What: `stopCurrentRun` in `frontend/src/App.tsx` line 1604 runs `void stopRun(runId, authToken).catch(() => stop())`. `stop` from `useAgentRun` (`frontend/src/hooks/useAgentRun.ts` lines 403 to 406) aborts `controllerRef.current`, whichever run is current WHEN the promise rejects, and sets that run's status to `done`. If the person presses Stop on question A and asks question B before A's stop request fails (a proxy timeout, a 5xx, a dropped network), the rejection aborts B's stream. The 5 s timer does not have this problem: its effect is keyed on `runId` and cleared when B starts.
- Reproduction: own probe in a copy of the branch's frontend, file `App.judge59.probe.test.tsx`, arm P1. Ask A over an open stream, A's `stopRun` returns a promise held open; press Stop ("Stopping…"); press "New search", ask "What is TP53?", B's stream opens (its mock honours the abort signal the way a real fetch body does); then reject A's stop with `Error("502 from the proxy")`; push B's answer frames and `done`; advance 40 s. Observed: `B aborted: true`, `answer on screen: false`, the run stepper still showing, the Stop button reading "Stop" and enabled. Control: the same probe with only line 1604's catch changed back to `() => undefined` gives `B aborted: false`, `answer on screen: true`, and the arm passes.
- Why it matters: for the person, question B hangs on the run screen and never answers, while the server answers B and records and remembers it. Screen, history and memory disagree on a question that had nothing to do with Stop. Pressing Stop on B then reads "Search stopped" about an answer the server kept. The window is how long A's failed stop takes to come back, so a slow proxy error is the likely trigger.
- NOT FIXED

### J-59-05: on a failed, slow or cut-off stop the screen says "Search stopped" while the server may still answer and remember
- Severity: minor
- Regression: no. Develop showed "Search stopped" on every press; this branch narrows the disagreement to these paths but does not close them. Filed because `build.md` and the `deriveStopVerdict` docstring say the screen then matches the server "by construction".
- What: three paths end in `stopped` through the `streamEnded` fallback (`frontend/src/components/chat/StopButton.tsx`, `deriveStopVerdict`, final line) with no word from the server: the stop request rejects (App.tsx line 1604, then `stop()`), no reply within `STOP_CONFIRM_TIMEOUT_MS` (App.tsx about lines 1057 to 1061), and the connection drops while "Stopping…". In each, the server may not have received the stop and may finish, writing an answered history row and a memory turn. A fatal server error that is not `cancelled` is also shown as "Search stopped" with no failure text, because `status` and `streamError` are rewritten for any first fatal error (App.tsx about lines 1043 to 1045).
- Reproduction: own probes in the branch copy. P2: stream left open, stop resolves but no reply: "Search stopped" appeared at 4,998 ms, not before 4 s. P5: the stream errored with `TypeError("network error")` while "Stopping…": "Search stopped", no error text. P4: a fatal error with `error_class` `internal` after the press: "Search stopped", no text matching /fail/.
- Why it matters: the person is told the search stopped, and the next follow-up can still resolve "it" against an answer the server kept. Rare (it needs the stop to be lost), but it is the card's own class of defect.
- NOT FIXED

### J-59-06: three of the card's stated behaviours have no test that fails when they are removed
- Severity: major (test gap on the fix's own claims)
- Regression: no behaviour regression; a gap in this phase's new tests.
- What: one-line mutations of the new code, run against the three shipped files (`App.stopAfterAnswer.test.tsx` 4, `App.stopUntilAnswer.test.tsx` 7, `StopButton.test.tsx` 32), all stayed green:
  - M1, the 5 s fallback deleted (App.tsx about lines 1057 to 1061, the `setTimeout(() => stop(), STOP_CONFIRM_TIMEOUT_MS)` effect replaced by `return;`). This is the only thing that keeps "Stopping…" from hanging for ever when the stream stays open with no reply. My probe P2 goes red under it: no "Search stopped" after 8.5 s.
  - M7, the reveal no longer frozen while the reply is awaited (App.tsx about line 1106, `stopped: stopped || stopping` changed to `stopped: stopped`). My probe P6 goes red: a sentence of the answer appears under "Stopping…" and stays on screen under "Search stopped" after the server confirms, a partial answer on a true stop, which card 58 forbids.
  - M6, the error text no longer suppressed on a confirmed stop (App.tsx about line 1045). My probe P7 goes red: failure text shows under "Search stopped". The shipped arm checks only for the server's wording, /stopped before it finished/, which the screen never renders in any case (`useAgentRun` replaces it with "run failed (cancelled)"), so that assertion cannot fail.
- Also surviving, and judged equivalent by my probes rather than gaps: M3 (no flush on `answered` in the pacing; the press already unpaces it), M4 (no slice at the press mark), M8 (`stopOffered` ignoring the press; `stopping` disables Stop anyway), M10 (no double-press guard; Stop is disabled after the first render, probe P3 sends one stop either way), M11 (`stopping` not disabling Stop; `stopEnabled` is already false).
- Killed: M2 (stop sent after `done`), M5 (status not rewritten), M9 (last terminal wins, StopButton unit arm only), M12 (no fallback to stopped), M13 (develop's abort on press), M14 (`answered` read as `stopped`). Server: removing the `done` check turns A1 and A2 red; making `cancel_run` a no-op turns B and card 58's S1 to S4 red.
- Reproduction: `mutate.py` and `mutprobe.py` in my probe folder, each mutation applied to a copy of the branch's frontend, one test file at a time, the source restored after each.
- Why it matters: the next change to App.tsx can bring back a hanging "Stopping…" or a partial answer under "Search stopped" with every gate green.
- NOT FIXED

### J-59-07: Stop and then a new question before the server replies: the first question can stay in memory unseen
- Severity: minor, unsure
- Regression: no, develop behaves the same.
- What: while "Stopping…", asking a new question calls `setRunId(null)` and `setStopPress(null)` (App.tsx about lines 1416 to 1417). Question A is not archived into the thread because it never landed (the `view.landed` guard, about line 1372), and A's stream is closed before its reply is read. If A's server had finished first, A's history row is answered and A's turn is in session memory. The session id does not change on "New search" (App.tsx line 567), so question B can resolve "it" against A's answer, which the person never saw.
- Reproduction: read, not probed. The order is: press Stop on A, A's `done` crosses the stop on the wire, the person asks B within that round trip.
- Why it matters: rare, and the same class as the card. Recorded so the owner knows the "server decides" rule only holds while the person waits for the reply.
- NOT FIXED

### J-59-08: Stop can no longer free a run stuck in its post-done writes
- Severity: minor, unsure
- Regression: arguably, by design of D18. On develop a Stop cancelled a run hung in its memory or history write; on this branch `cancel_run` returns at the `done` check (`run_registry.py` about line 1081).
- What: a run stays not `finished`, and so counts against the per-owner concurrent-run cap (`count_active_runs_for_owner`), until its post-done writes return. Only the abandonment timer (30 s of unwatched time by default, J-59-02) or the database's own timeout ends it.
- Reproduction: read, not probed separately. Probe P1 on the server side shows the run kept running after `done` until the parked write was released or the abandonment timer fired.
- Why it matters: with a stalled database a person at the cap could see "you already have the maximum number of runs in flight" for up to about 30 s after answers they already have, and Stop does not clear it. Small, and it trades against D18, so the owner may accept it.
- NOT FIXED

## Test counts

| Suite | Result |
|---|---|
| `frontend/src/App.stopAfterAnswer.test.tsx` | 4 passed |
| `frontend/src/App.stopUntilAnswer.test.tsx` | 7 passed on 8 of 10 runs; 1 failed, 6 passed on 2 of 10 (J-59-01; develop's copy 8 of 8) |
| `frontend/src/components/chat/StopButton.test.tsx` | 32 passed |
| `tests/system_03_search_agent/core/test_run_registry_stop_after_done.py` and `test_run_registry_stop_mid_write.py` | 7 passed |
| `tests/system_03_search_agent/core -k "run_registry or cancel or stop"` | 52 passed, 1386 deselected |
| Own frontend probes P1 to P7 (a copy of the branch's frontend) | P1 fails (J-59-04); P2 to P7 pass |
| Own server probes | both show behaviour shared with develop (J-59-02, J-59-03) |
| Mutations | 14 frontend: 6 killed, 3 surviving gaps (J-59-06), 5 equivalent. 2 server: both killed |
| Type check (`tsc -b`) and `ruff check` on the changed Python files | clean |

## Verdict

FAIL.

Worse than develop: yes, on one narrow path. J-59-04 sits inside this phase's own fix: the new `catch(() => stop())` at App.tsx line 1604 aborts whichever run is current when a stop request fails, so pressing Stop and then asking a new question can leave that new question hanging, never answered on screen, while the server answers and remembers it. Develop's catch did nothing. Because the defect is inside a fix made in this phase, the review loop's stop condition applies and this goes to the product owner.

Judged against the five questions:

1. Screen, history and memory agree for Stop before any token, mid-stream, after the last token, after `done` with the screen behind, and at the `done` boundary. They do not agree on four paths: a stop that fails late followed by a new question (J-59-04, a regression); a failed, slow or cut-off stop (J-59-05, same as develop); Stop then a new question before the reply (J-59-07, same as develop); and an abandonment cancel after `done` (J-59-02, same as develop). Two quick presses send one stop (probe P3).
2. "Stopping…" cannot hang: the 5 s fallback fired at 4,998 ms (P2), and a dropped connection or server error ends it at once (P4, P5). No test pins the fallback (J-59-06).
3. Server: a run with no `done` is still cancelled, with a `cancelled` error, no memory turn and a `refuse` row (arm B and card 58's S1 to S4, red under the no-op mutation). A run that errors after `done` cannot be stopped, by design. No new task or connection. The abandonment path is the remaining gap (J-59-02), and a hung post-done write can no longer be freed by Stop (J-59-08).
4. Card 58 holds where tested: a true stop sends the request at the press as before and records no answer. But "no partial answer under a stop" rests on the reveal freeze, which no shipped test pins (J-59-06, M7).
5. Worse than develop: yes, J-59-04.

Verified with my own probes: J-59-02, J-59-03, J-59-04 (with a control), the 5 s fallback, the single stop on a double press, the server-error and dropped-connection screens, the reveal freeze (P6), the suppressed failure text (P7), all mutation results, the test counts and the type check. Read only, not probed: J-59-07, J-59-08, the claim that capture and memory run after `done` in `core/run.py` (read at lines 946 to 967 and pinned by the author's populate-checks, not by me), and the follow-up inline-run path (App.tsx about line 1684), which I did not drive.
