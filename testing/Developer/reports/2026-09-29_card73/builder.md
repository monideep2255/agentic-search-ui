# Card 73 builder report

Card 73: a crashed search writes its reason to a place a developer can find, so a crash like G-026's on 2026-09-29 (trace 2ff4e9d4) can be traced.

## What changed

- `src/system_03_search_agent/core/run.py:208`: new `_log_crash(trace_id, exc)`, one `logger.error` record.
- `src/system_03_search_agent/core/run.py:664`: `run()`'s last-resort handler now calls it before building the fallback events.
- `src/system_03_search_agent/core/run.py:852`: `run_streaming()`'s handler does the same.
- The person's screen and the event stream are unchanged: same error payload, same done event, same order.

## What the log line carries

- The trace id.
- The exception class as `module.QualName`.
- The class names down the cause and context chain, at most 8.
- The traceback frames as `file:line in function`, the last 30 at most.

## The redaction choice

- I chose to log no exception message and no source text at all, rather than route the message through a redaction.
- A redaction exists in `observability/audit.py` (`redact_params`, `_redact_value_string`), but its own docstring calls it "BEST EFFORT ... NOT a control" and pins a known open gap (F-5.0-19, a secret inside a URL-valued assignment passes through byte-identical). `audit` itself already refuses free-text errors and takes a class name only, and `feedback/writer.py` logs `type(exc).__name__`.
- A provider error can echo a key and a driver error can echo a connection string, so a best-effort scanner is not enough for the production-standards rule against secrets in logs.
- The record carries no `exc_info`, because the standard formatter would print the message in the traceback's last line.
- Cost: a developer sees where and what class, not the message text. The trace id joins to the LangSmith trace and the audit log for the rest.

## Tests

In `tests/system_03_search_agent/core/test_run.py`, two new tests, each run for both paths (`run` and `run_streaming`), 4 cases:

- One ERROR record per crash, carrying the trace id, `builtins.ValueError` and a frame; no `exc_info`; the fallback events are `error` then `done` with the unchanged generic message and `error_class` of `unexpected`.
- A crash whose message holds a key-shaped fake secret and a DSN password puts neither, nor the message text, in any captured log record. The fake key is assembled from parts so no scanner flags the test file.
- The three older crash-fallback tests still pass and pin the event stream.

## Break-it results

- Removed both `_log_crash` calls: 4 tests red (both new tests, both paths). Restored.
- Made the log line append `str(exc)`: the two secret tests red (both paths). Restored.

## Gate counts

- `test_run.py`: 36 passed.
- Full unit suite as `gate04_unit_suite.sh` runs it: 6548 passed, 143 skipped, 24 deselected, 1 xfailed, exit 0 (272 s).
- `ruff check .`: All checks passed, exit 0.
- `gate02_import_order.sh` (isort): exit 0.

## Debugging guide

Not edited. Its `core/run.py` rows (lines 160 and 276) say the synthetic pair appears on a crash, which is still true.
