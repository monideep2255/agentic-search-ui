# Documentation index

Reference material for System 3. Start here to find the right document without opening six.

Planning documents live in `requirements/`, not here. This folder holds reference and how-to material. The distinction that matters: `requirements/` says what we are building and why, `docs/` says how things actually work.

Last updated: 2026-08-02.

## Table of contents

- [Start here, by what you are doing](#start-here-by-what-you-are-doing)
- [The folders](#the-folders)
- [What is not here](#what-is-not-here)
- [Two things to know about this folder](#two-things-to-know-about-this-folder)
- [Moved paths](#moved-paths)

## Start here, by what you are doing

| I want to | Read |
|-----------|------|
| Understand the project from zero | `data-engineering/Project_overview_A_to_Z.md`, the navigation hub |
| Understand the search agent's design | `architecture/System_3_architecture_brainstorming.md` |
| Know how the agent reaches data | `architecture/Three_layer_data_architecture.md` |
| Write a Cypher query against the graph | `architecture/Biolink_repos_explained.md`, then `data-engineering/Knowledge_graph_on_server_reference.md` |
| Wire up one of the seven tools | `ncbi/Tool_implementation_mechanics.md` first, then that tool's section in the tech spec |
| Find an NCBI endpoint, rate limit, or record count | `ncbi/NCBI_databases_and_APIs_reference.md` |
| Decide whether to build or reuse something NCBI published | `ncbi/NCBI_repos_deep_dive.md` |
| Run a build phase | `build/Build_workflow_cadence.md`, or `build/Phase_6_execution_flow.html` for the visual |
| Watch parallel builders in live panes | `build/Agent_teams_tmux_quickstart.md` |
| Run the security scan before a pull request | `Claude_security_plugin_usage.md` |

## The folders

### `architecture/` how the system is designed

| Doc | What it is |
|-----|-----------|
| `System_3_architecture_brainstorming.md` | The search agent's design: agent loop, tools, multi-model harness, cost model, deployment |
| `Three_layer_data_architecture.md` | Layer 1 the graph, Layer 2 on-demand NCBI APIs, Layer 3 enrichment, and how the agent uses each |
| `Biolink_repos_explained.md` | The BioLink model: categories, predicates, CURIEs. Needed to read the graph schema |

### `build/` how the work gets done

| Doc | What it is |
|-----|-----------|
| `Build_workflow_cadence.md` | The quick reference for one build phase: twelve stages, who acts at each, the model and effort per stage, where every file gets written. Stage 5 is the blocking premise gate |
| `Phase_6_execution_flow.html` | The same cadence as a visual page. Opens in a browser with no server. Also published as a Claude artifact |
| `Agent_teams_tmux_quickstart.md` | tmux launch guide so parallel builders appear in live panes rather than invisible background sessions |

### `ncbi/` the data sources and their traps

| Doc | What it is |
|-----|-----------|
| `Tool_implementation_mechanics.md` | Nineteen per-tool API traps from tech spec section 6. Facts a builder needs before wiring a tool. The policy versions live in the rules; this holds only the facts |
| `NCBI_databases_and_APIs_reference.md` | All 39 NCBI databases: endpoints, rate limits, record counts |
| `NCBI_repos_deep_dive.md` | Thirteen NCBI GitHub repos analyzed: what to reuse, what to adapt, what not to build locally |

### `data-engineering/` the graph System 3 queries

| Doc | What it is |
|-----|-----------|
| `Knowledge_graph_on_server_reference.md` | Operating the live graph: SSH access, Cypher examples, indexes, node and edge counts, cost |
| `Project_overview_A_to_Z.md` | The navigation hub with pointers into every doc across the whole project, including the data engineering repo |

### At the root

| File | What it is |
|------|-----------|
| `Claude_security_plugin_usage.md` | How to run the on-demand security scan and apply patches. Pinned here, see below |
| `Claude_Code_model_fallback_setup.md` | Personal dev-workflow note on switching Claude Code to a cheaper model backend past a weekly usage limit, without spending real money on prototype development |
| `publish_body.sh` | Derives the publishable fragment from a standalone HTML page in this repo |

## What is not here

| Looking for | It lives in |
|-------------|-------------|
| The PRD, tech spec, evaluation playbook, strategic memo | `requirements/` |
| The build order and its 26 phases | `requirements/Technical_specification.md` section 25 |
| The gate list, every obligation mapped to its owner | `requirements/phase_5/Coverage_map.md` |
| Decisions and their rationale | `DECISIONS.md` at the repo root |
| What broke during the build and what fixed it | `LEARNINGS.md` at the repo root |
| Current build status | `tracker/BOARD.md`, or `tracker/board.html` for the kanban view |
| Pipeline, parser, and graph-loading docs | The System 1 and 2 repo, symlinked at `reference/agentic-search-data-engineering` |

## Two things to know about this folder

`Claude_security_plugin_usage.md` cannot move. The locked technical specification references it at this exact path, and that spec is frozen until the Plan.md step 6.2 reconciliation. It is also a symlink into `personal-os-work` rather than a real file here, so it resolves only on a machine with that repo checked out alongside this one, and will dangle in a fresh clone or in CI. `data-engineering/` is pinned for the same reason.

HTML pages here are the source, not a copy. The file in this folder is what gets edited and version controlled. Publishing derives a fragment from it with `publish_body.sh`, into a temp path rather than into the repo. Never edit a published page and expect the repo to follow; the dependency runs one way.

## Moved paths

Files were regrouped into folders on 2026-07-26. Every reference in an editable file was updated. `DECISIONS.md` is append-only by rule, so three of its historical rows still cite the old flat paths. Those rows are a record of what was decided and when, not a live index, and they are correct about the decision even where the path has since changed. Use this table to translate:

| Old path | Now at |
|----------|--------|
| `docs/System_3_architecture_brainstorming.md` | `docs/architecture/System_3_architecture_brainstorming.md` |
| `docs/Agent_teams_tmux_quickstart.md` | `docs/build/Agent_teams_tmux_quickstart.md` |
| `docs/Build_workflow_cadence.md` | `docs/build/Build_workflow_cadence.md` |
| `docs/Phase_6_execution_flow.html` | `docs/build/Phase_6_execution_flow.html` |
| `docs/NCBI_databases_and_APIs_reference.md` | `docs/ncbi/NCBI_databases_and_APIs_reference.md` |
| `docs/NCBI_repos_deep_dive.md` | `docs/ncbi/NCBI_repos_deep_dive.md` |
| `docs/Tool_implementation_mechanics.md` | `docs/ncbi/Tool_implementation_mechanics.md` |
