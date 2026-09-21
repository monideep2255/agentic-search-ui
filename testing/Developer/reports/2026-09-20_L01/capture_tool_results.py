"""Establish L-01 shape 1: does a whole graph tool_result vanish on some
runs of "What diseases are caused by variants in the HNF1A gene?", hidden
by graceful degradation, while sources still shrink from 18 to 13 to 8?

Six runs, one question, fresh guest session each time. Unlike the prior
verification scripts (measure_with_errors.py in 2026-09-19_verification),
this one keeps the FULL payload of every `tool_result` event, not just a
count, because a missing or empty graph result is only visible in the
payload itself (`status`, `summary`, `result_count`, `tool`, `layer`), and
"Where we stopped" in testing/UI_fix_plan.md names exactly this gap:
"needs the measurement script to capture tool-result payloads".

Auth, post, and stream mechanics are copied unchanged from
testing/Developer/reports/2026-09-19_verification/measure_with_errors.py
(same BASE, same guest-auth flow, same SSE line parsing). Only the
collection and reporting logic is new: every tool_result payload is kept
verbatim per run, alongside the citation-derived source count, so a run
that dropped a graph tool result is visible next to the run that did not.

No credential VALUE is ever printed or written. The guest token is held
only in memory for the duration of one run's two requests.
"""
from __future__ import annotations

import json
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"

QUESTION = "What diseases are caused by variants in the HNF1A gene?"
AUDIENCE_DEPTH = "researcher"
N_RUNS = 6


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


def run_once(run_index):
    session = "l01-" + uuid.uuid4().hex[:10]
    started = time.time()
    try:
        auth = post(f"/auth/guest?session_id={session}", None, None)
        token = auth["guest_token"]
    except Exception as exc:  # noqa: BLE001
        return {
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
            {"text": QUESTION, "audience_depth": AUDIENCE_DEPTH, "session_id": session},
            token,
        )
        events = stream(run["run_id"], token)
    except Exception as exc:  # noqa: BLE001
        return {
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

    # Every tool_result event, FULL payload, in emission order. This is the
    # new capture: the prior script only counted citations, never looked at
    # a tool_result's own status/summary/result_count.
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
    outcome = "error" if error else (done["payload"]["trust_outcome"] if done else "no_done")

    # Flag any graph-layer tool_result whose status is not a clean "ok",
    # or whose result_count is 0 while its status still reads "ok" (the
    # empty-but-not-flagged shape graceful degradation can hide).
    graph_anomalies = [
        tr
        for tr in tool_results
        if tr is not None
        and tr.get("layer") == "layer_1"
        and (tr.get("status") != "ok" or tr.get("result_count", 0) == 0)
    ]

    return {
        "run": run_index,
        "session": session,
        "outcome": outcome,
        "elapsed": elapsed,
        "error_payload": error.get("payload") if error else None,
        "step_sequence": step_sequence,
        "tool_starts": tool_starts,
        "tool_results": tool_results,
        "graph_anomalies": graph_anomalies,
        "source_count": len(sources),
        "sources": sources,
    }


def main():
    print(f"Question: {QUESTION!r} [{AUDIENCE_DEPTH}], {N_RUNS} runs against {BASE}\n")
    all_runs = []
    for i in range(1, N_RUNS + 1):
        result = run_once(i)
        all_runs.append(result)
        n_tool_results = len(result["tool_results"])
        n_anomalies = len(result.get("graph_anomalies", []))
        print(
            f"run {i}: outcome={result['outcome']:12} elapsed={result['elapsed']:6}s "
            f"sources={result.get('source_count', 0):3} tool_results={n_tool_results:2} "
            f"graph_anomalies={n_anomalies}"
        )
        if n_anomalies:
            for anomaly in result["graph_anomalies"]:
                print(f"    ANOMALY: {json.dumps(anomaly)}")

    out_path = "runs.json"
    with open(out_path, "w") as f:
        json.dump(
            {
                "question": QUESTION,
                "audience_depth": AUDIENCE_DEPTH,
                "base_url": BASE,
                "n_runs": N_RUNS,
                "runs": all_runs,
            },
            f,
            indent=2,
        )

    print(f"\nSource counts across runs: {[r.get('source_count', 0) for r in all_runs]}")
    distinct_counts = sorted({r.get("source_count", 0) for r in all_runs})
    print(f"Distinct source-count values: {distinct_counts}")
    print(f"Full detail written to {out_path}")


if __name__ == "__main__":
    main()
