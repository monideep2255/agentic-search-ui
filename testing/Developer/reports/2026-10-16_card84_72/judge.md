# Judge, PR 251, cards 84 and 72 step 3b (one log line per event loop stall)

Round 1, dial 2. Branch fix/card84-72-freeze-count at d68e6505, develop at bff040aa.

## Findings

### J-84S-01: On deployed develop the stall line is filtered out, so the count would read zero
- Severity: major
- What: The API configures no logging of its own. The INFO line is visible only because the MCP library sets the root logger to INFO with a Rich handler when the app is imported. On develop, `RUN_MIGRATIONS_ON_STARTUP` is set on the service (tracker/phase_4.15.md, "Set on a service, NOT in env.example"; docs/build/Debugging_guide.md row says "yes"). That path runs `alembic upgrade head` in the API process inside `_lifespan`, and `alembic/env.py` calls `fileConfig(alembic.ini, disable_existing_loggers=False)`. alembic.ini sets `[logger_root] level = WARNING` and swaps the root handler. From then on, every INFO line from a `system_03_search_agent.*` logger is dropped, including `loop stall: ...`. The watcher starts after the migration call, so it always runs under the WARNING root.
- Reproduction: a probe module that imports the branch's `app` and adds `GET /j84block` (an `async def` doing `time.sleep(0.4)`), run with the same shape as railway.json: `PYTHONPATH=src:<probe> python -m uvicorn j84probe:app`.
  - Without RUN_MIGRATIONS_ON_STARTUP: one request gives `INFO loop stall: 0.35 s, began 2026-10-16T15:21:16Z` on stderr.
  - With `RUN_MIGRATIONS_ON_STARTUP=1` and `USER_DB_URL` set to a scratch sqlite file (the migration fails on `CREATE EXTENSION` after fileConfig has already run, so it is never fatal): two requests to `/j84block`, both 200, give no `loop stall` line at all. The log shows the alembic-format lines (`INFO  [alembic.runtime.migration] ...`), then only uvicorn's own lines. Even the MCP `StreamableHTTP session manager started` INFO line vanishes after the migration.
  - LEARNINGS.md (2026-09-22, L-01) already records that develop's Railway deploy logs "hold only uvicorn access lines at the configured log level", which fits this.
- Why it matters: The owner's decision is "count first, then decide with a week of data". With this build, a week of develop logs would show zero stalls whether the server froze or not. That reads as "no freezes" and would steer the decision on cards 84 and 72 wrongly. Fix options for the lead, not chosen here: log at WARNING, or give the logger its own level and handler, or reset the root level after the migration. Not verified against the live Railway variables (no live calls); the evidence is the repository's own record of the service variables.
- NOT FIXED

### J-84S-02: Where the line does appear, the handler splits it over two log lines
- Severity: minor
- What: When the root logger is at INFO, the only root handler is the MCP library's Rich handler. It wraps output at 80 columns when stderr is not a terminal. The stall line comes out as two physical lines, `INFO     loop stall: 0.35 s, began          loop_stall.py:44` and then `2026-10-16T15:21:16Z` on its own line.
- Reproduction: the uvicorn probe in J-84S-01 without RUN_MIGRATIONS_ON_STARTUP, output redirected to a file. The file shows the line split exactly as quoted.
- Why it matters: On Railway each physical line is a separate log entry. A search for "loop stall" still counts stalls, but the start time sits in a separate entry with no marker of its own, so pairing a stall with the minute it happened is harder. This only matters once J-84S-01 is fixed. A fix that adds the logger's own plain handler would remove this too.
- NOT FIXED

### J-84S-03: Reported length runs short by up to one look, so the real threshold is about 0.27 to 0.30 s, not 0.25 s
- Severity: minor
- What: `late_s` is measured from when the 50 ms look started, minus 50 ms. If a block starts at the beginning of a look, the reported length is the block minus up to 50 ms. Blocks shorter than about 0.27 to 0.30 s are never logged, depending on where in the look they fall.
- Reproduction: a direct probe of `_watch` with `time.sleep(d)` inside a coroutine, 10 runs each. `d=0.4` gives `loop stall: 0.37 s` five times out of five (the uvicorn probe gave 0.35 s). `d=0.26` logs 0/10, `d=0.28` 10/10, `d=0.30` 10/10. The "began" stamp is the start of the look, not of the block, and it is truncated to whole seconds.
- Why it matters: Small. For counting user-visible freezes, a 0.25 s versus 0.28 s floor does not change the decision. The docstring and build report say "0.25 s or more" and "a stall of that excess", and the week's data will be read against those words. Say in the week's analysis that lengths run short by up to 0.05 s.
- NOT FIXED

### J-84S-04: "A loop busy in short chunks writes nothing" holds only for a single busy coroutine
- Severity: minor (documentation; the behaviour is right for the purpose)
- What: When several coroutines each run 0.1 s chunks with `sleep(0)` between them, their chunks queue ahead of the watcher's timer and add up. The watcher logs that as a stall.
- Reproduction: 4 coroutines, each 5 rounds of `time.sleep(0.1); await asyncio.sleep(0)`, run under `gather`. Output: `loop stall: 1.21 s` and `loop stall: 0.78 s`. One coroutine doing 20 rounds of `time.sleep(0.1); await asyncio.sleep(0.005)` logged nothing.
- Why it matters: For the owner's purpose this is correct, because other coroutines' timers really were held up that long. The docstring promise in `loop_stall.py` is too broad, though. A reader of the week's data could wrongly rule out "many short chunks" as a cause because the docstring says they never log.
- NOT FIXED

### J-84S-05 (note, no defect): back-to-back blocks reading as one stall is the right reading
- Severity: none, recorded because the brief asked for it
- What: `time.sleep(0.2); await asyncio.sleep(0); time.sleep(0.2)` logs one line, `loop stall: 0.37 s`. In the same pattern, a third coroutine's 10 ms timer, already pending, fired 0.404 s later. `sleep(0)` re-queues the busy coroutine ahead of any timer that falls due, so the loop never ran other timers between the two blocks. For "periods when other coroutines' timers could not run", one stall of about 0.4 s is the true count. Two lines would over-count.
- Cost: over 5 s idle, process CPU was 0.9 ms without the watcher and 11.4 ms with it. That is about 0.2 % of one core: negligible.

### J-84S-06: No test covers the try/finally that stops the watcher when the MCP lifespan fails
- Severity: minor
- What: `_lifespan` stops the watcher in a `finally`, so an exception from the MCP sub-app's lifespan still cancels it. My probe shows this works today (see "Startup and shutdown" below). But no test pins it: removing the `try/finally` and calling stop only after a clean exit leaves the whole web_sse suite green.
- Reproduction: in my detached worktree, I replaced the `try: ... finally: await stop_loop_stall_watch(stall_watch)` block with the `async with` block followed by a plain `await stop_loop_stall_watch(stall_watch)`. Result: `pytest tests/system_03_search_agent/adapters/web_sse -m "not integration"` gave `144 passed`. Restored with `git checkout`, worktree clean.
- Why it matters: the brief's own requirement ("an exception in the MCP lifespan still stops the watcher") rests on code no test protects. A later edit to `_lifespan` could drop it silently. The cost would be one orphan task logging stalls on a loop being torn down, so the impact is small.
- NOT FIXED

### J-84S-07: The tests cannot see the defect in J-84S-01
- Severity: minor (test design, the root of why J-84S-01 shipped)
- What: every stall test calls `caplog.set_level(logging.INFO, logger=LOGGER)`. That raises the module logger's own level, so the tests pass whatever the root logger's level is in a deployed process. No test asserts that the line survives the process's real logging setup, including the in-process alembic `fileConfig`.
- Reproduction: Mutation 1 (mine): `logger.info` changed to `logger.debug` gives `FAILED test_one_forced_block_logs_one_line`, `1 failed, 4 passed`, then restored to `5 passed`. So the tests do guard the level of the call. But the uvicorn probe in J-84S-01 shows the same INFO call dropped in a process that ran the startup migration, while all 5 tests pass on that same code.
- Why it matters: the green suite is evidence that the line is written, not that anyone can read it.
- NOT FIXED

## Checklist

| Item | Result | How |
|---|---|---|
| 1. Nothing a person sees changes; no guardrail change | Holds | The diff touches 4 files only: `web_sse/app.py` (lifespan only, plus an import), the new `web_sse/loop_stall.py`, the new test file and the build report. No frontend, prompt, guardrail, route or response file changes. My runs of `pytest tests/system_03_search_agent/adapters/web_sse tests/system_03_search_agent/guardrail -m "not integration"`: develop `561 passed`, branch `566 passed` (develop plus the 5 new tests), no failures on either tree. |
| 2. Line visible in develop's deployed logs | Fails, J-84S-01 | Start command: `alembic upgrade head && PYTHONPATH=src uvicorn ...:app --host 0.0.0.0 --port $PORT`, with no `--log-level` or `--log-config` and one process. The app calls no `basicConfig` and no `dictConfig`. Root becomes INFO only as a side effect of the MCP library's Rich handler. With `RUN_MIGRATIONS_ON_STARTUP` set, which the repository records as set on the deployed service, the in-process alembic `fileConfig` sets root to WARNING before the watcher starts. Reproduced locally with a scratch sqlite database: no line after two forced 0.4 s blocks. |
| 3. Startup and shutdown | Holds; one gap in tests (J-84S-06) | The watcher starts after the synchronous migration call, so the migration cannot log a stall against itself, and `create_task` does not block. I probed the real `_lifespan` with the MCP lifespan swapped out. In every case, normal exit, MCP raising on enter, MCP raising on exit and the app body raising (fresh process), the watcher ended `done=True cancelled=True` with no leftover tasks. Uvicorn shut down cleanly in the probe server. |
| 4. Measurement | Holds for the purpose; J-84S-03, J-84S-04, J-84S-05 | One 0.4 s block logs one line, 5 runs out of 5 (`0.37 s`; 0.35 s under uvicorn). One coroutine busy in 0.1 s chunks: nothing. Back-to-back blocks with only `sleep(0)` between them count as one, which is correct (J-84S-05). CPU about 0.2 % of one core. |
| 5. Break it | Done | Mutation 1, `logger.info` to `logger.debug`: red (1 failed), then restored green. Mutation 2, dropping the `try/finally`: stays green, filed as J-84S-06. Both worktree edits reverted with `git checkout`. |
| 6. Gates | Pass | `ruff check` with no path: "All checks passed!". `isort --check-only --diff src tests services tracker alembic .claude .github`: exit 0. pytest as in item 1. |

## Verified by my own probes versus only read

- Probed: line present under the plain uvicorn start (no migration); line absent after an in-process alembic `fileConfig` (scratch sqlite, no live database); Rich wrapping; length and threshold (10 runs per length); short chunks, back-to-back blocks, a third coroutine's timer delay, four concurrent chunkers; CPU cost; lifespan under four failure shapes; both suites on both trees; two mutations; ruff and isort.
- Only read, not probed: that `RUN_MIGRATIONS_ON_STARTUP` is actually set on the deployed develop service today. That comes from tracker/phase_4.15.md and docs/build/Debugging_guide.md, plus LEARNINGS.md's note that develop's deploy logs hold only uvicorn lines. No live Railway call was made. If the variable has since been removed, the line would appear (Rich-wrapped, J-84S-02), and J-84S-01 would fall to a latent risk. The lead can settle this with one read of the service's variables, or by checking whether today's develop logs carry the `StreamableHTTP session manager started` line after the alembic lines.
- Nothing in this round sits inside a fix made earlier in this phase; this is round 1 of the change.

## Verdict

FIX FIRST.

For a person using the product, nothing here is worse than develop: no visible change, no guardrail change, both suites green, the watcher is safe at startup and shutdown, and the cost is negligible. But the change exists only to produce a count, and on the deployed configuration the count would be zero no matter what the server does (J-84S-01). A week of that would read as "no freezes" and steer the owner's decision on cards 84 and 72 wrongly. That is a confident wrong record, which is worse than having no count. Fix J-84S-01 and add a test that holds the line across the process's real logging setup (J-84S-07). J-84S-02, 03, 04 and 06 are minor and can ride along or be noted.
