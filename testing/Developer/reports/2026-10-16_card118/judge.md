# Judge, card 118 (PR #253), one round, dial position 3

## Findings (appended as established)

Progress note (judge's own runs, branch ae271905 vs develop 467d1081): card 75 verifier's `vp75/probe.py`, base and EXTRA rows, VERBOSE, both trees. Summary lines differ only in XH (204), XI (202) and R5 (`:443` re-login); full output differs additionally only in the 504 rows' reply and stderr wording (V1, XA, XB, FXB). Every row `leak=[]` on both trees.

### J-118-01: After a lock timeout on a latched bridge the reply still tells the person to run `s3 login`, and the new log line says no command to type
- Severity: minor (diagnosis and wording; nothing is sent, no token spent; same reply as develop)
- What: V-75B-04's log half is fixed (a stderr line, no path). The reply half is not: a person who has already run `s3 login` while another `s3` command holds the lock is told again "Your System 3 sign-in could not be renewed earlier ... run: s3 login". The new stderr line "could not check for a new sign-in: another s3 command was holding the sign-in file" names no next step (wait, or which command to stop). The build report states "reply unchanged", so this is a known choice, filed against brief check 5 ("every message says exactly what to type").
- Reproduction: judge's `jp118/l3.py` (lock held 5 s by another process, bound patched to 1.0 s, bridge latched by a ReadTimeout after rotation, two requests, then `s3 login`, one more). Both trees: codes `[(10,-32002),(11,-32001),(12,-32001),(13,'OK')]`, identical replies. Branch stderr adds, twice: `s3 mcp: could not check for a new sign-in: another s3 command was holding the sign-in file`. Develop: no line. No temp path and no token in any reply or stderr on either tree.
- Why it matters: the log now explains the cause to whoever reads it; the person in the chat still gets advice that will not help until the other command finishes.
- NOT FIXED

### J-118-02: If anything between the bridge and the app ever turned the app's 200 renewal into another 2xx, the quiet retry would resend the spent token and sign the web session out; the app itself never does
- Severity: unsure, leaning not a defect (the trade-off check 3 asks about; unreachable from the app as written)
- What: `_RenewalClient` now marks every 2xx other than 200 quiet and takes the token back. If the app had rotated before such an answer, the next request resends the spent token, the router's `_revoke_family_on_reuse` revokes the family, and the web session is signed out. Develop latched these with no send. Reading `auth/router.py`: `@router.post("/refresh", response_model=TokenResponse)` has no `status_code=`, so FastAPI answers 200; every failure path raises 401; the only app middleware that can answer for a route (`RequestTimeoutMiddleware`) gates itself on the GraphQL path. `credentials.py` line 705 rejects any status other than 200, even with a well-formed token body. So no 2xx other than 200 can follow a renewal the app saved, unless a proxy rewrites the status, which is the same class as the owner's accepted 500/502/503-after-rotation cost.
- Reproduction: judge's `jp118/twoxx.py`, statuses 201, 202, 203, 204, 205, 206, 207, 208, 226, 299, each with and without the stand-in having rotated first, two requests:
  ```
  develop, all 20 rows:        spent=0 famrev=0 web_out=False codes=[(10,-32001),(11,-32001)]
  branch, not rotated (10):    spent=0 famrev=0 web_out=False codes=[(10,-32002),(11,'OK')]
  branch, after rotation (10): spent=1 famrev=1 web_out=True  codes=[(10,-32002),(11,-32001)]
  branch, 201 with a valid token body after rotation: spent=1 famrev=1 web_out=True
  ```
- Why it matters: only if a status-rewriting intermediary is ever put in front of `/auth/refresh`. The class docstring's sentence "the app never answers one after renewing" is true of the app and is the claim this rests on; it would be cheap to pin it with a test on the router's refresh status.
- NOT FIXED

Progress note, check 4: judge's `jp118/port.py` ran `_normalised_address` on the branch over 30 addresses. The only merged classes are a bare host with its scheme's default port (`https` with `:443`, `http` with `:80`), with or without a path, query, upper case, trailing slash or surrounding spaces. Not merged: `http://host:443`, `https://host:80`, `:8443`, `:10443`, `:4430`, `:0443`, an empty port, a userinfo form against the bare host, `[::443]` against `[::]`, `system3.test443`, `system3.te:443` against `system3.test`, `other.test:443`. A malformed `host:443:443` loses one `:443` but still differs from the bare host. No two different servers compare equal. Check 4 passes.

### J-118-03: No test pins the 504 reply's error code; a mutation to the "try again" code survives the whole bridge test file
- Severity: minor (test gap inside this card's new 504 branch; the code ships right today)
- What: the new 504 branch raises `BridgeError(SIGN_IN_NEEDED, _UNKNOWN_RENEWAL)`. Changing it to `REMOTE_UNREACHABLE` (-32002, the code a host reads as "try again") leaves every test green. `test_a_504_says_the_outcome_is_unknown_not_expired` checks words only, and card 75's 504 test evidently checks sends, not the code. This is the same code-versus-words split V-75B-06 describes, so a host keyed on -32001 to prompt a sign-in would show none and nothing would catch it.
- Reproduction: judge's mutation M2 in the branch worktree, `raise BridgeError(SIGN_IN_NEEDED, _UNKNOWN_RENEWAL)` to `raise BridgeError(REMOTE_UNREACHABLE, _UNKNOWN_RENEWAL)`, then `pytest tests/system_03_search_agent/adapters/cli/test_mcp_bridge.py -q`: `122 passed`. Restored with `git checkout --`, `git status --short` empty. On the unmutated branch, the probe's 504 rows (V1, XA, XB) answer `-32001` as intended.
- Why it matters: a later edit can quietly turn the one "outcome unknown, run s3 login" reply into a "retry" code; the reply's purpose is that the person signs in once instead of retrying.
- NOT FIXED

### J-118-04: A lock timeout on a bridge that is not latched still prints the credential directory's path on stderr, and its reply still says "then restart this MCP server" (V-75B-05, unchanged)
- Severity: minor, pre-existing (identical on develop; the build report leaves V-75B-05 open on purpose). Filed because brief check 5 asks for no path in any log.
- What: the credential module's `RefreshLockTimeoutError` text, which names the lock file's path, still reaches stderr through `_sanitize_untrusted` on the renewal path. The new latched-path clause in this card drops the path; the unlatched path does not. The reply's "then restart this MCP server" contradicts `_SIGN_IN_NOW`, and `s3 login` does not clear a stuck lock.
- Reproduction: card 75's `vp75/lock2.py` (another process holds the lock past a 1.0 s bound, access token expired, one `tools/call`), both trees: `[(10,-32001),(11,'OK')]`, `tmp path in stderr: True | in replies: False`, reply `The s3 sign-in on this computer could not be used. In a terminal, run: s3 login, then restart this MCP server.`
- Why it matters: a host that keeps MCP stderr in a shared log carries the person's home path. Not worse than develop, so it does not block.
- NOT FIXED

## Checklist

| Check | Result | How |
|---|---|---|
| 1. V-75B-01 fixed | Yes. 204 and 202 (rows XH, XI) now answer -32002 "it answered 204 ... Try again in a moment.", then OK, 0 spent. My sweep of 201 to 299 agrees. | Own run of `vp75/probe.py` EXTRA plus `jp118/twoxx.py` |
| 1. V-75B-02 fixed | Yes. 504 rows (V1, XA, XB, FXB) reply "System 3 did not confirm whether it renewed your sign-in (a gateway timed out) ... The server may have renewed it. In a terminal, run: s3 login. ..."; stderr "... returned 504, so the outcome is unknown; ..."; no "expired" or "revoked". Code stays -32001 (but see J-118-03). | Own run, both trees, full-text diff |
| 1. V-75B-03 fixed | Yes. R5 (`https://system3.test:443`) resumes: `[(10,-32002),(11,'OK'),(12,'OK')]`; develop refused with restart. R4 (other host) still refused. | Own run |
| 1. V-75B-04 fixed | Half. Log line now present, no path; reply unchanged and the log line names no next step (J-118-01). | Own `jp118/l3.py`, card 75 `lockprobe.py` L3 |
| 2. Nothing else changes | Yes. All 29 base rows and all 40 EXTRA rows: summary lines identical except XH, XI, R5; full output differs elsewhere only in the 504 wording. Lock rows L1 to L5 identical in codes, times within 0.01 s, spent 0. Leak sweep identical apart from the new 2xx rows. | Own runs, both trees |
| 3. 2xx after a saved renewal | The app cannot produce one: `/auth/refresh` has no `status_code=` (200), failures raise 401, the only route-answering middleware is gated to GraphQL, and `credentials.py` rejects any non-200. If a status-rewriting proxy ever did, retrying would resend a spent token and sign the web session out (J-118-02, measured: 10 of 10 rotated 2xx rows give spent=1, web_out=True; develop 0). | Router read; consequence run |
| 4. Port normalisation | Cannot merge two different servers. Only a scheme's own default port is dropped. | Own `jp118/port.py`, 30 addresses; mutation M1 |
| 5. No token, secret or path; exact words | Replies, stderr, root logging at DEBUG and warnings, 18 rows including echoed tokens, bearer, body and temp directory, plus 202, 206 and 299 echo rows: `token_hits=[]`, `path_hits=[]` on both trees; positive control hit on both. Every latch says "In a terminal, run: s3 login"; every quiet reply says "Try again in a moment."; other server says "Restart this MCP server to use it." Exceptions: J-118-01 (log line names no command), J-118-04 (pre-existing path on the unlatched lock timeout). | Own `jp118/leak2.py` (extended `vp75/leak.py`) |
| 6. Gates | `ruff check`: All checks passed! (exit 0). `isort --check-only --diff src tests services tracker alembic .claude .github`: Skipped 2 files (exit 0). `pytest tests/system_03_search_agent/adapters -m "not integration" -q`: 939 passed, 2 warnings. pytest reads the worktree's `src` (`pythonpath = ["src", "."]`, confirmed by import path). | Run at ae271905 |
| 6. Mutations | M1: strip any port, not only the default: `test_only_a_default_port_is_dropped_from_an_address` red (1 failed, 121 passed). M2: 504 reply code to -32002: survived, 122 passed (J-118-03). Both restored, `git status --short` empty. | Run |

## Verified by my own probes versus only read

- Run: every row of card 75's scenario table on both trees (base, EXTRA, lock, lock2, leak), my 2xx sweep with and without rotation, my lock-timeout run on a latched bridge, my 30-address normalisation table, the three gates, two mutations.
- Read only: that the app's `/auth/refresh` answers 200 on success and nothing else in the 2xx range (route decorator, handler, middleware list, `credentials.py` line 705); that no proxy in the deployment rewrites statuses (not checked, no live calls); the build report's own mutation results (not rerun, apart from overlap with M1).

## Verdict

PASS. Nothing is worse than develop 467d1081 for any response the app can actually give. Every row of card 75's table matches develop except the three this card set out to change (XH, XI, R5), each now better, and the 504 rows, whose words now say what happened. No spent-token send was added for any reachable answer. No leaks.

What is worse than develop only in theory: J-118-02. A 2xx other than 200 after a rotation the app saved would now resend the spent token and sign the web session out, where develop latched. The app never answers that way, so this would need a status-rewriting proxy, the same class as the owner's accepted 500/502/503 cost.

Open, none blocking:
- J-118-01 (minor): V-75B-04's reply half and its log line's missing next step.
- J-118-03 (minor): a test gap in this card's new 504 branch. The -32001 code is unpinned, and a mutation to -32002 survives. This sits inside this card's own fix, so the lead should note it under the stop condition, though it is a test gap, not a shipped defect.
- J-118-04 (minor, pre-existing): V-75B-05 unchanged.
