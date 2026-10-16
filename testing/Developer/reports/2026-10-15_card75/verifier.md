# Card 75, fresh verifier

Fresh verifier, 2026-10-16. Subject: pull request #239 at ad192fef against origin/develop bce08af9. Probes run the real McpBridge from each tree against a stand-in server through httpx.MockTransport. Findings are V-75-NN, written as each is established.

## Findings

### V-75-01: A renewal lost before it reached the server (read timeout, dropped or stale connection, write error, proxy error) now locks the MCP server until s3 login; develop recovered on the next request
- Severity: major. Inside this phase's fix: the fix round closed A-75-02 by latching on every failure after the POST was attempted, except `ConnectError`, `ConnectTimeout`, `PoolTimeout` and a 429.
- What: `_RenewalClient.post` keeps the token in `_wired` for any transport error other than the three connect-phase ones, so `_latch_if_spent` latches. When the server never saw the renewal, the refresh token is still live, yet every later request is refused with "run s3 login". Develop sent the same live token again and answered.
- Reproduction: verifier probe `vprobe/probe.py` (scratchpad, not committed), stand-in copying `auth/router.py`'s rotation and `_revoke_family_on_reuse`, the transport raising the named error before the app sees anything, two `tools/call` in turn:
  ```
  develop bce08af9:
  V2 ReadTimeout, never reached app          spent=0 famrev=0 web_out=False mcp=1 codes=[(10, -32002), (11, 'OK')] log=['readtimeout_norot', 'rotated']
  V3 RemoteProtocolError, never reached app  spent=0 famrev=0 web_out=False mcp=1 codes=[(10, -32002), (11, 'OK')]
  V4 WriteError, never reached app           spent=0 famrev=0 web_out=False mcp=1 codes=[(10, -32002), (11, 'OK')]
  V5 ProxyError, never reached app           spent=0 famrev=0 web_out=False mcp=1 codes=[(10, -32002), (11, 'OK')]
  PR ad192fef:
  V2 ReadTimeout, never reached app          spent=0 famrev=0 web_out=False mcp=0 codes=[(10, -32002), (11, -32001)] log=['readtimeout_norot']
  V3 RemoteProtocolError, never reached app  spent=0 famrev=0 web_out=False mcp=0 codes=[(10, -32002), (11, -32001)]
  V4 WriteError, never reached app           spent=0 famrev=0 web_out=False mcp=0 codes=[(10, -32002), (11, -32001)]
  V5 ProxyError, never reached app           spent=0 famrev=0 web_out=False mcp=0 codes=[(10, -32002), (11, -32001)]
  ```
  PR messages for V2: first "Could not reach System 3 to renew your sign-in (ReadTimeout). Check the network connection, then try again.", then on trying again "Your System 3 sign-in could not be renewed earlier in this MCP server, so this request was not sent. In a terminal, run: s3 login. ..."
- Why it matters: the person is told to try again, tries again, and is told to sign in, though nothing was spent. A `RemoteProtocolError` ("server disconnected without sending a response") on a reused pooled connection is a known httpx failure where the server never processed the request; the bridge's renewal shares its long-lived client's pool. How often the server had already rotated in these cases is unknown from the client, so this is the same trade as A-75-04, extended by the fix round to network errors. Remedy for the person: `s3 login` (no restart, verified, row 17). Nobody is signed out of the web app.
- NOT FIXED

### V-75-02: A-75-04 holds as filed: one proxy 502, 503, or an HTML 200, with no rotation, refuses every later request until s3 login; develop answered the next request
- Severity: major against tonight's bar (worse than develop for that person); the specification's chosen trade.
- What: any non-200 and non-429 reply, and a 200 that is not usable JSON, latches. The latch is cleared only by a refresh token in the credential file that this process never sent, which in practice means `s3 login` or another process renewing successfully.
- Reproduction: `vprobe/probe.py`, the first `/auth/refresh` answered by a proxy without reaching the app, then healthy:
  ```
  develop: VC proxy 503 then healthy, 4 calls  mcp=3 codes=[(10, -32001), (11, 'OK'), (12, 'OK'), (13, 'OK')] log=['proxy503', 'rotated']
  PR:      VC proxy 503 then healthy, 4 calls  mcp=0 codes=[(10, -32001), (11, -32001), (12, -32001), (13, -32001)] log=['proxy503']
  develop: 05 proxy 502 once  codes=[(10, -32001), (11, 'OK')];  02 html 200  codes=[(10, -32001), (11, 'OK')]
  PR:      05 proxy 502 once  codes=[(10, -32001), (11, -32001)];  02 html 200  codes=[(10, -32001), (11, -32001)]
  ```
  PR message: "System 3 could not renew your sign-in (it answered 502), so this request was not sent. In a terminal, run: s3 login. This MCP server picks up the new sign-in by itself."
- Why it matters: see the weighing in the verdict section. No sign-out anywhere on either branch in these rows; the PR costs one `s3 login`, develop cost nothing.
- NOT FIXED

### V-75-03: A proxy's HTML 200 on renewal is still told "your sign-in has expired or was signed out", and the log says "Retry" though every retry is now refused
- Severity: minor (wording). J-75-06's fix covers a 429 and a 5xx only; a 200 that is not JSON falls through to `_message_from_credentials_error`.
- What: the reply to the agent claims the sign-in expired; nothing expired. The stderr line from the credential module ends "Retry, or report this to the operator if it recurs", while the latch refuses every retry.
- Reproduction: `vprobe/probe.py` row 02 at ad192fef, `/auth/refresh` answered 200 `text/html` by a proxy without rotation:
  ```
  msg: Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login. This MCP server picks up the new sign-in by itself.
  err: s3 mcp: could not renew the sign-in: POST /auth/refresh returned a non-JSON response (content-type text/html); this indicates a server or proxy misconfiguration, not a normal failure. Retry, or report this to the operator if it recurs.
  ```
- Why it matters: "Honesty beats polish": a person told they were signed out during a maintenance page may suspect their account. The remedy given (s3 login) does work.
- NOT FIXED

### V-75-04: The host log still says "then restart this MCP server" after an unreadable renewal reply, while the agent is told no restart is needed
- Severity: minor (wording, inside this phase's change).
- What: the `httpx.DecodingError` branch logs `_SIGN_IN_AGAIN` ("run: s3 login, then restart this MCP server") while the reply carries `_SIGN_IN_NOW` ("This MCP server picks up the new sign-in by itself").
- Reproduction: `vprobe/probe.py` row 01 at ad192fef:
  ```
  msg: Could not read System 3's sign-in renewal reply. ... In a terminal, run: s3 login. This MCP server picks up the new sign-in by itself.
  err: s3 mcp: could not decode the sign-in renewal reply; In a terminal, run: s3 login, then restart this MCP server.
  ```
- Why it matters: two instructions disagree; a person reading the host log restarts the app needlessly and may lose the conversation in progress. Harmless otherwise.
- NOT FIXED

### Checked, not a finding: the closed list reproduced by the verifier's own probe
- `vprobe/probe.py`, rows numbered as fix_round.md's 17 plus verifier rows V1 to VC, run against both trees. Closed with spent=0 and famrev=0 on ad192fef where develop had spent=1 famrev=1: A-75-01 (row 14), J-75-04 (row 15), A-75-07 (row 16), A-75-02 and J-75-02 (rows 08, 09, 10, and V1 a 504 after rotation). Recovered with no s3 login where 1dba1993 had locked out: A-75-06 and J-75-03 (row 12, `(11, 'OK')`), J-75-01's 429 half (row 07, `(11, 'OK')`). A-75-05 and J-75-07 (row 17: 401, then s3 login, then `(11, 'OK')` with no restart). J-75-06 (row 05 message "System 3 could not renew your sign-in (it answered 502)", stderr "POST /auth/refresh returned 502"; the HTML 200 half is V-75-03).
- J-75-05: mutant `_latch_if_spent` returns early for `SessionLostError`: `1 failed, 80 passed` (`test_a_renewal_that_could_not_be_saved_anywhere_latches`); restored. With the mutant the probe's row 13 still showed spent=0, because the check at the POST backstops it; the test pins the latch, the POST check pins the person's outcome.

### Checked, not a finding: no token in any reply, log or stderr
- `vprobe/leak.py`, both trees: refresh replies echoing the presented refresh token and the request body in a 502 body and header, a 401 detail and `www-authenticate`, an HTML 200, a bad-JSON 200, a 429 with the token in `retry-after`, and a `RemoteProtocolError` whose text holds the body. Searched agent replies, stderr, root logging at DEBUG (586 bytes captured on ad192fef) and warnings for every token the stand-in knew. ad192fef: `hits=[]` in all six. Positive control: a token written through `bridge.log`: `control hits: ['refresh-1']`. Every probe row above also printed `leak=[]`.

### Checked, not a finding: break it
- Mutant: `_RenewalClient.post` no longer raises `_SpentTokenRefused` for a token already sent (`raise _SpentTokenRefused` replaced by `pass`). `test_mcp_bridge.py`: `3 failed, 78 passed` (the A-75-01, J-75-04 and A-75-07 tests). Verifier probe on the mutant: rows 14, 15 and 16 went to `spent=1 famrev=1 web_out=True`; rows 01, 08, 12 and 13 stayed spent=0. Restored; `git status --short` empty at ad192fef; rows 14 to 16 back to spent=0.

### V-75-05: Weighed against the server code, the 5xx latch guards a case the server almost cannot produce, and costs an s3 login in the cases it does produce
- Severity: major for tonight's bar; unsure as to rate, since no production logs were read.
- What: `auth/router.py`'s `refresh` commits the rotation (`session.commit()`, line 641) and then only updates headers and returns `TokenResponse`; no middleware wraps `/auth/refresh` (`web_sse/app.py` adds CORS, `RequestTimeoutMiddleware`, which gates itself to `/graphql`, and `ProxySchemeMiddleware`). So:
  - A 5xx with rotation needs the container to die between the commit and the response write, or a proxy that answers 5xx after forwarding. A proxy timeout longer than the client's `REFRESH_TIMEOUT_SECONDS = 15.0` reaches the client as a `ReadTimeout`, not a 5xx. This is the row where develop revokes the family (probe rows 04 and V1, spent=1 famrev=1 web_out=True): rare, a deploy-drain race at most.
  - A 5xx without rotation is every app error before the commit (the database down or slow: the transaction rolls back, nothing rotates) and every proxy 502 or 503 that never reached the app. This is the row where the branch now needs `s3 login` (rows 05, 06, VC) and develop recovered by itself.
  - `railway.json` declares `healthcheckPath: /health`, so a deploy switches traffic after the new container is healthy; deploy 502 and 503 are therefore rarer than the judge's 30-second-blip estimate (about 3.6 percent of active sessions per deploy, J-75-01), but a database outage hits every s3 mcp that renews during it (one renewal per about 14 minutes of use, from the 15-minute access token and the 60-second margin).
- Reproduction: read only for the server, `router.py` lines 608 to 643 and `app.py` lines 307 to 374 at ad192fef. Client side by probe, rows 04, V1, 05, 06, VC above.
- Why it matters: for a 5xx, a person on this branch is worse off than on develop far more often than they are better off. In fairness to the branch: develop's reply to the same proxy 502 told the person "Your System 3 sign-in has expired or was signed out ... run: s3 login, then restart this MCP server" (row 05 on develop), so a person who followed develop's words did more work than this branch asks; develop was better only for an agent or person who simply asked again.
- NOT FIXED

## Scenario table

Spent-token sends (a refresh token the stand-in had already revoked reaching it) and family revocations, from `vprobe/probe.py` run against the real McpBridge of each tree with the same stand-in. "Web out" is whether a separate web-app session row was revoked. Two requests in turn unless the row says otherwise; codes in request order.

| Row | Scenario | develop sends/revoked | PR sends/revoked | develop codes | PR codes |
|---|---|---|---|---|---|
| 01 | gzip 200 after rotation | 1/1, web out | 0/0 | -32002, -32001 | -32001, -32001 |
| 02 | HTML 200 proxy, not rotated | 0/0 | 0/0 | -32001, OK | -32001, -32001 (worse) |
| 03 | 401 refused | 0/0 | 0/0 | -32001, -32001 | -32001, -32001 |
| 04 | 500 after rotation | 1/1, web out | 0/0 | -32001, -32001 | -32001, -32001 |
| 05 | proxy 502 once | 0/0 | 0/0 | -32001, OK | -32001, -32001 (worse) |
| 06 | proxy 503 once | 0/0 | 0/0 | -32001, OK | -32001, -32001 (worse) |
| 07 | proxy 429 once | 0/0 | 0/0 | -32001, OK | -32002, OK |
| 08 | ReadTimeout after rotation | 1/1, web out | 0/0 | -32002, -32001 | -32002, -32001 |
| 09 | ReadError after rotation | 1/1, web out | 0/0 | -32002, -32001 | -32002, -32001 |
| 10 | RemoteProtocolError after rotation | 1/1, web out | 0/0 | -32002, -32001 | -32002, -32001 |
| 11 | ConnectError, never sent | 0/0 | 0/0 | -32002, OK | -32002, OK |
| 12 | store fails once, recovery copy | 0/0 | 0/0 | -32001, OK | -32001, OK |
| 13 | store and recovery both fail | 1/1, web out | 0/0 | -32001, -32001 | -32001, -32001 |
| 14 | A-75-01 waiting request, renewer cancelled | 1/1, web out | 0/0 | id 4: -32001 | id 4: -32001 |
| 15 | J-75-04 request arrives after the cancel | 1/1, web out | 0/0 | id 4: -32001 | id 4: -32001 |
| 16 | A-75-07 deadline, then ask again | 1/1, web out | 0/0 | -32002, -32002 | -32002, -32002 |
| 17 | 401, then s3 login, no restart | 0/0 | 0/0 | -32001, OK | -32001, OK |
| V1 | 504 after rotation | 1/1, web out | 0/0 | -32001, -32001 | -32001, -32001 |
| V2 | ReadTimeout, never reached the app | 0/0 | 0/0 | -32002, OK | -32002, -32001 (worse) |
| V3 | RemoteProtocolError, never reached the app | 0/0 | 0/0 | -32002, OK | -32002, -32001 (worse) |
| V4 | WriteError, never reached the app | 0/0 | 0/0 | -32002, OK | -32002, -32001 (worse) |
| V5 | ProxyError, never reached the app | 0/0 | 0/0 | -32002, OK | -32002, -32001 (worse) |
| V6 | second s3 mcp on the same file, gzip after rotation (p1, p2, p1) | 2/2, web out | 1/1, web out (A-75-03, open) | p1 -32002, -32001; p2 -32001 | p1 -32001, -32001; p2 -32001 |
| V7 | second s3 mcp on the same file, proxy 503 | 0/0 | 0/0 | p1 -32001, OK; p2 OK | p1 -32001, OK; p2 OK (p1 resumed from p2's renewal) |
| V8 | s3 ask after a latch, gzip after rotation | 2/2, web out | 1/1, web out (A-75-03) | -32002, -32001 | -32001, -32001 |
| V9 | s3 ask after a latch, proxy 503 | 0/0 | 0/0 | -32001, OK | -32001, OK (resumed from s3 ask's renewal) |
| VA | renewal (gzip after rotation) racing s3 login | 0/0 | 0/0 | -32002, OK | -32001, OK |
| VB | renewal (200) racing s3 login | 0/0 | 0/0 | OK, OK | OK, OK |
| VC | proxy 503 once then healthy, four requests | 0/0 | 0/0 | -32001, OK, OK, OK | -32001 x4 (worse) |

Every row on both trees printed `leak=[]`.

## Gates

| Gate | Result at ad192fef |
|---|---|
| `ruff check` (no path) | All checks passed! (exit 0) |
| isort, gate 2 command (`isort --check-only --diff src tests services tracker alembic .claude .github`) | Skipped 2 files, exit 0 |
| `pytest tests/system_03_search_agent/adapters -m "not integration" -q` | 898 passed, 2 warnings in 43.35s |

## Verdict

HOLD, on V-75-02 (A-75-04, open) and V-75-01 (new, inside this phase's fix round), weighed in V-75-05.

- Worse than develop, plainly yes, for a person whose renewal meets a 502, 503, HTML 200, database error, or a network loss before the server saw it: develop answered their next request with no action; this branch refuses every request until they run `s3 login` in a terminal (no restart needed, verified). Nobody is signed out of the web app in those rows. How often: one renewal per about 14 minutes of active use, times the share of renewals that meet such a failure; no production rate was measured.
- Better than develop, strongly, in eleven rows where develop signed the person out of the command line and the web app at once (01, 04, 08, 09, 10, 13, 14, 15, 16, V1, and one of the two sends in V6 and V8). Those need a rotation followed by a lost reply, which the server code makes rare for a 5xx (V-75-05) and possible for a 15-second timeout, a dropped connection, a full disk, or a stop-and-ask-again during renewal.
- The owner's bar is "nothing worse than develop", not "better on balance", so this is HOLD. V-75-01 sits inside the fix round's change (A-75-02's closure), which fires the review loop's stop condition: escalate to the owner rather than another round.

Verified by the verifier's own probes: every closed finding (rows 07, 08 to 10, 12, 14 to 17, the 502 wording), the scenario table on both trees, the leak sweep with its positive control, the break-it mutation and the J-75-05 mutation, the three gates. Read only, not run: the server's commit-then-return order and the middleware list (V-75-05), the Railway health check, and every rate.
