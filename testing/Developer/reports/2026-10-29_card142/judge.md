# Card 142 judge, round 1 (draft PR #315)

Judge: independent reviewer, one round, on `git diff -w origin/develop...HEAD` at b27c1b51. Findings appended as established.

## Findings

Method for every real-signal line below: own stub (`scratchpad/j142/stub.py`, Starlette SSE serving create, events and stop; on a confirmed stop it sends the server's real cancelled fatal error and closes, as `core/run_registry.py:637-656` does) and own probe (`scratchpad/j142/probe.py`): `python -c "...main import main; sys.exit(main())" ask q --session-id s1`, which is what the `s3` console script in `pyproject.toml:87` runs, as a child in its own session, real SIGINT by `os.killpg`. Develop is `git archive origin/develop` (b5690f98) run by the same probe. Scratchpad root: <session scratchpad, not published>/j142/

### J-142B-01: Evidence, one press: confirmed, failed, unusable reply, slow, already finished (both endings)
- Severity: evidence, not a defect
- Branch, one SIGINT 0.3 s after the stub sent a token and a citation:
  - confirm: rc 130 at 0.41 s; stderr 0.1 s after the press already `s3: interrupted, stopping the run...\ns3: the run was stopped at your request; the answer above is incomplete.\n`; stdout keeps `Not verified · the run did not finish` and the references block. Develop, same probe: rc 130, stderr `s3: interrupted, stopping the run...\nerror: the run ended before a final answer was received; ...` (the card, reproduced on develop).
  - stop 500: rc 130 at 0.42 s, second line `s3: the server did not confirm the stop, so the run may still be going; the answer above is incomplete.`
  - stop 200 `{"nope": 1}`: rc 130 at 0.41 s, the same unconfirmed line (KeyError path, `main.py` `_STOP_REPLY_FAILURES`).
  - stop sleeps 30 s: stderr at 0.1 s is `s3: interrupted, stopping the run...\n` only; rc 130 at 3.35 s with the unconfirmed line. Owner clause 1 and 2 hold.
  - `stopped: false`, stream left open: rc 130 at 3.38 s, lines `...already finished, so there was nothing to stop.` then `s3: the rest of the answer did not arrive in time; the answer above is incomplete.` (V-142-05 answered: develop's trap of #298 is gone).
  - `stopped: false`, then the stub sends the rest and `done`: rc 0 at 0.55 s, stdout `TP53 ... pathogenic rest of the answer.\n[answer]\n\nReferences:...`, stderr the stopping line and the already-finished line only.
- No line on any of these runs contains "error".

### J-142B-02: A run whose `done` arrives while a slow stop call is pending is reported as "may still be going; the answer above is incomplete", and its `done` is thrown away
- Severity: minor (inside this build's new code, the held-events branch of `_consume_stream_with_interrupt`; develop's outcome on this path was also wrong, so not worse than develop, but the sentence is new and untrue)
- What: while the stop call is in flight every stream event is appended to `held` and never inspected (`main.py`, the `if stop_task is not None and not stop_answered: held.append(task)` branch). When the 3.0 s bound passes, the code prints `_STOP_UNCONFIRMED_LINE` and returns 130, discarding `held`, even when `held` already contains the run's terminal `done`. The program has in hand proof that the run finished, and says the opposite.
- Reproduction: stub `SCENARIO=held_done STOP_MODE=confirm STOP_SLEEP=30` (token and citation, then `done` 0.3 s after the stop request arrives, then the stream closes). One SIGINT at 0.3 s. Branch: rc 130 at 3.36 s, stub log `create, sent, stop, sent_done`, stderr `s3: interrupted, stopping the run...\ns3: the server did not confirm the stop, so the run may still be going; the answer above is incomplete.\n`, stdout ends `Not verified · the run did not finish` with no `[answer]` verdict. Develop, same probe: rc 130 at 15.37 s, `error: the run ended before a final answer was received`.
- Why it matters: the realistic trigger is a press during the last second of an answer while the network to the server is slow. The person is told the run may still be running and the answer is cut off when the run finished and its verdict was received. The real server cannot confirm here (`core/run_registry.py:711-713` answers false once `done` is sent), so only the slow or failed stop call reaches it.
- What a person sees: "the run may still be going; the answer above is incomplete" under an answer that had in fact finished.
- NOT FIXED

### J-142B-03: Evidence, two presses at each phase, a press before the first event, a press during the final answer, and `--json`
- Severity: evidence, not a defect
- Branch, real SIGINTs (delays after the stub's marker):
  - slow stop (30 s), presses 0.3 and 0.8: rc 130 at 0.91 s, stderr `s3: interrupted, stopping the run...\ns3: interrupted again, exiting immediately; the stop was not confirmed, and the answer above is incomplete.\n`. Owner clause 3 holds; V-142-04 answered.
  - confirmed stop, presses 0.3 and 0.8: the process had exited (rc 130 at 0.81 s) before press 2; two lines only.
  - "already finished", stream open, presses 0.3 and 1.2: rc 130 at 1.32 s, third line `s3: interrupted again, exiting immediately; the answer above is incomplete.`
  - "already finished", `done` 0.2 s after the stop, presses 0.3 and 0.35: rc 130 at 0.51 s, same third line, `done` never shown (the person asked twice to leave; acceptable).
  - before the first event (stub sleeps before sending anything), one press at 0.5: rc 130 at 0.61 s, `...stopping the run...` then `...stopped at your request; the answer above is incomplete.`, stdout empty. Two presses with a slow stop: rc 130 at 1.11 s, the "interrupted again ... not confirmed" line.
  - during the final answer (stub streams a token every 0.1 s), one press at 1.0: confirm, rc 130 at 1.11 s, stdout `word0 ... word9 \nNot verified · the run did not finish`; slow stop, rc 130 at 4.05 s with the unconfirmed line.
  - `--json`: confirm, rc 130, `error.message` `s3: you stopped this search. Start a new search if you still need an answer.` (develop's text, unchanged); slow stop and second press, the "did not confirm ... may still be going" message; "already finished" then `done`, rc 0, `"complete": true`, `"error": null`; "already finished", stream open, rc 130 at 3.38 s, the "cut_off" message. Every stdout parsed as one complete JSON object.
- Develop's CLI tests (455, from `git archive origin/develop`) run against the branch's `src`: `6 failed, 449 passed`; the same 6 fail against develop's own `src` (`6 failed, 449 passed`), all in `test_system3_cli_package.py`, because the archive has no `clients/` folder. So develop's own Ctrl-C and rendering tests pass unchanged on the branch.

### J-142B-04: With nothing on stdout, the stop lines still say "the answer above is incomplete"
- Severity: minor (wording, inside this build's new lines `_STOPPED_LINE`, `_STOP_UNCONFIRMED_LINE`, `_SECOND_PRESS_*`)
- What: a press before the first token prints a line about "the answer above" when no answer was printed. The same lines go to stderr under `--json`, where the answer is in a JSON object, not "above".
- Reproduction: stub `SCENARIO=late_first STOP_MODE=confirm`, one SIGINT 0.5 s after the events request: rc 130, stdout empty (0 bytes), stderr `s3: interrupted, stopping the run...\ns3: the run was stopped at your request; the answer above is incomplete.\n`.
- What a person sees: "the answer above is incomplete" with nothing above it. Not untrue in a harmful way; filed so it is not lost.
- NOT FIXED

### J-142B-05: A second Ctrl-C while a stopped run's references are still being written prints a 15-line Python traceback; develop prints none
- Severity: major (inside this build's new code: the stream generator is left suspended at its `yield` when `_consume_stream_with_interrupt` returns; worse than develop on this path; the card is about calling the person's stop an error, and this is a raw `RuntimeError` on the owner's "hard exit")
- What: after a confirmed stop, `_run_ask` calls `renderer.finish(stopped_by_person=True)`, which writes the references synchronously. If stdout drains slowly (a pager, a slow pipe, a long references list) the second press lands there, outside the stream window, and interpreter shutdown finalizes `CliClient.stream_events`, which the branch left suspended at `yield event` (`client.py:903`) because events were held rather than the read cancelled. Finalization fails: `RuntimeError: generator didn't stop after athrow()`.
- Reproduction: stub `SCENARIO=done_open NCIT=2500 STOP_MODE=confirm`, stdout a pipe left unread until 0.5 s after the last press (`OUT=block`), real SIGINTs at 1.0 and 1.2 s. Branch, 4 of 4 runs: rc 130 at 1.82 s, stderr:
  ```
  s3: interrupted, stopping the run...
  s3: the run was stopped at your request; the answer above is incomplete.
  an error occurred during closing of asynchronous generator <async_generator object CliClient.stream_events at 0x10809e5c0>
  asyncgen: <async_generator object CliClient.stream_events at 0x10809e5c0>
  Traceback (most recent call last):
    File ".../adapters/cli/client.py", line 903, in stream_events
      yield event
  GeneratorExit
  During handling of the above exception, another exception occurred:
  Traceback (most recent call last):
    File ".../adapters/cli/client.py", line 876, in stream_events
      async with self._http.stream(
    File ".../contextlib.py", line 257, in __aexit__
      raise RuntimeError("generator didn't stop after athrow()")
  RuntimeError: generator didn't stop after athrow()
  s3: interrupted
  ```
  Develop, same probe, 4 of 4 runs: rc 130, stderr `s3: interrupted, stopping the run...\nerror: the run ended ...\ns3: interrupted\n`, no traceback.
- Diagnosis by temporary edit (restored, `git status --short` after: only `?? frontend/node_modules` and this file): awaiting the cancelled read in the `finally` (`await asyncio.wait({pending_next}, timeout=1.0)`) did NOT remove it (3 of 3 still traced). Adding `await stream_iter.aclose()` in the `finally` after a press removed it (3 of 3: stderr only the two stop lines and `s3: interrupted`). So the cause is the open generator, not the pending task.
- What a person sees: they press Ctrl-C twice to get out and get a Python traceback with "RuntimeError" under the stop line.
- NOT FIXED

### J-142B-06: Evidence, A-142-01, A-142-02 and A-142-04 answered under real signals and real pipes
- Severity: evidence, not a defect
- A-142-01 and A-142-02 (press while a finished answer's references are being written into a slow pipe): stub `done_open NCIT=1500`, stop answers false once `done` is sent (the real registry's rule, `core/run_registry.py:711-713`), stdout unread until 0.5 s after the press, SIGINT at 5.0 s. Branch, 3 of 3: rc 0, stub log `create, sent` (no stop sent), stderr empty, stdout 99475 bytes ending `[1500] clinvar - .../VCV000001500`. Two presses (5.0, 5.2): rc 0, stderr empty. Develop, same probe: rc 130, stub log `create, sent, stop, stop_after_done_false`, stderr `s3: interrupted, stopping the run...\nTask exception was never retrieved\nfuture: <Task finished ... exception=StopAsyncIteration()>\nStopAsyncIteration\n`.
- A-142-04 (`| tee`, `| head -n 500`, SIGINT to the whole process group as a terminal does): branch, `tee` confirm rc 130 at 0.46 s, `head` rc 130 at 0.41 s, `tee --json` rc 130, `tee` slow stop rc 130 at 3.43 s, `tee` two presses rc 130 at 0.91 s, `tee` "already finished then done" rc 0; in every one stderr is only the stop lines, no `BrokenPipeError`, no `Exception ignored`. Develop `tee` confirm: rc 130 with the `error:` line. (In these runs `tee` survives the SIGINT long enough that no broken pipe fires; the broken pipe path itself is covered by the author's subprocess test, which I mutated in J-142B-09.)
- A scan of the stderr of all 62 probe runs for `never retrieved`, `Exception ignored`, `Traceback` and `unexpected error` finds only the J-142B-05 runs.

### J-142B-07: When the server says the run had already finished but the client is still reading a large backlog, the answer is cut at the 3 s bound and called incomplete
- Severity: minor (inside this build's new bound; better than develop, which cut sooner with an `error:` line; reachable only with a backlog that takes the client over 3 s to read)
- What: the bound that starts at the press also limits reading events the server had already sent. A finished answer still in the socket is cut, and the person is told "the rest of the answer did not arrive in time; the answer above is incomplete", exit 130.
- Reproduction: stub `done_open NCIT=2500`, stop answers false once `done` was sent, stdout unread until 0.5 s after the press, SIGINT at 1.0 s. Branch, 3 of 3: rc 130 at 4.69 to 5.01 s, stderr `...stopping the run...\n...already finished, so there was nothing to stop.\ns3: the rest of the answer did not arrive in time; the answer above is incomplete.\n`, stdout ends at reference [2282], [1877] and [2251] of 2500. Develop: rc 130 at 2.10 s, `error:` line, stdout ends at [1447].
- What a person sees: "nothing to stop", then "the answer above is incomplete" for an answer the server had finished sending. The words are true from the program's side; filed for the owner's call on whether the bound should restart when the server says "finished".
- NOT FIXED

### J-142B-08: Evidence, a real broken pipe after Ctrl-C (V-142-09 answered), and uninterrupted runs unchanged
- Severity: evidence, not a defect
- Real pipe whose reader is closed 0.2 s after the stream starts, then real SIGINT (`OUT=closedpipe` in `scratchpad/j142/probe.py`, an `os.pipe()` given to the child as stdout). Branch: confirm rc 130 at 0.57 s, `--json` rc 130, slow stop rc 130 at 3.57 s, slow stop and second press rc 130 at 1.07 s, "already finished then done" rc 130; stderr in every case only the stop lines. Develop, same probe: rc 120, stderr `...stopping the run...\nerror: the run ended ...\ns3: unexpected error (BrokenPipeError)\nException ignored in: <_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>\nBrokenPipeError: [Errno 32] Broken pipe\n`.
- Uninterrupted runs, branch against develop, same stub: a normal run (token, citation, `done`, close) human and `--json`: rc 0 on both, stdout and stderr byte-identical (`cmp` silent). A stream that never closes and no press, human and `--json`: still running at 80 s on both (the probe killed them), stdout and stderr byte-identical. The never-ending wait is pre-existing and outside this card.

### J-142B-09: With `2>&1 | tee` and the reader gone, Ctrl-C sends no stop at all, because the stopping line is written before the stop call
- Severity: minor (pre-existing, develop sends no stop here either; filed because this build chose the order "line first, then stop" and the flush in `say()` is new)
- What: in `_consume_stream_with_interrupt` the first press runs `say(_STOPPING_LINE)` (write and flush) before `asyncio.ensure_future(client.stop(run_id))`. When stderr is a broken pipe, `say` raises `BrokenPipeError`, `_run_ask` catches it (ctrl_c.pressed is already True) and returns 130, and the stop request is never sent. The run keeps going on the server until its abandonment timer ends it.
- Reproduction: stdout and stderr both the write end of one `os.pipe()` whose read end is closed 0.2 s in (`OUT=closedpipe2`), real SIGINT at 0.4 s, stub `mid`. Branch human and `--json`: rc 130, stub log `create, sent` (no `stop`). Develop: rc 120, stub log `create, sent`.
- What a person sees: nothing (their reader is gone); the cost is a server run the person asked to stop that is not stopped.
- NOT FIXED

### J-142B-10: Break it, results for 21 mutations (runner `scratchpad/j142/mut.py`, CLI suite each time, file restored with `git checkout --` after each)
- Severity: evidence; the four green rows are filed as J-142B-11 to J-142B-13
- Red (a test fails), with the failing tests:
  - bound not used (`deadline = loop.time() + 300.0`): 3 red, `test_the_stopping_line_appears_at_once_while_a_slow_stop_waits`, `test_a_slow_stop_exits_at_the_bound_and_claims_no_stop`, `test_one_press_exits_by_the_bound_when_the_server_says_finished_and_the_stream_stays_open`.
  - `_STOP_CONFIRM_BOUND_S` 3.0 to 10.0: 1 red, `test_the_confirmation_bound_is_a_few_seconds`.
  - second press ignored: 3 red, including develop's own `test_second_ctrl_c_during_a_slow_stop_returns_without_waiting_for_it`. Second press after "finished" ignored: 1 red.
  - press after the terminal event sends a stop: 2 red. "Rest did not arrive" says "unconfirmed": 1 red.
  - broken pipe: no `_quiet_a_broken_pipe` calls, 2 red (the real-pipe subprocess test, human and `--json`); `os.dup2` replaced by `pass`, 2 red (V-142-09 answered); every broken pipe made quiet, 1 red; `ValueError` caught too, 1 red (V-142-06 answered).
  - stop failures without `httpx.HTTPError`: 2 red. Stopping line written after the stop call: 2 red. `--json` confirmed message changed: 1 red. `Renderer.finish` ignores `stopped_by_person`: 7 red. Exit code 1 instead of 130: 7 red.
- Green (no test fails): "finished" path does not exit at `done`; held terminal not acted on; stop failure caught as broad `Exception`; `KeyError` dropped from `_STOP_REPLY_FAILURES`; `held` stream end never marks `stream_over`; `say()` without `flush()`.
- `git status --short` after the run: `?? frontend/node_modules` and `?? testing/Developer/reports/2026-10-29_card142/judge.md` only.

### J-142B-11: Break it, the "already finished, then `done`, stream stays open" exit is not pinned by any test
- Severity: minor (test gap on this build's own control; the shipped code works)
- What: replacing `if ctrl_c.pressed and terminal_seen: return None` with `pass`, or removing the `if terminal_seen: return None` inside the held-events replay, leaves the CLI suite at 473 passed. The test fake's `done_on_stop` ends the stream right after `done`, so the stream's own end exits either way.
- Live check of the shipped code: stub `done_after_stop_open` (stop answers false, then the rest and `done`, then the stream stays open), one SIGINT: rc 0 at 0.63 s, stderr `...stopping the run...\n...already finished, so there was nothing to stop.\n`; `--json` `"complete": true`, `"error": null`. With the mutation the same run would wait for the 3 s bound and then say "the rest of the answer did not arrive in time; the answer above is incomplete" under a complete answer, exit 130.
- What a person sees if it regresses: a finished answer called incomplete, with the suite green.
- NOT FIXED

### J-142B-12: Break it, the narrow match on a failed stop call is not pinned, and the `KeyError` branch has no test
- Severity: minor (test gap; the builder's account claims "No broad `Exception`" as a property, and nothing holds it)
- What: `except (*_client_typed_errors(), *_STOP_REPLY_FAILURES):` replaced with `except Exception:` stays green (473 passed); dropping `KeyError` and `TypeError` from `_STOP_REPLY_FAILURES` stays green. The fake `stop` never returns a 200 without `stopped`, and never raises an unexpected class.
- Live check of the shipped code: stop answers 200 `{"nope": 1}`: rc 130, the "did not confirm the stop" line (J-142B-01). So it works today, unpinned.
- NOT FIXED

### J-142B-13: Break it, a stream that ends while the stop call is pending is not pinned; breaking it gives a busy loop with the suite green
- Severity: minor (test gap on this build's own `held`/`stream_over` logic)
- What: replacing `if task.exception() is not None: stream_over = True` with a branch that never sets `stream_over` stays green (473 passed). With it broken, a stream that ends during the stop wait is read again at once on every turn of the loop (an exhausted generator raises `StopAsyncIteration` immediately), appending to `held` until the stop answers or the bound passes: a busy loop for up to 3 s, and every one of those tasks is retrieved only by luck.
- Evidence the shipped code is right: in the J-142B-01 confirm runs the stub closes the stream after its cancelled event while the stop answer is in flight, and the CLI exits at 0.41 s with clean stderr.
- NOT FIXED

Erratum to J-142B-13: the "evidence the shipped code is right" line is not established. In my stub the cancelled event is polled every 0.1 s after the stop reply, so the stream may end after the stop answers, not during it. The shipped `stream_over` branch is read, not exercised by any probe of mine.

### J-142B-14: Production standards, read and probed
- Severity: evidence, with one unsure point
- Network timeouts: the stop call keeps `timeout=_REST_CALL_TIMEOUT_S` (`client.py:1086`) and is never awaited past `_STOP_CONFIRM_BOUND_S` (`main.py:1283`, used once as the `deadline`); probed: a 30 s stop exits at 3.35 s (J-142B-01).
- Tasks after exit: a stop call still running at the bound is left to `asyncio.run` (`main.py:1838`), which cancels it at teardown; probed, every slow-stop run exits by 3.6 s with clean stderr. The stream generator is left suspended at its `yield` on every press exit; that is J-142B-05.
- Busy loop: none seen; `asyncio.wait(..., timeout=max(0.0, deadline - loop.time()))` blocks on real futures. The one path that could spin is J-142B-13 (unpinned, shipped code reads right).
- Exception breadth: `except BrokenPipeError` (`main.py:1224`) re-raises when no press; `except OSError` (`main.py:1268`) only around the `dup2`. Unsure: `TypeError` in `_STOP_REPLY_FAILURES` (`main.py:1341`) turns any `TypeError` raised inside `client.stop`, including a programming fault, into "the server did not confirm the stop" with no trace of the cause.
- No threads are added.

Erratum to J-142B-14: the bound is defined at `main.py:1278` and used at `main.py:1587`, not `main.py:1283`. The held-events append cited in J-142B-02 is `main.py:1562`.

## Verdict

FAIL, blocking: J-142B-05.

- J-142B-05 sits inside this build's own code (the stream generator left suspended when a press ends the stream), is worse than develop on the same probe (4 of 4 against 0 of 4), and puts a Python traceback with "RuntimeError" on the owner's third clause, the second Ctrl-C hard exit. Under the review loop's rule a finding inside the phase's own fix escalates rather than taking another silent round.
- The owner's three clauses otherwise hold under real signals: the stopping line is on screen 0.1 s after the press in every probe; the stop is confirmed in the background and never waited on past 3 s; a second press exits at once at every phase probed.
- Verified by my own probes: J-142B-01, 03, 05, 06, 07, 08, 09, 10, 11 (live part), 12 (live part), the `ruff check .` result (`All checks passed!`, ruff 0.16.0) and gate02's isort command (`Skipped 2 files`, exit 0), the CLI suite (`473 passed in 14.20s`), and develop's 455 tests against the branch's `src` (`6 failed, 449 passed`, the same 6 packaging tests failing on develop's own `src` in my archive).
- Only read, not exercised: the `stream_over` branch (J-142B-13), the `TypeError` breadth (J-142B-14), and that the abandonment timer ends the run J-142B-09 leaves unstopped.
