# Card 142 adversary, round 1 (draft pull request #315, b27c1b51)

Findings are appended as they are established. Ids A-142B-NN.

## Findings

Method: real `main()` as the `s3` console script runs it, child in its own session, real signals by `os.killpg`, against an extended copy of the judge's stub (`scratchpad/a142/stub.py`, new STOP_MODEs strfalse, nullstopped, list, nullbody, html, redirect, unauth, hang, confirm_apply; new SCENARIO held_fatal) driven by `scratchpad/a142/probe.py`. Develop is the judge's archive of b5690f98 (`scratchpad/j142/dev`). Scratchpad root: <session scratchpad, not published>/

### A-142B-01: A run that really failed while the stop call was pending is reported as "may still be going", and its real error is thrown away
- Severity: minor (inside this build's new held-events branch; a sibling of J-142B-02, which is about a held `done`; this one hides a real fatal error)
- What a person sees: they press Ctrl-C, the run fails on the server in the same second (here a fatal `unexpected` error, "the model provider failed"), the stop call is slow, and the command line says "the server did not confirm the stop, so the run may still be going". The failure is never shown. The run is over, and the program held proof of it.
- Evidence: `PORT=18771 SCENARIO=held_fatal STOP_MODE=confirm STOP_SLEEP=30 PRESSES=0.3 python probe.py <branch> hf_slow_b`: rc 130 at 3.48 s, stub log `create, sent, stop, sent_fatal`, stderr `s3: interrupted, stopping the run...` / `s3: the server did not confirm the stop, so the run may still be going; the answer above is incomplete.`; stdout ends `Not verified · the run did not finish` and the references. Same with `STOP_MODE=fail STOP_SLEEP=1` (stop answers 500 after 1 s, the error arrives at 0.3 s): the same "may still be going" line.
- Develop, same probe (`hf_slow_d`): also hides the error, with `error: the run ended before a final answer was received; ...`. Not worse than develop in hiding the error; the new sentence is the untrue part ("may still be going" about a run whose fatal error is in hand).
- NOT FIXED

### A-142B-02: A stop reply of `{"stopped": "false"}` is read as a confirmed stop: "the run was stopped at your request" while the run keeps going
- Severity: minor, unsure on reach (the real server sends a JSON boolean; a proxy, gateway or a future server that serializes it as a string would trigger it). New in this build: develop never read the reply's value.
- What: `CliClient.stop` returns `bool(body["stopped"])` (`client.py:1090`), and `bool("false")` is True. The branch now turns that value into the past-tense claim `_STOPPED_LINE`, the one line the builder says is used "only after the server says `stopped: true`".
- What a person sees: "s3: the run was stopped at your request" for a run the server did not stop. In `--json`, `error.message` "s3: you stopped this search."
- Evidence: `PORT=18781 SCENARIO=mid STOP_MODE=strfalse PRESSES=0.3 python probe.py <branch> m_strfalse`: rc 130 at 0.55 s, stderr `s3: interrupted, stopping the run...` / `s3: the run was stopped at your request; the answer above is incomplete.`; the stub never cancelled the run (stub log `create, sent, stop`, no cancel event sent, its stream still open).
- NOT FIXED

### A-142B-03: A stop reply with `stopped` null (or 0, or "") says "the run had already finished, so there was nothing to stop" about a run that is still running, and then the stop is never retried
- Severity: minor, unsure on reach (same malformed-reply class as A-142B-02). New in this build.
- What a person sees: "s3: the run had already finished, so there was nothing to stop." then, 3 s later, "s3: the rest of the answer did not arrive in time; the answer above is incomplete." The run was never stopped and never finished; the person was told there was nothing to stop, so they have no reason to run `s3 stop`.
- Evidence: `PORT=18782 SCENARIO=mid STOP_MODE=nullstopped PRESSES=0.3 python probe.py <branch> m_nullstopped`: rc 130 at 3.47 s, stub log `create, sent, stop` (no cancel), stderr the three lines above.
- Why it matters: both A-142B-02 and A-142B-03 are the lying line in its purest form: `bool()` of an unvalidated field picks between "stopped", "already finished" and "not confirmed". Only a JSON `true` or `false` should select the first two; anything else is "not confirmed".
- NOT FIXED

### A-142B-04: When the stop call is stuck resolving the server's name, the prompt does not come back for the full lookup time; the 3 s bound and the second-press hard exit both fail, and a third press prints a threading traceback
- Severity: major (the stuck terminal the owner's redesign exists to prevent; the builder's account says "a slow or unreachable server cannot hold the person at the terminal"). Not worse than develop, which is stuck for the same time.
- What: the stop call opens a new connection (the stream holds the first), so it calls `getaddrinfo`, which asyncio runs in its default thread pool. At the bound the code prints the unconfirmed line and returns, but `asyncio.run` then joins the default executor (`shutdown_default_executor`, no timeout on Python 3.11.6), and interpreter exit joins it again (`concurrent.futures.thread._python_exit`). Neither can be interrupted while the lookup thread runs. A slow resolver is exactly the flaky network on which a person presses Ctrl-C because the answer stalled.
- What a person sees: "the server did not confirm the stop, so the run may still be going..." at 3 s, then no prompt. Ctrl-C again prints "s3: interrupted" and still no prompt. Ctrl-C a third time prints an `Exception ignored in: <module 'threading'>` traceback ending `KeyboardInterrupt`.
- Evidence: name resolution made slow in the child only for the server's host after its first lookup (`scratchpad/a142/pre.py`: `socket.getaddrinfo` for `s3stub.test` sleeps 20 s from the second call; credentials point at `http://s3stub.test:<port>`), stub `SCENARIO=mid STOP_MODE=confirm`.
  - Branch, one press at 0.3 s (`dns0_b`): unconfirmed line on stderr by 3.4 s, rc 130 at 20.42 s.
  - Branch, presses 0.3 and 3.6 s (`dns1_b`): stderr 0.1 s after press 2 `...stopping the run...\n...did not confirm the stop...\ns3: interrupted\n`; rc 130 at 20.36 s.
  - Branch, presses 0.3, 4.0, 5.0 s (`dns_b`): after press 3 the stderr adds `Exception ignored in: <module 'threading' from '.../threading.py'>` / `Traceback ... concurrent/futures/thread.py, line 31, in _python_exit ... t.join() ... KeyboardInterrupt:`; rc 130 at 5.11 s.
  - Develop, one press (`dns0_d`): rc 130 at 20.36 s; three presses (`dns2_d`): rc 130 at 20.40 s, its second press says "exiting immediately" and does not.
  - Stub log in every run: `dns1, create, sent, dns2` (the stop request never reached the server, so "may still be going" is true here).
- NOT FIXED

### A-142B-05: J-142B-14 confirmed: a code fault raising TypeError inside the stop call is shown as "the server did not confirm the stop, so the run may still be going" after the server did stop the run, with no trace of the cause
- Severity: minor (latent; today's `client.stop` has no such fault). Inside this build's new `_STOP_REPLY_FAILURES` tuple (`main.py:1341`).
- What: `TypeError` is caught to cover a 200 reply whose body is not an object. Two real replies reach it and are reported correctly as unconfirmed: a body of `[]` (`m_list`, rc 130 at 0.41 s) and a body of `null` (`m_nullbody`, rc 130 at 0.42 s). But the same clause also swallows any programming fault that raises TypeError after the server has acted.
- Evidence: temporary edit (restored with `git checkout --`, `git status --short` afterwards only `?? frontend/node_modules` and this file) of `client.py:1090` to `return len(body["stopped"]) > 0`, a plausible refactor slip. Stub `STOP_MODE=confirm_apply` (the server cancels the run, then answers `{"stopped": true}`), one SIGINT at 0.3 s (`te_b`): rc 130 at 0.41 s, stub log `create, sent, stop, server_cancelled`, stderr `s3: interrupted, stopping the run...` / `s3: the server did not confirm the stop, so the run may still be going; the answer above is incomplete.` No class name, no trace, nothing in any log.
- What a person sees if a fault lands there: every Ctrl-C claims the server may still be running the search, when it stopped it. The same holds for `KeyError` from a code fault. A `TypeError`/`KeyError` raised before the request is sent would also say "the server did not confirm", when the server was never asked.
- NOT FIXED

### A-142B-06: After Ctrl-C, a stream that closes with no final event while the stop is pending prints the card's own "error:" line under "the run had already finished", and exits 1 instead of 130
- Severity: minor (inside this build's "already finished" replay path, point 5; reach needs the stream to close with no `done` or fatal error, which the real registry never does itself but a proxy idle timeout, a load balancer or a server restart does)
- What: the held read ends in `StopAsyncIteration`, the stop answers `stopped: false`, the replay's `take()` returns None, and `_run_ask` then calls `renderer.finish()` without `stopped_by_person`, so the run is treated as a normal run that broke off.
- What a person sees, after their own Ctrl-C: "s3: the run had already finished, so there was nothing to stop." directly followed by "error: the run ended before a final answer was received; any answer text above is incomplete..." Two lines that contradict each other, the second being the exact line card 142 removes.
- Evidence: new stub scenario `close_after_stop` (token and citation, then the stream closes 0.1 s after the stop request arrives, no terminal event), `STOP_MODE=finished STOP_SLEEP=0.3`, one SIGINT at 0.3 s.
  - Branch (`cas_b`): rc 1 at 0.67 s, stderr `s3: interrupted, stopping the run...` / `s3: the run had already finished, so there was nothing to stop.` / `error: the run ended before a final answer was received; ...`.
  - Branch `--json` (`casj_b`): stdout parses; `"complete": false`, `error.error_class` `stream_incomplete`, message "the event stream ended with no final answer or error"; nothing in the object says the person stopped it.
  - Develop (`cas_d`): rc 130, `s3: interrupted, stopping the run...` / `error: the run ended before ...`.
- Worse than develop in one respect: exit 1 rather than 130, so a script that branches on 130 to mean "the person stopped it" no longer sees the stop. The "error:" line is on both.
- NOT FIXED

### A-142B-07: On a terminal, the stop lines are glued into the middle of the answer's last word, and when the run had already finished the answer then resumes below them
- Severity: minor (display). The first line glued mid-word is pre-existing (develop writes the same line at the same moment); the answer resuming under "nothing to stop" is new in this build's point 5.
- What: `say()` writes to stderr without first ending the line stdout is in the middle of. A terminal shows both streams in one place.
- What a person sees (stdout and stderr to the same file, as a terminal shows them):
  ```
  TP53 has three ClinVar records [1]. The first is pathogenics3: interrupted, stopping the run...
  s3: the run had already finished, so there was nothing to stop.
   rest of the answer.
  [answer]
  ```
  "pathogenic" becomes "pathogenics3:", and the end of the answer sits under two status lines, so it reads as a separate fragment.
- Evidence: probe mode `OUT=merged` (one file for both streams), stub `SCENARIO=done_after_stop STOP_MODE=finished`, one SIGINT at 0.3 s (`merged_b`), rc 0.
- NOT FIXED

### A-142B-08: Evidence: three or more quick presses under `--json` leave stdout empty in 3 of 10 runs; A-142-03 still reproduces, same as develop
- Severity: minor, pre-existing (A-142-03, listed by the builder under "Left as they are"); not worse than develop. Filed so the count is on record for this build.
- What a person or script sees: stderr `s3: interrupted, stopping the run...` / `...interrupted again, exiting immediately; the stop was not confirmed...` / `s3: interrupted`, and 0 bytes on stdout, so `--json`'s "a script always has something to parse" does not hold. The third press lands in `JsonRenderer.finish`, outside the signal scope.
- Evidence: `scratchpad/a142/burst.py` (five SIGINTs to the process group, a fixed gap apart, starting 0.3 s after the stub's marker), stub `SCENARIO=mid NCIT=300 STOP_MODE=confirm STOP_SLEEP=30`, `--json`. Branch: gaps 2 ms (2 of 2 runs), 5 ms (1 of 2) give 0 bytes on stdout; gaps 10, 15 and 30 ms (6 of 6) give a JSON object that parses with the "did not confirm" message. Develop, gaps 2 ms (2 of 2) give 0 bytes, 5 ms (1 of 1) parses. Exit status in all: killed by SIGINT (subprocess -2, which a shell reports as 130, the same number a script already branches on).
- NOT FIXED

### A-142B-09: Evidence: stop replies that are handled honestly, and SIGTERM and SIGHUP
- Severity: evidence, with one pre-existing gap noted
- One SIGINT at 0.3 s, stub `SCENARIO=mid` (stream left open), branch. Each: rc 130, stderr exactly `s3: interrupted, stopping the run...` / `s3: the server did not confirm the stop, so the run may still be going; the answer above is incomplete.`, no traceback, stdout keeps the references:
  - body `[]` (`m_list`) 0.41 s; body `null` (`m_nullbody`) 0.42 s; 200 `text/html` proxy page (`m_html`) 0.42 s; 307 redirect (`m_redirect`) 0.42 s; 401 (`m_unauth`) 0.42 s; a server that accepts the stop and never answers (`m_hang`) 3.39 s.
- Pre-existing gap (develop the same): a 401 on the stop is never retried after a token refresh, so a person whose access token expired during a long run cannot stop it from Ctrl-C; the line says so honestly ("may still be going").
- SIGTERM and SIGHUP (the terminal closing) during the stream, branch and develop alike: the process dies at once (subprocess rc -15 and -1), nothing on stderr, and no stop is sent (stub log `create, sent`); the run keeps going on the server until the abandonment timer. Not worse than develop; the card did not promise either.
- Not probed: `s3 login`, `s3 stop` and a token refresh interrupted by Ctrl-C (all outside the stream window, code unchanged by this build: `git diff HEAD~1 --stat` touches only `main.py`'s stream loop and `_run_ask`, and `render.py`'s `finish`); a real TLS handshake (no certificate in the stub; the hang case covers a stop that never answers).

### A-142B-10: A second press in the same instant as the server's answer says "the stop was not confirmed" with the confirmation in hand
- Severity: minor (a narrow tie, inside this build's new loop; the builder made the stream win a tie with a press, but not the stop's answer)
- What: in `_consume_stream_with_interrupt` the interrupt branch runs before the `stop_task` branch in the same wake-up. When both are done, the second press exits with `_SECOND_PRESS_UNCONFIRMED_LINE` and outcome "unconfirmed" without reading the finished `stop_task`, whose result says the run was stopped (or had finished).
- What a person sees: "s3: interrupted again, exiting immediately; the stop was not confirmed, and the answer above is incomplete." The server did confirm it. `--json` says "the server did not confirm the stop, so the run may still be going".
- Evidence (scripted, not a real signal: the real `_consume_stream_with_interrupt` in a real event loop with a fake client whose `stop` returns when an asyncio.Event is set; `scratchpad/a142/race.py`): first press at 0.05 s, then in one callback the stop's answer is released and the second press is queued. Output: `stopped=True: rc 130, outcome unconfirmed` with stderr `s3: interrupted, stopping the run...` / `s3: interrupted again, exiting immediately; the stop was not confirmed, and the answer above is incomplete.`; the same for `stopped=False`.
- NOT FIXED

### A-142B-11: A run that failed is announced as "had already finished", directly above "this query failed unexpectedly before finishing"
- Severity: minor (wording of this build's new `_ALREADY_FINISHED_LINE`; the real server answers `stopped: false` for any run whose task is done, including a failed one, `core/run_registry.py` `_cancel_unless_finished`)
- What a person sees after Ctrl-C:
  ```
  s3: interrupted, stopping the run...
  s3: the run had already finished, so there was nothing to stop.
  error [agent]: this query failed unexpectedly before finishing.
  ```
  "finished" and "before finishing" about the same run, two lines apart. The error is shown, which is right; the new line's word is what is wrong ("had already ended" would be true of both).
- Evidence: stub `SCENARIO=held_fatal STOP_MODE=finished STOP_SLEEP=0.5` (a fatal `unexpected` error 0.3 s after the stop request, the stop answers false at 0.5 s), one SIGINT at 0.3 s (`hff_b`): rc 1 at 0.85 s, stderr as above. `--json` (`hffj_b`): rc 1, the object's `error` is the run's own `unexpected` error.
- NOT FIXED

### A-142B-12: A script cannot tell a confirmed stop from an unconfirmed one except by parsing English: exit code, `error_class` and `fatal` are identical for all three endings
- Severity: minor, unsure (a design point, not a wrong line; filed because the brief names exit codes and `--json` consumers)
- What: confirmed, unconfirmed and cut-off all exit 130 and all carry `error.error_class` "interrupted", `fatal` true, `complete` false. The only difference is `error.message`, prose meant for a person. A script that must decide "is the run still running on the server (so I should call `s3 stop`)?" has to match message text, which this card's own history shows changes.
- Evidence, `--json`, one SIGINT at 0.3 s, stub `SCENARIO=mid`: `STOP_MODE=confirm` (`jx_confirm`) rc 130, `interrupted`/true/false, "s3: you stopped this search. ..."; `STOP_MODE=fail` (`jx_fail`) rc 130, same three fields, "...but the server did not confirm the stop, so the run may still be going..."; `STOP_MODE=finished` (`jx_finished`) rc 130 at 3.39 s, same three fields, "...after the run had finished, but the rest of its answer did not arrive...".
- NOT FIXED

### A-142B-13: Two presses 40 ms apart with a fast confirmed stop and a plain file for stdout printed "Task exception was never retrieved" and a KeyboardInterrupt traceback (1 run in 41)
- Severity: unsure (rare; a different trace from J-142B-05, with no slow pipe involved; it contradicts the builder's "Every done task is read before it is dropped, so asyncio prints no 'Task exception was never retrieved'")
- What a person sees, after a fast double Ctrl-C:
  ```
  s3: interrupted, stopping the run...
  s3: the run was stopped at your request; the answer above is incomplete.
  s3: interrupted
  Task exception was never retrieved
  future: <Task finished name='Task-204' coro=<<async_generator_asend without __name__>()> exception=KeyboardInterrupt()>
  Traceback (most recent call last):
    File "<branch>/src/system_03_search_agent/adapters/cli/main.py", line 1838, in main
      return asyncio.run(_run())
    ...
    File "<branch>/src/system_03_search_agent/adapters/cli/client.py", line 898, in stream_events
      async for raw_bytes in response.aiter_bytes():
    ...
    File ".../httpcore/_async/http11.py", line 347, in aclose
      async with Trace("response_closed", logger, self._request):
  KeyboardInterrupt
  ```
- Likely mechanism (read, not proven): the `finally` of `_consume_stream_with_interrupt` cancels the in-flight stream read (`pending_next.cancel()`) but does not wait for it, so the cancellation runs on a later loop turn, after the signal scope has been removed; the second press then raises KeyboardInterrupt inside that task, which nobody retrieves.
- Evidence: `scratchpad/a142/burst.py` with two SIGINTs a fixed gap apart, stub `SCENARIO=mid NCIT=200 STOP_MODE=confirm STOP_SLEEP=0.03`, stdout and stderr plain files. Branch: 1 hit in 41 runs over gaps 20 to 150 ms (the hit: `dbl_40`, gap 40 ms, rc 130 at 0.09 s); 0 in a further 15-run sweep at 36 to 44 ms. Develop: 0 in 25 runs over the same gaps. Not shown to be worse than develop (develop also cancels the read without waiting); the sample cannot separate the two.
- NOT FIXED

## Verdict

FAIL against the owner's clause 2 and 3 on one reachable path (A-142B-04, not worse than develop), with no new blocking defect beyond the judge's J-142B-05. The build is better than develop on the card's own complaint: no line calls a confirmed or unconfirmed stop an error, on every path probed except A-142B-06.

- Inside this build's own new code: A-142B-01, 02, 03, 05, 06, 07 (second half), 10, 11. Of these, worse than develop: 02 and 03 (new lying lines from `bool()` of an unvalidated reply), 06 (exit 1 instead of 130), 10 and 11 (new untrue sentences in narrow cases).
- Verified by my own real-signal probes: A-142B-01, 02, 03, 04, 06, 07, 08, 09, 11, 12, 13 (13 is one hit in 41 runs). Verified by a temporary code edit plus a real signal: A-142B-05. Verified by driving the real loop with a scripted fake client, not a real signal: A-142B-10. Only read: A-142B-13's mechanism.
- The CLI suite at b27c1b51: `473 passed in 17.29s`.
- `git status --short` at the end: `?? frontend/node_modules` and `?? testing/Developer/reports/2026-10-29_card142/adversary.md` only.
