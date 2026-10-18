"""Print what each writer shipped for one question, for reading by hand.

For every model's run of the question: the outcome, whether the summary
was withdrawn, the first three prose sentences that shipped with the record
words each one was grounded against, and the writer's first reply as the
model wrote it (so a withdrawn summary can be read too, against the records
the writer was shown).

Usage: read_answers.py <question_id> <run> [--records]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    qid, run = sys.argv[1], int(sys.argv[2])
    show_records = "--records" in sys.argv
    for raw in sorted((HERE / "raw").glob(f"*__{qid}__r{run}.json")):
        detail = json.loads(raw.read_text())
        record = detail["record"]
        rec = detail["rec"]
        print(f"=== {record['model']} | {record['outcome']} | withdrawn={record['withdrawn']} "
              f"| writer s={[round(x, 1) for x in record['writer_elapsed_s']]}")
        first_reply = next((c.get("reply") or "" for c in rec.get("llm", []) if c.get("synth") and c.get("ok")), "")
        cited = {int(n) for n in re.findall(r"\[(\d+)[\]:]", first_reply[:1500])}
        if show_records and rec.get("findings"):
            # Each run retrieves its own records and numbers them itself, so
            # the records are printed per run: those the first reply cites.
            print("--- records the first reply cites, as this run numbered them")
            for f in rec["findings"]:
                if f["ref"] in cited:
                    print(f"  [{f['ref']}] {f['field']}: {f['value']}")
        grounds = rec.get("grounding") or []
        shipped = record.get("shipped_draft")
        if shipped is not None and not record["withdrawn"]:
            kept = [s for s in grounds[shipped]["sentences"] if len(re.sub(r"\[\d+\]", "", s).split()) >= 4]
            details = grounds[shipped].get("claim_detail") or []
            print("--- first three prose sentences shipped")
            for sentence in kept[:3]:
                print(f"  * {sentence}")
            for d in details[:6]:
                print(f"      grounded on [{d['ref']}] {d['field']}: {d['value'][:160]!r} quote={d['quote'][:120]!r}")
        replies = [c.get("reply") for c in rec.get("llm", []) if c.get("synth") and c.get("ok")]
        if replies:
            print("--- writer's first reply, as written")
            print("  " + (replies[0] or "")[:1500].replace("\n", "\n  "))
        print()


if __name__ == "__main__":
    main()
