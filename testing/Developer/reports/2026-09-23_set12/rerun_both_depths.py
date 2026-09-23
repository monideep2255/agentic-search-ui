"""Item 12.9 re-measure: the seven second-tester questions at both answer depths,
on today's HEAD, capturing the rendered answer text as well as the counts.

The 2026-09-23 numbers in the Set 12 table predate 29c8687, which deduplicated
the code-built listing. They are therefore stale by one commit and a diagnosis
built on them is worthless, so this re-runs all fourteen.

Writes one JSON per run to both_depths_rerun/, leaving the original
both_depths/ evidence untouched.

One question at a time: the NCBI rate pools are shared.

Run from the repository root:
    python testing/Developer/reports/2026-09-23_set12/rerun_both_depths.py
"""
import asyncio
import contextlib
import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "testing/Developer/scripts"))
OUT = pathlib.Path(__file__).parent / "both_depths_rerun"
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
    only = sys.argv[1:] or [key for key, _ in QUESTIONS]
    rows = []
    for key, question in QUESTIONS:
        if key not in only:
            continue
        for depth in ("plain_language", "researcher"):
            print(f"=== {key} {depth}", flush=True)
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    result = await measure(question, depth, show=True)
            except Exception as exc:  # noqa: BLE001 - a failed run is a result to record
                result = {
                    "depth": depth,
                    "question": question,
                    "outcome": f"EXCEPTION {type(exc).__name__}: {exc}",
                }
            result["key"] = key
            result["answer_text"] = buffer.getvalue()
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
    print("wrote both_depths_rerun/all.jsonl")


asyncio.run(main())
