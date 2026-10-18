"""L-01 measurement: does a whole Layer 1 graph tool_result vanish between
runs of the same question, hidden by graceful degradation so the answer
still looks fine?

Adapted from testing/Developer/reports/2026-09-20_L01/capture_tool_results.py,
which was written on 2026-09-20 and never run. Two changes from the original:

1. Two questions instead of one, both named in the L-01 task brief as the
   repository's own recurring probes: the BRCA1 disease-association question
   and the HNF1A gene-variant-disease question.
2. N_RUNS raised from 6 to 5 per question (10 runs total) and each run's
   full record is ALSO written to raw/<slug>_run<N>.json as it completes,
   not only batched into one runs.json at the end, so a captured run
   survives even if a later run in the loop fails outright.

Auth, post, and stream mechanics are unchanged from the 2026-09-20 original,
which itself copied them from
testing/Developer/reports/2026-09-19_verification/measure_with_errors.py.

No credential VALUE is ever printed or written. The guest token is held
only in memory for the duration of one run's two requests.
"""
from __future__ import annotations

import json
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
N_RUNS = 5


def post(path, body, token):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def stream(run_id, token):
    req = urllib.request.Request(BASE + f"/v1/query/{run_id}/events")
    req.add_header("Accept", "text/event-stream")
    req.add_header("Authorization", "Bearer " + token)
    out = []
    with urllib.request.urlopen(req, timeout=180) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("data:"):
                try:
                    out.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    pass
    return out


def slug(question):
    return "brca1" if "BRCA1" in question else "hnf1a"


def run_once(question, run_index):
    session = "l01-" + uuid.uuid4().hex[:10]
    started = time.time()
    try:
        auth = post(f"/auth/guest?session_id={session}", None, None)
        token = auth["guest_token"]
    except Exception as exc:  # noqa: BLE001
        return {
            "question": question,
            "run": run_index,
            "session": session,
            "outcome": "guest_auth_failed",
            "elapsed": round(time.time() - started, 1),
            "exception": str(exc)[:300],
            "tool_results": [],
            "sources": [],
            "step_sequence": [],
        }

    try:
        run = post(
            "/v1/query",
            {"text": question, "audience_depth": AUDIENCE_DEPTH, "session_id": session},
            token,
        )
        events = stream(run["run_id"], token)
    except Exception as exc:  # noqa: BLE001
        return {
            "question": question,
            "run": run_index,
            "session": session,
            "outcome": "transport_error",
            "elapsed": round(time.time() - started, 1),
            "exception": str(exc)[:300],
            "tool_results": [],
            "sources": [],
            "step_sequence": [],
        }

    elapsed = round(time.time() - started, 1)
    step_sequence = [e.get("type") for e in events]

    tool_results = [
        e.get("payload") for e in events if e.get("type") == "tool_result"
    ]
    tool_starts = [
        e.get("payload") for e in events if e.get("type") == "tool_start"
    ]

    done = next((e for e in events if e.get("type") == "done"), None)
    error = next(
        (e for e in events if e.get("type") == "error" and e.get("payload", {}).get("fatal")),
        None,
    )
    sources = sorted(
        {e["payload"]["source_id"] for e in events if e.get("type") == "citation"}
    )
    layer_1_citations = sorted(
        {
            e["payload"]["source_id"]
            for e in events
            if e.get("type") == "citation" and e.get("payload", {}).get("layer") == "layer_1"
        }
    )
    outcome = "error" if error else (done["payload"]["trust_outcome"] if done else "no_done")

    graph_anomalies = [
        tr
        for tr in tool_results
        if tr is not None
        and tr.get("layer") == "layer_1"
        and (tr.get("status") != "ok" or tr.get("result_count", 0) == 0)
    ]

    graph_row_counts = [
        tr.get("result_count")
        for tr in tool_results
        if tr is not None and tr.get("layer") == "layer_1"
    ]

    return {
        "question": question,
        "run": run_index,
        "session": session,
        "run_id": run.get("run_id"),
        "outcome": outcome,
        "elapsed": elapsed,
        "error_payload": error.get("payload") if error else None,
        "step_sequence": step_sequence,
        "tool_starts": tool_starts,
        "tool_results": tool_results,
        "graph_anomalies": graph_anomalies,
        "graph_row_counts": graph_row_counts,
        "source_count": len(sources),
        "layer_1_citation_count": len(layer_1_citations),
        "sources": sources,
    }


def main():
    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "raw"
    print(f"Questions: {QUESTIONS!r} [{AUDIENCE_DEPTH}], {N_RUNS} runs each against {BASE}\n")
    all_runs = []
    for question in QUESTIONS:
        for i in range(1, N_RUNS + 1):
            result = run_once(question, i)
            all_runs.append(result)
            n_tool_results = len(result["tool_results"])
            n_anomalies = len(result.get("graph_anomalies", []))
            print(
                f"[{slug(question)}] run {i}: outcome={result['outcome']:12} "
                f"elapsed={result['elapsed']:6}s "
                f"sources={result.get('source_count', 0):3} "
                f"l1_citations={result.get('layer_1_citation_count', 0):3} "
                f"tool_results={n_tool_results:2} "
                f"l1_rows={result.get('graph_row_counts', [])} "
                f"graph_anomalies={n_anomalies}"
            )
            if n_anomalies:
                for anomaly in result["graph_anomalies"]:
                    print(f"    ANOMALY: {json.dumps(anomaly)}")

            out_path = f"{raw_dir}/{slug(question)}_run{i}.json"
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)

            time.sleep(4)

    out_path = f"{raw_dir}/all_runs.json"
    with open(out_path, "w") as f:
        json.dump(
            {
                "questions": QUESTIONS,
                "audience_depth": AUDIENCE_DEPTH,
                "base_url": BASE,
                "n_runs_per_question": N_RUNS,
                "runs": all_runs,
            },
            f,
            indent=2,
        )

    print(f"\nFull detail written to {out_path}")
    for question in QUESTIONS:
        rows = [
            r.get("graph_row_counts")
            for r in all_runs
            if r["question"] == question
        ]
        print(f"[{slug(question)}] Layer 1 row counts per run: {rows}")


if __name__ == "__main__":
    main()
