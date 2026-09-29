# Card 73 fix round, 2026-09-29

The single fix round after one judge and one adversary round, on branch `fix/card73-crash-reason`. Only `src/system_03_search_agent/core/run.py` and `tests/system_03_search_agent/core/test_run.py` changed. Fixes are by category (Review_rounds Rule 2), not by the instances the reviewers happened to try.

## What a person and a developer notice

- The person: nothing changes. The crash still ends in the same `error` then `done` pair with the same sentence, and it now does so even when writing the log record itself fails.
- The developer: the log record's first line is `search crashed, trace <id>` and is under 80 characters, so a wrapping log handler cannot split the id. The lines after it carry the class, the cause chain, an exception group's member classes and the frames of the outermost and the innermost exception, with the entry point and the failure both kept.

## Findings

### Fixed

- F-73-J01 and F-73-A08: the logger can raise into the fallback path
  - Commit da0fe4b0, `core/run.py:295` (`_log_crash`), `core/run.py:231` (`_next_link` uses `is not None`).
  - By category: the whole body is inside one `try/except Exception`. A failure building the record logs one fixed line, `search crashed, trace <id>: crash record could not be built`, and a failure of that line too is swallowed, so `_log_crash` returns normally.
  - Tests: `test_a_crash_whose_record_cannot_be_built_still_gives_the_person_the_error_event` (run and run_streaming, a class with no `__module__`), `test_a_record_that_cannot_be_built_logs_one_fallback_line_carrying_the_trace_id`, `test_a_logger_that_itself_raises_never_costs_the_person_the_error_event` (run and run_streaming), `test_a_cause_whose_truthiness_raises_does_not_stop_the_record`.
- F-73-J05: the trace id was split by a wrapping handler
  - Commit da0fe4b0, `core/run.py:262` (`_crash_record`). First line is `search crashed, trace <id>`, the id cut to 48 characters so the line stays under 80.
  - Tests: `test_the_first_line_of_a_crash_record_starts_with_the_whole_trace_id_and_is_short` (both paths, the full id unbroken in the first line, length under 80), `test_a_very_long_trace_id_still_leaves_a_first_line_under_eighty_characters`.
- F-73-J02 and F-73-A01: only the deepest 30 frames were kept
  - Commit da0fe4b0, `core/run.py:243` (`_crash_frames`), constants at `core/run.py:208`. Keeps 8 outermost and 25 innermost frames and one line `... N frames omitted ...` between them.
  - Tests: `test_a_deep_traceback_keeps_the_entry_point_and_the_failure_and_counts_the_gap` (at least 5 head, at least 20 tail, the count exact), `test_a_short_traceback_is_listed_whole_with_no_omission_line`.
- F-73-A02: frames came from the outermost exception only
  - Commit da0fe4b0, `core/run.py:262`. When the innermost exception in the chain is not the outer one, an `innermost_frames (<class>):` section lists its frames under the same bounds.
  - Tests: `test_the_frames_of_the_innermost_exception_in_the_chain_are_in_the_record`, `test_the_innermost_exceptions_frames_obey_the_same_bounds`.
- F-73-A03: an ExceptionGroup showed only its own class
  - Commit da0fe4b0, `core/run.py:262`. A `group_members=` line lists the first 5 members' classes and `(+N more)`. Classes only, no messages.
  - Test: `test_an_exception_group_lists_its_members_classes_and_no_message`.
- F-73-J03: the chain rule differed from Python's own
  - Commit da0fe4b0, `core/run.py:231` (`_next_link`). `__cause__` when not None, otherwise `__context__` unless `__suppress_context__`; the chain is bounded at 8 links and a cycle ends it.
  - Tests: `test_the_chain_follows_the_cause_and_falls_back_to_the_context`, `test_a_falsy_explicit_cause_is_still_followed`, `test_raise_from_none_hides_the_suppressed_context`, `test_the_chain_is_bounded_and_a_cycle_ends_it`.
- F-73-A06: only counts were bounded, not lengths
  - Commit da0fe4b0, `core/run.py:221` (`_clip`, 100 characters for every class name, module path, file name and function name) and `core/run.py:218` (`_CRASH_LOG_MAX_CHARS`, 6000 for the whole record, first line kept).
  - Tests: `test_a_huge_class_name_module_file_and_function_name_are_each_cut`, `test_the_whole_record_has_a_size_ceiling_and_keeps_its_first_line`, `test_the_worst_case_record_stays_under_the_real_ceiling`.
- The no-message rule (decision 6) stays: `test_no_message_argument_or_local_reaches_the_record_from_any_link_or_group_member` covers a message, an argument and a local variable on the outer, the inner and a group member. The two earlier no-secret tests still pass.
- Commit a45c79fb, tests only: a crash logger that raises now fails its own test cleanly. The first version crashed the pytest run itself (an INTERNALERROR) because pytest tried to format the hostile exception, which hid the red result behind noise.

### Open, not in this card (named, not edited)

- F-73-J06: the step-level "A step in this query failed unexpectedly." in `core/graph.py` still logs nothing. Another builder is editing that file, and the fix needs it.
- F-73-A04: a `BaseException` that is not an `Exception` still ends the stream with no event and no record. It sits in `run.py`'s handlers' catch clause and in `run_registry.py`, and widening the catch changes Stop handling.
- F-73-A05: a failing `finally` after a crash still reaches the log only through asyncio's own handler, with its message and no trace id. The fix is in `core/run_registry.py`.
- F-73-A07: the older `session memory not loaded` warning at `core/run.py:491` and two neighbours log `exc_info=True`, so the full traceback with its message and absolute paths reaches the log on the most likely crash. Whether the no-message rule is a system property is the product owner's call.
- F-73-J04 and F-73-J07: the documented limits of logging names without messages. J04 is now bounded in length (A06) but still the developer-written premise; J07 is the price of the no-message rule.

## Break-it results

Each control was broken once in `core/run.py`, the file compared against the committed copy and restored, and the 58 tests in `test_run.py` run. Every break went red.

| Break | Result |
|-------|--------|
| No outer guard in `_log_crash` (J01, A08) | 5 failed, 53 passed |
| No guard on the fallback line | 2 failed, 56 passed |
| Trace id not cut | 1 failed, 57 passed |
| Class and detail put on the first line | 4 failed, 54 passed |
| Head frames set to 0 | 2 failed, 56 passed |
| Tail frames set to 5 | 2 failed, 56 passed |
| Omission count removed | 2 failed, 56 passed |
| No innermost frames | 2 failed, 56 passed |
| No group members | 1 failed, 57 passed |
| Group members bound raised to 50 | 1 failed, 57 passed |
| Chain uses `or` instead of `is not None` | 3 failed, 55 passed |
| `__suppress_context__` ignored | 1 failed, 57 passed |
| No per-name clip | 1 failed, 57 passed |
| No whole-record ceiling | 1 failed, 57 passed |
| Chain bound raised to 800 | 1 failed, 57 passed |
| Exception message appended to the record | 4 failed, 54 passed |

## Gate counts

- `tests/system_03_search_agent/core/test_run.py`: 58 passed (36 before this round).
- Full unit suite as `.github/gates/gate04_unit_suite.sh` runs it: 6570 passed, 143 skipped, 24 deselected, 1 xfailed, exit 0 (259 s). The builder's count was 6548, and the 22 new cases account for the difference.
- `ruff check .`: All checks passed, exit 0.
- `.github/gates/gate02_import_order.sh` (isort): exit 0.

## Commits

- da0fe4b0: the record shape, bounds and the never-raises guard, with 22 new test cases.
- a45c79fb: a raising crash logger fails one test cleanly.
- The docs commit carries `judge.md`, `adversary.md` and this file.

This was one code commit, not several: the record builder was rewritten as one unit, and splitting it by finding would have left intermediate commits that do not pass their own tests.
