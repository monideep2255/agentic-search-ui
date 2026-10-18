# Workstream W2 plan: understanding the question and the graph search

Scout `think_and_search`, 2026-10-05. Read-only. Cards: 87, 48, 56, 35, 4, 15, 91, 74, 16, 33, 77, 37, 38, 32. Cards 87 and 91 use the 2026-10-05 diagnoses (`testing/Developer/reports/2026-10-05_card87/diagnosis.md`, `testing/Developer/reports/2026-10-05_cards91_93/diagnosis.md`). Paths are relative to `<repo-root>`; code is under `src/system_03_search_agent/`.

## Table of contents

- [Live checks made](#live-checks-made)
- [Card table](#card-table)
- [Root causes shared by several cards](#root-causes-shared-by-several-cards)
- [Suggested order](#suggested-order)
- [Owner decisions](#owner-decisions)
- [What I did not check](#what-i-did-not-check)

## Live checks made

Five guest questions on develop, 2026-10-05, script `testing/Developer/reports/2026-10-05_board_plan/scripts_w2/live_w2.py`. No tokens saved.

| Question | What happened | Cards |
|---|---|---|
| What is rs334 and what condition is it associated with? | outcome ask, 38.7 s. Lists rs334348, rs334353, rs334773 as literature variant records beside rs334; the rs334 record is named by its clinical significance list | 37 |
| How do birds fly? | outcome answer, 12.7 s. A list of five loosely matched PubMed titles, no question back | 48 |
| Find SRA runs of SARS-CoV-2 ... | outcome ask, 16.3 s. Think resolved "SARS" three times as a disease, the answer is one MedGen record "SARS Coronavirus Protease Pathway", no SRA records | 56 |
| Which Mycobacterium tuberculosis genome assemblies are available ... | refuse, 12.8 s, no tool run. Reply: "which gene, variant or condition do you mean?" | 16 (G-036) |
| For PMID 11237011, what sequence data ... | refuse, 9.7 s. Only a `cypher_query` was planned and it errored: "One of my searches did not finish" | 74, 33 |

## Card table

| Card and feature in plain words | Impact on the person | Status today | Root cause | Shared cause | Code it touches | Size | Depends on, blocks | Needs the owner |
|---|---|---|---|---|---|---|---|---|
| 87. `recent-onset diabetes treatment` is asked "what would you like to know" and no search runs, though query 84 says answer it | Blocks an answer (a clarifying question instead of papers) | Still happens: 5 of 6 asked back, 1 of 6 searched after the writer's choices failed (2026-10-05 diagnosis) | Known: the short-question rule (3 words or fewer) sends the text to the `think.ask_back` decision; Jev reads "X treatment" as a bare noun phrase. `core/graph.py:3335` (`_MAX_CLARIFY_TRIGGER_WORDS`), `:959-979` (`_ASK_BACK`), `:3711-3729` | Cause C: 48, and the wrong question G-036 gets (16) | `core/graph.py` `_ASK_BACK` spec, `think_node` short-question path | S for the wording; the fix is only proven by five or more live runs on both sides, and Jev may not move on wording | Blocks 48 (same decision, opposite direction). Do before 48 | Yes. Query 84 (answer) and query 76 (`reflux disease` asks back) disagree about a subject plus a request noun. Recommend: a subject plus the kind of thing wanted counts as a request; amend query 76's note to say so. If Jev does not move, accept the ask-back and edit query 84 |
| 48. A fuzzy question such as "How do birds fly?" should ask which aspect, not list loosely matched papers | Wrong or degraded answer (confident list beside the question's substance) | Still happens: live run above returned five bird-and-fly titles, outcome answer. Measured by F-8.6-RA04 | Known: nothing asks. The ask-back only runs for 3 words or fewer; a longer fuzzy question passes the guard (allowlist or Jev on topic) and `ncbi_efetch` keyword-matches. `core/graph.py:3711` and the `think_node` path | Cause C (same decision as 87); cause E for the allowlist half (35); card 52 (next-step offers) sits beside it | `core/graph.py` think_node, `_ASK_BACK`, a new decision for a question with a topic but no biomedical entity; `harness/decide.py` only if a new decision spec needs registering | M | Depends on 87 (do not widen ask-back while it over-fires). Blocks nothing | Yes, one question: what counts as "fuzzy"? Recommend: Jev decides whether the question names a biomedical thing a search could bind (entity found or not), never a word list |
| 56. SARS-CoV-2 SRA question refused in some runs: subject not recognised, no search | Blocks an answer (some runs); degraded when it answers (live run: a SARS disease record, no SRA runs) | Still happens, intermittent. Golden G-005: 3 of 3 (2026-09-25), 1 of 3 (8.6 follow-up), 3 of 3 (2026-09-29, but graph layer 0 rows, answered by layers 2 and 3). Live today: answered with the wrong entity | Known in outline: Think's entity extraction knows genes, diseases, variants and PMIDs; an organism is returned as nothing or as a disease called "SARS". Run to run variance is the model's. `core/graph.py` entity resolution (`_resolve_entities`, around 2870-3090, 3921) and the Think prompt. Exact reason for the run to run flip not measured | Cause A: 16 (G-036, G-005), 33 (G-004) | `core/graph.py` think_node entity step, plan_node tool choice; `tools/ncbi_efetch_schemas.py` if an SRA search needs a field | M for the diagnosis of the variance, then L to add an organism entity type | Blocks 16 and 33 (G-004). Pairs with A below | No |
| 35. An off-topic follow-up with a word like "cell" or "study" still gets through | Wrong or degraded answer (an off-topic list) | Unknown today, not retested. Recorded as present on develop before phase 8.2 (F-8.2-V01), plus F-8.6-RA03: when the allowlist admits, no relevancy decision is asked | Known: `guardrail/prefilter.py` `clears_biomedical_allowlist` admits on a single word and skips the Jev relevancy decision (`guardrail/` node, `core/graph.py` guardrail_node). A word list deciding, against the "no hardcoded decisions" rule | Cause E: 48 | `guardrail/prefilter.py`, guardrail_node in `core/graph.py` | S to M | Best done with 48 (both are "is this a biomedical question"). No hard dependency | Yes, small: should the relevancy decision always run after an answered question, at the cost of one extra fast call? Recommend yes |
| 4. Tell the reader when the system wrote its own search rather than using a checked one | Screen or wording only (honesty about an unchecked search) | Still open. `CypherQueryOutput.template` is None exactly when drafted and `_cypher_output_to_structured_fields` (`core/graph.py:6711`) drops it; no "drafted" note exists anywhere in `src/` | Known: that dropped field | Cause B: closing the model path (15) makes this moot | `core/graph.py:6711`, `synthesis/refuse.py` (note text), `tools/cypher_query.py` | S | If 15 is done, close 4 as superseded. Otherwise do 4 first as a stopgap | Yes, with 15 (one question covers both) |
| 15. Close the remaining path where the system writes its own graph search, or ask instead | Wrong or degraded answer (a drafted query can return one count for a hundred rows, or fail) | Still open. The model path remains for aggregate questions with no shape, and for Disease or Article anchors on single and multi-hop classes (`tools/cypher_templates.py:711-788`) | Known: `select_template` returns None, then `cypher_query.py:1967-1972` generates and validates, one repair retry | Cause B: 4, 74, 91, 32, 33 (G-006) | `tools/cypher_templates.py` `select_template`, `tools/cypher_query.py`, `tools/cypher_validator.py` | L | Blocks 74, 91, and makes 4 and 32 moot. Count questions (G-034) must keep a path; the golden gate (at least 101 of 150) applies | Yes. Recommend: no model-written Cypher except true count questions; everything else gets the record template, a Layer 2 call, or a plain "I can't search that" naming what to type |
| 91. Background search note names neither which search nor why (query 25) | Screen or wording only for rate limits; wrong or degraded when the graph search was drafted and rejected | Still happens, 3 of 7 live runs (1 drafted Cypher rejected twice, 2 NCBI rate limits). Query 24 did not reproduce (5 of 5 clean), so the card title is wrong | Known: cause A `select_template` returns None for class `aggregate` on a Gene anchor, validator rejects the model Cypher (`cypher_templates.py:788`, `cypher_validator.py:1317-1330`). Cause B rate limit `tools/ncbi_transport.py:559`, note text `synthesis/refuse.py:111`, `core/graph.py:8091-8105`, `:9175` | Cause B (drafted path) and cause D (silent or vague failure note): 15, 74, 77 | `tools/cypher_templates.py:788`; then `core/graph.py` `_build_failed_search_note` | S for the template branch; S for the wording | Template branch first; wording after. Listing under 15 | No (diagnosis recommendation already stands) |
| 74. G-006, one PubMed paper's linked data, finds nothing, its graph search failing | Blocks an answer | Still happens. Golden 2026-09-29: 0 of 3; live today: one `cypher_query` planned, errored in 9.7 s. Earlier timeouts at 30 s | Known in part: the question gives an Article anchor, class multi_hop, no shape matches, so the model path runs (`cypher_templates.py:777-780` keeps Article anchors on it on purpose). Plan then plans only `cypher_query`, no Layer 2. Why the draft times out or errors is not measured | Cause B (15) and cause D (plan with one call) | `tools/cypher_templates.py` Article hops (`_HOPS`, around 268-279), `core/graph.py` plan_node breadth for an Article anchor | M | Depends on 15's decision. A Layer 2 link call for a PMID (elink) gives an answer without the graph | No |
| 16. Three golden questions get nothing from the graph: G-005, G-022, G-036 | Blocks an answer (G-036) or degraded | Partly stale. G-022 answered 3 of 3 on 2026-09-29 with 12 to 13 graph rows (fixed). G-005 answers 3 of 3 on 2026-09-29 but through layers 2 and 3 only. G-036 still refuses (live today, no tool run, wrong "which gene" question) | Known for G-036: no entity resolved, the fallback message names gene, variant or condition. Same as 56 | Cause A: 56, 33 (G-004) | Same as 56, plus the fallback text in `core/graph.py` plan or think | M, inside 56's work | Depends on 56. Narrow the card to G-036 and G-005 | No |
| 33. G-004 (Salmonella isolate) runs no search and G-006 finds nothing | Blocks an answer | Still happens for both. G-004: 0 of 3 on 2026-09-29, Think asked the person which resistance gene, no tool. G-006: see 74 | G-004: no isolate or organism entity, so `ask` path; the gene prompt is the Think default. G-006: as 74 | Cause A (G-004) and cause B (G-006) | As 56 and 74 | M | Split: G-004 follows 56, G-006 is card 74 | Yes, small: G-004 asks for a resistance gene because the question has no isolate id. Is asking right (it is honest) or should it search organism-level isolates? Recommend: answer with what is findable and say an isolate accession would narrow it |
| 77. When the MedGen name lookup fails or times out, "Any trials for GERD?" searches no literature or trials and says nothing | Blocks an answer (a missed layer is read as "no trials") | Still open as of the code read (`core/graph.py` `_disease_search_text`, F-53-A11 repro: 8 planned calls become 1). Not reproduced live: the MedGen lookup failure is intermittent | Known: `_disease_search_text` returns None on a MedGen error, `plan_node` then plans the single graph call (`core/graph.py:5715-5738`, `:4602`). No `failed_searches` entry because no call was tried | Cause D: 91 (wording), 74 (G-006 plans one call) | `core/graph.py` `_disease_search_text`, `plan_node`, `_build_breadth_calls`, `_build_failed_search_note` | S to M | Order after 91's wording change (same note). Golden gate blocks it | No. Recommend: plan breadth from the disease name the question already carries when MedGen fails; add the "a lookup failed" note |
| 37. rs334 listed with rs334348, rs334353, rs334773 as if they were rs334 | Wrong or degraded answer (a confident wrong record) | Still happens (live today, 2026-10-05) | Known: LitVar2 near misses kept by design, nothing downstream drops them. `tools/litvar2_lookup.py` (F-3.3-A-01), assembly in `core/graph.py` | Cause F: 38. Planned as T-8.9-04 | `tools/litvar2_lookup.py`, `core/graph.py` findings assembly | S | Phase 8.9 (planned, not opened: `tracker/phase_8.9.md`). Do not wait if 8.9 stays closed; a small exact-match filter ships alone | Yes: confirm phase 8.9 opens now. Recommend yes, rs334 is a wrong record a person trusts |
| 38. Answers list records that cannot answer the question: orthologs with no species, papers with no title, isolates with no gene | Wrong or degraded answer | Still happens, planned only. The graph has paper titles and the harness strips them (T-8.9-01); ortholog organism needs the template changed (T-8.9-02) | Known: `tools/cypher_templates.py` `gene_orthologs_one` returns no organism; findings pipeline `synthesis/findings.py` drops fields | Cause F: 37 | `tools/cypher_templates.py`, `core/graph.py` write_node, new `synthesis/article_titles.py`, `synthesis/findings.py` | L as written in `tracker/phase_8.9.md` (seven tickets) | Same as 37. Touches `cypher_templates.py` `_HOPS` and `write_node`, so sequence with 15 and 32 | Same decision as 37 |
| 32. A graph search column named `clinical_features` would be read as MedGen's | Not seen by a user (it needs the model to name an alias so; never reached live) | Unknown, probably cannot happen on the template path; possible on the model path | Known: `synthesis/findings.py` keys `CLINICAL_FEATURES_FIELD` on the field name alone, not the tool | Cause B: closed in effect by 15 | `synthesis/findings.py:167, 1794-1864`, `cypher_provenance._shape_derived_value` | S | After 15. If 15 is delayed, key the check on tool `ncbi_efetch` (one line plus test) | No. It moves to `testing/Future.md` per the board's own rule (a person would not notice it) |

## Root causes shared by several cards

- Cause A: entity resolution only knows genes, diseases, variants and PMIDs. An organism, an isolate or an accession gives no entity or the wrong one, so no search runs or the wrong one runs.
  - Cards: 56 (SARS-CoV-2 read as the disease "SARS"), 16 (G-036, G-005), 33 (G-004).
  - One fix: Jev (the classifier) classes the subject type, and code resolves an organism against the taxonomy source before binding; plan then routes it to Layer 2 SRA or Datasets. Also change the "which gene, variant or condition" fallback so it names the missing type. No word list.
  - Files: `core/graph.py` entity resolution and plan, Think prompt.
- Cause B: the model-written Cypher path. When no template fits, the plan-tier model writes Cypher; the validator rejects it, or it times out, or it returns a different shape each run.
  - Cards: 15, 4, 74, 91 (cause A of its diagnosis), 32, 33 (G-006).
  - One fix: card 15, no model-written Cypher except true count questions. The `aggregate` Gene anchor branch (`cypher_templates.py:788`) is the smallest first step and is already recommended in the 91 diagnosis. Closing it makes 4 and 32 moot.
  - Files: `tools/cypher_templates.py` `select_template`, `tools/cypher_query.py`, `tools/cypher_validator.py`.
- Cause C: one ask-back decision, `think.ask_back`, deciding when to ask. It over-fires on a short subject plus a request (87) and never fires on a longer fuzzy question (48).
  - Cards: 87, 48, and the guard half of 35.
  - One design: decide both inside one pass so 87 and 48 cannot undo each other. Jev decides "names a request, names a searchable thing, or neither".
  - Files: `core/graph.py` `_ASK_BACK` and the short-question branch.
- Cause D: a plan that depends on one lookup, and failure notes that are silent or vague.
  - Cards: 77 (MedGen fails, one call planned, no note), 91 (the note names neither which nor why), 74 (G-006 plans one graph call only).
  - One fix: when a lookup fails, plan the breadth from the question's own text and name what failed in the note.
  - Files: `core/graph.py` `_disease_search_text`, `plan_node`, `_build_failed_search_note`.
- Cause E: the guard admits by a word list and then skips the relevancy decision. Cards 35, 48 (via F-8.6-RA04). Fix: always ask Jev's relevancy decision after an answered question. Files: `guardrail/prefilter.py`, guardrail node.
- Cause F: the findings pipeline drops or never asks for the field the question needs. Cards 37 and 38, already planned as phase 8.9. Files: `tools/litvar2_lookup.py`, `tools/cypher_templates.py`, `synthesis/findings.py`, `core/graph.py` write_node.

Two cards touching the same function must go in sequence:

| Function | Cards |
|---|---|
| `select_template` and `_HOPS` in `tools/cypher_templates.py` | 15, 74, 91, 38 |
| `_build_failed_search_note` and `plan_node` in `core/graph.py` | 91, 77, 74 |
| `_ASK_BACK` and the short-question branch in `core/graph.py` | 87, 48 |
| `write_node` in `core/graph.py` | 4, 38, 37 |
| `synthesis/findings.py` | 32, 38 |

## Suggested order

1. Card 91, template branch for `aggregate` Gene anchors. Smallest change, already diagnosed, closes the one failure pinned to code, and starts card 15.
2. Card 87. A wording change on one decision, a person feels it first (a clarifying question instead of papers), and it must precede 48.
3. Card 77 and card 91's wording, together. One note and one plan function; fixes a silent missed layer.
4. Card 15 (with 4 and 32 closed as moot), starting with Article anchors for card 74. Removes the whole class of drafted-Cypher failures.
5. Card 74 (G-006) after 15, adding a Layer 2 link call for a PMID so the question answers even if the graph does not.
6. Cards 37 then 38 (phase 8.9). A confident wrong record is worse than a missing one; the rs334 filter is small and can go first.
7. Card 56, then 16 and the G-004 half of 33. Largest unknown (variance of entity extraction), so diagnose first; it needs the organism entity type.
8. Card 48 with card 35. After 87 has settled, so the ask-back is not widened while it over-fires.

## Owner decisions

1. Card 87: should a subject plus a request noun (`recent-onset diabetes treatment`) be answered? Recommend yes; amend query 76's expectation.
2. Card 15 and 4: no model-written Cypher except for count questions, with a plain "type this instead" when nothing fits? Recommend yes.
3. Card 48 and 35: Jev decides what is fuzzy, and the relevancy decision always runs after an answered question? Recommend yes.
4. Cards 37 and 38: open phase 8.9 now? Recommend yes, with the rs334 filter first.
5. Card 33 (G-004): ask for a resistance gene, or answer with what is findable and say an accession would narrow it? Recommend the second.

## What I did not check

- Why the G-006 draft errors in 9.7 s today but timed out at 30 s on 2026-09-29. I read the events, not the Railway logs.
- The cause of run to run variance in Think's entity extraction for card 56; no repeated runs, one live run only.
- Card 77 live: MedGen failure is intermittent; I read the code and the adversary's repro only.
- Card 35 and card 32 were not retested; no live probe.
- G-022's present state beyond the 2026-09-29 golden row (3 of 3 answered).
- Jev's training or whether a criteria wording change flips the classifier on card 87 (not tried, as in the diagnosis).
- Card 91's "which call failed" for runner A's own two runs.
- Cards 93, 88, 89 and 86 only as references; I did not read their rows.
