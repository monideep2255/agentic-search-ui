"""Render the live-proof run files as one Markdown table plus per-question
summaries: outcome, table rows, distinct diseases named in the table,
source-set hash, elapsed, first sentence. Reads the JSONL `measure_write2.py`
writes; adds nothing it did not record.

Usage: python3 analyze.py hnf1a_researcher.jsonl gck_mody_researcher.jsonl ...
"""

import hashlib
import json
import re
import statistics
import sys

FILES = sys.argv[1:]
_MARKER = re.compile(r"\s*\[\d{1,3}\]")

print("| Question | Depth | Run | Outcome | Elapsed s | Sources | Source set | Mapping rows | List rows | Distinct diseases in mapping | Placeholder note | First sentence |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
per_question: dict[str, dict] = {}
for path in FILES:
    with open(path) as handle:
        lines = handle.readlines()
    for index, line in enumerate(lines, start=1):
        r = json.loads(line)
        key = f"{r['question']} ({r['depth']})"
        source_hash = hashlib.sha256(json.dumps(sorted(r["sources"])).encode()).hexdigest()[:8]
        all_rows = r.get("table_rows", [])
        # The mapping table only: a trial row's first cell is a study title
        # and its second a status; a mapping row's second cell names diseases.
        table_rows = [c for c in all_rows if len(c) > 1 and c[1] not in ("RECRUITING", "COMPLETED", "UNKNOWN", "TERMINATED", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING", "WITHDRAWN", "SUSPENDED", "ENROLLING_BY_INVITATION", "")]
        distinct = set()
        for cells in table_rows:
            for name in (cells[1] if len(cells) > 1 else "").split(";"):
                if name.strip():
                    distinct.add(name.strip())
        note = "yes" if any("placeholder" in n for n in r.get("notes", [])) else "no"
        runon = any(("gene symbol:" in t or "Disease name:" in t) for t in r.get("claim_texts", []))
        first_col = f"{r['question'][:45]}{' RUN-ON' if runon else ''}"
        first = r["first_sentence"].replace("|", "/")[:140]
        print(
            f"| {first_col} | {r['depth']} | {index} | {r['outcome']} | {r['elapsed_s']} | "
            f"{r['source_count']} | {source_hash} | {len(table_rows)} | {r['list_rows']} | {len(distinct)} | {note} | {first} |"
        )
        q = per_question.setdefault(key, {"elapsed": [], "hashes": set(), "outcomes": [], "rows": [], "diseases": []})
        q["elapsed"].append(r["elapsed_s"])
        q["hashes"].add(source_hash)
        q["outcomes"].append(r["outcome"])
        q["rows"].append(len(table_rows))
        q["diseases"].append(len(distinct))

print()
print("| Question (depth) | Runs | Answered | Distinct source sets | Median elapsed s | Table rows per run | Distinct diseases per run |")
print("|---|---|---|---|---|---|---|")
all_elapsed = []
for key, q in per_question.items():
    answered = sum(1 for o in q["outcomes"] if o in ("answer", "ask", "flag"))
    all_elapsed.extend(q["elapsed"])
    print(
        f"| {key} | {len(q['elapsed'])} | {answered} | {len(q['hashes'])} | "
        f"{statistics.median(q['elapsed'])} | {q['rows']} | {q['diseases']} |"
    )
print()
print(f"Median elapsed over all runs: {statistics.median(all_elapsed) if all_elapsed else 'n/a'} s")
