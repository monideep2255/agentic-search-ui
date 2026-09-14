#!/bin/bash
set -e
cd "/Users/anuradhachakraborti/Desktop/Tech Skills/agentic-search-ui/testing/Developer/reports/2026-09-14_speed_fix"
python3 measure_write2.py --depth researcher --runs 5 "Which diseases are associated with BRCA1?" r1.jsonl
python3 measure_write2.py --depth researcher --runs 5 "What variants cause disease in BRCA1?" r2.jsonl
python3 measure_write2.py --depth researcher --runs 5 "Variants in GCK causing MODY" r3.jsonl
echo QUEUE_A_DONE
