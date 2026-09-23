"""Is L-01 still live on today's develop, and what does the unstable call do now?

The 2026-09-21 measurement ran against commit 99a3495. Two commits since then
narrowed the model path for a gene question (27d68ae, 2bc8ec0) and one carried
a graph error reason into the tool_result summary (7f0aa7b), so the 2026-09-21
row counts cannot be mapped onto today's templates without re-measuring.

This re-runs the same two questions and reports each Layer 1 call by START
slot (joined on call_id), not by result emission order. The two graph calls run
concurrently and their results arrive in either order, which is why the earlier
report read one unstable POSITION where there is in fact one unstable CALL.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_L01_cause/remeasure.py [runs] [outdir]
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
QUESTIONS = [
    "Which diseases are associated with BRCA1?",
    "What diseases are caused by variants in the HNF1A gene?",
]
AUDIENCE_DEPTH = "researcher"
LAYER_1 = "layer_1_graph"


def post(path: str, body: object, token: str | None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def stream(run_id: str, token: str) -> list[dict]:
    req = urllib.request.Request(BASE + f"/v1/query/{run_id}/events")
    req.add_header("Accept", "text/event-stream")
    req.add_header("Authorization", "Bearer " + token)
    out: list[dict] = []
    with urllib.request.urlopen(req, timeout=240) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("data:"):
                try:
                    out.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    pass
    return out


def slug(question: str) -> str:
    return "brca1" if "BRCA1" in question else "hnf1a"


def run_once(question: str, index: int) -> dict:
    session = "l01c-" + uuid.uuid4().hex[:10]
    started = time.time()
    try:
        token = post(f"/auth/guest?session_id={session}", None, None)["guest_token"]
        run = post(
            "/v1/query",
            {"text": question, "audience_depth": AUDIENCE_DEPTH, "session_id": session},
            token,
        )
        events = stream(run["run_id"], token)
    except Exception as exc:  # noqa: BLE001 - every outcome is data
        return {
            "question": question,
            "run": index,
            "outcome": "transport_error",
            "exception": str(exc)[:300],
            "elapsed": round(time.time() - started, 1),
        }

    starts = [e["payload"] for e in events if e.get("type") == "tool_start"]
    results = {
        e["payload"]["call_id"]: e["payload"]
        for e in events
        if e.get("type") == "tool_result"
    }
    citations = [e["payload"] for e in events if e.get("type") == "citation"]
    done = next((e for e in events if e.get("type") == "done"), None)
    error = next(
        (
            e
            for e in events
            if e.get("type") == "error" and e.get("payload", {}).get("fatal")
        ),
        None,
    )

    slots = []
    for slot, start in enumerate(s for s in starts if s.get("layer") == LAYER_1):
        result = results.get(start["call_id"])
        slots.append(
            {
                "slot": slot,
                "call_id": start["call_id"],
                "status": result and result.get("status"),
                "result_count": result and result.get("result_count"),
                "summary": result and result.get("summary"),
                "truncated": result and result.get("truncated"),
            }
        )

    l1_citations = {c.get("source_id") for c in citations if c.get("layer") == LAYER_1}
    return {
        "question": question,
        "run": index,
        "run_id": run.get("run_id"),
        "outcome": "error" if error else (done["payload"]["trust_outcome"] if done else "no_done"),
        "elapsed": round(time.time() - started, 1),
        "error_payload": error.get("payload") if error else None,
        "layer_1_slots": slots,
        "source_count": len({c.get("source_id") for c in citations}),
        "l1_citation_count": len(l1_citations),
        "all_tool_results": [
            {
                "tool": r.get("tool"),
                "layer": r.get("layer"),
                "status": r.get("status"),
                "result_count": r.get("result_count"),
                "summary": r.get("summary"),
            }
            for r in results.values()
        ],
    }


def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    outdir = pathlib.Path(
        sys.argv[2] if len(sys.argv) > 2
        else "testing/Developer/reports/2026-09-23_L01_cause/raw"
    )
    outdir.mkdir(parents=True, exist_ok=True)
    collected = []
    for question in QUESTIONS:
        for index in range(1, runs + 1):
            result = run_once(question, index)
            collected.append(result)
            slot_text = " | ".join(
                f"slot{s['slot']}={s['status']}:{s['result_count']}"
                for s in result.get("layer_1_slots", [])
            )
            print(
                f"[{slug(question)}] run {index}: {result['outcome']:12} "
                f"{result['elapsed']:6}s sources={result.get('source_count')} "
                f"l1_cites={result.get('l1_citation_count')} {slot_text}"
            )
            (outdir / f"{slug(question)}_run{index}.json").write_text(
                json.dumps(result, indent=2)
            )
            time.sleep(4)
    (outdir / "all_runs.json").write_text(json.dumps(collected, indent=2))
    print(f"\nWritten to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
