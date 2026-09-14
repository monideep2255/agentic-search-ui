"""Render measure_write.py JSONL files as the report's markdown tables."""
import hashlib
import json
import sys
from pathlib import Path

CASES = [
    ("n_brca1_plain.jsonl", "BRCA1 diseases"),
    ("n_brca1_researcher.jsonl", "BRCA1 diseases"),
    ("n_gck_researcher.jsonl", "GCK MODY variants"),
    ("n_gck_serial_researcher.jsonl", "GCK MODY variants (serial rerun)"),
    ("n_cftr_researcher.jsonl", "CFTR variants"),
    ("n_egfr_researcher.jsonl", "EGFR NSCLC and trials"),
    ("n_brca12_researcher.jsonl", "BRCA1 and BRCA2 diseases"),
    ("n_brca12_plain.jsonl", "BRCA1 and BRCA2 diseases"),
    ("n_brca1var_researcher.jsonl", "BRCA1 variants"),
    ("n_brca1var_plain.jsonl", "BRCA1 variants"),
]

print("| Case | Mode | Run | Outcome | First sentence | Words | Headings | List rows | Sources (hash) | Markers ok | URL sentence | Synth first s / words | Synth repair s / words | Elapsed s | Errors |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
worst_first = 0.0
worst_write = 0.0
for path, label in CASES:
    try:
        lines = Path(path).read_text().splitlines()
    except FileNotFoundError:
        continue
    for index, line in enumerate(lines, start=1):
        r = json.loads(line)
        sources = r["sources"]
        digest = hashlib.sha256(",".join(sources).encode()).hexdigest()[:8]
        first = [c for c in r["synth_calls"] if not c.get("repair")]
        repair = [c for c in r["synth_calls"] if c.get("repair")]
        f = f"{first[0]['wall_s']} / {first[0].get('reply_words', '?')}" if first else "none"
        rp = f"{repair[0]['wall_s']} / {repair[0].get('reply_words', '?')}" if repair else "none"
        if first:
            worst_first = max(worst_first, first[0]["wall_s"] or 0)
            worst_write = max(worst_write, sum(c.get("wall_s") or 0 for c in r["synth_calls"]))
        errors = "; ".join(f"{e['source']}/{e['error_class']}" for e in r["errors"]) or "none"
        print(
            f"| {label} | {r['depth']} | {index} | {r['outcome']} | {r['first_sentence'][:90]} | {r['words']} | "
            f"{len(r['headings'])} | {r['list_rows']} | {len(sources)} ({digest}) | "
            f"{'yes' if r['unmarked_claims'] == 0 else 'NO'} | {'YES' if r['has_source_url_sentence'] else 'no'} | "
            f"{f} | {rp} | {r['elapsed_s']} | {errors} |"
        )
print()
print(f"Worst first Synth call: {worst_first} s. Worst write step (first plus repair): {worst_write} s.")
if len(sys.argv) > 1:
    print()
    print("Source sets:")
    for path, label in CASES:
        try:
            lines = Path(path).read_text().splitlines()
        except FileNotFoundError:
            continue
        sets = {tuple(json.loads(line)["sources"]) for line in lines}
        for s in sets:
            print(f"- {label} / {path}: {len(s)} ids: {', '.join(s)}")
