# Documentation index

Reference material for System 3. Start here to find the right document without opening six.

Planning documents live in `requirements/`, not here. This folder holds reference and how-to material: architecture explanations, API facts, and the workflow the build runs on. The distinction that matters: `requirements/` says what we are building and why, `docs/` says how things actually work.

Last updated: 2026-07-26.

## Table of contents

- [Start here, by what you are doing](#start-here-by-what-you-are-doing)
- [Everything in this folder](#everything-in-this-folder)
- [What is not here](#what-is-not-here)
- [Why the folder is flat](#why-the-folder-is-flat)

## Start here, by what you are doing

| I want to | Read |
|-----------|------|
| Understand the project from zero | `data-engineering/Project_overview_A_to_Z.md`, the navigation hub |
| Understand the search agent's design | `System_3_architecture_brainstorming.md` |
| Know how the agent reaches data | `architecture/Three_layer_data_architecture.md` |
| Write a Cypher query against the graph | `architecture/Biolink_repos_explained.md`, then `data-engineering/Knowledge_graph_on_server_reference.md` |
| Wire up one of the seven tools | `Tool_implementation_mechanics.md` first, then the tool's section in the tech spec |
| Find an NCBI endpoint, rate limit, or record count | `NCBI_databases_and_APIs_reference.md` |
| Decide whether to build or reuse something NCBI already published | `NCBI_repos_deep_dive.md` |
| Run a build phase | `Build_workflow_cadence.md`, or `Phase_6_execution_flow.html` for the visual |
| Watch parallel builders in live panes | `Agent_teams_tmux_quickstart.md` |
| Run the security scan before a pull request | `Claude_security_plugin_usage.md` |

## Everything in this folder

### The build workflow

| Doc | What it is |
|-----|-----------|
| `Build_workflow_cadence.md` | The quick reference for how one build phase runs: eleven stages, who acts at each, the model and effort per stage, and where every file gets written |
| `Phase_6_execution_flow.html` | The same cadence as a visual page. Opens in a browser with no server. Also published as a Claude artifact |
| `Agent_teams_tmux_quickstart.md` | tmux launch guide so parallel builders appear in live panes rather than invisible background sessions |
| `Claude_security_plugin_usage.md` | How to run the on-demand security scan, apply patches, and how it complements the always-on guidance plugin. See the note below, this one is a symlink |

### Architecture

| Doc | What it is |
|-----|-----------|
| `System_3_architecture_brainstorming.md` | The search agent's design: agent loop, tools, multi-model harness, cost model, deployment |
| `architecture/Three_layer_data_architecture.md` | Layer 1 the graph, Layer 2 on-demand NCBI APIs, Layer 3 enrichment, and how the agent uses each |
| `architecture/Biolink_repos_explained.md` | The BioLink model: categories, predicates, CURIEs. Needed to read the graph schema |

### Data and APIs

| Doc | What it is |
|-----|-----------|
| `Tool_implementation_mechanics.md` | Nineteen per-tool API traps taken from tech spec section 6. Facts a builder needs before wiring a tool. The policy versions of these live in the rules; this file holds only the facts |
| `NCBI_databases_and_APIs_reference.md` | All 39 NCBI databases: endpoints, rate limits, record counts |
| `NCBI_repos_deep_dive.md` | Thirteen NCBI GitHub repos analyzed: what to reuse, what to adapt, what not to build locally |
| `data-engineering/Knowledge_graph_on_server_reference.md` | Operating the live graph on the Hetzner box: SSH access, Cypher examples, indexes, node and edge counts, cost |
| `data-engineering/Project_overview_A_to_Z.md` | The navigation hub with pointers into every doc across the whole project, including the data engineering repo |

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

One caveat on `Claude_security_plugin_usage.md`: it is a symlink into `personal-os-work`, not a file in this repo. It resolves on the machine where that repo is checked out beside this one, and will dangle in a fresh clone or in CI. Everything else in this folder is a real file.

## Why the folder is flat

Grouping these into subfolders by topic was considered and rejected, because four of the eleven documents are pinned in place by files that cannot be edited to follow them:

- `DECISIONS.md` is append-only by rule, and its rows reference `Agent_teams_tmux_quickstart.md`, `Claude_security_plugin_usage.md`, and `Tool_implementation_mechanics.md`. Moving those would leave permanently wrong paths in the decision history.
- `requirements/Technical_specification.md` is locked until the Plan.md step 6.2 reconciliation, and it references `data-engineering/Knowledge_graph_on_server_reference.md` and `Claude_security_plugin_usage.md`.

Moving only the unpinned seven would produce a half-organized folder, which is harder to navigate than a flat one. So this index does the organizing instead, and the paths stay stable. Revisit at step 6.2, when the spec unfreezes and the whole set can move together.
