"""One live run of a question against develop, keeping the token events the
consistency runner drops, so the code-built table under an isolate answer
can be read as the web app receives it: each token's kind and its cells.

Usage, from the repository root:

    caffeinate -i python testing/Developer/reports/2026-09-22_isolate_search/capture_tokens.py \\
        --accounts <path to a JSON list of sign-in bodies, never committed> \\
        --question "What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?" \\
        --out testing/Developer/reports/2026-09-22_isolate_search/round2/tokens_G-035.json
"""
import argparse
import importlib.util
import json
import pathlib
import sys
import time
import uuid

ROOT = pathlib.Path(".")
CLIENT = ROOT / "testing" / "Developer" / "reports" / "2026-09-22_10.3_consistency" / "run_consistency.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--base", default="https://search-agent-api-develop-43b3.up.railway.app")
    args = parser.parse_args()

    spec = importlib.util.spec_from_file_location("run_consistency", CLIENT)
    assert spec is not None and spec.loader is not None
    client = importlib.util.module_from_spec(spec)
    sys.modules["run_consistency"] = client
    spec.loader.exec_module(client)

    account = json.loads(pathlib.Path(args.accounts).read_text())[0]
    bearer = client.sign_in(args.base, account)
    session_id = "c103-" + uuid.uuid4().hex[:12]
    t0 = time.time()
    created = client._post(args.base, "/v1/query", {"text": args.question, "session_id": session_id}, bearer)
    events, timed_out = client.stream(args.base, created["run_id"], bearer, t0 + client.RUN_DEADLINE_S)
    seconds = round(time.time() - t0, 1)
    tokens = [e.get("payload") or {} for e in events if e.get("type") == "token"]
    kinds: dict[str, int] = {}
    for token in tokens:
        kinds[str(token.get("kind"))] = kinds.get(str(token.get("kind")), 0) + 1
    table_rows = [t for t in tokens if t.get("kind") == "table_row"]
    headers = [t for t in tokens if t.get("kind") == "table_header"]
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"question": args.question, "seconds": seconds, "timed_out": timed_out, "events": events}))
    print("seconds", seconds, "timed_out", timed_out)
    print("token kinds", json.dumps(kinds))
    print("table headers", json.dumps([h.get("cells") for h in headers]))
    for row in table_rows[:3]:
        print("table row", json.dumps(row.get("cells")))
    print("table rows", len(table_rows))


if __name__ == "__main__":
    main()
