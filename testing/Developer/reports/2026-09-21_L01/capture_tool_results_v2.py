"""L-01 measurement, batch 2: same as capture_tool_results.py but with the
layer-value bug fixed and full citation payloads kept.

Batch 1 (capture_tool_results.py, raw/*_run*.json) used the literal string
"layer_1" to filter Layer 1 tool_results and citations, copied unchanged
from the untested 2026-09-20 instrument. The live API actually tags events
"layer_1_graph" / "layer_2_api" / "layer_3_enrichment", discovered by
inspecting batch 1's saved tool_result payloads. That bug meant batch 1's
graph_anomalies and layer_1_citation_count fields were always empty/zero,
even though the underlying tool_results (saved in full regardless) show
the real picture. Batch 1's tool-call and row-count data is still valid
and is not re-collected here.

This batch adds one thing batch 1 did not save: the full citation event
list (source_id, layer, source pairs), so the report can state the number
of Layer 1 citations per run, not just infer it from graph row counts.
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
LAYER_1 = "layer_1_graph"


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
    session = "l01v2-" + uuid.uuid4().hex[:10]
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
            "citations": [],
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
            "citations": [],
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
    citations = [
        e.get("payload") for e in events if e.get("type") == "citation"
    ]

    done = next((e for e in events if e.get("type") == "done"), None)
    error = next(
        (e for e in events if e.get("type") == "error" and e.get("payload", {}).get("fatal")),
        None,
    )
    outcome = "error" if error else (done["payload"]["trust_outcome"] if done else "no_done")

    l1_tool_results = [tr for tr in tool_results if tr and tr.get("layer") == LAYER_1]
    graph_anomalies = [
        tr for tr in l1_tool_results
        if tr.get("status") != "ok" or tr.get("result_count", 0) == 0
    ]
    graph_row_counts = [tr.get("result_count") for tr in l1_tool_results]

    distinct_sources = sorted({c.get("source_id") for c in citations if c})
    l1_citations = [c for c in citations if c and c.get("layer") == LAYER_1]
    distinct_l1_sources = sorted({c.get("source_id") for c in l1_citations})

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
        "l1_tool_results": l1_tool_results,
        "graph_anomalies": graph_anomalies,
        "graph_row_counts": graph_row_counts,
        "citations": citations,
        "source_count": len(distinct_sources),
        "l1_citation_count": len(distinct_l1_sources),
    }


def main():
    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "raw"
    print(f"Batch 2 (fixed layer filter): {QUESTIONS!r} [{AUDIENCE_DEPTH}], {N_RUNS} runs each\n")
    all_runs = []
    for question in QUESTIONS:
        for i in range(1, N_RUNS + 1):
            result = run_once(question, i)
            all_runs.append(result)
            n_anomalies = len(result.get("graph_anomalies", []))
            print(
                f"[{slug(question)}] run {i}: outcome={result['outcome']:12} "
                f"elapsed={result['elapsed']:6}s "
                f"sources={result.get('source_count', 0):3} "
                f"l1_citations={result.get('l1_citation_count', 0):3} "
                f"l1_rows={result.get('graph_row_counts', [])} "
                f"graph_anomalies={n_anomalies}"
            )
            if n_anomalies:
                for anomaly in result["graph_anomalies"]:
                    print(f"    ANOMALY: {json.dumps(anomaly)}")

            out_path = f"{raw_dir}/v2_{slug(question)}_run{i}.json"
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)

            time.sleep(4)

    out_path = f"{raw_dir}/v2_all_runs.json"
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


if __name__ == "__main__":
    main()
