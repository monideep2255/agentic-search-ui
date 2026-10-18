# Fix round, PR 251 (cards 84 and 72, step 3b)

Tests: `tests/system_03_search_agent/adapters/web_sse/test_loop_stall.py` (10 pass). Each fix was checked by mutating the code back and watching its test go red.

| Finding | Result | Test |
|---|---|---|
| A-84S-09 (CI red), A-84S-08 first half, J-84S-06 | FIXED. The MCP sub-app lifespan is stubbed, `_lifespan` is driven directly, the stop call is spied and must run once, also when the MCP lifespan raises. Debugging guide row and manifest entry added (manifest regenerated, one line added). | `test_lifespan_starts_and_stops_watch`, `test_lifespan_stops_watch_when_mcp_lifespan_fails` (red with the stop call deleted) |
| J-84S-01, A-84S-01, J-84S-02 | FIXED. Level is WARNING (the `harness/call_log.py` convention: the service sets no root level and alembic's `fileConfig` leaves the root at WARNING). Test uses root at WARNING with its own handler and no `caplog.set_level`, and asserts one physical line. | `test_line_reaches_root_handler_at_warning_on_one_line` (red at INFO) |
| A-84S-02, J-84S-04, A-84S-06 | FIXED in words, measurement unchanged. Line: `event loop lag: 0.40 s (timers ran late), began ...`. The docstring says a frozen loop, several busy tasks and a paused host all produce it. | `test_one_task_with_short_blocks_and_real_gaps_logs_nothing` (renamed, honest claim), `test_several_busy_tasks_do_produce_a_line` |
| A-84S-05 | FIXED. `stop_loop_stall_watch` re-raises when the current task is being cancelled. | `test_stop_passes_on_a_cancel_aimed_at_the_caller` (red with the check removed) |
| A-84S-08 second half | FIXED. | `test_measurement_ignores_wall_clock_jumps` (red on wall time) |
| J-84S-03, A-84S-03 | FIXED in words. Docstring: threshold is "timers late by 0.25 s or more", the figure can be up to 0.05 s short, "began" is the start of the look. | none (documentation) |

No guardrail code and no user-visible text changed. `app.py` is untouched in this round.
