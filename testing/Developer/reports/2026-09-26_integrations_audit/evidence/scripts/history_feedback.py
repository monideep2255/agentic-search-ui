"""History, reopen and feedback across the surfaces, spending no questions.

For each principal used in the parity runs (guest = REST, account a = GraphQL
and s3, account b = MCP): list /v1/history, reopen every saved answer, and
rate one run through POST /v1/query/{run_id}/feedback. The reopened s3 answers
replace the truncated s3 stdout captured by parity_runs.py.
"""
import json
import urllib.request

import live_lib as L


def get(path: str, tok: str) -> tuple[int, dict]:
    req = urllib.request.Request(L.API + path, headers={"Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, {"raw": exc.read().decode(errors="replace")[:300]}


out: dict = {}
for who, label in (("guest", "REST (guest)"), ("a", "GraphQL and s3 (account a)"), ("b", "MCP (account b)")):
    tok = L.token(who)
    status, hist = get("/v1/history?limit=20", tok)
    rows = hist.get("items") or hist.get("entries") or hist.get("history") or []
    entry = {"history_status": status, "history_keys": sorted(hist.keys()), "rows": []}
    for r in rows:
        row = {k: r.get(k) for k in ("trace_id", "question", "trust_signal", "citation_count", "has_saved_answer")}
        if r.get("has_saved_answer"):
            s, ans = get(f"/v1/history/{r['trace_id']}/answer", tok)
            row["reopen_status"] = s
            if s == 200:
                md = ans.get("answer_markdown", "")
                row["reopen_depth"] = ans.get("depth")
                row["reopen_citations"] = len(ans.get("citations") or [])
                row["reopen_trust_line"] = ans.get("trust_line")
                row["reopen_first_sentence"] = L.first_sentence(md)
                row["reopen_answer_head"] = md[:600]
        entry["rows"].append(row)
    out[label] = entry
    print(f"== {label}: history HTTP {status}, {len(rows)} rows")
    for row in entry["rows"]:
        print(f"   {row['question'][:55]!r:60} trust={row['trust_signal']} cites={row['citation_count']} "
              f"saved={row['has_saved_answer']} reopen={row.get('reopen_status')} "
              f"reopen_cites={row.get('reopen_citations')} :: {str(row.get('reopen_first_sentence'))[:90]}")

# Feedback: one REST run (guest), one GraphQL run (account a), one MCP run (account b).
fb: dict = {}
targets = {
    "REST run, guest token": ("guest", json.loads((L.EVIDENCE / "rest_03_what.json").read_text())["run_id"]),
    "MCP run, account b token over REST": ("b", next(r["trace_id"] for r in out["MCP (account b)"]["rows"] if "Marfan" in r["question"])),
}
gql = json.loads((L.EVIDENCE / "graphql_03_what.json").read_text())
for label, (who, run_id) in targets.items():
    status, body = L._post_json(f"{L.API}/v1/query/{run_id}/feedback",
                                {"rating": "up", "comment": "integrations audit 2026-09-26, test rating"},
                                {"Authorization": f"Bearer {L.token(who)}"})
    fb[label] = {"status": status, "body": body}
    print(f"feedback {label}: HTTP {status} {json.dumps(body)[:160]}")
fb["GraphQL run"] = "GraphQL's AskResult returns a runId; the schema has no feedback mutation (see schema.py)"
L.save("history_and_feedback", {"history": out, "feedback": fb})
