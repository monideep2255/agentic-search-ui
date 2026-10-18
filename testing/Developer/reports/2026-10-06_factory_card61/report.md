# Card 61: Command line and MCP bridge edge cases

A queued MCP request gets its full exchange time after a slot opens, but it cannot wait without limit for a slot. Invisible-only feedback no longer replaces an earlier rating. JSON names the right credential file or folder remedy, and distinguishes a person stopping a search from a broken stream. An unreadable renewal reply says to sign in again, not to retry a possibly spent token. Past-answer timestamps have bounded output schemas. These changes use the existing production server contract.

## Table of contents

- [What changed](#what-changed)
- [Red and green evidence](#red-and-green-evidence)
- [Review follow-up](#review-follow-up)
- [Findings not changed](#findings-not-changed)
- [Checks](#checks)
- [Not covered](#not-covered)

## What changed

| Finding | Files | Person-visible result |
|---|---|---|
| V01 | `adapters/cli/mcp_bridge.py`, `test_mcp_bridge.py` | The wait behind eight active requests no longer spends the ninth request's own answer deadline. A separate one-minute queue limit stops a deep backlog from waiting without bound. |
| V02 | `adapters/mcp/server.py`, `test_parity_tools.py` | Isolated zero-width characters, variation selectors, combining marks, Hangul fillers and controls are refused before they can replace a rating. Real letters and emoji remain valid. |
| V04 | `adapters/cli/credentials.py`, `adapters/cli/main.py`, CLI tests | JSON distinguishes a file needing `chmod 600` from a folder needing `chmod 700`, a directory occupying the credential-file path, and a file that cannot be read. It never publishes the absolute path; stderr keeps the file-specific remedy. |
| V05 | `adapters/cli/main.py`, `adapters/cli/render.py`, CLI tests | A 200 stream with no final event gets `stream_incomplete`. Ctrl-C gets `interrupted` with exit 130 instead of a connection-failure claim. |
| V07 | `adapters/cli/mcp_bridge.py`, `test_mcp_bridge.py` | An unreadable renewal reply tells the person to run `s3 login` on the agent-facing text and stderr. It never suggests retrying a potentially spent token. |
| V08 | `adapters/mcp/server.py`, `test_parity_tools.py` | Both `asked_at` output schemas state a 40-character bound for their serialized date-time string. Normal timestamps still serialize unchanged. |

The per-finding plan, including the production-server boundary, is in `plan.md`. Each built finding has its own commit.

## Red and green evidence

| Finding | Without its fix | With its fix |
|---|---|---|
| V01 | A ninth 0.22-second call through eight slots timed out against a 0.31-second exchange budget while queued. The new test saw error code -32002 rather than a result. | The ninth succeeds after its slot opens. The existing stuck-request, exchange-timeout and shielded-renewal tests also pass. |
| V02 | A call carrying only U+200B returned `recorded: true` after an earlier rating, rather than refusing it. | The same database-backed test rejects format-only comments and reasons, and keeps the earlier rating. |
| V04 | Mode-0644 and corrupt credential files both returned `sign_in_needed` in JSON; stderr text containing the absolute file path was also copied into JSON. | Both cases have a distinct, path-free JSON class and message. The path and actionable remedy stay on stderr. |
| V05 | An empty 200 event stream returned exit 1 with `complete: false` and `error: null`. | JSON has `stream_incomplete`, a reason and a retry instruction. A normal complete stream still exits 0. |
| V07 | A simulated `httpx.DecodingError` during renewal said "Could not reach" and did not log the decode failure. | A real malformed-gzip HTTP 200 renewal now gets one safe diagnostic, one answer naming `s3 login` and no second refresh call. No token or untrusted exception text is printed. |
| V08 | Both `asked_at` schema properties lacked `maxLength`. | Both report 40 and still serialize a normal timestamp. |

## Review follow-up

| Finding | Red without the review fix | Green with the review fix |
|---|---|---|
| V01 | In a 24-call queue through eight slots, the third wave succeeded after waiting longer than the stated limit. | The third wave gets a busy error without reaching the server; each request receives exactly one reply and all slots return. |
| V04 | A mode-0600 file in a 0777 or 0770 folder got the wrong JSON remedy, `chmod 600` on the file. A 000 folder and a directory at the file path said only to run `s3 login`. | Folder permissions call for `chmod 700`; a directory at the file path must be moved aside. Both stdout remedies are path-free, while stderr names the location. |
| V05 | Ctrl-C during `s3 ask --json` returned `stream_incomplete`, claiming a connection problem. | The genuine JSON renderer returns `interrupted` and a message that the person stopped the search. An empty 200 stream retains `stream_incomplete`. |
| V07 | An HTTP 200 renewal with unreadable gzip said to try again, risking reuse of a rotated token. | It makes one refresh call, forwards no MCP request, and tells the person to sign in again with `s3 login` in both channels. |
| V02 and V04 smaller cases | An isolated variation selector was stored as feedback. An unreadable-file JSON remedy differed from stderr. | The expanded feedback test preserves the earlier rating for four more invisible-only inputs. The unreadable-file remedy now names the same next step on both channels. |

## Findings not changed

| Finding | Outcome |
|---|---|
| V03 | Deferred by the product owner. `Row [7]` and a missing citation `[7]` are indistinguishable in stored Markdown without marker metadata. The four-digit `Year [2023]` was already excluded by the current one-to-three-digit pattern. Keep the existing missing-citation count rather than guess from a word list. |
| V06 | Card 62 already removed the "coming to MCP next" promise. Its existing no-schedule test passed on the merged card 47 worktree, whose named test and component match develop; the card 61 worktree has no frontend dependencies installed. |
| V09 | Left unbuilt as assigned. The bridge rejects `"params": null`; the MCP SDK parses it, but production-server acceptance has not been established. Recommendation: retain the current filter until a production-compatible request contract is confirmed. |
| V10 | Card 62 already prints a full executable path in the agent configuration. Its existing full-path test passed in the same merged card 47 worktree. |

## Checks

| Command | Result |
|---|---|
| `PYTHONPATH=src bash .github/gates/gate01_compile_and_import.sh` | Passed. |
| `bash .github/gates/gate02_import_order.sh` | Passed, 2 files skipped by that gate. |
| `bash .github/gates/gate03_lint.sh` | Passed. |
| `bash .github/gates/gate04_unit_suite.sh` | Passed: 7,000 tests, 143 sanctioned skips, 24 deselected, 1 expected failure, 7 warnings. |
| `bash .github/gates/gate04b_no_unsanctioned_skips.sh` | Passed: 7,144 cases accounted for, every skip sanctioned. |
| `npm test -- src/components/screens/IntegrationsScreen.test.tsx -t 'promises no schedule|tells the reader to put the full path'` | Passed: 2 tests in the merged card 47 worktree. Not run in the card 61 worktree because its frontend packages are not installed. |
| `python3 tracker/check_doc_drift.py --check` | Passed: 2 facts computed, 0 stale or structural findings. |
| `python3 .claude/skills/ship/scripts/check_public_leaks.py --base origin/develop` | Passed: 0 findings, no binary files. |

## Not covered

- Live questions and production-server calls. Tests use a fake HTTP transport and temporary credentials; no production account, server change or migration was needed.
- V03 and V09, by decision and scope respectively. The lead and product owner still decide whether either needs a later card.
- Browser screenshots at 390 and 1280 pixels: this card changes no screen, so none were taken.
