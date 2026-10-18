"""Card 88 reproduction: `GERD`, then the ask-back pick, on develop as a guest.

Usage: python3 repro_card88.py <label> <depth> [pick_text] [--no-bare]

Opens a fresh guest session, asks `GERD` at the given audience depth, reads the
ask-back options from the think event, then asks the pick in the same session
(as the web app's clarifying-option button does: same session, same depth).
Saves every streamed event of each run as JSON lines next to this script.
The guest token is held in memory only and never written to disk.
Approach copied from testing/Developer/scripts/flagship_measure.py.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
HERE = Path(__file__).resolve().parent
DEFAULT_PICK = "What are the typical symptoms and risk factors of GERD?"


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


def ask(text, depth, session, token, out_name):
    started = time.time()
    run = post("/v1/query", {"text": text, "audience_depth": depth, "session_id": session}, token)
    events = stream(run["run_id"], token)
    elapsed = round(time.time() - started, 1)
    with open(HERE / f"{out_name}.jsonl", "w") as fh:
        fh.writelines(json.dumps(e) + "\n" for e in events)
    done = next((e for e in events if e.get("type") == "done"), None)
    outcome = done["payload"]["trust_outcome"] if done else "no_done"
    kinds = {}
    for e in events:
        if e.get("type") == "token":
            k = e["payload"].get("kind") or "none"
            kinds[k] = kinds.get(k, 0) + 1
    claims = [
        e["payload"]["text"] for e in events
        if e.get("type") == "token" and e["payload"].get("kind") in ("claim", None)
    ]
    print(f"{out_name}: depth={depth} outcome={outcome} elapsed={elapsed}s token_kinds={kinds}")
    for c in claims[:12]:
        print("   CLAIM:", c[:160])
    return events, elapsed, outcome


def main():
    label, depth = sys.argv[1], sys.argv[2]
    pick = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else DEFAULT_PICK
    bare = "--no-bare" not in sys.argv
    session = "c88-" + uuid.uuid4().hex[:10]
    token = post(f"/auth/guest?session_id={session}", None, None)["guest_token"]
    if bare:
        events, _, _ = ask("GERD", depth, session, token, f"{label}_bare")
        think = next((e for e in events if e.get("type") == "think"), None)
        opts = (think or {}).get("payload", {}).get("clarifying_options") or []
        print("   options:", opts)
    ask(pick, depth, session, token, f"{label}_pick")


if __name__ == "__main__":
    main()
