"""Card 101 offline check, no model call: the pairs `check_phrases` proposes
on the labelled set, before card 101 (develop f5729ec5) and after.

Usage, from the repository root with the repository's virtual environment:
    python testing/Developer/reports/2026-10-06_card101/raw/offline_word_forms.py
Writes offline_word_forms.jsonl beside this script, one line per item with
its pairs before and after, and prints the per-label totals.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT / "src"))
EVAL = ROOT / "testing/Developer/reports/2026-10-05_qualifier_check/raw/eval_set.jsonl"
BASE = "f5729ec5"

from system_03_search_agent.synthesis import sentence_check as new


def _load_base():
    source = subprocess.run(
        ["git", "show", f"{BASE}:src/system_03_search_agent/synthesis/sentence_check.py"],
        cwd=ROOT, check=True, capture_output=True, text=True).stdout
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        handle.write(source)
    spec = importlib.util.spec_from_file_location("sentence_check_base", handle.name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    old = _load_base()
    rows = [json.loads(x) for x in EVAL.read_text().splitlines()]
    totals: Counter = Counter()
    a_fewer = []
    out = []
    for r in rows:
        before = old.check_phrases(r["sentence"], r["quotes"])
        after = new.check_phrases(r["sentence"], r["quotes"])
        removed = sorted((Counter(before) - Counter(after)).elements())
        added = sorted((Counter(after) - Counter(before)).elements())
        totals[(r["label"], "items")] += 1
        totals[(r["label"], "before")] += len(before)
        totals[(r["label"], "after")] += len(after)
        totals[(r["label"], "fewer")] += len(after) < len(before)
        totals[(r["label"], "more")] += len(after) > len(before)
        totals[(r["label"], "changed")] += bool(removed or added)
        if r["label"] == "A" and len(after) < len(before):
            a_fewer.append(r["id"])
        out.append({"id": r["id"], "label": r["label"], "sublabel": r["sublabel"], "before": before,
                    "after": after, "removed": removed, "added": added})
    (HERE / "offline_word_forms.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out))
    for label in ("A", "F", "B", "R"):
        print(label, {k[1]: v for k, v in totals.items() if k[0] == label})
    print("A items with fewer pairs:", a_fewer or "none")
    for x in out:
        if x["label"] == "A" and (x["removed"] or x["added"]):
            print("A", x["id"], "removed", x["removed"], "added", x["added"])
    print("F items whose proposals shrink:")
    for x in out:
        if x["label"] == "F" and len(x["after"]) < len(x["before"]):
            print(" ", x["id"], "removed", x["removed"], "added", x["added"])
    print("F items whose proposals grow:")
    for x in out:
        if x["label"] == "F" and len(x["after"]) > len(x["before"]):
            print(" ", x["id"], "removed", x["removed"], "added", x["added"])


if __name__ == "__main__":
    main()
