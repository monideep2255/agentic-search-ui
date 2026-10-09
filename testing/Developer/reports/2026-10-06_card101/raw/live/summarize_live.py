"""Card 101 live answers: per answer, the sentences shown and the three
counts the brief names. No model call. Reads <label>.jsonl from OUT_DIR
(the raw answers stay outside the repository) and prints one block per answer.

Usage: OUT_DIR=<raw answers folder> python summarize_live.py gp1 gp2 ... gr2

Counted, per answer:
- shown: claim sentences on screen, without the code-built "I found N" line.
- risk factor: a shown sentence whose check candidate quotes the record's
  risk-factor sentence (the one naming "hiatal hernia"), or that names the
  sphincter or hiatal hernia itself.
- young dropped: a shown sentence whose candidate quote says "young
  children" and whose text says "children" without "young".
- hedge dropped: a shown sentence whose candidate quote says "potentially"
  and whose text carries no hedge word.
- transient kept: the risk-factor sentence keeps "transient".
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

OUT_DIR = Path(os.environ["OUT_DIR"])
HEDGE = re.compile(r"\b(potential\w*|may|might|possibl\w*|could|suspect\w*|likely|can be|perhaps)\b", re.IGNORECASE)


def norm(text: str) -> str:
    text = re.sub(r"\[[0-9#,\s]+\]", " ", text)
    return " ".join(re.sub(r"[()\[\]{}.,;:]", " ", text.lower()).split())


def summarize(label: str) -> dict:
    rows = [json.loads(x) for x in (OUT_DIR / f"{label}.jsonl").read_text().splitlines()]
    cands = {}
    for r in rows:
        if r["tag"] == "CHECK_IN":
            for it in r["data"]["items"]:
                cands[norm(it["sentence"])[:60]] = it
    shown = [t[len("claim: "):] for t in (r["data"] for r in rows if r["tag"] == "TOKEN")
             if t.startswith("claim: ") and not re.match(r"claim: (Found|I found) \d", t)]
    done = next((r["data"] for r in rows if r["tag"] in ("DONE", "ERROR")), {})
    out = {"label": label, "shown": len(shown), "risk_factor": 0, "transient_kept": 0, "young_dropped": 0,
           "hedge_dropped": 0, "seconds": round((done.get("elapsed_ms") or 0) / 1000, 1),
           "cost_usd": round(done.get("total_cost_usd") or 0, 4), "outcome": done.get("trust_outcome"),
           "sentences": []}
    for s in shown:
        it = cands.get(norm(s)[:60])
        quotes = " ".join(it["quotes"]).lower() if it else ""
        low = s.lower()
        tags = []
        if "hiatal hernia" in quotes or "sphincter" in low or "hiatal hernia" in low:
            out["risk_factor"] = 1
            tags.append("risk factor")
            if "transient" in low:
                out["transient_kept"] = 1
        if "young children" in quotes and re.search(r"\bchildren", low) and "young" not in low:
            out["young_dropped"] += 1
            tags.append("YOUNG DROPPED")
        if "potentially" in quotes and not HEDGE.search(low):
            out["hedge_dropped"] += 1
            tags.append("HEDGE DROPPED")
        out["sentences"].append((tags, "reworded" if it else "copied", s.strip()))
    return out


def main() -> None:
    for label in sys.argv[1:]:
        o = summarize(label)
        print(json.dumps({k: v for k, v in o.items() if k != "sentences"}))
        for tags, kind, s in o["sentences"]:
            print(f"   [{kind}{', ' + ', '.join(tags) if tags else ''}] {s}")


if __name__ == "__main__":
    main()
