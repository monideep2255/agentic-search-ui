# Card 75 build: a renewal that cannot be read signs the person out everywhere

Branch `fix/card75-renewal-latch`, base `7626fe85`. Change is in the client alone: `src/system_03_search_agent/adapters/cli/mcp_bridge.py`. No server file changed.

## Table of contents

- [What changed](#what-changed)
- [Decisions](#decisions)
- [Tests and their mutations](#tests-and-their-mutations)
- [Not covered](#not-covered)

## What changed

- `_SIGN_IN_SPENT` constant below `_SIGN_IN_AGAIN`.
- `McpBridge._sign_in_spent`, false at start.
- `_exchange` raises `SIGN_IN_NEEDED` with `_SIGN_IN_SPENT` first thing when the latch is set.
- `_renew` raises the same first thing inside `self._renew_lock`, so a request already waiting on the lock stops there.
- `_latch_if_spent`, a done callback registered on the renewal task after `_retrieve_quietly` and before `asyncio.shield`. It sets the latch for `httpx.DecodingError` and `credentials_module.RefreshError`, and leaves a cancelled task, a success and every other failure alone.
- The `DecodingError` branch now answers `SIGN_IN_NEEDED` (sentence and stderr line unchanged).

## Decisions

- Owner decision of 2026-10-06: the latch fires on an unreadable reply and on a refused renewal.
- Five-xx choice: a 5xx reply to the renewal latches too. `_refresh_and_store` raises `RefreshError` for any reply that is not 200, and the bridge cannot tell whether the server rotated the token before the proxy answered. Latching is the safe side of that doubt. The cost is a restart of the MCP server after `s3 login`, which every message already says.
- The latch is set only in the done callback, not in the `except` branches, because the shielded renewal outlives a cancelled request.
- Network failures (`httpx.HTTPError` other than `DecodingError`), a missing credential file and the local credential errors keep today's behaviour and do not latch.

## Tests and their mutations

All in `tests/system_03_search_agent/adapters/cli/test_mcp_bridge.py`, class `TestRenewal`. Each mutation was applied alone, the file run, then restored.

| Test | Mutation that turns it red |
|---|---|
| Two existing assertions now expect `SIGN_IN_NEEDED` | Step 6 reverted to `REMOTE_UNREACHABLE`: both fail |
| `test_unreadable_reply_latches_two_requests_in_turn` | `DecodingError` removed from `_latch_if_spent` |
| `test_unreadable_reply_latches_a_request_waiting_on_the_lock` | Check inside the lock removed |
| `test_a_200_that_is_not_json_latches` | `RefreshError` removed from `_latch_if_spent` |
| `test_a_refused_renewal_latches` | `RefreshError` removed |
| `test_a_server_error_on_renewal_latches` (the five-xx choice) | `RefreshError` removed |
| `test_nothing_is_sent_after_the_latch` | Check at the top of `_exchange` removed |
| `test_a_renewal_that_fails_after_its_request_was_cancelled_still_latches` | Latch set in the `except` branches instead of the done callback |
| `test_a_network_failure_does_not_latch` | Latch widened to every failure |
| `test_a_missing_credential_file_does_not_latch` | Latch widened to every failure |

Every new test also asserts no reply or stderr line holds the access token or `refresh-1`. The in-turn tests assert the second message equals `_SIGN_IN_SPENT`. The stand-in is a local `httpx.MockTransport`; no live sign-in was used.

## Not covered

As the brief names them: the older bearer-token message items, the next process reading the spent token from the credential file, connection failures after the request was sent, a request already waiting on the lock when another is cancelled mid-renewal, and `s3 ask`'s own remedy text.
