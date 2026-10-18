# Card 61: Command line and MCP bridge edge cases

The installed client must still work with today's production server. All probes below run locally with fake data, not against the live service. No server, dependency or answer-path change is part of this card.

## Table of contents

- [Finding plan](#finding-plan)
- [Review refinement](#review-refinement)
- [Compatibility and boundaries](#compatibility-and-boundaries)
- [Questions](#questions)

## Finding plan

| Finding | State on develop and reproduction | File and one-line change | Red-without-fix test |
|---|---|---|---|
| V01 | Reproduces by inspection: `mcp_bridge.py` puts `self._slots` inside `asyncio.timeout`, so queue time consumes the request's deadline. Existing stuck-slot test checks eventual release, not a fresh budget. | `adapters/cli/mcp_bridge.py`: acquire the slot before starting the per-request deadline, retaining a bounded deadline for the exchange. | `test_mcp_bridge.py`: 9 calls with 8 slots, each 2 seconds against a 3 second deadline; the ninth must complete rather than time out. |
| V02 | Reproduces: `bool("\u200b".strip())` is true and `send_answer_feedback` treats that as a comment. | `adapters/mcp/server.py`: treat Unicode format-only feedback text as empty before the write, while retaining meaningful text. | `test_parity_tools.py`: store a rating, then send a zero-width-only comment and assert a refusal and the unchanged rating. |
| V03 | Reproduces: `_reopened_citations([], "Row [7]. Year [2023].")` reports one omission. Four-digit year is already excluded by the current regex; `[7]` is indistinguishable from an actually missing citation in the saved Markdown alone. The product owner chose to defer V03 until markers are distinguishable. | No change. Preserve the missing-citation signal instead of adding a word-based guess. | Existing `test_parity_tools.py` missing-marker count stays; a non-citation bracket test waits for unambiguous marker metadata. |
| V04 | Reproduces by inspection: `credentials.load()` rejects an insecure file with its path in the remedy; `main.py` copies stderr into the `sign_in_needed` JSON error. | `adapters/cli/main.py`: give an insecure-file refusal its own error class and fixed, path-free JSON wording; keep the existing actionable `chmod 600 <file>` on stderr. | `test_main.py`: `s3 ask --json` with a mode-0644 credential file must not contain the path on stdout, while stderr names the remedy. |
| V05 | Reproduces: `JsonRenderer.finish()` on no events exits 1 and writes `complete: false` with `error: null`. | `adapters/cli/render.py`: report an actionable error when the stream ends without any terminal event. | `test_main.py` or the renderer tests: a 200 empty stream exits 1 and has a non-null JSON error; a normal `done` still succeeds. |
| V06 | Already handled by card 62: `IntegrationsScreen.test.tsx` asserts the MCP card does not say "coming" and names the limitation. | None, outside this card's lane. | Existing `promises no schedule for the MCP follow-up offers` test. |
| V07 | Reproduces by inspection: renewal's `httpx.HTTPError` branch returns a "Could not reach" message and writes no stderr line. | `adapters/cli/mcp_bridge.py`: distinguish a decode failure from a network failure, give a next step and log one safe diagnostic line. Leave renewal refusal handling untouched. | `test_mcp_bridge.py`: malformed gzip on the refresh reply gets a decode-specific agent message and a safe stderr line without tokens. |
| V08 | Reproduces: both `PastSearch` and `ReopenedAnswerOutput` schemas publish `asked_at` as a date-time string without `maxLength`. | `adapters/mcp/server.py`: bound both datetime output fields without changing their serialized value. | `test_parity_tools.py`: both generated schema properties have the limit and still serialize a normal timestamp. |
| V09 | Reproduces: `_shape_of` returns `None` for a JSON-RPC request with `"params": null`; the MCP SDK can parse it. Marked unsure; leave unbuilt. | `adapters/cli/mcp_bridge.py`: no change until production-server compatibility is decided. | Proposed interoperability test for null parameters, pending the product owner's decision. |
| V10 | Already handled by card 62: `MCP_STDIO_CONFIG` names a full virtual-environment executable path. | None, outside this card's lane. | Existing `tells the reader to put the full path to s3` test. |

## Review refinement

The lead's judge and adversary found four blocking gaps in the first implementation. Each follow-up below went red before its fix and green after it.

| Finding | Refined behavior | Test |
|---|---|---|
| V01 | Keep a fresh deadline after slot acquisition, but cap the wait for a slot separately at one minute. A timed-out queued request gets a busy error without reaching the server. | 24 requests through eight slots: the third wave gets one busy reply per request before it can be forwarded. |
| V04 | Distinguish a mode-0600 file in a 0777 or 0770 credential folder from an insecure file. A folder without owner access and a directory at the credential-file path also get their own path-free remedies. | Temporary folders at 0777, 0770 and 000, plus a directory in place of the credential file. |
| V05 | An interrupted JSON run says the person stopped it, not that its stream or network failed. | Signal interruption during an in-flight JSON run; the genuine JSON renderer reports `interrupted` and exit 130. |
| V07 | An unreadable HTTP 200 renewal may follow server-side token rotation. Never recommend retrying a spent refresh token: tell the person to run `s3 login` on stdout and stderr. | Real malformed gzip response on the renewal endpoint; exactly one refresh call and no forwarded MCP request. |

Smaller review checks: V02 now rejects isolated variation selectors, combining marks, Hangul fillers and NUL. V04's unreadable-file JSON remedy now agrees with stderr. All changes keep the production-server wire contract intact.

## Compatibility and boundaries

- The bridge may not rely on a develop-only server behavior. In particular, do not change the renewal refusal handling reserved for card 75.
- Tests use fake transport, fake credentials and local schemas. Do not send live questions or create production accounts.
- Run the five Python gates named in Factory onboarding after implementation, followed by document drift and the publication leak check.

## Questions

- V03: The product owner chose to defer this finding until the producer supplies unambiguous marker metadata. The current missing-citation count stays in place.
- V09: The SDK accepts `"params": null`, but the bridge's current filter and the production server may disagree. Recommendation: leave the filter as is in this card until a production-compatible request contract is confirmed.
