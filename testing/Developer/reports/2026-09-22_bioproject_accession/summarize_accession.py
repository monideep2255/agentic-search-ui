"""The accession runs, and the guard retest, read from a run folder.

For every live run in the folder given on the command line: the outcome,
the time, the trust outcome and the Layer 2 and 3 calls spent from the done
event, the sources cited by NCBI database, which of the probed records the
answer names, whether a not-found answer appeared, and whether the answer
carries the "does not address the following entities" note the generic-word
guard exists to stop. Reads `runs.jsonl` and `raw/`, writes nothing.

    python testing/Developer/reports/2026-09-22_bioproject_accession/summarize_accession.py \\
        testing/Developer/reports/2026-09-22_bioproject_accession
"""
import collections
import json
import pathlib
import re
import sys

folder = pathlib.Path(sys.argv[1])
runs = [json.loads(line) for line in (folder / "runs.jsonl").read_text().splitlines() if line.strip()]
MARKS = {
    "PRJNA31257": re.compile(r"PRJNA31257"),
    "SAMN12121739": re.compile(r"SAMN12121739"),
    "an SRR run": re.compile(r"\bSRR\d+"),
    "GCF_/GCA_": re.compile(r"\bGC[FA]_\d+"),
    "Human Genome Project": re.compile(r"Human Genome Project", re.IGNORECASE),
}

print("| id | pass | outcome | seconds | trust | calls | sources by database | records named | not found? | entities note? |")
print("|---|---|---|---|---|---|---|---|---|---|")
for run in sorted(runs, key=lambda r: (r["id"], int(r["pass"]))):
    capture = folder / "raw" / f"{run['id']}_run{run['pass']}.json"
    trust = calls = None
    by_db: collections.Counter = collections.Counter()
    text = ""
    if capture.exists():
        with capture.open() as handle:
            raw = json.load(handle)
        text = raw.get("answer_text") or ""
        for e in raw.get("events", []):
            kind = e.get("type") or e.get("event")
            payload = e.get("payload", e)
            if kind == "done":
                trust = payload.get("trust_outcome")
                calls = payload.get("layer_calls_used")
            elif kind == "citation":
                by_db[str(payload.get("source") or "?")] += 1
    named = [name for name, pat in MARKS.items() if pat.search(text)]
    not_found = "was not found" in text
    note = "does not address the following entities" in text
    sources = ", ".join(f"{db} {n}" for db, n in sorted(by_db.items())) or "-"
    print(
        f"| {run['id']} | {run['pass']} | {run['outcome']} | {run.get('seconds')} | {trust} | {calls} | {sources} | "
        f"{', '.join(named) or '-'} | {'yes' if not_found else 'no'} | {'YES' if note else 'no'} |"
    )
