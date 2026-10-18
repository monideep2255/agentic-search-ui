"""List each answered run's first kept prose sentence, for grading by hand.

Prints one block per question: the question, then for every run of the given
run indexes that kept prose, its key and the first whole prose sentence that
shipped. The grader writes "yes" (it answers what was asked) or "no" per key
into grades.json, which analyze.py reads. Runs with no kept prose have no
writer sentence to grade and are not listed.

Usage: first_sentences.py <runs>
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    runs = {int(r) for r in sys.argv[1].split(",")}
    by_question: dict[str, list[tuple[str, str]]] = defaultdict(list)
    questions: dict[str, str] = {}
    for line in (HERE / "results.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["run"] not in runs or row["outcome"] != "answered" or row["withdrawn"]:
            continue
        kept = [s for s in row.get("prose_kept") or [] if len(re.sub(r"\[\d+\]", "", s).split()) >= 4]
        if not kept:
            continue
        questions[row["question_id"]] = row["question"]
        by_question[row["question_id"]].append((f"{row['model']}|{row['question_id']}|{row['run']}", kept[0]))
    for qid in sorted(by_question):
        print(f"## {qid}: {questions[qid]}")
        for key, sentence in sorted(by_question[qid]):
            print(f"  {key}\n      {sentence}")
        print()


if __name__ == "__main__":
    main()
