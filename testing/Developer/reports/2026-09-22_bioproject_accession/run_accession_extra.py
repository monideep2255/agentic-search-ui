"""Live runs of two accession questions the golden set does not carry, through
the consistency run's own client, into this folder in the same shape as every
other live measurement. G-007 itself is a golden row and is run with
`run_consistency.py --ids G-007`.

Usage, from the repository root:

    python testing/Developer/reports/2026-09-22_bioproject_accession/run_accession_extra.py \\
        --accounts <path to a JSON list of sign-in bodies, never committed> \\
        --passes 2 --base https://search-agent-api-develop-43b3.up.railway.app --commit <sha>

The first question names an accession NCBI does not have: the answer should
say it was not found and ask for the accession to be checked, never ask for
a gene. The second names a BioSample, the second of the four accession kinds,
so the shape is shown to work off the one probed record.
"""
import argparse
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(".")
CLIENT = ROOT / "testing" / "Developer" / "reports" / "2026-09-22_10.3_consistency" / "run_consistency.py"
OUT = ROOT / "testing" / "Developer" / "reports" / "2026-09-22_bioproject_accession"

ROWS = [
    {
        "id": "R-UNKNOWN-ACCESSION",
        "question": "What is in BioProject PRJNA999999999?",
        "search_category": "kiss",
        "query_class": "lookup",
        "expected_outcome": "refuse",
    },
    {
        "id": "R-BIOSAMPLE",
        "question": "What is BioSample SAMN12121739 and which SRA runs and assemblies come from it?",
        "search_category": "kiss",
        "query_class": "multi_hop",
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
    parser.add_argument("--ids", default="", help="comma-separated row ids; default both")
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
            print(row["id"], pass_index, record.get("outcome"), record.get("seconds"), "s")


if __name__ == "__main__":
    main()
