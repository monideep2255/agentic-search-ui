# CLAUDE.md

Claude Code instructions for `agentic-search-ui`. This IS a software project.

This repo covers System 3 (search agent, API, UI). System 1 (data pipelines) and System 2 (knowledge graph) live in a separate repository symlinked at `reference/agentic-search-data-engineering`.

Stack: Python 3.11+, FastAPI, LangGraph, React, PostgreSQL (user data), psycopg2 (AGE graph read-only), LiteLLM/multi-model harness.

---

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | System 3: planning | COMPLETE, all 5 phases (2026-07-21 to 2026-07-26): architecture decisions and source review (Phase 1), competency questions and the evaluation playbook (Phase 2, requirements/Evaluation_playbook.md), the locked PRD (Phase 3, requirements/PRD.md), the locked technical specification plus strategic memo (Phase 4, requirements/Technical_specification.md and requirements/Strategic_memo.md; requirements/System_3_overview.html combines all four Phase 4 docs), and the Phase 5 tooling and harness update (bossman-mode overhaul, task-tracker and learnings skills, new rules, requirements/phase_5/Phase_5_synthesis.md). Full narrative for every phase: requirements/Plan.md's Revision history and the requirements/phase_N/ synthesis docs. |
| 2 | System 3: build (Phase 6) | IN PROGRESS, Step 6.1 prototype. Done and merged: build phases 1.0 (FastAPI skeleton, event contract, PR #5), 1.1 (auth service, PostgreSQL user-data schema, PR #6), 2.0 (real LangGraph loop, three-tier harness, PR #9), 1.2 (React shell, SSE streaming, chat UI wired end to end, PR #12), 2.1 (cypher_query over Layer 1, first live graph access, PR #15). Build phase 2.1 closed after five judge passes and five adversary passes: it failed four consecutive reviews with a green suite, and the cause was a composition defect between a stub query_class and a 0-hop schema slice that handed the generator no Disease label. Read LEARNINGS.md's retrospective before opening any tool phase. The process changes it forced merged as PR #16, including a new BLOCKING cadence stage: write the premise gate and watch it fail before any tool code. Build phase 2.2 (deterministic cite-or-refuse, Layer 1 provenance, the first trust signal) closed 2026-08-03 after three independent review rounds. Rounds 1 and 2 each returned a failing verdict, and each round's worst defect was in the previous round's fix, the pattern the 2.1 retrospective predicts. Every adversary, judge and re-review exploit now refuses, verified by hand and mutation-tested. Two findings are deliberately open and carried to Step 6.2: F-2.2-T-01-residual (a comma-spliced injection inside a single wh-question, pinned by a strict xfail) and F-2.2-A-05 (the flagship gene-disease claim classifies low risk, since a Disease endpoint row is indistinguishable from an identifier lookup at that boundary). Next: build phase 3.0, the full guardrail, continuing in Section 25 order. Step 6.2 moved on 2026-08-03 to run after the 3.x tool phases, since its own reasoning names 3.x as the code its security scan most exists for, and reconciling the frozen documents after the tool phases is better input than before them. That scan is separately PAUSED INDEFINITELY on cost; exposure is the one condition that turns it back on, meaning a deploy, a public URL, or first contact with a user who is not the product owner. 202 decisions logged (DECISIONS.md), 43 learnings plus a retrospective (LEARNINGS.md), 1154 Python tests plus 120 frontend tests plus 3 Playwright end-to-end tests passing, plus a live premise gate at 9 of 9. These counts are checked by `python tracker/check_doc_drift.py --check`. Full per-phase detail, what shipped, judge and adversary findings, decisions, release gate outcomes: requirements/Plan.md's Revision history. Current phase status and open flags: tracker/BOARD.md. |
| 3 | System 3: tool integration | PLANNED, seven tools. cypher_query, ncbi_efetch, ncbi_dbsnp, pubtator_annotate, litvar2_lookup, pathogen_detection, clinicaltrials_search. Build phases 2.1 and 3.1 to 3.5. |
| 4 | System 3: eval and tracing | PLANNED. LangSmith tracing, PostHog, the 50-query golden dataset, the eval harness against the playbook. Build phases 5.0 and 5.1. |

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
| `data-engineering/Knowledge_graph_on_server_reference.md` | A-Z operations reference for the live graph on Hetzner CPX42: SSH access, Cypher query examples, index listing, node/edge counts, cost breakdown | Before writing cypher_query tool or debugging graph access |
| `ncbi/NCBI_databases_and_APIs_reference.md` | All 39 NCBI databases, API endpoints, rate limits, record counts | Before implementing Layer 2 tools (ncbi_efetch, ncbi_dbsnp) |
| `ncbi/NCBI_repos_deep_dive.md` | Analysis of 13 NCBI GitHub repos: code to reuse, architecture decisions informed, patterns to adopt, what not to build locally | Before implementing any Layer 2 or Layer 3 tool; before making architecture decisions about entity resolution or data access |
| `data-engineering/Project_overview_A_to_Z.md` | Navigation hub with pointers into every doc in the project | First doc to read for project orientation |
| `build/Agent_teams_tmux_quickstart.md` | tmux launch guide so bossman-mode parallel builders show in live panes | Before running `/bossman-mode` with 2 or more builder tasks |
| `Claude_security_plugin_usage.md` | Reference for the on-demand `claude-security` scan plugin: how to run a scan, apply patches, and how it complements the always-on `security-guidance` plugin | Before the release-workflow Step 3 security scan gate, or before opening a pull request |
| `ncbi/Tool_implementation_mechanics.md` | Per-tool API traps taken from tech spec Section 6: edge-label enforcement, ELink target db, the `global_mafs` array, sequential dbSNP calls, snapshot pinning | Before wiring any of the seven tools. Facts, not policy; the policy lives in the rules |
| `build/Build_workflow_cadence.md` | The quick reference for how a build phase runs: the twelve stages, who acts at each, the model and effort per stage, where every file gets written. Stage 5, the premise gate, is mandatory and blocking for any phase whose deliverable is model-generated | Before opening any build phase, and any time the model tiering is in question |
| `build/Phase_6_execution_flow.html` | The same cadence as a visual page, openable in a browser. Also published as a Claude artifact | When explaining the build loop to someone, or checking the flow at a glance |

---

## Build order (System 3)

The authoritative build order is `requirements/Technical_specification.md` Section 25: 26 numbered build phases from 1.0 to 7.1, each with its branch name, what it delivers, what it depends on, and a dependency graph. Read that section, not a summary. The four-week table that used to live here is superseded.

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

Tools live in `system_03_search_agent/tools/`. Each tool is a self-contained module with a schema, execute function, and test fixture.

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
| ship | Sync docs, commit, push phase branch | `/ship` |
| first-principles | Explain concepts from fundamentals | `/first-principles` |
| socratic-questioning | Clarifying questions before advice | `/socratic-questioning` |
| release-workflow | End-to-end release verification and ship | `/release-workflow` |
| eval-harness | The offline evaluation gate, operationalizing the evaluation playbook: 8-point rubric, hard-fails, coverage metric, must-pass set | `/eval-harness` |
| verify | Pre-commit checks: Python compile, tests, lint, git status | `/verify` |
| phase-checkpoint | Sync planning docs at a phase or sub-phase boundary (decisions, session doc, meeting note, continuation prompt, and at phase end the synthesis and Plan status). Runs before `/ship`, never touches git | `/phase-checkpoint` |

Auto-read skills (loaded by other skills or before specific tasks): best-practices, release-workflow, dev-standards.

All rules are in `.claude/rules/` and loaded automatically. No need to duplicate here.

---

## Running this project with a different agent

The harness was audited for portability on 2026-07-26. The model layer is swappable; the enforcement layer is not, yet. Read this before handing execution to a non-Claude-Code agent.

Portable as is, no changes needed:

- The file artifacts: `tracker/BOARD.md`, `tracker/phase_N.M.md`, `LEARNINGS.md`, `DECISIONS.md`. Plain markdown any agent can read and write.
- `tracker/render_board.py`. Stdlib Python, no Claude Code dependency. Verified by running it outside a Claude Code context.
- `tracker/check_doc_drift.py`. Stdlib Python, no Claude Code dependency. Computes every tracked count (tests, DECISIONS.md and LEARNINGS.md rows, open flags) from source and fails on a stale value; `phase-checkpoint` already gates on it, `verify` does not yet.
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

The rule of thumb the audit confirmed: anything expressed as a file is portable, anything expressed as a mechanism is not. That is why the board, the learnings log, and the renderer were built as files.

Security hooks in `.claude/hooks/` (wired in `.claude/settings.json`) run on PreToolUse (secret scan on Bash commands, secret scan on config writes, deletion block) and SessionStart (context-injection scan, session context, duplicate-copy scan and auto-clear).

---

Last updated: 2026-08-03
