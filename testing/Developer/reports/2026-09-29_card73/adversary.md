# Card 73 adversary round, 2026-09-29

Subject: commit 6afd295e on `fix/card73-crash-reason` (`core/run.py` `_log_crash` and its two call sites). One round. Findings are filed, never fixed or closed. The judge's F-73-J01 to J07 are not refiled.

## Findings

### F-73-A01: a real database connection failure already fills the 30-frame cap; the node survives by 2 frames and the run.py frame (which entry point, buffered or SSE) is always cut
- Severity: minor (should-fix; distinct from F-73-J02, which is a recursion; this is the ordinary, most likely crash)
- Where: `src/system_03_search_agent/core/run.py:239` (`][-_CRASH_LOG_MAX_FRAMES:]`), constant `core/run.py:205`, whose comment says "a crash deep inside a graph node, a provider client and an HTTP stack is about 20 frames".
- Reproduction: scratch script `adv73/p2_frames.py`, real compiled graph, nothing patched except a spy that counts `traceback.extract_tb` before calling the real `_log_crash`. `USER_DB_URL=postgresql://probeuser:<marker>@127.0.0.1:1/probedb` (a local closed port, no network), so `guardrail_node`'s `session_scope()` / `check_system_daily_cost_cap` hits a genuine psycopg2 connection refusal. Output:
  ```
  run guest total_tb_frames 35 logged 30 graph.py at index [2] graph.py:1730 in guardrail_node
  run uid total_tb_frames 35 logged 30 graph.py at index [2] graph.py:1729 in guardrail_node
  run_streaming guest total_tb_frames 35 logged 30 graph.py at index [2] graph.py:1730 in guardrail_node
  run_streaming uid total_tb_frames 35 logged 30 graph.py at index [2] graph.py:1729 in guardrail_node
  ```
  First logged frame `_runnable.py:733 in ainvoke`, last `__init__.py:122 in connect`. `run.py:... in run` / `run_streaming` is never in the record (5 head frames dropped).
- What a developer would notice: the constant's premise ("about 20") is wrong by 75% on the first real crash shape measured; a stack three frames deeper (pool pre-ping, a retry, a different SQLAlchemy path, an HTTP client under a tool) drops `graph.py ... in <node>`, the only frame that says where the search was. And the record cannot tell the buffered `/query` path from the SSE path, since the only frame naming it is always the first cut. The marker password did not appear in any record (0), so the no-message rule held.
- NOT FIXED

### F-73-A02: frames are taken from the outermost exception only, so when a library wraps the real error the node that failed is not in the record
- Severity: minor (should-fix)
- Where: `src/system_03_search_agent/core/run.py:236-238` (`traceback.extract_tb(exc.__traceback__)` on the top exception; the chain loop at `:231-235` records only class names for each cause).
- Reproduction: scratch script `adv73/p4_shapes.py`, real compiled graph run through a real `RunRegistry` and `subscribe`, with `core.graph._guardrail_after_prefilter` replaced by a coroutine that does `raise asyncio.CancelledError()` itself (a node-internal cancellation, not Stop; the graph cancels its own decision tasks at `core/graph.py:1241`, `:1288`, `:1344`, `:1367`). LangGraph wraps it. The record, in full:
  `search crashed, trace_id=f3e6a357-... exception_class=langgraph.errors.NodeCancelledError chain=langgraph.errors.NodeCancelledError <- asyncio.exceptions.CancelledError frames=run.py:824 in run_streaming > main.py:3440 in astream > _runner.py:557 in atick > _runner.py:687 in _panic_or_proceed > _retry.py:792 in arun_with_retry`
  No `graph.py` frame, no node name, no probe-file frame: the place that raised is only in the CancelledError's own traceback, which is never read.
- What a developer would notice: the line proves LangGraph cancelled a node and does not say which of the five. The same holds for any `raise X from Y` wrapper (SQLAlchemy wraps psycopg2, litellm wraps provider SDK errors, LangGraph wraps node errors): the deepest, most useful frames live on the cause. Fix shape: also extract the frames of the last link in the chain (or of each link, bounded).
- Person's screen: unchanged (`error` "This query failed unexpectedly before it could complete."), as the card intends.
- NOT FIXED

### F-73-A03: an ExceptionGroup crash logs only `builtins.ExceptionGroup`; the leaf exception's class and its frames are absent
- Severity: minor, unsure on reachability (no `asyncio.TaskGroup` in `src/` today; `anyio` task groups raise groups and are in the dependency tree; the MCP adapter uses them)
- Where: `src/system_03_search_agent/core/run.py:231-238`. The chain walks `__cause__`/`__context__` only and never `.exceptions`.
- Reproduction: `adv73/p4_shapes.py`, real graph via `RunRegistry`, `_guardrail_after_prefilter` replaced by `async with asyncio.TaskGroup() as tg: tg.create_task(leaf_fail())` where `leaf_fail` does `{}["MISSING_KEY"]`. Record in full:
  `search crashed, trace_id=d1acffc9-... exception_class=builtins.ExceptionGroup chain=builtins.ExceptionGroup frames=run.py:824 in run_streaming > main.py:3440 in astream > ... > graph.py:1780 in guardrail_node > p4_shapes.py:19 in via_taskgroup > taskgroups.py:147 in __aexit__`
  `KeyError` appears nowhere, and neither does `leaf_fail`.
- What a developer would notice: "a task group failed in the guardrail" and nothing about which task or what kind of error. With several sub-exceptions the log is equally silent about all of them.
- NOT FIXED

### F-73-A04: a crash that is a BaseException but not an Exception (and not Stop) still ends the person's stream with zero events and writes no reason
- Severity: minor, unsure (pre-existing, outside the diff's lines; recorded because it is a crash shape where the card's outcome, "the reason is written where a developer can find it", does not hold, and the person's screen is blank rather than the generic failure)
- Where: `src/system_03_search_agent/core/run.py:851` (`except Exception as crash`) and `:663`; `core/run_registry.py:629-635` catches only `asyncio.CancelledError`.
- Reproduction: `adv73/p4_shapes.py`, real graph via `RunRegistry.create_run` and `subscribe`, node replaced by `raise Custom()` where `class Custom(BaseException)`. Output:
  `CUSTOM_BASEEXC person sees: []`
  `CUSTOM_BASEEXC crash records: 0 []`
  All WARNING+ logs for the trace: only `interaction capture failed ...` and `analytics query_completed event failed ...` (the DB is unreachable in the probe). Contrast, same harness: a node-internal `CancelledError` (wrapped by LangGraph into `NodeCancelledError`, an `Exception`) and a TaskGroup failure both produced the `error` event and one crash record.
- What a person would notice: the answer area gets no error, no done, nothing; SSE closes. What a developer would notice: no line for the trace at all. Real triggers are rare (`SystemExit` from a library calling `sys.exit`, `KeyboardInterrupt`, a third-party BaseException subclass). The Stop path is correct: my probe `adv73/p3_cancel.py` cancelled a hung real-graph run at 0.05, 0.5 and 2.0 s on both entry points and got `CancelledError`, no events and `ERROR records for trace: 0` every time, so Stop is never logged as a crash.
- NOT FIXED

### F-73-A05: a second crash in the run's `finally` after a first crash gets no crash record; asyncio later logs it with its full message and without the trace id
- Severity: unsure (pre-existing, outside the diff; triggering it needs `_terminal_events_for_capture` or `harness.get_query_cost_usd`, both outside `_capture_interaction`'s own `except Exception` at `core/run.py:373`/`:420`, to raise, which I did not find a real way to do; I raised from `_capture_interaction` itself to stand in)
- Where: `src/system_03_search_agent/core/run.py:873-887` (the `finally`), `core/run_registry.py:629-690` (`_drain_into_entry` has no `except Exception`, so the task keeps the exception unretrieved).
- Reproduction: `adv73/p6_two.py`, real graph via `RunRegistry`; the node raises `ValueError("first crash <MARK>")`, `core.run._capture_interaction` raises `KeyError("second crash in capture <MARK>")`; registry entry dropped and `gc.collect()`. Output:
  ```
  person sees: ['error']
  LOG ERROR system_03_search_agent.core.run | search crashed, trace_id=7a5ce389-... exception_class=builtins.ValueError ... | MARK in rendered: False | trace id in rendered: True
  LOG ERROR asyncio | Task exception was never retrieved future: <Task finished name='Task-2' coro=<_drain_into_entry() done, ... | MARK in rendered: True | trace id in rendered: False
  ```
- Why it matters: the person's screen is fine. For the log as evidence, the card's no-message rule is a property of one record, not of the crash path: the second failure reaches the log only through asyncio's own handler, only when the entry is collected (minutes later, after eviction), carrying the exception message (the probe's secret-shaped marker) and no trace id to join it by.
- NOT FIXED

### F-73-A06: the record's size is bounded by frame and chain COUNT only, not by length; one long class name makes a 400 KB log line
- Severity: note (overlaps F-73-J04's premise on a different axis: J04 is whose text, this is how much)
- Where: `src/system_03_search_agent/core/run.py:234` and `:238`; the class name is written twice (`exception_class=` and `chain=`); no per-field or whole-line cap.
- Reproduction: `adv73/p5_timing.py`, `Big = type("E"*200000, (Exception,), {})`, raised and passed to `_log_crash`:
  `record length with 200k-char class name 400104`
  Same script, timing, which is fine: a 1000-frame RecursionError costs `2.37` ms cold and a 10000-link context chain `0.06` ms (the 8-link cap holds), so the new call does not delay the person's error event measurably.
- What a developer would notice: nothing today (no class that long is loaded; the J01 follow-up walked 1430). The production-standards rule asks for a hard character cap on anything bounded; a `[:N]` on each field would make the bound real rather than dependent on developer-written names.
- NOT FIXED

### F-73-A07: on the most likely crash (the user database down), the same trace's earlier WARNING already prints the exception message and full file paths, so the ERROR's no-message rule protects nothing on that path and the reason sits in a different record
- Severity: minor (pre-existing lines, but it undercuts the rationale in the new docstring at `src/system_03_search_agent/core/run.py:218-229`, and it decides where a developer actually finds the reason)
- Where: `src/system_03_search_agent/core/run.py:491-493` (`session memory not loaded ... exc_info=True`), also `:374-376` (capture) and `:421-425` (analytics), each `exc_info=True`, which the app's RichHandler renders with `rich_tracebacks=True` (the handler F-73-J05 found).
- Reproduction: `adv73/p8_all.py` (imports `p1_realdb.py`), real compiled graph, `run_streaming`, a guest `owner_id`, `USER_DB_URL` at a closed local port. Every INFO+ record for the trace, in order:
  ```
  WARNING system_03_search_agent.core.run | exc_info: True | has 127.0.0.1: True | msg: session memory not loaded for trace_id=d1dff100-...
  ERROR system_03_search_agent.core.run | exc_info: False | has 127.0.0.1: False | msg: search crashed, trace_id=d1dff100-... exception_class=sqlalchemy.e...
  WARNING system_03_search_agent.feedback.writer | exc_info: False | ... | msg: interaction write failed for trace_id=d1dff100-... (OperationalErr...
  ```
  The WARNING's traceback ends: `sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "127.0.0.1", port 1 failed: Connection refused ~ Is the server running on that host and accepting TCP/IP connections?`, and its frames carry absolute paths (`File "<repo-root>/src/system_03_search_agent/core/session_memory.py", line 490`, the probe machine's home path in the raw output) where the new record uses basenames. With a guest query lacking `owner_id` the same WARNING instead prints the `CallerIdentityRequired` message in full.
- What it means: for a developer this is the useful record (host, port, "connection refused") and it is one line above the ERROR. For the secrets argument the builder made (a driver error can echo a connection string), the same text already reaches the same log under the same trace id through a neighbouring handler, and a statement-level SQLAlchemy error would add `[SQL: ...] [parameters: ...]` (the owner and session identifiers) there. Either the no-message rule is a system property, and these three `exc_info=True` warnings break it, or it is not, and the ERROR drops the one field a developer needs. Recorded for the product owner to choose; I am not asserting which.
- NOT FIXED

### F-73-A08: a second, independent way for `_log_crash` itself to raise (an exception class with no `__module__`); the `is not None` half of F-73-J01's fix shape would not cover it
- Severity: minor, INSIDE THIS PHASE'S FIX (the new `_log_crash`). Additive evidence for F-73-J01, not a refile: J01's trigger is `bool()` on the cause; this one is the attribute read at `src/system_03_search_agent/core/run.py:234` (`f"{cls.__module__}.{cls.__qualname__}"`), which J01's suggested `is not None` change does not touch. Only J01's other half, a `try/except` around the whole body, covers it.
- Reproduction (the real `_log_crash`, direct call):
  ```
  g = {}; exec("E=type('E',(Exception,),{})", g)   # class built in exec'd code whose globals lack __name__
  E.__module__            -> AttributeError __module__
  _log_crash("t", E())    -> _log_crash RAISED AttributeError __module__
  F = type("F", (Exception,), {"__module__": M()})  # M.__format__ raises
  _log_crash("t", F())    -> _log_crash RAISED on F RuntimeError fmt
  ```
  Because `_log_crash` is the first statement of both handlers (`core/run.py:664`, `:852`), either raise replaces the crash and the person gets no `error`/`done` pair, as J01 measured.
- Reachability, measured: with the web app, MCP sub-app and `core.run` imported, I walked 1401 loaded `BaseException` subclasses; none has a missing or non-string `__module__` or `__qualname__`. So, like J01, not reachable today by any class I found; recorded so the fix for J01 is the guard, not only the `or`.
- NOT FIXED

## Verified by my own probes, no finding

All scripts are in the session scratchpad under `adv73/`. They import from `src/` and change nothing in the worktree.

- Stop is never logged as a crash (`p3_cancel.py`). A real compiled graph was hung inside `guardrail_node` and cancelled at 0.05, 0.5 and 2.0 s, through both `run` and `run_streaming`. Every time the result was `CancelledError`, no events, and `ERROR records for trace: 0`.
- A node-internal cancellation that is not Stop is logged. LangGraph wraps it as `NodeCancelledError`, an `Exception`, and the person gets the generic error (`p4_shapes.py`).
- Concurrent crashes are attributed correctly (`p7_conc.py`). Forty concurrent crashing runs went through one `RunRegistry`, each raising a class chosen by its own question. Result: `runs 40 records 80 mismatched or missing 0`. The 80 records are 40 crash lines plus 40 "session memory skipped" INFO lines; every crash line carries its own run's trace id and its own class.
- The trace id is not user-controlled. It is minted server-side as `uuid4` on every surface: `adapters/web_sse/app.py:1462`, `adapters/mcp/server.py:1380`, `adapters/graphql/schema.py:291`.
- No question text can reach a class name, module or frame today. A search of `src/` found no `exec(`, `eval(`, `compile(` (other than regex and graph compile), `create_model(`, three-argument `type(` or `make_dataclass(`.
- The new call adds no measurable delay (`p5_timing.py`). A 1000-frame RecursionError costs 2.37 ms cold. The 8-link chain cap holds on a 10000-link chain, at 0.06 ms.
- No log shipping. No `logging.Handler` subclass and no `addHandler` exist in `src/`, so the record goes nowhere beyond stderr.
- On a real database connection failure, the marker password in `USER_DB_URL` appeared in 0 records (`p1_realdb.py`).

## Read, not run

- `run()` has no production caller: `core/run_registry.py:175` imports only `run_streaming`. `adapters/web_sse/app.py:418-424` records that the buffered `POST /query` was removed in build phase 4.0. So F-73-J01's "on `run()` the buffered endpoint raises" applies only to developer scripts, such as `testing/Developer/scripts/local_loop_run.py`, and to tests. The SSE half of J01 stands.
- The deployed log's rendering is unverified: no request was made to deployed apps.

## Count by severity

- critical: 0
- major: 0
- minor: 6
  - A01, A02 and A07.
  - A03 and A04, both also unsure on reachability.
  - A08, which is inside this phase's fix.
- unsure: 1 (A05)
- note: 1 (A06)

## Verdict against the card

PASS on the card's two claims as the person meets them, with named items:

- A person's screen is unchanged for every crash shape I raised that is an `Exception`: before the first event, mid-stream, wrapped by LangGraph, a task group, and a crash after which the `finally` also fails.
- Stop is never misread as a crash.
- Records are never misattributed across concurrent runs.

Two items weaken "a developer can find the reason":

- A02 and A03: the frames that locate the failure are on the cause, not on the wrapper.
- A01: the frame budget is already full on the first real crash shape.

A08 sits inside this phase's new `_log_crash`. It is the same stop condition J01 fired, and it changes J01's fix shape.
