"""Items 12.9 to 12.12, measured: the seven questions from testing/User-feedback, each asked twice: once as a
plain-language reader and once as a researcher.

Set 12 was graded on whether a question answers at all. This asks the next
question, which is the product owner's actual bar: is what comes back worth
reading to each of the two people the product is built for, a biomedical
researcher and someone without the technical depth.

One question at a time, since the NCBI rate pools are shared.

Run from the repository root:
    python testing/Developer/reports/2026-09-23_synthesis/run_both_depths.py
"""
import asyncio
import contextlib
import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "testing/Developer/scripts"))
OUT = pathlib.Path(__file__).parent / "runs"
OUT.mkdir(exist_ok=True)

from local_loop_run_depth import measure

QUESTIONS = [
    ("q1", "reflux disease"),
    ("q2", "GERD"),
    ("q3", "Any trials for GERD?"),
    ("q4", "papers on the effects of caffeine on exercise performance"),
    ("q5", "Does coffee help make exercise more effective?"),
    ("q6", "Are there any beneficial variants typically found in people of mediterranean descent?"),
    ("q7", "What positive and negative genes do ashkenazi jewish people have?"),
]


async def main() -> None:
    rows = []
    for key, question in QUESTIONS:
        for depth in ("plain_language", "researcher"):
            print(f"=== {key} {depth}", flush=True)
            try:
                # The answer text itself is the evidence here, not only the
                # counts, so the printed answer is captured with the result.
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    result = await measure(question, depth, show=True)
                result["answer"] = buffer.getvalue()
            except Exception as exc:  # noqa: BLE001 - a failed run is a result to record, not to raise on
                result = {"depth": depth, "question": question, "outcome": f"EXCEPTION {type(exc).__name__}: {exc}"}
            result["key"] = key
            rows.append(result)
            (OUT / f"{key}_{depth}.json").write_text(json.dumps(result, indent=2, default=str))
            print(json.dumps({
                "key": key, "depth": depth, "outcome": result.get("outcome"),
                "words": result.get("words"), "sources": len(result.get("sources") or []),
                "unmarked_claims": result.get("unmarked_claims"),
                "headings": result.get("headings"), "table_rows": result.get("table_rows"),
                "errors": result.get("errors"),
            }, default=str), flush=True)
    (OUT / "all.jsonl").write_text("\n".join(json.dumps(r, default=str) for r in rows) + "\n")
    print("wrote runs/all.jsonl")


asyncio.run(main())
