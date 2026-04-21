# Next steps for Phase 4.0 (handoff)

Temporary working doc. Captures state as of 2026-04-21 ~18:40 ET, what's running unattended on the VPS, and the resume plan.

Delete this file after Gate 3 closes and the canonical docs (bossman_execution_plan.md, learnings.md, DECISIONS.md, data_inventory.md) are updated.

## Current state at 2026-04-21 ~18:40 ET

Complete:
- Hetzner CPX42 provisioned at 46.225.128.133, Postgres 15.17 + AGE 1.5.0 installed
- 144 GB merged KGX rsynced to VPS (complete 2026-04-20 17:38)
- Data verified structurally: Python csv module reports 0 mismatches on both nodes.tsv (115,406,761 rows) and edges.tsv (693,295,991 rows). Awk had flagged 64,882 node "mismatches" but those were PubMed abstracts with embedded newlines inside quoted TSV fields; csv parses them correctly. Investigation closed, data is clean.
- kgx validate on VPS was attempted but crashed with a Python TypeError (tool bug, not data). Skipped. Four independent proofs of BioLink compliance already exist from Gate 2.
- age-load attempt 1 failed with pg_hba auth error. Fixed by adding trust for postgres on localhost. pg_hba.conf updated.
- age-load attempt 2 failed with `UndefinedTable: ncbi_kg.NamedThing`. Fixed by adding NamedThing to VERTEX_LABELS in loader/schema.py and scp'ing to VPS.
- age-load attempt 3 OOM-killed after Step 5 (curie_to_id dict exceeded 16 GB RAM). Fixed by adding 16 GB swap file, persistent via fstab.
- Phase 4.0 checkpoint commit shipped as 7c06457 on branch phase/4.0-cloud-deploy, pushed to GitHub. Mid-phase updates shipped as 90adb07.

Running unattended on the VPS as of 2026-04-21 ~18:40 ET:
- age-load attempt 4 (PID 78503 started at 19:11 UTC = 15:11 ET)
- Step 5 (node load): DONE, 115,406,761 nodes in 41 min
- Step 6 (curie_to_id dict build): DONE, 115,406,761 entries in 48 min under swap pressure
- Step 7 (edge load): IN PROGRESS, 89M of 693M edges loaded as of 17:44 ET at ~23,000 edges/sec, swap stable around 13 GB
- Step 8 (index build): NOT YET STARTED, runs after edge load completes

Expected overnight trajectory:
- Edge load finishes around 22:00-01:00 ET
- Step 8 index build runs 10-30 min after edges done
- Full load should be complete by morning

## How to resume tomorrow

First command in the chat: say "check age-load" and I will ssh to the VPS and report state.

Three possible states to find:

State 1, full load COMPLETE (edges + indexes all done). Log ends with a "pipeline done" line and a total rows/edges summary. Proceed to Cypher test queries.

State 2, edges done but Step 8 index build still running. Log shows `Step 7 load_edges: ... in Xs` but no `Step 8 indexes` line yet. Wait for index build to finish, then Cypher.

State 3, age-load died overnight. PID gone, log ends with a traceback or mid-progress. Check `free -h` for swap state, `dmesg | grep -i oom` for OOM signatures. If OOM again, either (a) accept the partial state and investigate or (b) upgrade to CPX52 and relaunch with --drop-existing. User decides.

## Cypher test queries (after full load complete)

Three queries to validate the graph works end to end:

```cypher
-- Q1: Gene to variant traversal
SELECT * FROM cypher('ncbi_kg', $$
    MATCH (g:Gene {id: 'NCBIGene:672'})-[r]-(v:SequenceVariant)
    WHERE v.clinical_significance CONTAINS 'Pathogenic'
    RETURN g.name, v.id, v.clinical_significance
    LIMIT 20
$$) as (gene agtype, variant_id agtype, clinsig agtype);

-- Q2: Disease to gene traversal (phenylketonuria to PAH)
SELECT * FROM cypher('ncbi_kg', $$
    MATCH (d:Disease)-[:gene_associated_with_condition]-(g:Gene)
    WHERE d.name =~ '(?i).*phenylketonuria.*' OR d.id = 'MONDO:0009861'
    RETURN d.id, d.name, g.id, g.name
$$) as (disease_id agtype, disease_name agtype, gene_id agtype, gene_name agtype);

-- Q3: Human genes involved in glucose metabolism
SELECT * FROM cypher('ncbi_kg', $$
    MATCH (g:Gene)-[:participates_in]->(p:BiologicalProcess)
    WHERE p.name =~ '(?i).*glucose metabolism.*'
    RETURN g.name, p.name LIMIT 50
$$) as (gene agtype, process agtype);
```

Run on VPS via `sudo -u postgres psql -d ncbi_kg` or through the loader's venv.

If all 3 return expected-looking results, Gate 3 passes.

## Gate 3 close-out tasks (after Cypher passes)

1. Update canonical docs to mark Phase 4.0 + Gate 3 DONE:
   - docs/bossman_execution_plan.md (Phase 4.0 row, Realistic calendar, Plan overview Mermaid)
   - docs/learnings.md (Gate 3 outcome)
   - docs/data_inventory.md (final counts in AGE graph)
   - DECISIONS.md (close-out row)
2. Tier 1 mirrors: CLAUDE.md, AGENTS.md, README.md to V1 complete
3. qa-gate (pytest, doc compliance, eval-harness)
4. Commit on phase/4.0-cloud-deploy, push, open PR to main
5. After PR merged:
   - Delete /root/data/kgx/merged/ on VPS (frees ~135 GB)
   - Delete data/kgx/merged/ on laptop (frees ~135 GB; FTP cache stays)
   - Hetzner snapshot via console (~$1-2/mo)
   - Downgrade VPS CPX42 to CPX32 (saves ~$10/mo, ~$24/mo steady state)

## Billing worry, addressed

Independently verified with Perplexity on 2026-04-21 ~18:40 ET. Confirmed:

1. Hetzner Cloud is flat monthly billing (prorated hourly), not per-CPU-usage
2. 100% CPU vs idle on a CPX42 costs the same per hour
3. CPX42 rate is roughly $0.05/hour, capped ~$34/month
4. Large bills come from volumes, many instances, bandwidth overages, or forgotten resources - NOT from a long-running load
5. On a single CPX42 with no extra volumes or unusual bandwidth, one night of 100% CPU cannot generate a bill in the hundreds of dollars

Worst case overnight is about $0.75 added to the VPS's steady monthly cost. Not $500. Not $50. Not $5.

## Open items NOT blocking Gate 3

- kgx Python TypeError "unhashable type: list" is a tool bug worth filing upstream, not a data issue
- Loader's in-memory curie_to_id dict design is brittle at >100M node scale; a future refactor could use SQLite or LMDB to avoid the swap dependency
- When we add Protein, SmallMolecule, or any other BioLink category in a future pipeline, the loader's VERTEX_LABELS constant will need updating or should be made data-driven

## References

- docs/bossman_execution_plan.md - Phase 4.0 section
- docs/learnings.md - Phase 4.0 execution section, Problems 1 through 9 + Understanding subsections (retry loop, --append, streaming pattern, awk vs kgx, drop-existing, time vs money)
- DECISIONS.md - rows 67 through 73 capture all Phase 4.0 decisions
- scripts/rsync-retry.sh - the retry wrapper that survived the 121 reconnects

Last updated: 2026-04-21 ~18:40 ET
