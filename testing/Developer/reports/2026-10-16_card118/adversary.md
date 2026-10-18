# Adversary round, card 118 (PR #253), dial 3

## Findings

Round started. Trees: branch head ae271905, develop 467d1081. Card 75 probe (verifier's `vp75/probe.py`, base and EXTRA rows) rerun on both trees before any new probe.

Card 75 scenario rows, branch vs develop 467d1081: every base row (01 to 17, V1 to VC) is byte-identical. In the EXTRA rows only XH (204), XI (202) and R5 (`:443` re-login) changed outcome, all three in the intended direction (latch to quiet retry; restart to resume), plus the 504 wording on XA, XB and FXB. No other row moved.

### A-118-01: A 2xx other than 200 that arrives after the app saved a renewal now resends the spent token and signs the person out of the web app; develop asked for one `s3 login`
- Severity: minor (needs something between the bridge and the app to turn the app's 200 into a 201, 202, 204, 206 or 299 after the app committed; the app itself never sends one). Worse than develop 467d1081. Inside this phase's fix (V-75B-01's new classifier `elif status not in (401, 504):`).
- What: `_RenewalClient.post` now marks every 2xx except 200 as `quiet` and takes the token back off the wire list, so the next request posts the same refresh token again. When the app had already rotated it, the stand-in's copy of `_revoke_family_on_reuse` fires and the web session goes with it. The owner's rule names 502 and 503 ("clear server errors") as the quiet class; a 2xx is not a server error, and its body can carry the new tokens, which the bridge discards.
- Reproduction: `adv118/p1.py` (reuses the card 75 verifier's stand-in server), three `tools/call` each, the app rotates and then the reply status is rewritten:
  ```
  develop  Y1 202 {} after rotation   spent=0 famrev=0 web_out=False codes=[(10,-32001),(11,-32001),(12,-32001)]
  branch   Y1 202 {} after rotation   spent=1 famrev=1 web_out=True  codes=[(10,-32002),(11,-32001),(12,-32001)] log=['rotated','st202R','REUSE->FAMILY']
  branch   Y2 204 empty, Y3 201 JSON, Y4 299 html, Y7 206 JSON after rotation: identical, spent=1 famrev=1 web_out=True
  ```
  Following the words (`seq_follow`): develop F1 202 says `s3 login`, the person runs it, request 11 OK, web untouched. Branch F1 says "Try again in a moment.", the person tries again, request 11 is refused and the web session is revoked.
  Reply 1 on the branch: "System 3 could not renew your sign-in right now (it answered 202), so this request was not sent. Try again in a moment."
- Why it matters: the owner's trade was "an occasional extra command; in return nobody is ever signed out of the web app by surprise". For this class the branch gives the opposite trade: it saves the extra command when the 2xx came from a proxy that never forwarded (V-75B-01's rows XH, XI), and signs the web app out when the 2xx came back after the app saved. Which way the owner wants a 2xx counted is the owner's call; this is filed because it is a newly reachable family revocation. A narrower option the lead could weigh: quiet only for a 2xx whose body is empty or not JSON, latch a JSON 2xx.
- NOT FIXED

### A-118-02: Status codes 600 to 999 also became quiet retries, which neither the build report nor any test names
- Severity: minor (a non-standard code; h11 accepts any three-digit final status from 200 to 999 on a real connection). Worse than develop for the after-rotation case. Inside this phase's fix: dropping `300 <= status < 600` removed the upper bound as well as the lower one.
- What: develop latched 600 to 999 (outside `300 <= status < 600`). The branch retries them quietly. The build report describes the change as "a 2xx that is not 200 included"; the code comment says the same. The new test covers 201, 202, 204 only.
- Reproduction: `adv118/p1.py`:
  ```
  develop  Y5 600 after rotation  spent=0 famrev=0 web_out=False codes=[(10,-32001),(11,-32001),(12,-32001)]
  branch   Y5 600 after rotation  spent=1 famrev=1 web_out=True  codes=[(10,-32002),(11,-32001),(12,-32001)]
  branch   Y6 999 after rotation  same as Y5
  branch   Y8 600 not rotated     codes=[(10,-32002),(11,'OK'),(12,'OK')]   (develop latched)
  ```
- Why it matters: an unannounced widening of the quiet class. No proxy is known to send these, so the user impact is small, but the stated rule ("every other status, a 2xx included") and the tests do not describe what shipped.
- NOT FIXED

### A-118-03: The new 504 log line puts a capitalised full sentence after a semicolon
- Severity: minor (wording in the host log only; no token, no path, the command is right).
- What: the 504 branch logs `... returned 504, so the outcome is unknown; {_SIGN_IN_NOW}`, so the line reads "...; In a terminal, run: s3 login. This MCP server picks up the new sign-in by itself." Same pattern as develop's existing "could not read the sign-in renewal reply; In a terminal ..." line, so not new in kind.
- Reproduction: `vp75/probe.py` with `EXTRA=1 VERBOSE=1`, row XA on the branch:
  `err: s3 mcp: could not confirm the sign-in renewal: POST /auth/refresh returned 504, so the outcome is unknown; In a terminal, run: s3 login. This MCP server picks up the new sign-in by itself.`
- Why it matters: cosmetic. The reply text itself reads cleanly and is accurate ("did not confirm whether it renewed ... The server may have renewed it. In a terminal, run: s3 login."). Worse than develop: no; develop's line falsely said the token was "expired, already used, or revoked".
- NOT FIXED

### A-118-04: The lock-timeout log line names the cause but no remedy, and the reply beside it still says to run `s3 login`
- Severity: unsure (diagnosis only; not worse than develop 467d1081, which said nothing at all).
- What: on a latched bridge whose credential-file lock is held past the bound, each request logs "could not check for a new sign-in: another s3 command was holding the sign-in file" and replies with `_SIGN_IN_SPENT` ("... could not be renewed earlier ... run: s3 login"). A person who already ran `s3 login` is told to run it again; the line does not say to wait for or end the other `s3` command.
- Reproduction: `adv118/p4.py` (bound patched to 0.5 s, another process holds the lock 6 s, bridge latched by a ReadTimeout after rotation):
  ```
  develop seq  10 requests 5.01 s  stderr lines 0
  develop conc 30 requests 2.01 s  stderr lines 0
  branch  seq  10 requests 5.01 s  stderr lines 10, one distinct: "s3 mcp: could not check for a new sign-in: another s3 command was holding the sign-in file"
  branch  conc 30 requests 2.01 s  stderr lines 30, same one line
  both: credential directory path in output False; leak []
  ```
- Why it matters: one line per request, and each only after the full lock wait (20 s unpatched), so it is not a stderr flood: at most one line per in-flight request per wait. No path and no token. Filed only because the reply and the log disagree about what to do.
- NOT FIXED

## Probed and clean

- Port normalisation (`adv118/p3.py`, 30 address pairs on both trees): no two different servers compare equal on the branch. Newly equal pairs are all the same origin: `https://h` with `https://h:443`, `http://h` with `http://h:80`, `HTTPS://H:443`, `https://[::1]:443`, `https://u@h:443` with `https://u@h`, and `:443` before a path or query. Still different, correctly: `https://h:8443`, `:4443`, `https://h:80`, `http://h:443`, `http://h:8080`, `https://[::443]` against `https://[::]`, `https://h:443@evil` against `https://h` and against `https://evil`, `ws://h:443`. Residues that need a restart for the same server, the same on develop: `https://h:` (empty port), `https://h:0443`, a userinfo difference, `https://h.` (trailing dot).
- Odd status lines on a real loopback socket (`adv118/p2.py`, httpx 0.28.1, h11 0.16.0): `HTTP/1.1 200 Weird`, `HTTP/1.1 200`, `HTTP/1.1 200 ` (trailing space), `HTTP/1.0 200 OK` and `103` then `200` all arrive as 200 and go through the unchanged 200 checks. `2000`, `020`, `+20`, a lowercase `http/1.1`, `HTTP/2 200` and a bare `101` raise RemoteProtocolError, which latches on both trees. `100` then `202` arrives as 202 (quiet on the branch, A-118-01). `650` arrives as 650 (quiet on the branch, A-118-02).
- 504 reply and log: no token, no path, the command is `s3 login`, code -32001 as on develop. Leak scan of every row in the card 75 probe on both trees: `leak=[]`.

## Verdict

FAIL, narrowly, on the owner's rule "nobody is ever signed out of the web app by surprise".

What is worse than develop 467d1081: a renewal reply with a status of 201 to 299, or 600 to 999, that arrives after the app has already saved the renewal. On the branch the bridge sends the spent refresh token again, which revokes the person's whole sign-in family, the web app included. Develop asked for one `s3 login` and revoked nothing. This sits inside this phase's own fix, the V-75B-01 classifier `elif status not in (401, 504):`, so it fires the review loop's stop condition. Rows A-118-01 and A-118-02.

What makes it rare: the app only ever answers 200, 401, 422 or a 5xx. Something in front of the app has to rewrite a 200 after the app committed. The owner already accepted this same cost for a 500 or 502 after rotation (card 75's rows F04 and FX1). Whether a 2xx belongs in that accepted class is the owner's call. The owner's own words name only "clear server errors (502, 503)".

Everything else asked for in the brief came out the same as develop or better:

- Port normalisation: no two different servers merge.
- The 504 reply and the lock-timeout reply: no token, no path, the right command.
- The lock-timeout log line: one line per request, and only after the full lock wait.
- The card 75 scenario rows: no row changed beyond XH, XI, R5 and the 504 wording.

### Verified by my own probes

| Claim | How it was checked |
|---|---|
| Every card 75 row on both trees | Base and EXTRA rows rerun, then diffed |
| 2xx and 600+ after rotation, and not rotated | `adv118/p1.py` |
| Following the reply's words after a 202, 204 or 600 | `adv118/p1.py` |
| How odd status lines arrive over a real socket | `adv118/p2.py` |
| 30 address pairs through `_normalised_address` | `adv118/p3.py` |
| Lock-timeout log count, path and token, sequential and concurrent | `adv118/p4.py` |
| 504 reply and log text | Card 75 probe rows XA, XB and FXB, VERBOSE |

### Read only, not run

- The new tests in `test_mcp_bridge.py`. I did not run them and did not mutate them.
- The build report's gate results: ruff, isort and the 939-test adapters run.
- The app's refresh route answering only 200 or 401. I read `auth/router.py` lines 608 to 643; middleware was not inspected.

Worktrees `a118` and `a118dev` removed. No live calls were made. No repository file was changed.
