"""Ask each named question 3 times on develop, each in a fresh guest
session, and record per run: outcome, elapsed, the citation source ids,
and (new in this copy) the full payload of any `error` event plus which
step was last seen immediately before it. Prints one line per run and a
per-question summary of how many distinct source SETS were seen, and
dumps a JSON file with every run's full detail (including verbatim error
payloads) for the live-check report.

This is a throwaway copy of testing/Developer/scripts/flagship_measure.py
for the 2026-09-19 five-day-idle verification. Only the printing and
collection logic changed: the question list, audience_depth handling,
step-sequence tracking, and error-payload capture are new. The request
and streaming mechanics (post, stream) are unchanged from the tracked
script.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from collections import Counter

BASE = "https://search-agent-api-develop-43b3.up.railway.app"

# (question text, audience_depth) - matches the five verification questions
# named in the task, in the given order (BRCA1 asked twice: once at
# researcher, once at plain_language).
QUESTIONS = [
    ("Which diseases are associated with BRCA1?", "researcher"),
    ("What diseases are caused by variants in the HNF1A gene?", "researcher"),
    ("Variants in GCK causing MODY", "researcher"),
    ("What genes are associated with MODY?", "researcher"),
    ("Which diseases are associated with BRCA1?", "plain_language"),
]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3


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


results = {}
detail_log = []  # full per-run detail, including verbatim error payloads

for q, depth in QUESTIONS:
    key = f"{q} [{depth}]"
    results[key] = []
    for i in range(N):
        session = "veri-" + uuid.uuid4().hex[:10]
        token = post(f"/auth/guest?session_id={session}", None, None)["guest_token"]
        started = time.time()
        try:
            run = post(
                "/v1/query",
                {"text": q, "audience_depth": depth, "session_id": session},
                token,
            )
            events = stream(run["run_id"], token)
        except Exception as exc:  # noqa: BLE001
            elapsed = round(time.time() - started, 1)
            results[key].append(("transport_error", elapsed, frozenset(), str(exc)[:200]))
            detail_log.append({
                "question": q,
                "audience_depth": depth,
                "run": i + 1,
                "outcome": "transport_error",
                "elapsed": elapsed,
                "step_sequence": [],
                "last_step_before_error": None,
                "error_payload": None,
                "transport_exception": str(exc),
            })
            print(f"{key[:55]:55} run {i+1}: transport_error")
            continue
        elapsed = round(time.time() - started, 1)
        step_sequence = [e.get("type") for e in events]
        done = next((e for e in events if e.get("type") == "done"), None)
        error = next((e for e in events if e.get("type") == "error" and e["payload"].get("fatal")), None)
        sources = frozenset(e["payload"]["source_id"] for e in events if e.get("type") == "citation")
        outcome = "error" if error else (done["payload"]["trust_outcome"] if done else "no_done")
        if outcome in ("answer", "ask", "flag") and not sources:
            outcome = "no_sources"

        # Determine the step last seen before the error event, if any.
        last_step_before_error = None
        error_payload = None
        if error is not None:
            error_payload = error.get("payload")
            try:
                error_index = events.index(error)
            except ValueError:
                error_index = None
            if error_index is not None and error_index > 0:
                last_step_before_error = events[error_index - 1].get("type")
            elif error_index == 0:
                last_step_before_error = "none (error was the first event)"

        results[key].append((outcome, elapsed, sources, error["payload"].get("source") if error else ""))
        detail_log.append({
            "question": q,
            "audience_depth": depth,
            "run": i + 1,
            "outcome": outcome,
            "elapsed": elapsed,
            "sources": sorted(sources),
            "step_sequence": step_sequence,
            "last_step_before_error": last_step_before_error,
            "error_payload": error_payload,
        })
        print(
            f"{key[:55]:55} run {i+1}: {outcome:10} {elapsed:6}s sources={len(sources)}"
            + (f" | last_step_before_error={last_step_before_error} error_payload={error_payload}" if error_payload else "")
        )

print("\n=== summary ===")
for key, rows in results.items():
    answered = sum(1 for r in rows if r[0] in ("answer", "ask", "flag"))
    sets = Counter(r[2] for r in rows if r[2])
    elapsed_values = sorted(r[1] for r in rows)
    mid = len(elapsed_values) // 2
    median = elapsed_values[mid] if len(elapsed_values) % 2 == 1 else round((elapsed_values[mid - 1] + elapsed_values[mid]) / 2, 1)
    print(
        f"{key[:60]:60} answered {answered} of {len(rows)} | distinct source sets {len(sets)}"
        f" | sizes {[len(s) for s in sets]} | median {median}s | max {max(elapsed_values)}s"
    )

out_path = sys.argv[2] if len(sys.argv) > 2 else "run_detail.json"
with open(out_path, "w") as f:
    json.dump(detail_log, f, indent=2)
print(f"\nFull detail written to {out_path}")
