# Card 33 diagnosis: G-004 and G-006 stopped answering

Read on develop at `c916cfa3`, 2026-10-08. Code reading and saved run files only; no live run, no model call.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

| Half | Status | Evidence |
|---|---|---|
| G-006, data linked to PMID 11237011 | Already fixed on develop by card 74 (#172, merge `c1fc7040`), with card 15 step 1 (#171, merge `5ae4d4a1`) | The full golden question passed live on develop on 2026-10-05: `testing/Developer/reports/2026-10-05_final_test_queries/results.md`, item 5, 23.0 s, "I found 5 records, 2 research projects, 1 sequencing dataset and 5 genome assemblies related to PMID 11237011." Board row card 74 waits on the owner's retest, query 104 |
| G-004, a Salmonella isolate's SNP cluster, AMR genes and 5-SNP neighbours | Still happens, in a new form | Since card 56 (#173, #186) the question is asked back "Which kind of Salmonella record do you want?" instead of "which resistance gene". Still no search. Card 56's own report says so: `testing/Developer/reports/2026-10-05_wave3/card56.md`, live runs table, 3 of 3 |

The card's premise needs one correction. Neither question truly answered on 2026-09-22. The saved runs of that day show:

| Question | What the 2026-09-22 "answer" was | File |
|---|---|---|
| G-004 | "Found 1 gene record for AMR: alpha 2-HS glycoprotein [1], linked to 1 disease: Alopecia-intellectual disability syndrome 1". The word "AMR" was bound as a gene. A confident wrong record | `testing/Developer/reports/2026-09-22_10.3_consistency/raw/G-004_run1.json` and `_run2.json` |
| G-006 | "Found 1 article record for PMID 11237011: PMID:11237011 [1]." The paper itself, no linked data | same folder, `G-006_run2.json` and `_run3.json` |

So the golden count fell, but the product got more honest. G-004's refusal since 2026-09-25 replaced a wrong answer.

## What a person sees

- G-006 today: the sequence records, BioProjects, SRA run and assemblies NCBI links to the paper, each linked to its NCBI page, with "NCBI lists no linked GEO records for PMID 11237011." The question also asks to mark each link "direct, inferred, or absent". Absent kinds are stated; direct and inferred are not shown (observation in the same results file). Every ELink link is direct, so this is a wording gap, not a wrong record.
- G-004 today: a question back, "Which kind of Salmonella record do you want? For example Salmonella genome assemblies, Salmonella SRA sequencing runs, or Salmonella isolates in Pathogen Detection that carry a resistance gene family, such as ESBL or carbapenemase genes." The person already said which kind: one isolate's SNP cluster, its AMR genes and its neighbours. They cannot answer this question sensibly, and none of the offered options leads to what they asked.
- If the person then names an isolate by BioSample accession, they get its linked SRA runs and assemblies, not its SNP cluster or neighbours (see the cause, part 3).

## The cause

G-004, three parts:

1. The isolate shape fires and asks back. `parse_isolate_question` (`src/system_03_search_agent/core/isolate_search.py:325`) matches the isolate word, the organism "Salmonella" (`:106`) and the generic resistance word "AMR" (`_GENERIC_RESISTANCE`, `:217`). No gene family or gene token is present, so `IsolateQuestion.clarification` (`:284` to `:288`) returns `record_question(organism)` (`:236`). `think_node` publishes it (`src/system_03_search_agent/core/graph.py:4446` to `:4449`). Plan then selects no tool.
2. The question names no isolate. "For a Salmonella enterica isolate ... which isolates are within 5 SNPs of it" asks about one isolate the person never identified. No search can answer "it". Asking is right; asking for the kind of record is the wrong question. The right one is which isolate.
3. The capability behind the answer is not wired. The `pathogen_detection` tool has `isolate_lookup` (by BioSample accession) and `cluster_snp_neighbors` (by PDS cluster, `max_snp_distance` 5 by default) (`src/system_03_search_agent/tools/pathogen_detection_schemas.py:194` to `:225`). No planner calls either mode: a search of `src/system_03_search_agent/core/` for `isolate_lookup` and `cluster_snp_neighbors` finds nothing. A SAMN accession takes the accession path instead (`core/accession.py:214`, links to `sra` and `assembly`), and `parse_isolate_question` is skipped when an accession is found (`core/graph.py:4125` to `:4126`).

Side note: the golden row's `must_resolve` is `NCBITaxon:28901` (Salmonella enterica). The `ORGANISMS` table maps "salmonella" to the genus, taxid 590 (`isolate_search.py:106`). An answer would cite the genus page, so G-004 can never hit its must-cite Taxonomy link as written.

G-006: fixed by card 74. Plan asks the `plan.paper_links` decision when exactly one PubMed paper resolved (`core/graph.py:1049`, `:6589` to `:6603`) and plans ELink calls per target with summary follow-ups (`:6899`, `:8452` to `:8454`). Write states each empty kind and the count cut (`:9585` to `:9597`). The graph has no edge from a paper to its data (card 15's report, `testing/Developer/reports/2026-10-05_wave3/card15.md`), so the old graph-only plan could never answer.

## The smallest fix

G-006 needs no fix. Close its half of the card when query 104 passes the owner's retest.

G-004, two steps. Step 1 alone stops the wrong question back.

| Step | What changes, in the person's words | Fence | Answer path | Dial | Size |
|---|---|---|---|---|---|
| 1 | An isolate question that names an organism and no gene is asked which isolate it means, by its BioSample accession, with one example, and is also offered the gene-family search. "Which kind of record" is gone for this shape | `core/isolate_search.py`: `record_question` and `IsolateQuestion.clarification` only; test file `tests/system_03_search_agent/core/test_isolate_search.py` | Yes, the ask-back text | 1, copy | S |
| 2 | A named isolate gets its SNP cluster, its AMR genes and the isolates within 5 SNPs, each linked to Pathogen Detection | `core/graph.py` `think_node` (route a BioSample accession in an isolate question to the isolate lookup), `plan_node` (plan `isolate_lookup`), `act_node`'s follow-up step (plan `cluster_snp_neighbors` from the PDS id the lookup returns); `core/isolate_search.py` new `plan_lookup_calls`; Write's isolate table already exists | Yes | 2, runnable behaviour | M to L |

Step 1 is a fixed sentence keyed on the shape the parser already recognises, not a new word rule, so it stays inside "no hardcoded decisions". Whether the question asks about one isolate or many is still not read; step 1 offers both routes in one sentence.

Optional with step 1: map "Salmonella enterica" to taxid 28901 in `ORGANISMS`, verified live first as that table's docstring requires. S, dial 2.

## Overlap with phase 8.7 and the guardrail

| Step | Phase 8.7 overlap | Guardrail overlap |
|---|---|---|
| 1 | None. `core/isolate_search.py` is not in 8.7's list | None |
| 2 | Yes: `act_node` in `core/graph.py`, for the neighbours follow-up. `think_node` and `plan_node` are not on 8.7's list | None |

## Needs the owner

Yes, one design choice. D19 (`testing/Board_plan.md:225`) says "answer with what is findable rather than asking for a resistance gene". For G-004 nothing about "it" is findable until the isolate is named. Recommendation: ask which isolate (step 1), and build step 2 so the follow-up answers. The alternative, listing some Salmonella isolates unasked, would show records the person did not ask about. Step 2 needs no package, migration or security change.

## Test query

G-006 is covered by query 104. A new entry for G-004, in section 5. The number is provisional: other diagnoses tonight propose 108 and 109, so the lead assigns the next free number when filing.

```markdown
### 112. One unnamed isolate's cluster and neighbours (card 33, G-004)

Queries to try:

- `For a Salmonella enterica isolate, what SNP cluster does it belong to, which AMR genes does it carry, and which isolates are within 5 SNPs of it?`

What you should see:

- One question back asking which isolate you mean, by its BioSample accession, with one example accession, and offering the search for Salmonella isolates by resistance gene family.
- Never "Which kind of Salmonella record do you want?", and never an answer about a gene or a disease called "AMR".
- No isolate rows, since no isolate was named.
- Plain language and Researcher show the same question back.
- Why it matters: the person asked about one isolate; the only honest next step is to ask which one, in words they can act on.
```

When step 2 is built, the entry gains a second query: the same question with a real BioSample accession, expecting the isolate's SNP cluster, its AMR genes and the isolates within 5 SNPs, each linked to its Pathogen Detection page, at both depths.
