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

### Decision: Q1 coordinate-range feasibility resolved, cap holds at seven

Ran the lightweight feasibility check the previous decision flagged: can our data-access paths answer Q1's coordinate-range query for the CNV chr6:24545637-24548192 (GRCh37)? Broke Q1 into its five named evidence sources and checked each against the three layers, using the reference docs only (no live query; the live API deep dive is Phase 4 Step 4.0).

Source by source:

- dbVar by region: feasible via Layer 2. dbVar indexes Chromosome/Position (42 searchable fields), and ESearch's `term` supports numeric ranges. A `chr6 AND 24545637:24548192[position]` query is constructable.
- ClinVar by region: feasible and cleaner. ClinVar stores an explicit GRCh37 position field (`C37`) plus variant length (`VLEN`), so Q1's GRCh37 coordinate queries directly, no liftover.
- Overlapping genes plus OMIM phenotypes: feasible. Resolve genes in the region, then link OMIM by gene.
- Variation Viewer: feasible as a citation link, not a data pull. It is a genome-browser view, so it is a graphical-context link-out that fits assemble-and-cite.
- Segmental duplications: not reachable. Segmental dups are a UCSC genome-browser track (genomicSuperDups), not an NCBI E-utilities database. None of the three layers returns them. This is the one real gap.

Layer 1 note: the knowledge graph has no genomic-coordinate node properties, so Q1 rides Layer 2, not the graph. Q1 is an API-driven question, not a graph traversal.

Net finding: Q1 is not binary infeasible. It is feasible minus segmental duplications, with an overlap-completeness caveat. So the decision was not "seven or six" but how to handle the segmental-dup gap.

Chosen (Option A): keep Q1 at seven. Re-scope Q1's v1 required evidence to the four reachable sources plus the Variation Viewer link. Move segmental duplications to the fast-follow set, added later with a UCSC integration. Cap holds at seven.

Rationale: Q1 still clears the moat bar (provenance pass, deterministic at a fixed data state, cannot-just-Google high) and still covers the coordinate-keyed gene-variant-literature wedge. Four of five evidence sources are reachable and citable now; one unreachable sub-source should not sink an otherwise-strong must-pass. This matches the assemble-the-reachable-cited-evidence principle and v1 minimalism (no new non-NCBI source in the PoC build).

Two items flagged for Phase 4 Step 4.0 verification, not resolved here:

1. Interval-overlap semantics: ESearch range-filters by an anchor position, which can miss a large SV that spans the query window (starts before, ends after). True interval overlap is not a documented native operator. Region filtering works; completeness for large SVs needs empirical confirmation.
2. UCSC segmental-duplication source design (the fast-follow integration).

Considered and rejected: drop Q1 whole to fast-follow and lock v1 at six (segmental dups are diagnostically load-bearing for CNV interpretation, but four reachable sources already make Q1 a strong assembled-evidence answer); add a UCSC genomicSuperDups source now (expands v1 build scope beyond the NCBI three-layer set, against v1 minimalism).

Logged to DECISIONS.md.

### Decision: the coverage metric (PoC, diagnostic only)

Defined the coverage metric that pairs with the moat test. It answers the orthogonal question: of the graph's concept and predicate space, how much does our eval actually exercise? The moat test measures depth on chosen questions; coverage measures breadth against what exists. This is the Step 1.12 guard: a 100 percent CQ pass rate can hide large concept incompleteness (one cited study passed 100 percent while touching only 14 percent of a domain's concepts).

First design choice: role. Chosen (Monideep, PoC-appropriate): a pure diagnostic. It reports blind spots but never blocks shipping. Rejected: a soft gate with a coverage floor that triggers review. Reason: the moat set is engineered to be narrow and cross-database-biased, so by construction it scores low on breadth; gating a deliberately narrow set on breadth contradicts its own design and would pressure us to pad the set with questions that dilute the wedge.

Definition:

- Denominator: the deployed graph's enumerable schema. 11 vertex labels and 14 edge labels, per section D and E of the knowledge-graph reference. Drop `NamedThing` from the concept denominator (it is dangling-endpoint merger cruft, not a real concept), giving 10 concepts and 14 predicates.
- Numerator: distinct concepts and predicates the CQ set exercises. Static hand-mapping now; replaced by dynamic instrumentation once the agent runs and its Cypher is observable.
- Two ratios reported separately: concept coverage and predicate coverage.
- Secondary, qualitative: a Layer 2 API-reach checklist (which NCBI databases beyond the graph the set touches), reported as a list, not a ratio, because the API universe is not cleanly enumerable.

First-pass hand-mapping of the locked seven (confirmed with Monideep):

| Graph concept | Touched by |
|---|---|
| Gene | Q1, Q3, Q4 |
| SequenceVariant | Q1, Q3, Q4 |
| Disease | Q1, Q3, Q4 |
| Article | Q3, Q4, Q8 |
| OrganismTaxon | Q5, Q6 (entity resolution only) |
| PhenotypicFeature | Q4, if it surfaces phenotypes (uncertain) |

| Graph predicate | Touched by |
|---|---|
| is_sequence_variant_of | Q1, Q3, Q4 |
| gene_associated_with_condition | Q1, Q3, Q4 |
| mentioned_in | Q3, Q4, Q8 |
| has_phenotype | Q4 (uncertain) |

Result: concept coverage about 5 of 10 (~50%), predicate coverage about 3 of 14 (~21%). Untouched predicates: `has_mesh_annotation`, `in_taxon`, `actively_involved_in`, `participates_in`, `located_in`, `orthologous_to`, `cited_in`, `subclass_of`, `close_match`, `exact_match`. That is the GO-annotation, taxonomy, orthology, MeSH, citation, and ontology-structure capability of the graph, exercised by zero of the seven. The metric reproduces the Step 1.12 warning concretely.

Reframe (important): low graph coverage here is by design, not a defect. Four of the seven (Q5, Q6, Q8, Q10) are Layer 2 dominant and barely touch the graph; the moat set's real breadth is cross-database reach into roughly 9 API databases outside the graph (dbVar, OMIM, GTR, Pathogen Detection, SRA, BioProject, GEO, Assembly, PubChem). So the metric's job is not to gate v1. It guides set growth: as the set expands past the seven, coverage shows whether new questions broaden into untouched capabilities or just pile onto the same three predicates.

Logged to DECISIONS.md.

### Discussion: does a seven-question set limit what the system answers?

Monideep pushed on the obvious worry: if v1 has seven competency questions, does the system only answer seven things?

Clarified, because it is the crux: the seven are the eval gate, not the menu. They are the seven things we test to decide v1 is good enough to ship, not the seven things the system can answer. The system is a general agent: any question runs through Guardrail, Think, Plan, Act, Write and is answered by whatever the three layers support. It does not pattern-match against seven templates and refuse the rest. This restates the already-locked distinction (moat set versus full query set).

Analogy: the seven are a driving test, not a list of roads you are allowed to drive. Pass a few hard maneuvers and we trust you to drive anywhere.

Why only seven for the eval: real evaluation is expensive (each question needs a known-good answer, pinned fixtures, provenance checks, pass/fail criteria), so you pick the hardest, most differentiating set. If the seven hardest cross-database questions pass, the easy single-source long tail is covered by construction.

The honest risk, named: seven is a deliberately narrow eval. Passing it proves the wedge on documented cases, not general robustness. Two things protect everything outside the seven:

1. Cite-or-refuse at runtime, on every answer. An untested query cannot silently hallucinate: the agent grounds the answer in a real cited record or returns "I could not find information on this" and stops. The long tail is protected by the same gate as the seven.
2. The feedback loop (Step 2.5). Seven is the start, not the ceiling. Real interactions generate new competency questions that grow the eval set toward what people actually ask.

This framing is also why the old Tier 2 and Tier 3 are an expansion pool, not discards, and it directly settles the disposition depth (below).

### Decision: Tier 2/3 disposition rule now, full re-score deferred

Chosen (Monideep): define the disposition rule at the band level now, defer the full per-question re-score to set-expansion time.

Rule:

- Old Tier 2 (28): the expansion candidate pool. Each is scored against the moat bar (the two gates plus the empirical cannot-just-Google test) when the set grows past the moat seven. High joins Tier 1, partial becomes the Tier 2 should-pass set, none is handled but outside the moat eval set.
- Old Tier 3 (27): split by why it was parked.
  - Compute-tool questions (BLAST, VCF, similarity): fast-follow set (already Q2, Q7, Q9, plus the seg-dup enrichment for Q1).
  - Clinical-verdict questions (ACMG classification, prioritization, diagnosis, treatment): fail the assemble-not-classify boundary. Either reframed to evidence-assembly (as Q1 and Q2 were) or they stay out.
  - Single-source fetches (score none on cannot-just-Google): handled but outside the moat eval set.

Rejected: re-score all 55 individually now. cannot-just-Google needs an empirical external test per question, not cheaply runnable at planning scale, and Tier 2/3 do not gate v1. Attack the constraint: lock the rule now, run the full per-question re-score when the set actually expands.

Logged to DECISIONS.md. Step 2.3 is now complete.

## Step 2.4: the offline eval gate

Working mode note: to finish Phase 2 and push into Phase 3 in one day, we shifted to a faster drafting mode. Claude drives the drafting, batches the small calls, and surfaces only genuine forks. Monideep reviews in chunks.

### Decision: the offline eval gate

The 8-point rubric from `02_Tier1_eval_spec.md` holds and matches the locked architecture. It already encodes assemble-not-classify (rendering a classification when it only assembled evidence is a listed fail) and graceful degradation (hit all required databases or explain the unavailable ones). It needed abstain-scoring added and wiring to the eval-harness outcome model.

Design (confirmed with Monideep):

- Two scoring layers compose, they do not compete. The rubric grades a single run into one outcome: pass (score >= 13 of 16, no hard-fail), fail (any hard-fail, or score < 13), or abstain (returned the refusal string). eval-harness then aggregates those per-run outcomes across k samples with pass@k and pass^k. The rubric is how one run is judged; pass@k and pass^k are how many runs must pass.
- Hard-fails are absolute, checked on every run: provenance = 0 (an uncited claim), safety/limits = 0 on a clinical or pathogenicity question (rendered a verdict), or missing assembly/version context on a coordinate or sequence question. Cite-or-refuse lives here: zero retrieval plus a correct refusal scores as pass, not fail.
- Targets for a must-pass moat question (two levels): the hard-fails must hold on every run (pass^k = 100%, no fabrication and no verdict ever); the 13/16 quality score uses pass@3 as the floor (it can produce the cited answer within 3 tries) and pass^3 >= 90% as the reliability target (it does so consistently). A fabrication is never acceptable; quality is high but not required to be perfect. This matches a biomedical setting where a confident wrong answer is worse than no answer.
- Determinism via pinned fixtures, with a freshness-window allowance for the live-API questions.
- The moat seven are the initial offline eval set; the Phase 4 golden 50 is the expansion.

Eval-spec open decisions, resolved by what we already locked:

- ACMG classification in scope? No, evidence assembly only.
- Live BLAST/SRA sequence search in scope? No, fast-follow with fixtures.
- dbGaP controlled-access flows in Tier 1? No, the seven are public-data.
- Determinism source? Pinned fixtures plus a freshness window.
- Who signs off the expected answers for clinical questions? A real gap: the golden fixtures for the moat seven need a domain sign-off. Flagged as a Phase 4 process item, not closable in planning.

Logged to DECISIONS.md.

## Step 2.5: the online feedback loop

### Decision: the five-stage loop and v1 scope

The loop turns real usage into better routing. Phase 0 already fixed the promotion mechanism (few-shot routing examples, not a classifier and not fine-tuning), so the loop's output is new few-shot examples and new eval cases, nothing heavier.

Five stages:

1. Capture. Every interaction is traced and analytics-logged: the query, the agent's route and plan, tools called, the answer, its citations, the rubric outcome, any abstain or cite-or-refuse miss, the coverage instrumentation (which concepts and predicates the run hit), and explicit user feedback.
2. Mine and cluster. Periodically cluster captured queries by intent and surface three signals: queries the routing handled poorly (low score, wrong route, or abstained when a source existed), queries hitting untouched coverage areas, and moat wins worth reinforcing.
3. Review, semi-automated. An automated pass proposes deduped candidate CQs; a human approves before anything is promoted, because changing routing is a behavior change and the security rules require a human gate.
4. Trigger rule. A cluster that recurs above a frequency threshold, passes the moat bar, and is not already covered becomes a candidate new CQ. A cluster matching an existing CQ with new phrasings reinforces it (a few-shot variant or a re-rank signal). This is where the deferred moat signals, learn-from-the-system and loop-human-behavior, re-enter as re-ranking inputs.
5. Promote. An approved CQ becomes a few-shot routing example in the orchestrator and a new eval case in the offline set, human-approved and provenance-gated.

The loop closes: the offline gate (2.4) sets the bar, the online loop (2.5) grows the CQ set from real usage, and new CQs re-enter both the offline eval set and the orchestrator routing. This is the start-small-at-seven, prove-the-loop, expand mechanism made concrete.

v1 scope (chosen): ship stages 1, 3, and 5 with a human in the loop (capture everything, a lightweight manual review ritual, hand-promotion). Defer stage 2 (automated mining, clustering, auto-proposal) to a fast-follow, built once enough data is captured to cluster. Capture is cheap and is the raw material; a human turns the loop immediately; the expensive automation waits for data.

### Decision: data storage and where the LLM-judge sits

Two design questions Monideep raised.

Storage, split by what each store is good at:

- PostgreSQL (already in the stack for user data): the loop's durable system-of-record. An `interactions` table (query, normalized entities, route, rubric outcome, citations, coverage tags, user feedback, `trace_id`) and a `cq_candidates` table (proposed and promoted CQs with few-shot examples and provenance). The human review reads from here; promoted CQs live here.
- LangSmith: the raw per-run traces (hop-by-hop, tool returns, tier outputs), linked to a Postgres row by `trace_id` and consumed by the graders.
- PostHog: behavioral analytics aggregates (volume, feedback clicks, abstain rate, follow-up funnel), feeding the frequency threshold and the loop-human-behavior signal.

Postgres is the owned source of truth, not LangSmith, so the promotion pipeline does not depend on a third-party tracing tool's API or retention. Privacy, detail in Phase 4: PII minimization, scoped access, a retention policy, and provenance on every promoted CQ. Never store secrets. Biomedical queries can carry sensitive context (Q2 is a suspected-patient scenario).

Where the LLM-judge sits, relative to the human: always a filter upstream of the human, never the final say after. The human is the terminal gate on any promotion, because promotion changes routing and the security rule requires a human to approve behavior changes. Three appearances:

1. Offline eval grader (v1): code graders first (deterministic), then the LLM-judge (semantic), then a human only on flagged edge cases.
2. Online candidate pre-screen (deferred to the fast-follow): drafts candidate CQs with a rationale for the human to approve.
3. Model-bench scorer for tier selection: a separate use of the same technique.

In v1 the online loop has no LLM-judge (stage 2 is deferred, so review is manual); the offline gate does have one, as a grader before the human.

Logged to DECISIONS.md. Step 2.5 is complete, and all Phase 2 design steps (2.1 to 2.5) are done. Next: assemble the evaluation playbook.

## Phase 2 deliverable: the evaluation playbook

Assembled `requirements/Evaluation_playbook.md`, the Phase 2 output. It consolidates everything decided in Phase 2 into a standing, living reference: the moat test, the full competency-question set (the v1 seven with wedge types and personas, the fast-follow set, the expansion pool and its disposition rule), the coverage metric, the offline evaluation gate, model selection, and the online feedback loop, with two mermaid diagrams (the moat bar and the closing loop) and a Phase 4 open-items list.

Graded by a fresh-context agent against a decision-fidelity, CQ-accuracy, completeness, coherence, and writing-style checklist. Result: 5 of 5 criteria pass. Two minor polish issues were fixed: the predicate-coverage arithmetic now names `has_phenotype` as the borderline fourteenth predicate so the count closes, and the online loop's stage 3 now states explicitly that v1 review is manual because the stage 2 auto-proposal is deferred.

The playbook is the Phase 2 synthesis and deliverable. It, plus this session doc and DECISIONS.md, is the input to Phase 3 (the PRD); no separate Phase 2 synthesis document is created, since the playbook already organizes the decisions by topic for the downstream phase.

### Refinement: the moat bar's general-tool test (raised after the playbook draft)

Monideep flagged that the moat's ranking criterion should test against modern LLMs and answer engines (Claude, GPT, Gemini, Perplexity), not just Google, and asked whether we had considered them.

Answer: the written criterion nominally said "a general search engine or AI tool," so LLMs were in scope in principle. But two real gaps: the name undersold it, and the test rigor was underspecified.

Refined (confirmed with Monideep):

- Renamed the dimension from "cannot just Google" to "no general-tool equivalent."
- The empirical test runs each candidate against a panel of the strongest general tools: a frontier chat LLM (Claude, GPT, or Gemini), an answer engine with retrieval (Perplexity), and plain web search. The question passes only if none produces the correct answer with verifiable citations across the required databases.
- The pass condition is grounding, not fluency: a fluent, uncited, or hallucinated-citation answer does not count as the general tool producing it. General LLMs hallucinate citations and cannot ground across NCBI databases with resolvable source records, which is exactly System 3's differentiation.

Why it matters: frontier LLMs and answer engines are far stronger than a Google search page. Testing only against Google would falsely pass questions a strong LLM already handles and inflate the moat. Testing against the strongest tools, scored on verifiable grounding, keeps the bar honest against 2026 tools. The seven still pass. The playbook was updated and the refinement logged to DECISIONS.md.

Phase 2 is complete. Next is Phase 3, the PRD.
