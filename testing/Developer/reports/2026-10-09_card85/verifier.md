# Card 85 fresh verifier report

Fresh verifier, 2026-10-09. Checkout detached at 777b5d5edd0df3fef98e5c9ae3ad048bd2cda271 (expected 777b5d5e, matches). Change: `git diff origin/develop...HEAD`, commits 86c30008 and 777b5d5e (fix round).

## Findings and checks

### Test runs

- `tests/system_03_search_agent/core/test_run.py`: 66 passed in 3.64s.
- `tests/system_03_search_agent/core/test_graph.py`: 244 passed in 5.04s.
- `tests/system_03_search_agent/core` as a directory: 1415 passed, 56 skipped, 2 warnings in 59.41s.
- ruff check on the four changed Python files: All checks passed!

### Fix-round findings, each re-derived

Mutations: each applied by a string replace to the source, the two changed test files run together (310 tests), and the file restored from a byte backup. `git status --short` was empty after.

| Finding | Mutation | Result | Status |
|---|---|---|---|
| J-85-04 (real run's trace id unpinned) | `run()` binds `trace_id_scope(None)` (run.py:727) | 3 failed, 307 passed | Fixed |
| J-85-04 | `run_streaming` binds `set_trace_id(None)` (run.py:856) | 3 failed, 307 passed | Fixed |
| A-85-03 (forged line via class name) | cause class not stripped (graph.py:883) | 1 failed, 309 passed | Fixed |
| A-85-03 | cause class cap removed (graph.py:884) | 1 failed, 309 passed | Fixed |
| A-85-01 (`from None`) | suppress check removed (graph.py:873) | 1 failed, 309 passed | Fixed |
| A-85-02 (falsy cause) | `if exc.__cause__:` | 1 failed, 309 passed | Fixed |
| J-85-05 (context fallback) | `return None` instead of `__context__` | 1 failed, 309 passed | Fixed |
| J-85-02, A-85-07 Think | Think unusable line removed (graph.py:3988) | 2 failed, 308 passed | Fixed |
| J-85-02, A-85-07 guardrail | guardrail unusable line removed (graph.py:2107) | 2 failed, 308 passed | Fixed |
| same | guardrail unusable line passes `None` as cause | 2 failed, 308 passed | Fixed |
| same | guardrail unusable line logs `step=think` | 2 failed, 308 passed | Fixed |
| no-message rule | step line logs `str(cause)` | 7 failed, 303 passed | Held |
| crash line 1 | class taken from `str(exc)` | 6 failed, 304 passed | Held |
| crash line 1 | 30 character class cap removed | 1 failed, 309 passed | Held |
| A-85-03 second half | `error_class` not stripped (graph.py:895) | 310 passed | Behaviour fixed, unpinned (V-85-01) |

Direct probe, `_step_error_kwargs("think", e)` inside `trace_id_scope`, handler formatting `%(levelname)s %(name)s %(message)s`:

- `from None` over a KeyError context: `step failed trace_id=T-A01_fromNone step=think error_class=transient cause_class=none`.
- Falsy explicit cause over a ValueError context: `... cause_class=Falsy`.
- Class named `"Timeout\nWARNING core.graph step failed trace_id=OTHER-RUN\x1b[31m" + "C"*400`: one physical line, `... cause_class=Timeout_WARNING_core.graph_step_failed_trace_id_OTHER_RUN__3` (60 characters, no newline, no escape).
- Implicit context, no `from`: `... cause_class=KeyError`.
- The exception messages carried the marker text in every case; it appeared in no line.

End to end probe, appended to `test_run.py` temporarily so its fixtures applied (file restored from backup after). Four searches run at once, each in its own task, through both `run` and `run_streaming`: one with an unusable guard reply, one with an unusable Think reply, one whose Think call raises `RuntimeError`, one normal; the question text carried a marker. Output, both paths identical:

```
step failed trace_id=tid-alphaq step=guardrail error_class=recoverable cause_class=ClassificationUnavailableError
step failed trace_id=tid-bravoq step=think error_class=recoverable cause_class=ThinkClassificationUnavailableError
step failed trace_id=tid-charlq step=think error_class=unexpected cause_class=RuntimeError
```

2 passed. The normal search logged no step line; no step line held the question marker, the reply marker or the exception marker, none had `exc_info`, none had a newline.

Hand-built step errors in `src`: `grep '"scope": "step"'` finds three, graph.py:926 (the shared helper), 2111 and 3992; the last two are now preceded by `_log_step_failed`. No step error path is left without a line.

### V-85-01: the `error_class` strip added in the fix round is not pinned by any test

- Severity: minor
- What: the fix round runs `error_class` through the same character strip as the cause class (graph.py:895). Reverting that one expression to `str(error_class)` leaves all 310 tests in the two changed files green.
- Reproduction: mutation "M11 error_class not stripped" above: `310 passed in 6.36s`. Behaviour with the strip in place, probe: `HarnessCallError("m", error_class="private question text\nINJ step failed trace_id=OTHER")` logs one line, `step failed trace_id=T-A04_badclass step=think error_class=private_question_text_INJ_step_failed_trace_id_OTHER cause_class=none`, then `KeyError` escapes (A-85-04, still open).
- Why it matters: the property is true today and every constructor in `src` passes a literal from the closed set, so nothing a person sees or a log reader reads is wrong. It is a test gap inside the fix commit, not a wrong line. Not worse than develop.
- NOT FIXED

### Worse than develop

- Exception message or user text on a log line: not found. Every new line logs only the trace id, a step name, a closed-set or stripped class, and a class name. Probed above with markers in the question, the reply and the exception.
- Forged line: the step line can no longer be forged by a class name (probe above). Crash record line 1 (A-85-11, open) can be forged by a class name with a newline, but develop's own record already could: develop's `_crash_record` with the same class gives lines `['search crashed, trace 8f1c2d3e-...', 'exception_class=__main__.Boom', 'search crashed trace_id=OTHER error_class=Fake', 'chain=__main__.Boom']`. Same reach, not worse.
- Another run's trace id: only when two `run_streaming` generators are advanced from one task (J-85-01, A-85-05, open). Develop logged no step line at all there. With one task per search, the shape `run_registry` uses, every line carried its own id (probe above).
- Updated assertions: read against the diff. `startswith("search crashed trace_id=")`, `f"trace_id={query.trace_id}" in first`, the size ceiling test's whole-line equality now including `error_class=ValueError`, and the fallback's `trace_id=` key each pin as much or more than before. Only the length bound moved, 80 to 120. A real UUID line is 83 characters (probe: `A12 len: 83`), so the old 80 bound could not hold with the class on line 1; this is the open J-85-06 and A-85-12, a trade the card made on purpose.

### Items left open, each against develop

| Item | Against develop |
|---|---|
| J-85-01, A-85-05 one task, two runs | Develop logged no step line; not worse |
| J-85-03, A-85-09 three trace key spellings | Develop had two; the new key is on lines develop did not write |
| J-85-06, A-85-12 line 1 past 80 characters | The trace id still leads line 1; the class is extra. Not worse for the id |
| A-85-04 unknown error class | Logs a stripped line, then the same `KeyError` crash develop had; latent, every constructor uses the closed set |
| A-85-06 raising log filter | Same risk as every other `logger.warning` in graph.py; no filter in `src` |
| A-85-08 `source` not logged | Develop logged nothing |
| A-85-10 nested class name cut on line 1 | Line 2 carries the full name, as on develop |
| A-85-11 newline class forges crash line 1 | Develop forged the same line one line lower (probe above) |

### What I verified and what I only read

- Verified by my own probes: every fix-round finding (15 mutations, direct probe, end to end concurrent probe through both entry points), the no-message rule on the new lines, the develop comparison for A-85-11, the line length.
- Only read: that `run_registry` gives each search its own task, and that surfaces mint the trace id server side (web_sse app.py:1475, graphql schema.py:306, `Query.trace_id` capped at 64).

## Verdict

MERGE (nothing worse than develop). Every finding the fix round claims is fixed is fixed, each confirmed by a mutation going red. One minor test gap inside the fix commit (V-85-01), not a wrong line.
