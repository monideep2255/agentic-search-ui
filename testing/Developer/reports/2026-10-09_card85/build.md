# Card 85 build: a failed search says which search and why

## Table of contents

- [Base](#base)
- [What changed](#what-changed)
- [Tests](#tests)
- [Mutation checks](#mutation-checks)
- [Test query](#test-query)
- [Deviations](#deviations)

## Base

Branch `fix/card85-logging-gaps`, cut from `origin/develop` at `d5dcc02c41a148f39c243ae2df4a03d5a53b94fd`. Scope is the diagnosis column "Logs: V01 and J06" only. No model call was made.

## What changed

- `core/run.py`, `_crash_record`: line 1 is now `search crashed trace_id=<id> error_class=<ClassName>`. The class is the short name, cut to 30 characters (`_CRASH_LOG_FIRST_LINE_CLASS_CHARS`), so the line stays short. The fallback line ("crash record could not be built") uses `trace_id=` too.
- `core/graph.py`, `_step_error_kwargs`: logs one warning, `step failed trace_id=<id> step=<step> error_class=<class> cause_class=<class>`. The trace id comes from the audit ContextVar the run already binds (`audit.current_trace_id()`), because the function has no trace id argument and its callers sit inside the guardrail, which this card must not edit. It never logs the exception's message and passes no `exc_info`.
- Untouched, as asked: `_write_answer`, `_answer_tokens`, `write_node`, `act_node`, every guardrail function, the five `exc_info=True` warnings, `harness/call_log.py`.

## Tests

- `tests/system_03_search_agent/core/test_run.py`: 60 passed in 3.06s.
- `tests/system_03_search_agent/core/test_graph.py`: 240 passed in 4.68s.
- `tests/system_03_search_agent/core` as a directory: 1405 passed, 56 skipped, 2 warnings in 60.76s.
- New in `test_run.py`: line 1 names the trace id and the class (and not the message); a very long class name is cut. Four existing assertions that pinned the old `search crashed, trace <id>` wording and a 80 character bound now pin `trace_id=` and a 120 character bound.
- New in `test_graph.py`: a step failure logs exactly one warning with the trace id, step, `error_class` and the cause's class; a second test puts a marker string in the exception message and the cause, and proves it is in no log line and no record carries `exc_info`.
- ruff check clean on the touched Python files; isort --check-only clean on them; `bash .github/gates/gate02_import_order.sh` exit 0.

## Mutation checks

Each broke one property, ran red, and was restored by the inverse edit:

| Break | Result |
|---|---|
| Line 1 without `error_class=` | 4 failed, 56 passed in `test_run.py` |
| Line 1 with the id but no `trace_id=` key | 4 failed, 56 passed in `test_run.py` |
| Step warning logs `str(exc)` instead of the cause class | 2 failed, 1 passed (step tests) |
| Step warning removed | 2 failed, 1 passed (step tests) |

## Test query

Nothing a person sees changes: this card changes log lines only. No line was added to `testing/Test_queries_and_workflows.md`.

## Deviations

- The trace id reaches `_step_error_kwargs` through the audit ContextVar, not a new argument, to avoid editing the guardrail's calls. Outside a run it logs `trace_id=none`.
- The guardrail step already logs its call outcome through `call_log`; a guardrail failure now also gets this warning, so that one failure has two lines (outcome, then class). Think and Write get their first.
- Write's failure is logged where `_write_answer` calls `_step_error_kwargs` (graph.py line 13164 region) with no edit to `_write_answer`.
- The first attempt at a mutation check used `git checkout` on a source file and wiped its edits; they were reapplied and the full test run was repeated after.
