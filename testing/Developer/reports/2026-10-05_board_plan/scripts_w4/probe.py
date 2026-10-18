"""W4: six guest questions on develop; record outcome, fatal error class and source, elapsed."""
import json
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
QS = [
    "What is the function of TP53?",
    "Which diseases are associated with CFTR?",
    "What is the clinical significance of BRCA2 variants?",
    "Tell me about the gene APOE",
    "What conditions are linked to LDLR?",
    "What does the gene HBB do?",
]

def post(path, body, token):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def stream(rid, token):
    req = urllib.request.Request(BASE + f"/v1/query/{rid}/events")
    req.add_header("Accept", "text/event-stream")
    req.add_header("Authorization", "Bearer " + token)
    out = []
    with urllib.request.urlopen(req, timeout=180) as r:
        for raw in r:
            l = raw.decode("utf-8", "replace").rstrip("\n")
            if l.startswith("data:"):
                try:
                    out.append(json.loads(l[5:].strip()))
                except json.JSONDecodeError:
                    pass
    return out

for q in QS:
    s = "w4-" + uuid.uuid4().hex[:10]
    tok = post(f"/auth/guest?session_id={s}", None, None)["guest_token"]
    t = time.time()
    try:
        run = post("/v1/query", {"text": q, "audience_depth": "researcher", "session_id": s}, tok)
        ev = stream(run["run_id"], tok)
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        print(q[:40], "transport_error", str(e)[:80]); continue
    el = round(time.time() - t, 1)
    done = next((e for e in ev if e.get("type") == "done"), None)
    err = next((e for e in ev if e.get("type") == "error" and e["payload"].get("fatal")), None)
    print(f"{q[:45]:45} {el:5}s outcome={(done or {}).get('payload',{}).get('trust_outcome')} fatal={(err or {}).get('payload',{}).get('error_class')} src={(err or {}).get('payload',{}).get('source')}")
