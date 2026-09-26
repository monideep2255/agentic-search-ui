# AGENTS.md

Instructions for `agentic-search-ui`. For all AI agents (Gemini, Copilot, Codex, GPT, etc.). Exact same content as CLAUDE.md.

This repo covers System 3 (search agent, API, UI). System 1 (data pipelines) and System 2 (knowledge graph) live in a separate repository symlinked at `reference/agentic-search-data-engineering`.

Stack: Python 3.11+, FastAPI, LangGraph, React, PostgreSQL (user data), psycopg2 (AGE graph read-only), LiteLLM/multi-model harness.

---

## Table of contents

- [Current focus](#current-focus)
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
| 2 | System 3: build (Phase 6) | IN PROGRESS. Step 6.1 (prototype) and Step 6.2 (the one reconciliation pause) are COMPLETE. Step 6.3 (v1) is underway. Current counts, all computed and verified by `python tracker/check_doc_drift.py --check`: 5704 Python tests, 459 frontend tests, 43 Playwright end-to-end declarations expanding to 50 executed cases, seven live tool premise gates, 698 decisions (DECISIONS.md), 193 learnings plus a retrospective (LEARNINGS.md). WHERE TO LOOK: `HANDOFF.md` for what is live, what awaits the product owner and the one next action; `testing/UI_fix_plan.md`, the board, for the UI fix loop; `tracker/BOARD.md` for build phases; `requirements/Plan.md` for the full dated narrative, including the build phase history that used to sit in this file. |
| 3 | System 3: tool integration | PLANNED, seven tools. cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, pathogen_detection, clinicaltrials_search. Build phases 2.1 and 3.1 to 3.5. |
| 4 | System 3: eval and tracing | Build phases 5.0 to 5.3 merged. THE EVALUATION TRACK IS CLOSED by product-owner decision on 2026-08-31, with what is left unfinished recorded under Phase 7 in `requirements/Plan.md`. Since 2026-09-12 UI fixes run through the UI fix loop, tracked on the board, `testing/UI_fix_plan.md`. Full narrative: `requirements/Plan.md`, "Build phase history, moved out of CLAUDE.md". |

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

The agent orchestrates across all three layers. Layer 1 provides the pre-ingested graph (115M nodes, 693M edges from 5 NCBI databases), hosted on Hetzner CPX42 (`<server-ip>`) and queryable via openCypher over psycopg2. Layers 2 and 3 reach live APIs for data not in the graph or for real-time enrichment.

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
| `architecture/Model_architecture.md` | Which language model answers each tier on develop, every place the loop calls a model, what checks each call's output, and the planned Jev classifier seam | Before changing a model, a tier, a prompt, or any decision point in the loop |
| `architecture/Biolink_repos_explained.md` | BioLink model reference: categories, predicates, CURIEs | Understanding the graph schema when writing Cypher |
| `architecture/Multi_agent_system_design_explained.md` | Converted external reading on how groups of AI agents fail in a shared environment: correlated failure, tacit collusion, trust and dissent errors, turf wars, and the bounded-swarm architecture that contains them | Before designing anything that runs more than one agent against a shared resource: the bossman-mode builder fan-out, tool-call rate-limit pools, or any future multi-agent retrieval path |
| `data-engineering/Knowledge_graph_on_server_reference.md` | A-Z operations reference for the live graph on Hetzner CPX42: SSH access, Cypher query examples, index listing, node/edge counts, cost breakdown | Before writing cypher_query tool or debugging graph access |
| `ncbi/NCBI_databases_and_APIs_reference.md` | All 39 NCBI databases, API endpoints, rate limits, record counts | Before implementing Layer 2 tools (ncbi_efetch, ncbi_dbsnp) |
| `ncbi/NCBI_repos_deep_dive.md` | Analysis of 13 NCBI GitHub repos: code to reuse, architecture decisions informed, patterns to adopt, what not to build locally | Before implementing any Layer 2 or Layer 3 tool; before making architecture decisions about entity resolution or data access |
| `data-engineering/Project_overview_A_to_Z.md` | Navigation hub with pointers into every doc in the project | First doc to read for project orientation |
| `build/Agent_teams_tmux_quickstart.md` | tmux launch guide so bossman-mode parallel builders show in live panes | Before running `/bossman-mode` with 2 or more builder tasks |
| `Claude_security_plugin_usage.md` | Reference for the on-demand `claude-security` scan plugin: how to run a scan, apply patches, and how it complements the always-on `security-guidance` plugin | Before the release-workflow Step 3 security scan gate, or before opening a pull request |
| `ncbi/Tool_implementation_mechanics.md` | Per-tool API traps taken from tech spec Section 6: edge-label enforcement, ELink target db, the `global_mafs` array, sequential dbSNP calls, snapshot pinning | Before wiring any of the seven tools. Facts, not policy; the policy lives in the rules |
| `build/Build_workflow_cadence.md` | The quick reference for how a build phase runs: the eleven stages, who acts at each, the model and effort per stage, where every file gets written, and the 8-hour and 8-dispatch budget. The golden consistency run blocks any answer-path change; premise gates for everything else were retired on 2026-09-24 | Before opening any build phase, and any time the model tiering is in question |
| `build/Phase_6_execution_flow.html` | The same cadence as a visual page, openable in a browser. Also published as a Claude artifact | When explaining the build loop to someone, or checking the flow at a glance |
| `build/Golden_dataset_method.md` | The complete method behind the 50-query golden dataset: the three options for what a row pins and why two were rejected, the KISS / KISSES / discovery taxonomy and why each is graded differently, why verification runs on a path independent of the agent's own tool layer, the eleven build steps, and the proof that the verifier can actually reject | Before adding, removing or editing any golden row, and before changing the eval harness's expectations |
| `build/Debugging_guide.md` | Which file to open when something is wrong. A symptom index, then one row for every Python file under `src/`, plus the frontend, test, tracker and CI files a debugger opens | When anything is broken and you do not know where to start. ALSO: update it in the same commit that adds, deletes, renames or repurposes a file under `src/`, which `tests/system_03_search_agent/test_debugging_guide_coverage.py` enforces |
| `build/Feedback_review_ritual.md` | The weekly human-gated review of captured interactions (Section 16 stage 3): the cadence, the exact commands, what the reviewer is looking for, and Section 16's own warning that most of what turns up is noise rather than a real gap | Before running the weekly review, and before promoting any competency question into the few-shot pool |
| `build/design/NCBI_design_system_migration_assessment.md` | Assessment, not a decision: what this app's design system is today, what the NCBI design system is (`@ncbi-design-system/base` 5.12.0 and `@ncbi-design-system/react` 5.12.0-b0, both NCBI-internal), which of its 25 React components could replace an app surface, and that the public NCBI Storybook is reachable off-network while the packages are not | Before scoping or deciding on a migration to the NCBI design system |
| `build/Search_and_conversation_behaviour.md` | The four situations a question puts the search agent in, stated for the product owner and testers: known item search, continuing the discussion (a pronoun binds to the most recently mentioned entity), changing the subject, and a reference with nothing behind it (the answer asks which), plus the firewall that memory guides retrieval and never assertion, each with the code that decides it and a develop check | Before testing follow-ups on develop, and before changing anything in `core/session_memory.py`, `_antecedent_curie`, `_is_memory_bound_follow_up` or `_needs_clarification` |
| `../visualizations/Architecture_diagram.md` (repository root, not `docs/`) | System 3's architecture as six Mermaid diagrams with short explanations: the five delivery surfaces over one FastAPI app, the five-step loop with the harness tier and the deterministic control at each step, the three data layers with each tool's per-call budget and rate-limit pool, the request lifecycle as a sequence of typed events, auth and identity including refresh rotation, and the two deployments plus the read-only graph query service and the three observability records | When orienting someone on how the system fits together, or before changing a surface, a loop step, a tool budget or the deployment topology |
| `../visualizations/Schema_visualization.md` (repository root, not `docs/`) | Every schema System 3 owns or reads: the Layer 1 graph slice (11 vertex labels including `NamedThing`, 14 edge labels, sample CURIEs, and which provenance properties sit on a node versus an edge), the full `v1` event contract with each payload's fields and bounds, the citation and provenance type with its trust fields, the nine-table user-data schema as an ER diagram, and one row per tool for its input and output bounds | Before changing the event contract, a citation field, a database table or a tool schema, and when checking what a payload is actually allowed to carry |

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
| phase-reviewer | dispatched by name at cadence stage 6, never by phrase | Judge, adversary or re-review round for a build phase. Runs probes, files findings to one report, closes nothing. Has Read, Grep, Glob and Bash, and deliberately NO Write or Edit: a round with full access once deleted a tracked file outside its brief |
| product-reviewer | dispatched by name at cadence stage 10, never by phrase | Pre-screen of the deployed develop app before the product owner retests: every changed screen at 1280 and 390 beside the design prototype, the golden consistency run, and a five-line answer rubric. Files what to look at first, closes nothing. Read, Grep, Glob and Bash only |

---

## Skills

User-invocable skills (slash commands):

The invocation is always the skill's exact name. A shortened alias does not resolve.

| Skill | Purpose | Invocation |
|-------|---------|-----------|
| bossman-mode | Autonomous execution in two modes: build-phase mode (a file-fenced team through the eleven-stage cadence, inside 8 hours and 8 dispatches) and UI fix mode (a product-owner defect straight to develop, no branch, no review round) | `/bossman-mode` |
| task-tracker | The in-repo build board: tickets, acceptance criteria, status, evidence, append-only history | `/task-tracker` |
| learnings | Capture what broke and what fixed it in LEARNINGS.md, and recall it before a phase | `/learnings` |
| dev-standards | Production readiness review (6 lenses) | `/dev-standards` |
| objective-review | Critical feedback, not agreement | `/objective-review` |
| repo-dive | First-principles analysis of a reference repo | `/repo-dive <path>` |
| skill-adapt-verify | Verify adapted skill for stale paths and style violations | `/skill-adapt-verify <path>` |
| ship | Run the CI gates locally (ruff over the whole repository, isort, the unit suite when Python changed, `npm run build` when the frontend changed, the doc drift check, and the registry's freshness check that proves the checkpoint ran today), sync the four canonical docs, commit with a Conventional Commit subject, push (develop in the UI fix loop, the phase branch in build-phase mode), prove the remote advanced, confirm the deploy, and clear leftover agent worktrees. Runs after `/phase-checkpoint` at any session boundary | `/ship` |
| first-principles | Explain concepts from fundamentals | `/first-principles` |
| socratic-questioning | Clarifying questions before advice | `/socratic-questioning` |
| release-workflow | End-to-end release verification and ship | `/release-workflow` |
| eval-harness | The offline evaluation gate, operationalizing the evaluation playbook: 8-point rubric, hard-fails, coverage metric, must-pass set | `/eval-harness` |
| verify | Pre-commit checks: Python compile, tests, lint, git status | `/verify` |
| standup | Where the build stands right now, in seven plain lines: phase, what landed, what is in motion this moment, what is next, how long until done, what decisions are waiting on the product owner, and what is blocked. Reports committed AND uncommitted work, including running agents and commands. Reads the tracker and git, never the conversation, so it is correct in a fresh session. Reports only, never edits | `/standup` |
| phase-checkpoint | Sync the planning and build documents at a boundary, in one of three modes: planning phase, build phase, or the UI fix loop. Its first step is a decision guard that reads the new DECISIONS.md rows and updates `tracker/Living_documents.md`, the registry of every living document and its shape, so no instruction overrules a decision. Every mode appends decisions and learnings, rewrites `HANDOFF.md` in place, and refreshes Plan.md's revision history, PROGRESS.md and the tracked counts; the UI fix loop mode also refreshes the board, the done file's cutoff and its session table. Runs before `/ship`, never touches git | `/phase-checkpoint` |
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

Last updated: 2026-09-25
