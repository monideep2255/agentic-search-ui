# Build phase 4.2 adversary report, round 1

Dispatched 2026-08-16 against the merged branch, one fresh-context reviewer at Depth tier, high effort, unscripted. It filed 30 findings, 4 critical and 12 major and 14 minor, every one with a reproduction it actually ran. It fixed nothing and closed nothing, per the finder-is-never-the-closer rule.

The single finding it would fix first, if only one could be fixed: F-4.2-A-01.

## Critical

### F-4.2-A-01: untrusted content reaches the terminal unescaped

A CLI writes to a terminal, and a terminal EXECUTES control sequences. Layer 2 and Layer 3 content is untrusted external text, and none of it is escaped before `render.py` writes it to a stream. A hostile abstract or record field can clear the screen (`\x1b[2J`), reposition the cursor, retitle the window (`\x1b]0;...\x07`), conceal text (`\x1b[8m`), and overwrite an already-printed line with a carriage return.

Worse than the terminal control is the trust attack. Because a `token`'s text is written verbatim, an attacker-supplied abstract can print its own `[answer]` trust prefix and its own `References:` block naming any host. And because `NCBI_SOURCE_URL_PATTERN` is anchored at the start but never TERMINATED, everything after the host is free text including a newline, so a single `source_url` field can carry a whole forged reference row pointing anywhere. All four payloads pass Pydantic validation today.

This lands on the ordinary success path, with exit 0, and needs no rare precondition. It is simultaneously a security defect and an attack on the citation-trust guarantee the product exists to provide.

It also escalates an existing repo-wide open flag. `F-3.4-A-06` records the missing end-anchor on that pattern and says it is "confirmed still not exploitable through any current call site". That was true when every surface rendered to a browser. It is no longer true: this phase adds the first surface where the injected content is executed rather than displayed, and the flag's own stated fix, a character-class restriction rather than a bare `$`, is exactly what closes it.

### F-4.2-A-02: one ordinary Unicode character destroys the entire run

U+2028, U+2029 and U+0085 are ordinary characters in biomedical free text. The server's own serializer emits them raw. `httpx`'s line decoder splits on them, so a `data:` line carrying one is cut in half and the JSON no longer parses. Observed: exit 1, stdout EMPTY, the whole answer lost, against a baseline of exit 0 without the character.

A browser `EventSource` splits only on LF, CR and CRLF per the `text/event-stream` grammar, so the web UI is unaffected and only this surface breaks. The fix belongs in the CLI's own reader.

### F-4.2-A-03: a failed write-back after a successful rotation logs the user out of every surface

Reproduced by making `store()` raise `OSError(28)` after the server had already rotated. The new token is discarded unprinted and unlogged, the file still holds the old one, and the next run replays a rotated token, which revokes the entire session family server-side. The same happens on a `KeyboardInterrupt` at that point, except it escapes uncaught with an empty stderr.

The phase premise calls this a data-loss bound. Today nothing bounds it, and the user is told only `unexpected error (OSError)`.

### F-4.2-A-04: `s3` is uninterruptible outside the stream loop

`main()` installs a `SIGINT` handler for the whole process, but only the stream consumer ever drains its queue, and Python's default `KeyboardInterrupt` is gone. Observed against a real socket and a real signal: Ctrl-C before the create returns hangs indefinitely, and so does three of them; Ctrl-C during `s3 stop` hangs the same way. `SIGKILL` is required. Mid-stream interrupt works exactly as the premise describes, which is precisely why nothing caught this.

## Major

| ID | Finding |
|----|---------|
| F-4.2-A-05 | `CliApiError`, the BASE class, is absent from the caught tuple, so 400, 500, 502 and 503 escape `render_client_error` and dump a raw uncapped body to the terminal: a 16 KB body with ANSI intact reached stderr unfiltered. This is the THIRD instance of the F-4.2-08 seam, and it is in the code that was repaired for exactly that defect |
| F-4.2-A-06 | The refresh-failure handler is dead code. `main.py` catches `httpx.HTTPStatusError`; `credentials.py` raises `RefreshError`. The curated "session expired, run s3 login" message is unreachable. Independently found by the judge as J-4.2-02 |
| F-4.2-A-07 | The answer is NOT streamed. Nothing is ever flushed, so against a server dribbling tokens over two seconds the first stdout byte appeared at t+2.26s, at process exit. `system-design-patterns` rule 6 requires time to first token under one second, and the premise says "streamed to stdout as it is produced" |
| F-4.2-A-08 | `POST /v1/query` IS reissued on a 401, measured at two creates for one user command, and the justification comment in the code is factually false about the server. Independently found by the judge as J-4.2-09 |
| F-4.2-A-09 | The "independent second layer" of cost suppression is a client-side flag anyone can type. Independently found by the judge as J-4.2-03 |
| F-4.2-A-10 | A single unknown or malformed frame aborts the run and discards a complete answer. An event type the server adds later breaks every CLI, though `system-design-patterns` rule 10 names a new enum value as an allowed additive v1 change. `render.py` deliberately tolerates unknown types and `client.py` makes that tolerance unreachable |
| F-4.2-A-11 | Unbounded wait on the refresh lock. A foreign holder hangs `s3` forever with no timeout and no message, against `tool-call-budgets`'s bounded-wait-and-fail-fast requirement |
| F-4.2-A-12 | F-4.2-01 is real and demonstrable, not theoretical. With a server that sends a terminal fatal error and then holds the connection open, the CLI was still hanging twelve seconds later, bounded only by the 45-second read timeout. `TestStoppedRun` passes only because the real server closes the stream. This answers the judge's open question on F-4.2-01 and upgrades it from minor |
| F-4.2-A-13 | A corrupt credential file produces a raw internal error rather than an actionable message: empty file, truncated JSON, wrong JSON type and missing key each surface a bare `JSONDecodeError`, `TypeError` or `KeyError` |
| F-4.2-A-14 | `s3 login` ECHOES THE PASSWORD IN CLEARTEXT on a real terminal. Verified against a real pty: the echo bit is on, and the typed password is echoed back to the screen. `getpass` appears nowhere. `_read_password`'s own docstring claims the password is "never echoed", which is the comment-asserting-a-property-the-code-lacks liability again. The phase file calls this the one genuinely new risk the phase introduces, and the gate arm checked argv, stdout and stderr but never terminal echo |
| F-4.2-A-15 | Exit 0 with no grounded answer: a `done` carrying a non-refuse outcome with zero tokens and zero citations exits 0 with only `[answer]` on stdout, so a shell pipeline reads success |
| F-4.2-A-16 | A truncated stream produces a partial answer, exit 1, and NOTHING on stderr. A user piping to a file gets a silently truncated answer with no explanation anywhere |

## Minor

Fourteen filed, summarized: a lock file that follows a symlink (arbitrary file creation), an unchecked parent-directory mode, a duplicate `citation_id` silently rewriting an already-cited source under a printed marker, error copy promising a retry policy that does not exist, a missing sentence separator in error copy, nonsense `chmod` advice when the path is a directory, `S3_CREDENTIALS_PATH` not expanding `~`, non-JSON 2xx and 3xx responses crashing raw, no bound on SSE line length, diagnostic text written into the answer artifact rather than stderr, a guard-rejected query still printing `[answer]` to stdout, three shipped features with zero production callers (`fetch_citations`, `Last-Event-ID` resume, the disclosure headers), the one-request guarantee depending on a per-client setting outside the module's control, and `load()` doing no type validation.

## Surfaces where it found nothing, stated so its own gaps are visible

Clean: `store()`'s atomic replace does not follow a symlink; the refresh lock genuinely serializes in-process contention, measured at exactly one rotation across six concurrent runs; keepalive comment lines are skipped correctly at real frame boundaries; `id:` values that are negative, enormous, non-numeric or backwards are all correctly ignored with no resume loop; CRLF parses; a frame split across three chunk boundaries reassembles; Ctrl-C MID-STREAM behaves exactly as the premise says; the mode-600 refusal works including through a symlink to a wide target; a create timeout issues exactly one create.

Its own declared coverage gaps: the real abandonment budget under load, multi-process lock contention beyond one foreign holder, the real agent loop and graph since it controlled the wire in every test, non-POSIX platforms, and `s3 login` against the real auth router.
