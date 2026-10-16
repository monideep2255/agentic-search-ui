# Card 75 judge report, pull request #239 at 1dba1993

One round, judge at dial position 3. Findings are appended as they are established. The judge closes nothing.

## Findings

### J-75-01: A proxy 502, 503 or 429 on renewal now needs s3 login and a restart, where develop recovered by itself

- Severity: minor (the 5xx half is the specification's named choice; the 429 half is not named by it)
- What: `_latch_if_spent` latches on every `RefreshError`, and `_refresh_and_store` raises `RefreshError` for any non-200 status. A reply from a proxy that never reached the server (the server did not rotate) therefore latches the process for good. On develop the next request renewed with the same, still live, refresh token and got an answer.
- Reproduction: judge probe `p1_matrix.py` (scratchpad, not committed). Stand-in server with reuse detection; first `/auth/refresh` answered by a "proxy" status without the server seeing it; then the proxy recovers and a second `tools/call` is sent. Pasted output:
  - PR 1dba1993: `proxy 503 (not rotated) codes=[-32001, -32001] latch=True posted=['refresh-1'] outcomes=['proxy:503'] family_revoked=0`
  - develop bce08af9: `proxy 503 (not rotated) codes=[-32001, 'OK'] latch=n/a posted=['refresh-1', 'refresh-1'] outcomes=['proxy:503', 'rotated->refresh-2'] family_revoked=0`
  - Same shape for 502 and 429 (PR `[-32001, -32001]`, develop `[-32001, 'OK']`).
- Why a person would care: the access token lives 15 minutes (`auth/tokens.py`, `_ACCESS_TOKEN_TTL_SECONDS = 15 * 60`), so an `s3 mcp` in use renews about every 14 minutes. Any renewal that lands in a deploy's gateway blip (a 502 or 503 from the hosting proxy) now ends the session in the agent app until the person runs `s3 login` and restarts the MCP server. With a 30 second blip that is roughly 30/840, about 3.6 percent of active sessions per deploy. Develop recovered from it with no action. `/auth/refresh` has no server-side 429 (`auth/router.py` rate-limits only `/auth/guest`), so a 429 can only come from a proxy, which never rotates; the owner's words "a refused renewal" do not obviously cover it. The 5xx half is the specification's stated trade (Card 75, "A 5xx reply latches too"), filed so the owner sees the measured cost.
- NOT FIXED

### J-75-02: A renewal that loses its connection after the server rotated still resends the spent token and signs the person out everywhere

- Severity: unsure (named as out of scope in the specification's "Not in this card"; filed so it stays visible, it is the same user harm the card exists to stop)
- What: `ReadTimeout`, `ReadError` and `RemoteProtocolError` on `/auth/refresh` do not latch, by design. If the server committed the rotation before the connection died, the next request posts the spent token and the server revokes the whole family.
- Reproduction: `p1_matrix.py`, PR 1dba1993: `ReadTimeout after rotation codes=[-32002, -32001] latch=True posted=['refresh-1', 'refresh-1'] outcomes=['rotated->refresh-2', '401'] family_revoked=1`; `RemoteProtocolError after rotation` identical. Develop is the same (`family_revoked=1`), so this is not worse than develop.
- Why a person would care: a mobile or flaky connection during renewal still signs them out of the command line and the web app at once, the exact symptom in the card's user words.
- NOT FIXED
### J-75-03: A renewal whose new sign-in was saved to the recovery copy now latches, where develop picked the copy up and carried on

- Severity: minor (rare: needs the credential write to fail, for example a full disk)
- What: `SessionLostError` is a `RefreshError`, so it latches. When `_write_recovery_copy` succeeded, the new refresh token is safe on disk and `load()` promotes it, so the stored token is not spent. Develop's next renewal re-read the file and recovered; the PR refuses every later request.
- Reproduction: `p1_matrix.py`, `credentials.store` made to raise `OSError(28)` once. PR 1dba1993: `store fails once (SessionLost, recovery copy) codes=[-32001, -32001] latch=True posted=['refresh-1'] outcomes=['rotated->refresh-2'] family_revoked=0`. Develop bce08af9: `codes=[-32001, 'OK'] ... posted=['refresh-1']`.
- Why a person would care: they are told to run `s3 login` and restart, though nothing was lost; the credential module's own remedy says the recovery copy "will be used automatically". A restart alone would recover. Low frequency, low cost, filed for completeness.
- NOT FIXED
### J-75-04: After a request is cancelled mid-renewal, any request that starts before that renewal ends still posts the spent token, with the latch already set

- Severity: minor (two rare events must coincide, and develop is worse; but the excluded case is wider than the specification and build report state, and it sits inside this phase's new latch)
- What: the latch is read before `refresh_locked` is called (top of `_exchange`, top of `_renew`'s lock), never at the moment of the POST. A cancelled request releases `_renew_lock` while its shielded renewal still runs. A second request then takes the lock, sees no latch, calls `refresh_locked`, waits on the file lock, re-reads the unchanged file and posts `refresh-1` after the first renewal has failed and set the latch. The specification names only "a request that was already waiting on the renewal lock when another request was cancelled". A request that ARRIVES after the cancel, while the renewal is still in flight, hits the same hole: an agent that stops a question and asks again within the renewal's duration.
- Reproduction: judge probe `p2_cancel.py` / `p2b.py` (scratchpad). Refresh answers after 0.5 s with the unreadable gzip 200 (server rotated). Request 1 sent, `notifications/cancelled` for it after 0.1 s, request 2 sent 0.05 s after the cancel ("after"), or before it ("waiting"). Instrumented to print the latch at each send. PR 1dba1993:
  ```
    POST /auth/refresh; latch at send = False
    POST /auth/refresh; latch at send = True
  after    replies=[(2, -32001), (3, -32001)] latch=True posted=['refresh-1', 'refresh-1'] outcomes=['rotated->refresh-2', '401'] family_revoked=1
  ```
  "waiting" gives the same two lines and `family_revoked=1`. Develop bce08af9: `posted=['refresh-1', 'refresh-1', 'refresh-1'] ... family_revoked=2` for both.
- Why a person would care: this is the exact outcome the card promises cannot happen ("never sends the spent token again, so I am never signed out of the command line and the web app by it"). A person who presses stop in their agent app during a renewal and asks again is signed out everywhere if that renewal's reply was unreadable or refused. The build report's "Not covered" line should say "a request that starts before a cancelled request's renewal finishes", not only one already waiting.
- NOT FIXED
### J-75-05: No test pins that a lost rotation (SessionLostError) latches; a mutant that drops it passes all 885 adapter tests and signs the person out

- Severity: minor (test gap; the shipped code is right)
- What: `_latch_if_spent` latches `SessionLostError` only because it subclasses `RefreshError`. That case matters most: the server rotated, both local writes failed, and the file still holds the spent token. No test exercises it, so a later edit narrowing the check would ship green.
- Reproduction: in the judge worktree, `_latch_if_spent`'s condition changed to `isinstance(exc, httpx.DecodingError) or type(exc) is credentials_module.RefreshError`, everything else as at 1dba1993. `pytest tests/system_03_search_agent/adapters -m "not integration" -q`: `885 passed, 2 warnings in 143.81s`. Judge probe `p4_sessionlost.py` (both `store` and the recovery write fail, then a second request):
  - PR: `codes [-32001, -32001] latch True posted ['refresh-1'] outcomes ['rotated->refresh-2'] family_revoked 0`
  - Mutant: `codes [-32001, -32001] latch True posted ['refresh-1', 'refresh-1'] outcomes ['rotated->refresh-2', '401'] family_revoked 1`
  - Source restored afterwards; `git status --short` in the judge worktree empty.
- Why a person would care: a full disk during renewal is exactly when the latch must hold; without a test, a future cleanup could reopen the sign-out-everywhere path with every check green.
- NOT FIXED
### J-75-06: A server outage during renewal is reported to the person as "your sign-in has expired or was signed out", and is now permanent for the process

- Severity: minor (wording; the action it gives matches the new behaviour)
- What: a 503 from the hosting proxy reaches `_message_from_credentials_error`'s `RefreshError` sentence, and stderr repeats the credential module's "the stored refresh token is expired, already used, or revoked". Neither says the server was unavailable. On develop the same sentence was shown once and the next request recovered; with the latch it is the last thing the session ever says.
- Reproduction: judge probe `p1b.py`, PR 1dba1993, `/auth/refresh` answered 503 by the proxy:
  ```
  msgs: ['Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.', 'Your System 3 sign-in could not be renewed earlier in this MCP server, so this request was not sent. In a terminal, run: s3 login, then restart this MCP server.']
  stderr: s3 mcp: could not renew the sign-in: POST /auth/refresh returned 503; the stored refresh token is expired, already used, or revoked. Run: s3 login
  ```
- Why a person would care: "Honesty beats polish" (decide-from-the-users-chair). A person told they were signed out, when System 3 was briefly down, may suspect their account or a stolen sign-in. Saying "System 3 could not renew your sign-in (it answered 503)" keeps the same remedy and tells the truth.
- NOT FIXED
### J-75-07: Running s3 login no longer revives a running s3 mcp; develop picked the new sign-in up from the file with no restart

- Severity: minor (the specification's stated cost, measured here so the owner sees it)
- What: after a refused renewal, the person runs `s3 login`. Develop's next renewal re-read the credential file, found a different refresh token and used it without calling the server. The latch now refuses before that re-read, so a restart of the MCP server is required too.
- Reproduction: judge probe `p5_login.py`. First renewal refused (401), then a new pair is stored as `s3 login` would, then a second request. PR 1dba1993: `codes [-32001, -32001] posted ['refresh-1'] outcomes ['401']`. Develop bce08af9: `codes [-32001, 'OK'] posted ['refresh-1'] outcomes ['401']`.
- Why a person would care: anyone who reads only "run s3 login" and skips the restart stays stuck. Every message says to restart, so this is honest, but restarting an MCP server inside an agent app is often buried in settings. The same re-read could serve as a safe exit from the latch: if the file now holds a refresh token different from the spent one, it was not spent, and using it sends nothing spent. Filed for the owner's weighing, not as a defect against the specification.
- NOT FIXED

## Checklist evidence

| Item | Result | How |
|---|---|---|
| 1. Latch set only for `DecodingError` and `RefreshError` (5xx included) | Holds | Probe `p1_matrix.py`: latch True for gzip 200, text/html 200, 401, 500, 502, 503, 429, SessionLost; False for ConnectError, missing file, insecure file. Probe `p3_senders.py`: after the latch, initialize, tools/list, resources/list, a notification and a response made 0 `/mcp/` posts and 0 refresh posts; ping answered locally |
| 1. Latch when the triggering request was cancelled | Holds for the next request after the renewal ends; fails for a request that starts before it ends (J-75-04) | Probes `p2_cancel.py`, `p2b.py` |
| 2. Code change `REMOTE_UNREACHABLE` to `SIGN_IN_NEEDED` | No other consumer | `grep` over `src`, `tests`, `docs`, `services`, `README.md`: only `test_mcp_bridge.py` and the specification |
| 3. No token in replies or stderr; `auth/` unchanged | Holds | Every probe row `leak=False` (checked old and renewed access tokens, `refresh-1` to `refresh-3`); `git diff --stat origin/develop...1dba1993 -- src/system_03_search_agent/auth` empty |
| 4. Production and AI security rules | Holds, except wording J-75-06 | Messages say what to do next; no secret in any string; no new dependency or network surface |
| 5. Break it | Red, then restored | Callback registration removed: `7 failed, 61 passed`. In-lock check removed: `1 failed, 67 passed` (`test_unreadable_reply_latches_a_request_waiting_on_the_lock`). SessionLost excluded: survives, J-75-05 |
| 6. Gates | Green | `ruff check`: `All checks passed!`; gate 2 isort: exit 0; `pytest tests/system_03_search_agent/adapters -m "not integration" -q`: `885 passed, 2 warnings in 68.42s` |
| 7. Worse than develop | Three recoverable cases now need `s3 login` and a restart | J-75-01, J-75-03, J-75-07 |

## Verdict

SHIP. Every probe where develop signed the person out everywhere (gzip 200, text/html 200, 500 after rotation, the cancel races) now posts the spent token at most once instead of two or three times, and the specification's done-when holds. Owner attention: J-75-01's 429 half is not covered by the owner's words, and J-75-04 sits inside this phase's new latch, a wider gap than the build report's "Not covered" states.

Correction to the verdict's count: counting only posts of the spent token, the PR makes 0 where develop made 1 (gzip 200, text/html 200, 500 after rotation) and 1 where develop made 2 (the two cancel races, J-75-04).
