"""Collect every (sentence, quotes) pair the traces sent to the sentence check
into one file, each with Jev's live verdict and the text of the record its
quotes came from, so a rejection can be classified against the whole record.

Usage: python3 build_pairs.py <label> [<label> ...]   -> pairs.jsonl, and a
readable listing on stdout.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(text: str) -> str:
    text = re.sub(r"[()\[\]{}]", " ", text.lower())
    return " ".join(text.split())


def find_record(quote: str, findings: list[dict]) -> dict | None:
    q = norm(quote)
    for f in findings:
        if q and q in norm(f["text"]):
            return f
    return None


pairs = []
for label in sys.argv[1:]:
    rows = [json.loads(line) for line in (HERE / f"{label}.jsonl").read_text().splitlines()]
    findings = next(r["data"] for r in rows if r["tag"] == "FINDINGS")
    checks = [r["data"] for r in rows if r["tag"] == "CHECK_IN"]
    jevs = [r["data"] for r in rows if r["tag"] in ("JEV_RESULT", "JEV_RAISED")]
    for call_no, check in enumerate(checks, start=1):
        answers = jevs[call_no - 1].get("answers", {}) if call_no - 1 < len(jevs) else {}
        for i, item in enumerate(check["items"], start=1):
            a = answers.get(f"item_{i}", {})
            p = a.get("probabilities", {})
            records = []
            for q in item["quotes"]:
                f = find_record(q, findings)
                records.append({"ref": f["ref"] if f else None, "url": f["url"] if f else None,
                                "text": f["text"] if f else None})
            pairs.append({
                "id": f"{label}-c{call_no}-i{i}", "run": label, "call": call_no, "item": i,
                "sentence": item["sentence"], "quotes": item["quotes"], "records": records,
                "live_choice": a.get("choice"), "live_p_no": p.get("no"), "live_p_yes": p.get("yes"),
                "live_approved": a.get("choice") == "no" and (p.get("no") or 0) > (p.get("yes") or 0),
            })

with open(HERE / "pairs.jsonl", "w") as out:
    out.writelines(json.dumps(pr, ensure_ascii=False) + "\n" for pr in pairs)

for pr in pairs:
    print(f"\n[{pr['id']}] {'APPROVED' if pr['live_approved'] else 'rejected'} p_no={pr['live_p_no']}")
    print(f"  S: {pr['sentence']}")
    seen = set()
    for q, r in zip(pr["quotes"], pr["records"]):
        print(f"  Q: {q}")
        if r["ref"] not in seen and r["text"]:
            seen.add(r["ref"])
            print(f"  R{r['ref']}: {r['text'][:1800]}")
print(f"\n{len(pairs)} pairs")
