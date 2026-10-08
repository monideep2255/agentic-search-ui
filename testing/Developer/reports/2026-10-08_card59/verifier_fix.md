# Card 59 fix round: fresh verifier's report

Verifier of the fix round on branch `fix/card59-stop-after-answer` at 83bfc071, pull request #208 against `develop`. Findings are appended as they are established.

## Findings

### VF-59-01: the post-done memory and history writes have no timeout of their own, but they block the whole event loop, so develop could not free them either
- Severity: minor (pre-existing; recorded because it answers the fix round's named trade)
- Regression: no. Measured identical on this branch and on develop.
- What: the three database calls a finished run makes after `done` (the session memory locked update, `core/session_memory.py` `_PostgresSessionMemoryStore.update` about line 646, and the two inserts in `feedback/writer.py` `_write_interaction_row` about line 341, retried up to three times by `write_interaction` about line 394) are synchronous SQLAlchemy calls inside `async def` functions, with no `await` that suspends. The engine (`data/base.py` `create_user_db_engine`, about line 52) sets only `pool_pre_ping`: no `statement_timeout`, no `lock_timeout`, no `connect_timeout`, no asyncio timeout anywhere on the path. The only bounds are SQLAlchemy's default pool checkout wait (30 s) and the operating system's TCP behaviour on a dead connection, which is minutes. The analytics call that follows (`observability/analytics.py`, `CAPTURE_TIMEOUT_SECONDS = 4.0`, line 126) is the only awaited step after `done`, and it is bounded.
- Consequence for the trade in `fix.md`: because the call blocks the event loop, neither the stop endpoint nor the abandonment timer can run while it hangs, on this branch or on develop. Develop's "freed after about 30 seconds" applied only to a hang at a real `await`, which the shipped post-done path does not contain (apart from the 4 s analytics call). So a person is not blocked from asking, or shown a cap error, for longer than on develop. What they see during a database hang, on both, is the whole server worker frozen for every user until the call returns.
- Reproduction: own probes in a private folder, run against an export of this branch and of `origin/develop`, the 4.16 premise fixtures, `RunRegistry(abandon_grace_seconds=0.3, max_active_runs_per_owner=1)`, a reader that stops at `done`, and a ticker coroutine measuring the longest event-loop stall.
  - Shipped writes, `session_scope` replaced by a database whose memory row lock and history inserts each sleep 1.5 s: branch "calls=['memory.load(no hang)', 'memory.get', 'history.insert', 'history.insert'] held after done 4.54s longest loop stall 4.54s cancelled=False last=['cost', 'done']"; develop "held after done 4.55s longest loop stall 4.54s cancelled=False last=['cost', 'done']". Identical.
  - A blocking 2 s memory write (`time.sleep`): branch "run held after done 2.02s ... longest loop stall 2.01s; memory written=True"; develop "2.03s ... 2.02s; memory written=True". Identical.
  - Only an awaited 2 s hang (`asyncio.sleep`, the shape the author's tests park on) differs: branch "run held after done 2.02s; cap refused new question until 1.97s; memory written=True"; develop "run held after done 0.32s; cap refused new question until 0.26s; memory written=False; cancelled=True; last events=['cost', 'done', 'error']". That difference does not occur with the shipped store.
- Why it matters: the trade the fix round named as the owner's to confirm is, measured, not a change for a real database hang. The real exposure is pre-existing and larger: one hung user-database statement freezes every user's stream in that worker, with no timeout to end it. Worth a card of its own (a `statement_timeout` and `connect_timeout` on the user engine, or the writes moved off the event loop), not a blocker for this pull request.
- NOT FIXED

### VF-59-02: three comments still describe the old stop contract
- Severity: minor (documentation; no behaviour)
- Regression: introduced by this fix round's contract change, not by code behaviour.
- What: after A-59-03 the REST stop answers `stopped: false` for a finished run, and after J-59-02 the abandonment timer no longer cancels a run that sent `done`. Three comments still say otherwise:
  - `frontend/src/lib/api.ts` lines 166 to 170: "calling this on an already-finished or already-stopped run still returns `{stopped: true}`". Named in `fix.md` as left for later.
  - `frontend/src/components/chat/StopButton.tsx` line 203: "a repeat or late call still returns `{stopped: true}`". Not named in `fix.md`. (The component is not rendered by `App.tsx`; only its tests and `deriveStopVerdict` are used.)
  - `core/run_registry.py` module docstring, lines 60 to 63: "a run is cancelled once its CUMULATIVE unwatched time ... reaches `abandon_grace_seconds`", with no mention that a run that already sent `done` is now exempt. The exemption is stated only on `_cancel_unless_finished` and `_cancel_if_still_abandoned`.
- Reproduction: `grep -n "stopped: true" frontend/src/lib/api.ts frontend/src/components/chat/StopButton.tsx` at 83bfc071 prints both lines; `sed -n 60,63p src/system_03_search_agent/core/run_registry.py`.
- Why it matters: the next person reading the client or the registry is told the opposite of what the server does, the shape that produced A-59-01 in the first place.
- NOT FIXED

### VF-59-03: the J-59-01 test change is unproven as a flake fix and couples the arm to real time
- Severity: minor, unsure
- Regression: no behaviour change; a test-only change made in this fix round.
- What: `frontend/src/App.stopUntilAnswer.test.tsx` about line 340 now installs `vi.useFakeTimers({ shouldAdvanceTime: true })` before the ask. `fix.md` says the original failure was not reproduced (10 of 10 green before the change). With `shouldAdvanceTime` the fake clock moves with wall time, so on a slow machine the screen can walk forward during `askAndLetTheWholeRunArrive()` itself; if the first sentence lands before the arm's first check ("Stop was grey with no answer on screen") that check fails, the opposite direction of the original flake. I did not reproduce such a failure.
- Reproduction: own runs of the file in a copy of the branch's frontend on this loaded machine: 5 of 5 runs "Tests 7 passed (7)". Nothing red observed; filed on reading, for the closer to judge.
- Why it matters: if it flakes again, it will look like card 58 regressing.
- NOT FIXED

## Re-derivation of the fix round's claims

Each claimed fix was re-derived with my own mutation, applied to an export of 83bfc071 outside the worktree, the source restored after each. Every mutation was killed by the arm named, with the arm's own assertion message, not an import or setup error.

| Finding | Code at 83bfc071 | My mutation | Result |
|---|---|---|---|
| J-59-04, A-59-02 | `frontend/src/App.tsx` lines 1612 to 1617: `pressedOn` read at the press, `stop()` only if `askSeq.current === pressedOn` | catch back to `() => stop()` | killed: "A's failed stop closed question B's stream: expected true to be false" |
| same | same | `pressedOn` read inside the catch (a guard that can never differ) | killed, same message |
| same, other side | same | catch never calls `stop()` (develop's shape) | killed by "a stop the server never receives falls back to Search stopped"; card 58's file stays green |
| A-59-01 | `adapters/graphql/schema.py` lines 401 to 403, `stopped = default_registry.cancel_run(resolved)` | back to reading `task.done()` beside the cancel | killed: C2 "stopRun said stopped for a run whose answer the server kept" |
| A-59-03 | `adapters/web_sse/app.py` lines 1897 and 1898 | back to `StopRunResponse(stopped=True)` | killed: C3 and the idempotency arm |
| J-59-02 | `core/run_registry.py` line 815, `_cancel_unless_finished(entry)` in `_cancel_if_still_abandoned` | timer back to `entry.task.cancel()` | killed: C1 "the abandonment timer ended the run while it was saving an answer the reader already has" |
| D18 guard | `core/run_registry.py` lines 697 to 715 | drop the `done` check | killed: A1 |
| `cancel_run`'s answer | `core/run_registry.py` line 1105 | always `True`; always `False` | both killed (A1; the REST still-running arm) |
| J-59-06 M1 | `App.tsx` lines 1057 to 1061 | fallback effect returns at once | killed: "Stopping… never ended without a reply" |
| J-59-06 M7 | `App.tsx` line 1106 | `stopped: stopped` | killed: "a sentence appeared while Stop was awaiting the server" |
| J-59-06 M6 | `App.tsx` line 1045 | `streamError = rawStreamError` | killed: "a confirmed stop showed a failure notice" |
| J-59-01 | test-only change | not mutable; see VF-59-03 | 5 of 5 whole-file runs green |

`askSeq` coverage, read: `runId` is set non-null only at `App.tsx` line 1495, inside the one ask function, after `++askSeq.current` at line 1361 and a `seq` check; sign-out moves `askSeq` at line 813 and clears `runId` at line 829. So every path that opens a new stream (landing ask, inline follow-up, Run again, history reopen, tour) moves `askSeq` first. "New search" alone moves neither, and the run on screen is still A, so a late failure closing A is correct.

## The named trade: a hung write after done

See VF-59-01. Bound found: none of its own. No `statement_timeout`, `lock_timeout`, `connect_timeout` or asyncio timeout on the user database path; only SQLAlchemy's default 30 s pool checkout wait and the operating system's TCP limits. The analytics call after it is bounded at 4 s. Because the shipped writes are synchronous calls inside the event loop, a hang freezes the worker for everyone and neither Stop nor the abandonment timer can act, on develop exactly as on this branch: measured 4.54 s held on this branch against 4.55 s on develop for three 1.5 s hung calls. The 30 s release `fix.md` attributes to develop only happens for a hang at a real `await`, which the shipped store does not have. Not worse than develop.

## Screen, history and memory across orders

- Server, read and probed: `done` is appended to `entry.events` with no `await` between the generator's `yield` and the append (`_drain_into_entry`, about line 631), and every reader takes events from `entry.events`. So when a stop is handled, either `done` is on the read path and nobody cancels, or no reader can have it and the cancel produces the `cancelled` error, a `refuse` row and no memory turn. `_cancel_unless_finished` is now the only task cancel in the registry (grep of `task.cancel()` under `src/`).
- Surfaces, own probe with a real registry and a run held before `done`: GraphQL `stopRun` and REST stop each answered `True` on the running run, `True` again when repeated before the task unwound, `False` once it had ended; the run is `cancelled` with error class `cancelled`. After `done` both answer `False` (C2, C3, and my mutations). CLI prints "run was already finished" for `False` (`adapters/cli/main.py` line 957) and its Ctrl-C path ignores the value. The web client never reads the body (`StopRunResponse` is typed but unused). Shapes unchanged: GraphQL `runId`, `stopped`; REST `stopped`.
- Client: the J-59-04 arm and my three mutations of it. Paths left open and unchanged from develop, as named in `fix.md`: A-59-04 / J-59-05 (a failed stop reads "Search stopped" while the server may keep the answer), J-59-07, J-59-03, J-59-08.

## Test counts

| Suite | Result |
|---|---|
| `tests/system_03_search_agent/core -k "run_registry or cancel or stop"` | 55 passed, 1386 deselected |
| `adapters/graphql/test_types.py`, `adapters/web_sse/test_streaming_endpoints.py`, `adapters/cli/test_main.py`, `adapters/cli/test_client.py` | 188 passed |
| `frontend/src/App.stopAfterAnswer.test.tsx` | 7 passed, 5 of 5 runs |
| `frontend/src/App.stopUntilAnswer.test.tsx` | 7 passed, 5 of 5 runs |
| `frontend/src/components/chat/StopButton.test.tsx` | 32 passed |
| `tsc -b` (frontend), `ruff check` on the changed Python | clean |
| `git merge-tree` against `origin/develop` | merges clean |
| Own server probes (hang timing on branch and develop, shipped writes with a hanging database, stop surfaces) | 4 probe files, all ran; results in VF-59-01 and above |
| Mutations | 6 server, 6 client: 12 of 12 killed |

## Verdict

MERGE WITH NAMED ITEMS.

Worse than develop: no.

- Named items: VF-59-01 (pre-existing, a card of its own: a timeout on the user database engine, or the writes moved off the event loop); VF-59-02 (three stale comments, one line each).
- Inside this fix round's own changes: VF-59-02 (comments made stale by the round's contract change) and VF-59-03 (the J-59-01 test change, unsure). Neither is a behaviour defect, both are minor; the closer should judge whether that fires the review loop's stop condition.
- Verified with my own probes: every row of the mutation table; the hang timing and the absence of any timeout bound (VF-59-01, both variants); the stop surfaces' answers for a running, a re-stopped and a finished run; the test counts, type check, ruff and merge.
- Read only, not probed: the `askSeq` coverage of every ask path (no inline follow-up driven); the CLI's printed message against a real server (the CLI test fakes the client); the analytics 4 s bound in practice; VF-59-03's flake risk.
