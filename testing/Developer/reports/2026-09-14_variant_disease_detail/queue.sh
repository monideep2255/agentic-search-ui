#!/bin/bash
set -e
cd "<repo-root>/testing/Developer/reports/2026-09-14_variant_disease_detail"
python3 measure_write2.py --depth researcher --runs 5 "What diseases are caused by variants in the HNF1A gene?" hnf1a_researcher.jsonl
python3 measure_write2.py --depth researcher --runs 5 "Variants in GCK causing MODY" gck_mody_researcher.jsonl
python3 measure_write2.py --depth researcher --runs 5 "What genes are associated with MODY?" mody_genes_researcher.jsonl
python3 measure_write2.py --depth plain_language --runs 5 "What genes are associated with MODY?" mody_genes_plain.jsonl
python3 measure_write2.py --depth researcher --runs 5 "Which diseases are associated with BRCA1?" brca1_researcher.jsonl
python3 measure_write2.py --depth plain_language --runs 5 "Which diseases are associated with BRCA1?" brca1_plain.jsonl
echo QUEUE_DONE
