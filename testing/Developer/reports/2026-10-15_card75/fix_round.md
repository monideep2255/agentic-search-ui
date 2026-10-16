# Card 75 fix round: the latch holds at the moment of the POST

Branch `fix/card75-renewal-latch`, base `6bf6288f`, pull request #239. Client change only: `src/system_03_search_agent/adapters/cli/mcp_bridge.py`. `auth/` and `credentials.py` are untouched. No live sign-in was used.

## Table of contents

- [Design](#design)
- [Findings](#findings)
- [Scenario table](#scenario-table)
- [Mutations](#mutations)
- [Gates](#gates)
- [Open](#open)

## Design

The lead's design of 2026-10-15, as built:

- `_RenewalClient` is the client `refresh_locked` renews through. Immediately before each POST it checks that this refresh token was never sent by this process, and refuses without sending if it was. The check sits inside the file lock, so a renewal that was started while another was in flight (its request cancelled or timed out) cannot put the same token on the wire.
- Every token sent is remembered in memory (`McpBridge._wired`, never printed). Two outcomes take the token back, because they cannot have rotated it: a connection that was never made (`ConnectError`, `ConnectTimeout`, `PoolTimeout`) and a 429.
- The latch is set in the renewal's done callback for any failure or cancellation of a renewal whose token was sent. A lost reply (`ReadTimeout`, `ReadError`, `RemoteProtocolError`), a cancelled renewal and a `SessionLostError` therefore latch.
- A latched bridge re-reads the credential file on the next request (`_resume_from_file`, through `credentials.load()`, which also promotes a recovery copy). It resumes only when the file's refresh token is not among the sent ones, and the base URL is the same. It never resumes with the spent token itself.
- A 429 gets "System 3 could not renew your sign-in right now (it answered 429) ... Try again in a moment", code `REMOTE_UNREACHABLE`, and does not latch. A 5xx gets "System 3 could not renew your sign-in (it answered 503) ...", and stderr says the status, not "expired, already used, or revoked". A `SessionLostError` gets "System 3 renewed your sign-in, but it could not be saved on this computer".
- Messages that follow a latch now say "run: s3 login. This MCP server picks up the new sign-in by itself", with no restart.

## Findings

| Finding | Status | Test (class `TestRenewalLatchFixRound`) |
|---|---|---|
| A-75-01 waiting request after the renewer is cancelled | Closed | `test_a_waiting_request_never_sends_the_spent_token_when_the_renewer_is_cancelled` |
| J-75-04 request that starts after a cancel | Closed | `test_a_request_that_arrives_after_a_cancel_never_sends_the_spent_token` |
| A-75-07 timeout, then ask again | Closed | `test_asking_again_after_a_timeout_never_sends_the_spent_token` |
| A-75-02, J-75-02 reply lost after send | Closed | `test_a_renewal_reply_lost_after_it_was_sent_latches` (three errors) |
| A-75-05, J-75-07 `s3 login` without restart | Closed | `test_s3_login_revives_a_latched_bridge_without_a_restart`, `test_a_latched_bridge_never_resumes_with_the_spent_token_itself` |
| A-75-06, J-75-03 recovery copy locked out | Closed | `test_a_renewal_saved_to_the_recovery_copy_is_picked_up_not_locked_out` |
| J-75-01, 429 half | Closed | `test_a_proxy_429_on_renewal_does_not_latch` |
| J-75-06 5xx wording | Closed | `test_the_message_after_a_server_error_says_the_renewal_failed` |
| J-75-05 SessionLost test | Closed | `test_a_renewal_that_could_not_be_saved_anywhere_latches` |
| Design: a cancelled renewal latches | Added | `test_a_renewal_cancelled_after_it_was_sent_latches` |
| A-75-03 another process reads the same file | Open | Needs `credentials.py` (a spent mark in the file under the file lock) |
| A-75-04, 5xx half | Open | The specification's safe side. A 502 or 503 still latches. The new exit is `s3 login` alone, no restart. |
| A-75-08 `-32001` is the MCP SDK's `REQUEST_TIMEOUT` | Open | Unchanged |

Each test stands on the stand-in `RotatingRefresh`, which copies `auth/router.py`'s rotation and `_revoke_family_on_reuse`, over `httpx.MockTransport`. Every test also asserts that no reply or stderr line holds an access token, `refresh-1` to `refresh-3` or `login-1`.

## Scenario table

Spent-token sends (a used refresh token reaching the server) and family revocations, from `probe.py` run against each bridge source with the same stand-in: develop `bce08af9`, PR `1dba1993`, this fix. Two requests in turn unless the row says otherwise. Reply codes are in the order of the requests.

| Scenario | develop sends/revoked | 1dba1993 sends/revoked | fix sends/revoked | fix replies |
|---|---|---|---|---|
| gzip 200 after rotation | 1/1 | 0/0 | 0/0 | -32001, -32001 |
| html 200, proxy, not rotated | 0/0 | 0/0 | 0/0 | -32001, -32001 (latched, open A-75-04) |
| 401 refused | 0/0 | 0/0 | 0/0 | -32001, -32001 |
| 500 after rotation | 1/1 | 0/0 | 0/0 | -32001, -32001 |
| proxy 502 once | 0/0 | 0/0 | 0/0 | -32001, -32001 (latched, open A-75-04) |
| proxy 503 once | 0/0 | 0/0 | 0/0 | -32001, -32001 (latched, open A-75-04) |
| proxy 429 once | 0/0 | 0/0 | 0/0 | -32002, OK (develop recovers, 1dba1993 did not) |
| ReadTimeout after rotation | 1/1 | 1/1 | 0/0 | -32002, -32001 |
| ReadError after rotation | 1/1 | 1/1 | 0/0 | -32002, -32001 |
| RemoteProtocolError after rotation | 1/1 | 1/1 | 0/0 | -32002, -32001 |
| ConnectError, never sent | 0/0 | 0/0 | 0/0 | -32002, OK |
| store fails once, recovery copy written | 0/0 | 0/0 | 0/0 | -32001, OK (1dba1993: -32001, -32001) |
| store and recovery copy both fail | 1/1 | 0/0 | 0/0 | -32001, -32001 |
| A-75-01 waiting request, renewer cancelled | 1/1 | 1/1 | 0/0 | only id 4 answered: -32001 |
| J-75-04 request arrives after the cancel | 1/1 | 1/1 | 0/0 | only id 4 answered: -32001 |
| A-75-07 timeout, then ask again | 1/1 | 1/1 | 0/0 | -32002, -32002 |
| `s3 login`, no restart | 0/0 | 0/0 | 0/0 | -32001, OK (1dba1993: -32001, -32001) |

All 17 rows on all three sources: no token value in any reply or stderr (`leak=False`). The ConnectError row first read 1/1 on every source because the probe rotated before raising; the row above is the corrected probe (the error is raised before the server sees anything).

## Mutations

Each applied alone to `mcp_bridge.py`, the class run, then the file restored (`git diff` shows only the intended change).

| Mutation | Tests that turn red |
|---|---|
| `_RenewalClient.post`: the sent-token check replaced by `False` | A-75-01, J-75-04, A-75-07 tests |
| `_RenewalClient.post`: take the token back on every `httpx.HTTPError` | The three lost-reply cases |
| `_resume_from_file` returns `False` at once | `s3 login` test, recovery copy test |
| `_resume_from_file`: the "token among the sent ones" check replaced by `False` | Never-resumes-with-the-spent-token test, SessionLost-anywhere test, cancelled-renewal test |
| `_latch_if_spent` returns early for `SessionLostError` | SessionLost-anywhere test |
| `_latch_if_spent` returns early for a cancelled task | Cancelled-renewal test |
| `_RenewalClient.post`: the 429 take-back replaced by `False` | 429 test |
| `_renew`: the status branch for 429 and 5xx never matches | 5xx wording test, 429 test |

Two protections overlap for a sequential second request: the latch (top of `_exchange`) and the check at the POST. A test that removes only one of them stays green for the sequential cases, so the sequential tests send a request whose observable differs (a request reaching `/mcp/` after the latch), and the concurrent tests, where the latch is not yet set, pin the POST check.

## Gates

| Gate | Result |
|---|---|
| `ruff check` (no path) | All checks passed! |
| isort, gate 2 command (`isort --check-only --diff src tests services tracker alembic .claude .github`) | exit 0 |
| `pytest tests/system_03_search_agent/adapters -m "not integration" -q` | 898 passed, 2 warnings in 104.82s |
| `test_mcp_bridge.py` alone | 81 passed (68 before, 13 new test cases) |

## Open

- A-75-03: the latch lives in one process. A second `s3 mcp` or `s3 ask` on the same file still sends the spent token. Closing it needs a spent mark in the credential file under the file lock, which is `credentials.py`.
- A-75-04, 5xx half: a proxy 502, 503 or an HTML 200 still latches, because the bridge cannot tell whether the server rotated. The cost is now `s3 login` alone, with no restart. The wording no longer says the sign-in expired.
- A-75-08: `SIGN_IN_NEEDED` is `-32001`, the MCP SDK's `REQUEST_TIMEOUT`. Not touched.
- The re-read reads the credential file without the file lock (`credentials.load()`, which can promote a recovery copy). A concurrent writer in another process is atomic (`os.replace`), so a torn read is not possible, but the promotion is not serialized with another process's refresh.
