"""Card 101 fix round: per answer, every sentence on screen beside the record
words it was checked against, so a widened claim can be judged by hand. No
model call. Reads <label>.jsonl from OUT_DIR, which stays outside the
repository because the quotes are record text.

Usage: OUT_DIR=<raw answers folder> python shown_with_quotes.py hb1 hd1 ...

Per answer: the elapsed time, the reported cost, the number of claim
sentences on screen (without the code-built "I found N" line), and per
sentence whether it went through the sentence check ("reworded", with its
quotes) or not ("copied", with the cited findings' opening text).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

OUT_DIR = Path(os.environ["OUT_DIR"])


def norm(text: str) -> str:
    text = re.sub(r"\[[0-9#,\s]+\]", " ", text)
    return " ".join(re.sub(r"[()\[\]{}.,;:]", " ", text.lower()).split())


def main() -> None:
    for label in sys.argv[1:]:
        rows = [json.loads(x) for x in (OUT_DIR / f"{label}.jsonl").read_text().splitlines()]
        cands = {}
        for r in rows:
            if r["tag"] == "CHECK_IN":
                for it in r["data"]["items"]:
                    cands[norm(it["sentence"])[:60]] = it
        findings = next((r["data"] for r in rows if r["tag"] == "FINDINGS"), [])
        by_ref = {f["ref"]: f["text"] for f in findings}
        shown = [t[len("claim: "):] for t in (r["data"] for r in rows if r["tag"] == "TOKEN")
                 if t.startswith("claim: ") and not re.match(r"claim: (Found|I found) \d", t)]
        done = next((r["data"] for r in rows if r["tag"] in ("DONE", "ERROR")), {})
        n_cands = sum(len(r["data"]["items"]) for r in rows if r["tag"] == "CHECK_IN")
        n_ok = sum(r["data"]["approved"] for r in rows if r["tag"] == "CHECK_OUT")
        print(f"== {label}: shown {len(shown)}, seconds {round((done.get('elapsed_ms') or 0) / 1000, 1)}, "
              f"cost {round(done.get('total_cost_usd') or 0, 4)}, outcome {done.get('trust_outcome')}, "
              f"check candidates {n_cands}, approved {n_ok}")
        for n, s in enumerate(shown, start=1):
            it = cands.get(norm(s)[:60])
            print(f"  S{n} [{'reworded' if it else 'copied'}] {s.strip()}")
            if it:
                for q in it["quotes"]:
                    print(f"      Q: {q}")
            else:
                for ref in re.findall(r"\[(\d+)\]", s):
                    print(f"      F{ref}: {(by_ref.get(int(ref)) or '')[:300]}")
        approved = set()
        for r in rows:
            if r["tag"] == "CHECK_OUT":
                approved.update(norm(x)[:60] for x in r["data"]["approved_sentences"])
        k = 0
        for r in rows:
            if r["tag"] != "CHECK_IN":
                continue
            for it in r["data"]["items"]:
                k += 1
                ok = norm(it["sentence"])[:60] in approved
                print(f"  C{k} [{'approved' if ok else 'held back'}] {it['sentence'].strip()}")
                for q in it["quotes"]:
                    print(f"      Q: {q}")


if __name__ == "__main__":
    main()
