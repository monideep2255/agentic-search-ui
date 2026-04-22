# Next steps for Phase 4.0 (handoff)

Temporary working doc. Delete after Gate 3 close-out is merged.

## Current state at 2026-04-22 ~11:55 ET

Gate 3 functionally PASSES. Full load complete. All 3 smoke queries return correct results.

Complete:
- Hetzner CPX42 at 46.225.128.133, Postgres 15.17 + AGE 1.5.0
- 144 GB merged KGX loaded: 115,406,761 nodes, 693,295,991 edges
- All 11 vertex labels have B-tree `agtype_to_text(properties -> '"id"')` functional indexes (from loader)
- GIN indexes on Gene, Disease, BiologicalProcess, SequenceVariant properties (added 2026-04-22 after Problem 12 — B-tree functional indexes do not match the `properties @>` containment filter the Cypher engine emits)
- B-tree indexes on `start_id` and `end_id` for 3 edge tables used in smoke queries: `is_sequence_variant_of`, `gene_associated_with_condition`, `participates_in`

Smoke-test results (2026-04-22):

| Query | Shape | Time | Result |
|-------|-------|------|--------|
| Q1 BRCA1 variants | Gene → is_sequence_variant_of → SequenceVariant | 229 ms | 20 ClinVar variants |
| Q2 PKU gene | Disease(MedGen:C0031485) → gene_associated_with_condition → Gene | 2:23 | PAH (NCBIGene:5053) |
| Q3 glucose metabolism | Gene → participates_in → BiologicalProcess | 218 ms | Hexokinases, glucokinase, G6PD, etc. |

Reproducible query suite: `tests/cypher/gate3_queries.sql`
Saved results: `tests/cypher/gate3_results_2026-04-22.txt`

## Known data-quality issue (not blocking Gate 3)

MedGen Disease nodes have `name` populated with source-vocabulary codes like `"SNOMEDCT_US"` instead of human-readable disease names. Root cause is in the MedGen ETL (Phase 1). Filed as a Phase-2 followup — does not affect graph traversals, only display text.

## Gate 3 close-out checklist

1. [ ] Update canonical docs:
   - [ ] `docs/bossman_execution_plan.md` — Phase 4.0 row to DONE, Gate 3 row to DONE
   - [ ] `docs/learnings.md` — Problem 12 + Gate 3 outcome section added (in progress)
   - [ ] `docs/data_inventory.md` — final counts (115.4M nodes, 693.3M edges) + index list
   - [ ] `DECISIONS.md` — new rows for GIN index decision + typed-edge query convention
2. [ ] Tier 1 mirrors (CLAUDE.md, AGENTS.md, README.md) — mark V1 complete
3. [ ] Update loader/index_builder.py to emit GIN + edge-endpoint B-tree indexes (so next deploy has them from Step 8, not manually)
4. [ ] qa-gate (pytest, doc compliance, eval-harness)
5. [ ] Commit on phase/4.0-cloud-deploy, push, open PR to main
6. [ ] After PR merged:
   - [ ] Hetzner snapshot via console (~$1-2/mo)
   - [ ] Downgrade VPS CPX42 → CPX32 (save ~$10/mo)
   - [ ] Delete `data/kgx/merged/` on laptop (frees ~135 GB; FTP cache stays)
   - [ ] Delete `NEXT_STEPS.md` (this file)

## How to query the KG yourself

```bash
ssh root@46.225.128.133
sudo -u postgres psql -d ncbi_kg
```

Every psql session needs:
```sql
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
\timing on
```

Then Cypher via `cypher()`:
```sql
SELECT * FROM cypher('ncbi_kg', $$
    MATCH (g:Gene {id: 'NCBIGene:672'})-[:is_sequence_variant_of]-(v:SequenceVariant)
    RETURN g.name, v.id LIMIT 20
$$) as (gene agtype, variant_id agtype);
```

Three rules:
1. Always specify the edge label (`[:is_sequence_variant_of]` not `[r]`). Untyped edges force the planner to scan all 14 edge tables.
2. Match by `id` with the right CURIE prefix: `NCBIGene:`, `MedGen:`, `GO:`, `NCBITaxon:`, `PMID:`, `ClinVar:`. To discover prefixes for a label: `MATCH (n:Disease) RETURN n.id LIMIT 5`.
3. The SQL function signature `as (col1 agtype, ...)` arity/order must match the Cypher `RETURN`.

To run the canonical test suite:
```bash
sudo -u postgres psql -d ncbi_kg -f /tmp/gate3_queries.sql
```

## References

- `tests/cypher/gate3_queries.sql` — canonical smoke query suite
- `tests/cypher/gate3_results_2026-04-22.txt` — latest pass results
- `docs/learnings.md` Problems 1-12 — every issue hit during Phase 4.0
- `DECISIONS.md` rows 67-75 — decisions log
- `scripts/rsync-retry.sh` — retry wrapper that survived 121 reconnects

Last updated: 2026-04-22 11:55 ET
