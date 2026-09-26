# Builder R, build phase 8.10: the page's words

Builder R's report for tickets T-8.10-07 and T-8.10-08 of `tracker/phase_8.10.md`, on the branch `feat/8.10-r`, cut from the pushed phase branch at `47943cf3` (builder Q's tools merged). Paths are written as `<repo-root>` and `<scratch>`. No email, password or token appears.

## Table of contents

- [Summary](#summary)
- [T-8.10-07: the Integrations page](#t-810-07-the-integrations-page)
- [T-8.10-08: About, Architecture and the tour](#t-810-08-about-architecture-and-the-tour)
- [The lead's mid-task item: the 30-second graph budget](#the-leads-mid-task-item-the-30-second-graph-budget)
- [Checks](#checks)
- [What is expected but not fixed here](#what-is-expected-but-not-fixed-here)
- [For the lead](#for-the-lead)

## Summary

| Ticket | Status |
|---|---|
| T-8.10-07, the Integrations page says what is true | Done |
| T-8.10-08, About, Architecture and the tour say what is true | Done |

Commits, on `feat/8.10-r`:

- `fix(web-ui): the Integrations page says what MCP, the CLI and the event stream really carry`
- `fix(web-ui): About, Architecture and the tour say what the loop and layer 2 really do`
- `fix(web-ui): the graph query budget is 30 seconds, not 90` (the lead's mid-task item)

## T-8.10-07: the Integrations page

Every item the audit's "The page's words" section named, fixed in `InfoScreens.tsx`:

- The MCP config now carries `"type": "http"` and a `headers.Authorization` entry, says a token lasts 15 minutes, and says `POST /auth/login` mints one.
- The MCP server card now says four tools, naming `list_past_searches`, `reopen_past_answer` and `send_answer_feedback` beside `ask_biomedical_question`, matching builder Q's merged work.
- The command line card now shows an install command (`pip install "git+https://github.com/monideep2255/agentic-search-ui.git#subdirectory=clients/system3-cli"`), never `pip install s3`. A new "Copy install command" button carries it.
- `CLI_EXAMPLE` prints `s3 login you@example.org`, not a bare `s3 login`, plus `s3 mcp` for a command-running AI agent.
- The command line card's body now says `s3-kgx-export` needs graph credentials only the operator grants.
- The Access box now says `POST /auth/guest` issues a guest's own token.
- The event stream card now says twelve kinds of event, adds `step` to the list, and names `done`'s `decisions`, `trust_line` and `layer_calls_used` and `think`'s `clarifying_options`.
- The citations card no longer claims a `tool` field, which `CitationPayload` does not carry.
- The two stale source comments at the top of the file ("NOT claimed to work here", "EVERY COMMAND PRINTED HERE WAS RUN") are rewritten to say what is true today.

## T-8.10-08: About, Architecture and the tour

Every item 1 to 7 in `testing/Developer/reports/2026-09-26_ui_facts/report.md`'s "Stale facts in plain words":

1. The tour's app bar step now names the MCP server as a fourth way in.
2. The tour's seed step now says two of the four seeds come word for word from the evaluation set, rather than claiming all four do.
3. About's Plan tier card now says Plan picks the tools in code and asks one routing decision; the graph query is written in Act, from a template, or by the plan tier only when no template fits.
4. About now says every one of the five steps can ask a model, not four of five.
5. About's stop 5 now says a reworded sentence that passes the exact checks is judged by a model and can be kept, rather than claiming code alone decides.
6. About's layer 2 card now names PubChem and Pathogen Detection; Architecture's `ncbi_efetch` card in `architectureFacts.ts` now names PubChem too.
7. Architecture's stop 4 no longer says the agent reads layer 1 first; it says all three layers are read at once, matching `_gather_planned_calls`'s `asyncio.gather`.

## The lead's mid-task item: the 30-second graph budget

Sent mid-task: pull request #119 cuts `CYPHER_QUERY_TIMEOUT_SECONDS` from 90 to 30, merging to develop tonight. Changed every screen place: `architectureFacts.ts`'s `budget` string, `ArchitectureScreen.tsx`'s prose and its two test assertions, and About's "30 seconds for a graph query" line in `InfoScreens.tsx`. This branch was cut before #119, so the facts checker reports these three as FAIL against this branch's own code (still 90). That is expected, not a miss, and it will read PASS once run against develop after #119 merges.

## Checks

`check_facts.py`, run from the main checkout's venv against this worktree (no request left this machine; `reference/` is the local read-only symlink):

```
facts: 64 | stale 10 | not fully checked 7 | places: PASS 151, FAIL 21, GAP 0, ERROR 8 | NOT PASSED
```

Every FAIL and ERROR left is one of three kinds, none of them a page that states something false:

- The three `budget.graph_query_s` screen FAILs (Architecture, About, `architectureFacts.ts`), expected per the lead's PR #119 note above.
- A FAIL or a document-only ERROR on `CLAUDE.md`, `AGENTS.md`, `README.md`, `visualizations/*.md` or a code copy (`catalogue.py`, `frontend/src/lib/events.ts`). None of these files is in my fence; they are the lead's per the ledger and per `tracker/phase_8.10.md`'s own note that `contracts/events.py`'s docstring and the debugging guide are the lead's.
- Six ERRORs on my own screens (`surfaces.mcp_tools` and `loop.steps`, `loop.steps_asking_a_model`, `loop.plan_on_plan_tier`, `loop.layer_one_read_first`, `loop.sentences_checked_by_code_alone`, `seeds.from_golden_set`), each reading "pattern finds nothing, update the registry". Every one of these facts is keyed to the EXACT stale sentence the audit found wrong (for example `r"(Four) of the five steps ask a language model"`), on the `chore/verify-facts` branch's `facts_registry.py`, which is outside every builder's fence this phase. Correcting the false sentence is the point of T-8.10-08, so the literal pattern can no longer find it. This is the registry needing an update to the corrected wording, not a false claim left on a page. One more, `surfaces.s3_options` ("JSON with --json"), FAILs here only because builder P's `--json` flag lives on `feat/8.10-p`, not yet merged into this branch; P's report confirms `s3 ask --help` lists `--json` on that branch.

`npx vitest run` on `AboutScreen.test.tsx`, `IntegrationsScreen.test.tsx`, `ArchitectureScreen.test.tsx` and `OnboardingTour.test.tsx`: `Test Files 4 passed (4) | Tests 45 passed (45)`.

`npm run build`: `tsc -b && vite build` succeeded, `✓ built in 2.13s`.

`python3 tracker/check_doc_drift.py --check`: `ok: 2 facts computed | 0 could not be computed | 0 stale | 0 structural`.

The audit's `integrations_smoke.py` `page` check was not run live: the lead's golden-run note asked that nothing hit develop's API during this task, and `main()` always calls `/health` first, so there is no way to run only the `page` line against a live origin. Read instead, against `check_page`'s own code:

- `MCP_CONFIG`'s `url` ends in `/mcp/` and `headers.Authorization` is non-empty: both true.
- Every `s3`-leading line in `CLI_EXAMPLE` either is not `login`, or is `login` with a second token (`you@example.org`), so the "`s3 login` printed without the email it requires" check never fires.
- The only `--`-flag in `CLI_CARD_BODY` is `--json`, which builder P's branch adds to `s3 ask --help`.

To run the `page` line alone once develop is clear: build a wheel first (`build_cli` in the audit script, or reuse P's built wheel), then call `check_page(page_snippets(Path("<repo-root>/frontend/src/components/screens/InfoScreens.tsx"), "<api-origin>"), s3_bin_list, env)` directly from a Python shell, since `check_page` itself makes no network call.

## What is expected but not fixed here

- The registry patterns named above, on `chore/verify-facts`: the lead's, since that branch owns `facts_registry.py`.
- `surfaces.s3_options`'s `--json` truth: resolves once `feat/8.10-p` merges.
- The document and code-copy FAILs (`CLAUDE.md`, `AGENTS.md`, `README.md`, `visualizations/*.md`, `catalogue.py`, `events.ts`): outside every builder's fence this phase.

## For the lead

1. `facts_registry.py` (on `chore/verify-facts`) needs its six literal patterns named above updated to the corrected wording once this branch merges, or each will keep reading ERROR forever rather than PASS.
2. `surfaces.mcp_tools`'s stated truth is now 4 tools, not 1; its "(One) advertised tool" pattern is the oldest of the six and predates this phase entirely.
3. The `integrations_smoke.py` `page` check could not be run live per your no-network-during-the-golden-run note; see Checks above for the static read that stands in for it.
