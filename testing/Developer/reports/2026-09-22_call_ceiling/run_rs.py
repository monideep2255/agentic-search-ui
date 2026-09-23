"""Live runs of one question shape the golden set does not carry, several rs
numbers in one question, through the consistency run's own client, into this
folder in the same shape as every other live measurement.

Usage, from the repository root:

    python testing/Developer/reports/2026-09-22_call_ceiling/run_rs.py \\
        --accounts <path to a JSON list of sign-in bodies, never committed> \\
        --passes 3 --base https://search-agent-api-develop-43b3.up.railway.app --commit <sha>

The fix plan's call-ceiling item names this shape as the one that could
still reach twenty Layer 2 and 3 calls, since each rs number earns a dbSNP
and a LitVar2 call. One worker, the laptop kept awake by the caller.
"""
import argparse
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(".")
CLIENT = ROOT / "testing" / "Developer" / "reports" / "2026-09-22_10.3_consistency" / "run_consistency.py"
OUT = ROOT / "testing" / "Developer" / "reports" / "2026-09-22_call_ceiling"

ROWS = [
    {
        "id": "R-THREE-RS",
        "question": "What conditions are rs334, rs1801133 and rs429358 associated with?",
        "search_category": "kiss",
        "query_class": "multi_hop",
        "expected_outcome": "answer",
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

    account = json.loads(pathlib.Path(args.accounts).read_text())[0]
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
