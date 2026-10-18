#!/bin/bash
# Card 101 round 2: 5 plain-language runs each of GERD, Mediterranean and bronchiolitis, interleaved.
S="${OUT_ROOT:?set OUT_ROOT to a folder outside the repository}"
WT="${REPO_ROOT:?set REPO_ROOT to the checkout}"
PY="${PYTHON:-python3}"
export REPO_ROOT="$WT" OUT_DIR="$S/live" ENV_FILE="${ENV_FILE:?set ENV_FILE to the main checkout .env}"
export USER_DB_URL="postgresql://postgres@localhost:5433/search_agent_users"
cd "$WT"
for i in ${RUNS:-1 2 3 4 5}; do
  for spec in "ge gerd" "me med" "br bronch"; do
    read -r p which <<< "$spec"
    label="$p$i"
    spent=$("$PY" -c "
import json,glob
t=0.0
for f in glob.glob('$S/live/*.jsonl'):
    for l in open(f):
        r=json.loads(l)
        if r['tag'] in ('DONE','ERROR'): t+=float(r['data'].get('total_cost_usd') or 0)
print(round(t,4))")
    echo "before $label: cumulative \$$spent"
    if [ "$("$PY" -c "print($spent > 0.42)")" = "True" ]; then echo STOP; exit 0; fi
    "$PY" "$WT/testing/Developer/reports/2026-10-06_card101/raw/check_every/trace_run.py" "$label" "$which" plain_language > "$S/live/$label.log" 2>&1
    echo "$label exit $?"
    grep '"tag": "DONE"\|"tag": "ERROR"\|"tag": "ELAPSED_S"' "$S/live/$label.jsonl" | cut -c1-200
  done
done
