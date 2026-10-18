"""Print, per trace, every sentence the check approved with the quotes the
judge read, the writer's own quotes and the cited record, then what the
screen showed. With --brief, one line per run.

Usage: python3 summarize.py [--brief] <label> [<label> ...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(text: str) -> str:
    return " ".join(re.sub(r"[()\[\]{}]", " ", text.lower()).split())


def approved(answer: dict) -> bool:
    p = answer.get("probabilities", {})
    return answer.get("choice") == "no" and (p.get("no") or 0) > (p.get("yes") or 0)


brief = "--brief" in sys.argv
for label in [a for a in sys.argv[1:] if a != "--brief"]:
    rows = [json.loads(line) for line in (HERE / f"{label}.jsonl").read_text().splitlines()]
    findings = next((r["data"] for r in rows if r["tag"] == "FINDINGS"), [])
    checks = [r["data"] for r in rows if r["tag"] == "CHECK_IN"]
    jevs = [r["data"] for r in rows if r["tag"] in ("JEV_RESULT", "JEV_RAISED")]
    tokens = [r["data"] for r in rows if r["tag"] == "TOKEN"]
    done = next((r["data"] for r in rows if r["tag"] == "DONE"), {})
    sent = sum(c["n"] for c in checks)
    ok = []
    for n, check in enumerate(checks):
        answers = jevs[n].get("answers", {}) if n < len(jevs) else {}
        for i, item in enumerate(check["items"], start=1):
            a = answers.get(f"item_{i}", {})
            if approved(a):
                ok.append((n + 1, i, a["probabilities"].get("no"), item))
    claims = [t for t in tokens if t.startswith("claim: ")]
    prose = [t for t in claims if not re.match(r"claim: (Found|I found) \d", t)]
    shown_ok = [t for t in prose if any(norm(item["sentence"])[:60] in norm(t) for *_, item in ok)]
    fmf = any("familial mediterranean fever" in t.lower() for t in claims)
    if brief:
        print(f"{label}: sent {sent} in {len(checks)} call(s), approved {len(ok)}, prose sentences shown "
              f"{len(prose)} (of them model-approved {len(shown_ok)}), FMF named {fmf}, "
              f"outcome {done.get('trust_outcome')}, {done.get('elapsed_ms')} ms, ${done.get('total_cost_usd')}")
        continue
    print(f"===== {label}: {sent} sentences sent in {len(checks)} call(s), {len(ok)} approved, outcome {done}")
    for call, item_no, p_no, item in ok:
        print(f"\n[{label} c{call} i{item_no}] APPROVED p_no={p_no}")
        print(f"  S: {item['sentence']}")
        for q in item["quotes"]:
            print(f"  JUDGE READ: {q}")
        for q in item.get("writer_quotes", []):
            print(f"  WRITER QUOTED: {q}")
        for f in findings:
            if any(norm(q)[:80] in norm(f["text"]) for q in item["quotes"]):
                print(f"  RECORD [{f['ref']}] {f['url']}: {f['text'][:2500]}")
    print("\n--- shown:")
    for t in tokens:
        print("   ", t[:400])
    print()
