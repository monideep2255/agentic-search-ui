# Build phase 8.10: the integrations work for someone outside the project

Branch: `phase/8.10-integrations`, cut from `develop` at 00f45e8 on 2026-09-26. Status: open.

The phase comes from the product owner's ask of 2026-09-26 (card 49 of `testing/UI_fix_plan.md`): "make sure that the integrations that we have such as the MCP, the API, ... the command line tools and all that, everything on the integration page. That is also updated" and "that MCP should be able to do everything that is done on the web, but now from the command line ... or ask another AI agent to have that MCP and run those questions."

Two decisions of the same evening shape it (`DECISIONS.md`, 2026-09-26):

- The MCP server gets full parity with the web app, overruling the locked specification's Section 13.2 for MCP. The specification itself stays locked.
- People outside the project get the MCP server and the command line through one small published package, `system3-cli`. It is published only after the client ignores unknown fields, is split from the server's dependencies and passes a review. Every release is the owner's yes.

The diagnosis this phase builds on is `testing/Developer/reports/2026-09-26_integrations_audit/report.md`. Where it disagrees with the code, the code wins.

## Table of contents

- [Goal contract](#goal-contract)
- [Budget](#budget)
- [Tickets](#tickets)
- [Builder split](#builder-split)
- [Dispatch plan](#dispatch-plan)
- [Review focus](#review-focus)
- [Out of scope, and why](#out-of-scope-and-why)
- [Decisions this plan takes](#decisions-this-plan-takes)
- [History](#history)
- [Findings](#findings)

## Goal contract

### Done when

1. Every ticket below meets its acceptance, and each builder's report pastes its test command's result line.
2. CI is green on the pull request, including the new check that installs the packages and runs their commands.
3. One judge round and one adversary round, then one fix-and-verify round, leave nothing blocking.
4. The audit's smoke script (`testing/Developer/reports/2026-09-26_integrations_audit/integrations_smoke.py`) passes every line against develop after the merge. Today it fails two: `kgx` and `page`.
5. Nothing that works today gets worse, the product owner's standing rule of 2026-09-26. The REST and event stream path, which the web app uses, is unchanged byte for byte. The existing adapter suites for cli, graphql, mcp and web_sse still pass.

### Verify

- Each builder: its ticket's test command, `ruff check` over the whole repository, `isort` as CI's gate 2 runs it, and the unit suite as `bash .github/gates/gate04_unit_suite.sh` runs it.
- The lead, before the pull request: the same gates, then the smoke script against a local stack of the branch.
- After the merge: the smoke script against develop, and the product reviewer's run of every surface.

### Output

- The pull request from `phase/8.10-integrations` to `develop`.
- The builders' reports in `testing/Developer/reports/2026-09-26_phase_8.10/`.
- A built `system3-cli` wheel proven to install and run in a clean environment. Nothing is published.

### Constraints

- Not answer path. No file under `core/`, `synthesis/`, `guardrail/`, `harness/` or `tools/` changes, so the golden consistency run is not required. Nothing merges to develop while another phase's golden run is running.
- The event contract, `contracts/events.py`, stays as it is on the server. The server keeps validating what it sends with `extra="forbid"`. Only a client reading the stream becomes lenient.
- Nothing is published to PyPI or anywhere else, and no name is registered. Publishing is the owner's yes, release by release.
- No new dependency beyond the MCP SDK the server already uses, `httpx` and `pydantic`. Every dependency of `system3-cli` is pinned exactly, per `.claude/rules/supply-chain-security.md`.
- History, reopen and feedback over MCP call the same service functions as the REST routes, with the same ownership checks. A caller never sees another account's history or answers.
- Public repository: no secrets, local paths, emails or tokens in anything committed.

### Blocked-stop

A builder stops and reports, rather than guessing, when:

- a change would need a file outside its fence;
- a test it did not write fails;
- a permission, hook or safety system refuses something. It never routes around one.

## Budget

- Wall clock: 8 hours from 22:08 UTC on 2026-09-26.
- Dial: position 3. The MCP server's response allowlist is a manual control approved by the owner on 2026-08-20, and this phase widens it on the owner's decision of 2026-09-26. A numbered phase keeps its branch and pull request anyway.
- Dispatches, 8 of 8 planned: builders P and Q now, builder R after both report, the judge, the adversary, one fix agent, a fresh verifier, and the product reviewer.

| Role | Model | Effort | Started | Ended | Tokens |
|---|---|---|---|---|---|
| builder P, T-8.10-01 to 04 | Opus 5.5 | default | 22:10 | 23:42 | 747,091 |
| builder Q, T-8.10-05 and 06 | Opus 5.5 | default | 22:10 | 23:10 | 598,199 |
| builder R, T-8.10-07 and 08 | Sonnet 5 | default | 23:33 | 23:56 | 329,279 |

## Tickets

### T-8.10-01: The command line tools install and start from a built package (audit gaps 5 and 14)

- Builder: P. Status: in-review.
- Acceptance, in the words a person would use:
  - "`s3-kgx-export --help` prints its help from an installed copy instead of crashing." Today it fails with `ModuleNotFoundError: No module named 'system_03_search_agent.observability'`.
  - "An installed server finds its own data files." `data/personas_v1.json` and `orchestrator/few_shot_examples.json` ship in the wheel.
  - "A package that leaves out a module fails CI, not a user." A new CI check builds every wheel this repository makes, installs each into a clean environment, and runs every console script with `--help`.
- Fence: `pyproject.toml`, a new gate script under `.github/gates/`, and its step in `.github/workflows/ci.yml`.
- Test command: the new gate script, run locally.

### T-8.10-02: A client reads tomorrow's stream without failing (audit gap 12)

- Builder: P. Status: in-review.
- Acceptance:
  - "An `s3` installed today keeps answering after the server adds a field or a new kind of event." A test feeds the client a frame of a known type carrying an extra field, and a frame of an unknown type. The answer still prints, and the unknown frame is skipped.
  - "The contract's promise is true." The `contracts/events.py` docstrings that say an older client ignores new optional fields become true of the Python client. The docstring text itself is left to the lead, since that file is outside every fence.
- Fence: `src/system_03_search_agent/adapters/cli/` and its tests.

### T-8.10-03: `s3` works as the page prints it (audit gaps 3 and 4)

- Builder: P. Status: in-review.
- Acceptance:
  - "`s3 login` asks for my email when I leave it off, instead of failing."
  - "`s3` talks to the live product unless I say otherwise." The default base URL is the public production API origin, from one named constant, and `--base-url` and `S3_BASE_URL` still override it. If the repository does not record production's API origin, the builder stops and asks the lead rather than guessing.
  - "`s3 ask --json` prints the whole answer as JSON": the answer text, citations with their URLs, the trust outcome, the clarifying question and its options, and the session id to continue with.
  - "A bare topic shows its clarifying options, numbered, so I can pick one." Today `s3` prints the question but not the options.
  - What is useful from the parked tag `parked/phase-8.4-2026-09-25` for `adapters/cli/` is taken from there and credited, not rewritten.
- Fence: `src/system_03_search_agent/adapters/cli/` and its tests.

### T-8.10-04: `system3-cli`, one small package that carries `s3` and a local MCP server (owner's decision, 2026-09-26)

- Builder: P. Status: in-review.
- Acceptance:
  - "I install one small package and get `s3` and an MCP server, without the whole backend." A separate distribution, `system3-cli`, lives under `clients/system3-cli/` with its own `pyproject.toml`. Its only dependencies are `httpx`, `pydantic` and the MCP SDK, pinned exactly. Installing its wheel into a clean environment pulls none of FastAPI, uvicorn, LangGraph, LiteLLM, psycopg2, Redis, SQLAlchemy, Alembic or Strawberry.
  - "I sign in once, and my AI agent can use System 3." `s3 mcp` runs a stdio MCP server. It forwards every tool the remote `/mcp/` server offers, using the sign-in `s3 login` stored, and renews the token itself before it expires.
  - "An agent that only runs commands can connect." A test drives `s3 mcp` over stdio with the MCP SDK's client: initialize, list tools, and call a tool against a stand-in server.
  - Built, never published. The builder's report shows the wheel's dependency list and a clean-environment install.
- Fence: a new `clients/system3-cli/` directory, plus `src/system_03_search_agent/adapters/cli/` if the split needs it. The wheel's contents come from the same source files as the server's, never a second copy that could drift.

### T-8.10-05: MCP does what the web does (owner's decision, 2026-09-26; audit gaps 6 to 10)

- Builder: Q. Status: in-review.
- Acceptance:
  - "An AI agent can ask for Plain language." `audience_depth` accepts every depth the web offers. The default stays Researcher, so existing clients see no change. `tests/system_03_search_agent/adapters/test_audience_depth_values.py` changes to cite the decision row.
  - "A long answer keeps every citation it points at." No marker in the answer text, such as [77], lacks its citation. The cap of 50 is raised to the bound the event contract already puts on one answer's citations, and a bound remains.
  - "An agent knows how to continue a conversation." The tool's input schema describes `session_id` and `audience_depth` in words an agent reads, and the result returns the session id to reuse.
  - "A bare topic gives the agent the clarifying options, and it is not labelled a refusal." The result carries `clarifying_options`, and the trust outcome for an ask-back is not `refuse`.
  - "The agent gets the same trust line the web shows."
  - "An agent can list my past searches, reopen an answer, and send feedback." New tools, each calling the same service functions as the REST routes `/v1/history`, `/v1/history/{trace_id}/answer` and `/v1/query/{run_id}/feedback`, under the same ownership checks. Each has a test proving one account cannot read or rate another's.
  - The response allowlist gains exactly the keys this ticket adds, each named in the ledger's History when added.
- Fence: `src/system_03_search_agent/adapters/mcp/`, its tests, and `tests/system_03_search_agent/adapters/test_audience_depth_values.py`.

### T-8.10-06: GraphQL keeps every citation and the clarifying options (audit gaps 6 and 9)

- Builder: Q. Status: in-review.
- Acceptance:
  - "A long answer keeps every citation it points at", as in T-8.10-05.
  - "A bare topic gives the clarifying options": the `ask` result carries them.
  - "The same trust line the web shows."
  - All additive. No existing field changes name or type.
- Fence: `src/system_03_search_agent/adapters/graphql/` and its tests.

### T-8.10-07: The Integrations page says what is true, and every command on it runs (audit gaps 1, 13 and the page's words)

- Builder: R, dispatched after P and Q report, so the page describes what they built. Status: in-review.
- Acceptance:
  - "The MCP config I copy connects and answers." It carries `"type": "http"` and an `Authorization` header, says how long a token lasts, and says how to get one.
  - "The page tells me how to install `s3`." Until the owner's first release, that is an install from this public repository's `clients/system3-cli` directory. The page never prints `pip install s3`, a stranger's package.
  - "The page says that KGX export needs graph access only the operator grants."
  - "The page says how a guest gets a token."
  - "The page lists the event kinds and fields the stream really carries."
  - Every sentence the audit's "The page's words" lists as false, stale or missing is fixed.
  - `/verify` at 1280 and 390 passes. The smoke script's `page` line passes.
- Fence: `frontend/src/components/screens/InfoScreens.tsx` and `IntegrationsScreen.test.tsx`.

### T-8.10-08: The About, Architecture and tour pages say what is true (card 51's first run)

- Builder: R, with T-8.10-07, since About and Integrations share `InfoScreens.tsx`. Status: in-review.
- Source: the stale facts on a screen in `testing/Developer/reports/2026-09-26_ui_facts/report.md`, found by the facts checker of pull request #118.
- Acceptance, each in the words a person reads:
  - "The tour names all four ways in, the MCP server included."
  - "The tour does not claim every example question comes from the evaluation set." Reword it; do not change the questions.
  - "About says what the Plan step does today": it picks the tools in code, and the graph query is written in Act.
  - "About says every step can ask a model," not four of five.
  - "About says a reworded sentence is judged by a model after the exact checks, and can be kept."
  - "About and Architecture name every live service layer 2 calls, PubChem and Pathogen Detection included."
  - "Architecture does not say the graph is read first." All three layers are read at once.
  - `check_facts.py` reports no FAIL on any screen. The document-only facts are the lead's, card 53.
- Fence: `frontend/src/components/screens/InfoScreens.tsx`, `ArchitectureScreen.tsx`, `frontend/src/lib/architectureFacts.ts`, `frontend/src/components/tour/OnboardingTour.tsx`, and their tests.

## Builder split

| Builder | Model | Tickets | Fence |
|---|---|---|---|
| P | Opus | T-8.10-01 to 04 | `pyproject.toml`, `.github/gates/`, `.github/workflows/ci.yml`, `src/system_03_search_agent/adapters/cli/`, `clients/system3-cli/`, their tests |
| Q | Opus | T-8.10-05 and 06 | `src/system_03_search_agent/adapters/mcp/`, `src/system_03_search_agent/adapters/graphql/`, their tests, `tests/system_03_search_agent/adapters/test_audience_depth_values.py` |
| R | Sonnet | T-8.10-07 and 08 | `InfoScreens.tsx`, `ArchitectureScreen.tsx`, `lib/architectureFacts.ts`, `tour/OnboardingTour.tsx`, and their tests |

P and Q share no file. The one contract between them: `s3 mcp` forwards whatever tools the remote server lists, so P never hard-codes Q's tool names.

## Dispatch plan

1. P and Q, in parallel, each in its own worktree from the pushed phase branch.
2. R, after P and Q report.
3. The judge and the adversary, on the merged branch.
4. One fix agent and a fresh verifier, only if a finding blocks.
5. The product reviewer, after the merge to develop: every surface run against develop with the smoke script, and the Integrations page at 1280 and 390.

## Review focus

### The judge

- Every acceptance line against the code and a test that fails when the behaviour is broken.
- Ownership on every new MCP tool: can one account read, reopen or rate another account's run?
- The client leniency: can a malformed or hostile frame now crash the client, or print something it should not?

### The adversary

- The confident wrong answer through a surface: a citation dropped while its marker stays, a Plain language answer that says more than its records, an ask-back shown as an answer.
- The token: does `s3 mcp` ever print, log or leak the stored sign-in? Does renewal fail open?
- The package: does the `system3-cli` wheel pull anything unpinned, or anything of the server's?

## Out of scope, and why

- Publishing `system3-cli`: the owner's yes, release by release.
- Long-lived personal tokens and OAuth on the remote server: an auth change the owner chose not to take first. The package's self-renewing sign-in covers the clients that can run a command.
- The follow-up offers on MCP: card 52's phase adds `next_steps` to every surface.
- History, reopen and feedback on GraphQL and `s3`: the owner's parity decision named MCP. Each is a later card if wanted.
- Wiring the smoke script into `/verify`: the lead does it once `chore/verify-facts` merges, since that branch owns the skill's files.

## Decisions this plan takes

- MCP's default depth stays Researcher. Plain language is there on request, so no existing client's answers change without asking.
- Until the first release, the page's install path is this public repository's `clients/system3-cli` directory, which works for anyone today without a published package.

## History

- 2026-09-26 22:08: branch cut from develop at 00f45e8, ledger written.
- 2026-09-26 22:10: builders P and Q dispatched from 8cd197d, in the worktrees `.claude/worktrees/p810p` and `p810q`.
- 2026-09-26 22:19: T-8.10-08 added for builder R, the screen facts the checker of pull request #118 found stale.
- 2026-09-26 23:10: builder Q finished T-8.10-05 and 06 (report `testing/Developer/reports/2026-09-26_phase_8.10/builder_Q.md`), merged as 29edcc9. Gates on its branch: ruff and isort clean, gate04 6190 passed with every database test run.
  - MCP accepts Plain language, keeps every citation up to the run's own bound of 100, returns the session id, labels an ask-back `ask` with its question and options, and returns the trust line. Three new tools list past searches, reopen an answer and send feedback, under REST's ownership checks.
  - GraphQL keeps every citation and gains the trust line and the clarifying question and options, all additive.
  - The lead's answers to its three questions:
    - `clarifying_question` stays, although the ticket did not name it. An agent needs the question's words to relay it, and it tells an ask-back from a hedged answer the way the web does.
    - GraphQL still labels an ask-back `refuse`, because its fold only lowers a verdict. It is named open here, since the new `clarifyingQuestion` lets a client show the question. One label on every surface comes with card 52's phase, which touches the clarifying options everywhere.
    - Builder R's brief says MCP has four tools and accepts Plain language.
  - Outside every fence, for card 54: the REST citations export and the answer capture still stop at 50 citations, so a reopened long answer points at markers with nothing behind them. The debugging guide's `server.py` row still says one tool; the lead fixes it before the pull request.
- 2026-09-26 23:42: builder P finished T-8.10-01 to 04 (report `testing/Developer/reports/2026-09-26_phase_8.10/builder_P.md`), merged as 9f06326 with no conflict.
  - Packages are discovered under `src/` and the two data files ship. The new package gate failed the old tree on 16 missing files and 27 modules that could not import, and both wheels pass after the fix.
  - `s3` reads tomorrow's stream: unknown keys are dropped, and unknown event types are skipped.
  - `s3 login` asks for the email, the default server is production, `--json` exists, and a bare topic prints its options numbered.
  - `system3-cli` installs 11 pinned packages and none of the server's. `s3 mcp` answered live through the MCP SDK's stdio client and renewed an expired sign-in.
  - A question back reads `[ask]` and exits 0, as over MCP; a refusal reads `[refuse]` and exits 1.
  - Fence extensions the lead approved: the builder's own debugging guide rows and the regenerated manifest, and one exact string, "notifications/cancelled", in `test_tiers.py`'s exemption list, because the MCP specification names that method.
  - The six gate04 failures are database tests that fail the same way on 8cd197d on this machine; CI has the database.
  - Left for the lead after the golden run: one live `s3 ask GERD` from a build of this branch.
- 2026-09-26 23:56: builder R finished T-8.10-07 and 08 (report `testing/Developer/reports/2026-09-26_phase_8.10/builder_R.md`), merged as de62030.
  - The Integrations page:
    - an MCP config carrying `"type": "http"` and the Authorization header, with the 15-minute token and how to get one;
    - the four MCP tools;
    - the git install line for `system3-cli`, never `pip install s3`;
    - `s3 login you@example.org` and `s3 mcp`;
    - KGX export needing operator-granted graph access;
    - `POST /auth/guest`;
    - twelve event kinds;
    - a citations sentence without the nonexistent tool field.
  - The tour, About and Architecture: all seven stale screen facts corrected, and the graph limit shown as 30 seconds (F-8.6-FJ08).
  - Frontend: 4 test files, 45 tests passed, and `npm run build` succeeded.
  - The facts checker from the closed #118 branch errors on six facts whose patterns are keyed to the old false sentences. That was passed to the re-split builder on `chore/verify-facts-2`.
- 2026-09-27 00:00: develop merged into the branch (9a0148a), bringing phase 8.6's follow-up and the 30 s graph limit. The lead corrected the debugging guide's `server.py` row to the four tools (b31974b).
  - Gates on b31974b: `ruff check` clean; `isort` clean; `gate_packages_install.sh` 2 passed, 0 failed; `gate04_unit_suite.sh` 6349 passed, 143 skipped, 24 deselected, 1 xfailed.
  - T-8.10-01 to 08 are in review.
- 2026-09-27 00:12: pull request #120 opened. The judge (Opus 5.5) and the adversary (Fable 5.1) dispatched on 5ba8f4d, dispatches 4 and 5 of 8. Their findings come back in their final messages, and the lead files them here.

## Findings
