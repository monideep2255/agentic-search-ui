# Card 59 adversary report

Round 1, 2026-10-08. Branch `fix/card59-stop-after-answer` at 90e69895, pull request #208 against develop. Findings are appended as they are established.

## Table of contents

- [Findings](#findings)
- [What held](#what-held)
- [Verdict](#verdict)

## Findings

### A-59-01: GraphQL `stopRun` reports `stopped: true` for a run the server no longer stops

- Severity: major (API surface; the web screen is not affected)
- Regression: yes, introduced by this phase's server fix (`cancel_run`'s new `done` check, commit b89843e5)
- What: `adapters/graphql/schema.py`'s `stop_run` computes `was_in_flight = not entry.task.done()` and returns it as `stopped`. Card 59 made `cancel_run` a no-op once `done` is in `entry.events`, but the task keeps running after `done` (memory write, then history row). In that window the mutation now says `stopped: true` while the run is left alone, `entry.cancelled` stays false and `citations.runCancelled` will say false. That is the exact two-fields-disagree shape F-4.3-A-20 was fixed for, and the resolver's own comment ("`stopped` REPORTS WHAT HAPPENED ... an exact report") is no longer true.
- Reproduction: a probe outside the repository (`test_probe_graphql_stop.py`, run with the 4.16 premise fixtures) parks `_remember_turn` after `done`, swaps `schema.default_registry` for its own registry and calls the real `Mutation.stop_run` resolver. Output: `done in buffer: True task done: False`, then `GraphQL stopRun.stopped = True`, then `entry.cancelled = False memory finished = 1 last event = done`. On develop the same call cancelled the task, so `stopped: true` was true there.
- Why it matters: an MCP or GraphQL caller that asks "did my stop do anything" is told yes, and may treat the answer as discarded while history and session memory keep it, so its next "it" points at an answer it believes it stopped. The REST endpoint already returned a fixed `stopped: true` before this card and the web client ignores the body, so the screen is unaffected. The fix is one line (`was_in_flight` must also require no `done` in `entry.events`), but it lives inside this phase's own fix.

### A-59-02: a stop request that fails late kills the next question's stream

- Severity: major (rare trigger, frozen screen and a lost answer when it fires)
- Regression: yes, introduced by this phase's client fix (`stopCurrentRun` in `frontend/src/App.tsx`)
- What: `stopCurrentRun` now does `stopRun(runId, authToken).catch(() => stop())`. `stop` is `useAgentRun`'s, which aborts `controllerRef.current`, whatever run is current when the promise settles, not the run that was stopped. If the stop request is still pending when the 5 second fallback shows "Search stopped" and the person presses Run again (or New search, or asks anew), a later rejection of run 1's stop request aborts run 2's stream. On develop the catch was `() => undefined`, so this could not happen.
- Reproduction: a vitest probe outside the repository (`probe1.test.tsx`, own config pointing at the worktree's `App`) mocks `stopRun` with a promise it rejects by hand. Ask, wait for the first chunk, press Stop (button reads "Stopping…"), wait for the 5 second fallback ("run-stopped" appears), press Run again, wait until run 2's stream is being read, then reject run 1's stop request. Logged output: `run 2 signal aborted before reject: false`, `run 2 signal aborted after run-1 stop rejection: true`. Then run 2's answer frames are pushed: `run 2 answer on screen: false`, `run-stopped on screen: false`, `stop button: Stop`.
- Why it matters: the person sees the second question's run screen frozen mid-search with Stop still offered, and its answer never arrives. The server was not told anything, so run 2 keeps running and spending; if it finishes inside the 30 second abandonment window, history and session memory keep an answer the screen never showed, and the next "it" points at it. The trigger needs a stop request that hangs past 5 seconds and then fails (a dropped connection, a stalled proxy), so it is rare, but the fix is inside this phase's own change. Guarding the catch on the run it was issued for (or capturing the controller at press time) closes it.

### A-59-03: REST `stopped: true` and the CLI's "run stopped" now cover a run the server deliberately kept

- Severity: minor
- Regression: partly. The REST endpoint has always returned a fixed `stopped: true`, so it already said so for a run whose task had fully ended. This phase widens the false case to the after-`done` window, where on develop the cancel really did happen.
- What: `post_v1_query_stop` returns `StopRunResponse(stopped=True)` unconditionally, and `s3 stop <run_id>` prints "run stopped" if `stopped` else "run was already finished". After this phase a stop landing after `done` is a documented no-op that keeps the answer in history and memory, yet the CLI still prints "run stopped".
- Reproduction: read, not probed. `adapters/web_sse/app.py` `post_v1_query_stop` (fixed literal) and `adapters/cli/main.py` line 957; combined with the probe in A-59-01 showing `cancel_run` leaves such a run uncancelled with `done` as its last event.
- Why it matters: a command-line user told "run stopped" will not expect the next follow-up's "it" to resolve to that answer. Same root as A-59-01; the CLI's "run was already finished" branch exists and is never reached.

### A-59-04: when the stop request fails, the screen still says "Search stopped" while the server keeps the answer

- Severity: minor
- Regression: no. Develop behaves the same; this phase kept it on purpose ("as it did before this card").
- What: if `stopRun` rejects (network error, 401 on an expired access token, 404), `stopCurrentRun`'s catch calls `stop()`, which closes the stream, and `deriveStopVerdict` falls back to `stopped`. The server never heard the stop, so the run finishes, and if it finishes inside the 30 second abandonment window its answer goes to history and session memory. The same holds for the 5 second fallback when the stop request succeeded as a no-op (`done` already buffered) but the stream stalled before delivering `done`.
- Reproduction: the author's own fourth arm (`stopRun` rejects, "Search stopped" shows) plus the server rule read from `run_registry.py` (an aborted subscriber only starts the abandonment clock). The server half is read, not probed.
- Why it matters: this is the defect class card 59 exists to close ("Search stopped" on screen, the answer kept in history and memory, the next "it" pointing at it), left open on the failure path. Now that the stream is no longer aborted on press, the client could keep reading after a failed stop request and let the server's own terminal event decide, instead of closing the stream.

### A-59-05: Stop can no longer end a run whose post-`done` write hangs

- Severity: minor (unsure it matters in practice)
- Regression: yes, a direct consequence of this phase's `cancel_run` change, and the intended trade
- What: once `done` is buffered, `cancel_run` never cancels. If the memory write or the `interactions` write then hangs (neither has its own timeout that I found), the run stays unfinished, still counts against the per-owner concurrent-run cap of 3, and no stop request can free it. On develop a stop cancelled it.
- Reproduction: the A-59-01 probe parks `_remember_turn` after `done`, calls the stop, and the task stays running until the probe releases the gate (`memory finished = 1`, `entry.cancelled = False`). The cap consequence is read, not probed. The abandonment timer still bounds it once the reader detaches after `done` (30 seconds of cumulative unwatched time), so the hold is bounded.
- Why it matters: during a database stall a person who stops and re-asks several times could hit "too many searches running" for up to about 30 seconds per held run. Low impact; filed so the trade is recorded rather than implicit.

## What held

Checked with my own probes (vitest files and pytest files outside the repository, run against this branch):

- Stop with the answer's sentence, citation and trust signal already arrived but no `done`: "Stopping…" with no sentence, source or trust line shown; the `cancelled` reply then shows "Search stopped" and still none of them.
- The same press with `done` arriving alone afterwards: the sentence, `source-1` and the trust line all show, and "Search stopped" never does.
- Stop, then a genuine fatal error instead of the cancel: "Search stopped", no server wording on screen. Same as develop.
- Stop, the answer arrives during the wait, no reply for 6 seconds: "Stopping…" for the whole wait with nothing of the answer shown, then the fallback "Search stopped". The screen never shows an answer under "Stopping…".
- Server, stop before `done` at four points in a real offline run (2, 4, 6 and 19 events in): no `done`, a `cancelled` last event, `entry.cancelled` true, no memory write, one capture call. A true stop is not weakened.
- Server, stop with `done` buffered and the memory write parked: the write finishes, no `cancelled` error follows `done`, `entry.cancelled` stays false.
- `tsc --noEmit` on the frontend is clean. The removed `eslint-disable` comments change nothing; the frontend has no ESLint config.

Read only, not probed: the history and memory writes on the pending-then-`done` path (the author's arms A1 and A2 cover them); reload during "Stopping…" (there is no run resumption, so the rail after reload shows the server's own record, consistent either way); two tabs (each tab owns its own run, so no shared stop state found).

## Verdict

FAIL, narrowly. The goal holds on the paths a person normally takes: a Stop after the server finished shows the whole answer with its sources and trust line, the server keeps that run in history and memory, and a true stop shows "Search stopped" and records nothing. Two regressions sit inside this phase's own fixes, which fires the review loop's stop condition:

- A-59-01 (major, regression, inside the server fix): GraphQL `stopRun` says `stopped: true` for a run the server now leaves alone.
- A-59-02 (major, rare trigger, regression, inside the client fix): a stop request that fails late aborts the next question's stream, freezing its screen while the server records its answer.

Both are one-line fixes. A-59-03 and A-59-05 are minor consequences of the same server change; A-59-04 is a pre-existing gap of the same class card 59 closes.

Worse than develop: yes, in the two narrow places above. Better than develop on the main path card 59 targets.
