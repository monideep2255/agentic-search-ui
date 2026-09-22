"""Did the server finish the runs the sleeping client abandoned?

Companion to run_consistency.py. For every record in runs.jsonl whose outcome
is `no_done` (the client machine slept mid-stream, see findings.md), sign in as
the account that ran it, list that account's history, and find the row for the
same question asked within 90 seconds of the record's start. A history row is
written only when a run captures an interaction, so its presence, trust signal
and citation count say whether the server completed the run after the client
vanished. Read-only: one sign-in and one history read per account, no query,
no NCBI call.

Usage: python3 check_server_side.py <out_dir> --accounts <accounts.json>
Writes <out_dir>/server_side_check.json and prints one line per abandoned run.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_BASE = "https://search-agent-api-develop-43b3.up.railway.app"
WINDOW = timedelta(seconds=90)


def _post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _get(base, path, bearer):
    req = urllib.request.Request(base + path)
    req.add_header("Authorization", "Bearer " + bearer)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def history_for(base, account):
    bearer = _post(base, "/auth/login", account)["access_token"]
    for limit in (200, 100, 50):
        try:
            return _get(base, f"/v1/history?limit={limit}", bearer)
        except urllib.error.HTTPError as exc:
            if exc.code != 422:
                raise
    raise RuntimeError("no accepted history limit")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--accounts", required=True)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--outcome", default="no_done")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    accounts = {a["email"]: a for a in json.loads(Path(args.accounts).read_text())}
    records = [
        json.loads(line)
        for line in (out_dir / "runs.jsonl").read_text().splitlines()
        if line.strip()
    ]
    for extra in ("runs_client_asleep.jsonl",):
        p = out_dir / extra
        if p.exists():
            records += [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
    abandoned = [r for r in records if r.get("outcome") == args.outcome]
    print(f"{len(abandoned)} abandoned run(s) with outcome {args.outcome}")

    histories = {}
    results = []
    for rec in abandoned:
        email = rec["account"]
        if email not in histories:
            histories[email] = history_for(args.base, accounts[email])
        items = histories[email].get("items", [])
        started = datetime.fromisoformat(rec["started_at"])
        matches = []
        for item in items:
            if item.get("question") != rec["question"]:
                continue
            asked = datetime.fromisoformat(item["asked_at"])
            if abs(asked - started) <= WINDOW:
                matches.append(item)
        row = {
            "id": rec["id"],
            "pass": rec["pass"],
            "run_id": rec.get("run_id"),
            "started_at": rec["started_at"],
            "client_seconds": rec.get("seconds"),
            "history_rows_total": histories[email].get("count"),
            "matches": matches,
            "server_completed": bool(matches),
        }
        results.append(row)
        desc = (
            ", ".join(
                f"trust={m.get('trust_signal')} citations={m.get('citation_count')} asked_at={m.get('asked_at')}"
                for m in matches
            )
            or "NO history row within 90 s"
        )
        print(f"{rec['id']} pass {rec['pass']} ({email.split('@')[0]}): {desc}")

    (out_dir / "server_side_check.json").write_text(json.dumps(results, indent=1))
    print("written", out_dir / "server_side_check.json")


if __name__ == "__main__":
    main()
