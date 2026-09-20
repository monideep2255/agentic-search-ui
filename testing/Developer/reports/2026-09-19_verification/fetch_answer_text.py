"""One-off, read-only helper for the 2026-09-19 verification's answer-quality
spot check (step 3). Fires exactly two queries (BRCA1 researcher, HNF1A
researcher), reassembles the token stream into the displayed answer text,
and writes it to a JSON file for inspection. Not part of the tracked
reliability measurement and does not touch any tracked file.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"

TARGETS = [
    ("Which diseases are associated with BRCA1?", "researcher"),
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


out = []
for q, depth in TARGETS:
    session = "veri-qc-" + uuid.uuid4().hex[:8]
    token = post(f"/auth/guest?session_id={session}", None, None)["guest_token"]
    run = post("/v1/query", {"text": q, "audience_depth": depth, "session_id": session}, token)
    events = stream(run["run_id"], token)
    tokens = [e["payload"].get("text", "") for e in events if e.get("type") == "token"]
    text = "".join(tokens)
    done = next((e for e in events if e.get("type") == "done"), None)
    outcome = done["payload"]["trust_outcome"] if done else "no_done"
    out.append({"question": q, "audience_depth": depth, "outcome": outcome, "answer_text": text})
    print(f"{q} [{depth}] -> outcome={outcome} chars={len(text)}")
    time.sleep(2)

with open(sys.argv[1] if len(sys.argv) > 1 else "answer_text.json", "w") as f:
    json.dump(out, f, indent=2)
