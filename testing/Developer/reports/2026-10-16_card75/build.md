# Card 75, build report (second attempt)

Branch `fix/card75-unknown-renewal`, cut from develop bff040aa. Staged, not committed.

## Table of contents

- [What changed](#what-changed)
- [Scenario table](#scenario-table)
- [Mutation](#mutation)
- [Gates](#gates)
- [Not done or worth knowing](#not-done-or-worth-knowing)

## What changed

- Started from the closed attempt's patch (src and tests), then changed which renewal outcomes latch, per the owner's decision of 2026-10-16.
- `_RenewalClient.post` takes the refresh token back (no latch) for: any 5xx, a 429, a 200 whose content type is not `application/json`, and a request that was not fully sent (ConnectError, ConnectTimeout, PoolTimeout, ProxyError, WriteError, WriteTimeout, UnsupportedProtocol).
- The token stays counted as sent (latch, ask for `s3 login` once) when the request was fully sent and no readable answer came back (ReadTimeout, ReadError, RemoteProtocolError, a cancelled renewal) and when a 200 with the JSON content type cannot be read (the gzip row, a bad body, missing fields). A 401 still latches as in the closed attempt.
- Messages: a 5xx, 429 or HTML 200 now says "System 3 could not renew your sign-in right now (it answered ...), so this request was not sent. Your sign-in is still good; try again in a moment." with code -32002 and no `s3 login`. This also closes V-75-03 (no "expired" claim for an HTML page). The latch messages say to run `s3 login` and that the server picks up the new sign-in by itself, so no restart. The host log for an unreadable reply now says the same (closes V-75-04).
- Every finding the closed attempt's fix round closed is kept: the check at the moment of the POST, the done-callback latch, resume from the credential file, the recovery copy.

## Scenario table

Rows are the verifier's. Each is pinned by a test in `tests/system_03_search_agent/adapters/cli/test_mcp_bridge.py`. "Spent sends" is a used refresh token reaching the stand-in server (`RotatingRefresh`, which copies the server's reuse rule and family revocation).

| Row | Scenario | Develop | This branch | Spent sends here | Verdict | Test |
|---|---|---|---|---|---|---|
| 01 | gzip 200 after rotation | 1, web out | latch, ask `s3 login` | 0 | better than develop | `test_a_reply_that_cannot_be_read_asks_for_s3_login_in_the_log_too` |
| 02 | HTML 200 from a proxy | recovers | recovers, next request OK | 0 | same as develop | `test_a_clear_failure_retries_quietly...[02 ]` |
| 03 | 401 refused | -32001 twice | latch | 0 | same as develop | `test_a_refused_renewal_latches` |
| 04 | 500 after rotation | 1, web out | retry, refused (as develop) | 1 | same as develop (owner's call; the closed attempt sent 0) | `test_a_server_error_after_the_server_rotated_is_retried_as_before[500]` |
| 05 | proxy 502 once | recovers | recovers | 0 | same as develop | `...[05 ]` |
| 06 | proxy 503 once | recovers | recovers | 0 | same as develop | `...[06 ]` |
| 07 | proxy 429 once | recovers | recovers | 0 | same as develop | `...[07 ]` |
| 08 | ReadTimeout after rotation | 1, web out | latch | 0 | better than develop | `test_a_renewal_with_no_readable_answer_asks_for_s3_login_once[08]` |
| 09 | ReadError after rotation | 1, web out | latch | 0 | better than develop | `...[09]` |
| 10 | RemoteProtocolError after rotation | 1, web out | latch | 0 | better than develop | `...[10]` |
| 11 | ConnectError, never sent | recovers | recovers | 0 | same as develop | `...[11 ]` |
| 12 | store fails once, recovery copy | recovers | recovers | 0 | same as develop | existing, `test_a_renewal_saved_to_the_recovery_copy_is_picked_up_not_locked_out` |
| 13 | store and recovery both fail | 1, web out | latch | 0 | better than develop | existing, `test_a_renewal_that_could_not_be_saved_anywhere_latches` |
| 14 | waiting request, renewer cancelled | 1, web out | refused at the POST | 0 | better than develop | existing, A-75-01 test |
| 15 | request after a cancel | 1, web out | refused at the POST | 0 | better than develop | existing, J-75-04 test |
| 16 | deadline, then ask again | 1, web out | refused at the POST | 0 | better than develop | existing, A-75-07 test |
| 17 | 401, `s3 login`, no restart | recovers | recovers | 0 | same as develop | existing, `test_s3_login_revives_a_latched_bridge_without_a_restart` |
| V1 | 504 after rotation | 1, web out | retry, refused (as develop) | 1 | same as develop (owner's call) | `...rotated_is_retried_as_before[504]` |
| V2 | ReadTimeout, never reached the app | recovers | latch | 0 | latch (owner's call) | same class as 08 |
| V3 | RemoteProtocolError, never reached the app | recovers | latch | 0 | latch (owner's call) | same class as 10 |
| V4 | WriteError, never reached the app | recovers | recovers | 0 | same as develop | `...[V4 ]` |
| V5 | ProxyError, never reached the app | recovers | recovers | 0 | same as develop | `...[V5 ]` |
| VC | proxy 503 once, then healthy, four requests | OK x3 after the first | OK x3 after the first | 0 | same as develop | `test_a_proxy_503_then_healthy_answers_every_later_request` |

Rows V6 to V9, VA and VB (two processes on one credential file, racing `s3 login`) are not changed by this edit: the latch still sits in `_wired` and `_resume_from_file` is untouched. They were not re-run as probes (no stand-in for a second process in the test file); the existing latch and resume tests pass.

## Mutation

Changed the 5xx classification in `_RenewalClient.post` (`status == 429 or status >= 500` to `status == 429`, so a 5xx counts as an unknown outcome). Result: `6 failed, 87 passed` in `test_mcp_bridge.py` (rows 05, 06, VC, the two rotated-5xx pins, and the 503 message test). Restored with `cmp` against a saved copy; 93 passed again.

## Gates

| Gate | Result |
|---|---|
| `ruff check` (no path) | All checks passed! |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | Skipped 2 files, exit 0 |
| `pytest tests/system_03_search_agent/adapters -m "not integration" -q` | 910 passed, 2 warnings |

## Not done or worth knowing

- Rows 04 and V1 (a 5xx after the server already rotated) send 1 spent token, as develop does. The owner's decision says any 5xx retries quietly, so this is the accepted cost; the closed attempt sent 0 there. The tests pin it so a change shows up.
- A 5xx answer now returns code -32002 (could not reach), not -32001 as develop and the closed attempt used, because nothing about the sign-in needs action.
- Other non-200 statuses (401, 403, 404) still latch, as in the closed attempt. The decision did not name them.
- No live calls. Query 114 added; the "Cards on the board" table row for card 75 was not added (outside the fence).
