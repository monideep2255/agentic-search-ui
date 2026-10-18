"""Print every (sentence, quotes) pair a trace sent to the sentence check with
Jev's verdict, for reading and classifying by hand.

Usage: python3 show_pairs.py <label> [<label> ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

for label in sys.argv[1:]:
    rows = [json.loads(line) for line in (HERE / f"{label}.jsonl").read_text().splitlines()]
    checks = [r for r in rows if r["tag"] == "CHECK_IN"]
    jevs = [r for r in rows if r["tag"] in ("JEV_RESULT", "JEV_RAISED")]
    done = [r for r in rows if r["tag"] in ("DONE",)]
    print(f"===== {label}: {len(checks)} check calls, {len(jevs)} jev calls, done={done[0]['data'] if done else None}")
    for call_no, check in enumerate(checks, start=1):
        jev = jevs[call_no - 1]["data"] if call_no - 1 < len(jevs) else {}
        answers = jev.get("answers", {})
        print(f"--- call {call_no}: {check['data']['n']} items, jev latency {jev.get('latency_ms')} ms, "
              f"cost {jev.get('cost_usd')}, model {jev.get('resolved_model')}")
        for i, item in enumerate(check["data"]["items"], start=1):
            a = answers.get(f"item_{i}", {})
            p = a.get("probabilities", {})
            verdict = "APPROVED" if a.get("choice") == "no" and p.get("no", 0) > p.get("yes", 0) else "rejected"
            print(f"[{label} c{call_no} i{i}] {verdict} choice={a.get('choice')} p_no={p.get('no')} p_yes={p.get('yes')}")
            print(f"   S: {item['sentence']}")
            for q in item["quotes"]:
                print(f"   Q: {q}")
    tokens = [r["data"] for r in rows if r["tag"] == "TOKEN"]
    print("--- shown:")
    for t in tokens:
        print("   ", t[:220])
