# Card 75 adversary round, 2026-10-15

Subject: pull request #239, commit 1dba1993, against origin/develop bce08af9. Findings are appended as they are established, numbered A-75-NN. Every finding is NOT FIXED; this round closes nothing.

## Findings

### A-75-01: a request waiting on the renewal lock still sends the spent refresh token when the renewing request is cancelled
- Severity: critical. This sits inside this pull request's fix: the latch check inside `_renew` runs before the in-flight renewal has finished, so it does not stop the case the card names.
- What: request A starts a renewal. Request B arrives and waits on `_renew_lock`. The agent cancels A (`notifications/cancelled`). A's `await asyncio.shield(refresh)` raises `CancelledError`, which releases `_renew_lock` while the shielded renewal is still in flight. B takes the lock, finds `_sign_in_spent` still false and `self._creds` unchanged, and starts a second `refresh_locked` with the same in-memory credentials. That second call waits on the file lock, which the first renewal still holds. When the first renewal gets the unreadable 200, it releases the file lock without storing anything. B then reads the old `refresh-1` back from disk and POSTs it. The server sees a revoked token and revokes the whole family. The latch is set only afterwards, so it protects nothing.
- Reproduction: the probe uses a stand-in server with the router's rotation and its `_revoke_family_on_reuse`. The token has expired. `/auth/refresh` rotates the token, sleeps 0.3 s, then answers 200 with `content-encoding: gzip` and the body `not gzip`. The agent sends CALL id 3 at 0 s, CALL id 4 at 0.05 s, and `notifications/cancelled` for id 3 at 0.1 s. Output at 1dba1993:
  ```
  0.007 sent A
  0.008 server got refresh with refresh-1
  0.058 sent B
  0.109 cancelled A
  0.369 server got refresh with refresh-1
  0.389 server answered 401 ('refresh-1', 'REUSE->FAMILY-REVOKED')
  0.390 drained; latch True family revoked True
  disk refresh: refresh-1
    reply id 4 -32001 Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.
  ```
  origin/develop gives the same sequence and family revocation, so this is not a regression. It is the card's defect, still open on this path.
- What a person sees: they stop one question in the agent app while a second question is waiting. They are then signed out of the command line and the web app at once. The message wrongly says the sign-in "has expired or was signed out", when the bridge itself spent it.
- Why the tests miss it: `test_unreadable_reply_latches_a_request_waiting_on_the_lock` never cancels the first request, so the first request holds `_renew_lock` until the renewal has finished. build.md names this case under "Not covered". The spec's step 4 claims "A request that was already waiting on the lock when the first renewal failed stops here", and that claim does not hold under cancellation.
- Possible direction (not a fix): a request that finds a renewal task still in flight should await that task, not start its own. Alternatively, keep `_renew_lock` held until the shielded task finishes.
- NOT FIXED
### A-75-02: a renewal reply lost after the server rotated (read timeout, dropped connection) still signs the person out on their next try
- Severity: major. The specification chose this scope ("Network failures keep today's behaviour"), so it is filed as a scope gap. It is not a build deviation. It is the same "the server may have rotated" doubt the card latches on for a 5xx.
- What: `_latch_if_spent` latches only on `httpx.DecodingError` and `RefreshError`. Suppose the server commits the rotation and the reply is then lost, because the read timed out (`REFRESH_TIMEOUT_SECONDS` is 15 s) or the connection dropped mid-body. The bridge then answers "Check the network connection, then try again". The person tries again, the bridge sends the spent token, and the family is revoked. From the server's side, a body cut off mid-transfer is the same event as the gzip-unreadable 200 the card fixes.
- Reproduction: same stand-in server as A-75-01. `/auth/refresh` rotates the token, then raises the named httpx error. Two CALLs in turn. Output at 1dba1993:
  ```
  [ReadTimeout] refresh log: [('refresh-1', 'REUSE->FAMILY-REVOKED')] | family revoked: True | latch: True
    reply id 3 -32002 Could not reach System 3 to renew your sign-in (ReadTimeout). Check the network connection, then try again.
    reply id 4 -32001 Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.
  [RemoteProtocolError] ... family revoked: True (same replies)
  [ReadError] ... family revoked: True (same replies)
  ```
  origin/develop: identical, so this is not a regression.
- What a person sees: "Check the network connection, then try again." They do as told, and are signed out of every surface. The only rotation the log records is the one the second request triggered.
- Possible direction (not a fix): latch on any failure raised after the request body was sent, and never on a failure to connect (`ConnectError`, `ConnectTimeout`).
- NOT FIXED
### A-75-03: the latch lives only in memory, so a second s3 mcp or s3 ask on the same machine still spends the token
- Severity: major. build.md names this case under "Not covered", and the card's rule reads "this `s3 mcp` process". It is filed because the person is signed out exactly as before, by a path the person cannot see.
- What: the latch leaves the credential file holding the spent `refresh-1`. Any other process that renews from that file sends `refresh-1`, and the server revokes the family. The candidates are a second `s3 mcp` (one per agent app window or per client), `s3 ask` in a terminal, or this MCP server after a restart if the person restarts it before running `s3 login`.
- Reproduction: bridge 1 receives the unreadable 200 after the server rotated. A second `McpBridge` is then built from `credentials.load()`, as `s3 mcp` builds one at start, and sends one CALL. Output at 1dba1993:
  ```
  bridge 1 latch: True
    reply id 3 -32001 Could not read System 3's sign-in renewal reply. The server may have rotated your sign-in, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.
  disk refresh after latch: refresh-1
  bridge 2:
    reply id 7 -32001 Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.
  refresh log: [('refresh-1', 'REUSE->FAMILY-REVOKED')] | family revoked: True
  ```
- What a person sees: one agent window says to sign in again. In the meantime a second window, or a terminal command, signs them out of the web app as well.
- Possible direction (not a fix): record the spent state where every process reads it. For example, mark the refresh token spent in the credential file under the file lock, or remove it, so that `refresh_locked` refuses to send a token marked spent.
- NOT FIXED
### A-75-04: one 502 or 503 during a deploy now locks the MCP server until s3 login and a restart, where develop recovered on the next request
- Severity: major. This is a lock-out regression against develop. The specification chose it ("A 5xx reply latches too"), and the regression is quantified here as the brief asked.
- What: a proxy 502 or 503, or a proxy's HTML 200 maintenance page, comes back before the request reaches the app. The server has not rotated anything. `_refresh_and_store` raises `RefreshError`, and the bridge latches. On develop, the next request renews with the same, still valid, `refresh-1` and gets its answer. Nothing is signed out on either branch. Server side, `refresh` commits the rotation and then returns a `TokenResponse` (router.py lines 638 to 643), so a 5xx that follows a rotation needs a proxy timeout racing a slow commit (a 504). A 502 or 503 from an edge proxy during a deploy has not rotated anything.
- Reproduction: same stand-in server. The first `/auth/refresh` answers the status shown without rotating, and later calls behave normally. Three CALLs in turn.
  ```
  1dba1993:
  [502 once, not rotated] refresh log: [('refresh-1', 'not-rotated-answered-502')] | family revoked: False | mcp requests sent: 0
    reply id 3 -32001 Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.
    reply id 4 -32001 Your System 3 sign-in could not be renewed earlier in this MCP server, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.
    reply id 5 -32001 (same)
  [503 once, not rotated] identical, mcp requests sent: 0
  [html 200 once, not rotated] refresh log: [('refresh-1', 'not-rotated-answered-200')] | mcp requests sent: 0, both replies -32001
  origin/develop:
  [502 once, not rotated] refresh log: [('refresh-1', 'not-rotated-answered-502'), ('refresh-1', 'rotated')] | family revoked: False | mcp requests sent: 2
    reply id 3 -32001 Your System 3 sign-in has expired or was signed out, ...
    reply id 4 result
    reply id 5 result
  [503 once] same as 502. [html 200 once] reply id 4 result.
  ```
  Develop: one failed request, then it recovers by itself, and no one is signed out. This change: every later request fails until the person runs `s3 login` and restarts the MCP server. In an agent app that usually means quitting and reopening the app.
- What a person sees: one deploy blip, and the agent app answers every question with "sign in again". The first message says the sign-in "has expired or was signed out", which is untrue: nothing expired and nothing was signed out.
- Possible direction (not a fix): latch on 401 and on a 200 that cannot be used. On a 5xx or a non-JSON reply with no rotation evidence, keep develop's retry. Alternatively, have the server tell the client whether it rotated. Both are the owner's call, because the card's Decisions section chose this.
- NOT FIXED
### A-75-05: after s3 login the latched MCP server still refuses every request until it is restarted; develop picked up the new sign-in on its own
- Severity: minor (unsure whether major). The specification names this cost ("a person who runs `s3 login` and does not restart the MCP server must restart it"). It is filed with numbers because it is a lock-out that develop does not have.
- What: once the latch is set, `_exchange` refuses before it looks at the credential file. On develop, `refresh_locked` re-reads the file, finds the new `s3 login` refresh token, returns it without calling the server, and the request goes through.
- Reproduction: the stand-in refuses `refresh-1` (unknown, 401). After CALL id 3 fails, the probe stores a fresh login session in the credential file, as `s3 login` does, then sends CALL ids 4 and 5 to the same bridge.
  ```
  1dba1993:   [s3 login, no restart] refresh log: [('refresh-1', 'unknown-401')] | mcp requests sent: 0
    reply id 4 -32001 Your System 3 sign-in could not be renewed earlier in this MCP server, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.
    reply id 5 -32001 (same)
  origin/develop: [s3 login, no restart] refresh log: [('refresh-1', 'unknown-401')] | mcp requests sent: 2
    reply id 4 result
    reply id 5 result
  ```
- What a person sees: they ran `s3 login` as told and asked again, and still get "sign in again". In most agent apps, restarting one MCP server means restarting the app and losing the conversation in progress.
- Possible direction (not a fix): clear the latch when the credential file's refresh token differs from the spent one. That cannot resend the spent token.
- NOT FIXED
### A-75-06: a SessionLostError whose recovery copy was saved latches, though the new sign-in is safe on disk and develop recovered
- Severity: major. This is a lock-out regression against develop, and it was not named in the specification's cost. The specification lists `SessionLostError` as "the server rotated the token but the new one could not be saved". When the recovery copy is written, the new token is saved, and `load()` promotes the copy on its next read.
- What: `SessionLostError` is a `RefreshError`, so `_latch_if_spent` latches on it, recovery copy or not. In that case nothing is spent: the server issued `refresh-2`, the recovery copy holds `refresh-2`, and `refresh_locked`'s `load()` would promote it and return it without calling the server. Develop does exactly that on the next request. The bridge's own stderr line says the copy "will be used automatically", and then the bridge never reads it.
- Reproduction: same stand-in server. The first `credentials.store` raises `OSError(28, "No space left on device")`, and later calls work. Three CALLs in turn.
  ```
  1dba1993:
  refresh log: [('refresh-1', 'rotated')] | family revoked: False | mcp requests sent: 0
  disk refresh now: refresh-2
    reply id 3 -32001 Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.
    reply id 4 -32001 Your System 3 sign-in could not be renewed earlier in this MCP server, so this request was not sent. ...
    reply id 5 -32001 (same)
  stderr: s3 mcp: could not renew the sign-in: The server rotated your session, but the new credentials could not be saved to <dir>/credentials (OSError: [Errno 28] No space left on device). A recovery copy was written to <dir>/credentials.recovery and will be used automatically the next time s3 runs. If that also fails, run: s3 login.
  origin/develop: same refresh log, mcp requests sent: 2, reply id 4 result, reply id 5 result, stderr ends "| s3 mcp: renewed the sign-in"
  ```
- What a person sees: a full disk for a moment, then "sign in again" on every question until they sign in and restart. The first message says the sign-in "has expired or was signed out", which is untrue, and the host log says the opposite.
- Possible direction (not a fix): do not latch on a `SessionLostError` whose recovery copy was written. It needs to be distinguishable from the one where both writes failed, which should latch.
- NOT FIXED
### A-75-07: the same spend happens with one request at a time: cancel or time out, then ask again before the slow renewal finishes
- Severity: critical. This is the same root as A-75-01, inside this pull request's fix. It is filed separately because it needs no concurrency from the agent, so the spec's cancelled-request test, which waits 0.8 s before asking again, cannot see it.
- What: request A's deadline or cancellation fires while its shielded renewal is in flight. A is answered, and `_renew_lock` is free. The person asks again before the renewal finishes. Request B finds the latch unset and starts its own `refresh_locked`, which waits on the file lock. After the first renewal's unreadable 200, B reads `refresh-1` back from disk and sends it. B's renewal is shielded too, so it is sent even if B is itself cancelled or times out.
- Reproduction: same stand-in server, with `REQUEST_DEADLINE_SECONDS` set to 0.2. `/auth/refresh` rotates the token, sleeps 0.5 s, then answers the unreadable 200. CALL id 3 is sent at 0 s, and is answered before CALL id 4 is sent at 0.3 s. Output at 1dba1993:
  ```
  replies before B:
    reply id 3 -32002 System 3 did not answer within 0.2 seconds, so this request was stopped. Try again; if several questions are running at once, send fewer at a time.
  refresh log: [('refresh-1', 'rotated'), ('refresh-1', 'REUSE->FAMILY-REVOKED')] | family revoked: True | latch: True
    reply id 4 -32002 System 3 did not answer within 0.2 seconds, ...
  ```
  origin/develop: the same refresh log, and family revoked: True.
- What a person sees: they press stop on a slow question and ask again at once, as anyone would. They are signed out of every surface. The message says "Try again", and trying again is the thing that signs them out.
- NOT FIXED
### A-75-08: SIGN_IN_NEEDED is -32001, which the MCP SDK defines as REQUEST_TIMEOUT, and this change moves the unreadable-reply answer onto it
- Severity: minor. The code value was already on develop. This pull request adds one more answer to it: the `DecodingError` branch moves from -32002 to -32001. It also adds the latch reply, which every later request now gets.
- What: the MCP SDK in this repository's venv (mcp 2.0.0) defines `mcp_types.jsonrpc.REQUEST_TIMEOUT = -32001`, and the SDK raises its own timeouts with that code (`jsonrpc_dispatcher.py` line 425, `MCPError(code=REQUEST_TIMEOUT, ...)`). A host or client that branches on the code, not the text, reads "sign in again" as "the request timed out", which is a recoverable, retry-later error. It is not an instruction to the person. The retries are harmless once latched, because nothing is sent, but the person is never told to sign in unless the host shows the message text.
- Reproduction:
  ```
  $ python -c "import mcp_types as t, importlib.metadata as m; print('mcp', m.version('mcp'), 'REQUEST_TIMEOUT', t.REQUEST_TIMEOUT); print([n for n in dir(t) if n.isupper() and getattr(t,n) in (-32001,-32002,-32003)])"
  mcp 2.0.0 REQUEST_TIMEOUT -32001
  ['REQUEST_TIMEOUT']
  ```
  At 1dba1993, `mcp_bridge.SIGN_IN_NEEDED == -32001`, and the unreadable-reply answer is `-32001 Could not read System 3's sign-in renewal reply. ...` (probe output in A-75-03).
- What a person sees: depends on the host. A host that shows the text gives a clear instruction. A host that maps codes shows "timed out", or retries silently, and the person never learns they must run `s3 login`. I did not run a third-party MCP host in this round, so how common clients show this is unverified (unsure).
- Also unverified: the MCP spec asks for tool failures to be returned as a `tools/call` result with `isError: true`, so the model reads the text and can relay it. A JSON-RPC error on `tools/call` is a protocol error, and some hosts show it only in their logs.
- NOT FIXED
### Checked and not a finding: credential leaks
- The probe sent nine failure shapes to `/auth/refresh`: 200, 401, 500 and 502 HTML bodies, plus a 200 bad-JSON body, all echoing the presented refresh token and the Authorization header back; an unreadable gzip 200; a 200 with missing fields; a 200 nested 100000 deep; and a `RemoteProtocolError` whose text holds the request body. Each shape ran two CALLs. The probe searched replies, stderr, root logging and warnings for the old access token, `refresh-1`, every issued access token and `refresh-2` to `refresh-5`. Result, at 1dba1993: `hits=[]` in all nine.
- Positive control: the same search flags `refresh-1` when the probe writes it to the bridge's log (`control hits: ['refresh-1']`), so the empty result is not vacuous.

### Checked and not a finding: the case the build covers
- Two CALLs at once, no cancellation, rotation then an unreadable 200. At 1dba1993: refresh log `[('refresh-1', 'rotated')]`, family revoked False, and replies 3, 4 and 5 all -32001. On origin/develop the same probe gives `('refresh-1', 'REUSE->FAMILY-REVOKED')` twice, family revoked True. The probe can tell the two apart, and the latch works in this shape. The author's file passes (68 passed), but that was not counted as evidence.

## Verdict

FAIL. The card's goal is "this `s3 mcp` process never calls `/auth/refresh` again" after an unreadable or refused renewal. That goal is not met within one process: under cancellation (A-75-01), and with one request at a time when the person asks again during a slow renewal (A-75-07). Both sit inside this pull request's fix. A-75-04, A-75-05 and A-75-06 are lock-outs that develop does not have. Two of them, 04 and 05, are costs the specification chose and should go to the owner as decisions. A-75-06 was not named.

Verified with my own probes: A-75-01 to A-75-07, the leak sweep and its control, and the covered-case control, each run against both 1dba1993 and origin/develop bce08af9 (the leak sweep ran on 1dba1993 only). Read only, not run: the server router's behaviour (modelled in the stand-in from router.py lines 328 to 413 and 608 to 643, not run against a database), and how third-party MCP hosts show -32001 (A-75-08).
