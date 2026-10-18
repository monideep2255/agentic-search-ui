# Card 73 fresh verifier

Branch fix/card73-crash-reason, fix commits da0fe4b0 and a45c79fb. Verdicts appended as established.

## Verdicts

Test file run once, `PYTHONPATH=src venv/bin/python -m pytest tests/system_03_search_agent/core/test_run.py -q`: `58 passed in 2.99s`. Python 3.11.6. Every verdict below comes from my own probes in the scratchpad (`ver73/`), not from that suite.

- F-73-J01: FIXED. Own probe `ver73/p2_graph.py`, real compiled graph, `check_system_daily_cost_cap` patched to raise `ValueError(MARK) from BoolRaises(MARK)` (`__bool__` raises). run: `person=['error', 'done'] msg='This query failed unexpectedly before it could complete.' raised=None crash_records=1 leak_records=0`; run_streaming the same; through a real `RunRegistry.subscribe`: `person=['error']` (subscribe stops at a fatal error by design, `run_registry.py:1123-1127`), one record. The record lists `chain=builtins.ValueError <- __main__.BoolRaises`. Direct call (`ver73/p1_direct.py`): `returned`, 1 record.
- F-73-A08: FIXED. Same probe with an exec-built class that has no `__module__`: all three paths `person=['error', 'done']` (registry `['error']`), one record `search crashed, trace <uuid>: crash record could not be built`. Direct call with a `__module__` whose `__str__` raises, a `__class__` property that raises RuntimeError, and a `__class__` property that claims `BaseExceptionGroup`: each `returned`, one fallback line, no marker.
- F-73-J02: FIXED. Real graph, `check_system_daily_cost_cap` recursing forever: record head is `run.py:740 in run` (or `run.py:907 in run_streaming`) down to `graph.py:1730 in guardrail_node`, then `... 964 frames omitted ...`, then 25 tail frames. Entry point, node and failure all present on both paths.
- F-73-J03: FIXED. Direct: a falsy explicit cause inside `except KeyError` gives `chain=builtins.ValueError <- __main__.Falsy` (no KeyError); `raise ... from None` gives `chain=builtins.ValueError`; a two-exception cause cycle gives `chain=builtins.ValueError <- builtins.KeyError` and returns; a self-referencing context gives one link; a 10000-link chain returns in 0.04 ms with a 309-character record.
- F-73-A02: FIXED. Real graph, `_guardrail_after_prefilter` replaced by a coroutine raising `asyncio.CancelledError(MARK)`: record `chain=langgraph.errors.NodeCancelledError <- asyncio.exceptions.CancelledError`, and a new `innermost_frames (asyncio.exceptions.CancelledError):` section ending `graph.py:1780 in guardrail_node > p2_graph.py:38 in _after > p2_graph.py:78 in cancel_inside`. Person `['error', 'done']` on run and run_streaming, marker in 0 records.
- F-73-A03: FIXED for the kind of error, NOT FIXED for where the member failed. Real graph, a TaskGroup whose task does `{}["MISSING_" + MARK]`: record now carries `group_members=builtins.KeyError`, so the class the adversary said was missing is present; the frames end at `taskgroups.py:147 in __aexit__` and the failing task's own function never appears, the second half of A03's "KeyError appears nowhere, and neither does leaf_fail". Filed as F-73-V02 below. Person `['error', 'done']`, 0 leaks.
- F-73-A01: FIXED. Own probe `ver73/p3_db.py`, real compiled graph, nothing patched, `USER_DB_URL` pointing at a closed local port with a marker password, guest query. Spy count: outer traceback 35 frames, innermost (psycopg2) 16. Record: head `run.py:740 in run` (or `run.py:907 in run_streaming`) through `graph.py:1730 in guardrail_node`, then `... 2 frames omitted ...`, then 25 tail frames ending `__init__.py:122 in connect`, then `innermost_frames (psycopg2.OperationalError):` 16 frames. 55 lines, 1715 characters. The entry point that tells buffered from SSE is now kept. Marker password in 0 records of any logger.
- F-73-J05: FIXED as the judge measured it. Own probe `ver73/p4_rich.py`: import `adapters/web_sse/app.py` (MCP sub-app installs RichHandler on root), apply uvicorn `LOGGING_CONFIG`, call the real `_log_crash` with the G-026 uuid, stderr to a file (not a terminal). `grep -c 2ff4e9d4-6499-4167-9e92-8c54d8ab720e`: 1 with COLUMNS unset, 80, 120 and 200 (the judge measured 0 before the fix). The fallback line's id is also whole at all four widths. Caveat, filed as F-73-V01: at 80 columns Rich's message column is about 40 characters, so the "under 80" first line is still wrapped; the id survives only because a 36-character uuid fits that column on a line of its own:
  ```
                      ERROR    search crashed, trace                    run.py:321
                               2ff4e9d4-6499-4167-9e92-8c54d8ab720e
                               exception_class=builtins.ValueError
  ```
- F-73-A06: FIXED. Own probe `ver73/p5_caps.py`: an 8-link chain plus a 50-member group, every class name and module 5000 characters, every frame in a 5000-character function compiled under a 5000-character file name, 100 frames deep, trace id 64 characters. Record length 6033 (6000 plus the cut notice), first line 70 characters, longest line 1464. A 200000-character class name alone gives a 399-character record (`p1_direct.py`; the adversary measured 400104 before).
- F-73-J06: OPEN AS NAMED, correctly out of this card. Own probe `ver73/p6_open.py`, real graph, `litellm.acompletion` raising `RuntimeError(MARK)`, "which genes are associated with cystic fibrosis": run and run_streaming both `person=['error', 'done'] msg=['A step in this query failed unexpectedly.']`; the only records naming the trace are `session memory skipped`, `interaction capture failed`, `analytics query_completed event failed`. Still no reason logged, as the judge found. Why it is a separate card and not a disguised miss: G-026, the card's own evidence (`2026-09-29_card63_golden/raw/G-026_run1.json:45`), ended in "This query failed unexpectedly before it could complete.", the `core/run.py` handler this card covers; J06 is the step-level sibling in `core/graph.py`, a different sentence and a different file that another builder holds. It is the same user problem, so it should get its own card rather than be dropped.
- F-73-A04: OPEN AS NAMED, correctly out. Same probe, a `class Custom(BaseException)` raised in the guardrail, through a real `RunRegistry`: `person=[] crash_records=0`, unchanged from the adversary's result. It is pre-existing, the fix did not touch the `except Exception` clauses, and widening them would change how Stop behaves.
- F-73-A05: OPEN AS NAMED, correctly out. Same probe, first crash `ValueError(MARK)` in the node, then `_capture_interaction` raising `KeyError(MARK)`, entry dropped and collected: the `core.run` record has the trace and no marker; `asyncio ERROR | MARK True | trace False | Task exception was never retrieved ... _drain_into_entry()`. It reproduces exactly as filed, and the fix belongs in `core/run_registry.py`.
- F-73-A07: OPEN AS NAMED, correctly out, and it still needs the product owner's decision. The J06 probe shows the neighbouring `interaction capture failed for trace_id=...` and `analytics query_completed event failed ...` WARNINGs rendering full tracebacks with absolute paths from this machine (`File "<home>/Desktop/Tech ...`). This is pre-existing (`core/run.py` `exc_info=True` sites). fix.md calls it "the product owner's call" but records no question asked; under the decision-cadence rule it should be asked now, not left in a report.
- F-73-J04: OPEN AS NAMED. Names are now cut at 100 characters but still printed verbatim. One new consequence of the multi-line record: a class with `__qualname__ = "A\nB"` and `__module__ = "mod\nfake=line"` produces the record `'search crashed, trace ...\nexception_class=mod\nfake=line.A\nB\nchain=...'`, which adds physical lines that look like record fields (`p5_caps.py`). It is still developer-written only, and no such class was found by the judge's 1430-class walk. Recorded under J04's premise, not as a new defect.
- F-73-J07: OPEN AS NAMED. The trade-off stands as described: the A03 record says `builtins.KeyError`, not which key. The DB record says `sqlalchemy.exc.OperationalError <- psycopg2.OperationalError`, not "connection refused".

## New findings

### F-73-V01: the reason is no longer on any line that carries the trace id, so a line search for the id returns "search crashed" and nothing else
- Severity: minor, unsure (it depends on how develop's log viewer groups lines, which I could not check). INSIDE THIS PHASE'S FIX (da0fe4b0's multi-line record, which answered J05).
- What: `_crash_record` (`core/run.py:262`) now emits one record of up to 55 physical lines, and only line 1 carries the trace id. Class, chain and frames sit on later lines that carry no id, timestamp or level. The pre-fix record was one physical line holding the id, the class and the frames.
- Reproduction (`ver73/plain.log`, a plain `logging.basicConfig` line handler, the pre-fix `_log_crash` from e084e1c3 and the fixed one, the same KeyError):
  - `grep <old id>` gives `... ERROR old.core.run search crashed, trace_id=aaaaaaaa-... exception_class=builtins.KeyError chain=builtins.KeyError frames=<stdin>:9 in <module> > <stdin>:8 in a`.
  - `grep <new id>` gives `... ERROR system_03_search_agent.core.run search crashed, trace bbbbbbbb-1111-4222-8333-944455556666`, and nothing else.
  - Under the app's RichHandler at 80 columns (`ver73/rich_80.txt`), the line holding the id is the bare uuid with no "ERROR" or "search crashed" on it.
- Also: every other line in `core/run.py` writes `trace_id=<id>`, while the crash record now writes `trace <id>`. A developer searching `trace_id=<id>` finds every other line for the trace but not the crash line.
- Why it matters: a log viewer that stores one entry per line (most container log collectors) returns the id line alone for a trace id search. The developer gets "it crashed" but not why, and has to open the surrounding lines by time. That is a step back from the pre-fix record on any handler that does not wrap. Under Rich the old record was already split, so there it is no worse. What to check on develop: search a crash's trace id in the deployed log viewer and see whether the class and frames come back with it.
- NOT FIXED

### F-73-V02: an exception group's member is named but its frames are not, so the task that failed inside a TaskGroup is still unnamed
- Severity: minor (the rest of F-73-A03)
- What: `group_members=` lists member classes only. Neither the member's traceback nor its cause chain is read. `innermost` is found by walking `__cause__`/`__context__`, never `.exceptions`.
- Reproduction: `ver73/p2_graph.py A03`, real graph, `asyncio.TaskGroup` whose task does `{}["MISSING_" + MARK]`: `group_members=builtins.KeyError`, and the frames end `graph.py:1780 in guardrail_node > p2_graph.py:81 in taskgroup > taskgroups.py:147 in __aexit__`. The task's function `leaf` appears nowhere.
- Why it matters: the reachability is unsure (no TaskGroup in `src/` today, anyio groups exist in the dependency tree). Where it happens, a developer learns the kind of error and the node, not which task failed.
- NOT FIXED

### F-73-V03: `_log_crash` can still raise when a hostile exception object raises a BaseException from one of its hooks; its docstring says it never raises
- Severity: note (synthetic; in the real graph LangChain's own tracer fails on the same object first)
- What: both guards in `_log_crash` (`core/run.py:319`, `:325`) catch `Exception`. A `KeyboardInterrupt`, `SystemExit`, `GeneratorExit` or `asyncio.CancelledError` raised from an exception's `__cause__`, `__class__` or `__traceback__` property goes straight through.
- Reproduction (`ver73/p1_direct.py`, direct call): all twelve combinations print `RAISED <that class> ... records=0`. Examples: `[__cause__ property raises CancelledError] RAISED CancelledError`, `[__class__ property raises SystemExit] RAISED SystemExit`.
- Through the real graph (`ver73/p2_graph.py`): a crash whose `__cause__` property raises CancelledError gives `run person=[] raised=CancelledError crash_records=0`. Through the registry it gives `person=['error'] msg='this run was stopped before it finished'`, so the person sees Stop, not a failure.
- I could not tell which layer raised first. The KeyboardInterrupt variant's traceback shows `langchain_core/tracers/core.py:119 _get_stacktrace -> traceback.format_exception` failing on the same property before `run()`'s handler is reached. So this is not solely `_log_crash`'s doing, and no real exception class does this. Recorded because the docstring's "It never raises" is not true as written. Widening to `BaseException` would swallow a real KeyboardInterrupt, so this may be accepted as is.
- NOT FIXED

### F-73-V04: the whole traceback is walked, with source lines read, before the cap is applied, so a pathologically long traceback blocks the event loop
- Severity: minor, unsure on reachability. This is not new in da0fe4b0: 6afd295e had the same full `extract_tb`, and da0fe4b0 now runs it twice, for the outer and the innermost exception.
- What: `_crash_frames` (`core/run.py:243`) calls `traceback.extract_tb(exc.__traceback__)` with no limit, and that call reads each frame's source line through linecache, then keeps 33. `_log_crash` is synchronous inside the async handler, so the time is spent on the event loop that serves every other search.
- Reproduction (`ver73/p1_direct.py`): the same exception object re-raised in a loop, each raise prepending traceback entries, the known retry-loop leak shape.
  - 10000 entries: `ms=39.15`.
  - 200000 entries: `ms=854.76`.
  - 1000000 entries: `ms=4141.97`.
  - Each record is still about 1050 characters, so the cap holds; only the time is unbounded.
- Reachability: I found no pattern in `src/` that re-raises a stored exception object (`grep "raise self._|raise last_"` returned nothing). A library that caches and re-raises one failure object across calls would build it. LangChain's tracer also formats the full traceback, so the framework already pays a similar cost.
- Fix shape, for whoever fixes it: walk `tb_next` to count, and extract only the head and tail with `StackSummary.extract(..., lookup_lines=False)`.
- NOT FIXED

### F-73-V05: the fallback line is 91 characters, over the 80 the fix states for the first line
- Severity: note
- Reproduction (`ver73/p1_direct.py`): `first='search crashed, trace 2ff4e9d4-6499-4167-9e92-8c54d8ab720e: crash record could not be built' firstlen=91`.
- Why it matters little: the id still ends at character 58, and `ver73/p4_rich.py` shows it whole at COLUMNS unset, 80, 120 and 200. It is recorded because fix.md's rule "first line under 80" holds only for the main record, and no test checks the fallback line's length.
- NOT FIXED

### F-73-V06: no test would notice if "innermost" picked the second link of the chain instead of the last
- Severity: note (test gap; the code is right)
- Reproduction: in a scratch copy of HEAD (`ver73/mut/`), changing `innermost = chain[-1]` to `innermost = chain[1] if len(chain) > 1 else chain[0]` leaves `test_run.py` at `58 passed`, because every innermost test uses a two-link chain. The code itself is correct: a direct three-link probe (ValueError from OSError from KeyError) gives `innermost_frames (builtins.KeyError): <stdin>:9 in middle, <stdin>:7 in deepest`.
- My other mutations were caught: an outer guard narrowed to AttributeError (2 failed), no file-name clip (1 failed), the cycle check removed (1 failed), only one group member listed (1 failed). Control: 58 passed.
- NOT FIXED

## Verified by my own probes versus read only

- Run, with output quoted above: every J and A verdict except J04 and J07, which are trade-offs I confirmed from the probe records rather than reproduced separately. Also run: the person's screen (`['error', 'done']` with "This query failed unexpectedly before it could complete.") on run, run_streaming and a real `RunRegistry` for every Exception-shaped crash; no marker from a message, argument, local, note or DB password in any record of any logger at DEBUG; the first line (58 characters for a real uuid, 70 at most); the size caps; the J05 rendering under the app's real handler at four widths; six mutations of my own.
- Read, not run: the deployed log viewer's line grouping (V01) and the deployed console width. No request was made to a deployed app. I did not run the full unit suite, ruff or isort, so fix.md's gate counts are its own.
- Nothing in the worktree was changed except this report. Probes and the mutation copy live in the session scratchpad under `ver73/`.

## Verdict: MERGE WITH NAMED ITEMS

The card holds under my probes. A crash writes one record findable by the full trace id on both entry points, and the person's screen is unchanged, including when the record cannot be built. No J or A finding is NOT FIXED or REGRESSED. Named items:

- F-73-V01 (minor, unsure). INSIDE THIS PHASE'S FIX, which fires the review loop's stop condition: the multi-line record puts the reason on lines with no trace id. Check a trace id search on develop's log viewer after merge, and decide whether that is acceptable.
- F-73-V02 (minor): the rest of A03, member frames.
- F-73-V04 (minor, unsure): an unbounded traceback walk on the event loop, pre-existing since 6afd295e.
- F-73-V03, V05, V06: notes.
- F-73-J06: needs its own card, the same user problem in `core/graph.py`.
- F-73-A07: the product owner's decision, to be asked now.
- F-73-A04, A05, J04, J07: open as named, correctly out of this card.
