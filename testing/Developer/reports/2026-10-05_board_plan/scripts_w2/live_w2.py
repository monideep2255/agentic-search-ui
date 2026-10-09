"""W2 scout: five live guest questions on develop. Prints a short summary, saves no tokens."""
import json
import time
import urllib.request
import uuid

BASE = "https://search-agent-api-develop-43b3.up.railway.app"
QS = [
    "What is rs334 and what condition is it associated with?",
    "How do birds fly?",
    "Find SRA runs of SARS-CoV-2 sequenced on Illumina from clinical respiratory samples",
    "Which Mycobacterium tuberculosis genome assemblies are available, and how do I retrieve them?",
    "For PMID 11237011, what sequence data, BioProjects, GEO series and assemblies are linked to it? Mark each link as direct, inferred, or absent.",
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
for q in QS:
    s = "w2-" + uuid.uuid4().hex[:10]
    tok = post(f"/auth/guest?session_id={s}", None, None)["guest_token"]
    t = time.time()
    run = post("/v1/query", {"text": q, "audience_depth": "researcher", "session_id": s}, tok)
    ev = stream(run["run_id"], tok)
    el = round(time.time() - t, 1)
    done = next((e for e in ev if e.get("type") == "done"), {}).get("payload", {})
    think = next((e for e in ev if e.get("type") == "think"), {}).get("payload", {})
    tools = [(e["payload"].get("tool"), e["payload"].get("status")) for e in ev if e.get("type") == "tool_result"]
    text = "".join(e["payload"].get("text", "") for e in ev if e.get("type") == "token")
    print("Q:", q[:70]); print("  s", el, "outcome", done.get("trust_outcome"), "class", think.get("query_class"),
          "entities", [x.get("text") for x in think.get("resolved_entities", [])], "tools", tools)
    print("  text:", text[:420].replace("\n", " ")); print()
