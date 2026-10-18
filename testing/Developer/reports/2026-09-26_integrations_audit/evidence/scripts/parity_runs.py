"""The parity runs: the same questions through the web's own path (REST plus
the event stream), GraphQL, MCP and `s3`, four surfaces in parallel, each
surface's questions in order so a follow-up follows its first question.

Budget: REST 5, GraphQL 4, MCP 5, s3 5 = 19 live questions. Each one is
logged to question_count.log before it is sent.
"""
import json
import os
import subprocess
import tempfile
import threading
import time
import traceback
from pathlib import Path

import live_lib as L

BRCA1 = "Which diseases are associated with BRCA1?"
MARFAN = "What are the clinical features of Marfan syndrome?"
FOLLOW = "What variants of it are pathogenic?"
BLACK = "Tell me about black holes."
BARE = "GERD"

SNIPS = L.page_snippets(L.SCRATCH / "int_tree/frontend/src/components/screens/InfoScreens.tsx", L.API)
RESULTS: dict[str, list] = {}


def _record(surface: str, name: str, summary: dict) -> None:
    L.save(name, summary)
    RESULTS.setdefault(surface, []).append({"name": name, **{
        k: summary.get(k) for k in ("question", "outcome", "trust_outcome", "citation_count",
                                   "first_sentence", "wall_s", "graphql_errors", "error")
    }})
    print(f"[{surface}] {name}: {summary.get('outcome')} cites={summary.get('citation_count')} "
          f"wall={summary.get('wall_s')} :: {str(summary.get('first_sentence'))[:140]}", flush=True)


def _run_snippet(snippet: str, tok: str) -> dict:
    t0 = time.time()
    env = {**os.environ, "TOKEN": tok}
    p = subprocess.run(["bash", "-c", snippet], capture_output=True, text=True, env=env,
                       timeout=320, check=False)
    return {"exit": p.returncode, "stdout": p.stdout, "stderr_tail": p.stderr[-400:], "wall_s": round(time.time() - t0, 1)}


def rest_worker() -> None:
    tok = L.token("guest")
    # 1. REST_EXAMPLE exactly as the Copy button gives it, $TOKEN = a guest token.
    L.count_question("REST", BRCA1 + " [page snippet]")
    t0 = time.time()
    out = _run_snippet(SNIPS["REST_EXAMPLE"], tok)
    body = json.loads(out["stdout"])
    L.save("rest_00_page_snippet_raw", {"command": SNIPS["REST_EXAMPLE"], **out, "stdout": body})
    summary = {"surface": "REST+SSE", "question": BRCA1, "session_id": "demo-1", "via": "page snippet, then the event stream"}
    _record("REST", "rest_01_brca1_page_snippet", L.rest_stream(tok, body["run_id"], summary, t0))
    for i, (q, sid) in enumerate([(FOLLOW, "demo-1"), (MARFAN, "audit-rest-marfan"),
                                   (BLACK, "audit-rest-black"), (BARE, "audit-rest-bare")], start=2):
        L.count_question("REST", q)
        _record("REST", f"rest_0{i}_{q.split()[0].lower().strip('?.')}", L.rest_ask(tok, q, sid))


def graphql_worker() -> None:
    tok = L.token("a")
    L.count_question("GraphQL", BRCA1 + " [page snippet]")
    out = _run_snippet(SNIPS["GRAPHQL_EXAMPLE"], tok)
    try:
        data = json.loads(out["stdout"])
    except ValueError:
        data = {"unparsed": out["stdout"][:1000]}
    L.save("graphql_00_page_snippet_raw", {"command": SNIPS["GRAPHQL_EXAMPLE"], **out, "stdout": data})
    ask = (data.get("data") or {}).get("ask") or {}
    summary = {"surface": "GraphQL", "question": BRCA1, "session_id": "demo-1", "via": "page snippet",
               "graphql_errors": [e.get("message") for e in data.get("errors", [])] or None,
               **L._common(ask.get("answer", ""), ask.get("citations", []), None), "wall_s": out["wall_s"]}
    summary["outcome"] = "answered" if summary["citation_count"] else "no citations (page query asks for no trust signal)"
    _record("GraphQL", "graphql_01_brca1_page_snippet", summary)
    for i, (q, sid) in enumerate([(FOLLOW, "demo-1"), (MARFAN, "audit-gql-marfan"), (BLACK, "audit-gql-black")], start=2):
        L.count_question("GraphQL", q)
        _record("GraphQL", f"graphql_0{i}_{q.split()[0].lower().strip('?.')}", L.graphql_ask(tok, q, sid))


def mcp_worker() -> None:
    tok = L.token("b")
    calls = [
        ("ask_biomedical_question", {"query": BRCA1, "session_id": "audit-mcp-brca1"}),
        ("ask_biomedical_question", {"query": FOLLOW, "session_id": "audit-mcp-brca1"}),
        ("ask_biomedical_question", {"query": MARFAN}),
        ("ask_biomedical_question", {"query": BLACK}),
        ("ask_biomedical_question", {"query": BARE}),
    ]
    for _, a in calls:
        L.count_question("MCP", a["query"])
    res = L.mcp_session(tok, calls)
    L.save("mcp_03_parity_session", res)
    for i, c in enumerate(res["calls"], start=1):
        c = {"surface": "MCP", "question": c["args"]["query"], **c}
        _record("MCP", f"mcp_1{i}_{c['question'].split()[0].lower().strip('?.')}", c)


def s3_worker() -> None:
    bodies = json.loads((L.SCRATCH / "accounts_20260926int.json").read_text())
    email, secret = bodies[0]["email"], bodies[0]["pass" + "word"]
    cred = Path(tempfile.mkdtemp(prefix="s3cred_", dir=L.SCRATCH / "int_secrets"))
    env = L.s3_env(cred)
    env["S3_BASE_URL"] = L.API  # what the parked page fix prints; the page on develop does not
    s3 = [str(L.PREFIX / "bin" / "s3")]
    login = L.run_cmd(s3 + ["login", email], env, stdin=secret + "\n")
    login["argv"] = [a.replace(email, "<throwaway-email>") for a in login["argv"]]
    L.save("s3_00_login", login)
    print(f"[s3] login exit {login['exit']}: {login['stdout'].strip()[:120]} {login['stderr'].strip()[:200]}", flush=True)
    plan = [
        ("s3_01_page_line_2", ["ask", "diseases linked to BRCA1"]),
        ("s3_02_brca1", ["ask", "--session-id", "audit-cli-brca1", BRCA1]),
        ("s3_03_followup", ["ask", "--session-id", "audit-cli-brca1", FOLLOW]),
        ("s3_04_marfan", ["ask", MARFAN]),
        ("s3_05_black", ["ask", BLACK]),
    ]
    for name, argv in plan:
        L.count_question("s3", argv[-1])
        r = L.run_cmd(s3 + argv, env, timeout=320)
        summary = {"surface": "s3", "question": argv[-1], "argv": r["argv"][1:], "exit": r["exit"],
                   "stderr_tail": r["stderr"][-1500:], "stdout_tail": r["stdout"][-2500:], "wall_s": r["wall_s"],
                   **L.parse_s3_stdout(r["stdout"])}
        _record("s3", name, summary)


def _guard(fn):
    def inner():
        try:
            fn()
        except Exception:  # noqa: BLE001 - print and keep the other surfaces running
            print(f"[{fn.__name__}] CRASHED\n{traceback.format_exc()}", flush=True)
    return inner


threads = [threading.Thread(target=_guard(f)) for f in (rest_worker, graphql_worker, mcp_worker, s3_worker)]
t0 = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()
Path(__file__).with_name("parity_summary.json").write_text(json.dumps(RESULTS, indent=2))
print(f"all done in {time.time() - t0:.0f}s")
