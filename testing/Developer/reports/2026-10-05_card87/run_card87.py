"""Card 87 live runs on develop, guest only. Saves raw events (no tokens)."""
import json
import os
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
QS = ["recent-onset diabetes treatment"] * 6 + [
    "recent papers on statins", "papers on statins since 2022",
    "reflux disease", "Any trials for GERD?"]

def post(path, body, token):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)

def stream(run_id, token):
    req = urllib.request.Request(BASE + f"/v1/query/{run_id}/events")
    req.add_header("Accept", "text/event-stream")
    req.add_header("Authorization", "Bearer " + token)
    out = []
    with urllib.request.urlopen(req, timeout=180) as r:
        for raw in r:
            l = raw.decode("utf-8", "replace").rstrip("\n")
            if l.startswith("data:"):
                try: out.append(json.loads(l[5:].strip()))
                except json.JSONDecodeError: pass  # malformed data
    return out

for i, q in enumerate(QS, 1):
    s = "c87-" + uuid.uuid4().hex[:10]
    tok = post(f"/auth/guest?session_id={s}", None, None)["guest_token"]
    t = time.time()
    run = post("/v1/query", {"text": q, "audience_depth": "researcher", "session_id": s}, tok)
    ev = stream(run["run_id"], tok)
    el = round(time.time() - t, 1)
    with open(f"{OUT}/run{i:02d}.json", "w") as f: json.dump({"q": q, "seconds": el, "events": ev}, f, indent=1)
    done = next((e for e in ev if e.get("type") == "done"), {})
    print(i, q, el, done.get("payload", {}).get("trust_outcome"), flush=True)
