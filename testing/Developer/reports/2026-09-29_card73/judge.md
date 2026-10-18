# Card 73 judge round, 2026-09-29

Judge, one round, on branch fix/card73-crash-reason (commits 6afd295e, e084e1c3). Findings appended as established.

## Findings

### F-73-J01: a failure inside `_log_crash` escapes both last-resort handlers, so the person gets no error event at all
- Severity: should-fix. INSIDE THIS PHASE'S FIX (the new `_log_crash`).
- Where: `src/system_03_search_agent/core/run.py:236` (`link = link.__cause__ or link.__context__`), called unguarded at `core/run.py:664` and `core/run.py:852`, BEFORE `_crash_fallback_events`.
- What: `_log_crash` is the first statement of each `except` block and has no guard of its own. Any exception it raises replaces the original crash and leaves `run()` / `run_streaming()` with no `error`/`done` pair, breaking F-2.0-11's never-raises contract that the handler exists for. One concrete trigger: `or` calls `bool()` on the cause, so a cause exception whose `__bool__` raises (or `__len__` raises) propagates out of the logger.
- Reproduction (judge probe, a temporary test file, `raise ValueError("outer") from _BoolRaises("inner")` where `_BoolRaises.__bool__` raises `RuntimeError`), output:
  `P2 RAISED OUT OF run RuntimeError bool not supported`
  `P2 RAISED OUT OF run_streaming RuntimeError bool not supported`
  Before this change the same crash yielded `['error', 'done']`.
- What a person would notice: on the SSE path `_drain_into_entry` (`core/run_registry.py:629`) has no `except Exception`, so the stream ends with no terminal event, a spinner or blank result instead of "This query failed unexpectedly". On `run()` the buffered endpoint raises.
- The trigger I used is synthetic; I found no installed exception class with a raising `__bool__` (see J-note below if any). The defect is the missing guard: the logger is new code sitting in front of the only safety net. Fix shape: `is not None` instead of `or`, and wrap the body of `_log_crash` in `try/except Exception` that falls back to a class-name-only line or passes.
- NOT FIXED

Follow-up to F-73-J01, how likely the trigger is: with the web app, the graph, litellm, httpx, sqlalchemy, psycopg2, pydantic, langgraph, langsmith, openai, anthropic and aiohttp imported, I walked all 1430 loaded `BaseException` subclasses for a `__bool__` or `__len__`. One hit, `graphql.pyutils.undefined.UndefinedType.__bool__`, which returns False rather than raising and is a sentinel, not something raised. So J01's `bool()` trigger is not reachable by any exception I found installed today; the finding stands on the missing guard in front of the safety net, and I would accept should-fix rather than blocking.

### F-73-J02: a RecursionError keeps only the 30 deepest frames, which are all the recursing function, so the node and the entry point are lost
- Severity: should-fix
- Where: `src/system_03_search_agent/core/run.py:241` (`][-_CRASH_LOG_MAX_FRAMES:]`), constant at `core/run.py:205`.
- What: the cap keeps the TAIL of the traceback. In a runaway recursion (the case the constant's own comment names) the tail is 30 copies of one frame, and the frames that say which node and which step was running are dropped.
- Reproduction (judge probe: `check_system_daily_cost_cap` patched to call a function that recurses forever, real compiled graph, `run()`), output:
  `P5 EVENTS ['error', 'done']`
  `P5 guardrail_node in line: False | len 1548`
  `P5 head: search crashed, trace_id=trace-p5 exception_class=builtins.RecursionError chain=builtins.RecursionError frames=test_zz_judge_probe_card73.py:121 in _recurse > test_zz_judge_probe_card73.py:121 in _recurse > ...`
- What a developer would notice: the line says a recursion happened in one function and not where the search was when it started. Keeping the first few frames plus the last ones (or collapsing repeated frames the way `traceback` itself does, "[Previous line repeated N more times]") would keep both ends.
- NOT FIXED

### F-73-J03: the cause chain uses `__cause__ or __context__`, so a falsy cause is skipped and `raise X from None` still lists the suppressed context
- Severity: note
- Where: `src/system_03_search_agent/core/run.py:236`
- Reproduction (judge probe: inside `except KeyError`, `raise ValueError("outer") from _Falsy("inner")` where `_Falsy.__len__` returns 0), output:
  `chain=builtins.ValueError <- builtins.KeyError` : the real cause `_Falsy` is missing and the implicit context appears in its place.
- `__suppress_context__` is not read either, so the chain can differ from what Python's own traceback would print. Harmless for secrets (class names only); it can mislead a developer reading the chain. `link.__cause__ if link.__cause__ is not None else (None if link.__suppress_context__ else link.__context__)` matches Python's rule.
- NOT FIXED

### F-73-J04: class names, module paths, file names and function names reach the record verbatim, so the no-message rule only holds while those stay developer-written
- Severity: note
- Where: `src/system_03_search_agent/core/run.py:235` and `:239`
- Reproduction (judge probe: an exception class built with `type("Err_" + MARK, ...)` and `__module__ = "mod_" + MARK`, raised from a function named `fn_<MARK>` compiled with filename `file_<MARK>.py`), output:
  `exception_class=mod_PROBEMARKxyz987.Err_PROBEMARKxyz987 chain=mod_PROBEMARKxyz987.Err_PROBEMARKxyz987 frames=run.py:657 in run > test_zz_judge_probe_card73.py:110 in _boom > file_PROBEMARKxyz987.py:2 in fn_PROBEMARKxyz987`
- What it means: the builder's premise (`core/run.py:218-221`, "A class name and a frame are developer-written") is correct for every class I found loaded (J01 follow-up walked 1430) and for normal code. It is not enforced: a library that builds exception classes from a service's response, or code compiled from a template, would put that text in the log. No such path exists in this repository today that I found. Recorded so the premise is visible, not as a defect to fix now.
- NOT FIXED

### F-73-J05: under the app's own logging stack the crash line is wrapped at 80 columns and the trace id itself is cut in two, so a search for the full trace id finds nothing
- Severity: should-fix (unsure on the deployed width, see below; the card's stated outcome is "a developer can find it by trace id")
- Where: the record is built at `src/system_03_search_agent/core/run.py:241-247`; the handler is not this repository's: importing `adapters/web_sse/app.py` builds the MCP sub-app, and `mcp/server/mcpserver/utilities/logging.py:32-39` (site-packages) calls `logging.basicConfig(..., handlers=[RichHandler(console=Console(stderr=True), ...)])` on the ROOT logger. `grep -rn "basicConfig\|dictConfig\|RichHandler" src/` returns nothing, so no repository code replaces it.
- Reproduction: `PYTHONPATH=src python -` that imports `system_03_search_agent.adapters.web_sse.app`, applies uvicorn's `LOGGING_CONFIG` the way `uvicorn ...:app` does (the `railway.json` start command), then calls `_log_crash("2ff4e9d4-6499-4167-9e92-8c54d8ab720e", ValueError("x"))`, stderr redirected to a file (not a terminal). The file holds:
  ```
                      ERROR    search crashed,                          run.py:240
                               trace_id=2ff4e9d4-6499-4167-9e92-8c54d8a
                               b720e
                               exception_class=builtins.ValueError
                               chain=builtins.ValueError
                               frames=<stdin>:7 in <module>
  ```
  `grep -c 2ff4e9d4-6499-4167-9e92-8c54d8ab720e` on that file: 0. `grep -c 2ff4e9d4`: 1. The G-026 run's real trace id is that same uuid form (`raw/G-026_run1.json`, `"trace_id": "2ff4e9d4-6499-4167-9e92-8c54d8ab720e"`).
  With 12 frames the frames list spanned 7 more physical lines, none carrying the trace id.
- What a developer would notice: on a log viewer that stores one entry per line, a search for the trace id copied from the answer's error returns nothing; a search for its first 8 characters returns only the first line, and the class and frames sit on following entries that can interleave with other requests' lines.
- What I could not verify: the width the deployed container gives Rich. Rich uses `COLUMNS` when stderr is not a terminal and 80 otherwise; I made no request to the deployed app or its logs (brief constraint). If the deployed console is wide the split does not happen. The builder's tests use `caplog`, which bypasses this handler, so no test covers what the line looks like where a developer reads it.
- Pre-existing and wider than this card: every `logger.warning("... trace_id=%s", ...)` in `core/run.py` goes through the same handler. It matters here because a findable line is the card's whole outcome. A fix shape inside this card: put the trace id first and keep the first physical line short, or emit the frames as a separate record that also starts with the trace id; a proper fix is a plain `StreamHandler` configured at app start.
- NOT FIXED

### F-73-J06: a sibling path still ends a search with "A step in this query failed unexpectedly." and logs no reason
- Severity: should-fix, outside this diff (pre-existing), recorded because the brief asks whether any other "failed unexpectedly" path still logs nothing
- Where: `src/system_03_search_agent/core/graph.py:1905-1907` (guardrail, a non-transient `HarnessCallError` on attempt 1 or any on attempt 2), `core/graph.py:3542-3543` (think), `core/graph.py:12051-12052` (write). Each turns the `HarnessCallError` into the fatal step error through `_step_error_kwargs` (`core/graph.py:855-877`, message from `core/graph.py:843`) with no log call. The harness builds a message carrying the cause (`harness/harness.py:701-706`) that nothing writes anywhere.
- Reproduction (judge probe, real compiled graph, `harness_module.litellm.acompletion` patched to raise `RuntimeError`, question "which genes are associated with cystic fibrosis", both `run` and `run_streaming`), output:
  `P6 run EVENTS ['error', 'done']`
  `P6 error payloads [{'fatal': True, 'scope': 'step', 'source': 'guardrail', 'error_class': 'unexpected', 'message': 'A step in this query failed unexpectedly.', 'retry_after_s': 0}]`
  INFO-and-above records naming the trace: only `session memory skipped ...`, `interaction capture failed ...`, `analytics query_completed event failed ...`. No record names the step, the class or the model. `_log_crash` is not reached, correctly, because the graph returned normally.
- What a developer would notice: the same "cannot trace it" problem card 73 fixes, for a provider error the harness classes as unexpected (anything outside its transient and recoverable lists), which is the more likely shape of a G-026-like failure 4 seconds in, before the guard reply. The person sees a different sentence ("A step in this query failed unexpectedly.") and a developer has nothing, as before. I exercised only the guardrail site; the think and write sites I read, not ran.
- Other `except Exception` sites checked: `core/run.py:373`, `:420`, `:490`, `:684`, `:867` all log a warning with the trace id; `core/session_memory.py:157` and `core/run_registry.py:576` are best-effort side paths that do not end the search; `adapters/web_sse/app.py:223` is startup migrations. `core/run.py` code outside the two inner `try` blocks (`Harness(...)` at `:643`/`:797`, which only assigns fields, `harness/harness.py:555-562`, and `_load_session_memory`, which catches `Exception` at `core/run.py:490`) could not raise in practice, so I found no third unlogged crash route in `core/run.py`. `core/run_registry.py:629-657` has no `except Exception`, which only matters if `run_streaming` itself raises (see J01).
- NOT FIXED

Line-number correction, judge's own error (append-only, so corrected here): in the committed `core/run.py` the `or` is at line 235 (J01, J03 said 236), the frame slice at 239 (J02 said 241), the class and frame formatting at 234 and 238 (J04 said 235 and 239), the `logger.error` call at 240-246 (J05 said 241-247), and `Harness(...)` at 640 and 776 (J06 said 643 and 797). The handler call sites 664 and 852 are right.

### F-73-J07: class plus frames locates a typical crash to its line; it does not say which key, field or provider status failed
- Severity: note (the builder's trade-off, stated so the product owner sees what it costs)
- Evidence that it locates: a real crash through the compiled graph (judge probe P1, a database error raised inside the daily cost cap check) logged
  `search crashed, trace_id=trace-p1 exception_class=sqlalchemy.exc.OperationalError chain=sqlalchemy.exc.OperationalError frames=run.py:657 in run > main.py:4090 in ainvoke > main.py:3440 in astream > _runner.py:396 in atick > _retry.py:744 in arun_with_retry > _runnable.py:733 in ainvoke > _runnable.py:501 in ainvoke > graph.py:1730 in guardrail_node > test_zz_judge_probe_card73.py:36 in _boom`
  That is 9 frames, well under the cap of 30, and it names the node (`guardrail_node`), the line (`graph.py:1730`, `cost_control.check_system_daily_cost_cap(session)`) and the class. For G-026's shape (no guard event, 4.2 seconds in) a line like this would have said which statement in the guardrail died and with what kind of error. That is the question card 73 asked, and it answers it.
- What is lost without the message, by crash kind:
  - `KeyError` / `IndexError`: the line, not the key or index.
  - `AttributeError`: the line, not which attribute or which object was None.
  - `pydantic.ValidationError`: the construction site, not which field or which rule (its message carries the field `loc` and the input value).
  - A database error: that it was operational, not whether it was refused, timed out or rejected the login.
  - A provider error outside the harness: the class (for litellm this encodes the status family), not the provider's body.
- Frames show `basename:line in function`, no directory, so no local path from the machine reaches the log; verified in every probe output above (`run.py:657`, `graph.py:1730`).
- A safe middle step, if wanted later: a per-class allowlist of structured, developer-shaped detail, for example `[(e["loc"], e["type"]) for e in exc.errors()]` for a pydantic error without `input`. Not needed to meet the card.
- NOT FIXED

## Verified by my own probes

Probes ran from a temporary test file under `tests/system_03_search_agent/core/`. I moved it to the session scratchpad afterwards. `git status --short` then showed only this report as untracked, and `git diff --stat` was empty.

- Exactly one ERROR record per crash, carrying the trace id, on both paths:
  - A crash before the first event (P1, P2 baseline).
  - A crash in a real node through the compiled graph (P1, `guardrail_node`).
  - A mid-stream crash after 4 real events (P7: `crash lines 1`, events `guard 0, cost 1, think 2, cost 3, error 4, done 5`).
  - A consumer that closes after the first yielded event (P8: `crash lines 1`).
- The fallback is unchanged. `['error', 'done']` still comes with "This query failed unexpectedly before it could complete." (P1, both paths), and `seq` stays monotonic mid-stream (P7).
- No message text reaches any record at DEBUG, across every logger, on the real-graph path. That includes a database error whose statement parameters and wrapped cause both carry the marker (P1: `LEAKING RECORDS 0 of 6`, both paths; P7: `leaks 0`). This is a stronger subject than the builder's test, which patches `ainvoke` and so never runs LangGraph's own code.
- Mutations, each applied to `core/run.py` and reverted with `git checkout`, run against `tests/system_03_search_agent/core/test_run.py`:
  - M1, drop `run()`'s call: 2 red.
  - M2, drop `run_streaming()`'s call: 2 red.
  - M3, append `str(exc)`: 2 red.
  - M4, add `exc_info=exc`: 4 red.
  - M5, message on a separate DEBUG record: 2 red.
  - M6, log twice in `run()`: 1 red.
  - M7, drop the trace id: 2 red.
  - M8, `repr` of the exception in the chain: 2 red.
  - Every control has a test that fails without it. Not covered by any test: J01 (a failing logger) and J05 (how the line renders in the app's real handler).
- `ruff check` on the two changed Python files: passed. `test_run.py`: 36 passed, after all reverts.

## Read, not run

- The think (`core/graph.py:3543`) and write (`core/graph.py:12051`) step-error sites in J06. I ran only the guardrail site.
- The deployed container's console width in J05. No request was made to deployed apps or their logs.
- LangSmith: with tracing on, the traced run records the exception remotely. That is pre-existing and not a log line, and I did not examine it.
- The builder's full-suite count (6548 passed). I did not re-run the full suite.

## Verdict: MERGE WITH NAMED ITEMS

- The card's two claims hold under my own probes:
  - Every crash on both last-resort paths writes one trace-id line.
  - The person's screen is unchanged.
  - The no-message rule is enforced, and its tests fail when it is removed.
- Named items:
  - J01 (should-fix, INSIDE THIS PHASE'S FIX): guard `_log_crash` so a failure in it can never cost the person the error event, and use `is not None` in place of `or`.
  - J05 (should-fix, unsure): confirm on develop's log that the line and the full trace id are findable. If Rich wraps at 80 columns there, the card's outcome ("find it by trace id") is not met.
  - J02 (should-fix): keep the head of the traceback as well as the tail.
  - J06: a separate card for the step-level "A step in this query failed unexpectedly." path, which still logs nothing.
  - J03, J04, J07: notes.
- Because J01 sits inside this phase's own new code, the review loop's stop condition applies. The lead should decide whether J01 is fixed before merge or merged as a named item.

