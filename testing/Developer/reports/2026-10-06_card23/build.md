# Card 23 build: the source note under the variant-to-disease table

Card 23, the owner's decision of 2026-10-06 (`DECISIONS.md`): under the variant-to-disease table, one plain line names where its links come from. Built on branch `fix/card23-source-note` from develop `d8179c4e`, from the helper parked on `parked/phase-8.4-2026-09-25` (commit `830e1d05`, cherry-picked alone as `2f7850bd`).

## Table of contents

- [In the user's words](#in-the-users-words)
- [Where the table's rows truly come from](#where-the-tables-rows-truly-come-from)
- [The change](#the-change)
- [Choices](#choices)
- [Tests and mutations](#tests-and-mutations)
- [Live runs](#live-runs)
- [Gates](#gates)
- [Not covered](#not-covered)

## In the user's words

A person who asks "What diseases are caused by variants in the HNF1A gene?" at Researcher depth now sees, directly under the "Variant-to-disease mapping" table:

> Variant-to-disease links are ClinVar assertions, each cited to its variation record. Disease names are MedGen titles read live from NCBI.

The line appears only under that table. The gene-to-disease table, the trial table, the isolate table and the plain lists of records get no line. A Plain language answer lists the same records as titles with no table, so it shows no line either.

## Where the table's rows truly come from

Established from the code before any wording was kept. Every fact below holds for every row the table can show.

| Fact | Where |
|---|---|
| The table's mapping column reads the row field `clinvar_condition_ids` | `src/system_03_search_agent/synthesis/answer_layout.py:297` |
| Only the two variant fold templates write that field, and both traverse `has_phenotype` from a SequenceVariant to a Disease | `src/system_03_search_agent/tools/cypher_templates.py:135`, `:497`, `:516` |
| The fold runs on the template path only; a model-written graph query never writes it, and a derived column is never a SequenceVariant row | `src/system_03_search_agent/tools/cypher_query.py:2179` |
| `has_phenotype` joins SequenceVariant to Disease, and a SequenceVariant's only CURIE prefix is `ClinVar` | `src/system_03_search_agent/tools/graph_schema_constants.py:99`, `:140` |
| In System 1, the only writer of `has_phenotype` is the ClinVar variant-summary parser: one edge per MedGen concept in ClinVar's `PhenotypeIDS`, with source "ClinVar" and the variant's ClinVar variation page as `source_url`; the variant node carries the same page | The data-engineering reference repository, read only |
| Disease names are MedGen titles: the fold's MedGen CURIEs are resolved through one live MedGen ESearch and one ESummary per answer | `src/system_03_search_agent/core/graph.py:12806`, `src/system_03_search_agent/synthesis/disease_names.py:265` |
| A CURIE with no MedGen title, or a ClinVar placeholder title, is not shown; the cell never carries a code or a guess | `src/system_03_search_agent/synthesis/answer_layout.py:602` |

So the rows come from one source, the graph's ClinVar `has_phenotype` edges, and the names from one source, MedGen. LitVar2, PubTator and the Layer 2 ClinVar search never reach this table: a Layer 2 ClinVar record is a "Clinvar records found" list of its own, which the live runs show without the line.

## The change

- `2f7850bd`: the parked helper, `VARIANT_TO_DISEASE_SOURCE_NOTE` and `variant_to_disease_source_note(entity_type, mapped)` in `answer_layout.py`, with its two tests. One conflict in `test_answer_layout.py` (card 95's tests had landed at the same place); both sides kept.
- `c75dbf81`: the wiring in `core/graph.py`, inside `grouped_listing` of `_answer_tokens` (`graph.py:12441`). After the table's last row it calls the helper with the same `entity_type` and `mapped` that chose the table's heading (`graph.py:12353`, `:12387`) and emits the line as a `note` token after a paragraph break. One import line added. The call site named in phase 8.4's builder F report still exists today, about 3,000 lines further down.
- One line under query 79 in `testing/Test_queries_and_workflows.md`, naming the line and that Plain language shows none.

No event schema change and no frontend change: the `note` token kind exists, and the answer screen and the saved answer both render a `note` already.

## Choices

| Choice | Alternatives | Why |
|---|---|---|
| Keep the owner's wording of 2026-09-25 verbatim | Reword it | The table above shows each clause is true. The owner chose this text over a shorter one (`DECISIONS.md`, 2026-09-25) |
| Emit the line from inside the table's own group | Add it to the answer-wide notes list | Phase 8.4's builder F report: the line must sit with its table. Mutation M5 shows the answer-wide form puts it on answers with no table |
| Key it on `mapped`, the flag that chose the table heading | Key it on any SequenceVariant record | A variant list with no linked diseases is not the mapping table, and the line would describe a table the reader cannot see |
| No line in Plain language | A line under the plain list | The plain list shows titles only, no pairing; a line about "links" would describe something not on the page |
| A paragraph break before the line | None | Every other note is preceded by one, so a surface that joins text keeps the line apart from the last row. On screen it changes nothing |

One honest limit of "read live from NCBI", for the lead: the titles are read from NCBI's MedGen service when an answer is built, and a process keeps each title for up to one week (`disease_names.py:70` to `:82`), so a repeated question can show a title read days earlier. MedGen titles change rarely. I judged the wording true and kept the owner's text; if the owner wants it exact, "Disease names are MedGen titles looked up from NCBI" carries no timing claim.

## Tests and mutations

Five new arms (three in `tests/system_03_search_agent/core/test_write_answer_structure.py`, one parametrized three ways) plus the helper's own two, through the real `write_node` and grounding pass with only the model call faked:

| Arm | Property |
|---|---|
| `test_card23_the_source_note_sits_directly_under_the_variant_table` | Exactly one line; only the table's header and rows lie between the "Variant-to-disease mapping" heading and it; the next structure after it is the gene table's heading |
| `test_card23_no_variant_table_no_source_note` (Plain language, variants with no linked diseases, a gene-to-disease table) | No line without the table; each case is populate-checked so it cannot pass on an empty page |
| `test_card23_the_note_names_the_sources_the_code_actually_uses` | The mapping field, both templates' edge, the edge's endpoints and the SequenceVariant prefix are the ones the note describes; the note names ClinVar, the variation record and MedGen titles, and no other source |

Each mutation was applied, the arms run, and the file restored (`raw/mutate.py`, output in `raw/mutations.txt`):

| Mutation | Turns red |
|---|---|
| M1 the wiring removed | The placement arm |
| M2 the line emitted above the rows | The placement arm |
| M3 the helper ignores the record type | The gene-table case, the placement arm, three helper cases |
| M4 the helper ignores `mapped` | The no-linked-diseases case, one helper case |
| M5 the line made answer-wide | The Plain language case, the no-linked-diseases case, the placement arm |
| M6 the wording names LitVar2 | The wording arm, the helper's pinned text |

## Live runs

Method: `core.run.run` locally with the real models, tools and graph, `CLASSIFIER_PROVIDER=jev`, as card 101's `build_r2.md` ran it. The user database was a throwaway Postgres on a separate port in the session scratchpad, migrated to alembic head (`0010_interactions_saved_answer`), started for the runs and stopped afterwards. Scripts: `raw/live_run.py` and `raw/analyse_live.py`; the summary is `raw/live_summary.txt`; raw answers stay outside the repository.

Question: query 79's "What diseases are caused by variants in the HNF1A gene?".

| Run | Depth | Seconds | Cost | Table shown | Line shown | Rows citing their ClinVar variation record | Disease names that are a cited MedGen record's title |
|---|---|---|---|---|---|---|---|
| r1 | Researcher | 21.8 | $0.022 | Yes, 38 rows | Once, directly under it | 38 of 38 | 6 of 6 |
| r2 | Researcher | 24.9 | $0.018 | Yes, 38 rows | Once, directly under it | 38 of 38 | 6 of 6 |
| p1 | Plain language | 17.6 | $0.019 | No | No | Not applicable | Not applicable |

Total spend $0.059 of the $0.10 allowed. In both Researcher runs the "Gene records found" group followed the table, so the answer screen shows the line in place, between the table and that heading (`frontend/src/hooks/useRunView.ts:710` and `:811`). The "Clinvar records found" list further down, Layer 2 ClinVar records, got no line. 29 of the 38 rows had an empty disease cell, all placeholder links, which the existing note "39 variant links to ClinVar placeholder conditions ... are not listed" already discloses; an empty cell asserts nothing, so the line stays true for them.

## Gates

| Gate | Result |
|---|---|
| gate02, import order | Pass |
| gate03, lint over the whole repository | Pass |
| gate04, the whole unit suite (load 7.4 at the start) | 7035 passed, 143 skipped, 1 xfailed |
| `check_public_leaks.py --base origin/develop` | Pass, run after the last commit |

## Not covered

- When the variant table is the last thing in the answer, nothing follows the line, and the answer screen moves it to the "Notes" list after the answer as its first item (`useRunView.ts:827`), not directly under the table. Neither live run hit this, since a gene group followed both times; a question returning only variants and their diseases would. Fixing it is a frontend change (attach a note that directly follows a table's last row to that table), outside this card's fence while card 22 works in the same files.
- No screenshot: the screen's handling of a mid-answer note is existing code, read, not exercised visually here.
- `clinical_brief` and `deep_technical` depths take the Researcher path by the same `is_plain_language` test; not run live.
- The scratchpad is shared with the sibling builders: card 22's builder overwrote a `mutate.py` there after my run. My runs were unaffected (the committed `raw/mutate.py` reproduces every result), but parallel builders should write to their own subfolders.
