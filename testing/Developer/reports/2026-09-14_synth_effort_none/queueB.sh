#!/bin/bash
set -e
cd "<repo-root>/testing/Developer/reports/2026-09-14_synth_effort_none"
python3 measure_write2.py --depth researcher --runs 5 "Which diseases are associated with BRCA1 and BRCA2?" r4.jsonl
python3 measure_write2.py --depth researcher --runs 5 "what diseases are linked to brca1?" r5.jsonl
python3 measure_write2.py --depth plain_language --runs 5 "Which diseases are associated with BRCA1?" p1.jsonl
python3 measure_write2.py --depth plain_language --runs 5 "Variants in GCK causing MODY" p2.jsonl
echo QUEUE_B_DONE
