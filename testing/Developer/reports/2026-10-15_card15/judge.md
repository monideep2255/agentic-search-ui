# Judge, card 15 (PR #249), one round, dial 2

Branch fix/card15-checked-templates at af0439e5 against develop 851125c1.

## Findings

### J-15-01: a remembered condition is forced into the disease's-variants search and the topic search's memory guard is skipped
- Severity: major (worse than develop; sits inside this PR's own topic-search change)
- What: `_checked_graph_shape` does not look at `planned.memory_bound`. A turn that names no resolvable entity binds ONE remembered CURIE as the antecedent; when that CURIE is a condition, `possible_graph_shapes` returns `disease_variants`, the decision is asked with only the question TEXT as its state (the classifier never sees which identifier is bound, or that it came from memory), and a pick forces `disease_variants_one` on the remembered condition. The new `planned.template is None` guard then skips the whole topic block, including the 2026-09-23 memory rule that exists so a new question after an old subject reaches the new subject ("a person who types a new question about caffeine after one about a gene gets papers about the gene, which is the confident wrong answer").
- Reproduction: own probe, `plan_node` driven with only `decide` faked (`plan.graph_shape` picks `disease_variants`, `plan.literature` picks `wants_literature`), `_memory_curies` returning `["MedGen:C0010674"]` (cystic fibrosis from an earlier turn), Think resolving nothing, class multi_hop, text "Which variants are reported in papers on hearing loss in Ashkenazi Jewish families?".
  - Develop 851125c1: decisions asked `['plan.literature']`; calls `ncbi_efetch, ncbi_efetch, pubtator_annotate` (the topic literature search; no graph call).
  - Branch af0439e5: decisions asked `['plan.graph_shape']`; first call `cypher_query memory_bound=True template=disease_variants_one target=['MedGen:C0010674']`, then the disease fan-out. The literature decision is never read.
  - The fake decides the pick, so what the probe proves is the wiring: nothing in code stops a pick here, and the classifier is given no way to tell. Its criterion ("which variants ... are linked to ... the named condition, and names no gene") reads true for this text, because the text names a condition, just not the one bound.
- Why it matters: the person asked about hearing loss and is shown up to 100 cystic fibrosis variants, each cited, as the graph's answer. That is a confident wrong record where develop showed papers on the words typed. Reachable whenever a session's last resolved entity is a condition and the new turn's condition does not resolve (a misspelling, a rare or plain-English name). Only shape D can be reached this way (memory binds one CURIE; A, B and C need two or more). A fix candidate for the lead, not applied: skip `_checked_graph_shape` when `planned.memory_bound` is True, or pass the bound identifiers' names into the decision state.
- NOT FIXED

### J-15-02: a "how many" question about several genes' variants fires the list shape and gets no number
- Severity: major, unsure (whether it is worse than develop is not measured)
- What: the build report's own held-out check records `How many variants in MLH1 and MSH2 cause Lynch syndrome?` picking `genes_variants_for_condition`. That template is a UNION with two RETURN columns, so a capped result is reported `truncated=True, total_available=None`: the person who asked for a number gets up to 100 variants and "the exact total is not available". The records are right (anchored on the typed genes and condition), so this is not a wrong record, but it is the "how many" misfire the bar names. Develop's answer to the same count question was never run beside it; the build's develop runs used only the list wording.
- Reproduction: not reproduced by me (no live calls tonight). Source: build.md, Slice C, "Held-out: 19 of 20 agree. Miss: `How many variants in MLH1 and MSH2 cause Lynch syndrome?` picked the shape". My own probe confirms the output for a forced pick: the normalized query has two RETURN columns (`_return_column_count` = 2), so no count can be fetched.
- Why it matters: if develop's written search answers this count, the branch answers it worse. Recommendation: five live runs of the count wording on branch and develop before merge, or a criterion on `none_of_these` naming a count of variants explicitly.
- NOT FIXED

### J-15-03: every eligible question now waits for one more classifier call before Plan, even when it falls back
- Severity: minor (speed)
- What: `_checked_graph_shape` is awaited in sequence inside `plan_node`, after `_select_planned_tool_call`, for every question whose bindings make a shape possible and develop has no template for: any one-condition question on a hop or aggregate class, two to ten PMIDs on a hop class, a gene with a paper, several genes with a condition. "none_of_these" returns develop's call, but only after the call. A stalled decision holds Plan until its step deadline.
- Reproduction: own probe, Plan driven with `plan.graph_shape` sleeping 3 s and Plan's deadline patched to 0.3 s, question "Variants in MLH1 and MSH2 causing Lynch syndrome": branch `secs=0.30`, call unchanged; develop `secs=0.00`. Live cost by the design's measurement: 0.3 to 1.5 s per question on the guard tier.
- Why it matters: "nothing slower than develop". A question that does not get a shape is slower by one decision for nothing. Small against the 20 s guide, and the lead's brief accepts fallback, so recorded, not blocking.
- NOT FIXED

### J-15-04: a request for papers about one condition can now get variants instead of papers
- Severity: minor, unsure (depends on the live classifier)
- What: the topic search is skipped whenever a shape is forced. On develop, a question with no gene resolved that the literature decision reads as "wants literature" plans the PubMed topic search. On the branch, if Think resolves one condition (for example "papers on the variants that cause cystic fibrosis"), shape D is eligible, and the `disease_variants` criterion ("which variants ... linked to ... the named condition, names no gene") can match it. `none_of_these`'s criterion does not name "asks for papers or literature". A pick replaces the papers with the graph's variant list.
- Reproduction: the wiring is shown by the J-15-01 probe (a forced shape skips `plan.literature`); the J-15-01 probe with `_memory_curies` removed and the condition resolved by Think gives the same plan shape. Whether the live classifier picks D for this wording is not measured: the build's held-out near misses for D are not listed in the report.
- Why it matters: the records are about the right condition, so not a wrong record, but a person who asked for papers gets a different kind of answer than on develop.
- NOT FIXED

### J-15-05: the per-branch cap reports "more exist" for a result where no branch was capped
- Severity: minor
- What: `cypher_query` sets `hit_cap` when `len(rows) >= branch_row_cap`, so two genes returning 30 and 30 variants (60 rows, share 50, neither branch full) report `truncated=True, total_available=None`. Write then says the answer "was truncated before every matching record could be retrieved", which is false for that result. The check never claims a complete count when a branch is full (a full branch alone returns `share` rows, so the property the lead asked for holds), and it touches no template without `branch_row_cap` (`branch_cap is None` for every develop template, all of which set none).
- Reproduction: by the condition in code; the build's own 80-row test is the same input class (it asserts truncated for 80 rows that the fake graph returns regardless of branch). A branch-aware count (each branch's row count from the gene column) would remove it.
- Why it matters: claims less than is true, never more, as the build says. A sentence that is false is still false; low impact.
- NOT FIXED

### J-15-06: the several-conditions form of shape C uses an IN list and was not timed live
- Severity: minor, unsure
- What: with two or more conditions bound, each branch filters `WHERE x.id IN [...]` on the Disease end. The design's own convention says "no template uses `WHERE a.id IN [...]`" (the 8 October J-15-02). Here the IN filters a node reached by an edge, not an anchor, so it is probably not a table scan, and the one-gene develop template does the same. The live check ran one condition only; MedGen name matching often binds several concepts for one syndrome.
- Reproduction: own probe, three genes and two conditions, normalized branch `MATCH (v:SequenceVariant)-[:is_sequence_variant_of]->(a:Gene {id: $e_NCBIGene_1}) MATCH (v)-[:has_phenotype]->(x:Disease) WHERE x.id IN [$e_MONDO_5, $e_MedGen_C1] WITH v, collect(DISTINCT x) AS xs ORDER BY v.id LIMIT 33 RETURN v, xs ORDER BY v.id LIMIT 100`. No live timing.
- Why it matters: if it times out, the person sees a search that did not finish where develop's written search may have answered.
- NOT FIXED

### J-15-07: shape D replaces the designed GO and MeSH shapes with no DECISIONS.md row on the branch
- Severity: minor (process)
- What: the build report says the lead decided four shapes (D as a disease's variants) on 2026-10-15 in `DECISIONS.md`, and also lists "Not written: the `DECISIONS.md` row". `git diff 851125c1...af0439e5` touches no `DECISIONS.md`.
- Reproduction: `git diff --stat 851125c1...af0439e5` lists nine files, none of them `DECISIONS.md`.
- NOT FIXED

## Checklist

| Item | Result | How |
|---|---|---|
| 1. Template Cypher against the design | Correct. A: one inline Article match per paper, UNION ALL, name order. B: `(Gene {id})-[:mentioned_in]->(Article {id})`, both ends inline, gene end. C: per gene `(v)-[:is_sequence_variant_of]->(Gene {id})`, `(v)-[:has_phenotype]->(Disease)`, fold, `ORDER BY v.id LIMIT 100//n` before RETURN, validator adds `LIMIT 100` per branch. D: `(SequenceVariant)-[:has_phenotype]->(Disease {id})`, one column, so the count rewrite gives a true total. All validate; effective limit 100 | Own probe printed every normalized query. Own mutations, one per shape, each turned the card's tests red: A `MAX_SHAPE_IDENTIFIERS=2` (3 failed), B wrong edge label (2 failed), C `SHAPE_ROW_BUDGET=200` (4 failed), D edge reversed (1 failed), cap off by one (3 failed) |
| 2. Fallback leaves develop's call unchanged | Holds for "none_of_these", a timeout, a raising seam and an off-list pick | Own probe on "Variants in MLH1 and MSH2 causing Lynch syndrome": the graph call and all 13 planned tools equal develop's in all four modes; a pick changes only the template |
| 3. Topic-search guard cannot change a develop path with no forced template | Holds for develop's own calls: develop sets `template=` in one place, the context-only GO call, built after this block | grep of develop's `core/graph.py`; the probe's fallback modes equal develop. But the guard is what lets J-15-01 skip the memory rule once a shape IS forced |
| 4. Capped-result report | Never claims complete when a branch is full; no change for any template without `branch_row_cap` | Read plus the card's tests; J-15-05 notes the over-claim of truncation |
| 5. Gates | `ruff check`: all checks passed. isort gate command: exit 0. pytest core and tools, not integration: 3282 passed, 132 skipped, 24 deselected | Run in a detached worktree at af0439e5 |

## What I verified and what I only read

- Verified with my own probes: every template's normalized Cypher and validation; eligibility edge cases (HP, GO, MeSH, taxon and ClinVar mixes are ineligible; MONDO and MedGen alone are eligible for D); one mutation per shape; the four fallback modes against develop; the memory-bound path in J-15-01 against develop; the gates.
- Only read: the live timings, the held-out pick rates and the five-run checks in the build report (no live calls tonight); the classifier's actual behaviour on the J-15-01, J-15-02 and J-15-04 wordings.

## Verdict

FIX FIRST.

- J-15-01 is worse than develop: a session whose last resolved entity is a condition, followed by a question whose own condition does not resolve, can show up to 100 cited variants of the remembered condition where develop shows papers on the words typed. That is a confident wrong record. It sits inside this phase's own change (the topic-search guard added after the live check), so by the review loop's stop condition it goes to the owner rather than into another round. A narrow fix exists: do not ask `plan.graph_shape` when `planned.memory_bound` is True, so a remembered antecedent keeps develop's path.
- J-15-02 should be measured before merge (the count wording, five runs each side); it is not a wrong record.
- J-15-03 to J-15-07 are minor and do not block.
