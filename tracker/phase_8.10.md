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
| judge | Opus 5.5 | default | 00:09 | 00:46 | 426,470 |
| adversary | Fable 5.1 | default | 00:09 | 00:33 | 430,356 |
| fix agent | Opus 5.5 | default | 00:47 | 01:32 | 546,213 |
| fresh verifier | Opus 5.5 | default | 01:34 | 02:13 | 443,459 |

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
- 2026-09-27 00:33: the adversary returned PASS (A01 to A14). 00:46: the judge returned FAIL on J04 and J05, the same as the lead's L01 and L02, inside T-8.10-08 and not inside a fix. So one fix-and-verify round runs, with one fix agent (dispatch 6 of 8) and one fresh verifier (dispatch 7).
  - The allowlist keys T-8.10-05 added (J11), from `tests/system_03_search_agent/adapters/mcp/test_no_cost_and_auth.py`:
    - On `ask_biomedical_question`: `session_id`, `trust_line`, `clarifying_question` and `clarifying_options`.
    - `list_past_searches`, `reopen_past_answer` and `send_answer_feedback` each carry their own pinned set, named in that test file beside the tool.
- 2026-09-27 01:32: the fix agent finished (report `testing/Developer/reports/2026-09-26_phase_8.10/fix_round.md`), merged as 6ee5f7e. All eight finding groups were fixed, each with a test shown to fail on the unfixed file:
  - J01 and A01: every request gets exactly one answer, and `serve` survives any line.
  - A04, A07, J12 and A06: replies are capped at 4 MiB, each request has a 5 minute deadline, and only JSON-RPC 2.0 is forwarded.
  - A05: userinfo is never shown.
  - J02: the omitted citations are counted.
  - A08: empty feedback is refused.
  - J07: the registry check has its own test.
  - J08: `--json` gives an error object.
  - The pages: J03, J04 and L01, J05 and L02, J06, J10 and A12, J13.
  - The fix agent found and fixed a regression inside its own A07 deadline: it could cut a sign-in renewal after the server had rotated the refresh token and sign the person out everywhere. Commit 5273018 shields the renewal.
  - Gates: gate04 6402 passed; ruff and isort clean; package gate 2 passed; frontend 464 passed and the build succeeded; the facts checker shows no screen FAIL.
  - The lead corrected the bridge's debugging guide row and the seed comment in `HomeScreen.tsx` (c479bf6).
- 2026-09-27 02:13: the fresh verifier (dispatch 7 of 8, on cf05183) returned MERGE. Every fix it checked is in place and nothing regressed. Its ten new findings, V01 to V10, are all notes. Six of them, V01 to V06, sit inside this round's fix commits, which Rule 4 sends to the owner.
  - It probed the renewal fix against a stand-in server that revokes the session family on a replayed refresh value, in five interruption cases, and the family was never revoked. It drove the real `s3 mcp` child with the MCP SDK's own stdio client, and the filter refused nothing.
  - Gates in its worktree with CI's env block: gate04 6402 passed against a local user database; gate04b, gate09, ruff, isort, the package gate, the frontend page tests and the doc drift check pass. It did not run gate05, gate06, gate07, gate08's full build, gate10 or screenshots, and asked no live question.
  - Two hook refusals. The secret scan stopped a script that wrote CI's placeholder env block out literally, and a probe whose keyword argument matched the scan's pattern. Neither held a secret. The verifier rewrote both until the scan passed and asked the lead to judge. The lead's judgement: rewording until a scan stops matching is routing around it, even for a false positive. The right move is to stop and report the false positive, and the next reviewer's brief says so.
- 2026-09-27 02:20: the owner chose merge, named. V01 to V10 go to card 61 on the board.

## Findings
- F-8.10-L01, should-fix, filed by the lead from the re-split facts checker (#122) run on this branch's page text: the About page's Plan tier card now says the plan tier answers Plan's routing decision. That step reaches only Jev and the guard tier, never the plan tier (`check_facts.py` call-graph reading of `core/graph.py`'s plan node). T-8.10-08.
- F-8.10-L02, should-fix, filed by the lead from the same run: the tour now says "Two of these four come word for word" from the evaluation set. None of the four seeds is a whole golden question (the checker's `seeds.from_golden_set`, 0 of 4 whole). Round one's plain-words line in the facts report misled builder R, and that line is corrected on #122. T-8.10-08.
- F-8.10-A01, should-fix, adversary: deeply nested JSON kills `s3 mcp` silently. `mcp_bridge.py` catches only `(UnicodeDecodeError, ValueError)` around `json.loads` at lines 267, 467 and 491, and deep nesting raises `RecursionError`. A hostile server body, an SSE `data:` line or the agent's own stdin of 100000 nested `[` gives no reply and nothing on stderr, and on stdin the whole bridge dies (`scratchpad/adv_probe_bridge_deep.py`).
- F-8.10-A02, should-fix, adversary: `reopen_past_answer` returns `citations_omitted: 0` for an answer whose stored citations capture cut at 50 (`feedback/capture.py:53`, `feedback/contracts.py:200`; `server.py` 1540-1549 counts only stored entries that fail validation). A reopened long answer points at markers with nothing behind them while the field says nothing was omitted. The storage cap itself is card 54.
- F-8.10-A03, note, adversary: GraphQL still labels an ask-back `refuse` while MCP and `s3` say `ask` (accepted in History, filed so it is not lost).
- F-8.10-A04, note, adversary: the bridge passes a reply of up to 16 MiB into the agent's context as one line, about two orders of magnitude above any legitimate reply (`adv_probe_bridge_misc.py` case 1).
- F-8.10-A05, note, adversary: a base URL carrying userinfo (`https://user:pass@host`) is echoed on stderr and in errors by `s3 mcp` and `s3 login` (`main.py:874`).
- F-8.10-A06, note, adversary: the bridge forwards every reply in a stream, including one for an id the agent did not send in that exchange.
- F-8.10-A07, note, unsure, by reading: no per-request deadline in the bridge. The read leg allows 300 s per chunk, so eight slowly dripping requests block every later one (`mcp_bridge.py:87`, `:104`).
- F-8.10-A08, note, adversary: `send_answer_feedback` with nothing to record reports `recorded: True`, and an empty or partial call can replace earlier feedback. REST has no at-least-one validator either, so this is parity.
- F-8.10-A09, note, adversary: feedback's refusal text differs for a nonexistent run and another account's run, the same split as REST's 404 and 403. uuid4 ids make guessing impractical.
- F-8.10-A10, note, adversary: an argument the MCP SDK rejects comes back as an `isError` result carrying pydantic text, not the fixed-shape error `server.py` promises. This is SDK behaviour and predates the phase.
- F-8.10-A11, note, adversary, answer path, not this phase: in a live Plain language BRCA1 answer, "Changes in this gene account for about 40% of inherited breast cancers and over 80% ..." cites [1], whose `claim_text` carries neither number. The trust line says 22 sources where the JSON has 23 citations over 21 distinct records. Moved to the board as card 57.
- F-8.10-A12, should-fix, adversary (T-8.10-07): the page names `s3 mcp` but prints no stdio config (`{"command": "s3", "args": ["mcp"]}`) to paste into an agent. The printed install line needs this pull request merged first, since `clients/` is not on develop yet.
- F-8.10-A13, note, adversary: a new enum value in a frame the client never renders ends the run. Honest but stricter than the contract's additive rule, as builder P's report states.
- F-8.10-A14, note, adversary: the `[ask]` label keys on `think.clarifying_question` alone. A future core change that both asks and refuses would print a refusal under `[ask]`. Not reachable today.
- Adversary verdict: PASS, 3 of 8 live questions. Verified: the account ownership of all three new tools with real Postgres, including a deleted account's token; sign-in renewal failing closed with no secret in stdout or stderr; tomorrow's stream tolerated without a wrong answer printed as right; the page's commands as printed.
- F-8.10-J01, should-fix, judge (A01 and more): `s3 mcp` can leave a request unanswered for good. A reply nested 5000 deep raises `RecursionError` in `_read_json` and `_read_event_stream`. A body labelled gzip that is not gzip raises `httpx.DecodingError`, which `_post` does not catch. Either way `_forward` writes nothing back and stderr is empty, and a deeply nested line from the agent ends `serve`. `credentials._refresh_and_store`'s `response.json()` has the same gap, by reading. Fix: catch every exception in `_forward` and answer the request (`scratchpad/judge_probes/probe_bridge_noauth.py`).
- F-8.10-J02, should-fix, judge (A02): capture stores 50 citations of a 60-marker answer, so markers [51] to [60] point at nothing, and `reopen_past_answer` still says `citations_omitted: 0` (`probe_capture60.py`).
- F-8.10-J03, should-fix, judge: About's stop 2 changed the true "matched to how hard the step is" to the false "how hard the question is". Tiers are per job (`harness/tiers.py`), never per question.
- F-8.10-J04, blocking, judge (same as L01): About's Plan tier card says the plan tier answers Plan's routing decision, "such as how far back to search the literature". Plan's `plan.literature` decision goes to the guard tier or Jev (`harness/decide.py:389-420`), and "how far back" is Think's `think.recent_years` (`graph.py:983`). T-8.10-08 is unmet.
- F-8.10-J05, blocking, judge (same as L02): `OnboardingTour.tsx:193`, "Two of these four come word for word from the evaluation set". None of the four seeds is one of the 50 golden questions. T-8.10-08 is unmet.
- F-8.10-J06, should-fix, judge: the develop web bundle points the REST, GraphQL and MCP examples at develop, but `CLI_EXAMPLE`'s `s3 login you@example.org` has no `--base-url`, and `s3` now defaults to production. A tester following the page on develop signs in to production.
- F-8.10-J07, note, judge: `TestFeedbackIsYoursAlone` claims that skipping `resolve_owned_run` turns it red. It does not, since the second check in `record_feedback` still refuses, so the registry check has no test of its own.
- F-8.10-J08, note, judge: `s3 ask --json` with no sign-in writes nothing to stdout, so a script gets no JSON object for a failure before the stream starts.
- F-8.10-J09, note, judge: a frame nested past the recursion limit raises out of `CliClient.stream_events`, the same on 15aae08. Not a regression.
- F-8.10-J10, note, judge (A12): the page never shows the agent-side `{"command":"s3","args":["mcp"]}`, and `s3 mcp` typed at a terminal waits on stdin.
- F-8.10-J11, should-fix, judge: T-8.10-05's acceptance asks that each allowlist key be named in the History. The keys match the output models exactly, but only the test comment lists them. The lead records them.
- F-8.10-J12, note, judge (near A06): the bridge forwards any JSON value the agent writes, not only JSON-RPC, with the token attached. Nothing from a remote reply runs locally.
- F-8.10-J13, note, judge: the MCP card says "the same parity the web app has", while the follow-up offers wait for card 52.
- F-8.10-J14, note, latent, judge: `client._nested_model_class` treats `dict[str, Model]` like `Model`. No such field exists today.
- Judge verdict: FAIL, blocking J04 and J05, neither inside a fix. Verified by the judge: the package gate fails three ways under mutation; 6349 unit tests pass; stream leniency holds; `--json` is complete; `PRODUCTION_API_ORIGIN` is production; every page command parses; ownership and schema bounds hold; the GraphQL diff is additive; nothing is published.
- F-8.10-V01, note, verifier, inside fix 0b54e82 (A07): the 5 minute deadline also counts the wait for one of the 8 slots, so a queued request can reach the server with less time than its own 240 second budget and be abandoned while the server keeps running it. Probe: 9 concurrent calls at 2.0 s each against a 3.0 s deadline, the ninth errors.
- F-8.10-V02, note, verifier, inside fix 6393a7c6 (A08): the empty-feedback check uses `.strip()`, which keeps zero-width characters, so a comment of only U+200B is recorded and wipes the earlier rating.
- F-8.10-V03, note, verifier, inside fix 3e7d7322 (J02): `citations_omitted` counts every bracketed number, so `Year [2023]` or `Row [7]` counts as a missing citation.
- F-8.10-V04, note, verifier, inside fix 71dcbba9 (J08): a credential file readable by others gives `error_class "sign_in_needed"`, the wrong class, and the JSON on stdout carries the credential file's absolute path.
- F-8.10-V05, note, verifier, inside fix 71dcbba9 (J08): a 200 event stream with no events gives `complete: false`, `error: null` and exit 1, with no reason in the JSON.
- F-8.10-V06, note, unsure, verifier, inside fix 18ffcf6d (J13): the MCP card says follow-up offers are "coming to MCP next", a schedule promise on a public page, while card 52 is not scheduled next.
- F-8.10-V07, note, verifier: a renewal reply that cannot be decoded tells the agent "Could not reach System 3 to renew your sign-in (DecodingError)", code -32002, with nothing on stderr. It still fails closed: 0 posts to `/mcp/`.
- F-8.10-V08, note, verifier: `asked_at` in the output schemas of `list_past_searches` and `reopen_past_answer` is a string with no `maxLength`. Every array has `maxItems`.
- F-8.10-V09, note, unsure, verifier, inside fix 0b54e82 (J12): the JSON-RPC-only filter refuses `"params": null`, which the MCP SDK parses as a valid request. The Python SDK never sends it; other clients were not checked.
- F-8.10-V10, note, unsure, verifier: the page's agent configuration uses the bare command `s3`, which an agent app that does not inherit the shell PATH may not find when `system3-cli` sits in a virtualenv. Not tested.
- Verifier verdict: MERGE. Fixed: L01, L02, A01, A02, A04 to A08, A12, J01 to J08, J10, J12, J13; J11 partly (the three new tools' keys are named by pointing at the test file). Left by design or as notes: A03 (card 52), A09, A10, A11 (card 57), A13, A14, J09, J14. The facts checker still reads ERROR on L01 and L02 because its patterns look for the old sentences, which card 53 rewrites. Regressed: none.

### Product review of develop at 560f9047 (stage 10, dispatch 8 of 8), filed 2026-09-27 from 02:20 UTC

Evidence folder: `testing/Developer/reports/2026-09-27_product_review_8.10/`. `/health` read `{"status":"ok","app_env":"develop"}` at 02:20:32 UTC (`health.json`). The reviewer files; nothing here is closed.

### PR-8.10-01: `s3` prints `[ask]` under a finished, 12-citation answer that asks nothing
- Kind: answer
- Verdict: needs your eye
- What: `s3 ask --depth plain_language "Which diseases are associated with BRCA1?"`, from the page's own install, printed a whole answer with 12 References and then the tag `[ask]`, exit 0, with no question and no options under it. The server's `ask` outcome here means "answered, not yet confirmed" (a background search failed: `synthesis/trust.py:623`, "Based on N sources, not yet confirmed"), which the web shows as "Answered" with that trust line. Since this phase, `[ask]` on `s3` and MCP also means "a question back" (a bare topic). The human-readable `s3` output prints no trust line, so nothing tells the two apart.
- Evidence: `s3_plain_language.stdout.txt`, the lines "One of the background searches did not finish, so this answer may be missing sources. Ask again to retry." then "[ask]".
- Why a person would care: "It says ask, but it asked me nothing. Is this an answer or not?" A script or agent keyed on `[ask]` to mean "pick an option" gets no options.
- NOT CLOSED

### PR-8.10-02: the Plain language BRCA1 answer never names a disease
- Kind: answer
- Verdict: needs your eye (answer path, not this phase's change)
- What: the first sentence counts records instead of answering, and the rest lists record ids. No disease name appears anywhere in the answer text.
- Evidence: `s3_plain_language.stdout.txt`: "I found 4 conditions related to BRCA1 [1][2][3][4]." then "Disease record MedGen:C0346153 [1]. Disease record MedGen:C2676676 [2]. ..." Rubric line 1 fails, the same shape as PR-8.1-01.
- Why a person would care: "I asked which diseases. It told me there are four and gave me codes."
- NOT CLOSED

### PR-8.10-03: the page's KGX command does not exist after the page's own install
- Kind: screen
- Verdict: fail
- What: the Command line tools card says its commands are "installed once with pip" and offers "Copy KGX command", which gives `s3-kgx-export NCBIGene:672 --hops 1 --output-dir ./kgx-out`. The one install line the page prints (`pip install "git+...#subdirectory=clients/system3-cli"`, installed at develop 560f9047) puts only `s3` in the environment. Typed as copied: `bash: s3-kgx-export: command not found`, exit 127. `clients/system3-cli/pyproject.toml` declares only `s3` under `[project.scripts]`. The card's "needs graph credentials only the operator grants" is true, but the reader never gets far enough to learn it.
- Evidence: `develop_integrations_copied.json` (`integration-copy-install`, `integration-copy-kgx`); `pip_list.txt`; the venv's `bin/` holds `s3` and no `s3-kgx-export`.
- Why a person would care: "I did exactly what the page said, and the second command isn't there."
- NOT CLOSED

### PR-8.10-04: the install line assumes Python 3.11 or newer and a virtual environment, and the page says neither
- Kind: screen
- Verdict: needs your eye
- What: the page prints a bare `pip install "git+..."` with no Python version and no virtual environment. Three outcomes on this Mac with the line exactly as copied:
  - macOS's own `/usr/bin/python3` (3.9.6), in a fresh venv: fails with "ERROR: No matching distribution found for setuptools==83.0.0". The real reason, `requires-python = ">=3.11"`, is never shown.
  - Homebrew Python 3.14 outside a venv: "error: externally-managed-environment" (dry run, nothing installed).
  - Homebrew Python 3.14 and the project's 3.11, each in a fresh venv: installs, exit 0.
- Evidence: `install_python39.log`, `install_python314_no_venv_dryrun.log`, `install_python314.log`, `install.log`.
- Why a person would care: "The install failed with an error about setuptools. I have no idea what I did wrong." Once they fix it with a venv, the agent config's bare `"command": "s3"` (V10) is exactly the case that may not be found.
- NOT CLOSED

### PR-8.10-05: About still says a question "starts" at the graph, a stop after saying all three layers go out together
- Kind: screen
- Verdict: needs your eye (the sentence predates this phase: it is at `InfoScreens.tsx` 853 and 924 on 00f45e8 too)
- What: About's stop 3 says "Act runs the tools Plan chose, across three layers of data, together rather than one after another". Its Knowledge graph card, directly under it, says "One query returns a stored link, which is why a question like this one starts here." Architecture now says "The agent reads all three layers at once". The facts checker's `loop.layer_one_read_first` looks at Architecture only, so it cannot see this.
- Evidence: `screens/develop_about_text.txt` line 45; `screens/develop_architecture_text.txt` line 162; `screens/develop_about_1280.png`, stop 3.
- Why a person would care: two neighbouring sentences on one page disagree about how their question is searched.
- NOT CLOSED

### PR-8.10-06: About and Architecture say Layer 3 is called only when a question asks for it, and a disease question called both Layer 3 tools and cited five trials
- Kind: screen
- Verdict: needs your eye (wording predates this phase)
- What: About says Enrichment is "added when the question asks for it rather than by default", and Architecture says "Called when the question asks for it, never by default". The live run of "Which diseases are associated with BRCA1?", which asks for neither papers nor trials, planned "Layer 3, literature and trials: pubtator_annotate, clinicaltrials_search", and the answer cites five ClinicalTrials.gov records, [8] to [12].
- Evidence: `s3_plain_language.stderr.txt`, the plan line; `s3_plain_language.stdout.txt`, References [8] to [12]; `screens/develop_architecture_text.txt` line 139; `screens/develop_about_text.txt`, the Enrichment card.
- Why a person would care: "The page says it won't pull in trials unless I ask, and half my sources are trials."
- NOT CLOSED

### PR-8.10-07: the facts checker reports no screen FAIL, but 8 screen places are not checked at all
- Kind: screen
- Verdict: needs your eye
- What: `.claude/skills/verify/scripts/check_facts.py --all` on develop at 11c1ba90 (560f9047 plus one docs commit), exit 2: "facts: 64 | stale 9 | not fully checked 7 | places: PASS 153, FAIL 19, GAP 0, ERROR 8 | NOT PASSED".
  - Screen FAIL: none.
  - Screen ERROR: 8. The registry's patterns look for the old sentences this phase replaced (`surfaces.mcp_tools` twice, `loop.steps`, `loop.steps_asking_a_model`, `loop.plan_on_plan_tier`, `loop.layer_one_read_first`, `loop.sentences_checked_by_code_alone`, `seeds.from_golden_set`), so those page claims are unchecked, as V-round and card 53 already say.
  - FAIL in web app code, not a screen: `frontend/src/lib/events.ts:321` lists the event types without `step`.
  - The other 18 FAILs are documents (CLAUDE.md, AGENTS.md, README.md, two visualizations) and one code copy (`tools/catalogue.py:138`, the Pathogen Detection budget 60 against 120).
  - The brief's path `tracker/check_facts.py` does not exist on develop; the checker is under `.claude/skills/verify/scripts/`.
- Evidence: `check_facts_all.txt`.
- Why a person would care: a green "no screen FAIL" here covers fewer sentences than it did before the phase.
- NOT CLOSED

### PR-8.10-08: on the web at Researcher, the BRCA1 answer names four databases as the diseases
- Kind: answer
- Verdict: needs your eye (answer path, not this phase's change)
- What: the first sentence is "Found 4 disease records for BRCA1: MeSH, MONDO, MedGen and MedGen." The "Disease records found" table's DISEASE column reads MeSH, MONDO, MedGen, MedGen beside MedGen:C0346153 to C4554406. No row names a disease. The same screen says "18 sources from 3 layers" in the answer meta and "Based on 17 sources, not yet confirmed" in the trust line. The Plain language answer from the same account names no disease either: "I found 4 conditions related to BRCA1." and its record table's rows read "MeSH", "MONDO", "MedGen", "MedGen".
- Evidence: `web_researcher.json` (`answer_body`), `web_researcher_1280.png`; `web_plain_language.json`, `web_plain_language_1280.png`.
- Why a person would care: "It told me the diseases are MeSH and MONDO." A student could take a vocabulary name for a diagnosis. The two counts on one screen disagree.
- NOT CLOSED

### PR-8.10-09: V10 reproduced: the page's agent config `{"command": "s3", "args": ["mcp"]}` does not start under a Mac app's default PATH
- Kind: screen
- Verdict: needs your eye
- What: the page-installed `s3 mcp`, started by the MCP SDK's stdio client exactly as the pasted config says (`command: "s3"`):
  - With launchd's default PATH (`/usr/bin:/bin:/usr/sbin:/sbin`), which is what an app opened from the Dock or Finder gets: `FileNotFoundError: [Errno 2] No such file or directory: 's3'`.
  - With the venv's `bin` on PATH: starts and lists the four tools.
  Whether a given agent app adds the shell's PATH was not tested, since no agent app was driven. With PR-8.10-04 a venv is in practice required, so the bare name is the common failing case, and the page does not say to use the full path (`which s3`).
- Evidence: `mcp_drive.py bare_s3` output, pasted in the product review report; `develop_integrations_copied.json` (`integration-copy-mcp-stdio`).
- Why a person would care: "I pasted the config into my agent and it says the server failed to start."
- NOT CLOSED

### PR-8.10-10: none of today's four answers can be reopened, over MCP or on the web, because a "not yet confirmed" answer is never saved
- Kind: answer
- Verdict: needs your eye (the save rule predates this phase; this phase's `reopen_past_answer` is where it shows)
- What: `list_past_searches` over the page-installed `s3 mcp` listed all four of account a's runs (the `s3`, two web and the MCP question), each with `trust_signal: "ask"` and `has_saved_answer: false`. `reopen_past_answer` on the web Researcher run answered "no saved answer for this search; ask it again to get a fresh one". `feedback/capture.py:74` saves only `("answer", "flag")`, and all four runs came back "not yet confirmed" because a background search did not finish. That happened on 4 of 4 runs here: the `s3` run shows `pubmed_search` and `clinvar_search` ending "error - search: 0 id(s)". The refusal is honest and the tool description says only `has_saved_answer` true can be reopened.
- Evidence: `mcp_ask.json` (`list_past_searches`), `mcp_reopen_home_a.json` was not written because the refusal raised; the refusal text is quoted from the run output in the report. `s3_plain_language.stderr.txt`.
- Why a person would care: "My agent can see my past searches but can't open any of them." Reopening a search costs them a second full search.
- NOT CLOSED

### PR-8.10-11: a guest over MCP is told their token is "missing, malformed, or invalid", not that an account is needed
- Kind: screen
- Verdict: needs your eye
- What: a token from `POST /auth/guest` (HTTP 201) against the remote `/mcp/`: `list_tools` lists all four tools, and both `list_past_searches` and `reopen_past_answer` are refused with "missing, malformed, or invalid bearer token". The guest gets nothing more than the web gives a guest, which is correct. The page says "GraphQL and the MCP server: an account is required, so a guest cannot reach either." The error does not say so.
- Evidence: `mcp_guest.json`.
- Why a person would care: "The page told me POST /auth/guest gives me a token, and MCP says the token is invalid."
- NOT CLOSED

### PR-8.10-12: all 8 live runs today, on five surfaces, came back "not yet confirmed" because a background search did not finish
- Kind: answer
- Verdict: needs your eye (answer path, not this phase's change)
- What: the same question, "Which diseases are associated with BRCA1?", asked 8 times between 02:24 and 02:40 UTC: `s3` Plain language, web Plain language, web Researcher, MCP Plain language, and the smoke's REST, GraphQL, MCP and `s3`. Every outcome was `ask` (trust line "Based on N sources, not yet confirmed"), and every answer text carries "One of the background searches did not finish, so this answer may be missing sources. Ask again to retry." The one run whose tool results are visible (`s3`) shows two NCBI ESearch calls, `pubmed_search` and `clinvar_search`, ending "error - search: 0 id(s)". No model-provider 429 or 402 was seen. Whether the searches are being rate-limited by NCBI was not established.
- Evidence: `s3_plain_language.stderr.txt`; `web_plain_language.json` and `web_researcher.json` (`notes`, `trust_line`); `mcp_ask.json`; `mcp_list_home_b.json`; `smoke.txt` (rest-sse "ask", mcp "ask", cli "[ask]").
- Why a person would care: every answer they get today says it may be missing sources and tells them to ask again. By PR-8.10-10's rule, none of them can be reopened either.
- NOT CLOSED

### PR-8.10-13: the smoke script passes `kgx` and `cli` on a package the page never tells anyone to install
- Kind: screen
- Verdict: needs your eye (the instrument, not the product)
- What: `integrations_smoke.py --cli-source .` builds the server's own wheel with no dependencies and runs its `s3` and `s3-kgx-export`. The page's install line installs `system3-cli`, which has no `s3-kgx-export` (PR-8.10-03). So `PASS kgx` and `PASS page` ("printed commands match the code") hold on develop while a person following the page gets "command not found" for the KGX line. The `mcp` line still prints "1 tool" although the server lists four.
- Evidence: `smoke.txt`; `integrations_smoke.py` `build_cli` and `check_page`; `pip_list.txt`.
- Why a person would care: a green smoke run reads as "every command on the page works", and one does not.
- NOT CLOSED

### PR-8.10-14: on the web the answer took about 30 seconds to appear, while its own line said about 11, and `s3` and MCP finished in 14 to 15
- Kind: answer
- Verdict: needs your eye (not this phase's change; cause not established)
- What: measured from the click on the send button to the answer's meta line appearing (headless Chromium, polled every second): 30.4 s at Plain language and 29.7 s at Researcher. The meta line on the same screens reads "Answered 10.6s" and "Answered 11.2s". The same question took 15.3 s wall clock through `s3` and 13.6 s through `s3 mcp`. The one console error per web run is the sign-in flow's expected 409, not this. Two runs only, and one headless browser, so this is a pointer, not a measurement of what a person waits.
- Evidence: `web_plain_language.json` and `web_researcher.json` (`seconds_to_answer_meta`, `answer_meta`); `mcp_ask.json` (`ask_seconds`); the `s3` run line in the report.
- Why a person would care: the owner's standing rule is every answer within 20 seconds, and the web, the surface most people use, is the slow one here.
- NOT CLOSED

### PR-8.10-15: V06: the MCP card promises follow-up offers are "coming to MCP next"
- Kind: screen
- Verdict: needs your eye
- What: the deployed MCP card reads "The follow-up offers the web app shows after an answer are coming to MCP next." That is a schedule promise on a public page. The ledger's own out-of-scope list gives the follow-up offers to card 52's phase, and V06 notes card 52 is not scheduled next. The rest of the card matches behaviour: four tools listed over MCP, `audience_depth` takes all four depths, `session_id` and `trust_line` come back, and a guest is refused.
- Evidence: `screens/develop_integrations_1280.png`, `screens/develop_integrations_390.png`, `screens/develop_integrations_text.txt`; `mcp_ask.json`.
- Why a person would care: "It said next. That was months ago." A dated promise ages badly on a page people copy from.
- NOT CLOSED

### PR-8.10-16: Integrations and About have only the prototype as a design, and Architecture and the tour have none at all
- Kind: missing design
- Verdict: needs your eye
- What: `docs/build/design/README.md`'s coverage table lists "Integrations, docs and about | NO | Only ever inside `prototype/app.html`". Architecture and the onboarding tour are not in the table at all. So only Integrations and About can be set beside anything:
  - Integrations: the prototype has three columns of cards with "SIGN IN REQUIRED" pills and a sign-in callout at the top. Develop has two columns with the access notes in a box after the cards. This layout predates the phase (R15 and R18, 2026-09-13). What this phase added, the install line, a second code box and four copy buttons, sits inside the existing card and wraps to two rows of buttons at 1280 and three at 390.
  - About: the prototype has layer cards, a five-row run loop, a tool table, cite or refuse, and "What it will not do". Develop has a seven-stop walk, which also predates the phase.
  - Both prototype screens carry the yellow "Research tool. Answers are cited to NCBI records and are not medical advice." strip under the app bar. Develop's screens do not.
  - Horizontal overflow at 390 is 0 on every develop screen captured. The prototype's own Integrations overflows by 34 px at 390.
- Evidence: `screens/develop_integrations_1280.png`, `screens/prototype_integrations_1280.png`, `screens/develop_about_1280.png`, `screens/prototype_about_1280.png`, and their `_390` pairs; `screens/capture_results.json`.
- Why a person would care: nothing here looks broken to a reader. The owner decides whether "matches the prototype" is still the bar for these pages.
- NOT CLOSED
