"""Live runs of the isolate questions the golden set does not carry, through
the consistency run's own client, into this folder in the same shape as every
other live measurement. G-035 itself is a golden row and is run with
`run_consistency.py --ids G-035`.

Usage, from the repository root:

    caffeinate -i python testing/Developer/reports/2026-09-22_isolate_search/run_isolate_extra.py \\
        --accounts <path to a JSON list of sign-in bodies, never committed> \\
        --passes 2 --base https://search-agent-api-develop-43b3.up.railway.app --commit <sha>

The rows mirror `testing/Isolate_search_queries_and_workflow.md`: a second
organism, an explicit allele, a second family, a true zero, the two
clarifications, the older single-isolate mode, and the shortest phrasing.
"""
import argparse
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(".")
CLIENT = ROOT / "testing" / "Developer" / "reports" / "2026-09-22_10.3_consistency" / "run_consistency.py"
OUT = ROOT / "testing" / "Developer" / "reports" / "2026-09-22_isolate_search"

ROWS = [
    {
        "id": "R-SALMONELLA-ESBL",
        "question": "Which Salmonella isolates in Pathogen Detection carry ESBL genes?",
        "search_category": "kisses",
        "query_class": "exploratory",
        "expected_outcome": "answer",
    },
    {
        "id": "R-CTXM15",
        "question": "Which Salmonella isolates carry blaCTX-M-15?",
        "search_category": "kisses",
        "query_class": "exploratory",
        "expected_outcome": "answer",
    },
    {
        "id": "R-KLEBSIELLA-CARBAPENEMASE",
        "question": "Which Klebsiella isolates in Pathogen Detection carry carbapenemase genes?",
        "search_category": "kisses",
        "query_class": "exploratory",
        "expected_outcome": "answer",
    },
    {
        "id": "R-LISTERIA-ZERO",
        "question": "Which Listeria isolates in Pathogen Detection carry blaKPC?",
        "search_category": "kisses",
        "query_class": "exploratory",
        "expected_outcome": "answer",
    },
    {
        "id": "R-NO-ORGANISM",
        "question": "Which tomato isolates in Pathogen Detection carry resistance genes?",
        "search_category": "kiss",
        "query_class": "lookup",
        "expected_outcome": "refuse",
    },
    {
        "id": "R-NO-GENE",
        "question": "Which E. coli isolates are in Pathogen Detection?",
        "search_category": "kiss",
        "query_class": "lookup",
        "expected_outcome": "refuse",
    },
    {
        "id": "R-TERSE",
        "question": "ESBL E. coli isolates?",
        "search_category": "kisses",
        "query_class": "exploratory",
        "expected_outcome": "answer",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", required=True)
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument("--base", required=True)
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--out", default=str(OUT), help="run folder; a later round goes in its own subfolder")
    parser.add_argument("--ids", default="", help="comma-separated row ids; default all")
    args = parser.parse_args()
    out = pathlib.Path(args.out)
    wanted = {i.strip() for i in args.ids.split(",") if i.strip()}

    spec = importlib.util.spec_from_file_location("run_consistency", CLIENT)
    assert spec is not None and spec.loader is not None
    client = importlib.util.module_from_spec(spec)
    sys.modules["run_consistency"] = client
    spec.loader.exec_module(client)

    account = json.loads(pathlib.Path(args.accounts).read_text())[0]
    (out / "raw").mkdir(parents=True, exist_ok=True)
    jsonl = out / "runs.jsonl"
    done = set()
    if jsonl.exists():
        for line in jsonl.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                done.add((record["id"], record["pass"]))
    for row in ROWS:
        if wanted and row["id"] not in wanted:
            continue
        for pass_index in range(1, args.passes + 1):
            if (row["id"], pass_index) in done:
                continue
            record, raw = client.run_once(args.base, account, row, pass_index, "w1", args.commit)
            with jsonl.open("a") as handle:
                handle.write(json.dumps(record) + "\n")
            with (out / "raw" / f"{row['id']}_run{pass_index}.json").open("w") as handle:
                json.dump(raw, handle)
            print(row["id"], pass_index, record.get("outcome"), record.get("seconds"), "s", flush=True)


if __name__ == "__main__":
    main()
