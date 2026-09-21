"""Ask each flagship question N times on develop, each in a fresh guest
session, and record per run: outcome, elapsed, the citation source ids.
Prints one line per run and a per-question summary of how many distinct
source SETS were seen (1 means every run returned the same sources)."""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from collections import Counter

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
QUESTIONS = [
    ("What diseases are caused by variants in the HNF1A gene?", "researcher"),
    ("What genes are associated with MODY?", "researcher"),
    ("Which diseases are associated with BRCA1?", "plain_language"),
]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5


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
for q, depth in QUESTIONS:
    key = f"{q} [{depth}]"
    results[key] = []
    for i in range(N):
        session = "flag-" + uuid.uuid4().hex[:10]
        token = post(f"/auth/guest?session_id={session}", None, None)["guest_token"]
        started = time.time()
        try:
            run = post("/v1/query", {"text": q, "audience_depth": depth, "session_id": session}, token)
            events = stream(run["run_id"], token)
        except Exception as exc:  # noqa: BLE001
            results[key].append(("transport_error", 0, frozenset(), str(exc)[:80]))
            print(f"{key[:45]:45} run {i+1}: transport_error")
            continue
        elapsed = round(time.time() - started, 1)
        done = next((e for e in events if e.get("type") == "done"), None)
        error = next((e for e in events if e.get("type") == "error" and e["payload"].get("fatal")), None)
        sources = frozenset(e["payload"]["source_id"] for e in events if e.get("type") == "citation")
        outcome = "error" if error else (done["payload"]["trust_outcome"] if done else "no_done")
        if outcome in ("answer", "ask", "flag") and not sources:
            outcome = "no_sources"
        results[key].append((outcome, elapsed, sources, error["payload"]["source"] if error else ""))
        print(f"{key[:45]:45} run {i+1}: {outcome:10} {elapsed:5}s sources={len(sources)}")

print("\n=== summary ===")
for key, rows in results.items():
    answered = sum(1 for r in rows if r[0] in ("answer", "ask", "flag"))
    sets = Counter(r[2] for r in rows if r[2])
    print(f"{key[:50]:50} answered {answered} of {len(rows)} | distinct source sets {len(sets)} | sizes {[len(s) for s in sets]}")
