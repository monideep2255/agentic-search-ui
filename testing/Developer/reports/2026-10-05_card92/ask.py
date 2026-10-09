"""Ask card 92 questions as a fresh guest each run; save all events to raw/. No tokens saved."""
import json
import os
import sys
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
Q = {
 "q27": "What ACMG-relevant evidence is available for a copy number variant spanning chr17:43,044,295-43,125,364 on GRCh38? List the overlapping genes, dbVar records and ClinVar entries.",
 "q29": "What genes and ClinVar records are under chr7:117,480,025-117,668,665 on GRCh38?",
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
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
    with urllib.request.urlopen(req, timeout=240) as r:
        for raw in r:
            l = raw.decode("utf-8", "replace").rstrip("\n")
            if l.startswith("data:"):
                try: out.append(json.loads(l[5:].strip()))
                except json.JSONDecodeError: pass  # malformed data
    return out
for name, run_n in [a.split(":") for a in sys.argv[1:]]:
    s = "c92-" + uuid.uuid4().hex[:10]
    tok = post(f"/auth/guest?session_id={s}", None, None)["guest_token"]
    t = time.time()
    run = post("/v1/query", {"text": Q[name], "audience_depth": "researcher", "session_id": s}, tok)
    ev = stream(run["run_id"], tok)
    with open(f"{OUT}/{name}_run{run_n}.json", "w") as f: json.dump(ev, f, indent=1)
    from collections import Counter
    print(name, run_n, round(time.time()-t,1), Counter(e.get("type") for e in ev))
