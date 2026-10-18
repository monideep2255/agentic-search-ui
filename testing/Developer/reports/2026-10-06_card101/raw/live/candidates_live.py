"""Card 101 live answers: every check candidate that draws on the
risk-factor record sentence (its quotes name "hiatal hernia") or on a
"young children" or "potentially" quote, with its item verdict and any pair
that vetoed it, rebuilt with the shipped packing. No model call.

Usage: REPO_ROOT=<repo-root> OUT_DIR=<raw answers folder> python candidates_live.py gp1 ...
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ["REPO_ROOT"])
OUT_DIR = Path(os.environ["OUT_DIR"])
sys.path.insert(0, str(ROOT / "src"))

from system_03_search_agent.synthesis import sentence_check as sc
from system_03_search_agent.synthesis.grounding import SynthesisCandidate


def approves(a: dict) -> bool:
    p = a.get("probabilities") or {}
    return a["choice"] == "no" and p.get("no") is not None and p.get("yes") is not None and p["no"] > p["yes"]


def main() -> None:
    for label in sys.argv[1:]:
        rows = [json.loads(x) for x in (OUT_DIR / f"{label}.jsonl").read_text().splitlines()]
        jev = [r["data"] for r in rows if r["tag"] in ("JEV_RESULT", "JEV_RAISED")]
        checks = [r["data"] for r in rows if r["tag"] == "CHECK_IN"]
        k = 0
        for n, d in enumerate(checks, start=1):
            cands = [SynthesisCandidate(key=(str(i), tuple(it["writer_quotes"])), sentence=it["sentence"],
                                        quotes=tuple(it["quotes"])) for i, it in enumerate(d["items"], start=1)]
            _state, sent = sc.build_jev_state(cands)
            calls, _not_asked = sc.build_pair_calls(sent)
            mine = jev[k:k + 1 + len(calls)]
            k += 1 + len(calls)
            answers = {}
            for call in mine:
                answers.update(call.get("answers") or {})
            pair_of = {}
            for call in calls:
                for key, item in call.items.items():
                    pair_of[key] = item
            phrases = {i: sc._proposed_pairs(c.sentence, c.quotes) for i, c in enumerate(sent, start=1)}
            for i, it in enumerate(d["items"], start=1):
                q = " ".join(it["quotes"]).lower()
                if not ("hiatal hernia" in q or "young children" in q or "potentially" in q):
                    continue
                item_ok = approves(answers.get(f"item_{i}", {"choice": None}))
                vetoes = []
                for key, item in pair_of.items():
                    if item == i and not approves(answers.get(key, {"choice": None})):
                        j = int(key.split("_")[2])
                        p = (answers.get(key, {}).get("probabilities") or {}).get("no")
                        vetoes.append((phrases[i][j - 1][0], round(p or 0, 2)))
                topic = "risk" if "hiatal hernia" in q else ("young" if "young children" in q else "hedge")
                print(f"{label} c{n}i{i} [{topic}] item {'yes' if item_ok else 'NO'} vetoes {vetoes} "
                      f"transient {'transient' in it['sentence'].lower()} | {it['sentence']}")


if __name__ == "__main__":
    main()
