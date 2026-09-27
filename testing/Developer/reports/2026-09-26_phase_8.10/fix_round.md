# Build phase 8.10: the fix round

The one fix-and-verify round of `tracker/phase_8.10.md`, pull request #120. Branch `feat/8.10-fix`, cut from `origin/phase/8.10-integrations` at `68f2155f`, not pushed. Paths are written as `<repo-root>` and `<scratch>`. No email, password or token appears here.

## Table of contents

- [Summary](#summary)
- [Commits](#commits)
- [One line per finding](#one-line-per-finding)
- [Evidence, before and after](#evidence-before-and-after)
- [Checks](#checks)
- [For the lead and the verifier](#for-the-lead-and-the-verifier)

## Summary

| Group | Findings | Status |
|---|---|---|
| 1, the bridge answers every request | J01, A01 | fixed |
| 2, the bridge's bounds | A04, A07, J12, and A06 with it | fixed, plus one regression the deadline would have caused, found and fixed |
| 3, no userinfo printed | A05 | fixed |
| 4, a reopened answer counts what it cannot show | J02, A02 | fixed |
| 5, empty feedback | A08 | fixed |
| 6, the registry check's own test | J07 | fixed |
| 7, `s3 ask --json` fails as JSON | J08 | fixed |
| 8, the pages | J03, J04 (L01), J05 (L02), J06, J10 (A12), J13 | fixed |

Every fix has a test that fails when the fix is taken out. Each was proven by putting the unfixed file back and running the new tests, then restoring it.

## Commits

On `feat/8.10-fix`, oldest first:

- `f55de5aa` fix(cli): s3 mcp answers every request, whatever the server or the agent sends
- `0b54e82c` fix(cli): s3 mcp bounds each reply and each request, and forwards only JSON-RPC
- `8cbd7606` fix(cli): s3 login and s3 mcp name the server by its host, never its userinfo
- `3e7d7322` fix(mcp): a reopened answer counts the markers it has no citation for
- `6393a7c6` fix(mcp): feedback with nothing in it is refused, not recorded
- `6bdc512c` test(mcp): the registry's ownership check on feedback has a test of its own
- `71dcbba9` fix(cli): s3 ask --json writes one JSON object even when the run never streams
- `18ffcf6d` fix(web-ui): About, the tour and Integrations say what is true
- `5273018a` fix(cli): the request deadline never cuts off a renewal the server already made
- this report

## One line per finding

- F-8.10-L01: fixed with J04, below. The facts checker reads it as ERROR, since its pattern is keyed to the old sentence; it no longer FAILs.
- F-8.10-L02: fixed with J05, below. ERROR for the same reason, not FAIL.
- F-8.10-A01: fixed. Before: a 100000-deep body, SSE line or agent line got no reply and killed `serve`. After: one error reply each, and `serve` reads the next line.
- F-8.10-A02: fixed with J02.
- F-8.10-A03: left, a note. GraphQL's `refuse` for an ask-back is card 52's, as the History records.
- F-8.10-A04: fixed. Before: a 15 MiB reply reached the agent. After: the cap is 4 MiB, sized from the server's output schemas, whose largest reply is about 670 KB; a test builds that reply and proves it passes whole.
- F-8.10-A05: fixed. Before: `https://user:pass@host` was printed by `s3 login`, on `s3 mcp`'s stderr and in its errors. After: scheme, host and port only.
- F-8.10-A06: fixed by group 2, as the brief said. Before: a reply for id 42 in the stream of request 1 reached the agent. After: only the first response to the request's own id, and the server's requests and notifications, are passed on.
- F-8.10-A07: fixed. Before: no total deadline. After: five minutes from the moment the agent sends a request, the wait for a slot included, and eight stuck requests no longer block a ninth.
- F-8.10-A08: fixed. Before: a call with nothing in it answered `recorded: true` and replaced the stored rating. After: refused with a message naming the four fields, earlier feedback unchanged. The REST route is unchanged.
- F-8.10-A09: left, a note. Feedback's two refusal texts match REST's 404 and 403, and uuid4 ids make guessing impractical.
- F-8.10-A10: left, a note. The SDK's own argument errors predate the phase.
- F-8.10-A11: left, card 57, answer path.
- F-8.10-A12: fixed with J10.
- F-8.10-A13: left, a note. A new enum value in a frame the client never renders ends the run; stricter than the contract, and stated in builder P's report.
- F-8.10-A14: left, a note, not reachable today.
- F-8.10-J01: fixed. Before: `RecursionError` at 5000 deep and `httpx.DecodingError` for a gzip-labelled body left the request unanswered with stderr empty. After: `_forward` catches every exception and answers once; `handle_line` never raises; `_refresh_and_store` turns any failure to read its body into a `RefreshError`.
- F-8.10-J02: fixed. Before: a 60-marker answer, 50 citations stored, reopened with `citations_omitted: 0`. After: 10. The capture cap is card 54's and unchanged.
- F-8.10-J03: fixed. About says the tiers are "matched to how hard the step is" again.
- F-8.10-J04: fixed. The Plan tier card says the tier runs Think's classification and, in Act, writes a graph query only when no template fits; Plan never calls it, and its yes-or-no questions go to the guard tier or a classifier.
- F-8.10-J05: fixed. The tour step is titled "Example questions" and says "Try one of these four example questions", with no claim about their source. The questions are unchanged.
- F-8.10-J06: fixed. The printed `s3 login` is `s3 login --base-url <the page's API origin> you@example.org`.
- F-8.10-J07: fixed. A new test puts the registry's owner and the stored row's owner apart, so only `resolve_owned_run` refuses. With it replaced by `get_run`, that test alone fails. The old test's wrong mutation comment is corrected.
- F-8.10-J08: fixed. `s3 ask --json` writes one JSON object with every key an answer has for a failure before or while opening the stream, and still exits non-zero. Human mode is unchanged.
- F-8.10-J09: left, a note. The same on 15aae08, not a regression.
- F-8.10-J10: fixed. The command line card shows `{"mcpServers": {"system3": {"command": "s3", "args": ["mcp"]}}}` with its own copy button, and says `s3 mcp` goes in an agent's MCP settings, not a terminal. The terminal commands no longer end in `s3 mcp`, which only waits for input there.
- F-8.10-J11: the lead's; not touched.
- F-8.10-J12: fixed. Only a JSON-RPC 2.0 object is forwarded. A batch, a bare value, a missing or wrong `"jsonrpc"`, a null, boolean or object id is answered here with an invalid request error, and `NaN` is refused as not JSON.
- F-8.10-J13: fixed. The MCP card says the follow-up offers are coming to MCP, not "the same parity the web app has".
- F-8.10-J14: left, a note, latent.

One more, found by reviewing this round's own A07 fix: the new deadline can cancel a request while its sign-in renewal is in flight. The server rotates the refresh token as it answers, so the new one was lost and the next renewal replayed a used token. A test reproduced it (the credential file kept `refresh-1`). The renewal now runs shielded and `drain` waits for it (`5273018a`).

## Evidence, before and after

The judge's `probe_bridge_noauth.py`, before:

```text
_read_json raised non-BridgeError: RecursionError
_read_event_stream raised non-BridgeError: RecursionError
reply lines written to the agent for request id 7: []
reply lines for request id 8: []
deep agent line raised out of handle_line: RecursionError
stderr:
```

After:

```text
_read_json: BridgeError -32003
_read_event_stream: BridgeError -32003
reply lines written to the agent for request id 7: ['{"jsonrpc":"2.0","id":7,"error":{"code":-32603,"message":"This MCP server hit a problem it could not handle (RecursionError) ...
reply lines for request id 8: ['{"jsonrpc":"2.0","id":8,"error":{"code":-32603,"message":"This MCP server hit a problem it could not handle (DecodingError) ...
deep agent line: handled
stderr: s3 mcp: could not forward a message (RecursionError)
s3 mcp: could not forward a message (DecodingError)
```

The adversary's `adv_probe_bridge_deep.py`, before and after:

```text
before: A: replies written to agent: 0 | A: forward task exception: RecursionError
        B: replies written to agent: 0 | B: forward task exception: RecursionError
        C: handle_line raised out to serve(): RecursionError
after:  A: replies written to agent: 1 | A: forward task exception: None
        B: replies written to agent: 1 | B: forward task exception: None
        C: handled, replies: 1 [b'{"jsonrpc":"2.0","id":null,"error":{"code":-32700,...
```

The adversary's `adv_probe_bridge_misc.py`, before and after:

```text
before: 1 huge reply: lines to agent 1 bytes 15728714
        2 agent sees: ..."System 3 at https://<userinfo>@example.test answered HTTP 500..."
        3 replies forwarded: [42, 1]
        4 batch: replies 2
        6 odd ids: replies ['{"jsonrpc":"2.0","id":NaN,"result":{}}', '{"jsonrpc":"2.0","id":{"a":1},"result":{}}']
after:  1 huge reply: lines to agent 1 bytes 150
        2 agent sees: ..."System 3 at https://example.test answered HTTP 500..."
        3 replies forwarded: [1]
        4 batch: replies 1
        6 odd ids: replies [parse error, id null; invalid request, id null]
```

Case 2's stderr line in that probe is built by the probe itself, not by `serve`; `serve`'s own start-up line is covered by `test_a_password_in_the_base_url_is_never_printed` in `test_mcp_bridge.py`.

The judge's `probe_bridge_forwarding.py`: before, `"hello"`, `42`, `[]`, `{}`, `{"method":"tools/list"}` and a batch were forwarded to the remote; after, `forwarded to the remote: []`, and each of the 8 lines got exactly one reply, the ping answered locally.

The judge's `probe_capture60.py`, with the reopen count added: capture still stores 50 of 60 and markers 51 to 60 have no stored citation, before and after; `reopen_past_answer` now returns 50 citations with `citations_omitted = 10`. Before, the end-to-end test against the real database failed with `assert 0 == 10`.

The judge's `probe_json_keys.py`, `probe_stream.py`, `probe_stream_base.py` and the adversary's `adv_probe_stream.py` and `adv_probe_stream2.py` print the same before and after.

The new tests, run against the unfixed files:

- Group 1: 10 failed (8 bridge, 2 credentials).
- Group 2: 19 of 20 failed against group 1's bridge; the 20th, NaN, failed against the original bridge.
- Group 3: 2 failed.
- Group 4: 4 failed, the end-to-end one with `assert 0 == 10`.
- Group 5: 1 failed, "expected send_answer_feedback to refuse, it returned {... 'recorded': True}".
- Group 6: with `resolve_owned_run` replaced by `get_run`, `1 failed, 6 passed`, the new test alone.
- Group 7: 3 failed, 1 passed (the human-mode guard, by design).
- Group 8: 5 failed, 35 passed.
- The renewal fix: 1 failed without the shield.

## Checks

Pasted result lines, from `<repo-root>/.claude/worktrees/p810fix`:

- The page facts checker from `origin/chore/verify-facts-2` (`--root` the worktree, `--reference` the data-engineering repository): `facts: 64 | stale 9 | not fully checked 7 | places: PASS 153, FAIL 19, GAP 0, ERROR 8 | NOT PASSED`, identical line for line to the run before the fix. Every FAIL is a `document` or `code copy` place, card 53's. `loop.plan_on_plan_tier | About` and `seeds.from_golden_set | Onboarding tour` read ERROR, not FAIL. An interim MCP card wording turned `tools.count` from PASS to ERROR; it was reworded so it passes again.
- `ruff check`: `All checks passed!`
- `isort --check-only --diff src tests services tracker alembic .claude .github`: `Skipped 2 files`, exit 0.
- `bash .github/gates/gate_packages_install.sh`: `2 passed, 0 failed`.
- `bash .github/gates/gate04_unit_suite.sh`, against the local PostgreSQL: `6402 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 359.63s (0:05:59)`, exit 0. Every skip is a premise gate that needs `RUN_PREMISE_GATE=1` and a live model key or service; no database test was skipped.
- `npm test -- --run` for the four page test files: `Test Files  4 passed (4)`, `Tests  50 passed (50)`. The whole frontend suite: `Test Files  56 passed (56)`, `Tests  464 passed (464)`.
- `npm run build`: `✓ built in 641ms`, exit 0.
- `python3 tracker/check_doc_drift.py --check`: `ok: 2 facts computed | 0 could not be computed | 0 stale | 0 structural`.
- The audit smoke script's `page` check, run offline through its own `check_page` against the worktree's page and source: `page ok | printed commands match the code`.
- `tests/system_03_search_agent/test_integrations_page_claims.py`: `6 passed`.

No live question was sent to develop.

## For the lead and the verifier

- The command line card now shows a code block, the agent configuration, built with the same `IntegrationCard` code box the MCP card uses, so no new visual value. It was not screenshotted here; it is worth a look at 390 in `/verify`.
- Decision, from the user's chair: `s3 mcp` left the copied terminal commands. Pasted into a terminal it only waits for input after the answer prints, which reads as a hang. It is named in the card's text and is the command in the agent configuration beside it.
- Decision: the bridge shows a base URL as scheme, host and port rather than the bare host, so a person can still tell `http` from `https`. No userinfo, path, query or fragment is ever shown.
- Outside this round's files, not changed:
  - `docs/build/Debugging_guide.md`'s `mcp_bridge.py` row says it "forwards every message"; it now forwards every JSON-RPC message and answers anything else itself.
  - `frontend/src/components/screens/HomeScreen.tsx:25`, a code comment, still calls the seeds "Real must-pass questions from the evaluation set".
- A base URL with userinfo also makes `httpx` send Basic authentication in place of the bearer token: a stand-in server saw `Basic` on both a plain and a streamed POST. So such a sign-in never works, and the token is not what leaks. That predates the phase and was not changed.
