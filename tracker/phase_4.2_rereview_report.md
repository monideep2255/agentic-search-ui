# Build phase 4.2 independent verification, round 1

Verdict: DO NOT MERGE. Dispatched 2026-08-16 against the round-2 fixes, one fresh-context verifier that wrote none of the code and none of the fixes. It probed with its own payloads against real sockets, a real pty, real `SIGINT` delivery, and driven byte streams, rather than reading the fixers' own tests.

## Provenance, stated rather than buried

The originally-dispatched re-review ran at Depth tier and DIED PART-WAY THROUGH on a provider session limit, having reached its mutation proofs. What ran instead is a tier-down: a fresh-context verifier at the builder tier, given the concrete probe-each-critical half of the brief, which is well-specified work. The open-ended half, hunting for subtle regressions nobody named in advance, is Depth-tier work and DID NOT RUN TO COMPLETION.

That gap is recorded here rather than papered over. The lead did not self-certify in its place, since the lead oversaw the fixes and its sign-off would not be a check. A Depth-tier pass is owed before this merges. It is worth noting that the tier-down still found two unclosed criticals, so the substitution was not worthless, but it is not the review that was intended.

## Verdict per critical

| Finding | Verdict | Evidence |
|---------|---------|----------|
| F-4.2-A-01, terminal injection | NOT CLOSED | See F-4.2-RR-01 below |
| F-4.2-A-01, citation URL pattern | CLOSED for every shape tested | No false accept found: percent-encoding, `+`, `,`, `;`, a path colon, an empty path and fragments are all correctly gated to the printable-URL class, and no control byte or raw newline can enter. Two narrow false rejects found, a bare host with no trailing slash and un-percent-encoded non-ASCII path characters, both judged correct since every real call site emits an already-encoded URL carrying a path |
| F-4.2-A-02, Unicode line splitting | CLOSED, with one adjacent gap | U+2028, U+2029 and U+0085 all survive intact; a 2-byte UTF-8 character split across a chunk boundary reassembles; a truncated trailing sequence is handled. The adjacent gap is F-4.2-RR-04 |
| F-4.2-A-04, SIGINT | CLOSED, strongest evidence in the round | Real `SIGINT` to a real subprocess against a real socket, during create, stop, refresh, login, and at the instant the stream scope opens before any byte arrives. All five exit 130 within roughly 30ms with no hang and no `SIGKILL` |
| F-4.2-A-14, password echo | CLOSED | Real `pty.openpty()`. The `termios` ECHO bit is off while the password is read, against a baseline pty where it is on, and the password never appears in the pty transcript. The non-TTY path still works unchanged |

## New findings

| ID | Severity | Finding |
|----|----------|---------|
| F-4.2-RR-01 | CRITICAL | Bidirectional format characters bypass the sanitizer entirely and reach the answer body. `_escape_control_bytes` covers `code < 0x20`, `0x7F`, and `0x80` to `0x9F`. U+202E, U+200F and U+2066 to U+2069 are all outside that range and pass through byte-for-byte, in `token.text` and in `citation.source`. A bidi-aware terminal then renders the tail right-to-left, so a cited clinical claim DISPLAYS the opposite of what it encodes: `"The variant is benign‮ )1[ tnangilam si( "` shows as though it said malignant. This is the same threat model F-4.2-A-01 exists to close, unmitigated, and it lands inside the answer body rather than a peripheral field. The gap arose the way such gaps do: C0 and C1 were enumerated and everything else was implicitly trusted |
| F-4.2-RR-03 | major | A REGRESSION ROUND 2 INTRODUCED while closing F-4.2-A-10. A frame that would have been fatal but fails payload validation is now silently skipped and counted, and a later well-formed non-fatal `done` then reports clean success: exit 0, a trust-tagged answer on stdout, and only a generic stderr line that is indistinguishable from a benign future-event-type skip. `s3 ask > answer.txt` therefore captures a confident answer that dropped a fatal error on the floor. The control case is genuinely fixed and must stay fixed: a stream consisting only of one malformed `done` correctly exits 1 |
| F-4.2-RR-02 | major | The forgery defense is case-sensitive and literal-only. `[ANSWER]`, `[Answer]`, internal padding, fullwidth brackets, a fullwidth colon, a Cyrillic look-alike and an interior zero-width space all pass through unescaped, while the module docstring promises a forged occurrence can "never be indistinguishable". That is a docstring asserting a property the code lacks, which is the liability `self-eval-loop` names and the third instance of it in this phase |
| F-4.2-RR-04 | minor | An invalid UTF-8 byte mid-stream raises an uncaught `UnicodeDecodeError` out of the splitter, caught only by the broad handler at the call site. Not a hang and not a raw traceback, but inconsistent with the truncated-multi-byte case, which is handled locally |
| F-4.2-RR-05 | informational, unconfirmed | A theoretical signal-handler race at the scope's entry and exit boundaries. The pre-entry case is provably harmless. The post-exit case could in principle swallow one interrupt as a run is already finishing. NOT REPRODUCED across dozens of real signal deliveries in six scenarios; the window is too narrow to hit from a driver process. Recorded as an open question, not a demonstrated defect |

## Regression checks that came back clean

Worth recording, because a review listing only failures gives no signal about what is safe to build on.

- Ordinary biomedical text passes through the sanitizer byte-for-byte unchanged: brackets, `p.Arg175His` and `c.524G>A` notation, percent confidence intervals, Greek letters, superscripts, em-dashes and `HLA-DRB1*15:01`. The sanitizer does not mangle real answers, which would have been a worse defect than the one it fixes.
- A citation arriving in the SAME byte chunk as the terminal `done` is not dropped; both are yielded, in order.
- `--operator` is cleanly gone: no argparse entry, an exit 2 if passed, no stale help text, and every remaining `operator=` call site hardcodes `False` deliberately.

## What the verifier could not check, in its own words

F-4.2-A-03 (the failed write-back after rotation) and J-4.2-01 (the scanner false positive) were outside its assigned five. It tested against mocks and a hand-built fake server, never the real agent loop or graph. It sampled Unicode confusables rather than fuzzing the space exhaustively. It did not attempt non-POSIX signal handling.
