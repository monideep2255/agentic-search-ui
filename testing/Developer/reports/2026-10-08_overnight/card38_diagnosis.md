# Card 38 diagnosis: answers list records that cannot answer the question

Read on develop at `c916cfa3`, 2026-10-08. Code reading, saved run files and phase 8.9's recorded read-only probes; no live run, no model call.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

| Shape | Status | Evidence |
|---|---|---|
| TP53's orthologs carry no species (G-016) | Still happens | Golden run of 2026-09-29, G-016 passes 1 and 2: gene-page citations 41 on field `name`, 1 on `symbol`, none on `organism`. No commit since touches the ortholog template |
| CFTR's papers carry no title (G-021) | Still happens | Same run, G-021, all 3 passes: 54 PubMed-page citations on field `curie`, 5 on `title`. `_sanitized_citeable_row` is unchanged on develop |
| The ESBL isolates do not say which gene each carries (G-035) | Already fixed on screen by card 94 (#165, merge `4ee38111`; #174, merge `e8a8f91d`) | Test query 33 on develop, 2026-10-05: a table "Isolates and their AMR genes" with each isolate's full gene list, both runs passed (`testing/Developer/reports/2026-10-05_final_test_queries/results.md`, item 1). The writer is still given only each isolate's strain name (golden run: 20 Pathogen Detection citations on field `name` per pass), so a written sentence cannot name a gene per isolate; the table does |

The card's own open question is answered: the graph has paper titles and organism links, and the harness either strips them or never asks for them (`testing/Developer/reports/2026-09-25_harness_review/product_harness.md`, "What the writer model is actually given").

## What a person sees

- "What are the known orthologs of TP53 in other species?": about forty rows that all read "tumor protein p53", each linked to a gene page, and no species anywhere. The question asked which species.
- "Which papers in the graph mention the CFTR gene, and what do they cover?": a list of bare PubMed numbers such as "Article record PMID:10075921", and no titles. The person must open each one to learn what it is.
- "What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?": today a table of isolates with each one's genes. This part works.

## The cause

| Shape | Cause | Evidence |
|---|---|---|
| Orthologs | The ortholog template returns only the ortholog Gene vertex. A Gene vertex carries no organism: its keys are `agent_type, id, knowledge_level, name, source, source_url, xrefs`. The organism sits one hop away on `in_taxon`, which the template never walks | Template: `_HOPS[("Gene", "orthologs")]` and `_hop_template` (`src/system_03_search_agent/tools/cypher_templates.py:263`, `:581`). Phase 8.9 probe 1 (`tracker/phase_8.9.md`, "Premises and probes"): "591 of 591 TP53 orthologs have an `in_taxon` edge"; "Gene vertex property keys: ['agent_type', 'id', 'knowledge_level', 'name', 'source', 'source_url', 'xrefs']"; the candidate two-hop template took 5.1 s for 100 rows against 5.01 for today's |
| Papers | A graph Article's `name` is the PubMed title. It is treated as untrusted third-party text and quarantined: the row's `fields` are emptied before Write sees them, so the row is cited by its bare identifier. The guard-tier reader sees the titles, but its summary never becomes a citable value | `_UNTRUSTED_FREE_TEXT_NODE_TYPES` (`src/system_03_search_agent/core/graph.py:7337`), `_sanitized_citeable_row` (`:7382`), `_rows_for_citation` (`:7406`), applied in `_execute_planned_call` (`:8364` to `:8371`) |
| Isolates, writer side only | The isolate row's one finding is its strain name; the gene list rides in the table, not the prompt | One field per row: `synthesis/findings.py:587` to `:615`. Table: `synthesis/answer_layout.py:306`, `amr_genotypes` under "AMR genes" |

The quarantine is a security control and is right. The fix is to get titles from PubMed's own reading tool, not to lift the quarantine.

## The smallest fix

Phase 8.9 already specifies every step (`tracker/phase_8.9.md`). Ranked by what a person notices first:

| Step | What changes, in the person's words | Fence | Answer path | Dial | Size |
|---|---|---|---|---|---|
| 1, T-8.9-02 plus T-8.9-06 | TP53's orthologs list each species: "tumor protein p53 (Oryctolagus cuniculus)" at Plain language, an Organism column at Researcher | `tools/cypher_templates.py` (the single-gene ortholog template gains an `OPTIONAL MATCH` on `in_taxon` and a value fold), `tools/cypher_query.py` (write the fold onto `fields["organism"]`), `synthesis/answer_layout.py` (`record_label`, `plain_record_label`, `record_status_or_year`) | Yes | 2, runnable behaviour | M |
| 2, T-8.9-01 | CFTR's papers are listed by their titles, and the writer is given the titles | New `synthesis/article_titles.py` (titles read through `ncbi_efetch` PubMed EFetch, at most two requests of 50 PMIDs, joined by PMID); `core/graph.py`, the resolution block of `write_node` only; `synthesis/findings.py`, the title line in `build_synth_messages`. The quarantine functions stay byte-identical | Yes | 2, runnable behaviour | M |
| 3, T-8.9-03, optional | The written answer can name an ortholog's species | `synthesis/findings.py` `build_synth_findings` (companion finding for `Gene` row field `organism`), `core/graph.py` `_layer3_base_citation` | Yes | 2, runnable behaviour | S |

Isolates need no fix. If a written sentence naming each isolate's genes is wanted, it is one more row in T-8.9-03's companion table (row type `Pathogen Detection isolate`, field `amr_genotypes`); not proposed, since the table already answers.

None of the three is dial 3: no auth change, no event field (phase 8.9 adds nothing to the event contract), no `.claude/` edit, and the Article quarantine stays.

## Overlap with phase 8.7 and the guardrail

| Step | Phase 8.7 overlap | Guardrail overlap |
|---|---|---|
| 1 | Template half: none, `tools/` is not on 8.7's list. List half: yes, `synthesis/answer_layout.py` | None |
| 2 | Yes: `write_node` and `synthesis/findings.py` | None |
| 3 | Yes: `synthesis/findings.py` | None |

The template half of step 1 (T-8.9-02) can be built now. Its rows carry `organism` with nothing yet reading it, so it changes nothing a person sees until T-8.9-06 lands after 8.7.

## Needs the owner

No. Phase 8.9 is the owner's ordered work (decision of 2026-09-25, and D10 in `testing/Board_plan.md`), and its plan holds the cost (two EFetch calls inside the 20-call ceiling) and its own stop rule: if EFetch for 50 PMIDs takes more than 3 seconds at the median, the lead decides between EFetch and adding `title` to the PubMed ESummary allowlist (T-8.9-01, premise b). That is a lead decision with a `DECISIONS.md` row, not the owner's, unless it changes Section 6.2 of the locked specification.

## Test query

No existing query covers orthologs or a gene's papers in the graph. Two proposed entries, section 3. The numbers are provisional; the lead assigns the next free numbers when filing.

```markdown
### 114. A gene's orthologs name their species (card 38, G-016)

Queries to try:

- `What are the known orthologs of TP53 in other species?`: ask it once in Plain language and once in Researcher.

What you should see:

- Each ortholog listed with its species, for example "tumor protein p53 (Oryctolagus cuniculus)" in Plain language, and an Organism column in Researcher.
- Never forty rows that all read "tumor protein p53" with no species.
- One line saying how many orthologs the knowledge graph holds against how many are shown.
- Why it matters: the person asked which species carry the gene; a list of identical names answers nothing.

### 115. A gene's papers in the graph are named by their titles (card 38, G-021)

Queries to try:

- `Which papers in the graph mention the CFTR gene, and what do they cover?`

What you should see:

- Each paper listed by its title, linked to its PubMed page.
- Never a list of bare "Article record PMID:..." rows.
- Plain language and Researcher list the same papers.
- Why it matters: a paper's number tells a person nothing about what it covers; they would have to open every link to learn what the answer found.
```

The isolate half is covered by query 33.
