# Decision log: agentic search

Running log of all decisions made across the agentic search project. Organized by date.

---

## April 2, 2026: brainstorming session (1.5 hours)

All decisions made by Monideep, analysis and execution by Claude Code. These are brainstorming directions, not final commitments. See April 5 session for committed architecture decisions.

### Decisions made

| # | Decision | What was said | What it changed | Alternatives considered |
|---|---|---|---|---|
| 1 | Scope expansion beyond 4 databases | "Can we data engineer ALL the data? Let's think big" | Expanded from 4 databases to 6-8 ingested + 30 on-demand. Changed the entire project scale. | Stay with 4 (proposal), go to 10, try all 39 |
| 2 | Three-system architecture | "I see this as 3 things now: data engineering, knowledge graphs, UI" | Defined the system boundaries. Everything after this was organized around the 3 systems. | Single monolithic system, 2-system split |
| 3 | Subgraph pattern (small KGs feeding a big KG) | "Each with its own knowledge graph?" then "must have some commonalities to be linked" | Adopted the Monarch Initiative pattern: per-database subgraphs merged via node normalization. | Single monolithic graph, fully federated (no merge) |
| 4 | Cloud hosting question | "Should we host it in an AWS or GCP instance?" | Produced the cloud comparison table. Decision: use whichever NCBI already supports, or cheapest VPS for personal build. | On-prem, Railway (existing), managed Neo4j Aura |
| 5 | Streaming as a requirement | "We will need to stream the thought process then?" | Added 3-phase streaming to UI architecture (thought process, partial results, final answer). | Wait for complete answer, progress bar only |
| 6 | Graph visualization with source links | "There should also be a graph visualization that leads them to exact source, that is why the LitSense and all the variations" | Added Cytoscape.js interactive graph with clickable source links and entity cards. Connected LitVar2/LitSense as deep-link providers. | Text-only answers, static graph images |
| 7 | Evaluation built into the system | "The evaluations also need to be setup to keep improving the answer quality" | Added 3-channel evaluation pipeline (golden datasets, LLM-as-judge, user feedback) with quality dashboard. | Manual review only, no evaluation |
| 8 | Five access channels (added CLI) | "We are still going to provide the 4 outlets right? UI, MCP, API, KGX for bulk?" then "do we create a CLI agent?" | Expanded from 4 channels (proposal) to 5. CLI became the 5th channel. | Keep original 4 from proposal |
| 9 | Security designed in, not bolted on | "What about the security? Need that too be honest built in too" | Added full security architecture across all 3 systems: auth, Cypher injection prevention, prompt injection guardrails, session isolation, audit logging, FISMA/FedRAMP considerations. | Defer security to post-alpha |
| 10 | Multi-agent architecture (not monolithic) | "Can we create agents? Do I only have 1 agent or a group?" | Designed 8 specialized agents with specific roles, parallel execution, and async evaluation. | 1 monolithic agent, 39 per-database agents |
| 11 | Build independently if not funded | "Lets assume NCBI will not pay. I want to build it anyway. I have the data, I have you." | Created the personal build plan. Changed the project from "NCBI innovation proposal" to "open source portfolio project." | Wait for NCBI funding, scale down to smaller demo |
| 12 | Open source as strategy | "What if I open source this and this becomes my portfolio project" | Adopted Apache 2.0 license, GitHub-first development, community growth strategy. | Keep private, dual license, proprietary |
| 13 | No patent | "I want to open source everything" | Rejected patent path. Chose publication + open source as the protection and amplification strategy. | File provisional patent, dual patent + open source |
| 14 | Separate build plan document | "Create a separate build plan doc in the Agentic Search folder (cleaner for a project kickoff reference)" | Created Personal_build_plan.md as standalone document. | Add to Q&A doc, keep in conversation only |
| 15 | Paper and conference strategy | "That is what my manager proposed, writing a paper" then "Can then present at poster at conferences too" | Added publication targets (Bioinformatics, NAR, JAMIA) and 5 target conferences (ISMB, Bio-IT World, AMIA, BOSC, KGC). | Build without publishing, blog posts only |

---

### Decision pattern

Every decision followed the same pattern:

1. Monideep asked a question or stated a direction
2. Claude Code provided analysis, options, and trade-offs
3. Monideep picked the direction
4. Claude Code executed (wrote docs, designed architecture, created diagrams)

Zero decisions were delegated to Claude Code. The analysis was delegated. The decisions were not.

### Documents produced in this session

| Document | What it contains |
|---|---|
| NCBI_databases_and_APIs_reference.md | All 39 NCBI databases with live API data, record counts, fields, cross-links, rate limits, 4 research APIs |
| Agentic_search_architecture_QA.md | 18 questions and answers covering scope, architecture, BioLink compliance, ontology setup, multi-agent design, security, access channels, BCC comparison, cost analysis |
| Personal_build_plan.md | 2-month build plan, cost breakdown, repo structure, open source strategy, legal protections, patent decision, publication/conference plan, target companies, 6-month exit plan |
| Vision_of_success.md | 5 concrete user scenarios showing what the system looks and feels like when working |
| KG_prototype_feedback.md | Reformatted SME feedback defining query patterns and quality bar |
| Decision_log_April_2_2026.md | This document |

---

## April 5, 2026: architecture review session

Monideep reviewed the April 2 brainstorming docs to converge on what to actually build. Stress-tested each decision with questions. Crystallized into a committed System 1 plan.

### Decisions made

| # | Decision | What was said | What it changed | Alternatives considered |
|---|---|---|---|---|
| 16 | Data folder reorg: priority files vs reference | "Keep the two priority files at top level, move the rest to reference" | Created Data/reference/ subfolder. Architecture QA and Build Plan are the two priority docs. | Keep all 6 files flat, create multiple subfolders |
| 17 | Two-track plan (personal build vs innovation proposal) | "It doesn't really affect the innovation proposal, but indirectly it plays a role" | Created Two_track_plan.md. Track 1 (personal build) and Track 2 (innovation proposal) are parallel, neither depends on the other. | Single combined plan, sequential dependency |
| 18 | April 2 decisions are brainstorming, not commitments | "What you call decisions made are more brainstorming" | Reframed the Decision_log as brainstorming directions. Architecture review (today) is where commitments are made. | Treat April 2 decisions as final |
| 19 | Confirmed 6 databases with evidence-based reasoning | Questioned: "How did you come to this conclusion? What proof do we have?" | Validated the 6 databases using 3 evidence sources: connectivity ranking (einfo API data), SME feedback (March 2026), and traversal path completeness. | Add more databases, reduce to fewer |
| 20 | Provenance is a first-class architectural requirement | "I want the provenance, the sources, the exact sources... trust is the true moat" | Provenance (source URLs, source IDs) required on every node and every edge from day one. Not a UI feature to add later. | Add provenance after initial build |
| 21 | BioLink schema adopted, not invented | Confirmed after reviewing ontology gap analysis | Use BioLink Model as the schema standard. Interoperable with Monarch, RTX-KG2, KG-Hub. | Custom schema, RDF/OWL |
| 22 | Keep all records regardless of ontology coverage | "What if all diseases don't have MONDO IDs? Are we going to lose that data?" | Three-tier approach: fully mapped records use canonical IDs, partially mapped use fallback IDs (MedGen CUI instead of MONDO), orphan records still enter the graph. No data loss. | Drop records without canonical IDs |
| 23 | Fallback ID hierarchy confirmed | Discussed during ontology gap question | MONDO -> MedGen CUI -> OMIM for diseases. NCBIGene always available for genes. Multi-hop traversal handles the rest. | Single canonical or nothing |
| 24 | Schema lives in System 2, System 1 consumes it | "Does the schema come in System 2, and System 1 is just about pipelines?" | Clean boundary: System 1 produces KGX files, System 2 defines the schema and does merge/load. KGX files are the interface. | Schema defined in System 1, monolithic system |
| 25 | Build order: core triangle first | Confirmed after reviewing build phases | Gene + ClinVar + MedGen first (richest cross-references). Then PubMed + Taxonomy. Then SNP. Each phase connects to existing nodes. | Build all 6 in parallel, or alphabetical order |
| 26 | System 1 plan document created | "Come up with this architecture diagram and a detailed step-by-step" | Created Plan/System_1_data_engineering_plan.md with architecture diagram, FTP file inventory, pipeline pattern, schema, build order, risk table, wall-clock estimates. | Keep using brainstorming docs only |
| 27 | Five access channels are delivery mechanisms, not architecture | "Yes, those are delivery mechanisms and we can think about that later" | Deferred channel design to System 3. All 5 channels serve the same BioLink-compliant graph. | Design channels during System 1 |

### Decision pattern (same as April 2)

Every decision followed the same pattern:

1. Monideep reviewed the brainstorming doc
2. Asked probing questions ("how do you know? what's the evidence?")
3. Claude Code provided data-backed analysis
4. Monideep confirmed or redirected
5. Claude Code documented the committed decision

The shift from April 2: brainstorming became commitment. Divergent thinking became convergent.

---

## April 6, 2026: infrastructure and cost review session

Monideep reviewed the System 1 plan and architecture QA for realism. Focused on infrastructure costs for a personal build. Key theme: frugality. Maximum quality at minimum cost.

### Decisions made

| # | Decision | What was said | What it changed | Alternatives considered |
|---|---|---|---|---|
| 28 | PostgreSQL + AGE over Neo4j | "Not comfortable paying 100-200 a month. 10-15 works" | Replaced Neo4j as the default graph database. PostgreSQL + AGE is disk-based, handles 150M nodes on 8GB RAM, supports the same Cypher queries. Saves $100-200/month. | Neo4j Community (needs 64GB+ RAM), KuzuDB (abandoned, acquired by Apple Oct 2025), DuckDB (no Cypher) |
| 29 | Work computer as primary infrastructure | "This is fine: Run it on your work computer (355GB free, $0/month)" | Primary development and data storage on work computer. VPS ($10-15/month) as fallback for personal project if needed. | VPS from day one ($10-15/month), cloud provider ($50-200/month) |
| 30 | Frugal LLM strategy: open source models first | "What if we use open source model like from nvidia, gemma4 and the openai-120, the cheap ones only. The main thing is to build the harness/system that produces consistent results" | LLM cost dropped from $50-150/month to $5-20/month. Ollama (local, $0) for 3 of 4 agent tasks. OpenRouter for Cypher generation only. | Anthropic/OpenAI premium APIs ($50-150/month), all-local Ollama ($0 but slower) |
| 31 | Model-agnostic harness is the goal | "Goal to be honest is to create a harness so good that it does not matter what model we use" | Agent interfaces defined by input/output contracts, not model capabilities. Build once, swap models freely. Start cheap, upgrade only if quality demands it. | Optimize for one specific model, model-specific prompts |
| 32 | Budget cap: $100/month max, target $50/month | "Goal I am aiming for is max 100/month for all the cost. Best within 50. Do not count claude code max (that is personal)" | Set hard budget constraint. Claude Code Max ($100/month) excluded as already paid for other work. Incremental project cost: $10-35/month. | No budget cap, $300-500/month (original estimate) |
| 33 | Chinese models banned for NCBI, allowed for personal | "For NCBI cannot use any chinese: deep seek, kimi and others. But do think can use them for personal project to be honest" | Two model policies: Track 2 (NCBI) restricted to NVIDIA, Google, OpenAI, Anthropic, Meta, Mistral. Track 1 (personal) can also use DeepSeek, Qwen. | Ban Chinese models entirely, allow all models |
| 34 | Ollama Cloud as scaling option | "Ollama has a cloud version too. Planning on using that if needed" | Added Ollama Cloud (~$20/month Pro plan) as middle tier between local Ollama ($0) and OpenRouter API. | Only local Ollama, only OpenRouter |
| 35 | Live demo URL is Phase 2 | "I will eventually want a live working URL for people to play with" | Live URL deferred to after pipelines and graph work. Deploy to VPS when it works. Ship code and paper first. | Build with live URL from day one |
| 36 | System 1 plan is the real plan, rest is brainstorming | "Focus on the system 1 architecture plan, that is the most thought out, rest all was brainstorming" | Confirmed System 1 data engineering plan as the committed, actionable document. Personal_build_plan.md and other docs remain brainstorming context. | Treat all docs as equally committed |
| 37 | All data, not subsets | "Goal is to get all the data" and "No all organisms is the goal here" | Full PubMed baseline (40M articles), all-organism Gene (94M records). Subsets are fallbacks, not targets. | Start with PubMed 2024-2026 subset, human-only Gene |

### Decision pattern (same as prior sessions)

1. Monideep asked about costs and infrastructure
2. Claude Code provided options with pricing
3. Monideep chose the cheapest viable option
4. Claude Code updated the plan documents

Theme: every decision optimized for the same thing. Highest quality at the lowest price. The Amazon frugality principle applied to a personal project.

---

*Living document. Updated as decisions are made.*
