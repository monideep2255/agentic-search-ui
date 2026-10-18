"""One-off, read-only instrument for the 2026-09-21 11.31 divergence baseline.

Adapted from testing/Developer/reports/2026-09-19_verification/fetch_answer_text.py:
same base URL, same guest-auth flow, same SSE reassembly approach. Fires four
live queries (BRCA1 and HNF1A, each at plain_language and researcher depth),
reassembles the token stream into the displayed answer text, and writes each
run to raw/<slug>.json for the capture.py script to measure. Not part of any
tracked reliability suite; does not touch any tracked file.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"

TARGETS = [
    ("Which diseases are associated with BRCA1?", "plain_language"),
    ("Which diseases are associated with BRCA1?", "researcher"),
    ("What diseases are caused by variants in the HNF1A gene?", "plain_language"),
    ("What diseases are caused by variants in the HNF1A gene?", "researcher"),
]


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


def slug(question, depth):
    short = "brca1" if "BRCA1" in question else "hnf1a"
    return f"{short}_{depth}"


def main():
    raw_dir = sys.argv[1] if len(sys.argv) > 1 else "raw"
    for q, depth in TARGETS:
        session = "div-qc-" + uuid.uuid4().hex[:8]
        token = post(f"/auth/guest?session_id={session}", None, None)["guest_token"]
        run = post(
            "/v1/query",
            {"text": q, "audience_depth": depth, "session_id": session},
            token,
        )
        events = stream(run["run_id"], token)
        tokens = [e["payload"].get("text", "") for e in events if e.get("type") == "token"]
        text = "".join(tokens)
        done = next((e for e in events if e.get("type") == "done"), None)
        outcome = done["payload"]["trust_outcome"] if done else "no_done"
        record = {
            "question": q,
            "audience_depth": depth,
            "outcome": outcome,
            "answer_text": text,
            "run_id": run.get("run_id"),
            "raw_event_count": len(events),
        }
        out_path = f"{raw_dir}/{slug(q, depth)}.json"
        with open(out_path, "w") as f:
            json.dump(record, f, indent=2)
        print(f"{q} [{depth}] -> outcome={outcome} chars={len(text)} saved={out_path}")
        time.sleep(3)


if __name__ == "__main__":
    main()
