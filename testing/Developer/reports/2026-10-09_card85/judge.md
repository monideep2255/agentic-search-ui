# Card 85 judge report, round 1

Base: HEAD 86c30008 on fix/card85-logging-gaps, diff against origin/develop. Findings are appended as they are established.

## Findings

### J-85-01: two runs driven from one task log the other run's trace id
- Severity: minor (unsure; the production shape is not affected)
- What: `_step_error_kwargs` reads the trace id from the audit ContextVar (graph.py, the new `logger.warning` in `_step_error_kwargs`). `run_streaming` binds it with a bare `set_trace_id` inside an async generator (run.py:856), which writes into the context of whoever drives the generator. Two `run_streaming` generators advanced alternately from the same task share one context, so the later `set_trace_id` wins for both.
- Reproduction: a throwaway probe (deleted after) built two `run_streaming` generators with trace ids `AAA` and `BBB`, the model stub raising `RuntimeError` on every non-guard call, and advanced them alternately with `__anext__` from one task. Output: `PROBE3: ['step failed trace_id=BBB step=think error_class=unexpected cause_class=RuntimeError', 'step failed trace_id=BBB step=think error_class=unexpected cause_class=RuntimeError']`. Run AAA's failure is logged under BBB and AAA never appears.
- The production shape is fine: eight `run_streaming` runs each in its own `asyncio.create_task` (the shape `core/run_registry.py:628` and `:1025` use) logged `trace-0` to `trace-7` once each, and eight `run()` calls under `asyncio.gather` logged `r-0` to `r-7` once each. So this needs a consumer that merges two runs in one task, which no caller does today as far as I found.
- Why it matters: the card's promise is "the log line says which search". It holds per task, not per run. The existing audit trail (`record_tool_call`) has the same dependency, so this is not new risk, but the new line inherits it silently.
- Smallest fix: none required for merge. A one-line note in `_step_error_kwargs`'s docstring that the id is per task, or a test that pins the per-task shape, would stop a future merge-two-runs consumer from being surprised.
- NOT FIXED

### J-85-02: a step that fails on an unusable reply gets no `step failed` line
- Severity: minor
- What: two step failures build their step error by hand instead of through `_step_error_kwargs`, so the new warning never fires for them: Think's "both replies unusable" (graph.py:3954, `"source": "think"`) and the guardrail's "no usable verdict" (graph.py:2074, `"source": "guardrail"`). The person gets a step error; the log gets no `step failed trace_id=... step=... error_class=...` line.
- Reproduction: probe (deleted after) with the guard stub compliant and every other model reply `"not json at all"`, trace id `UNUSABLE-1`. Output: `PROBE4 ERROR EVENTS: [('step', 'think', 'recoverable')]` and `PROBE4 step failed lines: []`. The run's lines that name the trace are the older per-attempt ones, `think classification unusable (attempt 2 of 2, trace UNUSABLE-1): the plan tier did not return valid JSON for ...` (key `trace`, not `trace_id=`).
- Why it matters: an operator who greps `step failed` or `trace_id=` to find every failed step misses this class of failure, which is one of the more common ones (a model reply that is not JSON). The trace is still findable by its raw id, so it is not lost, which is why this is minor.
- Smallest fix: emit the same `step failed trace_id=%s step=%s error_class=recoverable cause_class=<parse error class>` warning on those two return paths (a small helper both call), and a test that drives an unusable reply twice and asserts one `step failed` line.
- NOT FIXED

### J-85-03: the same failure carries two different trace keys
- Severity: minor (unsure it is in scope)
- What: for a guardrail call failure the two lines are `model call point=guardrail.classify trace=GUARD-1 ... outcome=error` (`harness/call_log.py`, untouched) and `step failed trace_id=GUARD-1 step=guardrail ...` (new). A search for `trace_id=GUARD-1` finds only the second.
- Reproduction: probe (deleted after) with every model call raising `ValueError("SECRET-GUARD-abc")`, trace id `GUARD-1`. Records printed: `WARNING system_03_search_agent.harness.call_log model call point=guardrail.classify trace=GUARD-1 kind=guard elapsed_ms=0 outcome=error attempt=1 provider=unknown` then `WARNING system_03_search_agent.core.graph step failed trace_id=GUARD-1 step=guardrail error_class=unexpected cause_class=ValueError`. The doubled line the build note describes is real and is exactly these two; the secret was in neither (`PROBE5 SECRET in caplog.text: False`).
- Why it matters: "traced in one read" holds if the reader searches by the raw id, not by the `trace_id=` key the card introduces. Build note says `call_log.py` was out of scope, so this may be accepted as is.
- Smallest fix: none required for this card; note it on the board if `call_log` should move to `trace_id=`.
- NOT FIXED

### J-85-04: no test pins that a real run's step failure logs that run's trace id
- Severity: major (a test gap on the card's central promise; the code is correct today)
- What: the only test of the new line's trace id binds it by hand with `trace_id_scope("trace-card85")` and calls `_step_error_kwargs` directly (test_graph.py, `test_a_step_failure_logs_one_warning_with_the_trace_id_step_and_both_classes`). Nothing drives a step failure through `run()` or `run_streaming()` and checks the id. So if the run stops binding the ContextVar, or a refactor moves the graph into a context that does not inherit it, every step failure logs `trace_id=none` and the suite stays green.
- Reproduction: mutation runs against `test_graph.py` plus `test_run.py` (restored after each, `git diff --stat HEAD` empty):
  - baseline: `300 passed in 5.55s`
  - run.py:856 `set_trace_id(query.trace_id)` changed to `set_trace_id(None)`: `M12 run_streaming binds no trace id => 300 passed in 7.24s`
  - run.py:727 `trace_id_scope(query.trace_id)` changed to `trace_id_scope(None)`: `M13 run() binds no trace id => 300 passed in 6.76s`
  - for contrast, the hand-bound unit test does catch a constant: `M1 step warning trace id constant => 1 failed, 299 passed`
- Why it matters: "the log line says which search" is exactly the property that would silently become `trace_id=none`, and this repository's history is that the unpinned part is the part that regresses.
- Smallest fix: one async test in `test_run.py` that drives `run_streaming` with a think-tier failure (the shape `test_step_failure_on_think_routes_to_write_as_a_refusal` already uses) and asserts exactly one `step failed trace_id=<query.trace_id> step=think` line. My probe of that shape passed on this branch, so the test should go in green and turn red under M12.
- NOT FIXED

### J-85-05: the `__context__` fallback for the cause class is untested
- Severity: minor
- What: `cause = exc.__cause__ or exc.__context__` in `_step_error_kwargs`. Dropping the `or exc.__context__` leaves every test green.
- Reproduction: `M6 cause only __cause__ not __context__ => 300 passed in 5.24s`. The new test helper `_step_failure` raises with `from cause`, so it only exercises `__cause__`.
- Why it matters: a `HarnessCallError` raised inside an `except` without `from` would log `cause_class=none` instead of the real class, and nothing would notice. Today's `call_tier` raise uses `from exc` (harness.py:707 to 712), so this is a latent gap, not a live one.
- Smallest fix: a second case in the helper that raises inside `except` with no `from`, asserting the cause class.
- NOT FIXED

### J-85-06: the 80 to 120 character change loosens the "never wraps" promise, and one test name still says eighty
- Severity: minor (unsure)
- What: card 73 bounded line 1 under 80 characters so "a log handler that wraps long lines can never split it" (commit da0fe4b0). This card moves the bound to 120 in three assertions (test_run.py:955, :981, and the new long-class test). By construction line 1 is at most 24 + 48 + 13 + 30 = 115 characters, so the 120 bound pins the caps correctly, and mutations M8 and M9 (removing either cap) each turned one test red. But a real line with a 36 character UUID and `ValueError` is 83 characters, already past 80, so under an 80 column wrap the class lands on a continuation. The new comment at run.py:218 says the line "stays short enough not to wrap", which is not true at 80.
- Reproduction: arithmetic from run.py:277 to 280; `len("search crashed trace_id=") == 24`, `len(" error_class=") == 13`. The test at test_run.py:974 is still named `test_a_very_long_trace_id_still_leaves_a_first_line_under_eighty_characters` and asserts `< 120`.
- Were the four updated assertions weakened? Three are stronger or equal: the `startswith` and fallback assertions now pin the `trace_id=` key, the size ceiling test now pins the whole line including `error_class=ValueError` by equality, and the first-line test adds `f"trace_id={query.trace_id}" in first` (the id with its key) and `error_class=ValueError`. Only the length bound moved, from 80 to 120, which is the change the new content needs.
- Why it matters: if the deploy platform splits records at a fixed width near 80, trace and class can be split, which is the case card 73 guarded against. I could not verify the platform's width.
- Smallest fix: rename the test to say 120, and either reword the run.py:218 comment or confirm the log platform's split width.
- NOT FIXED

## Checklist with evidence

| Item | Result | Evidence |
|---|---|---|
| Line 1 of a crash record carries the trace id and the class | Verified by probe | Graph replaced by one that raises `LookupError("SECRET-CRASH-777 user text")`, run through both `run_streaming` and `run` with a real UUID: line 1 was `'search crashed trace_id=0d3a461e-08f4-4c78-ae4b-0ebd393c8928 error_class=LookupError'` (84 characters) both times; `PROBE7 secret anywhere: False`. Code: run.py:277 to 280. |
| A step failure logs one warning with trace id, step, error class and cause class | Verified by probe for guardrail, think and write; not true for the two unusable-reply step failures (J-85-02) | Think: `step failed trace_id=trace-0 step=think error_class=unexpected cause_class=RuntimeError`, one per run. Write: `PROBE8 step failed: ['step failed trace_id=W-1 step=write error_class=unexpected cause_class=ConnectionError']`. Guardrail: `step failed trace_id=GUARD-1 step=guardrail error_class=unexpected cause_class=ValueError`. Code: graph.py `_step_error_kwargs`. |
| Never the exception's message | Verified by probe | The `HarnessCallError` message carries the cause text (`... unexpected error (RuntimeError): SECRET-PROBE-xyz`, harness.py:707 to 712). After each failure I searched the whole formatted log text, tracebacks included: `PROBE6 SECRET in any formatted log text: False`, `PROBE5 SECRET in caplog.text: False`, `PROBE8 secret anywhere: False`. The new warning passes no `exc_info`. |
| Right run's trace id under concurrent runs | Verified by probe for the production shape; fails for two runs in one task (J-85-01) | 8 `run_streaming` runs in their own tasks logged `trace-0` to `trace-7` once each; 8 `run()` runs under `gather` logged `r-0` to `r-7` once each. Two generators advanced from one task logged `BBB` twice and `AAA` never. |
| The doubled guardrail line | Verified by probe | Exactly two lines for one guardrail failure, the `call_log` outcome line and the new `step failed` line (J-85-03 notes the differing keys). |
| Four updated assertions | Read and mutated | Not weakened in what they pin; only the length bound moved, 80 to 120 (J-85-06). |
| Each control breaks a test | Mutated, 13 runs | Red: M1 trace constant (1 failed), M2 cause none (1), M3 `exc_info=True` (1), M4 `str(cause)` (2), M5 step dropped (1), M7 class from message (6), M8 class cap off (1), M9 trace cap off (1), M10 class on line 2 (4), M11 fallback key (3). Green, so unpinned: M6 `__context__` fallback (J-85-05), M12 and M13 run-level binding removed (J-85-04). |
| Test runs | Run once | `tests/system_03_search_agent/core`: `1405 passed, 56 skipped, 2 warnings in 69.19s`. Changed files: `300 passed in 5.55s`. ruff on the four changed Python files: `All checks passed!` |

Verified by my own probes: crash line 1 content and length on both entry points; one step line per failure for guardrail, think and write; the no-message rule over the full formatted log; concurrency, both shapes; the doubled guardrail line; the unusable-reply gap; the 13 mutations. Read only: the claim that the five `exc_info=True` warnings, `_write_answer`, `act_node` and the guardrail functions are untouched (the diff touches only `_step_error_kwargs`, the import, and run.py's crash lines, so I accept it from the diff); the build note's own mutation table, which I did not reuse.

The tree was restored after every mutation (`cp` from a backup), the probe file was moved out of the checkout, and `git diff --stat HEAD` is empty at 86c30008.

## Verdict

FIX FIRST: J-85-04. The code does what the card says in the shape production runs, and I found no leak of the exception's message. But the card's central promise, that the line names the right search, is unpinned end to end: removing the run's trace binding leaves every test green. One run-level test closes it. J-85-02 (no `step failed` line for an unusable-reply step failure) is the next most useful fix and could ride in the same round; J-85-01, 03, 05 and 06 are minor and can merge as they are.
