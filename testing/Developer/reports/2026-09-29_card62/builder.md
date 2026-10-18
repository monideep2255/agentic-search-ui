# Card 62 builder report: install and connect on the first try

Branch `fix/card62-install-first-try`. Five fix commits were already on the branch when this run began. This run merged `origin/develop` (clean, no conflicts), mapped each defect to its fix and test, and ran the gates. No source or test file was changed.

## Table of contents

- [The five defects](#the-five-defects)
- [Test results](#test-results)
- [Not done](#not-done)

## The five defects

All five have a fix and a test that asserts it. Line numbers are in the merged tree.

| Defect | Fix commit | Fix lines | Tests |
|--------|-----------|-----------|-------|
| 1. KGX command not in the installed package (PR-8.10-03) | 4f749a7f | `frontend/src/components/screens/InfoScreens.tsx` 239 (`KGX_EXAMPLE` installs the server's own package first), card body at 736 | `tests/system_03_search_agent/test_integrations_page_claims.py` `test_every_printed_command_comes_with_the_install_the_page_prints_for_it` (423) and `test_every_printed_command_parses_as_printed`; `IntegrationsScreen.test.tsx` "says s3-kgx-export is not in the s3 install, and how to get it" and "installs s3 into a new virtual environment, and the KGX copy installs the server's own package" |
| 2. Page names neither Python 3.11 nor a virtualenv (PR-8.10-04) | 4f749a7f | `InfoScreens.tsx` 199 (`INSTALL_EXAMPLE` makes and enters `s3-env`), card body at 736 ("Python 3.11 or newer") | `test_the_python_version_the_card_states_is_the_one_the_install_needs` (495); `IntegrationsScreen.test.tsx` "says what the install needs: Python 3.11 or newer and a virtual environment" |
| 3. Desktop agent app cannot find bare `s3` (PR-8.10-09) | 4f749a7f for the page, 47929be9 for the CLI help | `InfoScreens.tsx` 225 (`"command": "/path/to/s3-env/bin/s3"`), card body at 736; `src/system_03_search_agent/adapters/cli/main.py` 749 (`s3 mcp --help` says to use the full path) | `test_the_agent_configuration_names_s3_by_a_full_path` (479); `IntegrationsScreen.test.tsx` "tells the reader to put the full path to s3 in the agent configuration"; `adapters/cli/test_s3_as_printed.py` `test_s3_mcp_help_says_to_name_s3_by_its_full_path` (776) |
| 4. `[ask]` under a finished answer with no trust line (PR-8.10-01) | 731ac19a | `src/system_03_search_agent/adapters/cli/render.py` 271 (web's caution text), 655 (`_tag_word`: a finished answer is tagged `answer`), 851 (tag printed), 855 (`_write_trust_line`), 927 and 1087 (called from done and from finish) | `adapters/cli/test_s3_as_printed.py` `test_an_unconfirmed_answer_reads_answer_with_its_trust_line` (697), plus the every-trust-line, web-caution, question-back-still-reads-ask, sanitized and JSON-unchanged tests beside it; `adapters/cli/test_render.py` adjusted |
| 5. Guest over MCP told the token is malformed (PR-8.10-11) | b09559a3 | `src/system_03_search_agent/adapters/mcp/server.py` 198 to 226 (three messages that say an account is needed and how to get a token), 846 and 852 (raised at the same two checks); `adapters/cli/mcp_bridge.py` 250 (renewal match still holds, the words "bearer token" are kept) | `adapters/mcp/test_no_cost_and_auth.py` `test_no_token_says_an_account_is_needed` (538), `test_a_header_without_the_bearer_scheme_is_called_malformed`, `test_a_token_that_does_not_verify_is_called_invalid` (552), `test_a_real_guest_token_is_told_an_account_is_needed` (560); `adapters/mcp/test_parity_tools.py` adjusted |

Commit bc898f39 also removes the MCP card's "next" promise for follow-up offers (fix in `InfoScreens.tsx`, test "promises no schedule for the MCP follow-up offers, and claims no parity"). It belongs to the same card and is not one of the five.

## Test results

Run from the worktree with the main checkout's virtualenv. Every process was polled to exit.

| Run | Result |
|-----|--------|
| `tests/system_03_search_agent/adapters/cli/`, `adapters/mcp/`, `test_integrations_page_claims.py` | 426 passed, 2 warnings in 19.47s |
| `IntegrationsScreen.test.tsx` via vitest from `frontend/` | Test Files 1 passed (1), Tests 16 passed (16) |
| Full unit suite, `.github/gates/gate04_unit_suite.sh` (`pytest -m "not integration"`) | 6516 passed, 143 skipped, 24 deselected, 1 xfailed, 7 warnings in 284.47s (0:04:44), exit 0 |
| `ruff check .` | All checks passed! |
| `isort --check-only --diff src tests services tracker alembic .claude .github` (gate02) | no diff, "Skipped 2 files" |

The 143 skips are the live-network and `RUN_PREMISE_GATE` tests. The unit suite did not need the local user database in this run, and it passed without one being set up.

## Not done

- No push, as instructed.
- The worktree's `frontend/node_modules` is a symlink to the main checkout's packages and is untracked. It is not committed.
- Nothing was run against the live product (a real desktop agent app or a real guest token over HTTP). The page claims are checked by tests against the page source and the tool's printed output, not by the owner's retest.
