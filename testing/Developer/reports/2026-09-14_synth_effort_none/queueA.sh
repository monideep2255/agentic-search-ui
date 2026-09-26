#!/bin/bash
set -e
cd "<repo-root>/testing/Developer/reports/2026-09-14_synth_effort_none"
python3 measure_write2.py --depth researcher --runs 4 "Which diseases are associated with BRCA1?" smoke_test.jsonl
python3 measure_write2.py --depth researcher --runs 5 "What variants cause disease in BRCA1?" r2.jsonl
python3 measure_write2.py --depth researcher --runs 5 "Variants in GCK causing MODY" r3.jsonl
echo QUEUE_A_DONE
