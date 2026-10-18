# Fresh verifier after the fix round: card 37 slice A1

Pull request #262, branch `fix/card37-rs334-named-by-its-id`: build commit `b250b689`, fix commits `2afba03e` and `10882a32`, on develop `78c68c1c`. Worktrees: `<worktrees>/card37a1-ver2` (detached at `10882a32`) and `<worktrees>/card37a1-ver2-dev` (develop, for comparison, removed after this report). Probes in `<scratchpad>/card37a1_ver2/`. Every verdict below was re-derived from the code and from my own runs; nothing is taken from `build_A1.md` or `verifier_A1.md`.

## Table of contents

- [Findings](#findings)
- [The five findings and the mixed table, closed or not](#the-five-findings-and-the-mixed-table-closed-or-not)
- [Mutations](#mutations)
- [The broad check against develop](#the-broad-check-against-develop)
- [The Plain language label](#the-plain-language-label)
- [Tests and lint gates](#tests-and-lint-gates)
- [Live runs](#live-runs)
- [Verdict](#verdict)

## Findings

### V-37-06, minor, not worse than develop for any observed record: the gene in the Plain language label is cut at 100 characters mid-name

`answer_layout.py:970`: `head = f"{base} ({gene.strip()[:100]})"`. The two values after it go through `_clip_terms` (V-37-03), the gene list does not. dbSNP's tool allows 10 genes of up to 30 characters (`tools/ncbi_dbsnp.py:391`, `:400`), so the joined list can reach 318 characters. Offline page, a constructed rs id with ten `LOC1053777NN` genes, branch, Plain language:

```
list_item ['Genetic variant (LOC105377703, LOC105377704, LOC105377705, LOC105377706, LOC105377707, LOC105377708, LOC105377709, LO), clinical significance: ...']  len=[355]
```

"LO" is half a gene symbol. A cut like this can, in principle, leave a different real symbol (a cut of "TP53TG1" after four characters reads "TP53"). The Researcher Gene cell is not affected: `table_second_cell` keeps 500 characters (`answer_layout.py`, `value.strip()[:500]`), so the same row shows all ten genes there. Not seen on real data: the longest gene list in the first verifier's 34 real rs ids is "VKORC1, LOC124903680" (20 characters), and it takes about eight long gene names to pass 100. Develop shows no gene at all in Plain language, so nothing develop showed is lost. It is the same class V-37-03 closed for the values (Review rounds, rule 2: fix by category), and a one-line fix inside the fence: `_clip_terms(gene, 100)`. No test covers this cut.

### V-37-07, minor, documentation, not worse for a person using the product: query 23's new line no longer matches the screen

`testing/Test_queries_and_workflows.md:557` (added in `b250b689`, untouched by both fix commits) says: "In Plain language it reads "Genetic variant (HBB)"." Live and offline, Plain language now reads "Genetic variant (HBB), clinical significance: not-provided, protective, likely-benign, pathogenic, other", which is the lead's V-37-02 decision. The line also does not mention the "Consequence" column (rs6025) or the mixed heading. The owner retests against this document, so the line should say what the screen says.

## The five findings and the mixed table, closed or not

| Item | Decision's words | Closed? | Evidence |
|---|---|---|---|
| V-37-01 | a withheld significance list shows its functional consequence in its own column | Closed | Closed table row at `answer_layout.py:593`. Offline rs6025 page from the real builder, branch Researcher: header `['Variant', 'Identifier', 'Gene', 'Consequence']`, row `['rs6025', 'rs6025', 'F5', 'coding_sequence_variant, missense_variant']`; develop showed the same value as the row's label, so the fact is still on screen. Live, `What are rs334 and rs6025?` shows it (below) |
| V-37-02 | Plain language keeps dbSNP's values verbatim after the gene, or the consequence when there is none | Closed | Live q23 Plain language, the no written answer fallback: `list_item ['Genetic variant (HBB), clinical significance: not-provided, protective, likely-benign, pathogenic, other']`. Offline rs6025: `'Genetic variant (F5), consequence: coding_sequence_variant, missense_variant'`. "pathogenic" stays on screen when no sentence survives |
| V-37-03 | the column is clipped at a term boundary, never mid-term | Closed for the column and both values; see V-37-06 for the gene | `_clip_terms` at `answer_layout.py:619`. Offline, a constructed 618 character consequence list: develop's label ends mid-term at 500 (`'..., splice_donor_region_'`); the branch column is 479 characters ending at a whole term plus an ellipsis, the Plain label 455 |
| V-37-04 | the guard test is built from the real dbSNP row builder | Closed | `_real_row` calls `graph_module._layer_tool_output_to_structured_fields("ncbi_dbsnp", output)` (test file lines 49 to 72). Mutation below turns it red |
| V-37-05 | the label's address check gets a test | Closed | `test_v37_05_a_url_in_the_rs_id_field_is_never_the_label`; mutation below turns it red |
| Mixed table | heads "Clinical significance or consequence", each cell names which it is, no row's value dropped; every other row type's heading as on develop | Closed | Offline, rs6025, rs334 and a row with neither: header `[..., 'Clinical significance or consequence']`, cells `'consequence: coding_sequence_variant, missense_variant'`, `'significance: not-provided, protective, likely-benign, pathogenic, other'`, `''`; every row kept, four cells each. Live (below). Every non dbSNP group byte identical to develop (below) |

The new call at `core/graph.py:13475` returns the very same list object for any type that is not `Variant record` (`answer_layout.py`, `if entity_type not in _ROW_TYPE_LABEL_FIELDS: return extras`; the test asserts `is extras`), and only `ncbi_dbsnp` emits that type (`grep -rn -i '"variant record"' src` finds only `core/graph.py:5033`). The type groups by noun "variant record", which no other emitted type shares (probe: `Literature variant` groups as "literature variant").

## Mutations

One property each, applied by `<scratchpad>/card37a1_ver2/mutate.py` (exact text replacement that must match once, file restored byte for byte after each), run against the slice file. `git status --short` empty afterwards.

| Mutation | Result |
|---|---|
| V-37-01: drop the `("Variant record", "functional_consequence")` column row | 4 failed, 19 passed |
| V-37-02: Plain details loop emptied | 5 failed, 18 passed |
| V-37-02: Plain details lose the consequence only | 1 failed, 22 passed |
| V-37-03: `_clip_terms` hard cut `text[:limit]` | 1 failed, 22 passed |
| V-37-03: Plain label clips to 500 ignoring its prefix | 1 failed (`assert 540 <= 500`), 22 passed |
| V-37-03: no ellipsis | 1 failed, 22 passed |
| V-37-04: the real builder in `core/graph.py` puts `rsid` first | 1 failed (`field='rsid'`), 22 passed |
| V-37-05: drop the URL check in `_row_type_label` | 1 failed, 22 passed |
| Mixed: remove the call in `grouped_listing` | 1 failed, 22 passed |
| Mixed: both kinds worded "significance" | 1 failed, 22 passed |
| Mixed: applies to a table of one kind | 4 failed, 19 passed |
| Mixed: the `Variant record` type gate removed | 1 failed, 22 passed |
| Mixed: no kind prefix in the cell | 1 failed, 22 passed |
| The column closed table ignores the row type | 1 failed, 22 passed |

Every mutation goes red. The tests read the property itself (cell text, heading, length, field order), not a correlate.

## The broad check against develop

`<scratchpad>/card37a1_ver2/probe_pages.py` runs `write_node` on each tree with a faked writer, network blocked at the socket and MedGen names stubbed, over 26 row shapes: rs334, rs6025 and a row with neither (all three from the real dbSNP builder), a bare rs id, a long significance list with ten long genes, a 618 character consequence list, three mixed dbSNP tables (one finding; one finding with a third row with neither; two calls), dbSNP plus LitVar2 on the same page and on its own page, a clinical trial group with mixed extras (status, registered year, nothing), a trial group of statuses, a trial group of years only, a graph gene group with conditions (one placeholder), a graph gene group without, a graph ClinVar group (resolved, placeholder, unresolved), a Layer 2 ClinVar group with a created year, graph Gene plus Layer 2 `gene` in one group in both orders, PubTator3, LitVar2 alone, a Pathogen Detection isolate group, an assembly with a status, a page of seven types, and a page of other types with the mixed dbSNP table. Each at Researcher, Plain language and `clinical_brief`, with a writer that grounds nothing and one that echoes the prompt lines, plus command line and MCP at Researcher and Plain language: 260 pages per tree, no crash on either. `<scratchpad>/card37a1_ver2/compare.out`:

```
pages 260
prompt differs []
non-token events differ []
tokens differ on a page with no Variant record row []
tokens differ on dbSNP pages 110 same on dbSNP pages 10
```

- The writer's prompt is identical on all 260 pages.
- Every citation, trust signal, step, cost and done event (the trust line) is identical on all 260 pages.
- Every token is identical on all 140 pages with no `Variant record` row, which includes every grouped table through the new `grouped_listing` call: the trial groups, the gene groups, the ClinVar groups, the isolate table and the mixed type groups.
- On the dbSNP pages, every differing token is the opening "Found ..." sentence (its text, and on 4 pages its emphasis, now `['rs334']`), the `Variant record` table header, or a `Variant record` row or list item's cells (`token_diff_kinds.out`: 58 claims, 66 headers, 96 rows, 64 list items, no other token). On "many_types_with_dbsnp" the ClinVar, gene, trial and publication groups around the dbSNP table are unchanged.
- The command line and MCP print the row's `text`, which is unchanged (`'Variant record clinical_significance: not-provided, ... [1].'`, `'Variant record functional_consequence: ... [2].'`), so there the values stay in the row's own sentence and only the opening sentence and cells change.
- The 10 dbSNP pages with identical tokens are the bare rs id (no significance, consequence or gene), which develop already labelled by its rs id.
- No call is added; no page took more than a few tenths of a second on either tree.

## The Plain language label

| Row | Develop | Branch | Length |
|---|---|---|---|
| rs334 | `not-provided, protective, likely-benign, pathogenic, other` | `Genetic variant (HBB), clinical significance: not-provided, protective, likely-benign, pathogenic, other` | 104 |
| rs6025 | `coding_sequence_variant, missense_variant` | `Genetic variant (F5), consequence: coding_sequence_variant, missense_variant` | 76 |
| Neither, with a gene | `Genetic variant` | `Genetic variant (ABC1)` | 22 |
| Neither, no gene | `Genetic variant` | `Genetic variant` | 15 |
| Ten long genes, ten long terms | the list, 212 | gene list cut mid-name at 100, then every term whole (V-37-06) | 355 |
| 618 character consequence | cut mid-term at 500 | whole terms plus an ellipsis | 455 |

The longest possible label: a 118 character head, a 25 character prefix, and values clipped to the rest, so never over 500, the `cells` cap (`contracts/events.py:428`). No value is cut mid-term; the gene list can be (V-37-06).

## Tests and lint gates

- `test_variant_record_label.py`, `test_answer_layout.py`, `test_answer_quality.py`, `core/test_write_answer_structure.py`, `core/test_layer_handoff.py`: `254 passed in 18.54s`.
- Neighbours of the `core/graph.py` change, `core/test_graph.py` and `test_listing_one_row_per_record.py`: `274 passed in 17.71s`.
- gate01 (`python -m compileall -q src services tests alembic` and the three imports): `gate01 ok`.
- gate02 (`isort --check-only --diff src tests services tracker alembic .claude .github`): `Skipped 2 files`, exit 0.
- gate03 (`ruff check`, no path): `All checks passed!`, exit 0.

## Live runs

Four runs on the branch through `core.run.run_streaming()`, web surface, placement on, `CLASSIFIER_PROVIDER=jev`, guard and plan models as in card 115's adversary run, writer from the local settings, `PER_QUERY_COST_CAP_USD=0.25`, session ids `card37a1-ver2-q23-researcher`, `card37a1-ver2-q23-plain`, `card37a1-ver2-mixed`, `card37a1-ver2-rs1-control`. Spend 0.0303 + 0.0027 + 0.0045 + 0.0108 = 0.048 USD. Times 8.45 s, 8.17 s, 11.32 s, 9.18 s. Script `<scratchpad>/card37a1_ver2/live.py`.

Query 23, Researcher (a writer sentence survived):

```
claim        'Found 1 literature variant record for rs334: c.20A>T [2].'
heading      'Variant record records found'
table_header ['Variant', 'Identifier', 'Gene', 'Clinical significance']
table_row    ['rs334', 'rs334', 'HBB', 'not-provided, protective, likely-benign, pathogenic, other']
trust line   "Based on 1 source cited, not yet confirmed" (ask); claim [1] dbsnp ask high, claim [2] litvar2 answer low
```

Query 23, Plain language (the no written answer fallback):

```
claim        'I found 1 genetic variant related to rs334 [1].'
heading      'Where this answer comes from'
list_item    ['Genetic variant (HBB), clinical significance: not-provided, protective, likely-benign, pathogenic, other']
trust line   "Based on 1 source cited, not yet confirmed" (ask); claim [1] dbsnp ask high
```

`What are rs334 and rs6025?`, Researcher (the mixed table):

```
claim        'Found 2 literature variant records for rs334 and rs6025: c.20A>T [3] and c.1691G>A [4].'
heading      'Variant record records found'
table_header ['Variant', 'Identifier', 'Gene', 'Clinical significance or consequence']
table_row    ['rs334', 'rs334', 'HBB', 'significance: not-provided, protective, likely-benign, pathogenic, other']
table_row    ['rs6025', 'rs6025', 'F5', 'consequence: coding_sequence_variant, missense_variant']
trust line   "Based on 2 sources cited, not yet confirmed" (ask); [1] dbsnp clinical_significance hedged, [2] dbsnp functional_consequence asserted
```

Control, `What does the RS1 gene do?`, Researcher: Gene rows `['retinoschisin 1', 'NCBIGene:6247']`, `['RS1', 'NCBIGene:6247']`; five PubMed rows, title and PMID; five ClinVar rows such as `['NM_000330.4(RS1):c.78+2T>C', 'VCV001723073']`; two OMIM rows; five trial rows with a Status column (`COMPLETED`). No Gene, Clinical significance, Consequence or mixed column on any of them. Trust line "Sources disagree on at least one claim" (flag), from two claim level flags, a path the offline probe shows byte identical on both trees.

## Verdict

Every item the lead decided is closed and each new test goes red under its mutation. Develop and the branch give the same writer prompt, citations and trust signals on all 260 offline pages. Every row type other than `Variant record` renders byte for byte as on develop, including every grouped table through the new `grouped_listing` call. On rs334, rs6025 and the mixed table, every value develop showed is still on screen. The two findings are minor and neither is worse than develop for any person on any record seen: V-37-06 is the gene list cut mid-name past 100 characters in Plain language, not reached by real data, with a one-line fix; V-37-07 is query 23's line in the test queries document, which needs to say what the screen now says.

VERDICT: PASS
