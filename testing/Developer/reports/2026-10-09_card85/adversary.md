# Card 85 adversary report

Base: 86c30008 (fix/card85-logging-gaps), compared with origin/develop. One round. Findings are appended as they are established.

## Findings

### A-85-01: a step failure raised "from None" logs the class the code chose to hide

- Severity: minor
- Where: `core/graph.py`, `_step_error_kwargs`, the new line `cause = exc.__cause__ or exc.__context__`. New code in this card.
- What: the cause lookup ignores `__suppress_context__`. When a `HarnessCallError` is raised `from None` inside an `except KeyError` block, the log names `KeyError` as the cause. `core/run.py`'s own `_next_link` (card 73) respects `__suppress_context__` for exactly this reason, so the two new log lines in this card disagree on what "the cause" is.
- Reproduction: inside `trace_id_scope("T1")`, call `_step_error_kwargs("think", e)` where `e` was made by `try: raise KeyError("x") except KeyError: raise HarnessCallError("m", error_class="transient") from None`. Output: `WARNING system_03_search_agent.core.graph step failed trace_id=T1 step=think error_class=transient cause_class=KeyError`. Python's own traceback for the same exception prints no cause at all.
- What it means for the person reading the log: the line names a reason that is not the reason. A developer chases a `KeyError` that the raising code had already handled and deliberately dropped. No raise site in `src` uses `from None` today (`grep -rn "raise HarnessCallError" src` shows three sites, all with `from exc` or no cause), so this is latent.
- NOT FIXED

### A-85-02: a falsy exception as the explicit cause is skipped, and the line names the wrong cause

- Severity: minor
- Where: `core/graph.py`, `_step_error_kwargs`, `exc.__cause__ or exc.__context__`. New code in this card.
- What: `or` tests truthiness. An exception object can be falsy (a class with `__bool__` or `__len__` returning false). Then the explicit `__cause__` is skipped and `__context__` is logged instead. `core/run.py`'s `_next_link` docstring says, in this repository's own words, "`is not None`, never truthiness: an exception object can be falsy". The new code does the thing that docstring forbids.
- Reproduction: `class FalsyCause(Exception): __bool__ = lambda self: False`. Then `try: raise ValueError("ctx") except ValueError: raise HarnessCallError("m", error_class="transient") from FalsyCause("real cause")`, caught as `e`, and `_step_error_kwargs("write", e)` inside `trace_id_scope("T2")`. Output: `step failed trace_id=T2 step=write error_class=transient cause_class=ValueError`. The real cause is `FalsyCause`. With no context present the same falsy cause logs correctly (`cause_class=FalsyCause`), so the bug shows only when both are set.
- What it means for the person reading the log: the "why" on the line is a different exception from the one that caused the failure. Latent with today's litellm classes, which are truthy, but it is the exact mistake card 73 fixed one file over.
- NOT FIXED

### A-85-03: the step failure line prints the cause's class name raw: a newline forges a second log line, an escape reaches the terminal, and there is no length cap

- Severity: minor
- Where: `core/graph.py`, `_step_error_kwargs`, `type(cause).__qualname__` passed straight to `logger.warning`. New code in this card. The crash record in `run.py` caps names at 100 and line 1 at 30; this line has no cap and neither path strips control characters.
- What: a class name is code-written, but it is not limited to printable text. `type()` accepts any string, and a third party library or a dynamically built exception class (some SDKs build error classes from server error codes) can carry anything.
- Reproduction: `Odd = type("Timeout\nWARNING core.graph step failed trace_id=OTHER-RUN", (Exception,), {})`, raised and wrapped `from` into a `HarnessCallError`, logged inside `trace_id_scope("T4")`. Output, two physical lines:
  `WARNING system_03_search_agent.core.graph step failed trace_id=T4 step=think error_class=transient cause_class=Timeout`
  `WARNING core.graph step failed trace_id=OTHER-RUN`
  With `type("\x1b[31mBoom", ...)` the line carries `cause_class=^[[31mBoom` (raw ESC, shown here through `cat -v`). With `type("C"*400, ...)` the line carries all 400 characters.
- What it means for the person reading the log: a line that names a run that never failed, which is the one thing this card exists to prevent ("which search"). Unlikely in practice since the cause classes today are litellm's; filed because the card's other line (`run.py`) caps and the step line does not, and a `grep trace_id=OTHER-RUN` would find a forged hit.
- NOT FIXED

### A-85-04: an error class outside the known set now logs "step failed" first and then crashes the step, so one failure leaves two disagreeing lines

- Severity: unsure
- Where: `core/graph.py`, `_step_error_kwargs`. The new warning runs before `_STEP_ERROR_END_USER_MESSAGES[exc.error_class]`, and it prints `exc.error_class` unescaped.
- What: `HarnessCallError.__init__` does not validate `error_class` at run time (only a type hint). A value outside the dict logs the step failure, then `KeyError` escapes the function, the node raises, and the run's crash path fires. On develop the same input produced only the crash record.
- Reproduction: `e = HarnessCallError("m", error_class="private question text\nINJ")`, `_step_error_kwargs("think", e)` inside `trace_id_scope("T9")`. Output: `WARNING ... step failed trace_id=T9 step=think error_class=private question text` then a second physical line `INJ cause_class=none`, then `KeyError: 'private question text\nINJ'` propagating out.
- What it means for the person reading the log: a "step failed, think" warning followed by a "search crashed" record for the same trace, describing one event as two different kinds of failure. Unsure because every constructor in `src` passes a literal from the closed set today.
- NOT FIXED

### A-85-05: two streamed searches advanced from one task log one search's failure under the other search's trace id

- Severity: minor (major if any surface ever drives two `run_streaming` generators from one task)
- Where: `core/graph.py`, `_step_error_kwargs`, reading `audit.current_trace_id()`. New code in this card. Root cause is older: `run_streaming` binds the ContextVar with a bare `set_trace_id` inside an async generator, and an async generator has no context of its own, so the value lands in whichever task calls `__anext__`. The new line inherits that, while every node that calls `_step_error_kwargs` already holds the run's own `trace_id` as a local (`guardrail_node`, `think_node` and `_write_answer` all pass `trace_id` to `_dispatch_tier_call` a few lines above), so the ContextVar was a choice, not a necessity.
- What: with two `run_streaming` generators advanced alternately by one task, both failures carry the second run's id.
- Reproduction: temporary test in the checkout (deleted after). litellm mocked: guard call compliant, Think call for "alpha question about something" raises `CauseA`, for "bravo question about something" raises `CauseB`. Two generators, `run_streaming(Query(text=alpha, trace_id="trace-A"))` and `run_streaming(Query(text=bravo, trace_id="trace-B"))`, advanced with `await g.__anext__()` alternately in one coroutine. Captured lines:
  `step failed trace_id=trace-B step=think error_class=unexpected cause_class=CauseA`
  `step failed trace_id=trace-B step=think error_class=unexpected cause_class=CauseB`
  Control: the same three searches through `asyncio.gather` (one task each), 6 seeds of random awaits, both `run` and `run_streaming`, 12 of 12 passed with every line carrying its own trace id and cause.
- What it means for the person reading the log: a failure of search A is filed under search B, and search A shows no failure at all. The card's promise, "says which search", is broken silently. Production surfaces I checked (`run_registry` uses one `asyncio.create_task` per run) do not do this today, so this is latent; filed because the line now trusts a value that a calling pattern can corrupt, where a local that cannot be corrupted was in reach.
- NOT FIXED

### A-85-06: a failure inside logging now turns a step error into a crash, where the crash logger in the same card swallows it

- Severity: minor (unsure on reach)
- Where: `core/graph.py`, `_step_error_kwargs`. The new `logger.warning` call has no guard. `core/run.py`'s `_log_crash` wraps its own `logger.error` in two nested `try` blocks with the comment "nothing here may cost the person the error event". The two new log lines in this card take opposite positions on the same risk.
- What: a `logging.Filter` that raises propagates out of `Logger.warning` (handlers' `emit` errors go through `handleError`, filters do not). Before this card, `_step_error_kwargs` did no logging and could not fail this way.
- Reproduction: `g.logger.addFilter(Boom())` where `Boom.filter` raises `RuntimeError("filter broke")`; then `_step_error_kwargs("think", HarnessCallError("m", error_class="transient"))` inside `trace_id_scope("T")`. Output: `ESCAPED RuntimeError filter broke`, no step error returned. Same filter on `core.run`'s logger with `_log_crash("T", ValueError("v"))`: `crash path: swallowed`.
- What it means for the person typing the question: their Think or Write failure would show the generic "failed unexpectedly" pair instead of the step's own message and retry hint. For the reader of the log, the step line is gone and a crash record names `RuntimeError` from a logging filter, not the model failure. Production today runs uvicorn with no filters on these loggers (`railway.json` start command, no `basicConfig` or `dictConfig` in `src`), so reach is limited to a future log filter, for example a redaction filter.
- NOT FIXED

### A-85-07: two of the step failures a person can see still log no "step failed" line

- Severity: minor
- Where: `core/graph.py`. Guardrail's "no usable verdict" step error (the dict literal after `if classifier_verdict is None:`) and Think's "classification is None" step error (the dict literal in the Think classification helper) are built by hand, not through `_step_error_kwargs`, so the card's new line never fires for them.
- What: the person gets an error event with `scope=step`, and the log holds per-attempt lines but no line saying the step failed.
- Reproduction: temporary test through `core.run.run`, litellm mocked, query `trace_id="trace-W"`.
  Think reply "not json at all": error events `[('think', 'recoverable', 'step')]`; warnings from `core.graph` are only `think classification unusable (attempt 1 of 2, trace trace-W): ...` and the same for attempt 2. No `step failed` line.
  Guard reply "not json at all": error events `[('guardrail', 'recoverable', 'step')]`; only `guard classification unusable (attempt 1 of 2, trace trace-W)` and attempt 2. No `step failed` line.
  Controls in the same test: a price gap logs `step failed trace_id=trace-W step=guardrail error_class=unexpected cause_class=none`; a Think timeout logs `step failed trace_id=trace-W step=think error_class=transient cause_class=TimeoutError`.
- What it means for the person reading the log: a search for `step failed` finds some step failures and not others, and the missing ones are the commonest model failure (an unusable reply). The ticket says "a step fails, the log line says which search and why"; for these two the reader must know to look for a different phrase in a different key format (see A-85-09).
- NOT FIXED

### A-85-08: when the failure has no cause, the line's "why" is empty, and the field that does say why (`source`) is not logged

- Severity: minor
- Where: `core/graph.py`, `_step_error_kwargs`. Logs `error_class` and `cause_class`, not `exc.source`.
- What: several `HarnessCallError`s carry no cause: the price gap (`source="harness.harness._price_per_token"`), the guardrail's own "budget spent before the classifier could be asked" (`source="core.graph.guardrail"`). For these the line says `cause_class=none`, and `error_class` is one of three words. `exc.source` is a code-written string that names exactly where it failed and is already curated (no message text), and it is left out.
- Reproduction: `get_model_info` patched to raise and the model absent from the fallback table, query `trace_id="trace-W"` through `core.run.run`. The only line: `step failed trace_id=trace-W step=guardrail error_class=unexpected cause_class=none`. Nothing on it separates a missing price from any other "unexpected" failure with no cause. The guardrail's synthetic budget error would read `error_class=transient cause_class=none`, the same as any other causeless transient.
- What it means for the person reading the log: "which search" yes, "why" no. The reader must reproduce the failure to learn it was a pricing gap, which is the situation card 73 and F-3.4-A-07 describe as the reason for these logs.
- NOT FIXED

### A-85-09: one failed search now writes its trace id in three formats, so one grep does not find the whole story

- Severity: minor
- Where: the card moves two lines to `trace_id=<id>` and leaves the rest of the run's warnings as they were.
- What: in one failed run the same id appears as `trace=trace-W` (`harness/call_log.py`), `trace trace-W` (`core/graph.py` guard and Think "unusable" lines, the guard retry lines), and `trace_id=trace-W` (the new step line, the crash record, and `core/run.py`'s capture and analytics lines).
- Reproduction: the Think-unusable run in A-85-07, every WARNING from `system_03*` loggers:
  `model call point=guardrail.classify trace=trace-W kind=guard ...`
  `think classification unusable (attempt 1 of 2, trace trace-W): ...`
  `interaction capture failed for trace_id=trace-W`
  A grep for `trace_id=trace-W` returns the last line only, which says nothing about why.
- What it means for the person reading the log: "traced in one read" holds only if the reader greps the bare id. The new `trace_id=` key invites a keyed search that misses the lines carrying the reason. Unsure whether the card meant to cover these, but the test pins only the two changed lines.
- NOT FIXED

### A-85-10: the crash record's line 1 cuts the class's qualified name from the front, so a nested class loses its own name

- Severity: minor
- Where: `core/run.py`, `_crash_record`, `_clip(type(exc).__qualname__)[:_CRASH_LOG_FIRST_LINE_CLASS_CHARS]`. New code in this card. The build report calls this "the short name"; `__qualname__` is not the short name for a class defined inside a function or another class, `__name__` is.
- What: the 30 character cut keeps the head, which for a nested class is the enclosing function and `<locals>`, and drops the tail, which is the class itself.
- Reproduction: `def make(): class ProviderResponseValidationError(Exception): pass; return ProviderResponseValidationError`, then `_crash_record("8f1c2d3e-0000-4000-8000-123456789abc", make()("x"))`. Line 1: `search crashed trace_id=8f1c2d3e-0000-4000-8000-123456789abc error_class=make.<locals>.ProviderResponse`. Line 2 has the whole name, so nothing is lost overall, only the "one read" promise of line 1. For an exception group line 1 reads `error_class=ExceptionGroup` and the members are three or more lines down; unsure whether any real crash arrives as a group.
- What it means for the person reading the log: line 1, the line built to be read alone, names a function and half a class. A reader scanning first lines across many crashes sees a truncated name that matches no class in the code by grep.
- NOT FIXED

### A-85-11: line 1 of the crash record now carries a class name, so a newline in a class name forges a whole "search crashed" first line

- Severity: minor (partly pre-existing)
- Where: `core/run.py`, `_crash_record`. Before this card line 1 held only the trace id; the class name sat on line 2 and the chain line, both already unescaped (pre-existing, card 73). This card adds the class name to line 1 with no control-character handling.
- Reproduction: `Odd = type("Boom\nsearch crashed trace_id=OTHER error_class=Fake", (Exception,), {})`, then `_log_crash("8f1c2d3e-0000-4000-8000-123456789abc", Odd("x"))`. Logged record, first six physical lines:
  `search crashed trace_id=8f1c2d3e-0000-4000-8000-123456789abc error_class=Boom`
  `search crashed trace_id=O`
  `exception_class=__main__.Boom`
  `search crashed trace_id=OTHER error_class=Fake`
  `chain=__main__.Boom`
  `search crashed trace_id=OTHER error_class=Fake`
  An escape sequence class (`"Esc\x1b[2K"`, erase line) reaches line 1 raw: `error_class=Esc^[[2K` through `cat -v`.
  A trace id with a newline does the same (`_log_crash("abc\nsearch crashed trace_id=FORGED error_class=X", ValueError("v"))` prints `search crashed trace_id=FORGED error_class=X error_class=ValueError` as its own line); every surface mints the id as a UUID today, so that half is latent and pre-existing.
- What it means for the person reading the log: a `grep "search crashed trace_id=OTHER"` finds a crash for a search that never crashed. Class names are developer-written in practice, so reach is low; filed because the card made line 1 the line to trust.
- NOT FIXED

### A-85-12: line 1 of the crash record grew past 80 characters, and the "never split" claim in its docstring no longer holds

- Severity: minor
- Where: `core/run.py`, `_crash_record` docstring ("so a log handler that wraps long lines can never split them from each other") and `test_run.py`, where four bounds moved from `< 80` to `< 120` in this card.
- What: with a real UUID trace id and a 30 character class, line 1 is 102 characters before any handler prefix (timestamp, level, logger name). On develop the same line was at most 22 + 48 = 70. A wrap at 80 columns now splits the class name in two, and a logger prefix pushes the trace id itself across the wrap.
- Reproduction: `_crash_record(str(uuid.UUID(int=0)), type("ProviderResponseValidationErr", (Exception,), {})("x")).splitlines()[0]` has length `102`; characters 0 to 79: `search crashed trace_id=00000000-0000-0000-0000-000000000000 error_class=Provide`, characters 80 on: `rResponseValidationErr`. A 48 character id and a long class give `115`.
- What it means for the person reading the log: on a narrow viewer the reason is on a different visual line from the id, and a copy of "the first line" may carry half a class name. The tests were loosened to fit the new line rather than the line fitted to the old bound, so the property card 73 pinned is now pinned at a weaker value. Unsure whether 80 still matters for the log viewer in use.
- NOT FIXED

## Verdict

PASS with findings, for the ticket as the person would read it: in every realistic run I drove, a failed step or a crash left a line with the right trace id and no question text. No finding blocks it. Several findings sit inside this card's own new code (A-85-01, 02, 03, 04, 06, 10, 11, 12), and A-85-01 and A-85-02 repeat mistakes that card 73's `_next_link` already fixed one file over.

Verified with my own probes:

- Three concurrent searches through `run` and `run_streaming`, 6 random seeds each, 12 of 12 with every step line naming its own trace id and cause class. No log record at any level held the question text or the exception message.
- A cancelled search beside three failing ones logs no step line under its id, and the others keep theirs.
- Two streamed searches advanced by one task: both lines carry the second id (A-85-05).
- The `from None`, falsy cause, newline, escape, 400 character, cycle and nested-`HarnessCallError` cause shapes (A-85-01 to 03).
- A raising log filter escapes the step path and is swallowed by the crash path (A-85-06).
- Think and guard unusable-reply step errors log no `step failed` line; price gap and Think timeout do (A-85-07, 08).
- Crash line 1 contents and length (A-85-10 to 12).
- `test_run.py`: 60 passed after the probes, tree clean.

Only read, not probed: that production surfaces drive each run in its own task (`run_registry` uses `asyncio.create_task` per run), and that production has no log filters (no `basicConfig` or `dictConfig` in `src`, uvicorn start command in `railway.json`).
