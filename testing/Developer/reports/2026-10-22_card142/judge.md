# Card 142 judge, one round

Branch fix/card142-ctrl-c-is-not-an-error at 627ad88c, worktree card142. Read and run only.

## Findings

### J-142-01: The new stop line says the run "was stopped" before the stop call has answered, and still says it when the stop failed
- Severity: minor (sits inside this card's fix, the reworded line at `src/system_03_search_agent/adapters/cli/main.py:1254`)
- What: `_handle_interrupt_during_stream` writes "s3: the run was stopped at your request." first, then sends `client.stop(run_id)` best-effort and never reads its result. A stop that raises, returns False, or is abandoned by a second Ctrl-C still leaves the past-tense claim on screen. Develop's "s3: interrupted, stopping the run..." made no claim of completion. The server still ends the run itself after 30 seconds with no subscriber, so the practical harm is small.
- Reproduction: own probe (scratchpad probe142.py, real `main.async_main` and real `Renderer`, fake `CliClient`) on the branch. `stop()` raising `httpx.ConnectError`: rc=130, stderr exactly `s3: the run was stopped at your request.`. `stop()` returning False: the same. A second Ctrl-C while `stop()` sleeps: `s3: the run was stopped at your request.` then `s3: interrupted again, exiting immediately`.
- Why it matters: someone who pressed Ctrl-C because a run was costly or wrong is told it stopped on the server when it may not have. Honesty beats polish. A wording such as "stopping the run you asked to stop" would not overclaim.
- NOT FIXED

### J-142-02: Non-interrupt paths are byte-identical to develop (evidence, not a defect)
- Severity: unsure (filed as evidence)
- What: `interrupted=True` is passed only on the `outcome == EXIT_INTERRUPTED` branch (`main.py:1205`). `EXIT_INTERRUPTED` comes only from `_handle_interrupt_during_stream` (`main.py:1277`, `main.py:1281`). That function is reached only when `interrupt_signals.get()` finishes (`main.py:1356`), and that queue is fed only by the SIGINT handler (`main.py:1628`). A server-side stop, a dropped connection or a timeout cannot set it.
- Reproduction: the same probe run against the branch and against `git archive origin/develop src`. On both: a server-side `cancelled` error event gives rc=1 and `error [run]: this query was stopped before it finished.`. A clean EOF with no terminal event gives rc=1 and `error: the run ended before a final answer was received; ...`. A truncated stream gives rc=1 with both the truncation line and the error line. `httpx.ReadTimeout` gives rc=1 and `s3: the event stream ended unexpectedly (ReadTimeout)`. A JSON clean EOF gives `error_class` `stream_incomplete`. In every case `stop_calls=[]`. For Ctrl-C itself, develop printed `error: the run ended before a final answer was received; ...` and the branch prints no error line. rc=130 and `stop_calls=['run-1']` on both.
- Why it matters: the hidden-real-failure risk named in the brief did not happen in any path probed.
- NOT FIXED

### J-142-03: A mid-stream transport error drops the references block for citations that already arrived (pre-existing, not in this diff)
- Severity: minor (pre-existing on develop, identical there, so not worse than develop)
- What: on `outcome == 1` in human mode, `_run_ask` returns at `main.py:1207` (`return outcome`) without calling `renderer.finish()`. A citation delivered before a `ReadTimeout` or `RemoteProtocolError` never gets its references block, and the unfinished notice is missing too.
- Reproduction: probe, stream yields a token with marker 1 and citation 1, then raises `httpx.ReadTimeout`. stdout is exactly `Partial text [1].`, with no `References:` and no "Not verified · the run did not finish". stderr is `s3: the event stream ended unexpectedly (ReadTimeout)`. Develop gives the same output.
- Why it matters: a `[1]` marker with no source behind it, which breaks the citation rule. This is outside card 142's acceptance, but it is the neighbouring path to "records that arrived are kept".
- NOT FIXED

### J-142-04: Ctrl-C outside the stream window prints a different line and sends no server stop (pre-existing, untouched by this diff)
- Severity: minor (unsure whether it is in card scope; develop behaves the same, so it is not worse)
- What: the handler that sends the stop is installed only around the stream (`main.py:1161`, `main.py:1628`). A Ctrl-C during `create_run`, during the sign-in renewal inside it, or while the references block prints after the stream raises `KeyboardInterrupt`. `main()` catches it at `main.py:1659` and writes `s3: interrupted` with rc 130. No `stop` is sent. A create that the server had already accepted then runs until its 30-second no-subscriber cancel. One more pre-existing case: a Ctrl-C inside `credentials.store` during renewal (`credentials.py:785`) turns into `SessionLostError` and is reported as an error. That is arguably right, because the token really was rotated.
- Reproduction: own real-signal probe. A subprocess runs `main.main(["ask","hi","--session-id","s1"])` with stdout and stderr piped and gets a real `SIGINT`. During the stream: rc=130, stderr `s3: the run was stopped at your request.\nSTOP-SENT\n`, stdout `Partial text. \nNot verified · the run did not finish\n`. During create: rc=130, stderr exactly `s3: interrupted\n`, with no STOP-SENT. During the stream with `--json` and piped output: rc=130, one JSON document on stdout, and the same stop line plus STOP-SENT on stderr.
- Why it matters: the card's "the person sees the stop line" holds only for the stream window. The person sees no error line in any window. This finding is about consistent wording only, so the acceptance is not broken.
- NOT FIXED

### J-142-05: Break it, the brief's mutation goes red, but a main-level mutation that hides every dropped connection's error stays green
- Severity: major (a missing guard on the control this card adds, so it sits inside this fix's own wiring)
- What: the "unasked early end still reports" property is guarded only at the renderer level. No test drives `main._run_ask` through an unasked early end and asserts the error line. If `main.py:1208`, the normal-path `exit_code = renderer.finish()`, ever passes `interrupted=True`, which is the one-token wiring mistake this card makes possible, every dropped connection loses its error line and the whole suite still passes.
- Reproduction:
  - Break A, the brief's mutation: a scratch line `interrupted = True` before `if not interrupted:` in `render.py` `Renderer.finish`. Result: `2 failed, 455 passed`, red in `test_render.py::TestInterruptedRunFinish::test_finish_prints_a_truncation_notice_and_the_references_delivered_so_far` and `test_s3_as_printed.py::TestARunThatDidNotFinishGetsNoVerdict::test_a_cut_off_answer_prints_no_tag_and_no_caution`. Restored, and `git diff HEAD` is empty.
  - Break B: `main.py:1208` changed to `exit_code = renderer.finish(interrupted=True)`. Result: `457 passed in 17.06s`, still green. With break B the own probe's dropped-connection case (clean EOF, no terminal event) printed rc=1 and an empty stderr, where unbroken it prints `error: the run ended before a final answer was received; ...`. Restored, and `git diff HEAD` is empty.
- Why it matters: the brief named this exact risk, a real failure hidden as a stop and therefore worse than develop. The shipped code does not hide failures today (J-142-02), but nothing stops a later edit from doing it. One test in `TestAskCommand` would close the gap: the stream yields a token then ends with no terminal event and no Ctrl-C, through the real `Renderer`, and asserts that "ended before a final answer" is present and rc is 1.
- NOT FIXED

## Runs and other mutations

- CLI suite: `venv/bin/python -m pytest tests/system_03_search_agent/adapters/cli -q` printed `457 passed in 20.64s`.
- Gate 2: `venv/bin/isort --check-only --diff src tests services tracker alembic .claude .github` printed `Skipped 2 files`, exit 0.
- Gate 3: `venv/bin/ruff check .` printed `All checks passed!`, exit 0.
- Break C, the card's own new test is not vacuous: change `renderer.finish(interrupted=True)` at `main.py:1205` back to `renderer.finish()`. Result: `2 failed, 455 passed`, both parametrizations of `test_ctrl_c_says_stopped_at_your_request_and_prints_no_error` red. Restored, and `git diff HEAD` is empty.
- Break D, the server stop is still sent and guarded: replace `client.stop(run_id)` with a no-op in `_handle_interrupt_during_stream`. Result: `1 failed, 456 passed`, with `test_ctrl_c_sends_stop_before_returning_a_nonzero_exit` red. Restored, and `git diff HEAD` is empty. The own probes also show `stop_calls=['run-1']` on every Ctrl-C path, and STOP-SENT under a real SIGINT.
- After every mutation, `git status --short` showed only `?? frontend/node_modules`.

## Verdict

PASS on card 142's acceptance, with one major test gap (J-142-05).

- Verified with own probes:
  - After Ctrl-C the person sees the stop line and no error line, in human mode and in `--json`, and with a real SIGINT and piped output.
  - Records that arrived before the stop are kept: the answer text and the references block, or the JSON citations.
  - The exit code is 130.
  - The server stop is still sent.
  - A second Ctrl-C still exits at once.
  - A server-side stop, a dropped connection, a truncated stream and a read timeout report exactly as on develop. The branch and develop were probed side by side.
- Only read, not run against a live server: the `credentials.store` interrupt path inside sign-in renewal (J-142-04). Its handler is unchanged by this diff.
- Worse than develop: nothing observed. J-142-01 is a small honesty regression in the reworded line itself. The new line claims a completed stop that develop's line did not claim.
- J-142-01 and J-142-05 sit inside this card's fix.
