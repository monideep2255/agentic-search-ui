# Card 30 diagnosis: BRCA1's "pathogenic" variants are 40 unclassified ones

Read on develop at `c916cfa3`, 2026-10-08. Code reading, saved run files and earlier read-only graph probes; no live run, no model call. My own read-only graph probe of BRCA1's variants failed to connect from this shell (`GraphConnectionError`), so the graph fact below rests on card 23's probe of 2026-10-06.

## Table of contents

- [Status today](#status-today)
- [What a person sees](#what-a-person-sees)
- [The cause](#the-cause)
- [The smallest fix](#the-smallest-fix)
- [Overlap with phase 8.7 and the guardrail](#overlap-with-phase-87-and-the-guardrail)
- [Needs the owner](#needs-the-owner)
- [Test query](#test-query)

## Status today

Still happens. Nothing on develop tells the person that the listed variants carry no classification. The owner's decision D15 (`testing/Board_plan.md`, "Card 30 keeps its list, says plainly that classification was not retrieved, and its trust verdict is 'ask'") is not built: a search of `src/` for "not retrieved" and "card 30" finds nothing, and no commit names card 30.

One part changed since the card was filed, and only a live run can say which way a given run goes:

| Run outcome | What the trust line does | Since |
|---|---|---|
| No model sentence grounds | The structured fallback lists the records, the verdict is floored to `ask`, and a generic note says "no written summary could be checked against the records" (`core/graph.py:13577` to `:13583`) | Card 46, #168, 2026-10-05 |
| One model sentence or the code-built count line grounds | No floor; the verdict can be `answer`, as on 2026-10-05: "Based on 58 sources", 40 variant names (`testing/Developer/reports/2026-10-05_board_plan/w1_writing.md:42`) | Unchanged |

Neither outcome says the variants are unclassified.

## What a person sees

Asked "Which BRCA1 variants are pathogenic?", the person reads "Found 40 sequence variant records for BRCA1, of 15350 available", then 40 missense variants such as c.4709T>C (p.Leu1570Pro), each linked to ClinVar. A reader takes these 40 as the pathogenic ones. Many BRCA1 missense variants are benign or of uncertain significance. The writing model said twice that "the pathogenicity status of these variants cannot be determined from the retrieved data alone", and that sentence was removed before the person saw it (`tracker/phase_8.1.md:810` to `:826`, F-8.1-A16). A confident wrong answer.

## The cause

Four links, each measured or read:

| Link | Evidence |
|---|---|
| 1. The graph holds no classification for any variant. The question's own search, the gene's variants template, returns whole SequenceVariant vertices, and they carry only `agent_type, id, knowledge_level, name, source, source_url, xrefs` | Read-only probe of 2026-10-06: "500 of 500 empty" for `v.clinical_significance` on HNF1A's variants (`testing/Developer/reports/2026-10-06_card23/fix_round.md:27` to `:35`). The ClinVar parser in System 1 reads the field; it was lost before the load. The template: `_HOPS[("Gene", "variants")]` and `_hop_template` (`src/system_03_search_agent/tools/cypher_templates.py:262`, `:581`) |
| 2. The live ClinVar records that do carry it are cut to one field before the writer sees them. Plan searches ClinVar by `BRCA1[gene]`, 10 records, and ESummary returns `germline_classification`; the writer is given only `title` | Search: `core/breadth_plan.py:756`, cap 10 at `:122`. Summary fields kept: `tools/ncbi_eutils_actions.py:871`. One field per row: `synthesis/findings.py:587` to `:615` with `core/graph.py:9110` (`_pick_representative_field` prefers `name`, then `title`). The only second field allowed is a gene's `summary` (`synthesis/findings.py:128`, `_EXPLANATORY_FIELDS`). Saved golden runs of 2026-09-29, ClinVar citations tallied by layer and field: 309 from Layer 2, all on `title`; from the graph, 856 on `name` and 71 on `curie`. None on a classification field |
| 3. The writer's honest caveat cannot pass the citation gate. A sentence saying a value is absent has no record value to quote, so the exact grounding pass strips it | F-8.1-A16, "The gate stripped both passes (claims=0)". The gate is correct and is not to change (phase 8.9's constraints, `tracker/phase_8.9.md`) |
| 4. Nothing code-built fills the gap. The variant-to-disease table already carries "the record's classification (for example pathogenic, benign or uncertain) is not shown here" (card 23), but only under that table; a plain gene-variants listing gets no such line | `synthesis/answer_layout.py:342` to `:346`, `variant_to_disease_source_note` returns None unless the table is the variant-to-disease mapping |

## The smallest fix

Two steps. Step 1 is what D15 decided and stops the confident wrong answer. Step 2 is the real answer.

| Step | What changes, in the person's words | Fence | Answer path | Dial | Size |
|---|---|---|---|---|---|
| 1 | Under any list of a gene's ClinVar variants, one line says "ClinVar's classification of these variants (for example pathogenic, benign or uncertain) was not retrieved, so this is not a list of pathogenic variants; open a record to see its classification." When the question asks about classification, the trust line reads "ask", never "answer" | `synthesis/answer_layout.py`: a note constant and selector beside `variant_to_disease_source_note`, keyed on record type SequenceVariant and the missing classification field. `core/graph.py`: one `_DecisionSpec`, `think.asks_classification`, started at Think beside `_ASKS_FEATURES` (`:1110`) and read in `_write_answer`, which emits the note and floors the verdict with `aggregate` (the mechanism at `:13581`). Tests in `tests/system_03_search_agent/core/` and `synthesis/` | Yes | 2, runnable behaviour | S for the note alone; M with the classifier floor |
| 2 | The list shows each variant's ClinVar classification, and a question about pathogenic variants lists ClinVar's pathogenic ones | `core/breadth_plan.py` (a ClinVar search filtered by classification, its ESearch syntax probed live first), `synthesis/findings.py` (emit `germline_classification` as a second finding for a ClinVar summary row, the way `_EXPLANATORY_FIELDS` emits a gene's summary), `core/graph.py` plan and write wiring | Yes | 2, runnable behaviour | L |

Why the floor needs a classifier decision rather than the record type alone: query 22 ("Which clinically significant variants have been reported in CFTR?") and other variant listings must keep answering as they do. A floor on every variant list would change them. The note itself is safe on every variant list, since it is true there too. The decision follows the existing `think.asks_features` pattern, so no word list decides.

Not a fix here: reloading the graph with the classification. That is System 1's pipeline, outside this repository (`.claude/rules/file-protection.md`).

## Overlap with phase 8.7 and the guardrail

| Step | Phase 8.7 overlap | Guardrail overlap |
|---|---|---|
| 1 | Yes: `synthesis/answer_layout.py` and `_write_answer` in `core/graph.py`. Phase 8.7 rewrites both. Build after 8.7 merges, or hand the note and the floor to 8.7's builder | None |
| 2 | Yes: `synthesis/findings.py`, which phase 8.7 rewrites, and `write_node` | None |

## Needs the owner

- Step 1: no. D15 already decided the behaviour.
- Step 2: yes, a cost and speed decision. A filtered ClinVar search and a classification per shown variant add calls to a question that already plans many, inside the 20-call ceiling, and phase 8.9's plan does not include them. Card 23's fix round reached the same point and stopped there for the same reason (`fix_round.md:33`).

## Test query

No existing query covers this question. Proposed, section 3. The number is provisional; the lead assigns the next free number when filing.

```markdown
### 113. Pathogenic variants are not shown as pathogenic unless ClinVar says so (card 30)

Queries to try:

- `Which BRCA1 variants are pathogenic?`: ask it once in Plain language and once in Researcher.

What you should see:

- A list of BRCA1's ClinVar variants, each linked to its ClinVar record.
- One plain line saying ClinVar's classification of these variants was not retrieved, so the list is not a list of pathogenic variants, and that opening a record shows its classification.
- The trust line never reads as a confirmed answer: no "answer" verdict, and no sentence anywhere calling the listed variants pathogenic.
- Both modes carry the same line.
- Why it matters: a person asking which variants are pathogenic will read any list under that question as the answer; a list of unclassified variants with no warning is a confident wrong answer about cancer risk.
```

When step 2 is built, the expectation becomes: each listed variant shows its ClinVar classification, the list holds only variants ClinVar classifies as pathogenic or likely pathogenic, and the line says how many ClinVar holds against how many are shown.
