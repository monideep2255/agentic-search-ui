# Adversary round, PR 251, cards 84 and 72 step 3b (freeze count log line)

Dial position 2. Branch fix/card84-72-freeze-count at d68e6505, develop at bff040aa. Written 2026-10-16.

## Findings

### A-84S-01: The line reaches the deployment's log only because the MCP library calls `logging.basicConfig(level="INFO")` as a side effect of import; nothing in the PR pins that, and the repository's own call-log module says INFO is dropped
- Severity: minor (major if the dependency changes; the count would read zero, which looks like "no freezes")
- What: `loop_stall` logs at INFO. The service configures no root level itself. `harness/call_log.py` states in its module docstring that "Python's default (WARNING) drops INFO lines before they reach the deployment's log", which is why call lines are WARNING. In fact the root is INFO today, because `adapters/mcp/server.py` line 556 constructs `MCPServer(...)`, whose `__init__` calls `mcp.server.mcpserver.utilities.logging.configure_logging(self.settings.log_level)`, i.e. `logging.basicConfig(level=<MCP log_level, default INFO>, format="%(message)s", handlers=[RichHandler or StreamHandler])`.
- Reproduction: probe `p1_visible.py` (applies uvicorn's default `LOGGING_CONFIG`, imports the app, forces a 1.0 s `time.sleep` under the watcher). Output: `root level: INFO effective for watcher: INFO root handlers: [<RichHandler (NOTSET)>]` then `INFO loop stall: 0.97 s, began 2026-10-16T15:32:09Z`. Probe `p2_who.py` (spies on `basicConfig` and root `setLevel`) shows the only caller is `mcp/server/mcpserver/utilities/logging.py` line 39, reached from `adapters/mcp/server.py` line 556.
- Why it matters: the owner's decision is made from a week of these lines. If the MCP SDK stops configuring logging, its `log_level` setting is raised to WARNING by environment, or the MCP mount moves, the line silently disappears and a week of "zero freezes" is indistinguishable from "no freezes". No test proves the line reaches a handler the deployment reads: the five tests use `caplog.set_level(INFO, logger=...)`, which sets the level itself, so they pass whatever the deployment's level is. Two documents in the repository now disagree about whether INFO reaches the log. The build report's "same style as the guard and Jev call lines" is not true: those lines are WARNING because of this exact concern.
- Unsure, local only: with `rich` installed (it is here, pulled in by `pip_audit`, not by `requirements.txt`), the RichHandler wraps the line at 80 columns when stderr is not a terminal, so `began <time>` lands on a second physical line. Production installs from `requirements.txt` and probably has no `rich`, so production probably gets the plain `%(message)s` StreamHandler. Not verified on the deployment (no live calls).
- NOT FIXED

### A-84S-02: A loop busy in short chunks does write "loop stall" lines; one task yielding every 0.1 s is logged as a 0.26 s stall, five such tasks as one 1.50 s stall, and the test that claims otherwise is shaped so it cannot see it
- Severity: major (the count is the whole deliverable, and this is the "could not tell a busy server from a frozen one" mechanism the design names as a cause of the 8 October failure)
- What: the module docstring says "A loop busy in short chunks under 0.25 s writes nothing". That is false whenever the busy task is ready again at once (yields with `await asyncio.sleep(0)`, awaits a done future, or several questions are busy together). asyncio appends a due timer behind the handles already in the ready queue, and the watcher's own wake-up then runs one more iteration later, behind the busy task again. So a look is late by up to about three chunks, and with N busy tasks by about 3 x N x chunk. No single block of the loop is anywhere near 0.25 s, yet lines are written, and the reported length is several times the longest block.
- Reproduction: probe `p3_busy.py`, part A, watcher running, N tasks each looping `time.sleep(0.1); await asyncio.sleep(0)` for 2 s:
  - N=1: `6 lines ['loop stall: 0.27 s, ...', 'loop stall: 0.26 s, ...', 'loop stall: 0.26 s, ...']`
  - N=2: `4 lines ['loop stall: 0.59 s', 'loop stall: 0.58 s', 'loop stall: 0.58 s', ...]`
  - N=3: `3 lines ['loop stall: 0.96 s', 'loop stall: 0.88 s', 'loop stall: 0.27 s']`
  - N=5: `2 lines ['loop stall: 1.50 s', 'loop stall: 0.87 s']`
  The author's `test_short_blocks_log_nothing` uses `await asyncio.sleep(0.01)` between its 0.1 s chunks, which lets the watcher's timer win the queue, so the test passes on exactly the code that writes the lines above. If the test's 0.01 is changed to 0, the same code writes lines (part A, N=1).
- Why it matters: the owner chose "Ship only a log line that counts real freezes, then decide with a week of data". A week in which several questions run CPU work in 0.1 s pieces at once reads as a week of 0.5 to 1.5 s "freezes", which is exactly the range in which the parked allowance design (2 s) looks worth building. The count can make the case for step 3b by itself. It is real timer lag on the loop, so it is not pure noise, but it is not "a stretch when the event loop runs nothing", which is what the line says it counts, and nothing in the line lets a reader tell the two apart.
- NOT FIXED

### A-84S-03: Stalls between 0.25 s and 0.30 s are missed or under-reported depending on where they land in a look; the line reports lateness, not the block's length
- Severity: minor
- What: a block of B seconds that starts just after the watcher re-arms makes the look late by about B minus 0.05, so the line's figure is up to 50 ms short of the block, and a block of 0.25 to about 0.30 s can write nothing.
- Reproduction: probe `p3_busy.py`, part B, one `time.sleep(B)` placed about 1 ms after a look starts, 5 runs each: `0.26 s: logged in 0/5`, `0.28: 5/5`, `0.29: 4/5`, `0.30: 5/5`, `0.31: 5/5`.
- Why it matters: small next to A-84S-02, and well under the 2.6 s that the design says changes a verdict. Worth one sentence in the build report: the threshold is "late by 0.25 s", not "blocked for 0.25 s".
- NOT FIXED

### A-84S-04 (no defect, recorded as a probe result): A sustained or very long stall does not flood the log
- Severity: none, recorded so the claim is on file as checked
- Reproduction: probe `p3_busy.py`, part C, one task blocking in 0.30 s chunks for 10 s writes `11 lines`, in 0.26 s chunks `13 lines`, about one per second at most. A single long block writes one line (probe `p1_visible.py`, a 1.0 s block wrote one line, `0.97 s`). Each look can write at most one line, and a line needs at least 0.25 s of lateness, so the ceiling is about 4 lines a second however the loop is blocked.
- NOT FIXED (nothing to fix)

### A-84S-05: `stop_loop_stall_watch` swallows a cancellation aimed at its caller, so a lifespan cancelled during shutdown keeps running instead of being cancelled
- Severity: minor (unsure on real impact: uvicorn's normal shutdown is message driven and does not cancel the lifespan task)
- What: `with contextlib.suppress(asyncio.CancelledError, Exception): await task`. If the task awaiting the watcher (the lifespan, after this PR's `finally`) is itself cancelled in that window, the CancelledError it receives is suppressed and it continues past the `finally` as if nothing happened. On Python 3.11+ the task is left with `cancelling() == 1` and is not cancelled. On develop the lifespan's exit has no such await, so a cancellation propagates.
- Reproduction: probe `p5_cancel.py`: outer task awaits `stop_loop_stall_watch(t)`, is cancelled one loop step later. Output: `{'after_stop': 'outer kept running after it was cancelled', 'end': 'outer finished normally'} o.cancelled()= False o.cancelling()= 1`.
- Why it matters: anything that tears down the app by cancelling the lifespan (an anyio task group in a test harness, a supervisor, a future server) gets a lifespan that ignores the cancel. Here it only means the generator finishes normally, which is harmless today, so this is filed as minor and unsure. The usual pattern is to suppress only when the watcher was cancelled, or to check `asyncio.current_task().cancelling()` and re-raise.
- NOT FIXED

### A-84S-06: A process suspended from outside (container paused by the host, SIGSTOP, a VM stalled) is logged as a "loop stall" of the full suspension
- Severity: minor (unsure whether the deployment's host ever does this)
- What: lateness is measured on `time.monotonic()`, which keeps running while the process is stopped but the system is not suspended. A pause of the whole process by the host is counted the same way as the app blocking its own loop. A laptop going to sleep is not counted: on both macOS and Linux the monotonic clock Python uses stops during system suspend (read, not run, because putting this machine to sleep would end the round). Wall clock jumps cannot produce a line: wall time is used only for the `began` stamp.
- Reproduction: probe `p6_sigstop.py` run as a child, `kill -STOP` after 0.8 s, `kill -CONT` 2.0 s later. Output: `loop stall: 1.99 s, began 2026-10-16T15:35:08Z`. The app did nothing during those 2 s.
- Why it matters: for a person waiting on an answer a host pause is a real freeze, so counting it is arguable. But step 3b's allowance cannot help with it (every clock and every socket freezes together), and the line does not say which kind it was. If the host pauses the container (for example during a live migration), the week's count includes freezes the planned fix does nothing about.
- NOT FIXED

### A-84S-07 (no defect, recorded as a probe result): A real uvicorn server starts, answers and shuts down as on develop; startup order is unchanged
- Severity: none
- Reproduction: probe `p7_uvicorn.py` runs `uvicorn.Server` on the app with `lifespan="on"`, waits for `/health`, sets `should_exit`. Branch, 8 runs: `health 200`, shutdown 0.125 to 0.208 s, only `MainThread` left. Develop, 4 runs: `health 200`, shutdown 0.161 to 0.179 s. No stall line at startup or shutdown. One early branch run did not reach `/health` and took 11.6 s; it did not reproduce in 8 more runs on fresh ports and is most likely a port clash in my probe, but it is recorded here rather than dropped.
- Startup order, read: `_run_startup_migrations_if_requested()` still runs first and synchronously, before the watcher, so a slow migration is not counted. The MCP sub-app's lifespan is entered after the watcher starts and exited before the watcher stops. If entering the MCP lifespan raises, the `finally` still cancels the watcher (read, not run). The railway start command has no `--workers`, so one watcher per deployment. With several workers there would be one watcher each, and the line carries no process id.
- User data, read: the line's only arguments are a float and a UTC stamp. The task is created in the lifespan's context, so no request context variable is in scope. No question text can reach it.
- NOT FIXED (nothing to fix)

### A-84S-08: The lifespan test passes with the stop call deleted, and the five tests pass with the monotonic clock swapped for wall time
- Severity: minor (test gap, not a runtime defect; it bears on the build report's claim that the tests prove start and stop)
- What: `test_lifespan_starts_and_stops_watch` asserts `started[0].done()` after the `TestClient` block. The test client's event loop thread cancels any task left on the loop when it shuts down, so the watcher is `done()` whether or not the lifespan stops it. Nothing tests that the line is measured on a clock that cannot jump.
- Reproduction: copies of the branch's `src` and test file in a scratch folder, author's tests run unchanged:
  - Unmutated: `5 passed`.
  - Mutation 1, in `app.py` replace `await stop_loop_stall_watch(stall_watch)` with `pass`: `test_lifespan_starts_and_stops_watch`, 4 runs out of 4, `1 passed`. The full file also passed (`....` then the fifth test passed on rerun). One early run looked hung; that was my probe killing it 0.2 s after it started, not a hang, and is recorded here so it is not mistaken for one.
  - Mutation 2, in `loop_stall.py` replace every `time.monotonic()` with `time.time()`: `5 passed`.
- Why it matters: the build report lists "starts and stops the watcher inside `_lifespan`" and "5 pass" as evidence. Its own mutation (threshold to 0) went red, but a deleted stop and a wall clock, which would turn a clock adjustment by NTP or by hand into a logged "stall", both stay green. Under uvicorn the stop is real (A-84S-07: the task is cancelled before the loop closes), so this is a missing guard, not a present bug.
- NOT FIXED

### A-84S-09: The full unit suite, run exactly as CI gate04 runs it, has 3 failures on the branch and 0 on develop
- Severity: critical for merge (the CI gate is red; no runtime harm)
- What: the build report's gate line is "web_sse suite 144 passed (3 runs)", which is one folder, not gate04 (`pytest -m "not integration" -q`). Over the whole suite:
  1. `tests/.../web_sse/test_loop_stall.py::test_lifespan_starts_and_stops_watch` fails with `RuntimeError: StreamableHTTPSessionManager .run() can only be called once per instance. Create a new instance if you need to run again.` The app's MCP sub-app is a module-level singleton. An earlier test in the same process has already run `app`'s lifespan, so this test's `with TestClient(app)` cannot enter it again. The test passes alone and in its own folder and fails in suite order, so it depends on test order.
  2. `tests/system_03_search_agent/test_debugging_guide_coverage.py::test_every_source_file_has_a_row`: `1 source file(s) have no row in the debugging guide ... Missing: ['src/system_03_search_agent/adapters/web_sse/loop_stall.py']`.
  3. `tests/system_03_search_agent/test_debugging_guide_coverage.py::test_manifest_covers_every_source_file`: `The manifest and the source tree disagree ... Extra items in the right set: 'src/system_03_search_agent/adapters/web_sse/loop_stall.py'`.
- Reproduction: in a detached worktree at the branch head `d68e6505`, `pytest -m "not integration" -q -p no:cacheprovider`: `3 failed, 7800 passed, 143 skipped, 24 deselected, 1 xfailed in 504.23s`. The same command in a detached worktree at develop `bff040aa`: `7798 passed, 143 skipped, 24 deselected, 1 xfailed in 502.23s`.
- Why it matters: worse than develop. The PR cannot pass gate04 as built. Failure 1 is inside the PR's own new test, and fixing it means the test must not drive the real app's lifespan a second time in one process (or it must run the lifespan on a fresh MCP instance). Failures 2 and 3 need the debugging guide row and the regenerated manifest that the repository requires for every new source file.
- NOT FIXED

- CI confirmation for A-84S-09 (read-only `gh` query): PR 251's check "Python gates (1, 2, 3, 4, 6, 9)" is `fail`. Its failed log reads `3 failed, 7800 passed, 143 skipped, 24 deselected, 1 xfailed`, and the three failures are the same three tests named above, including the same `RuntimeError: StreamableHTTPSessionManager .run() can only be called once per instance`.

## Verdict

FAIL.

What is worse than develop:
- A-84S-09: CI gate04 goes from 0 failures to 3, confirmed locally and on the PR's own CI run. One failure is the PR's own lifespan test, which depends on test order (it drives the real app's single MCP session manager a second time in one process). The other two are the missing debugging guide row and manifest entry for `loop_stall.py`.

What makes the count lie, judged against the owner's words "a log line that counts real freezes":
- A-84S-02 (major): a loop busy in short chunks writes lines. One task yielding every 0.1 s is logged as a 0.26 s stall, and five such tasks as one 1.50 s stall, while no block of the loop reaches 0.25 s. The module docstring says the opposite, and the test that claims it uses a 10 ms sleep between chunks, which hides it. A week of data could therefore argue for step 3b on load rather than on freezes.
- A-84S-01 (minor): the line is visible only because the MCP library calls `logging.basicConfig(level=INFO)` at import. `harness/call_log.py` says INFO is dropped, and no test covers it.
- A-84S-06 (minor, unsure): a host pausing the process counts as a stall.
- A-84S-03 (minor): blocks of 0.25 to 0.30 s can be missed, and the figure the line prints is up to 50 ms short of the block.

Smaller: A-84S-05, the stop swallows a cancellation aimed at its caller. A-84S-08, the lifespan test passes with the stop call deleted, and all tests pass on wall time.

Checked and clean: no flood (A-84S-04, at most about one line a second under sustained blocking, and one line per long block). Shutdown time and thread state under real uvicorn match develop (A-84S-07). Migration and MCP ordering are unchanged. No task per request. No question text or user data is ever in the line. The watcher cannot raise into the app: the only await is `asyncio.sleep`, and logging is inside `suppress(Exception)`. It runs once per lifespan.

Verified with my own probes:
- Line visibility under uvicorn's default logging, and who sets the root level (p1, p2).
- Busy loop, threshold edge and flood (p3).
- Swallowed cancellation (p5).
- SIGSTOP counted as a stall (p6).
- Real uvicorn start and shutdown, branch against develop (p7).
- Two mutations of the author's tests.
- The full gate04 suite on both trees, and the PR's CI log.

Only read, not run:
- Behaviour when the MCP lifespan raises on entry.
- Laptop sleep not counted (from how the monotonic clock behaves on macOS and Linux).
- Absence of user data (from the code).
- Production's handler being a plain StreamHandler, because `rich` is not in `requirements.txt`.
- One worker on Railway (from `railway.json`).

None of these findings sits inside a fix made during an earlier round of this phase; this is the first review of the build.
