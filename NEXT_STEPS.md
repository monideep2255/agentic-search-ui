# Next steps for Phase 4.0 (handoff for tomorrow)

Temporary working doc. Captures state as of 2026-04-20 ~20:15 ET, the open question that surfaced during VPS awk verification, and the action plan to close Gate 3.

Delete this file after Gate 3 closes and the canonical docs (bossman_execution_plan.md, learnings.md, DECISIONS.md, data_inventory.md) are updated.

## Current state

Done today:
- Hetzner CPX42 provisioned at 46.225.128.133
- PostgreSQL 15.17 + Apache AGE 1.5.0 built from source on VPS
- `ncbi_kg` database + `ncbi_kg` graph created (graphid 16969)
- Loader package deployed at `/root/repo/` with venv, psycopg2-binary, kgx, click, age-load CLI
- 144 GB merged KGX rsynced from laptop to VPS (`/root/data/kgx/merged/`); rsync completed 17:38 after 121 retry attempts
- All 3 files have Apr 17 timestamps (preserved from source): edges.tsv 92 GB, nodes.tsv 44 GB, merge_report.md 1.6 KB
- Phase 4.0 checkpoint commit shipped as `7c06457` on branch `phase/4.0-cloud-deploy`, pushed to GitHub

Started but did NOT complete today:
- On-VPS `kgx validate -i tsv` crashed at 1h48m elapsed with `unhashable type: 'list'` (Python TypeError inside the kgx tool, not a data issue)
- On-VPS awk verification (in progress as of writing): nodes.tsv done, edges.tsv still streaming
- AGE load: NOT started
- 3 Cypher test queries: NOT run
- Gate 3: NOT closed

## The open finding from awk verification

Awk on nodes.tsv reported:
- Header columns: 18
- Total data rows: 115,464,386
- Matching header NF=18: 115,399,504
- **Mismatched: 64,882 (~0.056%)**

This is a non-zero structural mismatch rate. Edges.tsv awk result still pending as of writing, but the same investigation pattern will apply to whatever it shows.

## What to investigate first thing tomorrow

The mismatched rows are most likely caused by tab characters embedded in node `name` or `description` fields, which split a single logical row into two TSV rows from awk's perspective. This is a TSV serialization issue, not a BioLink compliance issue. age-load uses the Python csv module with proper TSV dialect handling, so it MAY parse these rows correctly even though awk does not.

Investigation steps:

```bash
# 1. Pull a sample of mismatched rows on the VPS (before age-load)
ssh root@46.225.128.133 'cd /root/data/kgx/merged && \
  awk -F"\t" "NR==1 {n=NF; next} NF != n {print NR\":\"NF\"|\"\$0}" nodes.tsv | head -20 > /tmp/sample-bad-nodes.txt && \
  cat /tmp/sample-bad-nodes.txt'

# 2. Group mismatches by their NF count to see the distribution
ssh root@46.225.128.133 'cd /root/data/kgx/merged && \
  awk -F"\t" "NR==1 {n=NF; next} NF != n {counts[NF]++} END {for (k in counts) print \"NF=\"k\": \"counts[k]\" rows\"}" nodes.tsv'

# 3. If rows are mostly NF=17 or NF=19 (off-by-one), confirms embedded tabs
# If rows are wildly varying NF, suggests a different bug

# 4. Check whether the rows can be re-parsed by Python csv module:
ssh root@46.225.128.133 'cd /root/repo && source .venv/bin/activate && python3 -c "
import csv
mismatched = 0
total = 0
with open(\"/root/data/kgx/merged/nodes.tsv\", newline=\"\") as f:
    reader = csv.reader(f, delimiter=\"\t\", quoting=csv.QUOTE_NONE)
    header = next(reader)
    print(f\"header NF={len(header)}\")
    for row in reader:
        total += 1
        if len(row) != len(header):
            mismatched += 1
print(f\"csv module sees: total={total}, mismatched={mismatched}\")
"'
```

Three outcomes from the investigation:

1. **csv module also reports mismatches**: real serialization bug. Fix in System 1 by quoting the offending fields in `kgx_exporter.py`, regenerate the affected pipelines from FTP cache, re-merge, re-rsync. Cost: a few hours of pipeline work.
2. **csv module reports 0 mismatches**: awk was confused by an edge case (e.g., quoted fields with embedded tabs that csv handles correctly). Safe to proceed with age-load. Document the discrepancy.
3. **age-load itself fails on the bad rows**: fall back to option 1.

Quick sanity check before deep investigation: spot-check 2 or 3 of the bad rows visually. If they show obvious tab-in-name issues like `... \t\tname with a tab\t...`, the cause is settled and the fix is the csv module check above.

## After the investigation

If the data is determined safe (csv module clean, OR investigation completes with a fix in place):

1. Launch age-load on the VPS as nohup background:
   ```bash
   ssh root@46.225.128.133 "nohup bash -c 'cd /root/repo && source .venv/bin/activate && AGE_DSN=\"host=localhost dbname=ncbi_kg user=postgres\" age-load --kgx-dir /root/data/kgx/merged --graph-name ncbi_kg --drop-existing' > /root/age-load.log 2>&1 & echo \"PID: \$!\""
   ```
2. Wait 2-4 hours for age-load to finish (runs unattended; laptop can sleep)
3. Run the 3 Cypher test queries against the loaded graph:
   - BRCA1 → pathogenic variants traversal
   - Phenylketonuria → PAH gene traversal
   - Human genes involved in glucose metabolism (Taxonomy + Gene + GO)
4. If all 3 return expected results, **Gate 3 passes** and V1 is complete

## Gate 3 close-out tasks

Once Cypher queries pass:

1. Update the four canonical docs to mark Phase 4.0 + Gate 3 DONE:
   - `docs/bossman_execution_plan.md` (Coding time table, Realistic calendar, Plan overview Mermaid diagram)
   - `docs/learnings.md` (add Gate 3 outcome notes)
   - `docs/data_inventory.md` (final node/edge counts in the AGE graph)
   - `DECISIONS.md` (close-out row if any new decisions surfaced)
2. Tier 1 mirrors: `CLAUDE.md`, `AGENTS.md`, `README.md` updated to reflect V1 complete
3. Run qa-gate (pytest, doc compliance, eval-harness)
4. Commit on `phase/4.0-cloud-deploy`, push, open PR for merge to main
5. After PR merged:
   - Delete `/root/data/kgx/merged/` on VPS (frees ~135 GB)
   - Delete `data/kgx/merged/` on laptop (frees ~135 GB; FTP cache stays for regeneration)
   - Hetzner snapshot via console (~$1-2/mo)
   - Downgrade VPS CPX42 → CPX32 (saves ~$10/mo, ~$24/mo steady state)

## Open items NOT blocking Gate 3

These can wait until after V1 ships:

- The kgx Python TypeError (`unhashable type: 'list'`) is a tool bug worth filing upstream. Not blocking us because Gate 2 already validated the same KGX on the laptop.
- The CPU-bound nature of kgx validate at this scale (1h48m for ~57% of 144 GB on a single core) is a future-pipeline concern. If we ever rerun validate at this scale, parallelize per file or chunk.

## References

- `docs/bossman_execution_plan.md` — Phase 4.0 section + decision rows 18, 25, 67
- `docs/learnings.md` — Phase 4.0 execution section, Problems 3 through 7 + Understanding subsections (retry loop, append, streaming pattern, awk vs kgx)
- `DECISIONS.md` — rows 64-67 capture all of today's mid-phase decisions
- `scripts/rsync-retry.sh` — the retry wrapper that survived the 121 reconnects

Last updated: 2026-04-20 ~20:15 ET
