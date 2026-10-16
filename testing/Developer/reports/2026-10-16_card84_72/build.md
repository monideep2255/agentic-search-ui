# Cards 84 and 72, step 3b: count first, build report

Owner's choice (2026-10-16): ship only a log line that counts real freezes, then decide with a week of data.

- New module `src/system_03_search_agent/adapters/web_sse/loop_stall.py`: one task per API process, looks of 50 ms, a look late by 0.25 s or more writes one INFO line.
- `app.py`: starts and stops the watcher inside `_lifespan` only.
- Switch: environment variable `LOOP_STALL_WATCH`, default on; "0", "false", "off", "no" turn it off.
- Line format: `loop stall: <seconds, 2 decimals> s, began <UTC time>`. Example: `loop stall: 0.40 s, began 2026-10-16T09:30:00Z`. Logger: the module name `system_03_search_agent.adapters.web_sse.loop_stall` (same `getLogger(__name__)` style as the guard and Jev call lines). No question text or user data.
- Tests: `tests/system_03_search_agent/adapters/web_sse/test_loop_stall.py`, 5 pass. Threshold mutated to 0: 2 tests went red, then restored.
- Gates: ruff check clean; isort clean; web_sse suite 144 passed (3 runs).
