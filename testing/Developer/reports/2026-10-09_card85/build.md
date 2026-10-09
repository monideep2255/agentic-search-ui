# Card 85 build: a failed search says which search and why

## Table of contents

- [Base](#base)
- [What changed](#what-changed)
- [Tests](#tests)
- [Mutation checks](#mutation-checks)
- [Test query](#test-query)
- [Deviations](#deviations)
- [Fix round](#fix-round)

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

## Fix round

Base: 86c30008. One round.

| Finding | Status | What changed |
|---|---|---|
| J-85-04 | Fixed | `test_a_real_runs_think_failure_line_carries_that_runs_own_trace_id` drives `run` and `run_streaming` with a failing Think call and pins one `step failed trace_id=own-trace-85 step=think` line. Removing the run's trace binding turns it red |
| A-85-03 | Fixed | The cause class is stripped to letters, digits, dots and underscores and cut to 60 characters; `error_class` goes through the same strip. A class name with a newline and an escape cannot forge a second line |
| J-85-02, A-85-07 | Fixed | Think's and the guardrail's "no usable reply" step errors write the same `step failed` line (`error_class=recoverable`, cause class the parse error's) through one helper, `_log_step_failed` |
| A-85-01, A-85-02 | Fixed | The cause is chosen the way Python reports it: explicit cause when `is not None`, else the context unless `from None` suppressed it |
| J-85-03 | Fixed for the new lines | Every new line spells the key `trace_id=`; the lines on the unusable paths use the same helper |
| J-85-01, A-85-05 | Open | Needs two streams advanced from one task; no caller does that (the run registry gives each run its own task). The line is no worse than develop, which logged nothing |
| J-85-05, J-85-06 | Open | J-85-05 is now covered by the context test; J-85-06 is a wording of an old test name, no behaviour |
| A-85-04, A-85-06, A-85-08 to A-85-12 | Open | Each is an extra on a path that develop did not log at all, or a crash-record detail card 73 already shipped. None makes a line less true than develop's |
| `call_log` trace key (`trace=`) | Open | Out of scope; `call_log.py` untouched |

Mutations, each broke one property, ran red, restored (16 selected tests, 6 + 1 + 1 + 1 + 2 + 2 failures):

| Break | Result |
|---|---|
| Run binds no trace id | 6 failed, 10 passed |
| Cause class not stripped | 1 failed, 15 passed |
| `from None` ignored | 1 failed, 15 passed |
| Truthiness instead of `is not None` | 1 failed, 15 passed |
| Think unusable line removed | 2 failed, 14 passed |
| Guardrail unusable line removed | 2 failed, 14 passed |

Runs: `test_run.py` 66 passed; step-failure tests in `test_graph.py` 7 passed; `tests/system_03_search_agent/core` 1415 passed, 56 skipped. ruff check clean on touched files; `gate02_import_order.sh` exit 0 (bare `isort --check-only` on `graph.py` also fails on develop's own file, an existing difference between the tool's config and the gate).
