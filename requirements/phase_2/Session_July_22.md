# Phase 2 session, July 22

Phase 2 of System 3 planning: competency questions and the evaluation playbook. Phase 1 is complete (all 13 steps, 75 decisions logged, synthesis written). This session works Steps 2.1 and 2.3: understand the collected competency-question set, then refine it into a locked, tiered, capped v1 set using the moat test and a coverage metric.

This file is both the project record and a personal learning log. It captures the discussion, the reasoning, and the decisions, in order.

## Table of contents

- [Where we are](#where-we-are)
- [Step 2.1: the collected competency-question set](#step-21-the-collected-competency-question-set)
- [Step 2.3: refining the set](#step-23-refining-the-set)

## Where we are

Monideep clarified the sequencing: Step 2.1 (`01_Consolidated_findings.md`) is the collected, already-scraped user-research material, not a to-do. It merged four findings sources into one tiered set:

- A: Confluence personas and user research
- B: Confluence user journeys and workflows
- C: Confluence product, roadmap, and PRDs
- D: Jira feature requests and user issues

So there is no separate live-scrape gate. The real work is Step 2.3: refining that raw set into a locked v1 competency-question set.

## Step 2.1: the collected competency-question set

The set as it stands (source: `reference/personal-os-work/NIH/Agentic-Search/Reference/system-3-brainstorming/01_Consolidated_findings.md`):

- 65 competency questions across three tiers: 10 Tier 1 (must-answer wedge), 28 Tier 2 (should-answer baseline), 27 Tier 3 (stretch, edge, or risky).
- 11 personas. Strong evidence: literature researchers (1), sequence data users (2), geneticists (3), bioinformaticians (4), epidemiologists and public health (6, the strongest wedge persona), cross-database journey users (10), and AI agents / MCP / LLM consumers (11, an emerging 2025-2026 signal added during consolidation). Weak: structural biologists (5), drug discovery and pharma (7), educators and students (9). Clinicians (8) are moderate but need clinical-safety boundaries.
- Tier 1 is organized by wedge type: gene-variant-literature (Q1 to Q4), pathogen-sequence-outbreak (Q5 to Q7), paper-data-tool (Q8 to Q10). The two demo spines are human-variation/clinical interpretation and pathogen/SRA surveillance.

Gaps and flags the source itself raises, which refinement must resolve:

- Capability gaps flagged as undecided: ACMG classification (Q1), VCF and BLAST execution (Q2, Q7, Q9), controlled-access data (Q37 and dbGaP rows), clinical guidance (Q39, Q47, Q50, Q51), citation ranking and counts (Q14). Each is a "does the system classify or only assemble cited evidence" decision.
- The source's own caution: Tier 1 is an eval floor, not proof of robustness. Passing it shows the wedge works on documented cases, not that the system is generally robust.
- Carried in from Step 1.12: a 100 percent competency-question pass rate can hide large concept incompleteness (one study: a 100 percent pass rate captured only 14 percent of a domain's concepts). This is why the moat test is paired with a separate coverage metric.

## Step 2.3: refining the set

### Decision: the moat test is the primary selection and tiering bar

The five moat-test dimensions (cannot-just-Google, deterministic, provenance, learn-from-the-system, loop-human-behavior) become the primary bar for selecting and tiering the v1 competency-question set, outranking persona coverage and raw usage frequency.

Reasoning: the Phase 1 differentiation thesis is cited cross-database synthesis that a general AI tool cannot reach or cite. A question that scores high on persona coverage or usage frequency but low on cannot-just-Google is exactly what a general tool already answers, so it is weak for System 3 even if users ask it often. Persona coverage and frequency stay as secondary inputs (they keep the set representative and grounded in real usage), but they do not override a weak moat score.

Logged to DECISIONS.md.

### Decision: the moat test operates as a structured bar, not a flat score

The five dimensions are not the same kind of thing, so they are not averaged into one score. The bar is structured:

- Gates (binary, must-pass to qualify for the v1 set at all):
  - Provenance: every claim links to a source record. Already non-negotiable per the citations rule. A question whose answer cannot be cited is disqualified, not low-scored.
  - Deterministic: the answer is reproducible and verifiable, not a plausible generation that varies run to run.
- Ranking (drives which tier a question lands in):
  - Cannot-just-Google: needs synthesis across the graph and APIs, not one web result. The core differentiator.
  - Learn-from-the-system: surfaces a cross-database relationship or structured evidence a generic summary cannot give.
- Deferred:
  - Loop-human-behavior: about how users follow up, which cannot be observed until the system is live. It moves to the Step 2.5 online loop as a re-ranking signal, not a v1 static-selection criterion.

Determinism nuance (agreed): for a live system hitting live APIs, a pathogen, clinical-trial, or PubMed answer changes as the underlying data changes. That is not a determinism failure. Deterministic means reproducible and verifiable given the data state at query time. Eval fixtures pin the data state or accept a freshness window. A naive same-answer-forever reading would wrongly disqualify strong freshness-dependent questions, so it is rejected.

Logged to DECISIONS.md.

### Thread raised: do we need local MCP servers for live API calls?

Monideep noted that a previous NCBI API experiment required building local MCP servers to get the data reliably, and asked whether System 3 needs the same.

Resolution: no local MCP servers are needed for the agent to make live API calls. The earlier experiment needed them because that harness could only expose tools to the model through MCP. System 3 owns its harness (FastAPI plus LangGraph), so the agent calls direct Python tool functions that make the HTTP calls to E-utilities, Datasets API v2, Variation Services, PubTator3, and LitVar2. No MCP process sits in the loop. This is Decision 24. MCP still appears, but only outbound: System 3 is exposed as an MCP server so other agents can consume it (persona 11), one of the five delivery formats. Inbound is direct Python; outbound is MCP.

### Decision: refine the CQ set now, defer the API and tool study to Phase 4

CQ refinement proceeds now. The deep API and tool design is Phase 4 (one tech-spec section per tool) and Phase 6 (build). During Step 2.3 tiering we fold in only a lightweight "can we answer this today" feasibility check, because a question the APIs and graph cannot answer yet cannot be a Tier 1 must-pass.

Because System 3 depends heavily on the NCBI, Datasets, and enrichment APIs, a full current-state deep dive of those APIs is added to the plan as Phase 4 Step 4.0: live endpoints, request and response schemas, the fields each CQ needs, rate limits, auth, and empty-result behavior, plus any drift since the Phase 1 survey. Each tool specification is then written against that capability sheet.

Logged to DECISIONS.md.

### Admin and process for Phase 2

- Input pipeline: Phase 2 uses `requirements/phase_1/Phase_1_synthesis.md` as its primary input. The PRD is a downstream product built from the synthesis plus the Phase 2 evaluation playbook, not an input to Phase 2.
- Cadence maintained: meeting notes in `requirements/meetings/` (this session: `2026-07-22_Phase_2_steps_2.1-2.3.md`), a Phase 2 continuation prompt (`requirements/phase_2/Continuation_prompt.md`), and this session file.
- Open process question: whether to formalize the per-checkpoint documentation ritual (update meeting notes, continuation prompt, synthesis, session docs, DECISIONS.md, Plan.md status) as a user-invoked skill, versus a memory or a checklist doc. Resolved: a dedicated, user-invoked `/phase-checkpoint` skill (see below).

### Decision: dedicated /phase-checkpoint skill for the documentation cadence

Chose a dedicated skill over folding the step into `/ship` or keeping it as a memory plus a hand-run checklist. The skill (`.claude/skills/phase-checkpoint/SKILL.md`) syncs the planning artifacts at a sub-phase or phase boundary: DECISIONS.md, the session doc, the dated meeting note, the continuation prompt, and at a phase end the phase synthesis and Plan.md status. It is user-invoked at a declared boundary, never auto-run, and never commits or pushes (that stays `/ship`). Registered in the CLAUDE.md skills table.

Logged to DECISIONS.md.

### Refinement: one design-time ranking dimension, and the moat-set-versus-full-set distinction

Monideep pushed on two things that refine the structured bar.

First, learn-from-the-system is not cleanly a design-time score. Its distinctive content (does the user gain insight, does the system learn from usage) can only be observed once real users are on the app. Its other reading (surfaces cross-database structured evidence) just restates cannot-just-Google, so keeping both as ranking dimensions double-counts. So learn-from-the-system joins loop-human-behavior as a deferred online signal (Step 2.5 re-ranking).

Second, deciding that a question "needs" the databases is a judgment we impose, which biases the set. So cross-database span is rejected as a scoring axis. The only design-time ranking dimension is cannot-just-Google, scored by an external empirical test: run the candidate against a general AI tool or search engine; if it cannot produce the cited answer, the question passes. The judgment moves from us to an observation, and it needs no app and no users.

Tier mapping among gate-passers (provenance and deterministic both pass): cannot-just-Google high is Tier 1 must-pass, partial is Tier 2 should, none is not a moat CQ. Persona coverage and usage frequency are intra-band tiebreakers plus a coverage-balance check.

Moat set versus full query set (Monideep's framing): the PoC moat CQ set is a deliberately small, cross-database-biased subset that proves the wedge. It is not a model of all real usage. Simple single-source fetches (for example "give me the Datasets API link") are valid queries the system must handle, but they score zero on cannot-just-Google, so they sit outside the moat eval set. Excluding them from the moat set is not the system refusing them.

Logged to DECISIONS.md (refines the earlier structured-bar decision).

### Parked thread: A/B test questions across model combinations

Monideep raised A/B testing selected questions with different model combinations (orchestrator plus planner), randomly assigned, comparing outputs. This is the online complement to the offline model-bench (Decision 43): model-bench picks the initial model per tier offline; A/B testing validates and tunes the live combination on real or golden-set questions. Home: name it in the Phase 2 evaluation playbook's model-selection section; design the mechanism (randomized routing, output capture, comparison, LangSmith experiment tracking) in the Phase 4 tech spec. Parked here so it is not lost.

### First pass: scoring the 10 Tier 1 questions against the bar

Reasoned first pass (cannot-just-Google marked for empirical confirmation where a general tool gives a fluent but uncited answer). Gates are pass/fail; cannot-just-Google is high/partial/none.

| # | Question (short) | Provenance | Deterministic | Cannot-Google | First-pass verdict |
|---|------------------|-----------|---------------|---------------|--------------------|
| Q1 | CNV to ACMG classification plus evidence | pass (evidence) | fail if it classifies | high | Reframe to evidence-assembly, then Tier 1 |
| Q2 | VCF to prioritize ADA-region variants plus evidence | pass (evidence) | fail (prioritize plus VCF execution) | high | Weakest: reframe plus VCF gap, likely Tier 2 or narrowed |
| Q3 | BRCA1 to gene, PubMed, ClinVar, GTR, MedGen | pass | pass | high (confirm) | Clean Tier 1 (flagship) |
| Q4 | disease phrase to routed cross-database queries | pass | pass (ask-back on ambiguity) | high (confirm) | Tier 1 |
| Q5 | Salmonella to SNP cluster, AMR, BioSample | pass | pass | high | Tier 1 (feasibility: Pathogen Detection access) |
| Q6 | natural-language SRA metadata search | pass | pass | high | Tier 1 (feasibility: metadata field availability) |
| Q7 | SRA reads similar to a query sequence | pass | pass given data state | high | Tier 1 conditional on the execution decision |
| Q8 | PMID to linked SRA, BioProject, GEO, assembly, PubChem | pass | pass | high | Clean Tier 1 |
| Q9 | BLAST to top hit to gene, SRA, PubMed | pass | pass given data state | high | Tier 1 conditional on the execution decision |
| Q10 | BioProject to BioSamples, SRA, assembly bundle | pass | pass | high | Clean Tier 1 |

Tally: 6 clean Tier 1 (Q3, Q4, Q5, Q6, Q8, Q10, with feasibility caveats on Q5 and Q6); 2 conditional on the eval-execution decision (Q7, Q9); 2 needing the assemble-not-classify reframe (Q1, Q2, with Q2 the weakest because of the VCF-ingestion gap).

Two capability principles this scoring surfaces (pending confirmation):

1. Assemble, not classify. Moat CQs surface cited evidence and never render the clinical verdict (ACMG pathogenicity, variant prioritization). That is the deterministic gate working, and it matches the Phase 1 forbidden-outputs boundary. Reframes Q1 and Q2.
2. Fixtures for execution-heavy CQs in the eval. Q7, Q9, and Q2's VCF involve BLAST, similarity, or VCF execution. For the eval set, pin them to precomputed fixtures at a fixed data state so they stay deterministic; live-tool wiring is a Phase 3 and 4 build decision.

Cap implication: a realistic v1 must-pass moat set is roughly 6 to 8, which supports a small cap and the start-small-prove-the-loop intent. To confirm after the two capability principles are settled.

### Decision: assemble the evidence, never the verdict (Q1 and Q2 reworded)

Confirmed: a moat CQ, and every system answer, surfaces cited evidence and never renders the clinical verdict (pathogenicity classification, variant prioritization, diagnosis, treatment). The system assembles and cites; a human decides. This is the Phase 1 forbidden-outputs boundary applied at the competency-question level.

Reworded:

- Q1: For a CNV like chr6:24545637-24548192 (GRCh37), surface the ACMG-relevant, cited evidence for pathogenicity assessment from ClinVar, OMIM, dbVar, Variation Viewer, and segmental duplications. The system assembles the evidence for a human classifier; it does not return a pathogenicity classification.
- Q2: For a VCF on GRCh37 with variants in the ADA region from a SCID-suspected patient with IBD, surface the cited evidence for each candidate variant from ClinVar, dbSNP, GWAS, PubMed, Remap, and Sequence Viewer. The system assembles the evidence for a human to prioritize; it does not return a prioritization ranking. Q2 still carries the VCF-ingestion capability gap.

Both now pass the gates. Q2 remains the weaker of the two because of the VCF-ingestion requirement (see the execution-heavy question, pending).

Logged to DECISIONS.md.

### Decision: no live tools in v1; defer the three execution-heavy questions

Confirmed: v1 runs no compute tools (no BLAST, no sequence similarity, no VCF ingestion). The three execution-heavy questions defer to a fast-follow set (Q2 VCF, Q7 SRA similarity, Q9 BLAST), added later with pinned fixtures.

Wedge coverage is preserved without them: the remaining questions cover all three Tier 1 wedge types.

v1 must-pass moat set (pure cross-database fetch-and-join):

- Entity-keyed, cleanest (six): Q3 (BRCA1 assembly), Q4 (disease-phrase routing), Q5 (Salmonella cluster), Q6 (natural-language SRA metadata), Q8 (PMID linked records), Q10 (BioProject bundle).
- Q1 (reworded) is execution-free too, but it is coordinate-keyed (a CNV genomic range), so it needs a feasibility check: do our data-access paths support coordinate-range overlap queries (dbVar and ClinVar by region, segmental-duplication overlap)? If yes, Q1 is the seventh; if not, it defers.

Open: lock the v1 cap at the clean six, or seven including Q1 pending the coordinate-range feasibility check. Q5 and Q6 carry lighter feasibility flags (Pathogen Detection access; SRA metadata field availability) to verify in the lightweight check.

Logged to DECISIONS.md.

### Decision: v1 must-pass moat set locked at seven

The v1 Tier 1 must-pass moat set is seven questions: Q1 (reworded), Q3, Q4, Q5, Q6, Q8, Q10.

Wedge and persona balance:

- Wedge types: gene-variant-literature (Q1, Q3, Q4), pathogen-sequence-outbreak (Q5, Q6), paper-data-tool (Q8, Q10). All three covered.
- Personas touched: 1, 2, 3, 4, 6, 8, 10, 11.

Q1 carries a coordinate-range feasibility flag; if the dbVar and ClinVar by-region and segmental-duplication-overlap query proves infeasible in the lightweight check, Q1 drops to fast-follow and the cap is six.

Fast-follow set (added after the loop works, with pinned fixtures): Q2 (VCF), Q7 (SRA similarity), Q9 (BLAST).

Logged to DECISIONS.md.
