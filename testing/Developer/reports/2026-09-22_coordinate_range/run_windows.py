"""Live runs of the two window questions that are not golden rows, through the
consistency run's own client, so the records land in this folder in the same
shape as every other live measurement.

Usage, from the repository root:

    python testing/Developer/reports/2026-09-22_coordinate_range/run_windows.py \\
        --accounts <path to a JSON list of sign-in bodies, never committed> \\
        --passes 3 --base https://search-agent-api-develop-43b3.up.railway.app --commit <sha>

Two rows: a CFTR-locus window on chromosome 7 with GRCh38 named, and the BRCA1
window with no assembly named, which should be answered with the assembly
question rather than searched. The golden coordinate question itself (G-001)
is run with `run_consistency.py` as usual. One worker, the laptop kept awake
by the caller.
"""
import argparse
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(".")
CLIENT = ROOT / "testing" / "Developer" / "reports" / "2026-09-22_10.3_consistency" / "run_consistency.py"
OUT = ROOT / "testing" / "Developer" / "reports" / "2026-09-22_coordinate_range"

ROWS = [
    {
        "id": "W-CFTR",
        "question": "What genes and ClinVar records are under chr7:117,480,025-117,668,665 on GRCh38?",
        "search_category": "kiss",
        "query_class": "multi_hop",
        "expected_outcome": "answer",
    },
    {
        "id": "W-NOASM",
        "question": "What is under chr17:43,044,295-43,125,364?",
        "search_category": "kiss",
        "query_class": "multi_hop",
        "expected_outcome": "ask",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", required=True)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--base", required=True)
    parser.add_argument("--commit", default="unknown")
    args = parser.parse_args()

    spec = importlib.util.spec_from_file_location("run_consistency", CLIENT)
    assert spec is not None and spec.loader is not None
    client = importlib.util.module_from_spec(spec)
    sys.modules["run_consistency"] = client
    spec.loader.exec_module(client)

    accounts = json.loads(pathlib.Path(args.accounts).read_text())
    account = accounts[0]
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    jsonl = OUT / "runs.jsonl"
    done = set()
    if jsonl.exists():
        for line in jsonl.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                done.add((record["id"], record["pass"]))
    for row in ROWS:
        for pass_index in range(1, args.passes + 1):
            if (row["id"], pass_index) in done:
                continue
            record, raw = client.run_once(args.base, account, row, pass_index, "w1", args.commit)
            with jsonl.open("a") as handle:
                handle.write(json.dumps(record) + "\n")
            with (OUT / "raw" / f"{row['id']}_run{pass_index}.json").open("w") as handle:
                json.dump(raw, handle)
            print(row["id"], pass_index, record.get("outcome"), record.get("seconds"), "s")


if __name__ == "__main__":
    main()
