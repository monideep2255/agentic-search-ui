"""Ask the Mediterranean question N times, each in a fresh guest session; save raw events (no tokens)."""
import json
import os
import sys
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
Q = "Are there any beneficial variants typically found in people of mediterranean descent?"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
N = int(sys.argv[1]); START = int(sys.argv[2])
def post(path, body, token):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
def stream(run_id, token):
    req = urllib.request.Request(BASE + f"/v1/query/{run_id}/events")
    req.add_header("Accept", "text/event-stream"); req.add_header("Authorization", "Bearer " + token)
    out = []
    with urllib.request.urlopen(req, timeout=180) as r:
        for raw in r:
            l = raw.decode("utf-8", "replace").rstrip("\n")
            if l.startswith("data:"):
                try: out.append(json.loads(l[5:].strip()))
                except json.JSONDecodeError: pass  # malformed data
    return out
for i in range(START, START + N):
    s = "med-" + uuid.uuid4().hex[:10]
    tok = post(f"/auth/guest?session_id={s}", None, None)["guest_token"]
    t = time.time()
    run = post("/v1/query", {"text": Q, "audience_depth": "plain_language", "session_id": s}, tok)
    ev = stream(run["run_id"], tok)
    el = round(time.time() - t, 1)
    with open(f"{OUT}/run{i}.json", "w") as f: json.dump({"run": i, "seconds": el, "events": ev}, f, indent=1)
    print(i, el, len(ev), flush=True)
