# AGENTS.md

Instructions for `agentic-search-ui`. For all AI agents (Gemini, Copilot, Codex, GPT, etc.). Exact same content as CLAUDE.md.

This repo covers System 3 (search agent, API, UI). System 1 (data pipelines) and System 2 (knowledge graph) live in a separate repository symlinked at `reference/agentic-search-data-engineering`.

Stack: Python 3.11+, FastAPI, LangGraph, React, PostgreSQL (user data), psycopg2 (AGE graph read-only), LiteLLM/multi-model harness.

---

## Table of contents

- [Current focus](#current-focus)
- [Build phase history](#build-phase-history)
- [Architecture](#architecture)
- [Reference docs (in docs/)](#reference-docs-in-docs)
- [Build order (System 3)](#build-order-system-3)
- [Agent loop pattern (every query follows this)](#agent-loop-pattern-every-query-follows-this)
- [Citations: non-negotiable](#citations-non-negotiable)
- [Data source adapter pattern](#data-source-adapter-pattern)
- [Sub-agents](#sub-agents)
- [Skills](#skills)
- [Running this project with a different agent](#running-this-project-with-a-different-agent)

---

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | System 3: planning | COMPLETE, all 5 phases (2026-07-21 to 2026-07-26): architecture decisions and source review (Phase 1), competency questions and the evaluation playbook (Phase 2, requirements/Evaluation_playbook.md), the locked PRD (Phase 3, requirements/PRD.md), the locked technical specification plus strategic memo (Phase 4, requirements/Technical_specification.md and requirements/Strategic_memo.md; requirements/System_3_overview.html combines all four Phase 4 docs), and the Phase 5 tooling and harness update (bossman-mode overhaul, task-tracker and learnings skills, new rules, requirements/phase_5/Phase_5_synthesis.md). Full narrative for every phase: requirements/Plan.md's Revision history and the requirements/phase_N/ synthesis docs. |
| 2 | System 3: build (Phase 6) | IN PROGRESS. Step 6.1 (prototype) and Step 6.2 (the one reconciliation pause) are COMPLETE. Step 6.3 (v1) is underway. Merged: build phases 1.0 through 4.1, plus 4.8 and 4.9, the web UI's visual design and its fidelity pass. Current counts, all computed and verified by `python tracker/check_doc_drift.py --check`: 4652 Python tests, 235 frontend tests, 43 Playwright end-to-end declarations expanding to 50 executed cases, seven live tool premise gates, 458 decisions (DECISIONS.md), 149 learnings plus a retrospective (LEARNINGS.md). Full narrative for every phase merged since, with PR numbers, review-round counts and findings: see [Build phase history](#build-phase-history) below. WHERE TO LOOK, since this cell deliberately no longer carries the per-phase narrative it accumulated over twenty phases: current phase status, evidence and open flags are `tracker/BOARD.md`; one file per phase with its tickets, findings and history is `tracker/phase_N.M.md`; the full dated narrative of every phase, what shipped, what review found and what it cost, is `requirements/Plan.md`'s Revision history; what to read and do before opening the next phase is `requirements/phase_6/Continuation_prompt.md`. |
| 3 | System 3: tool integration | PLANNED, seven tools. cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, pathogen_detection, clinicaltrials_search. Build phases 2.1 and 3.1 to 3.5. |
| 4 | System 3: eval and tracing | IN PROGRESS. Build phase 5.0, observability, MERGED as PR #83 on 2026-08-30 with all four CI gates green: tech spec Section 20 in full, as three records with one job each, LangSmith per-run tracing joined on `trace_id`, PostHog behavioural analytics as aggregates only, and the append-only JSONL tool-call audit log. Build phase 5.1, the 50-query golden dataset, MERGED as PR #85 on 2026-08-30: 50 questions whose constraints were established from live NCBI lookups on a path that touches none of the agent's own machinery, in three product-owner-named search categories (KISS, KISSES, discovery). Build phase 5.2, the grading harness, MERGED as PR #86 the same day and is PARKED: it does NOT work, four review rounds returned FAIL, and its own suite is green with every defect live, so `replay()` refuses to run without `acknowledge_parked=True`. Parked by product-owner decision because the 50 questions are a first attempt rather than a settled target, so grader precision is aimed at a moving specification. NEXT is a product-owner decision, not a build step: whether the 50 questions are the right 50. |

---

## Build phase history

Detailed narrative behind the [Current focus](#current-focus) table's Priority-2 row, one row per group of merged build phases, oldest first.

| Build phase(s) | What happened |
|---|---|
| 4.10, 4.2 through 4.4 | Merged most recently: build phase 4.10, the anonymous run path and the server-side guest allowance, pulled ahead of 4.2 through 4.7 by product-owner decision on 2026-08-14, because until it existed nobody could use the product without creating an account first. Merged 2026-08-16: build phase 4.2, the CLI adapter (`system3-cli`, command `s3`), as PR #47, which resumed Section 25's order. Merged 2026-08-17: build phase 4.3, the GraphQL surface via Strawberry, as PR #48, after six independent review rounds, the reference case in this repo for independent review stated as evidence rather than as principle: the first five rounds each returned FAIL and each found its worst defect inside the previous round's fix, twice in the same safety-by-proxy shape, and fourteen vacuous gate arms turned up across the phase. Reports, one per round: tracker/phase_4.3_judge_report.md, _adversary_report.md, _rereview_report.md, _rereview2_report.md, _review5_report.md; full narrative in requirements/Plan.md's Revision history. The same day, 2026-08-18, the harness itself changed rather than the product (PR #49, PR #50), prompted directly by that six-round experience: the review loop is now capped at two rounds with escalation to the product owner instead of a third, fixes touching one file go to a single serial agent rather than parallel ones, a finding located inside an earlier fix stops the phase mid-round, and `tracker/preflight.py` probes each transport before any expensive dispatch. Merged 2026-08-19: build phase 4.4, KGX export, as PR #51, a query-scoped subgraph export (seed CURIEs, bounded hops over Layer 1, writing nodes.tsv, edges.tsv and a manifest), not a full-graph snapshot, a scope Section 25 and the PRD only bound negatively and the product owner settled. It required amending the file-protection rule, which had banned KGX exporters outright: the amendment splits by direction of data flow, writing KGX into the graph stays banned here as Systems 1 and 2 work, while reading a scoped subgraph out is a delivery surface. It was the first phase to run under the capped review loop and it ran three rounds, the third authorized by the product owner through the escalation the cap exists to force, not taken unilaterally by the lead. Its critical, and the phase's most transferable result: the premise gate passed 6 of 6 while the default invocation returned 500 Articles and zero of the twelve disease edges the gate itself pinned as ground truth, with a manifest certifying it had traversed all fourteen edge labels; five of the gate's six cases passed an explicit single-label list, so the default path was exercised by none of them, and the gate's own coverage statement had already named that omission. |
| 4.5 | Merged 2026-08-20: build phase 4.5, personalization and session memory, as PR #52, then its independent review and fixes as PR #53 on 2026-08-21: bounded session memory with a tokenizer-counted cap and per-session persistence, audience depth finally reaching synthesis after riding the contract unused since build phase 1.0, and 32 curated deceased scientists wired to all four surfaces. Closes F-4.1-A-15, F-4.8-A-22 and F-4.2-03. It was the FIRST phase in this build to merge with no judge round and no adversary round. That gap was closed on 2026-08-21 as PR #53, and closing it is the strongest evidence in this repository for why the split exists: two rounds run with separate briefs and separate contexts converged independently on the same three worst defects, and both criticals were reachable in the shipped product. Session memory could defeat the deterministic unresolved-entity refusal, so a question naming a gene that does not resolve was answered about a REMEMBERED gene instead, grounded, correctly cited and shipped as outcome `answer` with no disclosure. And every guest shared one ownership identity, because `user_id` is NULL for a caller with no account, so any anonymous caller could read and overwrite any other guest's session memory; the distinguishing identity already existed and was passed to `create_run` on the line after the Query was built, it simply was not the field the check read. The gate itself was the other finding: it ran `1 failed, 1 passed, 14 skipped in 0.06s`, so most of it did not run at all, and four arms were rebuilt rather than repaired. One finding this round filed was WITHDRAWN the next day, and that is recorded rather than quietly removed: a claimed budget regression was an artifact of the measuring instrument, not of the code. |
| 4.6 | Merged 2026-08-21: build phase 4.6, feedback capture, as PR #54. Interaction capture into `interactions`, a feedback endpoint and its wired frontend, the weekly review ritual and few-shot promotion. Closes F-2.0-04 and F-2.0-10 and takes F-4.10-A-14 and F-4.1-A-15 with it, so the per-user and system-wide daily caps can finally fire after querying an always-empty table since build phase 2.0. It took THREE review rounds against a two-round budget, the third authorised by the product owner. Both criticals defeated those same daily caps: one NUL byte in a question, or pressing Stop, made a query free and uncounted, because Section 16 requires capture to be best-effort while the caps count captured rows, and neither control was wrong alone. One ticket was REJECTED for a false premise (every surface already minted a server-side trace_id) and one fix REVERTED for breaking build phase 4.1's MCP gate and bypassing its anti-leak allowlist, so coverage tags ship with the `concept:` half only. FOUR defects were found in the phase's own premise gate. Merged with three live premise arms UNRUN and accepted as such, the graph tunnel being down. |
| 4.11 | Merged 2026-08-22: build phase 4.11, the read-only HTTPS graph query service, as PR #55. It replaces the hand-opened SSH tunnel with an authenticated HTTPS endpoint co-located on the Hetzner box, behind Caddy with a Let's Encrypt certificate, on the existing read-only `kg_reader` role. The transport swap lives INSIDE `graph_connection.execute_cypher` and dispatches on `GRAPH_QUERY_URL`, leaving `cypher_query`'s schema and all three of its call sites unchanged, which demonstrates Decision D's two-way door rather than asserting it. Server-side re-validation REUSES this repository's own `validate_cypher` and `execute_cypher`, copied to the box by the deploy script and asserted byte-identical by `check_drift.sh`, so the two validators cannot drift. It closes a dangling reference between two locked sections: Section 24 said `GRAPH_QUERY_TOKEN` is populated when the service is built per Section 25, and Section 25 never assigned it to a phase. THE TUNNEL IS GONE, measured rather than claimed: 59 of 59 live premise arms pass with none open, and `tracker/preflight.py` reports `graph ok, HTTPS query service`. It ran FOUR review rounds against a two-round cap, 26 findings, THREE Rule 4 stops, each escalated to the product owner. What justified continuing was that severity fell monotonically: round 1 found reachable majors in the original code, round 2's review found an unbounded resource inside round 1's fix, round 3's found a diagnostic regression and a CPU cost inside round 2's. THE MOST TRANSFERABLE RESULT: the lead wrote THREE VACUOUS GATE ARMS and all three were caught by mutation, none by reading, one of them vacuous twice while quoting the lesson against vacuous arms in its own docstring. The durable fix is the populate-check, now on every bound arm: an arm that cannot distinguish the control holding from nothing having happened is not an arm. Round 4 was run GATE FIRST by product-owner decision, and in one round that ordering caught the real defect, caught two wrong premises in the lead's own arms, and showed that two of the three findings it set out to fix were gate gaps over already-correct code. One process failure is recorded rather than dropped: a wrong blocker was reported and an infrastructure credential requested for a firewall that does not exist, because this harness renders 'nothing listening' and 'filtered' identically. |
| 4.14 | Build phase 4.14, continuous integration, MERGED as PR #68 on 2026-08-26. Section 24's ten gates now run on every pull request, and CI is live and green on `develop`. WHAT CI FOUND ON ITS OWN, four pre-existing defects invisible to every gate, premise test and review round here: `pip install -e .` broken for the LIFE OF THE PROJECT, so `s3` and `s3-kgx-export` were uninstallable by anyone since build phase 4.2; about thirty environment values the suite needs that a clean machine lacks, which means every earlier "verified locally" figure had been measured against a developer's own `.env`; a build phase 4.7 mutation arm calling a HEALTHY assertion vacuous depending on core count; and 25 tests that could never run in CI, hidden behind a green `4019 passed`. WHAT IT COST IS NOT THE WORKFLOW: three review rounds and a RULE 4 STOP, because the premise gate was defeated TWICE by text that read correctly and executed nothing. The second defeat is the transferable one: `run: ":;#ruff check"` runs NOTHING, since bash begins a comment at `#` whenever `#` starts a word and `;` ends a word, while the checker stripped comments only after whitespace. Eight of ten gates were neutralised with all 97 tests green, including the mutation harness whose job was proving those arms could fail. THE FIX WAS A CHANGE OF APPROACH BY PRODUCT-OWNER DECISION, not a fifth patch: THE SHELL LEFT THE WORKFLOW, every gate's command is a checked-in script under `.github/gates/`, and a gate step's `run:` is exactly one token, so the check became a whole-string EQUALITY with no room for a comment or a second command. One structural arm now catches all eight injection variants. THE GENERAL LESSON: a mutation harness proves only what it mutates, and when a check keeps losing to inputs of the same shape, stop hardening the check and change what it is checking. TWO THINGS MERGED OPEN: the gates are ADVISORY rather than merge-blocking, since branch protection needs GitHub Pro or a public repository (F-4.14-A-04, a product-owner decision), and gate 5's strict path has never executed for want of a graph credential (F-4.14-RV-08). |
| 4.7, 4.12, 4.16 | Build phase 4.7, competency-question routing, MERGED as PR #56 on 2026-08-23. It is where `think_node` stopped being a build-phase-2.0 stub, and it CLOSES F-2.0-15, the finding that survived twelve phases with an owner field reading "unassigned": real query-shape classification into Section 17's five shapes, real entity resolution in exact-ID-first order with every model-extracted span live-confirmed before it contributes a CURIE, the seven must-pass questions seeded into a few-shot pool loaded once into the stable prefix, and the retirement of `plan_node`'s capitalized-token gene guess with no fallback, which dissolves F-3.1-41 and F-3.1-42 rather than deciding them. Also closes F-4.6-A-08, proven by execution rather than by reading the code. Verified: live gate 16 of 16, suite `6 failed, 3813 passed` against a baseline re-measured at the branch point, ruff clean, drift 0 stale 0 structural. WHAT IT COST: four review rounds against a two-round cap, one Rule 4 stop, three product-owner escalations. THE MOST TRANSFERABLE RESULT IS NOT THE FEATURE: the phase produced THREE separate vacuous-gate-arm findings, all written by the lead, in a file whose own docstring quotes build phase 4.11's lesson against them, and the REPAIR for the first one survived its own fix because its populate-check verified a correlate of the property rather than the property, which is the safety-by-proxy shape build phase 4.3 shipped as a critical twice. The durable fix is a permanent offline mutation harness, `tests/system_03_search_agent/core/test_cq_routing_mutation.py`, 43 cases over 11 of 13 arms, making vacuity a build failure rather than a review finding. TWO CRITICALS MERGE OPEN, each on a branch with a trigger and both HARD BLOCKERS on build phase 4.12 before any public URL: `fix/a01-injection-guardrail`, where a plain-English parenthetical still steers which gene is looked up and the guardrail admitted it 6 of 6, making it Guard-tier classification and therefore build phase 3.0's control; and `fix/a02-discontinued-gene-record`, established PRE-EXISTING because the retired regex reached the identical wrong answer. NEXT: build phase 4.16, the UI defects the live demo surfaced, MERGED as PR #63 on 2026-08-25 and verified live on the deployed product; its most transferable output is not the features but SIX assertions that could not fail, five written by the lead in one phase, none caught by reading, and the deepest of them a pair of tests that were correct, honest, and measuring the wrong property; build phase 4.12 merged as PR #62 on 2026-08-24, the product live and answering, with build phases 4.13 through 4.15 queued behind it. |
| 4.13 | Build phase 4.13, durable cross-reload search history, MERGED as PR #69 on 2026-08-27; the harness's write-first rule for findings merged the same day as PR #70. What shipped: an owner-scoped read over the `interactions` rows build phase 4.6 writes, `GET /v1/history`, the rail that renders them, and a composite index taking the read from an 18.193ms sequential scan to a 0.025ms index scan. Verified: the Python suite `4126 passed, 159 skipped, 1 xfailed, 0 failed` out of 4286 collected, 235 frontend tests, 47 of the browser suite passing with the one documented pre-existing failure, the reload path proven both in a real browser and red under mutation, and all four CI gates green on the pull request. WHAT IT COST: three review rounds against a two-round budget, the third authorised by the product owner, plus a fourth blocking finding from the final verifier, 21 findings in total; the review loop's Rule 4 stop condition fired for the first time since it was written, on exactly the shape it exists for, a defect found inside the previous round's own fix. THE MOST TRANSFERABLE RESULT: two separate defects shipped because a change made an unstated invariant false, a re-ask fix whose id generator still assumed a list that only grows, and a second writer keyed on trace ID that an older effect's match-by-question-text then overwrote; both survived review because a comment asserted the invariant that SURVIVED, not the one that broke. THREE THINGS MERGE OPEN, all product-owner decisions taken the same day: a reload still signs an account out so history appears only after signing in again; on a shared browser one person's guest searches follow whoever signs up next, owned with build phase 4.10's migration since this phase only made a pre-existing leak visible; and three minor latent findings carry named owners. Full record: `tracker/phase_4.13.md`, plus four review reports. |
| 4.15 | Build phase 4.15, the two-app release flow, MERGED as PR #71 at the phase merge on 2026-08-28, all four CI gates green, then closed by the release-permission follow-up PR #74. There are now TWO SEPARATE DEPLOYMENTS: a develop app on the `develop` branch in Railway project `system3-search-agent-develop`, and a production app on the new `production` branch in `system3-search-agent`, each with its own Postgres, Redis and `AUTH_SECRET`. `develop` REMAINS THE DEFAULT BRANCH. Merging to `develop` deploys the develop app; cutting `release/<version>` and merging it into `production` deploys the production app AND cuts a release: a semantic version derived from the Conventional Commit subjects, a CHANGELOG.md section, an annotated tag, a GitHub Release, and an automated back-merge pull request into `develop`, all built from `git log` and `gh` with no new dependency. TWO PROJECTS RATHER THAN TWO ENVIRONMENTS, and this is the fact most likely to be wrongly simplified back by someone reading Section 24: a Railway service's git source, repository plus branch, is SERVICE-level, so two environments in one project cannot watch two branches. Measured rather than assumed, since pointing one service at a branch for one environment moved BOTH environments while an untouched service kept its own branch in both; Railway's own documentation says the opposite and the contradiction is recorded rather than resolved (F-4.15-03). The phase was designed as two environments and reversed the same day. Verified: the Python suite `4157 passed, 146 skipped, 1 xfailed, 0 failed` out of 4329 collected, 40 of 41 live premise arms green, 27 mutation cases, `ruff check` clean over the whole repository, doc drift 0 stale 0 structural, all four live surfaces answering 200. WHAT IT COST: FOUR review rounds against a two-round budget, every escalation authorised by the product owner, 44 findings, and the Rule 4 stop for a defect inside an earlier fix fired TWICE. THE MOST TRANSFERABLE RESULT IS NEITHER THE FEATURE NOR A BUG: FOUR defects were a CONFIDENT SENTENCE DESCRIBING A CHECK THAT WAS NOT THERE. A docstring claimed a comparison the body never performed; an arm claimed to prove the two apps hold different signing keys while only re-proving their databases differ, which took FOUR attempts because splitting it into "corrupt a signature" plus "compare the configured values" still left one arm that never reads a key and another that never sends a request; the mutation harness claimed to cover every arm TWICE, the second time INSIDE THE FIX for the first and naming an uncovered arm as covered; and the board made the same claim a third time, written while the second was being fixed. Each survived because a confident sentence is where the next reader stops looking, and THE FIX WAS DELETION rather than a better sentence: the completeness claims are gone, replaced by a rule that cannot rot, add the mutation case in the same edit as the arm. AN ADVERSARY ROUND FOUND THE CRITICAL NOTHING ELSE COULD: the develop web app was live, answered 200, and could reach NO API, because `VITE_API_BASE_URL` is compiled in at BUILD time and was set after the build, so the bundle shipped `http://127.0.0.1:8000`, the visitor's own machine. It satisfied every acceptance criterion including "all four surfaces answer 200", and no arm caught it because none had ever fetched a web URL. CI CAUGHT WHAT LOCAL RUNS DID NOT, one phase after the phase that added CI: gate 3 is `ruff check` with NO path, the whole repository, while every local check ran `ruff check src services`. THREE THINGS MERGE OPEN: CI stays ADVISORY rather than merge-blocking (F-4.14-A-04, unchanged); the back-merge pull request runs NO CI because `gh pr create` with the built-in token cannot raise workflow events, disclosed in the script, the pull request body and `docs/build/Release_flow.md` rather than closed by putting a personal access token into the release path; and P5 is red until the FIRST RELEASE rather than until this merge. NEXT: the first release, which is the only end-to-end proof the promotion path works. |
| 5.0 | Build phase 5.0, observability, MERGED as PR #83 on 2026-08-30, all four CI gates green. It delivers technical specification Section 20 in full, as THREE records with one job each so no single outage blinds the picture: LangSmith per-run tracing joined to everything else on `trace_id`, live and with account PII proven absent by reading traces back OUT of the service rather than by asserting it locally; PostHog behavioural analytics, aggregates only, on a `phc_` project token, with a `phx_` personal key or `phs_` project secret now REFUSED by prefix so a privileged credential cannot be used for capture; and the append-only JSONL tool-call audit log, one line per Layer 1, 2 and 3 access with its authorization recorded by identifier, never by value. THE DESIGN DECISION MOST LIKELY TO BE WRONGLY SIMPLIFIED BACK: the audit hook sits at the three TRANSPORT chokepoints and never at `act_node`, because five production call sites reach a data layer without passing through `act_node` and a live query proved it rather than a test, the first audit line ever written being `think_node`'s symbol resolution; the transport is also the ONLY place Section 20.3's required HTTP status and latency still exist, since both are discarded before a tool returns. The error field is BOUNDED, not scanned: both sinks discard free text and keep only a classified code and an exception class name. WHAT IT COST: one judge round, one adversary round and FIVE fix-and-verify rounds on ONE control, three Rule 4 stops, a design reversal authorized by the product owner, and 31 findings plus 30 from the adversary. Four consecutive rounds each shipped a fix defeated by an input of the SAME family, something upstream consuming the credential before the check saw it; the reversal that worked was to stop scanning text and BOUND what may enter the sink, which is `attack-the-constraint` applied to a check. THE MOST TRANSFERABLE RESULT IS A CRITIQUE OF THE LEAD'S OWN DECOMPOSITION rather than of any line of code: four rounds hardened the LOCAL audit sink's error field while the identical string shipped OFF-BOX to LangSmith with no control at all, found independently by both the judge and the adversary and by neither the lead nor any fix agent, because every round was scoped from the file the previous round had been editing rather than from where credentials actually flow. THE CLOSING SESSION ADDED ONE MORE OF THE SAME FAMILY, recorded rather than tidied away: the handoff, the continuation prompt and a commit message all said the phase's last item was open, and that same commit contained its fix, its two arms, its mutation case and its `fixed` status; the previous session had genuinely re-probed and still concluded wrongly, because it varied the KEY rather than the control (F-5.0-29). CI THEN FOUND WHAT NO LOCAL CHECK COULD, for the second phase running: gate 2, `isort --check-only`, went red on a file new in the phase while everything local was green, because `/verify` does not run `isort`, so that gate had never executed against the branch at all (F-5.0-30). Its fix was chosen by measuring three forms rather than taking the formatter's output, since isort is NOT idempotent here and its converged form silently broadens a `# noqa` from one name to three. FOUR THINGS MERGE OPEN with named owners: the analytics event is awaited INLINE on the query path with the patch written and deliberately not applied (A-5.0-24, a product-owner decision on 2026-08-30 to make it its own follow-up); an ordinary string under an ordinary key still reaches LangSmith unredacted (A-5.0-14); the old `phx_` PostHog personal key still needs revoking by hand, though it was never committed, `.env` being untracked and gitignored; and a side-effect import that no arm distinguishes from its own absence (F-5.0-31). |

---

## Architecture

```
Agent loop (every query):
  Guardrail -> Think -> Plan -> Act -> Write

Three-layer data access:
  Layer 1: Knowledge graph (Cypher via psycopg2 to AGE on Hetzner VPS, read-only)
  Layer 2: NCBI APIs live (EFetch, ELink, dbSNP REST, called at query time)
  Layer 3: Enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov)
```

The agent orchestrates across all three layers. Layer 1 provides the pre-ingested graph (115M nodes, 693M edges from 5 NCBI databases), hosted on Hetzner CPX42 (46.225.128.133) and queryable via openCypher over psycopg2. Layers 2 and 3 reach live APIs for data not in the graph or for real-time enrichment.

Multi-model harness with three tiers:
- Guard tier: fast, cheap model for input validation and guardrails
- Plan tier: mid-range model for query decomposition and tool selection
- Synth tier: strongest model for final answer synthesis and citation assembly

---

## Reference docs (in docs/)

| Doc | What it is | Read when |
|-----|-----------|-----------|
| `architecture/System_3_architecture_brainstorming.md` | Architecture design for the search agent: agent loop, tools, multi-model harness, cost model, deployment | Before writing any System 3 code |
| `architecture/Three_layer_data_architecture.md` | Layer 1 (graph), Layer 2 (on-demand API), Layer 3 (enrichment). How System 3 accesses each layer. | Understanding data access patterns |
| `architecture/Biolink_repos_explained.md` | BioLink model reference: categories, predicates, CURIEs | Understanding the graph schema when writing Cypher |
| `architecture/Multi_agent_system_design_explained.md` | Converted external reading on how groups of AI agents fail in a shared environment: correlated failure, tacit collusion, trust and dissent errors, turf wars, and the bounded-swarm architecture that contains them | Before designing anything that runs more than one agent against a shared resource: the bossman-mode builder fan-out, tool-call rate-limit pools, or any future multi-agent retrieval path |
| `data-engineering/Knowledge_graph_on_server_reference.md` | A-Z operations reference for the live graph on Hetzner CPX42: SSH access, Cypher query examples, index listing, node/edge counts, cost breakdown | Before writing cypher_query tool or debugging graph access |
| `ncbi/NCBI_databases_and_APIs_reference.md` | All 39 NCBI databases, API endpoints, rate limits, record counts | Before implementing Layer 2 tools (ncbi_efetch, ncbi_dbsnp) |
| `ncbi/NCBI_repos_deep_dive.md` | Analysis of 13 NCBI GitHub repos: code to reuse, architecture decisions informed, patterns to adopt, what not to build locally | Before implementing any Layer 2 or Layer 3 tool; before making architecture decisions about entity resolution or data access |
| `data-engineering/Project_overview_A_to_Z.md` | Navigation hub with pointers into every doc in the project | First doc to read for project orientation |
| `build/Agent_teams_tmux_quickstart.md` | tmux launch guide so bossman-mode parallel builders show in live panes | Before running `/bossman-mode` with 2 or more builder tasks |
| `Claude_security_plugin_usage.md` | Reference for the on-demand `claude-security` scan plugin: how to run a scan, apply patches, and how it complements the always-on `security-guidance` plugin | Before the release-workflow Step 3 security scan gate, or before opening a pull request |
| `ncbi/Tool_implementation_mechanics.md` | Per-tool API traps taken from tech spec Section 6: edge-label enforcement, ELink target db, the `global_mafs` array, sequential dbSNP calls, snapshot pinning | Before wiring any of the seven tools. Facts, not policy; the policy lives in the rules |
| `build/Build_workflow_cadence.md` | The quick reference for how a build phase runs: the twelve stages, who acts at each, the model and effort per stage, where every file gets written. Stage 5, the premise gate, is mandatory and blocking for any phase whose deliverable is model-generated | Before opening any build phase, and any time the model tiering is in question |
| `build/Phase_6_execution_flow.html` | The same cadence as a visual page, openable in a browser. Also published as a Claude artifact | When explaining the build loop to someone, or checking the flow at a glance |
| `build/Golden_dataset_method.md` | The complete method behind the 50-query golden dataset: the three options for what a row pins and why two were rejected, the KISS / KISSES / discovery taxonomy and why each is graded differently, why verification runs on a path independent of the agent's own tool layer, the eleven build steps, and the proof that the verifier can actually reject | Before adding, removing or editing any golden row, and before changing the eval harness's expectations |
| `build/Feedback_review_ritual.md` | The weekly human-gated review of captured interactions (Section 16 stage 3): the cadence, the exact commands, what the reviewer is looking for, and Section 16's own warning that most of what turns up is noise rather than a real gap | Before running the weekly review, and before promoting any competency question into the few-shot pool |

---

## Build order (System 3)

The authoritative build order is `requirements/Technical_specification.md` Section 25: 26 numbered build phases from 1.0 to 7.1, each with:

- Its branch name
- What it delivers
- What it depends on
- A dependency graph

Read that section, not a summary. The four-week table that used to live here is superseded.

Shape of the sequence:

| Group | Delivers | Maps to Plan.md |
|-------|----------|-----------------|
| 1.0 to 1.2 | FastAPI skeleton with the typed event contract, auth and the user-data schema, React shell with SSE | Step 6.1, the prototype |
| 2.0 to 2.2 | LangGraph loop and the three-tier harness, `cypher_query` over Layer 1, deterministic cite-or-refuse | Step 6.1, the prototype |
| 3.0 to 3.5 | Full guardrail, the six remaining tools, provenance and the two-tier trust gate | Step 6.3, v1 |
| 4.0 to 4.7 | The six delivery surfaces, personalization and memory, feedback capture, competency-question routing | Step 6.3, v1 |
| 5.0 to 5.1 | LangSmith tracing, PostHog, the 50-query golden dataset and eval harness | Step 6.3, v1 |
| 6.0 to 6.1 | Rate limiting and concurrency, the full `dev-standards` pass and release hardening | Step 6.3, v1 |
| 7.0 to 7.1 | model-bench per tier, the A/B routing mechanism | Step 6.3, v1 |

Step 6.2, the one reconciliation pause, sits between the prototype and v1.

---

## Agent loop pattern (every query follows this)

```
Step 1: Guardrail  - validate input, reject prompt injection, check rate limits
Step 2: Think      - classify query intent, identify required data layers
Step 3: Plan       - decompose into tool calls, select model tier per step
Step 4: Act        - execute tool calls (Cypher, NCBI APIs, enrichment APIs)
Step 5: Write      - synthesize answer with inline citations, format for UI
```

Tools live in `system_03_search_agent/tools/`. Each tool is a self-contained module with:

- A schema
- An execute function
- A test fixture

---

## Citations: non-negotiable

Every fact in a response must link back to its source:
- Graph results: link to the NCBI source record via `source_url` stored on each node/edge
- Layer 2 API results: link to the NCBI record page (e.g., `https://www.ncbi.nlm.nih.gov/gene/7157`)
- Layer 3 enrichment: link to the enrichment source (PubTator annotation, LitVar2 page, clinical trial)

Every claim must be verifiable. This is the trust moat.

---

## Data source adapter pattern

Each NCBI data source implements only the adapters that apply to its capabilities. No monolithic interface.

Adapter types:
- `QueryAdapter` (required): accepts a structured query, returns results
- `FacetAdapter` (optional): supports faceted search (PubMed has this; Gene does not)
- `CitationAdapter` (optional): returns structured citation metadata (PubMed, ClinVar)
- `RelationshipAdapter` (optional): can traverse entity relationships (Gene, MedGen)
- `StreamingAdapter` (optional): supports streaming large result sets (dbSNP)

The agent checks adapter availability before attempting operations. If a source lacks `FacetAdapter`, the agent skips faceted refinement for that source. No "not implemented" exceptions, no silent no-ops.

---

## Sub-agents

| Agent | Magic words | Purpose |
|-------|-------------|---------|
| first-principles | `what is`, `explain`, `how does X work` | Explain technical concepts |
| socratic | `should I`, `help me decide`, `I'm stuck` | Clarifying questions before advice |
| objective-review | `review this`, `is this good`, `am I missing` | Critical feedback |
| action-planner | `plan`, `action items`, `todos` | Break work into tasks |
| git-sync | `sync`, `push`, `pull` | GitHub operations |
| docs-sync | `update docs`, `sync docs` | Update documentation |
| doc-auditor | dispatched by doc-readability, never by phrase | Grade a restructured or authored document for lost facts and style, from fresh context |

---

## Skills

User-invocable skills (slash commands):

The invocation is always the skill's exact name. A shortened alias does not resolve.

| Skill | Purpose | Invocation |
|-------|---------|-----------|
| bossman-mode | Autonomous execution with agent teams | `/bossman-mode` |
| task-tracker | The in-repo build board: tickets, acceptance criteria, status, evidence, append-only history | `/task-tracker` |
| learnings | Capture what broke and what fixed it in LEARNINGS.md, and recall it before a phase | `/learnings` |
| dev-standards | Production readiness review (6 lenses) | `/dev-standards` |
| objective-review | Critical feedback, not agreement | `/objective-review` |
| repo-dive | First-principles analysis of a reference repo | `/repo-dive <path>` |
| skill-adapt-verify | Verify adapted skill for stale paths and style violations | `/skill-adapt-verify <path>` |
| ship | Sync docs, commit, push phase branch, and clear leftover agent worktrees | `/ship` |
| first-principles | Explain concepts from fundamentals | `/first-principles` |
| socratic-questioning | Clarifying questions before advice | `/socratic-questioning` |
| release-workflow | End-to-end release verification and ship | `/release-workflow` |
| eval-harness | The offline evaluation gate, operationalizing the evaluation playbook: 8-point rubric, hard-fails, coverage metric, must-pass set | `/eval-harness` |
| verify | Pre-commit checks: Python compile, tests, lint, git status | `/verify` |
| standup | Where the build stands right now, in five plain lines: phase, what landed, what is in motion this moment, what is next, what is blocked. Reports committed AND uncommitted work, including running agents and commands. Reads the tracker and git, never the conversation, so it is correct in a fresh session. Reports only, never edits | `/standup` |
| phase-checkpoint | Sync planning docs at a phase or sub-phase boundary (decisions, session doc, meeting note, continuation prompt, and at phase end the synthesis and Plan status). Runs before `/ship`, never touches git | `/phase-checkpoint` |
| doc-readability | Make one named document readable in house style: break prose walls, add the table of contents, add Mermaid, add first-principles explanation. Gated by a bundled no-loss script plus a fresh-context auditor, so no fact is lost. Refuses the two locked requirements documents | `/doc-readability` |

Auto-read skills (loaded by other skills or before specific tasks): best-practices, release-workflow, dev-standards.

All rules are in `.claude/rules/` and loaded automatically. No need to duplicate here.

---

## Running this project with a different agent

The harness was audited for portability on 2026-07-26. The model layer is swappable; the enforcement layer is not, yet. Read this before handing execution to a non-Claude-Code agent.

Portable as is, no changes needed:

- The file artifacts: `tracker/BOARD.md`, `tracker/phase_N.M.md`, `LEARNINGS.md`, `DECISIONS.md`. Plain markdown any agent can read and write.
- `tracker/render_board.py`. Stdlib Python, no Claude Code dependency. Verified by running it outside a Claude Code context.
- `tracker/check_doc_drift.py`. Stdlib Python, no Claude Code dependency. Computes every tracked count (tests, DECISIONS.md and LEARNINGS.md rows, open flags) from source and fails on a stale value; `phase-checkpoint` and `verify` both gate on it, and the `learnings` skill runs it after every append.
- `tracker/preflight.py`. Stdlib Python (`http.client`, `socket`, `ssl`), no Claude Code dependency. Probes one endpoint per transport, the product's model provider, the harness's own provider, and the graph, before any expensive agent dispatch. Wired into bossman-mode Step 1 and `docs/build/Build_workflow_cadence.md` stage 4.
- `.claude/skills/doc-readability/scripts/check_preservation.py` and `check_style.py`. Stdlib Python, no Claude Code dependency. The first proves a restructured document lost no fact, the second checks house style on one file. Both carry `--self-test` and `--mutation-test` harnesses that assert each arm can fail as well as pass. Note that only the script half of the `doc-readability` gate ports: its second half is the `doc-auditor` sub-agent, which is Claude Code coupled like every other agent here.
- Every planning document in `requirements/` and every reference doc in `docs/`.
- The model tiering, which names capability tiers rather than products. See `docs/build/Build_workflow_cadence.md` under "Provider mapping" for the tier-to-model table. Switching providers is a one-table edit.

Portable content, Claude-Code-coupled invocation:

- Skills under `.claude/skills/`. The bodies are plain markdown instructions any agent can follow. What does not port is the frontmatter routing and slash-command invocation. Another agent invokes a skill by reading its `SKILL.md` at its file path, not by typing its name.
- Sub-agents under `.claude/agents/`. Same split: the prompts port, the dispatch mechanism does not.
- Rules under `.claude/rules/`. They auto-load in Claude Code. Another agent must be pointed at the directory explicitly, and `AGENTS.md` should say so.

Does not port, and this is the blocker:

- The four security hooks (`scan-secrets.sh`, `scan-write-secrets.sh`, `block-bash-delete.sh`, `block-sensitive-read.sh`) are wired to Claude Code's PreToolUse and PostToolUse contract, and a fifth, `scan-duplicate-copies.sh`, is wired to SessionStart. These five are the only structural enforcement in this repo; every other control is an instruction a model chooses to obey. `scan-duplicate-copies.sh` is also the one hook that mutates the filesystem unattended (moving verified byte-identical duplicate-copy artifacts to Trash, never `rm`), since a SessionStart hook's internal commands are not gated by `block-bash-delete.sh`, which only fires on Bash calls Claude itself issues. Under another harness none of the five run, and nothing reports that they did not.
- `sync-agents-md.sh` and `sync-board.sh`, the same way. Their absence is quieter but leaves stale generated files.
- Agent teams and the tmux pane display. Parallel execution would need whatever the other agent provides instead.

Before any non-Claude-Code agent runs a build phase, in this order:

1. Stand up a substitute for the security hooks, most likely a git pre-commit hook, since losing secret scanning silently is the worst failure available here.
2. Replace the two sync hooks with an explicit step, or accept that generated files must be regenerated by hand at phase close.
3. Document skill and sub-agent invocation by file path in `AGENTS.md`, since slash commands will not resolve.

The rule of thumb the audit confirmed: anything expressed as a file is portable, anything expressed as a mechanism is not. That is why these were built as files:

- The board
- The learnings log
- The renderer

Security hooks in `.claude/hooks/` (wired in `.claude/settings.json`) run on PreToolUse (secret scan on Bash commands, secret scan on config writes, deletion block) and SessionStart (context-injection scan, session context, duplicate-copy scan and auto-clear).

---

Last updated: 2026-08-30
