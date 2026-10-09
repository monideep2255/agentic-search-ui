"""Ask one question as a fresh guest on develop; save all events. Usage: ask.py LABEL QUESTION"""
import json
import os
import sys
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
label, q = sys.argv[1], sys.argv[2]
def post(path, body, token):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body else None, method="POST")
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
s = "diag-" + uuid.uuid4().hex[:10]
tok = post(f"/auth/guest?session_id={s}", None, None)["guest_token"]
t = time.time()
run = post("/v1/query", {"text": q, "audience_depth": "researcher", "session_id": s}, tok)
req = urllib.request.Request(BASE + f"/v1/query/{run['run_id']}/events")
req.add_header("Accept", "text/event-stream"); req.add_header("Authorization", "Bearer " + tok)
ev = []
with urllib.request.urlopen(req, timeout=180) as r:
    for raw in r:
        l = raw.decode("utf-8", "replace").rstrip("\n")
        if l.startswith("data:"):
            try: ev.append(json.loads(l[5:].strip()))
            except json.JSONDecodeError: pass  # malformed data
el = round(time.time() - t, 1)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw", label + ".json")
with open(out, "w") as f: json.dump({"question": q, "seconds": el, "events": ev}, f, indent=1)
print(label, el, len(ev))
