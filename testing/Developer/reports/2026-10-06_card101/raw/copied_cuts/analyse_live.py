"""Card 101 round 3: summarise the live answers traced by `check_every/trace_run.py`.

No model call. Per answer: seconds, cost, claim sentences shown (the
code-built "I found N" line skipped), check calls, and the copied cuts that
went to the check (an item whose sentence is contiguous record text, so it
came from this round's rule) with how many the check approved.

Usage: python analyse_live.py <folder with the traced .jsonl files> [--counts]
Without --counts it also prints each copied cut and its verdict (record text,
console only).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

from system_03_search_agent.synthesis import grounding as gr

SUMMARY = re.compile(r"^(I found|Found) \d")


def main() -> None:
    folder = Path(sys.argv[1])
    verbose = "--counts" not in sys.argv
    print("answer | seconds | cost usd | shown | check calls | copied cuts asked | approved | held")
    totals = {"cuts": 0, "approved": 0, "no_prose": 0}
    for path in sorted(folder.glob("*.jsonl")):
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        texts = next((r["data"] for r in rows if r["tag"] == "FINDINGS"), [])
        values = [f["text"] or "" for f in texts]
        shown = [
            r["data"][len("claim: ") :]
            for r in rows
            if r["tag"] == "TOKEN"
            and r["data"].startswith("claim: ")
            and not SUMMARY.match(r["data"][len("claim: ") :])
        ]
        calls = cuts = approved = 0
        for i, r in enumerate(rows):
            if r["tag"] != "CHECK_IN":
                continue
            calls += 1
            out = next((o for o in rows[i + 1 :] if o["tag"] in ("CHECK_OUT", "CHECK_RAISED")), None)
            ok = set(out["data"]["approved_sentences"]) if out and out["tag"] == "CHECK_OUT" else set()
            items = r["data"]["items"]
            items = items if isinstance(items, list) else ast.literal_eval(items)
            for item in items:
                sentence = item["sentence"]
                if not any(gr.normalize(sentence) in gr.normalize(v) for v in values if v):
                    continue
                cuts += 1
                yes = gr.normalize(sentence) in ok
                approved += yes
                if verbose:
                    print(f"  {path.stem} [{'approved' if yes else 'held'}] {sentence}")
        done = next((r["data"] for r in rows if r["tag"] == "DONE"), {})
        seconds = next((r["data"] for r in rows if r["tag"] == "ELAPSED_S"), None)
        totals["cuts"] += cuts
        totals["approved"] += approved
        totals["no_prose"] += not shown
        print(
            f"{path.stem} | {seconds} | {round(float(done.get('total_cost_usd') or 0), 4)} | {len(shown)}"
            f" | {calls} | {cuts} | {approved} | {cuts - approved}"
        )
    print(
        f"\ncopied cuts asked {totals['cuts']}, approved {totals['approved']},"
        f" answers with no prose {totals['no_prose']}"
    )


if __name__ == "__main__":
    main()
