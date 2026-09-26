# UI facts inventory and freshness check

What System 3's web app states about itself, where each fact comes from, and whether it is true on develop `e43c769`. The check ran on a `git archive` export; the worktree base `0b75aa7` differs only in `DECISIONS.md` and the board.

The check is `/verify` Step 6: `.claude/skills/verify/scripts/check_facts.py` and `facts_registry.py`. Nothing in the app or in any document was changed.

The building agent returned this report as text, because its harness has sub-agents return findings rather than write report files. The lead saved it here unchanged.

## Table of contents

- [Summary](#summary)
- [Stale facts in plain words](#stale-facts-in-plain-words)
- [Checker run against develop](#checker-run-against-develop)
- [Inventory and downstream map, checked by the script](#inventory-and-downstream-map-checked-by-the-script)
- [Inventory read by hand](#inventory-read-by-hand)
- [The durable fix](#the-durable-fix)
- [Where the brief and the code disagreed](#where-the-brief-and-the-code-disagreed)
- [Noticed in passing](#noticed-in-passing)
- [What cost time](#what-cost-time)
- [Fix round](#fix-round)

## Summary

| Item | Value |
|------|-------|
| Develop commit | `e43c769` |
| Facts checked by the script | 64 |
| Stale facts | 15: 10 on a screen, 5 only in a document or a copy in code |
| Places | PASS 151, FAIL 28, GAP 0, ERROR 0 |
| Self-test | 179 comparisons proven to pass and to fail; 64 of 64 readers proven to follow a changed source; 9 parser cases; 0 failures |
| Read by hand | 37 rows |

Why the registry is Python: a fact's truth is rarely a plain lookup. For example:

- A count is the length of a `Literal`.
- "115M" is a rounding of 115,406,761.
- "Which steps ask a model" is a walk of the call graph.

The checker holds the engine: the readers, the comparisons, the call graph, the verdicts and the self-test. The registry holds the fact declarations and, beside them, the small functions that compute a particular fact's truth or parse what a particular place says. So an edit to the registry can change how that fact is decided. It gets the same review as an edit to the checker, and `--self-test` must pass after it. (Corrected in the fix round, PR118-06; the first version of this line said the registry only declared.)

## Stale facts in plain words

On a screen:

1. Onboarding tour, app bar step (`OnboardingTour.tsx:211`). Told: Integrations lists "the API, GraphQL, the command line and the export". True: the MCP server is the fourth way in, and it is left out.
2. Onboarding tour, seed step (`OnboardingTour.tsx:193`). Told: "These four are real questions from the evaluation set." True: only the BRCA1 and rs334 seeds have a golden counterpart. "Variants in GCK causing MODY" and "Trials recruiting for ALS" do not.
3. About, stop 2, Plan tier card (`InfoScreens.tsx:838`). Told: the plan-tier model "runs Plan, which picks the tools to call and writes the graph query itself". True: since 2026-09-14 Plan picks tools in code and asks one routing decision (Jev or the guard tier). The graph query is written in Act, from a template, or by the plan tier only when no template fits.
4. About, stop 2 (`InfoScreens.tsx:1170`). Told: "Four of the five steps ask a language model something." True: all five can. Act reaches the plan tier (Cypher fallback) and the guard tier (reader pass), and Plan asks its decision.
5. About, stop 5 (`InfoScreens.tsx:1303`). Told: each sentence is "checked in code", and an unsupported one is "dropped rather than reworded". True: since 2026-09-23 a reworded sentence that passes code's exact checks is judged by a model and can be kept.
6. About, layer 2 card (`InfoScreens.tsx:1114`), and Architecture, `ncbi_efetch` card (`architectureFacts.ts:124`). Told: layer 2 is "E-utilities, Datasets and dbSNP", and Architecture omits PubChem. True: layer 2 also calls PubChem and the Pathogen Detection FTP snapshot.
7. Architecture, stop 4 (`ArchitectureScreen.tsx:477`). Told: "The agent reads layer 1 first." True: Act reads all three layers at once (`_gather_planned_calls`).
8. Integrations, event stream card (`InfoScreens.tsx:729`). Told: "eleven kinds of event", with a list. True: twelve. `step` is missing.
9. Integrations, citations card (`InfoScreens.tsx:725`). Told: each claim carries "the tool that fetched it". True: `CitationPayload` has no tool field.
10. Integrations, command line card (`InfoScreens.tsx:660`). Told: `s3` prints "JSON with --json". True: `s3` has no `--json` option. This overlaps the Integrations audit.

Only in a document or a copy in code:

11. `CLAUDE.md:46`, `AGENTS.md:46` and `README.md:57` name LitSense, which no code calls. `CLAUDE.md:45`, `AGENTS.md:45` and `README.md:56` omit Datasets, PubChem and Pathogen Detection from layer 2.
12. `visualizations/Architecture_diagram.md:70` and `:83` say Act makes no model call.
13. `Architecture_diagram.md:82` and `:107`, `CLAUDE.md:53` and `AGENTS.md:53` put Plan on the plan tier.
14. `visualizations/System_3_deep_dive.md:467` says Plan makes no model call. It asks the literature decision.
15. `tools/catalogue.py:123` and `:138` say 30 s and 60 s. The code enforces 90 s and 120 s. The catalogue copies `.claude/rules/tool-call-budgets.md`, and no user sees it today.

## Checker run against develop

`check_facts.py --root <develop export> --reference <repo-root>/reference/agentic-search-data-engineering`, exit code 1, pasted unchanged:

```text
FAIL | layers.l2_apis | About | says "E-utilities, Datasets and dbSNP, called at the moment you ask. Narrower and slower, and always current." | true: Datasets, E-utilities, Pathogen Detection, PubChem, dbSNP; not named: Pathogen Detection, PubChem | frontend/src/components/screens/InfoScreens.tsx:1114 | src/system_03_search_agent/tools/ncbi_transport.py:361
FAIL | layers.l2_apis | Architecture | says "(reads as) Datasets, E-utilities, Pathogen Detection, dbSNP" | true: Datasets, E-utilities, Pathogen Detection, PubChem, dbSNP; not named: PubChem | frontend/src/lib/architectureFacts.ts:124 | src/system_03_search_agent/tools/ncbi_transport.py:361
FAIL | layers.l2_apis | document | says "Layer 2: NCBI APIs live (EFetch, ELink, dbSNP REST, called at query time)" | true: Datasets, E-utilities, Pathogen Detection, PubChem, dbSNP; not named: Datasets, Pathogen Detection, PubChem | CLAUDE.md:45 | src/system_03_search_agent/tools/ncbi_transport.py:361
FAIL | layers.l2_apis | document | says "Layer 2: NCBI APIs live (EFetch, ELink, dbSNP REST, called at query time)" | true: Datasets, E-utilities, Pathogen Detection, PubChem, dbSNP; not named: Datasets, Pathogen Detection, PubChem | AGENTS.md:45 | src/system_03_search_agent/tools/ncbi_transport.py:361
FAIL | layers.l2_apis | document | says "/ Layer 2: on-demand NCBI APIs / 30+ databases reached at query time via EFetch, ELink, dbSNP REST /" | true: Datasets, E-utilities, Pathogen Detection, PubChem, dbSNP; not named: Datasets, Pathogen Detection, PubChem | README.md:56 | src/system_03_search_agent/tools/ncbi_transport.py:361
FAIL | layers.l3_apis | document | says "Layer 3: Enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov)" | true: ClinicalTrials.gov, LitVar2, PubTator3; named but not so: LitSense (no code calls it) | CLAUDE.md:46 | src/system_03_search_agent/tools/ncbi_transport.py:361
FAIL | layers.l3_apis | document | says "Layer 3: Enrichment APIs (PubTator3, LitVar2, LitSense, ClinicalTrials.gov)" | true: ClinicalTrials.gov, LitVar2, PubTator3; named but not so: LitSense (no code calls it) | AGENTS.md:46 | src/system_03_search_agent/tools/ncbi_transport.py:361
FAIL | layers.l3_apis | document | says "/ Layer 3: enrichment APIs / PubTator3, LitVar2, LitSense, ClinicalTrials.gov /" | true: ClinicalTrials.gov, LitVar2, PubTator3; named but not so: LitSense (no code calls it) | README.md:57 | src/system_03_search_agent/tools/ncbi_transport.py:361
FAIL | budget.graph_query_s | code copy | says "_CYPHER_QUERY_BUDGET = (30.0" | true: 90 | src/system_03_search_agent/tools/catalogue.py:123 | src/system_03_search_agent/tools/graph_schema_constants.py:196
FAIL | budget.pathogen_s | code copy | says "_PATHOGEN_DETECTION_BUDGET = ( 60.0" | true: 120 | src/system_03_search_agent/tools/catalogue.py:138 | src/system_03_search_agent/tools/pathogen_detection.py:284
FAIL | events.types | Integrations | says "A run emits eleven kinds of event" | true: 12: guard, think, plan, tool_start, tool_result, token, citation, trust_signal, cost, error, done, step | frontend/src/components/screens/InfoScreens.tsx:729 | src/system_03_search_agent/contracts/events.py:672
FAIL | events.types | Integrations | says "guard, think, plan, tool_start, tool_result, token, citation, trust_signal, cost, error and done" | true: citation, cost, done, error, guard, plan, step, think, token, tool_result, tool_start, trust_signal; not named: step | frontend/src/components/screens/InfoScreens.tsx:729 | src/system_03_search_agent/contracts/events.py:672
FAIL | citations.fields | Integrations | says "with the layer that produced it, the tool that fetched it, its evidence type, its confidence and its licence" | true: assertion_confidence, citation_id, claim_text, display_index, entity_name, evidence_kind, field, layer, license, population_ancestry_context, snapshot_date, source, source_id, source_url; named but not so: tool | frontend/src/components/screens/InfoScreens.tsx:725 | src/system_03_search_agent/contracts/events.py:383
FAIL | surfaces.named | Onboarding tour | says "Integrations lists the other ways in: the API, GraphQL, the command line and the export." | true: GraphQL, MCP, REST, command line; not named: MCP | frontend/src/components/tour/OnboardingTour.tsx:211 | src/system_03_search_agent/contracts/query.py:292
FAIL | surfaces.s3_options | Integrations | says "JSON with --json" | true: exists: --base-url, --depth, --session-id | frontend/src/components/screens/InfoScreens.tsx:660 | src/system_03_search_agent/adapters/cli/main.py:1
FAIL | loop.steps_asking_a_model | About | says "Four of the five steps ask a language model" | true: 5: guardrail, think, plan, act, write | frontend/src/components/screens/InfoScreens.tsx:1170 | src/system_03_search_agent/core/graph.py:12617
FAIL | loop.steps_asking_a_model | document | says "Four of them make exactly one model call each" | true: 5: guardrail, think, plan, act, write | visualizations/Architecture_diagram.md:70 | src/system_03_search_agent/core/graph.py:12617
FAIL | loop.plan_on_plan_tier | About | says "Then runs Plan, which picks the tools to call and writes the graph query itself" | true: no (the plan step reaches: classifier, guard) | frontend/src/components/screens/InfoScreens.tsx:838 | src/system_03_search_agent/core/graph.py:12619
FAIL | loop.plan_on_plan_tier | document | says "- Plan: Plan tier, one call" | true: no (the plan step reaches: classifier, guard) | visualizations/Architecture_diagram.md:107 | src/system_03_search_agent/core/graph.py:12619
FAIL | loop.plan_on_plan_tier | document | says "PL["Plan, Plan tier"]" | true: no (the plan step reaches: classifier, guard) | visualizations/Architecture_diagram.md:82 | src/system_03_search_agent/core/graph.py:12619
FAIL | loop.plan_on_plan_tier | document | says "Plan tier: mid-range model for query decomposition and tool selection" | true: no (the plan step reaches: classifier, guard) | CLAUDE.md:53 | src/system_03_search_agent/core/graph.py:12619
FAIL | loop.plan_on_plan_tier | document | says "Plan tier: mid-range model for query decomposition and tool selection" | true: no (the plan step reaches: classifier, guard) | AGENTS.md:53 | src/system_03_search_agent/core/graph.py:12619
FAIL | loop.layer_one_read_first | Architecture | says "The agent reads layer 1 first" | true: no (Act runs every planned call at once with asyncio.gather) | frontend/src/components/screens/ArchitectureScreen.tsx:477 | src/system_03_search_agent/core/graph.py:7547
FAIL | loop.act_asks_no_model | document | says "Act makes no model call at all" | true: no (the act step reaches: guard, plan) | visualizations/Architecture_diagram.md:70 | src/system_03_search_agent/core/graph.py:12620
FAIL | loop.act_asks_no_model | document | says "AC["Act, no model call"]" | true: no (the act step reaches: guard, plan) | visualizations/Architecture_diagram.md:83 | src/system_03_search_agent/core/graph.py:12620
FAIL | loop.plan_asks_no_model | document | says "Note over L: Plan, no model call" | true: no (the plan step reaches: classifier, guard) | visualizations/System_3_deep_dive.md:467 | src/system_03_search_agent/core/graph.py:12619
FAIL | loop.sentences_checked_by_code_alone | About | says "Each sentence is then checked in code against the record it points at" | true: no (_ground_with_sentence_check reaches: guard) | frontend/src/components/screens/InfoScreens.tsx:1303 | src/system_03_search_agent/core/graph.py:8656
FAIL | seeds.from_golden_set | Onboarding tour | says "These four are real questions from the evaluation set" | true: 2: Diseases linked to BRCA1, Clinical significance of rs334 (4 seeds; no golden question for: Variants in GCK causing MODY, Trials recruiting for ALS) | frontend/src/components/tour/OnboardingTour.tsx:193 | eval/golden/golden_dataset.json:1
facts: 64 checked, 15 stale | places: PASS 151, FAIL 28, GAP 0, ERROR 0
```

## Inventory and downstream map, checked by the script

One row per fact. "Restated in" is the downstream map: change the source and every listed place needs a look. `check_facts.py --map --from <file>` prints the same thing for one changed file.

Paths are shortened:

- screens are under `frontend/src/components/`
- `lib/` is `frontend/src/lib/`
- backend paths are under `src/system_03_search_agent/`
- `ref` is `reference/agentic-search-data-engineering/`

| Fact | What the app says it is | Stated on | Source | Restated in | On develop |
|------|-------------------------|-----------|--------|-------------|------------|
| `graph.nodes` | how many nodes the knowledge graph holds | Architecture and About lib/architectureFacts.ts:38; Integrations InfoScreens.tsx:499; About InfoScreens.tsx:853, 1109; Home HomeScreen.tsx:493 | `ref docs/Knowledge_graph_on_server_reference.md:28` | CLAUDE.md:49; AGENTS.md:49; README.md:3; Schema_visualization.md:16 | TRUE |
| `graph.edges` | how many edges the knowledge graph holds | Architecture and About lib/architectureFacts.ts:39; Integrations InfoScreens.tsx:499; About InfoScreens.tsx:853, 1109; Home HomeScreen.tsx:493 | `ref docs/Knowledge_graph_on_server_reference.md:28` | CLAUDE.md:49; AGENTS.md:49; Schema_visualization.md:16 | TRUE |
| `graph.vertex_labels` | how many vertex labels the graph has | Architecture lib/architectureFacts.ts:40 | `ref docs/Knowledge_graph_on_server_reference.md:28` | Schema_visualization.md:16 | TRUE |
| `graph.edge_labels` | how many edge labels the graph has | Architecture lib/architectureFacts.ts:41 | `ref docs/Knowledge_graph_on_server_reference.md:28` | Schema_visualization.md:16 | TRUE |
| `graph.database_nodes` | how many nodes each of the five source databases contributes | Architecture lib/architectureFacts.ts:66 | `ref docs/Knowledge_graph_on_server_reference.md:68` | none | TRUE |
| `graph.databases` | which NCBI databases the graph is built from | Architecture and About lib/architectureFacts.ts:66 | `ref docs/Knowledge_graph_on_server_reference.md:28` | README.md:55 | TRUE |
| `graph.database_count` | how many NCBI databases the graph is built from | About InfoScreens.tsx:853, 1109, 1441; Architecture ArchitectureScreen.tsx:256, 326 | `ref docs/Knowledge_graph_on_server_reference.md:28` | CLAUDE.md:49; AGENTS.md:49; README.md:55 | TRUE |
| `graph.minor_label_nodes` | how many nodes sit outside the five main labels | Architecture ArchitectureScreen.tsx:380 | `ref docs/Knowledge_graph_on_server_reference.md:68` | none | TRUE |
| `graph.minor_label_count` | how many smaller labels hold those nodes | Architecture ArchitectureScreen.tsx:380 | `ref docs/Knowledge_graph_on_server_reference.md:68` | none | TRUE |
| `graph.gene_rows` | how many Gene nodes an unindexed lookup would scan | Architecture ArchitectureScreen.tsx:435 | `ref docs/Knowledge_graph_on_server_reference.md:68` | none | TRUE |
| `graph.snapshot_date` | the date the loaded graph snapshot was finished | Architecture and About lib/architectureFacts.ts:27; Architecture ArchitectureScreen.tsx:454 | `tools/cypher_query.py:258` | none | TRUE |
| `graph.name` | the name of the graph the agent queries | Architecture ArchitectureScreen.tsx:387; lib/architectureFacts.ts:138 | `tools/graph_schema_constants.py:41` | Schema_visualization.md:16 | TRUE |
| `graph.postgres_version` | the PostgreSQL major version the graph runs on | Architecture ArchitectureScreen.tsx:388 | `ref docs/Knowledge_graph_on_server_reference.md:39` | none | TRUE |
| `graph.edge_label_speedup` | how long the first BRCA1 query took without and with its edge label | Architecture ArchitectureScreen.tsx:437 | `ref docs/Knowledge_graph_on_server_reference.md:158` | none | TRUE |
| `graph.pipeline_steps` | the five steps every data pipeline runs | Architecture lib/architectureFacts.ts:92 | `ref CLAUDE.md:102` | none | TRUE |
| `graph.biolink_version` | the BioLink model version the pipelines map to | Architecture ArchitectureScreen.tsx:257 | `ref CLAUDE.md:7` | none | TRUE |
| `tools.count` | how many tools the agent has | Integrations InfoScreens.tsx:499, 645; About InfoScreens.tsx:1199; Architecture ArchitectureScreen.tsx:479 | `contracts/events.py:33` | CLAUDE.md:32; AGENTS.md:32; Architecture_diagram.md:121; Schema_visualization.md:3, 168; README.md:260 | TRUE |
| `tools.names` | the names of the agent's tools | code copy lib/events.ts:36 | `contracts/events.py:33` | CLAUDE.md:32; AGENTS.md:32 | TRUE |
| `tools.layers` | which tools read which data layer | About InfoScreens.tsx:848; Architecture lib/architectureFacts.ts:124 | `contracts/events.py:33` | Architecture_diagram.md:164 | TRUE |
| `layers.count` | how many data layers there are | Integrations InfoScreens.tsx:499; About InfoScreens.tsx:1128; Architecture ArchitectureScreen.tsx:246 | `contracts/events.py:43` | CLAUDE.md:43; AGENTS.md:43; Schema_visualization.md:169 | TRUE |
| `layers.l2_tools` | how many tools reach the live NCBI APIs | Architecture ArchitectureScreen.tsx:456 | `contracts/events.py:33` | none | TRUE |
| `layers.l3_tools` | how many tools add enrichment | Architecture ArchitectureScreen.tsx:465 | `contracts/events.py:33` | none | TRUE |
| `layers.l2_apis` | which live NCBI APIs layer 2 calls | About InfoScreens.tsx:1114; Architecture lib/architectureFacts.ts:124 | `tools/ncbi_transport.py:361` | CLAUDE.md:45; AGENTS.md:45; README.md:56 | STALE at all five |
| `layers.l3_apis` | which enrichment APIs layer 3 calls | About InfoScreens.tsx:1120; Architecture lib/architectureFacts.ts:124 | `tools/ncbi_transport.py:361` | CLAUDE.md:46; AGENTS.md:46; README.md:57 | STALE in the three documents |
| `budget.graph_query_s` | how long one graph query may take, in seconds | Architecture lib/architectureFacts.ts:139; ArchitectureScreen.tsx:442; About InfoScreens.tsx:1208 | `tools/graph_schema_constants.py:196` | Architecture_diagram.md:130, 164; System_3_deep_dive.md:358; tools/catalogue.py:123 | STALE at tools/catalogue.py:123 |
| `budget.row_limit` | the most rows one graph query may return | Architecture lib/architectureFacts.ts:139; ArchitectureScreen.tsx:442 | `tools/graph_schema_constants.py:167` | Architecture_diagram.md:164 | TRUE |
| `budget.live_call_s` | how long one live NCBI or enrichment call may take, in seconds | About InfoScreens.tsx:1208; Architecture lib/architectureFacts.ts:150, 155, 172, 173, 174 | `tools/ncbi_transport.py:308` | Architecture_diagram.md:134-142, 165-170; System_3_deep_dive.md:359; tools/catalogue.py:124, 128, 136, 137, 142 | TRUE |
| `budget.pathogen_s` | how long one Pathogen Detection call may take, in seconds | Architecture lib/architectureFacts.ts:160 | `tools/pathogen_detection.py:284` | Architecture_diagram.md:136, 167; System_3_deep_dive.md:360; tools/catalogue.py:138 | STALE at tools/catalogue.py:138 |
| `budget.live_calls_per_question` | how many live layer 2 and 3 calls one question may make | About InfoScreens.tsx:1209; Integrations InfoScreens.tsx:740 | `harness/call_budget.py:101` | Architecture_diagram.md:116; System_3_deep_dive.md:337 | TRUE |
| `events.types` | the kinds of event a run emits | Integrations InfoScreens.tsx:729 (count and list) | `contracts/events.py:672` | Schema_visualization.md:143 | STALE on the screen |
| `events.guard_fields` | the fields of a guard event's payload | Integrations InfoScreens.tsx:174 | `contracts/events.py:185` | none | TRUE |
| `events.guard_categories` | the reasons a question can be turned away | Refusal banner chat/GuardrailBanner.tsx:25; code copy lib/events.ts:55 | `contracts/events.py:189` | none | TRUE |
| `citations.fields` | what every citation carries | Integrations InfoScreens.tsx:725 | `contracts/events.py:383` | none | STALE |
| `query.max_chars` | how long a question may be, in characters | Onboarding tour OnboardingTour.tsx:174; Home HomeScreen.tsx:133 | `contracts/query.py:220` | none | TRUE |
| `modes.accepted` | the answer modes the web app sends are ones the server accepts | code copy controls/DepthControl.tsx:35 | `contracts/query.py:250` | none | TRUE |
| `modes.default` | the answer mode a question uses unless changed | About InfoScreens.tsx:1146; Onboarding tour OnboardingTour.tsx:184 | `controls/DepthControl.tsx:32` | none | TRUE |
| `modes.labels` | the answer modes a person can pick | About InfoScreens.tsx:1146; Onboarding tour OnboardingTour.tsx:184 | `controls/DepthControl.tsx:32` | none | TRUE |
| `surfaces.count` | how many ways a program can reach the agent | Integrations InfoScreens.tsx:565 | `contracts/query.py:292` | none | TRUE |
| `surfaces.named` | which ways a program can reach the agent | Onboarding tour OnboardingTour.tsx:211; Integrations InfoScreens.tsx:597 | `contracts/query.py:292` | none | STALE in the tour |
| `surfaces.mcp_tools` | the tools the MCP server advertises | Integrations InfoScreens.tsx:645 | `adapters/mcp/server.py:1` | none | TRUE |
| `surfaces.console_commands` | the console commands the package installs | Integrations InfoScreens.tsx:660 | `pyproject.toml:72` | none | TRUE |
| `surfaces.s3_options` | the options the s3 command accepts | Integrations InfoScreens.tsx:660 | `adapters/cli/main.py:1` | none | STALE |
| `surfaces.kgx_options` | the options the s3-kgx-export command accepts | Integrations InfoScreens.tsx:165 | `export/cli.py:1` | none | TRUE |
| `access.login_route` | the route that exchanges an email and password for a token | Integrations InfoScreens.tsx:721 | `auth/router.py:1` | none | TRUE |
| `access.graphql_refuses_guests` | a guest cannot use GraphQL | Integrations InfoScreens.tsx:695 | `adapters/graphql/context.py:123` | none | TRUE |
| `access.mcp_refuses_guests` | a guest cannot use the MCP server | Integrations InfoScreens.tsx:695 | `adapters/mcp/server.py:592` | none | TRUE |
| `access.rest_admits_guests` | a guest can ask questions over REST | Integrations InfoScreens.tsx:696 | `adapters/web_sse/app.py:1194` | none | TRUE |
| `access.history_kept` | a signed-in person's questions are kept across reloads | Onboarding tour OnboardingTour.tsx:212; About InfoScreens.tsx:1322 | `adapters/web_sse/app.py:1003` | none | TRUE |
| `access.api_reference` | the API serves /docs and /openapi.json | Integrations InfoScreens.tsx:612, 617 | `adapters/web_sse/app.py:251` | none | TRUE |
| `access.stream_resumes` | a dropped event stream can be resumed | Integrations InfoScreens.tsx:600 | `adapters/web_sse/app.py:1619` | none | TRUE |
| `loop.steps` | the steps every question goes through | Run screen RunProgress.tsx:184; Onboarding tour OnboardingTour.tsx:221; About InfoScreens.tsx:1170 | `core/graph.py:12617` | CLAUDE.md:41; AGENTS.md:41 | TRUE |
| `loop.steps_asking_a_model` | how many of the steps ask a language model something | About InfoScreens.tsx:1170 | `core/graph.py:12617` | Architecture_diagram.md:70 | STALE at both |
| `loop.tier_count` | how many model tiers the harness has | About InfoScreens.tsx:1171 | `harness/tiers.py:37` | CLAUDE.md:51; AGENTS.md:51 | TRUE |
| `loop.guardrail_on_guard_tier` | the guardrail step asks the guard-tier model | About InfoScreens.tsx:831 | `core/graph.py:12617` | none | TRUE |
| `loop.think_on_plan_tier` | the think step asks the plan-tier model | About InfoScreens.tsx:836 | `core/graph.py:12618` | none | TRUE |
| `loop.plan_on_plan_tier` | the plan step asks the plan-tier model to pick tools and write the query | About InfoScreens.tsx:838 | `core/graph.py:12619` | Architecture_diagram.md:82, 107; CLAUDE.md:53; AGENTS.md:53 | STALE at all five |
| `loop.write_on_synth_tier` | the write step asks the synth-tier model | About InfoScreens.tsx:841 | `core/graph.py:12621` | none | TRUE |
| `loop.layer_one_read_first` | the agent reads the graph before it calls the live layers | Architecture ArchitectureScreen.tsx:477 | `core/graph.py:7547` | none | STALE |
| `loop.act_asks_no_model` | the act step makes no model call | documents only | `core/graph.py:12620` | Architecture_diagram.md:70, 83 | STALE at both |
| `loop.plan_asks_no_model` | the plan step makes no model call | documents only | `core/graph.py:12619` | System_3_deep_dive.md:467 | STALE |
| `loop.sentences_checked_by_code_alone` | each answer sentence is checked against its record by code alone | About InfoScreens.tsx:1303 | `core/graph.py:8656` | none | STALE |
| `models.code_defaults` | the model each tier uses when the deployment names none | documents only | `harness/tiers.py:53` | System_3_deep_dive.md:176; docs/architecture/Model_architecture.md:50 | TRUE |
| `personas.historical` | each session's scientist is a historical figure | Onboarding tour OnboardingTour.tsx:202 | `data/personas_v1.json:1` | none | TRUE |
| `seeds.from_golden_set` | the Home screen's seed questions come from the evaluation set | Onboarding tour OnboardingTour.tsx:193 | `eval/golden/golden_dataset.json:1` | none | STALE |

## Inventory read by hand

These are not in the script, because they are qualitative, served at run time, or owned by the Integrations audit. Screens are under `frontend/src/components/`.

| Screen | What it says | Where | Source | On develop |
|--------|--------------|-------|--------|------------|
| About | The question is carried as data, not an instruction | screens/InfoScreens.tsx:1148 | synthesis/findings.py, "data, not an instruction to you" | TRUE |
| About | A tier's model is read once and held for the question | InfoScreens.tsx:1172 | harness/tiers.py:170 | TRUE |
| About | A call over its limit fails fast and names the limit | InfoScreens.tsx:1210 | harness/call_budget.py, tools/ncbi_transport.py | TRUE |
| About | Results are typed and bounded, and a cut is recorded | InfoScreens.tsx:1288 | tools/*_schemas.py, harness/coordinator_worker.py | TRUE |
| About | With nothing citeable it says so and stops | InfoScreens.tsx:1306 | synthesis/refuse.py | TRUE |
| About | The scientist's name is presentation only | InfoScreens.tsx:1335 | core/persona.py, shell/PersonaChip.tsx | TRUE |
| About | Layers 2 and 3 are stored nowhere | InfoScreens.tsx:1443 | only EInfo field names are cached, tools/ncbi_eutils_actions.py:246 | TRUE |
| Architecture | Five databases are downloaded in full over FTP | screens/ArchitectureScreen.tsx:256 | ref CLAUDE.md pipeline step 1 | TRUE |
| Architecture | Five sample identifiers | lib/architectureFacts.ts:66 | the cited Section F carries four; PMID:1088347 is only in the reference repository's Schema_visualization.md | TRUE, one attributed to the wrong section |
| Architecture | Read-only credential; nothing else writes to the graph | ArchitectureScreen.tsx:389 | tools/__init__.py (`kg_reader`), reference Section A | TRUE |
| Architecture | Node ids and both edge ends are indexed | ArchitectureScreen.tsx:434 | ref CLAUDE.md index passes | TRUE |
| Architecture | Each tool reaches one layer "and one access path within it" | ArchitectureScreen.tsx:480 | `ncbi_efetch` calls E-utilities, Datasets and PubChem; `ncbi_dbsnp` calls Variation Services and E-utilities | PARTLY STALE |
| Architecture | ClinicalTrials.gov is the one non-NCBI host | ArchitectureScreen.tsx:468 | tools/clinicaltrials_search.py:157 | TRUE |
| Architecture | A graph row's link is the URL stored on the node | ArchitectureScreen.tsx:486 | tools/cypher_provenance.py:444 keeps a stored NCBI URL, else builds one | MOSTLY TRUE |
| Architecture | Layer 1 is read over an authenticated HTTPS service | lib/architectureFacts.ts:134 | tools/graph_http_transport.py | TRUE |
| Integrations | GraphQL returns a run whole, with no stream | InfoScreens.tsx:625 | adapters/graphql/fold.py | TRUE |
| Integrations | The KGX export writes nodes.tsv, edges.tsv and a manifest | InfoScreens.tsx:660 | export/cli.py:156 | TRUE |
| Integrations | Log in issues the bearer token every surface takes | InfoScreens.tsx:694 | auth/router.py POST /auth/login | TRUE |
| Integrations | Per-tool timeout and pool; fails fast with a retry hint | InfoScreens.tsx:740 | tools/ncbi_transport.py, harness/call_budget.py | TRUE |
| Integrations | A refusal is a normal outcome with a reason | InfoScreens.tsx:729 | contracts/events.py GuardPayload.reason | TRUE |
| Integrations | Six printed snippets: REST :124, GraphQL :132, MCP config :154, CLI :162, KGX :165, event frame :172 | InfoScreens.tsx | adapters/web_sse/app.py, adapters/graphql/, adapters/cli/main.py, export/cli.py, contracts/events.py | NOT RUN (Integrations audit); names, flags and payload fields partly checked by the script |
| Home | Answered from the NCBI graph and live NCBI APIs | screens/HomeScreen.tsx:268 | layer 3 includes ClinicalTrials.gov | TRUE, omits the one non-NCBI source |
| Home | Live APIs per question; literature and trials on top | HomeScreen.tsx:494 | the layers | TRUE |
| Home | The four seed questions | HomeScreen.tsx:33 | golden set | checked through the tour's claim |
| Tour | Built from the NCBI graph and live NCBI APIs | tour/OnboardingTour.tsx:164 | same caveat | TRUE |
| Tour | The layer colours mean "graph, live API, or literature" | OnboardingTour.tsx:229 | layer 3 also carries trials | IMPRECISE |
| Guest | "N of M searches left today" | lib/guestSession.ts:156 | GET /v1/allowance, adapters/web_sse/app.py:669 | served, cannot go stale |
| Guest | "Guest searches are paused for today" and the network line | App.tsx:161 | server reason codes | TRUE, served |
| Guest | Five-dot "N searches left" | guest/GuestAllowance.tsx:130 | FREE_RUN_ALLOWANCE = 5, data/guest_sessions.py:60 | not on any screen: nothing renders the component |
| Refusal banner | "Try again after (reset time)." | chat/GuardrailBanner.tsx:32 | no reset time field, and no emitter of `rate_limited` found | literal placeholder, likely never shown |
| Disclaimer | Cited evidence for research, not medical advice | shell/DisclaimerModal.tsx:176 | product stance | TRUE |
| Disclaimer | Refuses rather than guesses | DisclaimerModal.tsx:185 | cite or refuse | TRUE |
| Disclaimer | A prototype under active development | DisclaimerModal.tsx:202 | status | TRUE |
| Account menu | "Signed in · N of M searches left today" | shell/AccountMenu.tsx:221 | GET /v1/allowance | served |
| Persona chip | Name, about line and Wikipedia link | shell/PersonaChip.tsx | persona endpoint over data/personas_v1.json | served |
| Answer modes | Both modes cite every claim; a change applies next time | controls/DepthControl.tsx:76 | App reads the mode when a question is asked | TRUE |
| Models | No screen names a model | About names tier kinds only | harness/tiers.py | the docs' code defaults are checked; develop's overrides live in the deployment's variables, a GAP by design |

## The durable fix

A fact that the backend or the deployment decides should come from the API and be drawn by the page, so it cannot go stale. A fact that is history, or a deliberate product statement, is fine as a constant the checker watches.

Serve from a read-only `GET /v1/about`, which carries no secrets and can be cached:

- The graph snapshot version and date. The deployment's `GRAPH_SNAPSHOT_VERSION` can differ from the code default, and only the API knows which it queries.
- Node and edge counts, total and per database, from a counts manifest shipped with each snapshot load. Not a live count per request.
- The tool roster with each tool's layer and time limit, built from `ToolName`, each tool's declared layer and the budget constants.
- The live API families per layer, from `ncbi_transport._LAYER_BY_FAMILY` plus the Pathogen FTP transport. PubChem is the drift this would have prevented.
- The event types and guard categories, from `contracts/events.py`.
- The question length limit, the answer modes and the call ceiling, from `contracts/query.py` and `harness/call_budget.py`.
- The commit the deployment was built from, added to `/health` as well, which closes the `/verify` gap. The platform exposes the commit as a deploy variable; confirm its name before relying on it.

Keep as constants the checker watches:

- How the loop behaves: which step asks which model, all layers read at once, the sentence check. Serving these as data means little. Either reword them into statements that do not churn (for example "each step may ask a model; the harness picks the tier"), or keep them under the call-graph checks.
- History and reference figures: the pipeline steps, BioLink 4.x, PostgreSQL 15, 4 minutes 17 seconds against 229 milliseconds, 67 million rows, about 78,000.
- Access rules, such as GraphQL and MCP needing an account. These are product decisions, and they are checked.
- The seed questions' provenance. Reword it ("four example questions"), or draw the seeds from the golden set.

Already served, needing nothing: the search limit, the daily cap reasons and the persona.

Also worth doing:

- Run `check_facts.py --self-test` in CI next to `tests/ci/test_verify_capture.py`.
- Add the full check as a non-blocking CI report until the 15 stale facts are fixed.

## Where the brief and the code disagreed

- The guest allowance is `FREE_RUN_ALLOWANCE` in `data/guest_sessions.py`, not `auth/guest.py`. No screen shows it now: `GuestAllowance.tsx` is rendered nowhere since set 1.
- `data/personas_v1.json` holds the 32 scientists, not depth names. Depth names come from `Query.audience_depth` in `contracts/query.py`, and the web app offers two of them through `DepthControl.tsx`.
- F-8.6-P12 is the tree-of-life layout finding at 390 pixels. The evidence that `/health` carries no commit is `health.json` in the same review folder, `{"status":"ok","app_env":"develop"}`.
- The worktree's `reference/` symlink is relative and does not resolve in an agent worktree. The checker falls back to the main checkout's copy through the git common directory, or takes `--reference`.
- Develop moved from `0b75aa7` to `e43c769` during the work, with documentation changes only. The run above is against `e43c769`.
- The `health.json` in the bullet above exists only on the unmerged `phase/8.6-followup` (`111028e3`); develop has only 8.1's copy (PR118-09). The skill no longer cites it: it cites `HealthResponse` in `adapters/web_sse/app.py`, which carries `status` and `app_env` only.

The review of pull request 118 left five notes that stay notes, fixed where the fix was one line:

- PR118-09: the evidence not on develop, above. Fixed in the skill, one line.
- PR118-12: a pattern that names a number word, such as "(Seven)", "(One)" or "(Four)", turns a correct edit of the page into an ERROR instead of a PASS. The ERROR still fails `/verify` and names the registry, so nothing passes wrongly, but it costs a registry edit. Left: loosening each such pattern to any word is a registry change, not one line. `NUMBER_WORDS` now reaches nineteen, plus thirty, forty and fifty, in one line.
- PR118-14: the registry sits under `.claude/`, so a copy card that adds a fact becomes a branch-and-pull-request change under the git-workflow rule's `.claude/` row. Left: where the registry lives is the owner's call.
- PR118-17: a backend-only run of Step 6. The verdict line and the exit checklist now cover it. Left: the flowchart still has no facts node.
- PR118-18: the docstring said nothing runs, but the script starts `git rev-parse`. Fixed in the docstring, one line: no code under check runs, and `git rev-parse` is the one process started.

## Noticed in passing

- The graph owner's reference, Section D, puts NamedThing at "~81K". That is more than the 77,842 the stated total leaves after the five exact labels. The reference is read-only here, so worth telling its owner.
- `tools/catalogue.py` copies the tool-call-budgets rule's 30 s and 60 s rather than the code's values. The rule itself still says 30 and 60, and the deep dive already records the difference.

## What cost time

Nothing failed for more than five minutes. The self-test caught three weak checks, each fixed in minutes:

- A text mutation that left "4.x" unchanged.
- A pattern that matched a type alias before the default it targeted.
- A REST guest marker that matched any route.

## Fix round

The one fix round for pull request 118, on `chore/verify-facts` after `f75d6df`. Commits: `7b42026` (engine), `f210aa9` and `6b63663` (registry), `98e3241` (skill), and this report. Each probe ran the checker from before the round and the checker after it, against a `git archive` export of develop with the reference present unless stated.

| Finding | Result | Probe, before then after |
|---------|--------|--------------------------|
| PR118-01 | Fixed | `--from` the graph reference with no reference repository: exit 0, "places: PASS 0, FAIL 0, GAP 33, ERROR 0"; now exit 3, "not fully checked 12 ... GAP 33 ... NOT PASSED". The skill lists exit 0 PASS, 1 FAIL, 2 ERROR, 3 GAP, and any non-zero fails `/verify` |
| PR118-02 | Fixed | A tool renamed in `ToolName` only: exit 2, "14 stale ... PASS 141, FAIL 23, GAP 0, ERROR 5", with the layer 2 and 3 API facts hidden behind ERROR; now exit 2, "stale 16 ... not fully checked 3 ... PASS 143, FAIL 31, GAP 0, ERROR 5", with their FAIL lines kept and one ERROR line per unjudged place. ERROR is a verdict word in the skill and fails `/verify` |
| PR118-03 | Fixed | The citation sentence rewritten to "with the reviewer who approved it, its DOI and the abstract it was quoted from": PASS, exit 0; now ERROR, exit 2. "its licence" changed to "its DOI": FAIL on the tool only; now ERROR naming 'its DOI'. An empty reading is an ERROR everywhere, never compared |
| PR118-04 | Fixed | Seeds "Songs about BRCA1", "Movies about rs334" and two more: PASS, exit 0; now FAIL, exit 1. The fact now asks for the seed's words, in order, inside a golden question, and says so in its description. On develop the seeds read 0 of 4 word for word, where the first version counted 2 of 4 by identifier; the note names the golden question sharing each seed's identifiers as a lead only |
| PR118-05 | Fixed | `MAX_LAYER_2_3_CALLS_PER_QUERY` made `int(os.environ.get(...))`: a `ValueError` traceback and no summary; now four ERROR lines, "... is not a literal, so it cannot be read without running the code (ValueError) ...", and the run goes on to "facts: 64 / stale 15 / not fully checked 1 / places: PASS 147, FAIL 28, GAP 0, ERROR 4 / NOT PASSED", exit 2. Messages are scrubbed of local paths |
| PR118-06 | Fixed | Both docstrings and this report's line now say the registry holds per-fact functions, so a registry edit can change a verdict |
| PR118-07 | Fixed | The after-merge step reruns the check on a `git archive` export of the merged develop commit. The API deploy is read as `/ship` reads it; the web deploy, which `/ship` does not read, is read the same way or named as a GAP |
| PR118-08 | Fixed | The placeholder points at `testing/Developer/reports/2026-09-26_integrations_audit/integrations_smoke.py` on develop, and says phase 8.10 makes it pass before the lead wires it in. Not wired in |
| PR118-09 | Fixed, one line | See the notes above |
| PR118-10 | Fixed | `--reference /nonexistent/typo`: exit 1 with a full run on the fallback reference; now exit 2, "check_facts: --reference names no directory; nothing was checked" |
| PR118-11 | Fixed | Self-test with no reference: exit 0, "179 comparisons proven ... 50 of 64 readers ... 0 failures"; now exit 1, "179 of 179 comparisons ... 50 of 64 readers ... 14 failures", one per unproven reader. The comparison count now counts only comparisons that passed both arms |
| PR118-12 | Left in part | See the notes above |
| PR118-13 | Fixed | `--map --from README_nope.md`: exit 2; now exit 0, "check_facts: no fact is computed from README_nope.md, so nothing restates it" |
| PR118-14 | Left | See the notes above |
| PR118-15 | Fixed | New place: `frontend/src/lib/events.ts` `KNOWN_EVENT_TYPES`, with `cost` counted as the omission its docstring declares. It fails: "not named: step". Places on develop go from 28 FAIL to 29 FAIL; stale facts stay 15, since `events.types` was already stale |
| PR118-16 | Fixed | `/usr/bin/python3`, which is 3.9: exit 1, "ModuleNotFoundError: No module named 'tomllib'"; now exit 2, "check_facts: needs Python 3.11 or later; run it with the repository's venv/bin/python (this is 3.9)". The skill runs `venv/bin/python` |
| PR118-17 | Left in part | See the notes above |
| PR118-18 | Fixed, one line | See the notes above |

The checks run before reporting, each line pasted from its output:

- `--self-test`, exit 0: "self-test: 180 of 180 comparisons proven to pass and to fail; 64 of 64 readers proven to follow a changed source; 10 parser cases; 0 failures"
- The full check against a fresh `git archive` export of develop `bc64e028` with `--reference`, exit 1: "facts: 64 | stale 15 | not fully checked 0 | places: PASS 151, FAIL 29, GAP 0, ERROR 0 | NOT PASSED"
- `ruff check` from the worktree, as gate 03 runs it, exit 0: "All checks passed!"
- `isort --check-only --diff src tests services tracker alembic .claude .github` from the worktree, as gate 02 runs it, exit 0: "Skipped 2 files"
- `tracker/check_doc_drift.py --check`: "ok: 2 facts computed | 0 could not be computed | 0 stale | 0 structural"

Noticed in this round: the shared repository holds a ref named `refs/remotes/origin/develop 2`, a duplicate-copy artifact that makes `git fetch` print "bad object". It is outside this branch's scope and was left alone.

