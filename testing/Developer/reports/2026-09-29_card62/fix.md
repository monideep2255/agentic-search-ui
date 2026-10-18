# Card 62 fix round, 2026-09-29

The single fix round after the judge (`judge.md`, F-62-J01 to J07) and the adversary (`adversary.md`, F-62-A01 to A09). One agent held every finding, by file, per Review_rounds Rule 1. Each control was fixed by category (Rule 2), then broken once to see a test go red, then restored. Local only: no request to the deployed develop or production apps.

## Table of contents

- [Commits](#commits)
- [Findings](#findings)
- [Decision 3: the KGX copy](#decision-3-the-kgx-copy)
- [Break-it results](#break-it-results)
- [Gates](#gates)
- [Left open, and why](#left-open-and-why)
- [After the fresh verifier, 2026-09-29](#after-the-fresh-verifier-2026-09-29)

## Commits

| Commit | Subject | Findings |
|--------|---------|----------|
| `ca824254` | fix(cli): s3 shows only the verdict the server sent, with the web's cautions | J04, J05, A01, A02, A05, A08, A09 |
| `3842019f` | fix(mcp): an agent's bad argument no longer tells the person to log in again | A06, J06 |
| `f3d0feba` | fix(web-ui): the Integrations page install works first try and installs only s3 | J01, J02, J03, J07, A03, A04, A07 |

## Findings

### The trust line in `s3` (`adapters/cli/render.py`)

What a person sees now: the tag and the one trust line come from the server's final verdict, the same `done` the web, `--json` and the exit code read. A run that did not finish shows no verdict at all, only the web's words "Not verified · the run did not finish". A question back reads `[ask]` and never carries a trust line. "Not fully grounded" and the risk mark sit on the trust line as they do on the web.

The change, by category:

- One source for the verdict: `_handle_trust_signal` prints nothing now. It records whether every signal was grounded and every risk tier, claim and answer scope alike, as `useRunView.ts` does. `_write_verdict`, called only from `_handle_done` with `done.trust_outcome` and `done.trust_line`, prints the tag and the line once.
- Nothing composed by `s3`: `finish()` no longer prints any trust line. A fatal error, or a stream that ended before `done`, gets `_write_unfinished_notice` and no tag.
- A question back is its own state: `_is_question_back(verdict)` is decided from the server's `refuse` verdict plus `_is_ask_back`. The server's `ask` verdict reads `[answer]` with its caution. The old `_tagged_outcome`, which held both as `"ask"`, is gone.
- One-line server text: `_single_line` replaces every character whose Unicode category is `Cc`, `Cf`, `Cs`, `Co`, `Zl` or `Zp` with a space, collapses only runs of spaces, and still escapes the renderer's own `[answer]` and `References:`. It covers the trust line and a risk tier.

| Finding | Fixed | Test |
|---------|-------|------|
| F-62-J04, "Single source" invented on a cut-off run | Yes. No `done`, no tag and no caution; the notice prints above the references | `test_s3_as_printed.py::TestARunThatDidNotFinishGetsNoVerdict::test_a_cut_off_answer_prints_no_tag_and_no_caution` |
| F-62-J04 note, a token glued to the trust line | Yes, by construction: the tag and line print together from `done`, after every token, behind the tag's leading newline | `test_render.py::TestTrustPrefixOwnLine` (now drives `done`) |
| F-62-J05, "printed at most once" unpinned | Yes. One `_printed_verdict` flag covers the tag and the line | `TestTheVerdictIsPrintedOnce` (two `done` events; nothing follows the references) |
| F-62-J05, `finish()` call unpinned | Yes. The call is gone; `finish()` prints only the notice, which is pinned | `TestARunThatDidNotFinishGetsNoVerdict` |
| F-62-J05, refusal guard defence in depth | Yes. A `refuse` verdict never gets a line, and a question back is a `refuse` verdict | `TestAQuestionBackIsItsOwnState::test_a_question_back_never_carries_a_trust_line` |
| F-62-A01, question back then fatal error printed "Single source" | Yes. No `[ask]`, no caution, one notice, exit 1 | `TestARunThatDidNotFinishGetsNoVerdict::test_a_question_back_that_is_stopped_claims_no_source` |
| F-62-A02, the web's two cautions dropped | Yes. "Not fully grounded" first when any signal is ungrounded; "High-risk claim" or "<tier> risk claim" last | `TestTheWebsTwoCautionsAppearBesideTheLine` (5 tests) |
| F-62-A05, tag from the first signal, not `done` | Yes. All three disagreeing shapes now follow `done` | `TestTheVerdictComesFromDone` (3 tests) |
| F-62-A08, positive line after a fatal error | Yes. `_write_verdict` returns on a fatal error; the notice prints instead | `TestARunThatDidNotFinishGetsNoVerdict::test_a_fatal_error_then_done_never_prints_the_positive_line` |
| F-62-A09, a newline in the trust line forged a reference row | Yes, by category | `TestAServerStringOnALineStaysOneLine`, parametrized over `\n`, `\r`, `\x0b`, `\x0c`, `\x85`, U+2028, U+2029, ESC and U+202E, plus a risk tier |

Two choices worth reading:

- The web ranks an `unknown` risk tier above `high`, then hides `unknown`, so one `unknown` claim signal beside a `high` one shows no risk mark on the web. `s3` ignores `unknown` instead, so it never hides a `high`. That is a web defect, outside this card's files, and is named in "Left open".
- For a run cut off before `done` with no fatal error, the web shows its failure screen, not a trust line. `s3` prints the same "Not verified · the run did not finish" it prints after a fatal error, on stdout, so a reader of a redirected file learns what stderr said. It is never a verdict, and it replaces the tag rather than sitting under one.

Three existing tests changed with the behaviour, each named in the commit:

- `test_render.py::test_flag_and_ask_outcomes_...` now expects "· High-risk claim", since its signal is `high`.
- `TestTrustPrefixOwnLine` now sends `done`.
- `test_the_trust_line_is_sanitized_like_any_server_text` now expects the control character removed rather than escaped.

### The MCP bridge and server (`adapters/cli/mcp_bridge.py`, `adapters/mcp/server.py`)

What a person sees now: an agent that sends an argument named "bearer token" gets back "unknown argument: this tool accepts only audience_depth, query, session_id. Remove any other argument and try again." The agent does not get "run s3 login", and no refresh rotation is burned.

| Finding | Fixed | Change | Test |
|---------|-------|--------|------|
| F-62-A06, a bad argument read as a refused sign-in | Yes | The server sets `data: {"reason": "sign_in_refused"}` on its sign-in refusals and on nothing else (`_sign_in_refused`). `_is_token_refusal` requires the INVALID_REQUEST code AND that field, and never reads the message. `_reject_unknown_arguments` names the tool's own accepted arguments and never echoes the caller's | `test_mcp_bridge.py::TestOnlyTheStructuredFieldMeansSignInRefused` (end to end through the real `McpBridge`, plus 5 structure cases); `test_no_cost_and_auth.py::TestOnlyARefusedSignInCarriesTheSignInField::test_an_argument_named_bearer_token_is_not_a_sign_in_refusal` and `test_every_sign_in_refusal_carries_the_field`, through the real streamable HTTP transport, which shows `data` survives it |
| F-62-J06, two Authorization headers read as none | Yes | New fixed `_DUPLICATE_HEADER_MESSAGE`, "malformed bearer token: the request carried more than one Authorization header..." | `test_two_authorization_headers_are_named_as_two` |
| F-62-J06, `Bearer ` with nothing after it read as invalid | Yes | Checked before the database, and gets the malformed message | `test_the_scheme_with_no_token_after_it_is_malformed` |

The security properties J06 confirmed still hold:

- Every message is a fixed constant.
- No token or exception text is in a message.
- A guest, an expired and a garbage token get the same words; the existing `TestARefusedTokenSaysWhatToDo` still passes.

Every refusal keeps the words "bearer token" for copies of `s3` installed before this change. Those copies still match on words, so they keep their old behaviour.

### The Integrations page (`frontend/src/components/screens/InfoScreens.tsx`)

| Finding | Fixed | Change | Test |
|---------|-------|--------|------|
| F-62-J01, `python3` is macOS's 3.9 | Yes | The first copied line is `python3.11 -m venv s3-env`. The card says to install 3.11 if `python3.11 --version` fails, or to put a newer Python's name in that line | `test_integrations_page_claims.py::test_the_python_version_the_card_states_is_the_one_the_install_needs` (the line must be `python<requires-python floor>`); vitest "installs s3 with python3.11 ..." |
| F-62-J07, POSIX only, unsaid | Yes | The card says "works on macOS and Linux" before the commands | vitest "says what the install needs, before the commands", which also checks the sentence sits before the install button in the DOM |
| F-62-A03, git needed, unsaid | Yes | "needs git and Python 3.11" | the same two tests |
| F-62-A04, `command -v s3` prints nothing in a new terminal | Yes | "In a new terminal, enter it again with . s3-env/bin/activate from the same folder before s3 login or s3 ask." The full-path sentence now ends "prints inside the virtual environment, after . s3-env/bin/activate" | vitest "says how to enter the environment again..."; the claims test's full-path arm |
| F-62-J02, root install with version floors | Yes, by removal (decision 3) | `KGX_EXAMPLE` and its copy button are gone | `test_the_page_installs_only_s3_exactly_pinned`: every `pip install "..."` on the page is `clients/system3-cli`, and every dependency there is `name==version` |
| F-62-J03, the KGX copy only worked inside the venv | Yes, by removal | No KGX command is printed to copy | `test_the_page_says_how_a_kgx_file_is_had_today`; vitest KGX arm checks no `integration-copy-kgx` exists |
| F-62-A07, the KGX package owned `s3`'s files | Yes, by removal | The page installs one package | `test_the_page_installs_only_s3_exactly_pinned` |

The page's install, run as printed in a scratch venv with `python3.11` and a `git+file://` URL of this branch standing in for GitHub:

- It exited 0.
- `s3 --help` exited 0.
- `pip check` printed "No broken requirements found."
- A fresh shell had no `s3` until `. s3-env/bin/activate`. After it, `command -v s3` printed the venv's `bin/s3`, which is the case the new sentences cover.

## Decision 3: the KGX copy

Chosen: replace the install copy with one plain sentence. The card now reads: "s3-kgx-export is not in that install and has no download: it reads the knowledge graph directly with credentials only the operator holds, so today a KGX file comes from the operator, who runs it for the seed CURIEs you name."

What an outsider can do today, from reading the code:

- There is no HTTP route for KGX. `frontend/src/stubs/registry.ts` says so, and `test_every_http_path_the_page_prints_is_a_real_route` exists because `POST /v1/export/kgx` was once advertised and never built.
- There is no web download.
- `export/cli.py` reads the graph through `tools.graph_connection` with the four `GRAPH_PG_*` variables, which only the operator holds. The judge's own run of the page's export line refused for exactly that reason.

So an outsider could never produce a KGX file themselves, whatever the install.

Why not the pinned install:

- The only package that ships `s3-kgx-export` is the repository root, which ships all of `system_03_search_agent`, including `adapters/cli`, and so owns `s3`'s files.
- A separate exporter package would need a new `clients/` package that ships `export/` and `tools/`, while leaving out `system_03_search_agent/__init__.py`, which `system3-cli` owns.
- It would also need an exactly pinned lock of the graph stack, psycopg2 and its neighbours, and a fresh-venv install and uninstall proof.
- All of that buys a command no outsider can run.

From the user's chair: one true sentence beats an install that works and then refuses for want of a credential.

## Break-it results

Each control was broken once in the worktree by a script that restored the file and checked it byte-for-byte afterwards. The script and its mutation lists are in the scratchpad, never committed. All went red.

`render.py`, against `tests/.../adapters/cli`:

| Mutation | Went red in |
|----------|-------------|
| Tag printed from the first answer-scope signal again | `test_flag_and_ask_outcomes_...` |
| Verdict printed after a fatal error | `test_a_fatal_error_then_done_never_prints_the_positive_line` |
| Notice dropped from `finish` | `test_a_cut_off_answer_prints_no_tag_and_no_caution` |
| The server's `ask` tagged `[ask]` again | `test_flag_and_ask_outcomes_...` |
| `_is_question_back` returns False | `test_same_stream_same_exit_code[question-back]` |
| "Not fully grounded" dropped | `test_an_ungrounded_claim_says_not_fully_grounded` |
| Risk mark dropped | `test_flag_and_ask_outcomes_...` |
| Only answer-scope signals read | `test_an_ungrounded_claim_says_not_fully_grounded` |
| `Zl` and `Zp` dropped from the categories | the U+2028 case |
| `Cf` dropped | the U+202E case |
| Only `\n` removed | `test_the_trust_line_is_sanitized_like_any_server_text` |
| Forgery escape dropped from `_single_line` | the same test |
| Printed-once flag removed | `test_a_second_done_prints_no_second_verdict` |
| `unknown` hides `high`, the web's ranking | `test_an_unknown_tier_never_hides_a_high_one` |
| Notice flag removed | `test_finish_is_idempotent_...` |
| Old `finish` fallback put back | `test_finish_prints_a_truncation_notice_...` |
| `ask` with no line loses its caution | `test_flag_and_ask_outcomes_...` |

Two first mutations stayed GREEN. Both were controls that did nothing, so the code was changed rather than the test:

- `not question_back` beside `verdict != "refuse"` was redundant, since a question back is always `refuse`. It was removed, and the `_is_question_back` mutation above replaced it.
- `" ".join(kept.split())` also split on U+2028, so `Zl` and `Zp` in the category set were not load-bearing. Only spaces are collapsed now, which makes the category check the one control.

`mcp_bridge.py` and `server.py`:

| Mutation | Went red in |
|----------|-------------|
| Match "bearer token" in the message again | `test_the_decision_reads_structure_not_words[error0-True]` |
| Code check dropped | `[error3-False]` |
| Echo the unknown names | `test_an_argument_named_bearer_token_is_not_a_sign_in_refusal` |
| Sign-in field on the unknown-argument error | the same test |
| Refusal without the field | `test_no_token_says_an_account_is_needed` |
| Two headers read as none | `test_two_authorization_headers_are_named_as_two` |
| Empty token not malformed | `test_the_scheme_with_no_token_after_it_is_malformed` |

`InfoScreens.tsx`, against the claims test and vitest:

| Mutation | pytest | vitest |
|----------|--------|--------|
| Bare `python3` | red | red |
| Git and platforms dropped | red | red |
| New-terminal sentence dropped | green | red |
| Full-path location dropped | red | red |
| Root install put back | red | red |
| KGX sentence dropped | red | red |

## Gates

Each command below ran to exit in the worktree:

| Gate | Command | Result |
|------|---------|--------|
| Touched adapters | `pytest tests/system_03_search_agent/adapters/cli tests/system_03_search_agent/adapters/mcp tests/system_03_search_agent/test_integrations_page_claims.py` | 464 passed |
| Page, vitest | `npx vitest run src/components/screens/IntegrationsScreen.test.tsx` | 17 passed |
| Full unit suite, as gate04 runs it | `pytest -m "not integration" -q -rs` | 6554 passed, 143 skipped, 24 deselected, 1 xfailed, exit 0 |
| Frontend build | `npm run build` | exit 0 (the existing chunk-size warning only) |
| Lint | `ruff check .` | All checks passed! |
| Imports | `isort --check-only --diff src tests services tracker alembic .claude .github` | exit 0 |

## Left open, and why

- `.claude/skills/verify/scripts/facts_registry.py`, fact `surfaces.kgx_options`, reads `export const KGX_EXAMPLE`, which this fix removed. `check_facts.py` now reports one more ERROR line for it ("pattern ... finds nothing ... update the registry"). The file is under `.claude/`, outside this round's fence. The facts check was already NOT PASSED before this change, with 9 ERROR and 19 FAIL lines about other pages, and card 53's worktree is on that registry. The fix is to drop that stated site, or point it at the page's sentence.
- `frontend/src/stubs/registry.ts`, entry `kgx-export`, still says the page's code block is the `s3-kgx-export` invocation, "copyable with the card's own copy control". It is internal text, not shown on the Integrations page, and outside this round's fence.
- The web's risk ranking puts `unknown` above `high` and then hides it (`frontend/src/hooks/useRunView.ts`, the `rank` in the trust block), so one `unknown` claim signal can hide "High-risk claim" on the web. `s3` does not copy that. It is outside this round's fence and worth its own card.
- `s3 ask --json` is unchanged, since it is the contract. After a fatal error followed by `done` it still reports that `done`'s `trust_outcome` and `trust_line`, beside its `error` object. The human output no longer does.
- Transition: `s3 mcp` built from this branch renews a refused sign-in only when the server sends the new field. Against a server without it, production until its next release, a refusal that the bridge's proactive renewal did not prevent reaches the agent in the server's own words, which say how to sign in, instead of a silent renewal. The proactive renewal, 60 seconds before expiry, covers ordinary expiry either way.

## After the fresh verifier, 2026-09-29

The fresh verifier (`verifier.md`) found every judge and adversary finding fixed, and one regression inside this round's MCP fix, F-62-V03: `s3 mcp` renewed an expired sign-in only when the refusal carried `data.reason`, which production does not send, and `s3` talks to production by default. The review loop allows no third round, so the product owner chose between the two options it allows and dropped the commit: `3842019f` is reverted by `16572df9`, and the rest of this round merges.

What that leaves open, named:

- F-62-A06 and F-62-J06 are open again. They become their own card, which lands the server's refusal field first and the client change after it, so no installed client ever waits on a server that does not send the field.
- F-62-V01, V02 and V04 are minor and named open: a `done` with a trust line but no trust signal prints the line, `s3 ask --json` reports `complete: true` after a fatal error, and a `flag` verdict prints `[flag]` where the web says "Answered".
- The facts checker reads the removed `KGX_EXAMPLE` (`surfaces.kgx_options`); card 53 owns the checker and drops or rewrites that fact when the two cards meet on develop.
