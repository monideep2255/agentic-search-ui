# Card 142 fresh verification

Fresh verifier, 2026-10-22, branch fix/card142-ctrl-c-is-not-an-error at 474d3e56 (fix round 7cfd513c). Findings are appended as they are established.

## Findings

### V-142-01: A-142-01 and J-142-01 closed for a finished run: no stop line, exit 0 (evidence)
- Severity: unsure (filed as evidence, not a defect)
- What: with a stub whose `POST /stop` answers as the real registry does (`stopped` is false once `done` was sent) and whose stream closes 0.2 s after `done`, a real SIGINT landing while 600 references are still being written to an unread pipe ends with the full answer and exit 0.
- Reproduction: own stub `v142/stub2.py` (STOP_MODE=real), own harness `v142/vprobe.py br done_blocked blockpipe`. Branch: RC 0, stdout 128851 bytes ending at `[600] ...`, stderr `''`, marks `create, sent_done, stop`. Develop (`git archive origin/develop src`, bae47b6e): RC 130, stderr `s3: interrupted, stopping the run...` then `Task exception was never retrieved ... StopAsyncIteration`. So A-142-02's traceback is also gone on this path.
- Why it matters: the person who presses Ctrl-C a moment late keeps a good answer and a script sees success.
- NOT FIXED (evidence row, nothing to fix)

### V-142-02: A-142-04 closed under a real pipeline: Ctrl-C into `| tee` and `| head` exits 130 with one line
- Severity: unsure (evidence)
- What: the adversary's `harness.py` pipeline_tee branch references `t0` before it is set (a NameError), so a new harness was built: `v142/launch.py` puts the CLI and `tee` or `head -n 500` in one new session and process group, and `v142/vpipe.py` sends one `killpg(SIGINT)`, which is what a terminal does to a foreground pipeline.
- Reproduction: scenario `mid`. Branch, all four of tee/head x human/`--json`: cli rc 130, reader rc -2, stderr exactly `s3: the run was stopped at your request; the answer above is incomplete.\n`. Develop, the same four: cli rc 120, stderr carries `s3: unexpected error (BrokenPipeError)` and `Exception ignored in: <_io.TextIOWrapper name='<stdout>' ...> BrokenPipeError: [Errno 32] Broken pipe`.
- Why it matters: the common way to keep an answer no longer shows the word error or a traceback.
- NOT FIXED (evidence)

### V-142-03: Regression of: J-142-01 / A-142-01 fix (7cfd513c). A slow stop now leaves the person 15 s with nothing on screen after Ctrl-C, where develop answered at once
- Severity: minor (inside the fix round's code; worse than develop on this path)
- What: 7cfd513c moved the only stderr line in `_handle_interrupt_during_stream` to after `stop_task` resolves (`src/system_03_search_agent/adapters/cli/main.py:1296` `await asyncio.wait(...)`, then the writes at `main.py:1325` and `main.py:1333`). Nothing acknowledges the key press while the stop call waits for `_REST_CALL_TIMEOUT_S = 15.0`. Develop wrote `s3: interrupted, stopping the run...` before sending the stop. The wait length itself is unchanged (15.0 s versus 15.1 s), and the final line is true: "the run may still be going" is printed after a timed-out stop, rc 130.
- Reproduction: stub `STOP_SLEEP=60`, scenario `mid`, stderr to a file, real SIGINT, stderr read 5 s later (`PEEK=5 vprobe.py <br|dev> mid file`). Branch at 5 s: `''`; exit after 15.1 s, stderr `s3: you pressed Ctrl-C, but the server did not confirm the stop, so the run may still be going; the answer above is incomplete.\n`. Develop at 5 s: `s3: interrupted, stopping the run...\n`; exit after 15.1 s.
- Why it matters: a person who presses Ctrl-C and sees no sign of life for 15 s will press it again (see V-142-04) or think the tool is hung. Speed is a feature, and an acknowledgement costs nothing. A present-tense "s3: stopping the run..." before the wait, as develop had, would not overclaim and would keep the confirmed line after.
- NOT FIXED

### V-142-04: Regression of: A-142-05 / J-142-01 fix (7cfd513c). A second Ctrl-C now prints only "interrupted again", with no first line and no word that the answer is incomplete or the stop unconfirmed
- Severity: minor (inside the fix round's code; less honest than develop on this path)
- What: on the second-Ctrl-C branch (`main.py:1305` to `main.py:1313`) the only line written is `s3: interrupted again, exiting immediately`. The first line no longer exists before the wait, so "again" refers to nothing on screen, and neither `_STOP_LINE` nor `_STOP_UNCONFIRMED_LINE` is written, so the person is not told the answer above is incomplete or that the run may still be going. The human `finish(interrupted=True)` suppresses the error line, so nothing else says it either. `--json` is fine: its `error.message` says the stop was not confirmed.
- Reproduction: stub `STOP_SLEEP=60`, scenario `mid`, two real SIGINTs 2 s apart (`NSIG=2 GAP=2 vprobe.py <br|dev> mid blockpipe`). Branch: rc 130 after 2.0 s, stderr exactly `s3: interrupted again, exiting immediately\n`, stdout ends `Not verified · the run did not finish` plus references. Develop: rc 130 after 2.0 s, stderr `s3: interrupted, stopping the run...\ns3: interrupted again, exiting immediately\nerror: the run ended before a final answer was received; any answer text above is incomplete and its citations may be partial.\n`.
- Why it matters: this is the path V-142-03 pushes people onto. They leave with a cut-off answer and no statement that it is cut off or that the server may still be running, which is exactly the honesty A-142-05 was fixed to restore.
- NOT FIXED

### V-142-05: Regression of: A-142-01 fix (7cfd513c). When the server answers `stopped: false` but the stream does not end, Ctrl-C no longer exits: every press is absorbed silently and the run ends 44 s later as an error
- Severity: major (unsure how often the real server reaches it; inside the fix round's code; worse than develop on this path)
- What: on `"finished"` the loop `continue`s reading the stream (`src/system_03_search_agent/adapters/cli/main.py:1420`), writes nothing, and a later Ctrl-C starts the same cycle again, so no number of presses ends the program. It ends only when the stream read times out (`_STREAM_READ_TIMEOUT_S = 45.0`, `client.py:136`), then reports `the event stream ended unexpectedly (ReadTimeout)` with rc 1 and, through the pre-existing J-142-03 path, no references block under a `[1]` marker. The second-Ctrl-C escape exists only while a stop call is in flight, not across this loop. The real registry answers false for a finished, `done`-sent or already-cancelled run (`run_registry.py:1083`), and its stream normally closes soon after, so the trigger is a stalled or half-dead stream connection to a run that has finished.
- Reproduction: stub `STOP_MODE=false`, scenario `mid` (stream left open after one token and one citation), stdout to a file, three real SIGINTs 1 s apart (`STOP_MODE=false NSIG=3 GAP=1 WAIT=70 vprobe.py <br|dev> mid file`). Branch: rc 1 after 44.0 s, stderr exactly `s3: the event stream ended unexpectedly (ReadTimeout)\n`, stdout exactly `TP53 has three ClinVar records [1]. The first is pathogenic` (59 bytes, no references), stub log `create, sent_mid, stop, stop, stop`. Develop: rc 130 after the first SIGINT (2.0 s), signals 2 and 3 found no process, stdout with `Not verified · the run did not finish` and the references block.
- Why it matters: Ctrl-C is the one control a person trusts to always work. Here it does nothing for 44 s, then the tool calls its own exit an error and drops the source behind the `[1]`. A bound such as "a second press after a `finished` answer exits", or a short wait for the stream to end before giving up, would keep A-142-01's fix without this trap.
- NOT FIXED

### V-142-06: Regression of: A-142-04 fix (7cfd513c). The new `except (BrokenPipeError, ValueError)` also swallows a real write error on a live stdout and points stdout at the null device
- Severity: minor (needs a non-UTF-8 stdout to show; inside the fix round's code)
- What: `ValueError` covers `UnicodeEncodeError` as well as "I/O operation on closed file". On the Ctrl-C path, `src/system_03_search_agent/adapters/cli/main.py:1211` to `main.py:1218` catches it, calls `_silence_closed_stdout` (`main.py:1242`), which `dup2`s the null device over a stdout that is not closed at all, and exits 130 with nothing said. The unfinished notice and the references block are lost with no reason given, and anything still in Python's stdout buffer at that moment goes to the null device at shutdown.
- Reproduction: `PYTHONIOENCODING=ascii`, scenario `mid`, stdout to a regular file, one real SIGINT (`vprobe.py <br|dev> mid file`). `Renderer.finish` raises `UnicodeEncodeError` on the `·` in `Not verified · the run did not finish`. Branch: rc 130, file holds only `TP53 has three ClinVar records [1]. The first is pathogenic`, stderr only the stop line. Develop: rc 1, the same file contents, stderr ends `s3: unexpected error (UnicodeEncodeError)`. The uninterrupted path is untouched: `done_small` with no signal gives rc 0 and the same 278 bytes on both, because the helper is reached only from the interrupt branch.
- Why it matters: the person loses the sources under a `[1]` and is not told why. Catching `BrokenPipeError` alone, or checking that the error is about a closed or broken stdout before redirecting, would keep A-142-04's fix without hiding other faults.
- NOT FIXED

### V-142-07: Left-open items A-142-02, 03, 06, 07, 08, 09 are not worse than develop, except where V-142-03 to V-142-05 say so (evidence)
- Severity: unsure (evidence)
- What and reproduction, each a real SIGINT, branch then develop:
  - A-142-02: stop failing (`STOP_MODE=fail`) after `done`, slow pipe: both print `Task exception was never retrieved ... StopAsyncIteration` after their line, rc 130 on both. On the confirmed and `finished` paths the branch no longer prints it (V-142-01).
  - A-142-03: `--json`, `done_blocked`, 2000 citations, unread pipe: both rc 130, stdout exactly 65536 bytes cut mid-object, stderr `s3: interrupted\n`, no stop sent. Identical.
  - A-142-06: the adversary's own `stub.py` and `harness.py`, scenario `clarify`: both rc 130 with the numbered options and no pick hint; the branch's line now says the answer above is incomplete, develop's carries `error:`. Not worse.
  - A-142-07: scenario `nonfatal`: both keep `error [ncbi_efetch]: this query hit a temporary error before finishing...` above their own line, rc 130. In `--json` both show only their one line. Not worse.
  - A-142-08: worse in one way, filed as V-142-03 (no acknowledgement during the 15 s wait). Same 15 s wait on both.
  - A-142-09: `done_small`, SIGINT with no delay after `done`, eight runs each. Branch: rc 0 seven times, rc -2 once. Develop: rc 0 four times, rc -2 four times. stderr empty in all sixteen. Not worse.
- NOT FIXED (evidence)

### V-142-08: One branch run printed an "Exception ignored ... KeyboardInterrupt" traceback at shutdown after a clean exit 0
- Severity: unsure (seen once; the code involved is not in this diff, so likely pre-existing)
- What: a Ctrl-C landing while the interpreter is shutting down after a finished run was reported by asyncio's async-generator finalizer as a traceback.
- Reproduction: `DELAY=0 vprobe.py br done_small blockpipe`, one run in eleven on the branch: rc 0, stderr starts `Exception ignored in: <async_generator object AsyncResponseStream.__aiter__ at 0x...>` and ends `KeyboardInterrupt: `. Not seen in eleven develop runs, but the window is outside `_run_ask`'s Ctrl-C scope, which this diff does not move.
- Why it matters: a script that greps stderr sees a traceback on a successful run. Filed so it is not lost; not counted as worse than develop.
- NOT FIXED

### V-142-09: Regression of: A-142-04 fix (7cfd513c), test half. The closed-pipe test stays green with the null-device redirect disabled, and the real pipe then exits 120 with a traceback
- Severity: minor (a test gap on the fix round's own code; the shipped code works)
- What: `test_ctrl_c_into_a_closed_pipe_exits_130_without_an_error` uses an `io.StringIO` subclass, whose `fileno()` raises, so `_silence_closed_stdout` always takes its `except` and returns. The `os.dup2` line that actually prevents the shutdown flush error is never run by any test.
- Reproduction: scratch edit replacing `os.dup2(devnull, stdout.fileno())` in `main.py` `_silence_closed_stdout` with `pass`. CLI suite: `461 passed in 10.73s`. Real pipeline (`vpipe.py br mid tee`): cli rc 120, stderr `s3: the run was stopped at your request; the answer above is incomplete.\nException ignored in: <_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>\nBrokenPipeError: [Errno 32] Broken pipe\n`. Restored from a copy; `git diff HEAD` 0 lines.
- Why it matters: the A-142-04 behaviour a person sees can regress with the suite green. A subprocess test with a real `os.pipe()` whose read end is closed would pin it.
- NOT FIXED

### Erratum to V-142-03
- The `await asyncio.wait(...)` in `_handle_interrupt_during_stream` is at `main.py:1303`, not 1296.

### V-142-10: A-142-05 and J-142-05 closed (evidence)
- Severity: unsure (evidence)
- A-142-05: every single-press Ctrl-C line now says the answer is incomplete. Confirmed stop: `s3: the run was stopped at your request; the answer above is incomplete.`; failed or timed-out stop: `s3: you pressed Ctrl-C, but the server did not confirm the stop, so the run may still be going; the answer above is incomplete.` (real SIGINT, scenarios `mid`, `clarify`, `nonfatal`, `STOP_MODE=fail`, `STOP_SLEEP=60`). The exception is the second-press path, V-142-04.
- J-142-05: `test_a_dropped_connection_without_ctrl_c_still_prints_the_early_end_error` drives `async_main` with the real `Renderer`. Judge's break B (`exit_code = renderer.finish(interrupted=True)` on the normal path) now turns it red: `1 failed, 460 passed`.
- NOT FIXED (evidence)

## Runs

- CLI suite: `venv/bin/python -m pytest tests/system_03_search_agent/adapters/cli -q` printed `461 passed in 10.81s`.
- Gate 2: `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github` printed `Skipped 2 files`, exit 0.
- Gate 3: `venv/bin/ruff check .` printed `All checks passed!`, exit 0.
- CI on pull request #298 at 474d3e56: Accessibility, Frontend gates, Integration suite and Python gates all pass.
- Break it, one property each, restored from a copy, `git diff HEAD` 0 lines after each, `git status --short` only `?? frontend/node_modules`:

| Break | Change | Result |
|---|---|---|
| A, the brief's | `if not stopped: return "finished"` made `if False:` | `1 failed, 460 passed`, red: `test_ctrl_c_on_a_run_that_already_finished_shows_it_as_completed` |
| B, judge's J-142-05 | normal path `renderer.finish(interrupted=True)` | `1 failed, 460 passed`, red: `test_a_dropped_connection_without_ctrl_c_still_prints_the_early_end_error` |
| D | unconfirmed path writes `_STOP_LINE` | `1 failed, 460 passed`, red: `test_ctrl_c_when_the_stop_call_fails_does_not_claim_a_stop` |
| F | `os.dup2` in `_silence_closed_stdout` made `pass` | `461 passed`, green; real pipe then rc 120 with a traceback (V-142-09) |

## Exit codes, branch against develop, real SIGINT

| Path | Branch | Develop |
|---|---|---|
| Ctrl-C mid-stream, stop confirmed, human or `--json` | 130 | 130 |
| Ctrl-C while a finished run's references are written (`stopped: false`) | 0 | 130 |
| Ctrl-C, stop call fails (500) | 130 | 130 |
| Ctrl-C, stop call times out (15 s) | 130 after 15.0 s, silent until then | 130 after 15.1 s, acknowledged at once |
| Two Ctrl-C during a slow stop | 130 after 2.0 s | 130 after 2.0 s |
| Ctrl-C into `| tee` or `| head`, human or `--json` | 130 | 120 |
| Ctrl-C, `stopped: false`, stream stays open, three presses | 1 after 44.0 s | 130 after the first press |
| Ctrl-C, stdout cannot encode `·` | 130, no reason given | 1, `unexpected error (UnicodeEncodeError)` |
| `--json` Ctrl-C while the object is written | 130, truncated | 130, truncated |
| No Ctrl-C, clean `done` | 0 | 0 |

## Verdict

HOLD: not "nothing worse than develop". The card's main promises hold, but four paths are worse than develop, and all four sit inside the fix round 7cfd513c. That is Rule 4's stop condition.

- Inside this phase's fix, filed as "Regression of:":
  - V-142-05, major: after a `stopped: false` reply on a stream that does not end, Ctrl-C cannot exit for 44 s, and the run then ends as an error (`main.py:1420`).
  - V-142-03, minor: nothing is shown for up to 15 s after Ctrl-C (`main.py:1303`).
  - V-142-04, minor: a second press prints only "interrupted again" (`main.py:1312`).
  - V-142-06, minor: `except ValueError` hides a real write error (`main.py:1211` to `1218`).
  - V-142-09, minor: a test gap on the redirect.
- Verified with own probes, real SIGINT, branch and develop side by side:
  - A-142-01 and J-142-01 are closed (V-142-01).
  - A-142-04 is closed under a real process-group pipeline (V-142-02).
  - A-142-05 is closed except on the second press (V-142-10, V-142-04).
  - J-142-05 is closed, shown by break B.
  - The left-open A-142-02, 03, 06, 07 and 09 are not worse (V-142-07).
  - Every row of the exit code table above.
- Only read, not run:
  - `--json` on the `finished` path. It shares the loop the human probe exercised.
  - The real server's stream-close timing after `stopped: false` (`run_registry.py` docstrings), which decides how often V-142-05 is reachable.
- Not a finding: the adversary's `harness.py` pipeline_tee mode reads `t0` before setting it, so a new pipeline harness was used (`v142/launch.py`, `v142/vpipe.py`).
