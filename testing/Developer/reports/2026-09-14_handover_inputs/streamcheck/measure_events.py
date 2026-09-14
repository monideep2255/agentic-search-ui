"""Measure SSE event arrival timing on develop for the streaming investigation.

Pattern taken from testing/Developer/scripts/flagship_measure.py. Records the
wall-clock arrival time (to the millisecond) of every SSE event for each run,
so we can see whether `token` events arrive progressively or in one burst.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"


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
            arrival = time.time()
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("data:"):
                try:
                    payload = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                out.append((arrival, payload))
    return out


def run_once(question, audience_depth, label):
    session = "stream-" + uuid.uuid4().hex[:10]
    token = post(f"/auth/guest?session_id={session}", None, None)["guest_token"]
    t0 = time.time()
    run = post(
        "/v1/query",
        {"text": question, "audience_depth": audience_depth, "session_id": session},
        token,
    )
    events = stream(run["run_id"], token)
    record = {
        "label": label,
        "question": question,
        "audience_depth": audience_depth,
        "t0": t0,
        "run_id": run["run_id"],
        "events": [
            {
                "arrival_s_since_t0": round(arrival - t0, 4),
                "type": payload.get("type"),
                "seq": payload.get("seq"),
                "ts_server": payload.get("ts"),
            }
            for arrival, payload in events
        ],
    }
    return record


def summarize(record):
    events = record["events"]
    token_events = [e for e in events if e["type"] == "token"]
    write_step_events = [
        e for e in events if e["type"] in ("step", "trust_signal") and e.get("seq") is not None
    ]
    done_events = [e for e in events if e["type"] == "done"]
    first_write_evidence = token_events[0] if token_events else None
    summary = {
        "label": record["label"],
        "total_events": len(events),
        "num_token_events": len(token_events),
        "first_token_s": token_events[0]["arrival_s_since_t0"] if token_events else None,
        "last_token_s": token_events[-1]["arrival_s_since_t0"] if token_events else None,
        "token_spread_ms": (
            round((token_events[-1]["arrival_s_since_t0"] - token_events[0]["arrival_s_since_t0"]) * 1000, 1)
            if len(token_events) > 1
            else 0.0 if token_events else None
        ),
        "done_s": done_events[0]["arrival_s_since_t0"] if done_events else None,
        "event_type_sequence": [(e["type"], e["arrival_s_since_t0"]) for e in events],
    }
    return summary


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "events_raw.json"
    runs = [
        ("Which diseases are associated with BRCA1?", "plain_language", "brca1_plain"),
        ("Which diseases are associated with BRCA1?", "plain_language", "brca1_plain"),
        ("Which diseases are associated with BRCA1?", "plain_language", "brca1_plain"),
        ("Variants in GCK causing MODY", "researcher", "gck_researcher"),
        ("Variants in GCK causing MODY", "researcher", "gck_researcher"),
        ("Variants in GCK causing MODY", "researcher", "gck_researcher"),
    ]
    all_records = []
    all_summaries = []
    for i, (q, depth, label) in enumerate(runs):
        print(f"run {i+1}/6: {label} ...", flush=True)
        try:
            record = run_once(q, depth, label)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}")
            all_records.append({"label": label, "question": q, "audience_depth": depth, "error": str(exc)})
            continue
        summary = summarize(record)
        all_records.append(record)
        all_summaries.append(summary)
        print(f"  total_events={summary['total_events']} tokens={summary['num_token_events']} "
              f"first_token={summary['first_token_s']} last_token={summary['last_token_s']} "
              f"spread_ms={summary['token_spread_ms']} done={summary['done_s']}")

    with open(out_path, "w") as f:
        json.dump({"records": all_records, "summaries": all_summaries}, f, indent=2)
    print(f"\nWrote {out_path}")
