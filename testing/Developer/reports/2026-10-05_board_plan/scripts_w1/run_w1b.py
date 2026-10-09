"""W1 scout: five live guest runs on develop; saves a compact summary per run (no tokens)."""
import json
import os
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
RUNS = [("mody_c", "What genes are associated with MODY?", "plain_language")]
_OLD = [
    ("mody_a", "What genes are associated with MODY?", "plain_language"),
    ("mody_b", "What genes are associated with MODY?", "researcher"),
    ("brca1_path", "Which BRCA1 variants are pathogenic?", "researcher"),
    ("brca1_dis", "Which diseases are associated with BRCA1?", "researcher"),
    ("brca1_what", "What is BRCA1?", "plain_language"),
]
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
for name, q, depth in RUNS:
    s = "w1-" + uuid.uuid4().hex[:10]
    tok = post(f"/auth/guest?session_id={s}", None, None)["guest_token"]
    t = time.time()
    run = post("/v1/query", {"text": q, "audience_depth": depth, "session_id": s}, tok)
    ev = stream(run["run_id"], tok)
    el = round(time.time() - t, 1)
    toks = [e["payload"].get("text", "") for e in ev if e.get("type") == "token"]
    cits = [(e["payload"].get("display_index"), e["payload"].get("source_id"), e["payload"].get("claim_text", "")[:300]) for e in ev if e.get("type") == "citation"]
    done = next((e["payload"] for e in ev if e.get("type") == "done"), {})
    summ = {"name": name, "q": q, "depth": depth, "seconds": el, "trust_outcome": done.get("trust_outcome"),
            "trust_line": done.get("trust_line"), "tokens": toks, "errors": [e["payload"] for e in ev if e.get("type")=="error"], "citations": cits,
            "types": sorted({e.get("type") for e in ev})}
    with open(f"{OUT}/{name}.json", "w") as f: json.dump(summ, f, indent=1)
    print(name, el, done.get("trust_outcome"), len(toks), len(cits), flush=True)
