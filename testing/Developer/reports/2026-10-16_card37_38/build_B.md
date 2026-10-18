# Build report: card 38 slice B, orthologs with species

Branch `fix/card38-orthologs-with-species`, from develop `655e9dfe`. Built from phase 8.9's recorded probe 1 (591 of 591 TP53 orthologs have an `in_taxon` edge). The live graph was not reachable from this shell, so no live timing was taken.

## What changed in the person's words

- TP53's orthologs list their species: an Organism column in Researcher, and "tumor protein p53 (Oryctolagus cuniculus)" in Plain language.
- The answer still says 591 orthologs against the 100 shown.
- Every other question's graph query and list are as on develop.

## Diff by file

| File | Change |
|---|---|
| `tools/cypher_templates.py` | `FOLD_FIELD_ORGANISM = "organism"`; new `CypherTemplate.value_fold` flag (default False); the single-gene ortholog template becomes `MATCH ... OPTIONAL MATCH (x)-[:in_taxon]->(t:OrganismTaxon) WITH x, collect(DISTINCT t.name) AS xs RETURN x, xs ORDER BY x.id` with `fold=("x","xs","organism")` |
| `tools/cypher_query.py` | `_fold_value_names` (strings only, one printable line, blanks dropped, deduplicated, sorted, capped at `MAX_FOLD_ITEMS`, joined ", "); `_apply_fold(..., value_fold)`; the count gate runs the count query when `column_count == 1 or value_fold`; edge-type derivation reads the query without the OPTIONAL MATCH clause for a value fold |
| `synthesis/answer_layout.py` | `("Gene", "organism")` in `_ROW_TYPE_COLUMNS` ("Organism") and `_ROW_TYPE_PLAIN_SUFFIXES` (empty noun, meaning the title leads); `plain_record_label` appends " (organism)" |

Two things worth the lead's eye:

- Without the edge-type step, the extra `in_taxon` touch on `x` made `_traversed_edge_type_by_column` return `{}` for the ortholog rows (probe: develop gives `{'c0': 'orthologous_to'}`). The ortholog rows would have lost their `orthologous_to` edge type. The step restores it; a test pins it.
- The count query becomes `... WITH x, collect(DISTINCT t.name) AS xs RETURN count(*) AS total_count`, which counts one row per ortholog. It passes `validate_cypher`. Whether the live graph accepts it and its time (phase 8.9 measured 5.44 s for a similar count) is untested here.

## Tests

New `tests/system_03_search_agent/tools/test_cypher_ortholog_organism.py` and two arms appended to `tests/system_03_search_agent/synthesis/test_answer_layout.py`.

| Test | Proves |
|---|---|
| `test_the_ortholog_template_reads_each_organism_and_stays_read_only` | Parameterized, no literal, no write words, OPTIONAL MATCH, passes the validator, fold constants |
| `test_only_the_single_gene_ortholog_template_changed` | The other 45 templates' Cypher hashes identical to develop's; no other `value_fold` |
| `test_the_list_carries_species_and_the_total_stays_591` | Stubbed count 591 gives `total_available == 591`, 100 rows, organism text cleaned, edge type kept |
| `test_the_count_query_counts_one_row_per_ortholog` | Count Cypher shape, valid |
| `test_a_taxon_never_becomes_a_row_and_odd_values_never_leak` | Four raw rows give four rows; list, dict, number and None items ignored; empty list writes no field; cap respected |
| `test_ortholog_row_shows_its_organism` | Organism column and the Plain language label |
| `test_gene_rows_without_an_organism_and_other_row_types_are_unchanged` | No organism leaves develop's output; the Layer 2 `gene` type is untouched; list, dict, number and empty values never render |

Against develop's three source files (swapped in through a probe copy and `-o pythonpath`): the new tools file fails at import (`FOLD_FIELD_ORGANISM` absent), and `test_ortholog_row_shows_its_organism` fails. The other layout arm passes on develop by design (it pins unchanged behavior).

## Commands and results

- The new tests plus `test_answer_layout.py`: 131 passed.
- `test_cypher_templates`, `_fold_templates`, `test_cypher_query`, `_query_templates`, `_budget`, `_e2e`, `_premise`, and `test_variant_record_label.py`: 168 passed, 32 skipped (live arms).
- `ruff check` (no path): all checks passed. `isort --check-only --diff src tests services tracker alembic .claude .github`: clean.
- `ruff format --check`: the three source files were already unformatted on develop, so they were left as is; the new test file is formatted.

## Outside the ticket

- If a future ortholog row ever has no `in_taxon` edge, it still lists, with no organism, as on develop.
- A single Researcher cell holds all taxon names joined by ", "; TP53's orthologs have one taxon each in the probe sample.
