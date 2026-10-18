# Adversary, card 75 second attempt, PR 252

Started 2026-10-16. Branch at 2306eaec, develop at bff040aa. Probes are in the `probes/` folder beside this report; no live calls.

## Findings

### A-75B-01: a proxy's one-off 403, 404, 408, 421 or 307 on renewal now locks the MCP server until s3 login; develop answered the very next request
- Severity: major. Worse than develop, and against the owner's words ("only a truly unknown outcome asks the person to run s3 login once"). The build report names it ("Other non-200 statuses (401, 403, 404) still latch ... The decision did not name them") but the decision's own rule covers them: they are clear answers, not unknown outcomes.
- What: `_RenewalClient.post` takes the token back only for a 429, a 5xx and a non-JSON 200. Every other non-200 status keeps the token counted as sent, so `_latch_if_spent` latches. The app's `/auth/refresh` (`auth/router.py`, `refresh`) can only answer 200, 401, 422 (validation) or a 5xx. A 403, 404, 408, 421 or 3xx therefore comes from something in front of the app that never passed the request on, so the token cannot have been rotated. These are "known not rotated" outcomes that the branch treats as unknown.
- Reproduction: my own harness (`probes/probe.py`, `probes/p1.py`), with an auth stand-in copying the router's rotation and reuse rule. A proxy answers the first renewal once, then the path is healthy. Three tool calls in a row:

| Proxy answer, once | develop replies 1, 2, 3 | branch replies 1, 2, 3 | Tokens sent (dev / branch) | Revoked |
|---|---|---|---|---|
| 403 text/html | -32001, OK, OK | -32001, -32001 latch, -32001 latch | 2 / 1 | 0 / 0 |
| 404 text/html ("Application not found") | -32001, OK, OK | -32001, latch, latch | 2 / 1 | 0 / 0 |
| 404 application/json | -32001, OK, OK | -32001, latch, latch | 2 / 1 | 0 / 0 |
| 408 (proxy request timeout) | -32001, OK, OK | -32001, latch, latch | 2 / 1 | 0 / 0 |
| 421 (misdirected request) | -32001, OK, OK | -32001, latch, latch | 2 / 1 | 0 / 0 |
| 307 redirect | -32001, OK, OK | -32001, latch, latch | 2 / 1 | 0 / 0 |

  On the branch, reply 1 says "Your System 3 sign-in has expired or was signed out", which is false for a proxy answer (the V-75-03 wording class, now on these statuses), and replies 2 and 3 are `_SIGN_IN_SPENT`.
- Why it matters: a person whose renewal hits a WAF challenge page, a deploy-time 404 or a load balancer 408 must now leave the agent and run `s3 login`; develop recovered with no command. No sign-out risk is removed in exchange, because these statuses never reach the app. The fix is a classification change (take the token back for any status the app cannot send), not a design change.
- NOT FIXED

### A-75B-02: a proxy's 200 with a JSON content type and an empty body latches; develop recovered on the next request
- Severity: minor, unsure. Worse than develop on recovery. Defensible as "unknown" only if the app could send it, and I believe it cannot.
- What: an empty-body 200 is classified as an unreadable JSON reply, so the token stays counted as sent and the bridge asks for `s3 login`. The app's `/auth/refresh` 200 is a `TokenResponse` model, always with both fields. httpx reads the whole body before `_refresh_and_store` parses it, so a body cut off mid-flight raises a read error instead of arriving as an empty 200. An empty 200 is therefore a complete answer from something that is not the app.
- Reproduction: `probes/p1.py`, case "200 json empty body proxy" (`200`, `content-type: application/json`, body empty, no rotation). Develop: -32001, OK, OK, with 2 sends and 0 revoked. Branch: -32001 "Could not read System 3's sign-in renewal reply. The server may have rotated your sign-in ...", then latch, latch, with 1 send and 0 revoked.
- Why it matters: it costs the person an `s3 login` for a proxy fault that develop rode out. Gzip-corrupted bodies (row 01) are a different case and are rightly unknown.
- NOT FIXED

### A-75B-03: after a 5xx or HTML 200 that followed a committed rotation, the bridge tells the person "Your sign-in is still good", and the very next try signs them out everywhere
- Severity: minor (wording). Inside this phase's fix: the message is new on this branch. The spend itself is the owner's accepted cost and matches develop (develop spends 2, the branch 1).
- What: the clear-error branch in `_renew` asserts "Your sign-in is still good; try again in a moment." for any 5xx, 429 or non-JSON 200. The bridge cannot know that. When the app rotated before the error, following the advice replays the spent token and the server revokes the whole family.
- Reproduction: `probes/p1.py`, cases "500 AFTER rotation", "504 AFTER rotation" and "html 200 AFTER rotation" on the branch. Reply 1: -32002 "System 3 could not renew your sign-in right now (it answered 504), so this request was not sent. Your sign-in is still good; try again in a moment." Reply 2: the server sees `refresh-1` again, `revoked 1`, and the reply is -32001 "Your System 3 sign-in has expired or was signed out". Develop's reply 1 for the same input made no such promise.
- Why it matters: in exactly the case where the owner accepted a sign-out, the product tells the person the opposite one message earlier. "Honesty beats polish": "try again in a moment" without the "still good" claim would be true in every case.
- NOT FIXED

### A-75B-04: the owner named 502 and 503 as the clear errors; the branch retries every 5xx, including 504 and 500, the two most likely to follow a committed rotation
- Severity: unsure (scope question for the owner, not worse than develop).
- What: the decision reads "Clear server errors (502, 503) retry quietly as today; only a truly unknown outcome asks". The branch implements `status == 429 or status >= 500`. A 504 means a gateway stopped waiting for an app that had the request, and that app may still have committed the rotation. That is a truly unknown outcome by the owner's own test. A 500 from the app can also follow `session.commit()` (any failure after the commit line in `refresh`, or in middleware on the way out).
- Reproduction: `probes/p1.py`, "504 AFTER rotation" and "500 AFTER rotation": branch sends `refresh-1` twice and the family is revoked once (develop: three sends, revoked twice). The build report rows 04 and V1 record the same and label them "owner's call". The owner's words name 502 and 503 only.
- Why it matters: if the owner meant 502 and 503 literally, 504 (and arguably 500) should latch. This is cheap to ask and changes one comparison. Not a regression against develop.
- NOT FIXED

### A-75B-05: after s3 login against a differently written server address, the latch never clears, though the message promises "picks up the new sign-in by itself"
- Severity: minor. Worse than develop in this narrow path, and the message is wrong there. Inside this phase's fix (`_resume_from_file`).
- What: `_resume_from_file` resumes only when `current.base_url == self._creds.base_url`, compared as strings. `s3 login` stores `str(http_client.base_url)`, built from `--base-url`, `S3_BASE_URL` or the default as typed, so `https://host` and `https://host/` are stored differently (checked: httpx keeps the slash). If the person signs in again with the address written another way, from a shell with a different `S3_BASE_URL`, or against another server, the latched bridge refuses every request until it is restarted. Every refusal says "This MCP server picks up the new sign-in by itself."
- Reproduction: `probes/p2.py`. The bridge latches on a ReadTimeout after rotation. The new sign-in is then stored with `login-1`:

| After the latch | develop, requests 2 and 3 | branch, requests 2 and 3 |
|---|---|---|
| `s3 login`, same address | OK, OK | OK, OK |
| `s3 login`, address with a trailing slash | OK, OK | `_SIGN_IN_SPENT`, `_SIGN_IN_SPENT`; still latched |
| `s3 login`, another host | OK, OK (sent to the old host) | `_SIGN_IN_SPENT`, `_SIGN_IN_SPENT`; still latched |

- Why it matters: the person did exactly what the message said and is still stuck, with no hint that a restart is needed. The guard has a real purpose for another host (do not silently move the bridge to a different server), so the defect is the message plus the string comparison, not the guard. Either the message names the restart in that case, or the comparison normalises the address.
- NOT FIXED

### A-75B-06: an abandoned renewal's late answer overwrites the next renewal's classification, so a latching outcome is reported as "Your sign-in is still good; try again"
- Severity: minor (message and log are wrong; no spent send). Inside this phase's fix.
- What: `_refresh_status` and `_refresh_not_json` are fields on the bridge. `_renew` resets them before it starts a renewal, but a renewal whose waiting request was cancelled (or hit `REQUEST_DEADLINE_SECONDS`) keeps running, shielded, and its `_RenewalClient.post` writes them when its answer arrives. `_refresh_not_json` is only ever set to True by `post`, never back to False. The sequence is: renewal N1 is in flight; its request is cancelled; the next request resets the fields and starts N2, which waits on the file lock; N1's HTML 200 arrives and sets `_refresh_not_json = True`; N2 then gets a 401 or an unreadable JSON 200. `_renew` reads the stale flag and takes the "clear error" branch. Meanwhile `_latch_if_spent` (which reads `_wired`, correctly) latches.
- Reproduction: `probes/p4.py`. Request 3 renews, the proxy answers HTML 200 after 0.3 s, request 3 is cancelled at 0.05 s, and request 4 arrives at 0.1 s.
  - N2 answered 401: branch reply 4 is -32002 "System 3 could not renew your sign-in right now (it answered a page that is not a sign-in reply), so this request was not sent. Your sign-in is still good; try again in a moment." The host log says "answered with a page that is not JSON". The bridge is latched, and reply 5 is `_SIGN_IN_SPENT`.
  - N2 answered a JSON 200 without the token fields, after the app rotated: same reply 4 and log; latched; reply 5 `_SIGN_IN_SPENT`. The correct reply was `_UNREADABLE_RENEWAL`.
- Why it matters: the person is told their sign-in is fine and to try again, and the try fails with "run s3 login". The host log points the operator at a proxy page that did not cause this failure. No token is resent: `_wired` guards correctly. Fix direction: the fields belong to one renewal (return them from the client instance, or reset `_refresh_not_json` in `post`), not to the bridge.
- NOT FIXED

### A-75B-07: the build's row V4 ("WriteError, never reached the app: recovers") holds only in the mock; over a real HTTP/1.1 connection a dropped request surfaces as ReadError and latches
- Severity: unsure (evidence gap, within the accepted latch). This is not a new regression beyond the owner's call on V2 and V3. It means the latch fires more often than the scenario table suggests.
- What: httpcore 1.x (`_async/http11.py`, `handle_async_request`) catches `WriteError` while writing the request and goes on to read the response ("Servers can sometimes close the request pre-emptively"). A front end that drops the connection therefore never raises `WriteError` to `_RenewalClient.post`. It raises `ReadError`, which keeps the token counted as sent. The `httpx.WriteError` entry in `_NEVER_SENT` is dead code for HTTP/1.1, and the V4 test exercises a `MockTransport` raising it directly.
- Reproduction: `probes/p7.py`, real loopback sockets, no live calls. In each mode a listener accepts, then drops the connection before any app could see the request. 20 POSTs per mode:
  - closes at once without reading: `ReadError` 20 of 20
  - resets at once: `ReadError` 19, `ConnectError` 1
  - reads 10 bytes, then resets: `ReadError` 20 of 20

  On the branch, `ReadError` latches (`probes/p6.py`, "never reached app ReadError": latched, reply 2 is -32001). Develop recovers on the next request.
- Why it matters: an edge that drops idle or draining connections during a deploy costs an `s3 login` every time, never "recovers" as V4 says. The client cannot tell this apart from a lost reply, so it is the owner's accepted cost. The owner should know it is the common shape of a dropped connection, not a rare one.
- NOT FIXED

### A-75B-08: while latched, every request reads the credential file outside the refresh lock, and that read can promote a recovery copy over the file
- Severity: unsure (a race I could not make fire; filed because it is new code on a credential path).
- What: `_refuse_if_spent` calls `credentials_module.load()` on every request while latched. `load()` runs `_promote_recovery_copy_if_present()`, which calls `store()`. Develop's bridge reads the file only inside `refresh_locked`, under `_CredentialFileLock`. If a recovery copy exists while another `s3` process holds the lock and is promoting and then rotating, this process can write the older promoted token after the other one stored the newer one. The next renewal would then send a spent token.
- Reproduction: not reproduced. The window is one read-then-write against another process's network round trip. `main.py`'s `_resolve_base_url_for_main` already calls `load()` unlocked at the start of every `s3` command, so the class exists on develop. The branch only raises its frequency (once per refused request).
- Why it matters: low likelihood, and the cost is the family revocation this card exists to prevent. A read that skips promotion, or that takes the lock, removes it.
- NOT FIXED

## Checked, not a finding

Every item below was run with my own probes (the `probes/` folder beside this report). The stand-in copies the router's rotation rule and its family revocation on reuse.

| Hunt item | Result on the branch | Develop |
|---|---|---|
| Spent token resent after an unknown outcome (ReadTimeout, ReadError, RemoteProtocolError, gzip 200 after rotation) | 1 send, 0 revoked, latched | 2 sends, revoked |
| Request cancelled mid-renewal, renewal ends 503 or HTML 200 with no rotation | next request retries and answers OK, 0 revoked (`p3.py`) | same |
| Request cancelled mid-renewal, renewal outcome unknown | refused at the POST, 0 revoked | revoked |
| 5xx or HTML 200 after a committed rotation | 2 sends, revoked once (accepted; see A-75B-03, A-75B-04) | 3 sends, revoked twice |
| Second process on the same credential file after a latch | that process sends the old token, revoked once (A-75-03's class, not worse) | revoked three times |
| 429 with Retry-After, 502, 503 once | OK on the next request, no command | same |
| ConnectError, ConnectTimeout, PoolTimeout, ProxyError, WriteTimeout (mock) | OK on the next request | same |
| Latch, then `s3 login` with the same address | OK on the next request, no restart | OK |
| Notification while latched | no reply line written (correct) | same |
| ping while latched | answered locally | same |
| 200 refused requests while latched | 0.03 s in total, no hang, no network call | 2.3 s, 200 renewals |
| Token or JWT in any reply or stderr | none (searched for the refresh tokens and the `eyJ` JWT prefix) | none |
| Local path in any branch-new message | none. The SessionLostError reply no longer quotes the credential path (better than develop) | quoted it in the log |
| Wrong command | every latch reply says `s3 login`, which is the command's real name | n/a |

## Verdict

FAIL. Worse than develop, beyond the accepted latch:

- A-75B-01 (major): a single 403, 404, 408, 421 or 3xx from whatever sits in front of the app on `/auth/refresh` now locks the MCP server until `s3 login`. Develop answered the next request. The app cannot send these statuses on that route, so the token is known not to be rotated. This breaks the owner's "only a truly unknown outcome asks". It is a one-line classification gap in `_RenewalClient.post`, the new code of this branch.
- A-75B-02 (minor, unsure): an empty JSON 200 from a proxy latches; develop recovered.
- A-75B-05 (minor): after `s3 login` with the server address written differently, the latch never clears, and the message promises it will.

No path sends a spent refresh token more often than develop: every revocation count on the branch is at or below develop's. The owner's accepted cost (one spend after a 5xx that followed a rotation) behaves as stated. A-75B-04 asks whether it should cover 504 and 500 as well as the named 502 and 503.

Stop condition: A-75B-01, A-75B-03, A-75B-05 and A-75B-06 sit inside this phase's fix (`_RenewalClient`, the new clear-error message, `_resume_from_file`, the per-bridge renewal fields). By the review loop's rule this escalates to the product owner rather than another round.

Verified with my own probes: A-75B-01, 02, 03, 05, 06 and 07, and every row of "Checked, not a finding". The base address stored by `s3 login` was checked by running httpx's URL normalisation.

Only read, not run: A-75B-04's claim about what the owner meant (it is a reading of the decision's words), the claim that `/auth/refresh` can only answer 200, 401, 422 or 5xx (read from `auth/router.py` and the app's middleware list), and A-75B-08 (the race was reasoned, not reproduced). Two-process rows V6 to V9, VA and VB from the build report were not re-run beyond the single second-process probe above.
