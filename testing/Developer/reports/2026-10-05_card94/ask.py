"""Card 94 diagnosis: ask one or more questions in ONE fresh guest session on
develop, in a chosen answer mode, and save the raw event stream per turn.

Usage: python ask.py <label> <audience_depth> "<question 1>" ["<follow-up>" ...]

Each later question is a follow-up in the same session, which is how the web
app sends one (same session_id, `frontend/src/App.tsx`). Copied from
`testing/Developer/scripts/flagship_measure.py`. The guest token is held in
memory only and never written to disk. Output: raw/<label>_turn<N>.json and a
one-line summary per turn on stdout.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
RAW = Path(__file__).resolve().parent / "raw"


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
    with urllib.request.urlopen(req, timeout=240) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").rstrip("\n")
            if line.startswith("data:"):
                try:
                    out.append(json.loads(line[5:].strip()))
                except json.JSONDecodeError:
                    pass
    return out


def main() -> None:
    label, depth, questions = sys.argv[1], sys.argv[2], sys.argv[3:]
    RAW.mkdir(exist_ok=True)
    session = "card94-" + uuid.uuid4().hex[:10]
    token = post(f"/auth/guest?session_id={session}", None, None)["guest_token"]
    for turn, question in enumerate(questions, start=1):
        started = time.time()
        record = {"label": label, "turn": turn, "depth": depth, "question": question}
        try:
            run = post(
                "/v1/query",
                {"text": question, "audience_depth": depth, "session_id": session},
                token,
            )
            events = stream(run["run_id"], token)
            record["events"] = events
        except Exception as exc:  # noqa: BLE001
            record["transport_error"] = f"{type(exc).__name__}: {exc}"[:300]
            events = []
        record["elapsed_s"] = round(time.time() - started, 1)
        (RAW / f"{label}_turn{turn}.json").write_text(json.dumps(record, indent=1))
        done = next((e for e in events if e.get("type") == "done"), None)
        fatal = next(
            (e for e in events if e.get("type") == "error" and e["payload"].get("fatal")), None
        )
        tools = [e["payload"].get("tool") for e in events if e.get("type") == "tool_call"]
        cites = sum(1 for e in events if e.get("type") == "citation")
        outcome = "error" if fatal else (done["payload"].get("trust_outcome") if done else "no_done")
        print(
            f"{label} turn {turn}: {outcome} {record['elapsed_s']}s tools={tools} "
            f"citations={cites} fatal={fatal['payload'] if fatal else None}"
        )


if __name__ == "__main__":
    main()
