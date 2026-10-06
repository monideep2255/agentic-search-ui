"""Adversary scan, card 101, no model: every pair develop proposes and the
branch does not, on (1) the labelled set and (2) the 304 recorded live
candidates of 2026-10-05 wave 3. For each removed pair, the missing word
(the one develop judged unused) and which sentence word now 'uses' it."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
DEV = Path(os.environ["DEV_SRC"])


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(ROOT / "src"))
new = _load(ROOT / "src/system_03_search_agent/synthesis/sentence_check.py", "sc_branch")
old = _load(DEV / "system_03_search_agent/synthesis/sentence_check.py", "sc_dev")


def explain(sentence: str, phrase: str) -> str:
    swords = old._words(sentence[: old.MAX_SENTENCE_CHARS])
    out = []
    for w in phrase.split():
        if w in swords:
            continue
        hits = [s for s in swords if new._word_forms(s) & new._word_forms(w)]
        out.append(f"{w}<-{'/'.join(sorted(set(hits))) or '?'}")
    return ", ".join(out)


def diff(sentence, quotes):
    b = old.check_phrases(sentence, quotes)
    a = new.check_phrases(sentence, quotes)
    return [p for p in b if p not in a], [p for p in a if p not in b]


def labelled():
    rows = [json.loads(x) for x in (ROOT / "testing/Developer/reports/2026-10-05_qualifier_check/raw/eval_set.jsonl").read_text().splitlines()]
    print("== labelled set: every A and B item whose pairs changed ==")
    for r in rows:
        rem, add = diff(r["sentence"], r["quotes"])
        if (rem or add) and r["label"] in ("A", "B", "R"):
            print(r["label"], r["id"], r.get("sublabel"))
            print("   sentence:", r["sentence"][:220])
            print("   removed:", [(p, explain(r["sentence"], p)) for p in rem])
            print("   added:", add)


def live():
    raw = ROOT / "testing/Developer/reports/2026-10-05_wave3/sentence_check_raw"
    files = sorted(raw.glob("*.jsonl")) + sorted((raw / "develop_control").glob("*.jsonl"))
    words = Counter()
    n = 0
    print("== 304 recorded live candidates: every removed pair and the word that now uses it ==")
    for path in files:
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        for c, d in enumerate([r["data"] for r in rows if r["tag"] == "CHECK_IN"], start=1):
            for i, it in enumerate(d["items"], start=1):
                n += 1
                rem, add = diff(it["sentence"], it["quotes"])
                if rem:
                    e = [(p, explain(it["sentence"], p)) for p in rem]
                    for _p, x in e:
                        for part in x.split(", "):
                            if part:
                                words[part] += 1
                    print(f"{path.stem}c{c}i{i}: removed {e} added {add}")
    print("candidates:", n)
    print("missing word <- sentence word, counts:")
    for k, v in words.most_common():
        print(f"  {v:3} {k}")


if __name__ == "__main__":
    labelled()
    live()
