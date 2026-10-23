# Card 142 adversary, one round

Branch fix/card142-ctrl-c-is-not-an-error, pull request #298. Findings appended as found, ids A-142-NN.

## Findings

### A-142-01: A run that already finished is told "the run was stopped at your request." and exits 130, under a full verified answer
- Severity: major (the new sentence at `src/system_03_search_agent/adapters/cli/main.py:1254` is inside this card's fix; the path itself is pre-existing)
- What: when the SIGINT lands while `renderer.handle(done)` is still writing (the verdict and references are synchronous writes inside the stream window, `main.py:1161`, `render.py:1060`), the next `asyncio.wait` sees both the interrupt and the generator's `StopAsyncIteration` ready and checks the interrupt first (`main.py` loop, `if pending_interrupt ... in done` precedes `if pending_next in done`). So a finished run takes the interrupt branch: stderr says the run was stopped, a `POST /stop` goes to a run that already ended, and the exit code is 130. Develop said "interrupted, stopping the run...", which described the key press; the branch states as a past fact that the run was stopped, which here is false.
- Reproduction: own stub server (Starlette SSE, scratchpad `a142/stub.py`, scenario `done_blocked`: one token, 600 citations, `done` with `trust_outcome=answer`), real CLI subprocess with stdout a pipe left unread so the references write blocks, real `SIGINT` 1 s after the stub sent `done`, then stdout drained. Branch: rc=130; stdout begins `BRCA1 is a gene [1].\n[answer]\nBased on 1 source cited\n\nReferences:\n[1] ...` and ends with `[600] ...` (complete, 128851 bytes); stderr `s3: the run was stopped at your request.\n` followed by a raw asyncio warning (A-142-02); stub log `create, sent_done, stop`. Develop source, same probe: rc=130, stderr `s3: interrupted, stopping the run...`.
- Why it matters: the realistic trigger is `s3 ask "..." | less` or any slow pipe, where the person presses Ctrl-C while a long references list is being written. They get a complete `[answer]` with its trust line, and the program says it was stopped and exits 130, so a script throws away a good answer, and a person may believe the answer above is partial. The tie should go to the event that completed the run, or the message should not claim a stop happened.
- NOT FIXED

### A-142-02: A Ctrl-C after `done` prints a raw "Task exception was never retrieved ... StopAsyncIteration" traceback on stderr
- Severity: minor (pre-existing, identical on develop; it defeats the card's "no error line" for scripts that grep stderr)
- What: in `_handle_interrupt_during_stream` (`main.py:1255`), `pending_next` is cancelled only `if not pending_next.done()`. When it is already done with `StopAsyncIteration`, its exception is never retrieved and asyncio's garbage-collection warning goes to stderr.
- Reproduction: the A-142-01 probe. stderr in full: `s3: the run was stopped at your request.\nTask exception was never retrieved\nfuture: <Task finished name='Task-605' coro=<<async_generator_asend without __name__>()> exception=StopAsyncIteration()>\nStopAsyncIteration\n`. Develop: the same warning after its own line.
- Why it matters: the card's promise is one plain stop line and nothing that reads as an error; a person sees a Python traceback fragment, and `grep -i exception` in a wrapper script fires.
- NOT FIXED

### A-142-03: `--json` with Ctrl-C while the JSON document is being written leaves a truncated, unparseable JSON object on stdout
- Severity: major (pre-existing, outside the stream window this diff touched; breaks the JsonRenderer's "never a partial one" promise exactly on Ctrl-C)
- What: `JsonRenderer` writes the whole object in `finish()` after the stream scope has exited (`main.py:1208`), so the gentle SIGINT handler is gone and a Ctrl-C raises `KeyboardInterrupt` mid-write. `main()` prints `s3: interrupted` (`main.py:1666`) and exits 130 with the object cut off.
- Reproduction: stub scenario `done_blocked`, `s3 ask q --session-id s1 --json`, stdout an unread pipe, real `SIGINT` 1 s after `done`. rc=130; stdout exactly 65536 bytes, starting `{\n  "run_id": "run-1", ... "complete": true,` and ending mid-object at `"source_url": "https://www.ncbi.nlm.nih.gov/gene/107...",\n      "layer": `; stderr `s3: interrupted\n`; no stop sent.
- Why it matters: a script reading `--json` gets an object that does not parse, and a different stderr wording than the card's line. The answer had in fact finished.
- NOT FIXED

### A-142-04: Ctrl-C on `s3 ask ... | tee answer.txt` prints "s3: unexpected error (BrokenPipeError)", a traceback line, and exits 120, not 130
- Severity: major (the card's acceptance, no error line and exit 130, fails for the most common way to keep an answer; the BrokenPipe path is pre-existing, but this card's `finish(interrupted=True)` call at `main.py:1205` is where it now raises)
- What: Ctrl-C reaches every process in the pipeline. The reader dies first, then the interrupt branch calls `renderer.finish(interrupted=True)`, which writes the unfinished notice and references to the closed pipe. The `BrokenPipeError` escapes `_run_ask` and is caught by `async_main`'s last-resort handler (`main.py:1519` onward), which prints `s3: unexpected error (BrokenPipeError)` and returns 1. Interpreter shutdown then fails to flush stdout and the process exits 120.
- Reproduction: stub scenario `mid` (one token `TP53 has three ClinVar records [1]. The first is pathogenic`, one citation, then the stream stays open). `s3 ask q --session-id s1` with stdout piped into `tee tee.txt`, a real `SIGINT` sent to tee and then to s3 (what a terminal does to a foreground pipeline). Branch: rc=120; stderr `s3: the run was stopped at your request.\ns3: unexpected error (BrokenPipeError)\nException ignored in: <_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>\nBrokenPipeError: [Errno 32] Broken pipe\n`; tee.txt is exactly `TP53 has three ClinVar records [1]. The first is pathogenic`. Develop: rc=120 and the same two error lines, after its own "error: the run ended before a final answer..." line.
- Why it matters: a person who saves the answer with tee and presses Ctrl-C sees the word "error" and a Python traceback fragment, and a script sees exit 120. The saved file holds a sentence cut mid-claim with a `[1]` marker, no source and no "did not finish" marker (see A-142-05).
- NOT FIXED

- Addendum to A-142-04, `--json`: the same pipeline with `--json` (`s3 ask q --session-id s1 --json | tee tee.txt`, SIGINT to both) gives rc=120, the same `s3: unexpected error (BrokenPipeError)` plus traceback lines on stderr, and an empty tee.txt (0 bytes).

### A-142-05: On Ctrl-C nothing on stderr says the answer above is incomplete or its sources may be partial any more
- Severity: minor (unsure; inside this card's fix, the `if not interrupted:` at `src/system_03_search_agent/adapters/cli/render.py:1226`)
- What: develop's stderr after Ctrl-C carried "any answer text above is incomplete and its citations may be partial". The branch drops that whole sentence along with the word "error". What is left is stderr `s3: the run was stopped at your request.` and stdout `Not verified · the run did not finish`. Neither says the text was cut part way, and neither warns that the sources listed may not cover the claims made.
- Reproduction: stub scenario `mid`, real SIGINT, stdout an unread pipe. stdout exactly `TP53 has three ClinVar records [1]. The first is pathogenic\nNot verified · the run did not finish\n\nReferences:\n[1] NCBIGene... - https://www.ncbi.nlm.nih.gov/gene/1...\n`; stderr exactly `s3: the run was stopped at your request.\n`; rc=130. The sentence ends mid-claim ("The first is pathogenic") with a References block under it that reads as complete. When stdout dies with the pipe (A-142-04), the saved file carries no marker at all.
- Why it matters: a confident wrong record is worse than a missing one. The fix should have dropped the word "error" and kept the incompleteness warning, for example "s3: the run was stopped at your request; the answer above is incomplete." The card asked to remove the error framing, not the honesty.
- NOT FIXED

### A-142-06: The human stop line gives no next step, while the `--json` message for the same stop does
- Severity: minor (inside this card's fix, `main.py:1254`)
- What: the human line is `s3: the run was stopped at your request.`. The JSON `error.message` for the same event, written at `main.py:1183`, is `s3: you stopped this search. Start a new search if you still need an answer.`. Two wordings for one event. Only the JSON one says what to do next, and neither says how to continue the same conversation.
- Reproduction: stub scenario `clarify`. Human mode stdout is `What would you like to know about GERD?\n  1. GERD genes\n  2. GERD trials\n\nNot verified · the run did not finish\n` and stderr `[P | think] n\ns3: the run was stopped at your request.\n`. The normal-path hint `s3: to ask one of these, run: s3 ask --session-id ...` (`main.py:1209-1219`) is skipped on the interrupt path, so the person gets numbered options and no way to pick one. Develop also skips the hint (pre-existing), but the new wording had the chance to say it.
- Why it matters: a refusal says what to type next, and a stop should too. Someone who stopped a question back has the options on screen and no command to choose one.
- NOT FIXED

### A-142-07: After Ctrl-C, a non-fatal tool error already in the stream leaves an "error [...]" line on stderr, so a script grepping stderr for "error" still fires
- Severity: unsure (pre-existing; the line comes from the server's real non-fatal error event, which may be correct to show)
- What: a non-fatal `transient` error renders as `error [source]: this query hit a temporary error before finishing. Run 's3 ask' again ...` even though the run kept going. Ctrl-C then adds the stop line under it.
- Reproduction: stub scenario `nonfatal` (token, citation, `error` with `fatal=false, error_class=transient, source=ncbi_efetch`, then the stream stays open), real SIGINT. rc=130. stderr: `error [ncbi_efetch]: this query hit a temporary error before finishing. Run 's3 ask' again to start a new attempt.\ns3: the run was stopped at your request.\n`. In `--json`, the interrupted record replaces the transient error, so the JSON carries no trace of it.
- Why it matters: the brief's script case. A wrapper that reads "error on stderr" as failure treats this stop as a failure, and the line says "before finishing" about a tool retry, which reads as the cause of the stop.
- NOT FIXED

- Addendum to A-142-01: `CliClient.stop` (`client.py:1077-1090`) returns the server's own `stopped` field, and its docstring says stopping an already-finished run is a no-op. `_handle_interrupt_during_stream` never reads that field, so it cannot tell "I stopped it" from "it had already finished". The stop line is written before the stop call is even sent.

### A-142-08: After one Ctrl-C with a slow server, "the run was stopped" is shown and then the CLI sits silent for 15 s, and the records that arrived appear only afterwards
- Severity: minor (sits next to J-142-01, but this is a different harm: time, and records held back. The ordering is pre-existing, the wording is this card's)
- What: the stop line is written first (`main.py:1254`). `await asyncio.wait({stop_task, second_interrupt})` then blocks for the full `_REST_CALL_TIMEOUT_S = 15.0` (`client.py:134`). The `renderer.finish(interrupted=True)` call, which prints the references and the "did not finish" notice, runs only after that wait (`main.py:1205`). A stop that times out is silently treated as done.
- Reproduction: stub with `STOP_SLEEP=60` on `POST /stop`, scenario `mid`, real SIGINT. From SIGINT to process exit took `EXIT_AFTER_SIGINT_S 15.0`. rc=130. stderr was only `s3: the run was stopped at your request.\n`, with nothing about the stop timing out.
- Why it matters: speed is a feature. A person who pressed Ctrl-C is told it is done, then waits 15 s with no sign of life before getting the records the card says are kept. Many will press Ctrl-C again, and then get "interrupted again, exiting immediately".
- NOT FIXED

- Second addendum to A-142-01: the server already answers this question. `POST /v1/query/{run_id}/stop` (`src/system_03_search_agent/adapters/web_sse/app.py:1943-1962`, card 59 A-59-03) returns `stopped: false` for a run that had finished, and says in its comment that "the command line prints [that] as 'run was already finished'". `s3 stop` does this at `main.py:957`: `"run stopped\n" if stopped else "run was already finished\n"`. The Ctrl-C path writes its line before the answer comes back and never reads it, so the same CLI gives two different accounts of the same server reply.

- Addendum to A-142-05: the 2026-08-16 decision `DECISIONS.md:364` (build phase 4.2, running `finish()` on the Ctrl-C path) says a partial answer kept after Ctrl-C "still needs its sources and a statement that it was cut short". Stdout's `Not verified · the run did not finish` says the run did not finish. It does not say the text above was cut short. The branch removed the only sentence that did.
- Addendum to A-142-06: `testing/Retest_product_owner.md:60` (row 40, card 61) promises the owner that "Ctrl-C says you stopped the search", which is the JSON wording. The human line now uses a third wording, so it no longer matches what the owner retests against.

### A-142-09: On a run that has finished, the exit status after Ctrl-C depends on timing: 0, death by signal with nothing on stderr, or 130 with "stopped"
- Severity: unsure (pre-existing; the answer on stdout was complete in every case)
- What: the same complete run, with Ctrl-C pressed at slightly different moments, ends three different ways. While `done` is still being rendered inside the stream window, it takes the interrupt branch (A-142-01). After the scope's SIGINT handler is removed, during interpreter shutdown, the process dies from SIGINT with no message. If it arrives after the process exits, the run is clean.
- Reproduction: stub scenario `done_small` (one token, one citation, `done` answer), real SIGINT with `DELAY=0` right after the stub sent `done`, three runs. rc=0 once, then rc=-2 twice (killed by SIGINT, the shell shows 130). stderr was empty in all three, stdout the full `[answer]` and references each time. With the slow-pipe variant, rc=130 and `s3: the run was stopped at your request.` (A-142-01).
- Why it matters: a script that reads the exit code cannot tell "the person stopped it" from "it finished and the person pressed Ctrl-C a moment late". Only the rc=130-with-stop-line variant also claims a stop.
- NOT FIXED

## Method

- Own stub server: Starlette SSE serving `POST /v1/query`, `GET /v1/query/{id}/events` and `POST /v1/query/{id}/stop`, with each call logged. Scenarios: `mid`, `mid_nocite`, `listing`, `clarify`, `nonfatal`, `empty`, `done_small`, `done_blocked`. The CLI ran as a real subprocess (`main.main`) with a real credentials file in the scratchpad, a real `SIGINT` sent with `os.kill`, and stdout as an unread pipe, a pipe into `tee`, or `--json`. The same probes were run against `git archive origin/develop src` for comparison. No live model calls. No scratch edits to the worktree: `git diff HEAD` is empty, and the only untracked path is `frontend/node_modules`.

## Verdict

FAIL against the card's acceptance as the person meets it: "after Ctrl-C the command line prints the stop line and no error line, keeps records that arrived, exits 130".

- Verified with own probes:
  - The plain case passes: real SIGINT mid-stream, stdout to a pipe, gives one stop line, no error line, records kept, rc 130. This held for the `mid`, `mid_nocite`, `listing`, `clarify`, `empty` and `--json` cases.
  - It fails for a pipeline into `tee`, the common way to keep an answer: "unexpected error (BrokenPipeError)", rc 120, and a file holding a cut sentence with no marker (A-142-04).
  - A finished run is told it "was stopped" and exits 130 (A-142-01).
  - A Python traceback fragment appears after `done` (A-142-02).
  - `--json` can be left truncated by a Ctrl-C (A-142-03).
  - The incompleteness warning is gone (A-142-05).
  - The 15 s silent wait after "was stopped" (A-142-08).
- Only read, not run: the server's `stopped: false` semantics (A-142-01's second addendum) and the 2026-08-16 decision text.
- Inside this card's fix: A-142-01 (the new past-tense sentence over a finished run), A-142-05 (the `if not interrupted:` that removed the cut-short statement), A-142-06 (the new wording) and A-142-08 (the wording before the wait). A-142-04 now raises from this card's `finish(interrupted=True)` call, though the BrokenPipe path is pre-existing. This fires the review loop's stop condition.
