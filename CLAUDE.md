# CLAUDE.md

Claude Code instructions for `agentic-search-ui`. This IS a software project.

This repo covers System 3 (search agent, API, UI). System 1 (data pipelines) and System 2 (knowledge graph) live in a separate repository symlinked at `reference/agentic-search-data-engineering`.

Stack: Python 3.11+, FastAPI, LangGraph, React, PostgreSQL (user data), psycopg2 (AGE graph read-only), LiteLLM/multi-model harness.

---

## Current focus

| Priority | System | Status |
|----------|--------|--------|
| 1 | System 3: planning | COMPLETE, all 5 phases (2026-07-21 to 2026-07-26): architecture decisions and source review (Phase 1), competency questions and the evaluation playbook (Phase 2, requirements/Evaluation_playbook.md), the locked PRD (Phase 3, requirements/PRD.md), the locked technical specification plus strategic memo (Phase 4, requirements/Technical_specification.md and requirements/Strategic_memo.md; requirements/System_3_overview.html combines all four Phase 4 docs), and the Phase 5 tooling and harness update (bossman-mode overhaul, task-tracker and learnings skills, new rules, requirements/phase_5/Phase_5_synthesis.md). Full narrative for every phase: requirements/Plan.md's Revision history and the requirements/phase_N/ synthesis docs. |
| 2 | System 3: build (Phase 6) | IN PROGRESS, Step 6.1 prototype. Done and merged: build phases 1.0 (FastAPI skeleton, event contract, PR #5), 1.1 (auth service, PostgreSQL user-data schema, PR #6), 2.0 (real LangGraph loop, three-tier harness, PR #9), 1.2 (React shell, SSE streaming, chat UI wired end to end, PR #12), 2.1 (cypher_query over Layer 1, first live graph access, PR #15). Build phase 2.1 closed after five judge passes and five adversary passes: it failed four consecutive reviews with a green suite, and the cause was a composition defect between a stub query_class and a 0-hop schema slice that handed the generator no Disease label. Read LEARNINGS.md's retrospective before opening any tool phase. The process changes it forced merged as PR #16, including a new BLOCKING cadence stage: write the premise gate and watch it fail before any tool code. Build phase 2.2 (deterministic cite-or-refuse, Layer 1 provenance, the first trust signal) closed 2026-08-03 after three independent review rounds. Rounds 1 and 2 each returned a failing verdict, and each round's worst defect was in the previous round's fix, the pattern the 2.1 retrospective predicts. Every adversary, judge and re-review exploit now refuses, verified by hand and mutation-tested. Two findings are deliberately open and carried to Step 6.2: F-2.2-T-01-residual (a comma-spliced injection inside a single wh-question, pinned by a strict xfail) and F-2.2-A-05 (the flagship gene-disease claim classifies low risk, since a Disease endpoint row is indistinguishable from an identifier lookup at that boundary). Build phase 3.0 (the full guardrail: Section 10.2's non-LLM pre-filter, 10.3 boundary validation, 10.4 Guard-tier injection and off-topic classification, 10.5 forbidden types and read-only) closed 2026-08-04 after one judge round and one adversary round, merged as PR #19. Its premise gate has two arms, because a guardrail has no safe direction of failure: `return refuse` scores perfectly on every attack test and destroys the product, so nine of its eighteen cases are legitimate questions that must be admitted. Written first and watched failing 9 of 20, now 20 of 20. One judge round returned FAIL with all 34 acceptance criteria individually passing, which is the argument for having a premise rather than a checklist: genuinely off-topic queries like "What is the capital of the USA?" were fully admitted, because the pre-filter's deliberately over-broad symbol pattern was excused by a code comment claiming the classifier would catch it, and the classifier judged only injection. One adversary round filed eight findings, two critical, including four third-person clinical questions ("Should this patient be started on tamoxifen?") that passed every layer since no layer owned advice about a third party. Six findings fixed and re-verified end to end. Two tickets carried: T-3.0-07 (clearing the F-2.1-J4-02 xfail needs the graph tunnel, which cannot be opened from this environment) and T-3.0-08 (F-2.1-C15's generation half, untouched). Build phase 3.1 (`ncbi_efetch`) merged as PR #22 on 2026-08-05, then closed out fully via PR #23 (commit `97aec83`) on 2026-08-07, after three independent re-review rounds paid off the re-review debt PR #22 left open. The F-2.1-C15 generation bound, the finding where a generated query took the graph server down for every user, closed on `fix/c15-generation-bound`, merged as PR #24 (commit `15efe57`) on 2026-08-07: `validate_cypher` now rejects a variable-length relationship pattern before execution. Its own first version was itself found bypassable by a fresh-context review (a nested bracket alongside the pattern defeated a hop-scoped check), fixed with a standalone pattern, and confirmed by a second independent review. F-2.2-01 (a separate, lower-severity generation flake) was deliberately left open rather than folded into the same branch; full account: `tracker/fix_c15_generation_bound.md`. Build phase 3.2 (`ncbi_dbsnp`, the second Layer 2 tool: variant normalization and dbSNP record retrieval over Variation Services and dbSNP ESummary) closed 2026-08-08 on `phase/3.2-ncbi-dbsnp`, merged as PR #25, after six full review passes: a blocking premise gate written and watched failing first (8 failed, 0 passed, every failure a `ModuleNotFoundError`, the correct direction per LEARNINGS.md row 43), an adversary round of 14 findings against the live APIs (a `_cap()` truncation shipping a wrong-length variant and a silently dropped clinical term both under `status: "ok"`, and a bare numeric rsid returning a confident, cited, unrelated variant), a judge round returning FAIL with 6 more findings (the premise gate's own coverage statement omitted the two gaps that mattered most, and `ClassificationResult` carried no HTTP status to tell a 429 from a 404), a fix round closing all five confirmed-blocking findings (refuse-not-truncate in place of silent truncation, an `rs`-prefix shape requirement at the schema layer closing the bare-numeric-rsid gap, an `allele_role` label distinguishing reference from variant population frequencies, and HTTP status threaded into the error message to tell transient from permanent), an independent fresh-context re-review that found two more defects inside that fix round itself (the refuse-not-truncate policy refusing roughly 10.4 percent of real clinically-cited variants outright, since two standard ClinVar vocabulary terms exceed the locked 40-char cap, and an inverted 5xx-versus-permanent-error message on a deterministic reference-mismatch input), and a second fix round closing both, lead-verified a third time. Every finding this phase's review filed was real; zero rejected across two full rounds. The truncation fix landed as field-level withholding (`fields_withheld`) rather than whole-call refusal, since the locked cap is too tight for real data and raising it unilaterally is not this ticket's call: `spdi_canonical` is the one field kept as whole-call refusal, since without it there is no variant identity to attach anything else to. Three spec-versus-reality gaps carried to Step 6.2: Section 25's build-order line for this phase names the dbVar coordinate-overlap sub-tool, which already shipped in build phase 3.1; Section 6.3 names `spdi/{spdi}/canonical_representative` as the SPDI normalization endpoint, live-confirmed broken server-side on every well-formed input tried including NCBI's own documented example, substituted with the live-working `/spdi/{spdi}/contextual`, unverified beyond not crashing on malformed input; and the `clinical_significance` 40-char item cap itself, too tight for real ClinVar vocabulary. Full account: `tracker/phase_3.2.md`. Build phase 3.3 (`pubtator_annotate` and `litvar2_lookup`, the two Layer 3 enrichment tools) closed 2026-08-08 on `phase/3.3-enrichment-tools`, merged as PR #26, after ten review rounds: a blocking premise gate written and watched failing first, a judge round (FAIL, two majors), a fix round, an independent re-review that found a real regression in that fix round, a second fix round, an adversary round against the live APIs (13 findings, 1 critical: both tools were silently discarding the upstream API's own match-relevance signal, so a bare number or a common word returned confidently cited but wholly unrelated data), a third fix round, a fourth fix round closing several carried findings that turned out addressable without a product decision after all (an entity_lookup citation, a real dbSNP citation replacing LitVar2's own unverifiable client-rendered UI, and disclosure parity between the two tools), an independent re-review of that round that found one more real regression (a multi-match result citing only its first, unrelated match as if it covered the whole answer), and a fifth fix round closing it. Build phase 3.5 (`pathogen_detection`, bulk access to the NCBI Pathogen Detection FTP snapshot tree, and `clinicaltrials_search`, ClinicalTrials.gov API v2, completing the seven-tool roster) closed 2026-08-08 on `phase/3.5-pathogen-clinicaltrials-tools`, merged as PR #27 (commit `28d333c`), after a judge round, an adversary round, and two fix rounds. Pre-build live probing found the phase's own headline constraint before any tool code existed: the Salmonella `SNP_distances.tsv` snapshot file measured roughly 411 GB, three orders of magnitude past a normal bulk TSV, ruling out a full download and forcing a wall-clock-bounded streamed scan instead (decision logged in DECISIONS.md). The judge round found one critical defect: the streaming transport's early-exit logic assumed a filter key is always unique per row, so a shared cluster id stopped the scan after its first matching row and reported an incomplete cluster as complete. That fix, and three related majors (an unbounded 120-second wait on an optional enrichment step, three of four network read sites reporting a routine snapshot rotation as an unclassified tool defect, stale module docstrings describing a mid-build dispatch accident as the shipped state) were fixed and lead-verified with a live premise gate pass, 8 of 8. An adversary round dispatched immediately after found that the fix itself had introduced two NEW critical regressions of the identical discard-real-data shape: `cluster_snp_neighbors` could no longer ever return a successful result at all (the fix's own early-exit removal, with no fallback, meant a cutoff scan always discarded what it had already found), and `clinicaltrials_search` pagination errored on every second page, since ClinicalTrials.gov omits its total-count field from every paginated response regardless of what the first fix assumed. Both were found live, coexisting with a green judge verdict and a passing premise gate, then fixed in two more rounds, the second only surfacing after a first live re-verification proved the initial fix incomplete (an upstream scan step was starving its own mandatory follow-up read of budget one call downstream). Every fix was re-verified against the adversary's own exact repro case, not just the mocked unit suite, which stayed green through every round including the two regressions. Two majors and five moderate or minor adversary findings were deliberately carried open rather than fixed this round, each with its own named reason in `tracker/phase_3.5.md`. Full account: `tracker/phase_3.5.md`, `LEARNINGS.md`'s 2026-08-08 rows. Build phase 3.4 (citation trust extended to Layers 2 and 3, the two-tier risk gate, data freshness and conflict resolution, T-3.1-28 folded in) closed 2026-08-10 on `phase/3.4-citation-trust-full`, merged as PR #28, the last of the six Step 6.3 tool-and-trust phases: extends Section 9.1/9.2 provenance to all six Layer 2/3 tools, fixes F-2.2-A-05 (the flagship gene-disease claim now classifies high risk via the traversed edge label, not the bare `Disease` node type), wires `act_node` to dispatch `ncbi_efetch` as a second answer-bearing tool alongside `cypher_query` (T-3.1-28, this repo's first dual-layer dispatch), and wires Sections 7.1/7.2/7.4 (live-wins-for-currency, conflict detection, staleness auto-cross-verify). Two judge rounds, a fix round, an adversary round (7 findings, 1 critical: a two-gene query silently dropped the second gene under a confident answer outcome, no citation, no disclosure), a fix round closing the critical and two majors, and a final judge round that independently live-verified that fix round rather than trusting its own report. Four items carried open, each with its own named reason: F-3.4-T06-01 (the staleness check is real and wired but has no field to fire against on this graph's current ingest, a System 1/2 gap), F-3.4-A-04, F-3.4-A-05, F-3.4-A-06. Full account: `tracker/phase_3.4.md`. With 3.0 through 3.5 all merged, Step 6.2 ran and closed the same day, 2026-08-10, across eight PRs (#29 through #36): the branch rename (`main` to `develop`), all four carried grounding findings, the premise-gate cadence folded into the tech spec, the two remaining process decisions, all fourteen spec-vs-reality gaps explicitly owned by Step 6.2, the new-intake sweep, and an informal manual smoke test of the seven v1 must-pass moat questions that surfaced one new finding, F-2.0-15 (`think_node`'s real query classification was never built past its build-phase-2.0 stub, causing 4 of 7 must-pass questions to refuse outright), assigned to build phase 4.7 as that phase's real deliverable, decided the same day. Step 6.2's security scan stays separately PAUSED INDEFINITELY on cost; exposure is the one condition that turns it back on, meaning a deploy, a public URL, or first contact with a user who is not the product owner. Build phase 4.0 (the REST plus SSE adapter finalized as the public API surface, Section 13.1) closed 2026-08-11 on `phase/4.0-rest-sse-hardening`, merged as PR #39 (commit `3166245`): closes F-1.2-01, F-1.2-02, and F-1.2-03 (bounded registry eviction, grace-period abandonment cancellation for an unwatched run, and multi-consumer resumable SSE via `Last-Event-ID`), adds `GET /v1/query/{run_id}/citations`, wires operator-scoped cost visibility (Section 19.4), and removes the legacy `POST /query` endpoint. Four judge rounds (round 1 FAIL with two blocking findings, round 2 PASS after a fix round, round 3 PASS confirming an adversary fix round with one new moderate finding filed, round 4 PASS confirming a CORS fix with one new tracker-tooling defect filed and fixed) and one adversary round against the live app under uvicorn (14 findings: 4 major, 5 moderate, 5 minor; 10 closed this round, including the abandonment-timer churn bypass F-4.0-A-01 and the missing cancellation terminal event F-4.0-A-04). Four findings carried open, each with a named owner: F-4.0-A-10 and F-4.0-A-11 (unbounded run creation and an O(n) eviction sweep, both owned by build phase 6.0, the rate-limiting phase that already names this scope), F-4.0-A-12 (the citations export drops the core's own truncation disclosure, needs a DonePayload contract change), and F-4.0-A-14 (an idle socket that never reads a byte still counts as someone watching, needs delivery-based liveness tracking). Full account: `tracker/phase_4.0.md`. Build phase 4.1 (the outbound-only MCP server wrapping the same tool functions, Section 13.2) closed 2026-08-11 on `phase/4.1-mcp-server`: adds `adapters/mcp/server.py`, exposing a single advertised tool, `ask_biomedical_question`, that folds the same `RunRegistry`/`run_streaming` core build phase 4.0 finalized behind `adapters/web_sse/` into one JSON result, never the seven internal tools directly and never a stream. Three judge rounds (round 1 FAIL, one blocking and three non-blocking gate-integrity findings against a shipped module every one independently re-confirmed as correct; round 2 PASS after a fix round closed all four; round 3 PASS, fresh-context, re-deriving both criticals and the two structural surface guarantees directly against the code rather than trusting either prior round's report) and one adversary round against the live mounted app (sixteen findings: two critical, four major, four moderate, six minor; twelve closed outright, one closed on its `grounded` half with the `risk_tier` half carried as F-4.1-J3-02, one closed with its underlying `core/graph.py` raw-exception-stringification pattern carried as F-4.1-J3-01, and two carried open as genuine product-level calls: F-4.1-A-10, whether relaying untrusted third-party source text to an autonomous agent consumer needs a provenance-labeling field the locked contract does not have, and F-4.1-A-15, a caller-supplied `session_id` unbound to its owner, latent until build phase 4.5 or 4.6 wires a consumer). Both criticals shared one shape: the fold loop asserted a positive trust verdict, a complete grounded low-risk answer, that the run's own events sometimes directly contradicted, fixed by flooring the top-level trust signal on any fatal or cancelled run and by aggregating claim-scoped signals worst-wins instead of discarding them. Full account: `tracker/phase_4.1.md`. Step 6.3 continues at build phase 4.2. 288 decisions logged (DECISIONS.md), 69 learnings plus a retrospective (LEARNINGS.md, restructured 2026-08-10 into short rows plus a detail section, PR #38), 2565 Python tests (2445 passing, 113 skipped, 1 xfailed, 6 failed on a known live-network-opt-in-gated set of tests, confirmed not a regression by diff) plus 120 frontend tests plus 3 Playwright end-to-end tests, plus seven live premise gates covering all seven tools: cypher_query at 9 of 9, the guardrail at 20 of 20, ncbi_efetch at 19 of 20 (1 tunnel-gated skip), ncbi_dbsnp at 8 of 8, the combined pubtator_annotate/litvar2_lookup gate at 12 of 12, pathogen_detection at 5 of 5, and clinicaltrials_search at 3 of 3, no tunnel-gated skip on any of the last four. Build phase 4.0's own premise gate (a normal test file, not one of the seven live tool gates above) is separately green at 26 tests, and build phase 4.1's own premise gate is separately green at 48 tests. These counts are checked by `python tracker/check_doc_drift.py --check`. Full per-phase detail, what shipped, judge and adversary findings, decisions, release gate outcomes: requirements/Plan.md's Revision history. Current phase status and open flags: tracker/BOARD.md. |
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

Last updated: 2026-08-11
