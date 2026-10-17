# Build report: card 37 slice A2, the writer is given the gene

## What changed, in the person's words

Asked "What is rs334 and what condition is it associated with?", the writer now sees one more fact: rs334 is in HBB, from rs334's own dbSNP record. A sentence "rs334 is in the HBB gene" passes the unchanged cite-or-refuse gate and is cited to that record. Nothing else changes.

## Diff summary

- `src/system_03_search_agent/synthesis/findings.py`: new closed table `_COMPANION_FIELDS` (`Variant record`, `genes` to `gene`) and helper `_with_companion_findings`, called once in `build_synth_findings` after admission and ordering are decided. The companion goes right after its row's last finding, with the row's `source_url`, `curie`, `entity_type`, `layer`, `tool` and `call_id`, never suspect.
- `src/system_03_search_agent/core/graph.py`, `_layer3_base_citation`: for `ncbi_dbsnp`, finding field `gene` is mapped to `genes` before `dbsnp_build_citation`.
- Design choice on the cap: a companion takes only a slot still free after the develop findings are admitted, and counts toward `capped` only when emitted. A list at the cap therefore shows exactly the records develop shows, and `capped` is unchanged. A full prompt means no gene sentence for that run.
- Nothing emitted when `genes` is missing, blank or not a string, when the row's own finding already uses it, or on a seen identity.

## Tests (`tests/system_03_search_agent/synthesis/test_gene_companion_finding.py`)

- rs334 row: `clinical_significance` first unchanged, then `gene` "HBB", same source, `db-1-2`, low risk. Fails on develop.
- Citation: `_layer3_base_citation` returns a dbsnp citation for rs334. Fails on develop.
- Gate: "rs334 is in the HBB gene [2]." passes `run_grounding_pass` unchanged (the question text is passed, as the gate requires) and cites the gene finding. Fails on develop.
- Trust: only the gene sentence surviving gives `answer`; with the significance claim also surviving, the most restrictive claim governs. Fails on develop.
- No companion without `genes`, or with blank or non-string values (passes on develop, guards the change).
- Other row types byte-identical in count and field: Layer 2 Gene, LitVar2 `Literature variant`, ClinVar record, graph `SequenceVariant` (passes on develop, guards).
- Cap: cap 3 shows the same three records as develop; cap 5 admits the companion; a list exactly at the cap is unchanged and not flagged capped. Fails on develop.

Verified by reverting my two source edits: 5 of 8 fail, the 3 guards pass.

## Commands

- New file plus `tests/system_03_search_agent/synthesis/` plus every core test naming `build_synth_findings` or `_layer3_base_citation`: 1284 passed, 10 skipped, 1 xfailed.
- `ruff check` (no path): clean. `isort --check-only --diff src tests services tracker alembic .claude .github`: clean.
- `ruff format --check` on `graph.py` and `findings.py` already reports pre-existing differences on develop; I did not reformat them. The new test file is formatted.

## Unsure or outside the ticket

- The gate licenses the gene sentence only when the question is passed; with an empty question the same sentence is stripped. In production the question is passed.
- The writer prompt gets no new instruction line (outside the fence); the writer may or may not choose to use the gene finding. Slice A1 shows the gene in the list regardless.
- Live G-024 before and after was not run (no model calls allowed for builders).
