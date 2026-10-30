# Card 142 build: Ctrl-C is the person's own stop, never an error

Second attempt at card 142, after pull request #298 was closed. It follows the owner's decision of 2026-10-25: the stop line prints at once, the stop is confirmed with the server in the background under a short bound, and a second Ctrl-C stays the hard exit. Every finding from `testing/Developer/reports/2026-10-22_card142/` (judge, adversary, verify) was used as an acceptance test.

## Table of contents

- [What the person sees](#what-the-person-sees)
- [Design](#design)
- [How each finding is answered](#how-each-finding-is-answered)
- [Exit codes](#exit-codes)
- [Tests](#tests)
- [Break it](#break-it)
- [Real signal probes](#real-signal-probes)
- [Left as they are](#left-as-they-are)
- [Fix round](#fix-round)
- [Fix round, left](#fix-round-left)

## What the person sees

These are real runs: a real SIGINT sent to the command line, which talks to a local stub server. Scenario: one token and one citation arrive, then the stream stays open.

One Ctrl-C, and the server confirms the stop. Exit 130, 0.1 s after the press.

```
TP53 has three ClinVar records [1]. The first is pathogenic
Not verified · the run did not finish

References:
[1] clinvar - https://www.ncbi.nlm.nih.gov/clinvar/VCV000123
```

stderr:

```
s3: interrupted, stopping the run...
s3: the run was stopped at your request; the answer above is incomplete.
```

Two presses 0.5 s apart while the stop call is slow (it answers after 30 s). Exit 130, 0.1 s after the second press. stdout is the same as above. stderr:

```
s3: interrupted, stopping the run...
s3: interrupted again, exiting immediately; the stop was not confirmed, and the answer above is incomplete.
```

The other endings of one press, as stderr lines after "s3: interrupted, stopping the run...":

| Situation | Second line | Exit, time after the press |
|---|---|---|
| Stop call fails (500) | s3: the server did not confirm the stop, so the run may still be going; the answer above is incomplete. | 130, 0.1 s |
| Stop call does not answer | the same line | 130, 3.1 s |
| Server says the run had already finished, stream stays open | s3: the run had already finished, so there was nothing to stop. then s3: the rest of the answer did not arrive in time; the answer above is incomplete. | 130, 3.1 s |
| Server says the run had already finished, `done` then arrives | s3: the run had already finished, so there was nothing to stop. | the run's own code (0) |
| The run's `done` had already arrived | no line at all, no stop sent | the run's own code (0), at once |

On develop the first case printed "error: the run ended before a final answer was received; ..." under the stop line. That is the card.

## Design

All of it is in `src/system_03_search_agent/adapters/cli/main.py`, `_consume_stream_with_interrupt`, with one keyword added to `render.py`.

- First press: `_STOPPING_LINE` (develop's own words, "s3: interrupted, stopping the run...") is written and flushed before anything else happens. The stop call starts as a background task. A deadline is set at `_STOP_CONFIRM_BOUND_S` = 3.0 s.
- While the stop call is in flight, events that arrive are held, not shown. This means a stopped run's own `cancelled` error event never prints an "error [run]" line.
- The server confirms: `_STOPPED_LINE`, exit 130, held events dropped.
- The stop call fails, or the deadline passes first: `_STOP_UNCONFIRMED_LINE`, exit 130. The stop call is never awaited past the bound. It is left running, as develop already did for a second press.
- The server answers `stopped: false`, so the run had already finished: `_ALREADY_FINISHED_LINE`. The held events and the rest of the stream are then shown as a normal run. The program exits as soon as the run's terminal event (`done` or a fatal `error`) is shown, without waiting for the stream to close. If no terminal event comes by the same deadline, it writes `_REST_DID_NOT_ARRIVE_LINE` and exits 130.
- A second press at any point exits 130 at once. The line says the answer above is incomplete. It also says the stop was not confirmed when that is true.
- A press that comes after the run's terminal event was already shown sends no stop and prints no line. The run finishes as it stands. When an event and a press are ready in the same instant, the event is taken first.
- `Renderer.finish(stopped_by_person=True)` leaves out the "error:" line. It still prints the references for what arrived and the "Not verified · the run did not finish" notice. `JsonRenderer.finish` accepts the same keyword and ignores it, because `main` records the stop with `record_failure` first.
- `--json`: `error.message` stays "s3: you stopped this search. Start a new search if you still need an answer." for a confirmed stop. It gets its own wording when the stop was not confirmed, or when the rest of a finished run did not arrive.
- Broken pipe: `_run_ask` catches `BrokenPipeError`, and only that class, only after a press. It then calls `_quiet_a_broken_pipe` on stdout and stderr, which flushes each one. Only a stream whose flush fails has its descriptor pointed at the null device, so the interpreter's exit flush cannot fail again. A broken pipe with no press is raised as before.
- A failed stop call is matched narrowly: the client's typed errors, `httpx.HTTPError`, and `KeyError` or `TypeError` for a 200 reply with no usable `stopped` field. No broad `Exception`.
- Every done task is read before it is dropped, so asyncio prints no "Task exception was never retrieved".

## How each finding is answered

| Finding | Answer | Test |
|---|---|---|
| V-142-05, Ctrl-C absorbed when the server says finished and the stream stays open | Point 5 above: the same 3 s deadline covers the rest of a finished run, and a second press always exits | `test_one_press_exits_by_the_bound_when_the_server_says_finished_and_the_stream_stays_open`, `test_a_second_press_exits_at_once_when_the_server_says_finished_and_the_stream_stays_open` |
| V-142-03, nothing on screen for up to 15 s | The stopping line is written before the stop call is sent, and the wait is bounded at 3 s | `test_the_stopping_line_appears_at_once_while_a_slow_stop_waits`, `test_a_slow_stop_exits_at_the_bound_and_claims_no_stop` |
| V-142-04, a second press said only "interrupted again" | The first line is already on screen. The second says the answer above is incomplete, and that the stop was not confirmed when it was not | `test_a_second_press_during_a_slow_stop_exits_at_once_and_says_incomplete` |
| V-142-06, catching ValueError hid an encoding error | Only `BrokenPipeError` is caught. An encoding error reports "unexpected error (UnicodeEncodeError)", as on develop | `test_an_encoding_error_after_ctrl_c_is_still_reported` |
| V-142-09, the redirect was never tested | A child process with a real pipe whose reader is gone, and a real SIGINT | `test_ctrl_c_into_a_pipe_whose_reader_is_gone_exits_130_with_no_traceback` (human and `--json`) |
| A-142-01, a finished run told it was stopped | No stop is claimed unless the server confirms it. A press after the terminal event sends nothing. A tie goes to the event | `test_a_press_after_done_reports_no_stop_and_exits_at_once`, `test_a_press_in_the_same_instant_as_done_reports_no_stop`, `test_a_server_that_says_already_finished_gets_the_whole_answer_and_no_stop_claim` |
| A-142-04, a crash into `\| head` or `\| tee` | The broken pipe path above | the pipe test above, `test_a_broken_pipe_without_ctrl_c_is_still_reported` |
| J-142-01, a stop claimed before the reply | The past tense is used only after the server says `stopped: true` | `test_a_failed_stop_exits_promptly_and_claims_no_stop` |
| J-142-05, nothing guards the dropped connection error | A dropped connection with no press still prints the "error:" line and exits 1, through the real `Renderer` | `test_a_dropped_connection_without_ctrl_c_still_prints_the_early_end_error` |
| A-142-02, "Task exception was never retrieved" | Done tasks are read before they are dropped, in the loop's `finally` | covered by the real signal probes, whose stderr carries no such line |
| A-142-05, no word that the answer is incomplete | Every line that ends a stopped run says "the answer above is incomplete" | the line assertions above |

## Exit codes

Develop's 130 is kept for every run that a press ends. The design reports gave no reason to change it. A press that comes after the run had finished does not end the run, so that run keeps its own code, 0 for an answer. This matches V-142-01, which judged exit 0 with an empty stderr as right for that case.

## Tests

`tests/system_03_search_agent/adapters/cli/test_main.py`, class `TestCtrlCIsThePersonsOwnStop`, plus one child process test. They drive the real `async_main` with the real `Renderer`, using a fake `CliClient` whose stream can stay open, send `done` and stay open, or send `done` once the stop is called. Its stop call can confirm, say finished, fail, or answer after 30 s.

| Acceptance line | Tests |
|---|---|
| 1, the line at once and never "error" | `test_a_confirmed_stop_says_stopping_then_stopped_and_never_error`, `test_the_stopping_line_appears_at_once_while_a_slow_stop_waits` |
| 2, confirmed in the background under a short bound | `test_a_failed_stop_exits_promptly_and_claims_no_stop`, `test_a_slow_stop_exits_at_the_bound_and_claims_no_stop`, `test_the_confirmation_bound_is_a_few_seconds` |
| 3, a second press always exits | the two second press tests |
| 4, a finished run is never reported as stopped | the three A-142-01 tests |
| 5, pipes | `test_ctrl_c_into_a_pipe_whose_reader_is_gone_exits_130_with_no_traceback[False/True]` |
| 6, exit codes | asserted in every test above |
| 7, nothing else changes | `test_a_dropped_connection_without_ctrl_c_still_prints_the_early_end_error`, `test_a_broken_pipe_without_ctrl_c_is_still_reported`, `test_json_keeps_its_message_for_a_confirmed_stop`, and the existing suite unchanged apart from the fake renderer's `finish` signature |

Runs:

- CLI suite: `PYTHONPATH=src venv/bin/python -m pytest tests/system_03_search_agent/adapters/cli -q` printed `473 passed` (455 before, 18 new).
- `venv/bin/ruff check` on the three files printed `All checks passed!`.
- gate02's isort command, limited to the three files, exited 0.

## Break it

Each part was broken by hand, the CLI suite was run, and the file was restored from memory. `git status` afterwards showed only the three changed files.

| Break | Red |
|---|---|
| No stopping line at once | 9, including the slow stop and JSON tests |
| No bound | 3, slow stop and finished with open stream |
| Second press ignored | 3, including develop's own second press test |
| `stopped: false` read as stopped | 3, the finished path tests |
| Press taken before a ready event | 1, the same instant tie |
| No check for a run already finished at the press | 2 |
| Renderer ignores `stopped_by_person` | 7, including the real pipe test |
| Normal path passes `stopped_by_person=True` | 1, the dropped connection test |
| The `os.dup2` redirect removed | 2, the real pipe tests |
| `ValueError` caught with `BrokenPipeError` | 1, the encoding test |
| Every broken pipe made quiet | 1, the no-press broken pipe test |
| No exit at the bound after "finished" | 1 |
| A failed stop claims "stopped" | 1 |
| Events shown during the stop wait | 1 |

## Real signal probes

A local stub server serves `POST /v1/query`, the SSE stream and `POST /v1/query/{id}/stop`. The real command line runs as a child process, and real SIGINTs go to its process group, as a terminal sends them. No live model or API calls.

- One press, two presses, a slow stop, a failed stop, and "already finished" with the stream left open: outputs as in the first section.
- `| tee` and `| head -n 500`, human and `--json`: the command line exits 130 in 0.1 s. stderr carries only the two stop lines. The same `| tee` probe on develop exits 120 with "error: the run ended...", "s3: unexpected error (BrokenPipeError)" and "Exception ignored ... BrokenPipeError".
- `| tee` with two presses during a slow stop: exit 130, the two lines shown above.

## Left as they are

These were filed on #298 as pre-existing, and they are unchanged:

- A-142-03: `--json` cut off when a press lands after the stream window.
- A-142-06: no "how to pick" hint after a stopped question back.
- A-142-07: a non-fatal tool error line above the stop line.
- A-142-09 and V-142-08: presses during interpreter shutdown.
- J-142-03: references dropped after a mid-stream transport error.
- J-142-04: a press outside the stream window prints "s3: interrupted".

## Fix round

The one fix round after the judge (`judge.md`, FAIL on J-142B-05) and the adversary (`adversary.md`). Each fix is the smallest change that answers its finding. Files: `main.py` (`_consume_stream_with_interrupt` and `_STOP_REPLY_FAILURES`), `client.py` (`CliClient.stop` only), and the two CLI test files.

What the person sees now, real SIGINTs against the stub. One press, the server confirms. Exit 130, 0.4 s after the marker:

```
s3: interrupted, stopping the run...
s3: the run was stopped at your request; the answer above is incomplete.
```

Two presses, the second while 2,500 references are still being written into a slow pipe (the J-142B-05 probe). Exit 130, no traceback, 4 of 4:

```
s3: interrupted, stopping the run...
s3: the run was stopped at your request; the answer above is incomplete.
s3: interrupted
```

Two presses 0.5 s apart while the stop call is slow. Exit 130, 0.1 s after the second press:

```
s3: interrupted, stopping the run...
s3: interrupted again, exiting immediately; the stop was not confirmed, and the answer above is incomplete.
```

### How each finding is answered

| Finding | Fix | Test |
|---|---|---|
| J-142B-05, a second press prints a RuntimeError traceback | After a press, the `finally` of `_consume_stream_with_interrupt` awaits the cancelled stream read, then calls `stream_iter.aclose()`, so no stream is left suspended for the interpreter to finalize at exit | `test_the_stream_is_closed_after_a_press` (confirm, slow, finished; one and two presses) |
| A-142B-02, `"false"` read as stopped | `CliClient.stop` returns the field only when it is a JSON `true` or `false`; any other reply raises `CliApiError`, which the loop already reads as "not confirmed" | `test_a_reply_without_a_json_true_or_false_raises` (nine bodies), `test_an_unusable_stop_reply_is_called_unconfirmed` |
| A-142B-03, null, 0 or "" read as already finished | The same strict read | the same tests |
| J-142B-02, a held `done` thrown away | When the stop call fails or passes the bound, a held `done` is shown: `_ALREADY_FINISHED_LINE`, the rest of the answer, the run's own exit code | `test_a_done_held_while_the_stop_is_unconfirmed_is_shown_as_finished` (slow, late failure) |
| A-142B-01, a held fatal error thrown away | A held fatal error other than `cancelled` is shown as any fatal error is, exit 1. The stop's own `cancelled` event still prints no error line | `test_a_fatal_error_held_while_the_stop_is_unconfirmed_is_reported`, `test_a_held_cancelled_event_is_never_shown_as_an_error` |
| A-142B-06, stream closes with no final event after a press | After "already finished", a stream end with no terminal event exits 130 with `_REST_DID_NOT_ARRIVE_LINE`, never "error: the run ended..." | `test_a_stream_that_ends_with_no_final_event_after_finished_exits_130` (live and held) |
| J-142B-14, A-142B-05, `TypeError` caught | `_STOP_REPLY_FAILURES` is `httpx.HTTPError` only. A code fault in the stop call is reported as "s3: unexpected error (TypeError)", exit 1 | `test_a_fault_in_the_stop_call_is_reported_not_called_unconfirmed` (TypeError, KeyError, AttributeError, RuntimeError) |
| J-142B-11, exit at `done` after "already finished" unpinned | Test added; the fake's stream now stays open after `done` | `test_already_finished_exits_at_done_while_the_stream_stays_open` (live and held) |
| J-142B-12, narrow catch unpinned | Tests added | the fault test and the unusable reply test |
| J-142B-13, `stream_over` unpinned | Test added; the fake counts reads after the stream's end | `test_a_stream_that_ends_while_the_stop_is_pending_is_not_read_again` |

One side effect, named: `s3 stop` reads the reply through the same `CliClient.stop`, so a reply of `{"stopped": "false"}` now ends in the client error message instead of "run stopped". A JSON `true` or `false` behaves as before.

A held `done` is shown when the stop call fails or at the 3 s bound, not the moment it arrives, so on a slow stop call the finished answer appears 3 s after the press.

### Runs

- CLI suite: `504 passed` (473 before the round, 31 new test cases).
- `ruff check .`: `All checks passed!`. gate02's isort command: `Skipped 2 files`, exit 0.

### Break it

Each fix was broken in place, the CLI suite run, and the file restored from a copy held in memory.

| Break | Result |
|---|---|
| No `aclose` after a press | red, 6 cases of the closed-stream test |
| Client reads any truthy `stopped` again | red, 8 client cases |
| Client returns `bool(body["stopped"])` after the strict check | green, equivalent: the value is already a bool |
| Held terminal events ignored when unconfirmed | red, 4 |
| A held `cancelled` shown as an error | red, 1 |
| No already-finished line before a held `done` | red, 2 |
| A stream end after "already finished" treated as a normal end | red, 2 |
| `KeyError` and `TypeError` caught again | red, 2 |
| Every `Exception` caught | red, 4 |
| `httpx.HTTPError` not caught | red, 4, including the failed stop test |
| No exit at `done` in the live loop after "already finished" | red, 1 |
| No exit at a held `done` after "already finished" | red, 1 |
| `stream_over` never set | red, 1 |

### Real signal probes

The judge's and the adversary's probes, unchanged, run with a real SIGINT to the process group. "Develop" is the judge's archive of develop. The J-142B-05 probe is the judge's own: its stub log (`create, sent, stop, closed`) shows the stream scenario was `mid` with 2,500 citations, so that is what was rerun.

| Case | Branch now | Develop |
|---|---|---|
| J-142B-05, two presses during the references into a slow pipe | 130, 4 of 4 with no traceback: the two stop lines, then `s3: interrupted` | 130, 4 of 4, with the `error:` line (the judge's runs) |
| A-142B-02, `stopped: "false"` | 130 at 0.42 s, "did not confirm the stop" | 130, `error:` line |
| A-142B-03, `stopped: null` | 130 at 0.42 s, "did not confirm the stop" | 130, `error:` line |
| `{"nope": 1}`, body `[]` | 130 at 0.41 s, "did not confirm the stop" | not rerun |
| J-142B-02, `done` held, stop slow | 0 at 3.37 s, the already-finished line, stdout ends with `[answer]` and the references; `--json` `complete: true`, `error: null` | 130 at 15.39 s, `error:` line |
| A-142B-01, fatal error held, stop slow | 1 at 3.39 s, `error [agent]: this query failed unexpectedly before finishing.` | 130 at 15.37 s, `error:` line |
| A-142B-01, fatal error held, stop fails at 1 s | 1 at 1.36 s, the same error line | 130, `error:` line |
| A-142B-06, stream closes, no final event | 130 at 0.67 s, already finished, then the rest did not arrive; `--json` the `cut_off` message | 130, `error:` line |
| A-142B-05, a temporary TypeError fault in `CliClient.stop`, server cancels | 1 at 0.42 s, `s3: unexpected error (TypeError)` (edit restored) | not applicable |
| One press, confirmed | 130 at 0.41 s, stopping then stopped | |
| One press, stop fails (500) | 130 at 0.41 s, "did not confirm" | |
| One press, stop slow | 130 at 3.36 s, "did not confirm" | |
| Already finished, stream open | 130 at 3.39 s, already finished, then the rest did not arrive | |
| Already finished, then `done` (closed, and left open) | 0 at 0.56 s and 0.60 s, already-finished line only; `--json` `complete: true` | |
| Two presses: slow stop, confirmed, already finished | 130 at 0.91 s, 0.81 s (exited before press 2), 1.31 s | |
| Press before the first event: one press, two with a slow stop | 130 at 0.62 s, stopped line; 130 at 1.11 s, second press line | |
| Press during the final answer: confirmed, slow | 130 at 1.11 s; 130 at 4.06 s | |
| `\| tee`, `\| head -n 500`, `\| tee --json`, `\| tee` slow, `\| tee` two presses | 130 at 0.41, 0.41, 0.41, 3.37, 0.92 s, stop lines only | |
| Reader closed before the press | 130 at 0.52 s, stop lines only | |
| `--json` confirmed, slow | 130, "you stopped this search."; 130, "did not confirm" | |
| Press while a finished answer's references go into a slow pipe | 0, stderr empty, no stop sent | |
| No Ctrl-C, human and `--json` | 0, stdout and stderr byte-identical to develop (`cmp` silent) | 0 |

No stderr in any branch run carries `Traceback`, `never retrieved`, `Exception ignored` or `RuntimeError`.

## Fix round, left

Named, not fixed, as the fix brief says:

- J-142B-04: "the answer above is incomplete" with nothing above it.
- J-142B-07: a large backlog after "already finished" is cut at the 3 s bound.
- J-142B-09: with `2>&1 | tee` and the reader gone, no stop is sent.
- A-142B-04: a stop call stuck in a name lookup delays exit about 20 s, the same as develop.
- A-142B-07: stop lines glued into the answer's last word on a terminal.
- A-142B-08: three or more quick presses under `--json` can leave stdout empty, as on develop.
- A-142B-10: a second press in the same instant as the stop's answer says "not confirmed".
- A-142B-11: "had already finished" above a failed run's error line.
- A-142B-12: confirmed, unconfirmed and cut off differ only in `error.message`.
- A-142B-13: a rare "Task exception was never retrieved" on two presses 40 ms apart. The fix for J-142B-05 now awaits the cancelled read after a press, which is the mechanism the adversary named; not re-measured, so not claimed.
