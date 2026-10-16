# Fix round, card 75 (PR #252)

One fix round on `fix/card75-unknown-renewal` from head 2306eaec, reading the owner's decision as the lead set it down in DECISIONS.md on 2026-10-16. Findings are the judge's (J-75B-NN) and the adversary's (A-75B-NN).

## Table of contents

- [The rule now](#the-rule-now)
- [Findings](#findings)
- [Scenario table, rows changed](#scenario-table-rows-changed)
- [Gates](#gates)

## The rule now

| Renewal answer | Result |
|---|---|
| 500, 502, 503, 429, other 5xx except 504 | Retries quietly, token taken back |
| Every 3xx and 4xx except 401 (301, 307, 400, 403, 404, 408, 421) | Retries quietly |
| 200 with a non-JSON type (a page) | Retries quietly, as before |
| 200 JSON with an empty body | Retries quietly (new) |
| 401 | Latches, as before |
| 504 | Latches (new): a gateway stopped waiting for a server that may have renewed |
| 200 JSON, non-empty, unreadable | Latches, as before |
| ReadTimeout, ReadError, RemoteProtocolError after the send | Latches, as before |

## Findings

| Finding | Status | Test (all in `test_mcp_bridge.py`) |
|---|---|---|
| J-75B-01, A-75B-01, J-75B-05 | FIXED | `test_a_status_the_app_cannot_send_after_renewing_retries_quietly` (400, 403, 404, 408, 421, 301, 307, 500, 502, 503, 429), `test_a_401_on_renewal_latches` |
| A-75B-02 | FIXED | `test_an_empty_json_200_retries_quietly`, `test_a_non_empty_unreadable_json_200_still_latches` |
| J-75B-02, A-75B-03 | FIXED | `test_the_quiet_retry_message_does_not_claim_the_sign_in_is_good` (503, page, empty, 500). The message now reads "System 3 could not renew your sign-in right now (it answered X), so this request was not sent. Try again in a moment." |
| A-75B-04 | FIXED | `test_a_504_on_renewal_asks_for_s3_login_once`. The 500-after-rotation case stays an accepted cost, pinned by `test_a_500_after_the_server_rotated_is_retried_as_before` (the old 504 half of that test moved to the 504 test above) |
| A-75B-05 | FIXED | `test_a_new_sign_in_with_a_trailing_slash_address_is_picked_up` (scheme and host case and a trailing slash), `test_a_new_sign_in_for_another_server_says_to_restart` (new `_OTHER_SERVER` text: "Restart this MCP server to use it.") |
| J-75B-04, A-75B-06 | FIXED | `test_one_renewals_outcome_does_not_leak_into_another`. Status, page and empty marks now live on the per-renewal `_RenewalClient`; the bridge fields are gone |
| A-75B-08 | FIXED within the fence | `test_a_latched_bridge_reads_the_credential_file_under_the_refresh_lock`. `_refuse_if_spent` and `_resume_from_file` are now async and read under `_CredentialFileLock` (the module's own lock, used through its private names `_CredentialFileLock` and `_lock_path`). `credentials.py` is unchanged. A lock timeout or error leaves the bridge refusing, as a failed read did before |
| A-75B-07 | NO CODE CHANGE, as briefed | Over real HTTP/1.1 a dropped connection surfaces as `ReadError`, not `WriteError` (httpcore reads on after a write error). It therefore asks for `s3 login`. `httpx.WriteError` in `_NEVER_SENT` only matters for a transport that raises it directly. Query 114 no longer promises recovery for a dropped connection |
| J-75B-03 | Information only | Reachability read, nothing to fix |

Each new test failed on the pre-fix source and passes now (17 failed on 2306eaec's `mcp_bridge.py`, 0 after; the source was swapped back and forth by copy, no stash).

## Scenario table, rows changed

Re-derived on this branch by the new tests, not by the judge's probe scripts. Rows not listed are untouched by the change and their tests still pass (the 910 earlier adapter tests all pass).

| Row | Input | Develop | Branch before | Branch now |
|---|---|---|---|---|
| X2 to X7 | 403, 404, 408, 400, 301, 307 or 421, not rotated | -32001, then OK | -32001, then latch | -32002 "try again", then OK; sends 2, spent 0, revoked 0 |
| 422 | 422 not rotated | -32001, then OK | latch | quiet retry like the other 4xx (covered by the same class rule, not a separate test) |
| A-75B-02 | empty JSON 200 | -32001, then OK | latch | quiet, then OK |
| X8, 500 | 500 JSON, not rotated | -32001, then OK | -32002, OK | same |
| V1, 504 | 504 after rotation | 2 sends, family revoked | 2 sends, revoked, "still good" | 1 send, latch, asks `s3 login`, nobody signed out |
| 04, 500 | 500 after rotation | revoked | revoked, "still good" | revoked (accepted cost), words no longer claim the sign-in is good |
| X1, 502 after rotation | proxy 502 after the app committed | revoked | revoked | revoked (accepted cost, owner's 502 call), words no longer claim it is good |
| 401 | refused sign-in | latch | latch | latch |
| V2, V3, 08 to 10 | ReadTimeout, RemoteProtocolError, ReadError after send | 2 sends | latch | latch (unchanged) |
| Unreadable non-empty JSON 200 | gzip lie | revoked | latch | latch (unchanged) |
| After latch, `s3 login` same address with trailing slash | | OK | still latched | OK |
| After latch, `s3 login` another server | | OK on the old host | refused, "picks up by itself" | refused, "Restart this MCP server" |

## Gates

| Gate | Result |
|---|---|
| `ruff check` (no path) | All checks passed! |
| `isort --check-only --diff src tests services tracker alembic .claude .github` | Skipped 2 files, no diff |
| `pytest tests/system_03_search_agent/adapters -m "not integration" -q` | 932 passed, 2 warnings |
| `bash .github/gates/gate04_unit_suite.sh` | Not run, on the coordinator's instruction (another agent runs the full suite; CI runs it on push) |
