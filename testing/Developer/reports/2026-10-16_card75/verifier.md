# Card 75 fresh verifier, pull request 252, branch at 57898161 against develop bff040aa

## Findings

Probe: my own `vp75/probe.py` in the scratchpad (built on the judge's stand-in, which copies the router's rotation and family revocation on reuse, extended with a generic status row, a follow-the-words mode, re-login rows and the overlapping-renewal race). Real McpBridge from each tree, `httpx.MockTransport`, no live calls.

### V-75B-01: A 204 or 202 renewal answer latches and says the sign-in "has expired or was signed out"; develop answered the next request, and the class's own docstring says every status except 200, 401 and 504 retries quietly
- Severity: minor (a proxy rarely answers a POST with 204 or 202). Worse than develop, not a truly unknown outcome. Inside the fix round's change: the classifier `elif status not in (401, 504) and 300 <= status < 600` covers only 3xx to 5xx, while `_RenewalClient`'s docstring says "every status except 200, 401 and 504". It was also latched at 2306eaec, so not a new regression, but the fix round's rule left the gap.
- Reproduction: `vp75/probe.py`, rows XH (204, empty body, no content type, no rotation) and XI (202, `application/json`, `{}`), three `tools/call`:
  ```
  develop: XH 204 empty  spent=0 famrev=0 codes=[(10,-32001),(11,'OK'),(12,'OK')]
           XI 202 json   spent=0 famrev=0 codes=[(10,-32001),(11,'OK'),(12,'OK')]
  branch:  XH 204 empty  spent=0 famrev=0 codes=[(10,-32001),(11,-32001),(12,-32001)]
           XI 202 json   same
   msg 1: Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login. ...
   err:   POST /auth/refresh returned 204; the stored refresh token is expired, already used, or revoked. Run: s3 login
  ```
  A 599 (row XJ) retries quietly, so the gap is exactly 1xx and 2xx other than 200 (and any code of 600 or more).
- Why it matters: the lead's reading names "an empty reply" as a quiet retry; a 204 is the plainest empty reply and it latches, and the person is told something false about their sign-in. Rare in practice.
- NOT FIXED

### V-75B-02: A 504 renewal answer, now a latch, tells the person their sign-in "has expired or was signed out", and the host log says the token "is expired, already used, or revoked"; the outcome is unknown, not an expiry
- Severity: minor (wording; the remedy `s3 login` is right and no token is resent). The 504 latch is new in the fix round (A-75B-04's closure); the words are the module's generic RefreshError text, the same text develop printed for a 504, so not worse than develop.
- Reproduction: `vp75/probe.py`, rows XA (504, not rotated) and XB (504 after rotation), branch:
  ```
  msg 1: Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login. This MCP server picks up the new sign-in by itself.
  err:   s3 mcp: could not renew the sign-in: POST /auth/refresh returned 504; the stored refresh token is expired, already used, or revoked. Run: s3 login
  ```
  Compare the read-timeout latch on the same branch (row R2): "Could not confirm that System 3 renewed your sign-in (ReadTimeout) ...", which is honest about the unknown.
- Why it matters: "a confident wrong record is worse than a missing one". A 504 is the case the fix round itself classified as "a gateway stopped waiting for a server that may have renewed"; the reply should say that, as the timeout branch does.
- NOT FIXED

### V-75B-03: After a latch, `s3 login` saved with an explicit default port (`https://host:443`) is treated as another server and needs a restart; develop answered at once
- Severity: minor (narrow path; the message names the right remedy, a restart). Inside the fix round's change (`_normalised_address`, A-75B-05's closure), which lowercases and strips a trailing slash but does not drop a default port.
- Reproduction: `vp75/probe.py` rows R1 to R5: latch on a ReadTimeout after rotation, then a new sign-in stored with the address written each way, two more `tools/call`:
  ```
  branch: R1 same / R2 trailing slash / R3 upper case   codes=[(10,-32002),(11,'OK'),(12,'OK')]   (A-75B-05 fixed)
          R4 other host   codes=[(10,-32002),(11,-32001),(12,-32001)]  msg: "... different server address ... Restart this MCP server to use it."
          R5 https://system3.test:443   same as R4
  develop: R1 to R5 all codes=[(10,-32002),(11,'OK'),(12,'OK')]  (R4 on develop adopts the other server's tokens against the old host)
  ```
- Why it matters: only a person who typed the port gets a needless restart. R4's refusal is safer than develop, not worse.
- NOT FIXED

### V-75B-04: When the cross-process lock times out on a latched bridge, the cause is dropped without a stderr line, and the reply only repeats "could not be renewed earlier ... run: s3 login"
- Severity: minor (diagnosis only; nothing is sent, no token is spent). Inside the fix round's change (`_resume_from_file` catches `CredentialsError` and `OSError`, including `RefreshLockTimeoutError`, and returns None with no log).
- Reproduction: `vp75/lockprobe.py` row L3: a separate process holds the refresh lock past the bound (bound patched to 1.5 s, held 4 s), the bridge is latched by a ReadTimeout after rotation, one more `tools/call`:
  ```
  develop: 1.5 s (11,-32001) "The s3 sign-in on this computer could not be used. ..."; stderr: "could not renew the sign-in: Another s3 process is holding the credential refresh lock at <path> ..."
  branch:  1.5 s (11,-32001) "Your System 3 sign-in could not be renewed earlier in this MCP server, ... run: s3 login ..."; stderr: no line for this request
  ```
- Why it matters: a person who has already run `s3 login` while some other `s3` command is stuck holding the lock is told to run `s3 login` again, every time, with nothing in the host log saying why. Develop named the stuck lock (though its line also printed the local lock path, see the leak section).
- NOT FIXED

### V-75B-05: A refresh-lock timeout on a bridge that is not latched still prints the local credential directory's path on stderr, and its reply still says "then restart this MCP server"; same on develop
- Severity: minor, pre-existing (not worse than develop; filed because check 4 asks for no path on any stderr line).
- Reproduction: `vp75/lock2.py`: another process holds the refresh lock past the bound (patched to 1.0 s), the bridge's access token is expired, one `tools/call`:
  ```
  develop: [(10,-32001),(11,'OK')]  tmp path in stderr: True | in replies: False
  branch:  [(10,-32001),(11,'OK')]  tmp path in stderr: True | in replies: False
  msg (both): The s3 sign-in on this computer could not be used. In a terminal, run: s3 login, then restart this MCP server.
  ```
  The stderr line is the credential module's `RefreshLockTimeoutError` text ("... holding the credential refresh lock at <path> ... rm <path>"), passed through `_sanitize_untrusted`, which does not remove paths. On a real machine that path is under the person's home directory. The reply's "restart" contradicts `_SIGN_IN_NOW` elsewhere on the branch, and `s3 login` is not the remedy for a stuck lock.
- Why it matters: a host that keeps MCP stderr in a shared log carries the home path. Develop does the same, so this does not block.
- NOT FIXED

### V-75B-06: A latch after a lost reply (read timeout, read error, protocol error) answers with code -32002, the "try again" code, while the text says to run `s3 login`
- Severity: unsure (an agent that branches on the code retries once and then gets -32001; no token is sent). Present at 2306eaec as well, not new in the fix round.
- Reproduction: `vp75/probe.py` rows 08, 09, 10, V2, V3 on the branch: codes `[(10,-32002),(11,-32001)]`; reply 1 "Could not confirm that System 3 renewed your sign-in (ReadTimeout), so this request was not sent. In a terminal, run: s3 login. ..." The other latches (gzip row 01, 504 rows XA and XB, 401) answer -32001 at once.
- Why it matters: the code and the words disagree on the one reply that matters most; an agent host keyed on -32001 to show a sign-in prompt shows none the first time.
- NOT FIXED

## Check 1: scenario table on both trees

My own probe (`vp75/probe.py`, base rows and `EXTRA=1` rows), same stand-in on both trees. "s/r" is spent-token sends and family revocations; a revocation also signs the web session out. Three requests for the X rows, two otherwise.

| Row | Scenario | Develop | Branch 57898161 | Verdict |
|---|---|---|---|---|
| 01 | gzip 200 after rotation | 1/1; -32002, -32001 | 0/0; latch | better |
| 02 | HTML 200, not rotated | 0/0; -32001, OK | 0/0; -32002, OK | same, truer words |
| 03 | 401 | 0/0; latched | 0/0; latched | same |
| 04, XM | 500 after rotation | 1/1 (XM: 2/2) | 1/1 | same or better; the owner's accepted cost |
| 05, 06, 07 | proxy 502, 503, 429 once | 0/0; -32001, OK | 0/0; -32002, OK | same |
| 08, 09, 10 | read timeout, read error, protocol error after rotation | 1/1 | 0/0; latch | better |
| 11 | ConnectError | 0/0; OK next | 0/0; OK next | same |
| 12 | store fails, recovery copy | 0/0; OK next | 0/0; OK next | same |
| 13 | store and recovery fail | 1/1 | 0/0; latch | better |
| 14, 15, 16 | cancel and deadline races | 1/1 each | 0/0 each | better |
| 17 | 401, s3 login, no restart | -32001, OK | -32001, OK | same |
| V1, XB | 504 after rotation | 1/1 (XB 2/2) | 0/0; latch | better (A-75B-04 closed) |
| XA | 504, not rotated | 0/0; -32001, OK | 0/0; latch | latch on an outcome the reading names unknown, accepted |
| V2, V3 | read timeout, protocol error, never reached the app | 0/0; OK next | 0/0; latch | latch on a truly unknown outcome, accepted |
| V4, V5 | write error, proxy error | 0/0; OK next | 0/0; OK next | same |
| V6 | second s3 mcp, gzip after rotation | 2/2 | 1/1 | better (A-75-03 still open, as before) |
| V7 | second s3 mcp, proxy 503 | 0/0 | 0/0 | same |
| V8 | s3 ask after latch, gzip after rotation | 2/2 | 1/1 | better (A-75-03) |
| V9 | s3 ask after latch, proxy 503 | 0/0; OK | 0/0; OK | same |
| VA, VB | renewal racing s3 login | 0/0; OK | 0/0; OK | same |
| VC | proxy 503 then healthy, four requests | -32001, OK x3 | -32002, OK x3 | same |
| X1, XN, XO | 502, 503, HTML 200 after the app rotated | 2/2 | 1/1 | better count; the owner's accepted cost |
| X2 to X7c, X9 | 403, 404 HTML, 404 JSON, 408, 400, 422, 301, 307, 421, 418, not rotated | 0/0; -32001, OK, OK | 0/0; -32002, OK, OK | same (A-75B-01, J-75B-01 closed) |
| X8, XJ, XK, XL | 500 JSON, 599, 429 JSON, 503 JSON, not rotated | 0/0; OK next | 0/0; OK next | same |
| XC, XD | empty JSON 200, empty 200 with no type | 0/0; OK next | 0/0; OK next | same (A-75B-02 closed) |
| XE, XG | `{}` or whitespace JSON 200, not rotated | 0/0; OK next | 0/0; latch | latch on a non-empty unreadable JSON 200, as the reading says |
| XF | `{}` JSON 200 after rotation | 2/2 | 0/0; latch | better |
| XH, XI | 204 empty, 202 JSON | 0/0; OK next | 0/0; latch | worse (V-75B-01) |
| F04, FX1 | follow the words, 500 or 502 after rotation | 0/0 (said s3 login) | 1/1 (said try again) | the owner's accepted cost for 500 and 502; the words no longer claim the sign-in is good |
| FXB | follow the words, 504 after rotation | 0/0 | 0/0 | same |
| R1, R2, R3 | latch, then s3 login same address, trailing slash, upper case | OK | OK | same (A-75B-05 closed) |
| R4 | latch, then s3 login for another host | OK on the wrong host | refused, "Restart this MCP server to use it." | safer |
| R5 | latch, then s3 login with `:443` | OK | refused, restart | worse, narrow (V-75B-03) |
| S1 to S3 | abandoned HTML-200 renewal, then 401, `{}` after rotation, or gzip | 0/0 or 1/1 | 0/0; right latch message each | better (J-75B-04, A-75B-06 closed) |
| S4 | abandoned HTML-200 renewal, then 503 | OK on the third | -32002 "answered 503", OK on the third | same |

Every row on both trees printed `leak=[]`.

## Check 2: fix-round closures, by probe

| Finding | By probe |
|---|---|
| J-75B-01, A-75B-01, J-75B-05 | Fixed: rows X2 to X7c, X9 retry quietly. Every named test exists; my 504 mutation turned `test_a_504_on_renewal_asks_for_s3_login_once` red |
| A-75B-02 | Fixed: rows XC, XD quiet; XE, XF, 01 still latch |
| J-75B-02, A-75B-03 | Fixed: no reply on the branch contains "still good" (all distinct replies listed in the run); the quiet text is "Try again in a moment." |
| A-75B-04 | Fixed: rows V1, XA, XB latch with one send; FXB leads to `s3 login`. Wording residue: V-75B-02 |
| A-75B-05 | Fixed for a trailing slash and case (R2, R3); another host now says restart (R4). Residue: V-75B-03 |
| J-75B-04, A-75B-06 | Fixed: rows S1 to S3 give the latch message of their own renewal and the right stderr line |
| A-75B-08 | Fixed: `lockprobe.py` L1 shows a latched request waits 3.0 s for another process's lock (so the read is under it); my mutation that drops the lock turned the fix round's test red and L1 to 0.0 s |

## Check 3: the new lock

| Probe (`vp75/lockprobe.py`, `selflock.py`) | Develop | Branch |
|---|---|---|
| L1, another process holds the lock 3 s, nothing new | 3.03 s, -32001 | 3.02 s, -32001 |
| L2, another process holds it 3 s and saves a renewal | 3.04 s, OK | 3.02 s, OK (resumed from the file) |
| L3, held past the bound (patched to 1.5 s) | 1.5 s, -32001 | 1.5 s, -32001, no stderr line (V-75B-04) |
| L4, 20 requests at once while held 2 s, plus a ping | 2.48 s; ping in 0.001 s | 2.05 s; ping in 0.001 s |
| L5, 200 refused requests one by one | 4.39 s, 201 renewal posts, 200 spent sends | 0.05 s, 1 renewal post, 0 spent |
| L5, 200 refused requests at once | 4.98 s, 200 spent sends | 0.02 s, 0 spent |
| Own abandoned slow renewal holding the lock while two requests arrive | 2.32 s, 2 spent, 2 revocations | 2.27 s, 0 spent, both refused, no hang |

- A refused request waits only as long as another process holds the lock, at most the module's 20 s bound, inside the bridge's 300 s deadline. Develop's request waited the same, because it went into `refresh_locked`.
- No deadlock: `_resume_from_file` releases the file lock before `refresh_locked` takes it, and the lock polls without blocking the loop.
- `_CredentialFileLock` and `_lock_path` are private names of an unchanged module, looked up at call time, so a patched `CREDENTIALS_PATH` is honoured. A rename would raise `AttributeError`, which `_resume_from_file` does not catch (every latched request would get the unforeseen-failure reply); the fix round's test references both names, so CI would go red first.

## Check 4: leaks and wording

- `vp75/leak.py`: refresh replies echoing the presented refresh token, the bearer, the request body and the temporary credential directory in body and headers, for 502, 504, 401, 403, 404 JSON, 204, 429, 301, HTML 200, a `{}` 200, a bad JSON 200, a protocol error and a gzip lie after rotation, a store failure and another-host re-login. Searched replies, stderr, root logging at DEBUG (1669 bytes on the branch) and warnings.
- Branch: `token_hits=[]` and `path_hits=[]` in all fifteen. Develop: a path hit in the store-failure row, which the branch removed.
- Positive control: a token and the directory written through `bridge.log`: `(['refresh-1'], ['<tmp>', ...])` on both trees.
- Outside the sweep: the lock-timeout path still prints the path on stderr on both trees (V-75B-05).
- Wording: every latch reply says "In a terminal, run: s3 login"; every quiet reply says "Try again in a moment."; the other-server reply says "Restart this MCP server to use it." Wrong claims remain for 504, 204 and 202 (V-75B-01, V-75B-02).

## Check 5: gates and mutation, at 57898161

| Gate | Result |
|---|---|
| `ruff check` | All checks passed! (exit 0) |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | Skipped 2 files (exit 0) |
| `pytest tests/system_03_search_agent/adapters -m "not integration" -q` | 932 passed, 2 warnings |
| Mutation 1: `_resume_from_file` reads `load()` with no lock | `test_a_latched_bridge_reads_the_credential_file_under_the_refresh_lock` red (1 failed, 114 passed); probe L1 0.0 s. Restored, `cmp` equal |
| Mutation 2: 504 removed from the latching statuses | `test_a_504_on_renewal_asks_for_s3_login_once` red (1 failed, 114 passed). Restored, `cmp` equal, `git status --short` empty |

## Verified by my own probes versus only read

- Run: every row in check 1 on both trees, the follow-the-words rows, the re-login rows, the overlapping-renewal rows, the lock waits with a real second process, the self-contention race, the 200-request timings, the leak sweep with its control, both mutations and the three gates.
- Read only: that the app's `/auth/refresh` can answer only 200, 401, 422 or a 5xx (from the judge's and adversary's reading, not re-read); how often any row happens in production; the claim that a rename of the private lock names would be caught (reasoned from the test's references, not run).

## Verdict

HOLD, narrowly. Nothing sends a spent token more often than develop: every revocation count on the branch is at or below develop's, and the 200-request run went from 200 spent sends to none. Worse than develop, outside the accepted latch:

- V-75B-01 (minor): a 204 or 202 renewal answer latches and says the sign-in expired. It contradicts `_RenewalClient`'s own docstring and the lead's "an empty reply retries quietly". This gap sits inside the fix round's rewritten classifier; it was not introduced by it (2306eaec latched these too). It is one comparison.
- V-75B-03 (minor): a re-login saved with an explicit `:443` needs a restart where develop needed nothing. This sits inside the fix round's new `_normalised_address`.

Both need an unusual proxy answer or an unusual typed address. If the lead judges them too rare to hold the card, the rest of the bar is met: every row is the same, better, or a latch on an outcome the reading names unknown. V-75B-02, 04, 05 and 06 are wording and diagnosis only.
