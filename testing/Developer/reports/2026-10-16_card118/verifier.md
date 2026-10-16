# Verifier report, card 118 (PR #253), fresh verifier

Branch 47eb17c1 against develop 43bcfcf7.

## Findings

- Check 1 (own run of card 75 vp75/probe.py, base 29 rows and EXTRA 40 rows, VERBOSE, both trees): diff shows only the 504 rows' reply and log wording (V1, XA, XB, FXB), XH (204 empty: latch to quiet retry then OK, spent 0) and R5 (:443 re-login: restart to resume). Every row leak=[] on both trees.
- Check 4 lock rows (own run of vp75/lockprobe.py L1 to L5 and lock2.py, both trees): only L3 differs, in wording: branch reply 'Another s3 command is using the sign-in file, so this request was not sent. Wait for that command to finish, then try again. If you have not run s3 login yet, run it once in a terminal after that.' plus one stderr line with no path. Times, codes and spent counts identical. lock2 (unlatched lock timeout) prints the temp path on stderr on BOTH trees (pre-existing V-75B-05 / J-118-04).

### V-118-01: Statuses 100 to 199 became quiet retries for every body, a JSON body carrying the app's new tokens included, so after a saved renewal the branch sends the spent token and signs the web app out; develop latched
- Severity: minor (a final 1xx cannot arrive over httpx's HTTP/1.1 stack: the adversary's real-socket run saw a bare 101 raise RemoteProtocolError and 100 or 103 treated as interim; reachable only through a transport that hands back a 1xx as final). Worse than develop. Inside this phase's fix: the fix round's quiet branch `elif status not in (401, 504) and status < 600:` has no lower bound, so it also catches 100 to 199. Its own comment says "A 3xx, a 4xx or a 5xx", and the class docstring says "every status from 300 to 599". The fix round closed A-118-02 for the top end only.
- Reproduction: own `vf118/sweep.py` (card 75 stand-in server with rotation and family revocation, real McpBridge, MockTransport, two `tools/call`), statuses 100, 101, 103, 199, 12 bodies each, rotated or not:
  ```
  branch  100|tokbody|rot  spent=1 web_out=True  codes=[(10,-32002),(11,-32001)]  msg0 "System 3 could not renew your sign-in right now (it answered 100) ... Try again in a moment."
  develop 100|tokbody|rot  spent=0 web_out=False codes=[(10,-32001),(11,-32001)]  msg0 "Your System 3 sign-in has expired or was signed out ... run: s3 login"
  ```
  Across the four 1xx statuses, all 12 bodies (JSON, JSON with tokens, empty, HTML, deep) after rotation: branch spent 1 in 48 of 48 rows, develop 0 in 48 of 48.
- Why it matters: it contradicts the fix round's own rule that a JSON reply keeps the token counted as sent. No test pins the 1xx class. The impact is theoretical on today's transport.
- NOT FIXED

### V-118-02: A 2xx renewal reply whose JSON body nests deeply escapes the new `_is_json` as RecursionError; the person sees "a problem it could not handle (RecursionError) ... Try again; if it keeps happening, restart this MCP server" with no `s3 login`, where develop said to run s3 login
- Severity: minor (no token is resent; the token stays counted as sent and the next request latches correctly; needs a 2xx with a pathological body). Worse than develop in what the person is told. Inside the fix round's own new code: `_is_json` catches only `ValueError`, and `json.loads` raises `RecursionError` for nesting past the interpreter limit. `credentials.py` already learnt this lesson (F-8.10-J01, "Every exception, not ValueError alone").
- Reproduction: own `vf118/one.py <tree> 202 deep rot` (body `[` repeated 200000 times, `application/json`, app rotated first), three `tools/call`:
  ```
  branch : [(10,-32603),(11,-32001),(12,-32001)] spent 0
    msg 1: This MCP server hit a problem it could not handle (RecursionError) while it was handling the request, so no answer was passed on. Try again; if it keeps happening, restart this MCP server.
    err  : s3 mcp: could not forward a message (RecursionError)
  develop: [(10,-32001),(11,-32001),(12,-32001)] spent 0
    msg 1: Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login. ...
  ```
  A valid but 5000-deep body (`[`*5000 + `]`*5000) does the same. All 99 statuses 201 to 299, rotated and not.
- Why it matters: the first reply tells the person to retry or restart, neither of which helps; only the second reply names `s3 login`. "A refusal says what to type next."
- NOT FIXED

### V-118-03: An empty, whitespace, HTML, non-JSON or undecodable 2xx after the app saved a renewal makes the branch send the spent token and sign the web app out; develop latched (the fix round's intended class, recorded so the owner sees it was measured)
- Severity: unsure (the fix round chose this on purpose, following A-118-01's suggestion; the app's refresh route never answers a 2xx other than 200, so this needs an intermediary that rewrites a 200 into another 2xx and also drops or replaces its body). Worse than develop for this case, and not the latch the owner accepted, so it is the one deliberate exception to the brief's bar.
- Reproduction: own `vf118/sweep.py`, statuses 201 to 299, rotated first:
  ```
  bodies empty, empty with application/json, "  \n" with application/json, HTML, HTML labelled application/json, bytes ff fe 7b:
    branch  spent=1 web_out=True  in 6 x 99 = 594 of 594 rows
    develop spent=0 web_out=False in 594 of 594 rows
  bodies {}, null, the app's token JSON (as application/json or text/plain), deep JSON:
    branch spent=0 in every row (latched), same as develop
  ```
  Not rotated, the same six bodies: branch `[(10,-32002),(11,'OK')]`, develop `[(10,-32001),(11,-32001)]` (the intended XH improvement).
- Why it matters: it is the same trade the owner accepted for a 500, 502 or 503 after a rotation, carried over to a class the owner's words did not name. A content type is not consulted, so a 2xx carrying the app's token JSON with any content type latches, which is the safe direction.
- NOT FIXED

- Check 2 (own `vf118/sweep.py`, 4 x 1xx, 99 x 2xx, 6 x 600+, 12 bodies, rotated and not, 2616 rows per tree): 600, 601, 650, 699, 700, 999 rows are byte-identical to develop for every body (A-118-02 fixed at the top end). 2xx with `{}`, `null`, or the app's token JSON (either content type) are byte-identical to develop, spent 0 (A-118-01 and J-118-02 fixed for JSON). Branch sends a spent token where develop sent none in exactly two classes: 1xx with any body (V-118-01) and 2xx with an empty, whitespace, HTML or undecodable body (V-118-03, by design). No exception escaped to the probe; leak=[] in all 5232 rows.

### V-118-04: A JSON 2xx and a status of 600 or more now latch, as intended, but tell the person their sign-in "has expired or was signed out" and log "the stored refresh token is expired, already used, or revoked"; the outcome is unknown, as with the 504 this card reworded
- Severity: minor (wording; the command `s3 login` is right and no token is sent; identical to develop, so not worse).
- Reproduction: own sweep rows on the branch, e.g. `201|jsonobj|norot` and `600|tokbody|rot`: msg 1 "Your System 3 sign-in has expired or was signed out, so this request was not sent. In a terminal, run: s3 login. ...", stderr "could not renew the sign-in: POST /auth/refresh returned 600; the stored refresh token is expired, already used, or revoked. Run: s3 login". The fix round's `fix_round.md` row for A-118-01 describes this as "keeps the token counted as sent and asks for s3 login", which is true; the words are the generic RefreshError text.
- Why it matters: a confident wrong statement about the sign-in, the same class V-75B-02 fixed for 504 in this card. Not a blocker.
- NOT FIXED

- Check 4 (own `vf118/busy.py`: latched by a ReadTimeout after rotation, another process holds the lock past a 0.8 s bound, two requests, lock released, one request, `s3 login`, one request): branch codes `[(10,-32002),(11,-32001),(12,-32001),(13,-32001),(14,'OK')]`, same as develop. Replies 11 and 12: "Another s3 command is using the sign-in file, so this request was not sent. Wait for that command to finish, then try again. If you have not run s3 login yet, run it once in a terminal after that." Log: "could not check for a new sign-in: another s3 command is using the sign-in file. Wait for that command to finish and try again." Temp path and home path absent from replies, stderr and DEBUG root log; no token. J-118-01 and A-118-04 fixed.
- Check 5 (own `vf118/leak.py`: 96 rows, statuses 100, 2xx, 302, 401, 404, 429, 500, 502, 503, 504, 600, 999, HTML, JSON and empty bodies, rotated and not; the server echoes the sent refresh token and the bearer into the body, an `x-echo` header and `www-authenticate`; capture of replies, stderr, root logging at DEBUG and warnings): hits [] on both trees. Positive control (a token and the temp path written into stderr) detected on both trees. The pre-existing unlatched lock-timeout path on stderr (J-118-04, V-75B-05) is unchanged and identical on develop.

### V-118-05: The new "another s3 command is using the sign-in file" reply carries code -32001 (sign in needed) while its words say wait and try again
- Severity: unsure (a host that keys a sign-in prompt on -32001 would prompt a person who only needs to wait; the words are right; develop gave -32001 with sign-in words, so the code is unchanged and nothing is sent).
- Reproduction: `vf118/busy.py` on the branch, replies 11 and 12 above: code -32001 with "Wait for that command to finish, then try again." The mirror of V-75B-06 (a "try again" code with sign-in words).
- Why it matters: code and words disagree on the reply this fix round added. Not worse than develop.
- NOT FIXED

- Check 6, gates at 47eb17c1 (own runs): `ruff check` "All checks passed!" exit 0; `isort --check-only --diff src tests services tracker alembic .claude .github` (gate02's command) "Skipped 2 files" exit 0; `pytest tests/system_03_search_agent/adapters -m "not integration" -q`: 949 passed, 2 warnings. The worktree's own `mcp_bridge.py` is the one imported (confirmed by import path, and by the mutations below turning red).
- Mutations (own, each restored with `git checkout --`, `git status --short` empty after each), bridge test file:
  - M1, 504 reply code to REMOTE_UNREACHABLE: 1 failed (J-118-03 pinned, fixed).
  - M2, `_is_json` always False (a JSON 2xx goes quiet): 4 failed.
  - M3, the "busy" outcome dropped from `_refuse_if_spent`: 1 failed.
  - M4, the `< 600` bound dropped: 3 failed (A-118-02 pinned).
  - M5, the lower bound `300 <=` put back (1xx latch again): 132 passed. No test pins the 1xx class in either direction, which is why V-118-01 shipped unseen.

## Check 3: earlier findings marked FIXED, by probe

| Finding | Result | Evidence |
|---|---|---|
| A-118-01, J-118-02 | Fixed for a JSON 2xx: `{}`, `null` and the app's token JSON latch, spent 0, byte-identical to develop across 201 to 299, rotated and not. The empty or non-JSON 2xx class still resends after a rotation, by design (V-118-03). | Own sweep |
| A-118-02 | Fixed at the top: 600, 601, 650, 699, 700, 999 identical to develop for 12 bodies. The open lower bound now lets 1xx through (V-118-01). | Own sweep; M4, M5 |
| J-118-03 | Fixed: the 504 code is pinned. | M1 red |
| J-118-01, A-118-04 | Fixed: reply and log say wait for the other s3 command, `s3 login` only for someone who has not run it, no path. | Own busy.py; lockprobe L3 |
| A-118-03 | Fixed: log reads "returned 504, so the outcome is unknown. In a terminal, run: s3 login. ..." | Own run of vp75 rows V1, XA, XB, FXB |

## Verified by my own probes versus only read

- Run myself: card 75's whole table (29 base, 40 EXTRA, lock L1 to L5, lock2) on both trees and diffed; my own sweep of 109 statuses x 12 bodies x rotated or not (2616 rows per tree); my latched lock-timeout run; my 96-row leak sweep with echoed tokens, DEBUG logging, warnings and a positive control; the three gates; five mutations.
- Read only: that the app's refresh route answers only 200, 401, 422 or 5xx (from the judge's and adversary's reading, not re-read); that a final 1xx cannot reach the bridge over httpx's HTTP/1.1 stack (the adversary's real-socket run in `adv118/p2.py`, not rerun; I did confirm by reading that the CLI's client does not enable HTTP/2); the probe stand-in's fidelity to `auth/router.py` (the card 75 verifier's server, reused, not re-audited).

## Verdict

HOLD, narrowly. Two things are worse than develop 43bcfcf7 beyond the class the fix round chose on purpose, and both sit inside this phase's fixes, which fires the review loop's stop condition:

- V-118-01 (minor): a 1xx renewal reply, any body, the app's token JSON included, retries quietly; after a saved renewal that sends the spent token and signs the web app out. Develop latched. Unreachable over today's HTTP/1.1 transport, unpinned by any test (M5 survives), and contrary to the fix round's own comment and docstring ("3xx, 4xx or 5xx", "300 to 599").
- V-118-02 (minor): a deeply nested JSON body on a 2xx escapes the new `_is_json` as RecursionError, and the first reply says "a problem it could not handle ... Try again; if it keeps happening, restart this MCP server" instead of `s3 login`. No token is sent. Develop said `s3 login`.

What is worse than develop by design and needs only the owner's eye: V-118-03, an empty or non-JSON 2xx after a saved renewal resends the spent token (594 of 594 such rows; develop 0). The app never answers that way.

Everything else matches develop or is better: card 75's table differs only in XH, R5, the 504 wording and the lock-timeout words; 600 and above and every JSON 2xx latch exactly as develop; no token or path in any reply or log; gates green. Open, not worse than develop: V-118-04 (expiry wording on JSON 2xx and 600+ latches), V-118-05 (busy reply code -32001), J-118-04 (pre-existing path on the unlatched lock timeout).

Worktrees `v118` and `v118dev` removed. No live calls. No repository file changed.
