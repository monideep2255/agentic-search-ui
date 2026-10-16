# Judge, card 75 (PR #252), round 1

Subject: `fix/card75-unknown-renewal` at 2306eaec against develop bff040aa. Probes run the real McpBridge from each tree against a stand-in server (the closed verifier's approach, rebuilt with extra rows). Findings are J-75B-NN, written as each was established.

## Table of contents

- [Findings](#findings)
- [Scenario table](#scenario-table)
- [Checklist](#checklist)
- [Verified by my own probes versus only read](#verified-by-my-own-probes-versus-only-read)
- [Verdict](#verdict)

## Findings

### J-75B-01: Any 4xx or 3xx renewal answer other than 429 latches, though each is a definite answer that rotated nothing; develop recovered on the next request
- Severity: major against the bar (worse than develop, not a truly unknown outcome). Inside this phase's change (`_RenewalClient.post` keeps every status that is not 200-JSON-content, 429 or 5xx counted as sent).
- What: a 400, 403, 404, 408, 422 or 301 from a proxy or the app, with no rotation, refuses every later request until `s3 login`. The server answered, so the outcome is known; the owner's decision latches only "a truly unknown outcome".
- Reproduction: judge probe (verifier's stand-in approach, own rows X2 to X7), first `/auth/refresh` answered with the status and no rotation, then healthy, two `tools/call`:
  ```
  develop bff040aa: X2 403 codes=[(10,-32001),(11,'OK')]  X3 404 same  X4 408 same  X5 400 same  X6 422 same  X7 301 same   spent=0 in all
  PR 2306eaec:      X2 403 codes=[(10,-32001),(11,-32001)] X3 404 same X4 408 same X5 400 same X6 422 same X7 301 same   spent=0 in all, mcp=0
  ```
- Why it matters: a person whose renewal meets a WAF challenge (403), a route missing during a bad deploy (404), a proxy request timeout (408) or a redirect (301) is told to run `s3 login`, where develop answered their next request. The only 4xx the app's refresh route itself emits is 401 (and 422 for a malformed body, which this client never sends), so a non-401 4xx comes from a proxy, and a proxy answer means the app never saw the token. Rate: rare on the current host, not measured.
- NOT FIXED

### J-75B-02: After a 5xx that followed a rotation (rows 04, V1, and a proxy 502 after the app committed), the new words say "Your sign-in is still good; try again", and following them signs the person out of the web app; develop's words (run s3 login) avoided it
- Severity: major against the owner's sentence "nobody is ever signed out of the web app by surprise". Inside this phase's change (the new 5xx message).
- What: the probe's spent-send count for rows 04 and V1 is the same as develop (1 send, family revoked) when the agent simply asks again. But the reply the person reads changed: develop said "Your System 3 sign-in has expired or was signed out ... run: s3 login, then restart this MCP server"; the branch says the sign-in "is still good; try again in a moment". A person who does exactly what each tree says: on develop runs `s3 login`, so no spent send; on the branch asks again, so the spent token goes out and the web session is revoked.
- Reproduction: judge probe, "follow the words" mode (between requests, run `s3 login` if the last error names it, otherwise ask again):
  ```
  develop: F04 500 after rotation  spent=0 famrev=0 web_out=False codes=[(10,-32001),(11,'OK')] did=['login']
           FV1 504 after rotation  spent=0 famrev=0 web_out=False did=['login']
           FX1 502 after rotation  spent=0 famrev=0 web_out=False did=['login']
  PR:      F04 500 after rotation  spent=1 famrev=1 web_out=True codes=[(10,-32002),(11,-32001)] did=[]
           FV1 504 after rotation  spent=1 famrev=1 web_out=True did=[]
           FX1 502 after rotation  spent=1 famrev=1 web_out=True did=[]
  ```
- Why it matters: the owner accepted "clear server errors retry quietly as today", so the resend itself matches the decision as written. But "as today" did not include telling the person their sign-in is still good, which is a confident claim the bridge cannot know after a 5xx. How reachable: see J-75B-03. If rare, the cost is small; it is still a statement that is wrong in exactly the case that signs someone out.
- NOT FIXED
### J-75B-03: How reachable rows 04 and V1 are on this server (read, not run)
- Severity: unsure (no production logs read; Railway's kill timing not verified).
- What, from the code at 2306eaec:
  - `auth/router.py` `refresh` is a sync route. Its last database step is `session.commit()`; after it only `response.headers.update` and `return TokenResponse(...)` of two strings run. Nothing there can raise. `get_session`'s teardown is `session.close()` after a commit. No middleware wraps `/auth/refresh` with a timeout (`RequestTimeoutMiddleware` gates itself to `/graphql`; the others are CORS and `ProxySchemeMiddleware`). So the app itself cannot produce row 04 (a 500 after it rotated) in practice. Every app 500 on this route comes before the commit (database down, pool exhausted, as the comment at router line 164 records happened), rolls back, and is now retried safely: an improvement.
  - Row V1 (a 504 after rotation) needs a proxy whose timeout is shorter than the client's `REFRESH_TIMEOUT_SECONDS = 15.0`. Railway's edge timeout is minutes, so a slow app reaches this client as a `ReadTimeout` (row 08, latched, no spent send) first. Not reachable as deployed.
  - The reachable variant is my row X1: the container dies between the commit and the response write (an out-of-memory kill, or a deploy that kills the old container before an in-flight refresh finishes), and the edge answers 502. Uvicorn's graceful shutdown waits for in-flight requests on SIGTERM; whether Railway allows that before SIGKILL was not verified. Rare, but it is the one path where the branch resends a spent token.
- Contradiction with "nobody is ever signed out of the web app by surprise": yes, in letter, on that rare path (X1, and 04 and V1 if a different proxy were put in front). The owner's same sentence orders "clear server errors (502, 503) retry quietly as today", and the two halves cannot both hold for a 502 after rotation, so the owner chose. The branch's tests pin the resend. What is not owner-chosen is the wording in J-75B-02.
- NOT FIXED

### J-75B-04: The new `_refresh_not_json` flag goes stale across overlapping renewals, so a refused renewal can be told "Your sign-in is still good; try again" while the bridge has latched
- Severity: minor (wording; no spent send, the latch holds). Inside this phase's change: `_refresh_not_json` is new in this attempt (absent from the closed attempt's patch), set by `_RenewalClient.post` and reset only at the start of `_renew`, never by a later POST.
- What: renewal A outlives its request's deadline and later gets a proxy HTML 200; request B, already inside `_renew` (flag reset before A finished), sends its own renewal and gets a 401. B's handler reads the flag A set and takes the "retry quietly" branch.
- Reproduction: judge probe `stale.py` at 2306eaec, deadline 0.2 s for request 3, first `/auth/refresh` answers HTML 200 after 0.5 s, second answers 401:
  ```
  posts 2 codes [(3, -32002), (4, -32002), (5, -32001)] latched True
   msg (id 4): System 3 could not renew your sign-in right now (it answered a page that is not a sign-in reply), so this request was not sent. Your sign-in is still good; try again in a moment.
   msg (id 5): Your System 3 sign-in could not be renewed earlier in this MCP server, so this request was not sent. In a terminal, run: s3 login. ...
   err: could not renew the sign-in: POST /auth/refresh answered with a page that is not JSON (a proxy or maintenance page)
  ```
  The 401 never appears in stderr. Develop has no such flag (develop says "expired or was signed out" for both).
- Why it matters: "a confident wrong record is worse than a missing one": the person is told their sign-in is good when it was refused, then the next try asks for `s3 login`. Rare (needs a deadline expiry during a renewal and a proxy page). Reset the flag in `post` per response, or carry it on the task.
- NOT FIXED

### J-75B-05: No test pins how a 403, 404, 408 or 3xx renewal answer is handled; a mutant that retries them quietly keeps all 93 bridge tests green
- Severity: minor (test gap), relevant to J-75B-01 whichever way it is decided.
- Reproduction: `_RenewalClient.post`'s `elif status == 429 or status >= 500:` replaced by `elif status != 401 and status >= 300:`. `test_mcp_bridge.py`: `93 passed`. Judge probe on the mutant: X2 403 and X4 408 `codes=[(10,-32001),(11,'OK')]` (develop's behaviour), row 03 (401) still latched. Restored with `cp` and `cmp`; `git status --short` empty.
- Why it matters: the build report says 401, 403 and 404 "still latch"; nothing holds that, nor its opposite, so a later edit can flip it silently.
- NOT FIXED

## Scenario table

Judge probe run on both trees, same stand-in (rotation plus family revocation on reuse). Sends/revoked counts spent refresh tokens reaching the stand-in and family revocations; "web out" is a separate web-app session revoked. Two requests unless stated. "Follow" is the same row with the person doing what the first reply says (run `s3 login` if it names it, else ask again).

| Row | Scenario | Develop | Branch | Verdict |
|---|---|---|---|---|
| 01 | gzip 200 after rotation | 1/1 web out; -32002, -32001 | 0/0; -32001, -32001 (latch) | better |
| 02 | HTML 200, not rotated | 0/0; -32001, OK | 0/0; -32002, OK | same, better words |
| 03 | 401 | 0/0; latched both | 0/0; latched both | same |
| 04 | 500 after rotation | 1/1 web out | 1/1 web out | same; follow: develop 0/0, branch 1/1 (J-75B-02) |
| 05, 06, 07 | proxy 502, 503, 429 once | 0/0; -32001, OK | 0/0; -32002, OK | same, better words |
| 08, 09, 10 | read timeout, read error, protocol error after rotation | 1/1 web out | 0/0; latch | better |
| 11 | ConnectError | 0/0; -32002, OK | 0/0; -32002, OK | same |
| 12 | store fails, recovery copy | 0/0; -32001, OK | 0/0; -32001, OK | same |
| 13 | store and recovery fail | 1/1 web out | 0/0; latch | better |
| 14, 15, 16 | cancel and deadline races | 1/1 web out each | 0/0 each | better |
| 17 | 401, s3 login, no restart | -32001, OK | -32001, OK | same |
| V1 | 504 after rotation | 1/1 web out | 1/1 web out | same; follow: develop 0/0, branch 1/1 (J-75B-02) |
| V2, V3 | read timeout, protocol error, never reached the app | 0/0; -32002, OK | 0/0; -32002, -32001 (latch) | latch on a truly unknown outcome, owner accepted |
| V4, V5 | write error, proxy error | 0/0; -32002, OK | 0/0; -32002, OK | same |
| V6 | second s3 mcp, gzip after rotation | 2/2 web out | 1/1 web out | better (A-75-03 still open) |
| V7 | second s3 mcp, proxy 503 | 0/0; p1 -32001, OK; p2 OK | 0/0; p1 -32002, OK; p2 OK | same |
| V8 | s3 ask after latch, gzip after rotation | 2/2 web out | 1/1 web out | better (A-75-03) |
| V9 | s3 ask after latch, proxy 503 | 0/0; -32001, OK | 0/0; -32002, OK | same |
| VA | renewal (gzip) racing s3 login | 0/0; -32002, OK | 0/0; -32001, OK | same |
| VB | renewal (200) racing s3 login | 0/0; OK, OK | 0/0; OK, OK | same |
| VC | proxy 503 then healthy, four requests | -32001, OK x3 | -32002, OK x3 | same |
| X1 (new) | proxy 502 after the app rotated | 1/1 web out | 1/1 web out | same; follow: develop 0/0, branch 1/1 (J-75B-02) |
| X2 to X7 (new) | 403, 404, 408, 400, 422, 301, not rotated | 0/0; -32001, OK | 0/0; -32001, -32001 (latch) | worse (J-75B-01) |
| X8 (new) | 500 JSON, not rotated | 0/0; -32001, OK | 0/0; -32002, OK | same |

Every row on both trees printed `leak=[]`.

## Checklist

| Item | Result |
|---|---|
| 1. Verifier's table on both trees, including V6 to V9, VA, VB | Reproduced every row of the closed verifier's table on develop. On the branch every row is same or better, and V2, V3 latch on a truly unknown outcome. V6 to V9, VA, VB run: same or better. Worse: the new rows X2 to X7 (J-75B-01). |
| 2. Rows 04 and V1 | Resend one spent token, as develop. Reachability (J-75B-03): 04 is close to impossible from the app code; V1 not reachable behind Railway's edge with a 15 s client timeout; the reachable twin is a 502 after the container dies mid-reply (X1). It does contradict "nobody is ever signed out by surprise" in letter, on a rare path the owner's own "502 retries quietly" chose. The new words make it worse for a person who follows them (J-75B-02). |
| 3. 403 and 404 latch | Worse than develop on every path where they come from a proxy, WAF or broken deploy; the app's refresh route only answers 401 (J-75B-01). Unpinned by tests (J-75B-05). |
| 4. Fix round's closures | Still closed by probe: A-75-01 (14), J-75-04 (15), A-75-07 (16), A-75-02 and J-75-02 (08 to 10), A-75-05 and J-75-07 (17), A-75-06 and J-75-03 (12), J-75-01's 429 (07), J-75-06 (stderr "returned 502"). All eleven fix-round tests still exist by name and pass. V-75-03 (HTML 200 no longer "expired") and V-75-04 (log no longer says restart) are closed by probe. A-75-03 still open, as before. |
| 5. Secrets, tokens, paths | Leak sweep (the verifier's echo replies plus my 500, 503 JSON, 403 and 408 echoes; root logging at DEBUG and warnings captured): `hits=[]` on both trees; positive control `['refresh-1']`. New messages interpolate only a status number or an exception class name. No path in any reply or stderr line. Every latch message says "In a terminal, run: s3 login". The 403/408 stderr line still says the token "is expired, already used, or revoked", false for those (part of J-75B-01). |
| 6. Gates | `ruff check`: All checks passed (exit 0). isort gate-2 command: exit 0, Skipped 2 files. `pytest tests/system_03_search_agent/adapters -m "not integration" -q`: 910 passed, 2 warnings. Mutation: `httpx.ProxyError` and `httpx.WriteError` removed from `_NEVER_SENT`: 2 failed, 91 passed (V4, V5), probe rows V4, V5 latched; restored with `cp`, `cmp` equal, `git status --short` empty. |

## Verified by my own probes versus only read

- Run: every scenario row on both trees, the follow-the-words rows, the X rows, the stale-flag race, the leak sweep with its control, both mutations, the three gates.
- Read only: the server's commit-then-return order, the middleware list, `get_session`'s teardown, the reachability of 04, V1 and X1 on Railway (edge timeout and kill timing not verified), and every rate.

## Verdict

FIX FIRST. Worse than develop, outside the owner's accepted latch:

- J-75B-01: a 400, 403, 404, 408, 422 or 3xx renewal answer, all definite answers that rotated nothing, now latches and asks for `s3 login`; develop answered the next request. Carried from the closed attempt's "every non-200 except 429 latches", kept deliberately by this build; not a regression inside a fix round.
- J-75B-02: after a 5xx that followed a rotation, the new reply says "Your sign-in is still good; try again", and doing so signs the person out of the web app; develop's reply led them to `s3 login`, which avoided it. Rare (J-75B-03), but it is a confident wrong statement in the one case that signs someone out. Saying the outcome without claiming the sign-in is good would keep the owner's quiet retry and lose the wrong claim.

Minor, fix while there: J-75B-04 (stale flag, new code in this attempt), J-75B-05 (pin the 4xx decision).
