"""Shared helpers for the 2026-09-26 integrations audit's live runs.

Every function returns a summary dict that is safe to write into the public
report: no token, no sign-in body, no absolute local path. Tokens are read from
`<scratch>/int_secrets/tokens.json`, which this module writes and never prints.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("AUDIT_API", "https://search-agent-api-develop-43b3.up.railway.app")
SCRATCH = Path(__file__).resolve().parent.parent
SECRETS = SCRATCH / "int_secrets"
EVIDENCE = Path(__file__).resolve().parent / "runs"
QUESTION_LOG = Path(__file__).resolve().parent / "question_count.log"


def _post_json(url: str, body: dict, headers: dict | None = None, timeout: float = 30) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, {"raw": raw[:500]}


def count_question(surface: str, question: str) -> int:
    """Append one line per live question, so the 30-question cap is auditable."""
    QUESTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with QUESTION_LOG.open("a") as fh:
        fh.write(f"{time.strftime('%H:%M:%S')}\t{surface}\t{question}\n")
    return sum(1 for _ in QUESTION_LOG.open())


def mint_tokens(label: str) -> None:
    """Sign in both throwaway accounts and mint one guest token. Never prints a value."""
    SECRETS.mkdir(exist_ok=True)
    bodies = json.loads((SCRATCH / f"accounts_{label}.json").read_text())
    tokens: dict[str, str] = {}
    for name, body in zip(("a", "b"), bodies):
        status, data = _post_json(API + "/auth/login", body)
        print(f"login {name}: HTTP {status}")
        tokens[name] = data["access_token"]
        tokens[name + "_refresh"] = data["refresh_token"]
    status, data = _post_json(API + "/auth/guest", {})
    print(f"guest: HTTP {status}")
    tokens["guest"] = data["guest_token"]
    (SECRETS / "tokens.json").write_text(json.dumps(tokens))
    os.chmod(SECRETS / "tokens.json", 0o600)


def token(name: str) -> str:
    return json.loads((SECRETS / "tokens.json").read_text())[name]


def first_sentence(text: str) -> str:
    text = " ".join(text.split())
    m = re.search(r"(.+?[.?!])(\s|$)", text)
    return (m.group(1) if m else text)[:300]


def classify(outcome: str | None, n_citations: int, answer: str) -> str:
    if outcome == "refuse":
        return "refused"
    if outcome == "ask" and n_citations == 0:
        return "asked back"
    if n_citations > 0:
        return "answered"
    return f"no citations ({outcome})"


def save(name: str, summary: dict) -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / f"{name}.json").write_text(json.dumps(summary, indent=2))
    return summary


# ---------------------------------------------------------------------------
# REST plus the event stream: the web app's own path.
# ---------------------------------------------------------------------------

def rest_ask(tok: str, text: str, session_id: str, depth: str | None = None, timeout: float = 240) -> dict:
    t0 = time.time()
    body: dict = {"text": text, "session_id": session_id}
    if depth is not None:
        body["audience_depth"] = depth
    status, data = _post_json(API + "/v1/query", body, {"Authorization": f"Bearer {tok}"})
    summary: dict = {"surface": "REST+SSE", "question": text, "session_id": session_id,
                     "depth_sent": depth, "create_status": status}
    if status != 202:
        summary["error"] = data
        return summary
    summary["persona_name"] = data.get("persona_name")
    return rest_stream(tok, data["run_id"], summary, t0, timeout)


def rest_stream(tok: str, run_id: str, summary: dict, t0: float, timeout: float = 240) -> dict:
    summary["run_id"] = run_id
    req = urllib.request.Request(
        f"{API}/v1/query/{run_id}/events",
        headers={"Authorization": f"Bearer {tok}", "Accept": "text/event-stream"},
    )
    types: list[str] = []
    tokens_text: list[str] = []
    citations: list[dict] = []
    done: dict | None = None
    think: list[dict] = []
    errors: list[dict] = []
    trust_answer: dict | None = None
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        summary["stream_status"] = resp.status
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if line.startswith("data:"):
                env = json.loads(line[5:].strip())
                types.append(env["type"])
                p = env["payload"]
                if env["type"] == "token":
                    tokens_text.append(p.get("text", ""))
                elif env["type"] == "citation":
                    citations.append(p)
                elif env["type"] == "think":
                    think.append(p)
                elif env["type"] == "error":
                    errors.append(p)
                elif env["type"] == "trust_signal" and p.get("scope") == "answer":
                    trust_answer = p
                elif env["type"] == "done":
                    done = p
                    break
                if env["type"] == "error" and p.get("fatal"):
                    break
    answer = "".join(tokens_text).strip()
    summary.update(_common(answer, citations, (done or {}).get("trust_outcome")))
    summary["event_type_counts"] = {t: types.count(t) for t in dict.fromkeys(types)}
    summary["clarifying_question"] = next((t.get("clarifying_question") for t in think if t.get("clarifying_question")), None)
    summary["clarifying_options"] = next((t.get("clarifying_options") for t in think if t.get("clarifying_options")), None)
    summary["think_narratives"] = [t.get("narrative", "")[:200] for t in think]
    summary["resolved_entities"] = [f"{e.get('text')}={e.get('curie')}" for t in think for e in (t.get("resolved_entities") or [])]
    if done:
        summary["done_trust_line"] = done.get("trust_line")
        summary["done_next_step"] = done.get("next_step")
        summary["done_decisions"] = [
            {k: d.get(k) for k in ("name", "chosen", "decided_by", "fallback_reason")}
            for d in (done.get("decisions") or [])
        ]
        summary["done_total_tool_calls"] = done.get("total_tool_calls")
        summary["done_elapsed_ms"] = done.get("elapsed_ms")
    summary["answer_trust_signal_message"] = (trust_answer or {}).get("message")
    summary["errors"] = [{k: e.get(k) for k in ("scope", "fatal", "error_class")} for e in errors]
    summary["wall_s"] = round(time.time() - t0, 1)
    return summary


def _common(answer: str, citations: list[dict], outcome: str | None) -> dict:
    urls = [c.get("source_url") or c.get("sourceUrl") for c in citations]
    hosts = sorted({re.sub(r"^https://([^/]+)/.*$", r"\1", u or "") for u in urls})
    return {
        "outcome": classify(outcome, len(citations), answer),
        "trust_outcome": outcome,
        "citation_count": len(citations),
        "citation_hosts": hosts,
        "citation_urls_sample": urls[:5],
        "first_sentence": first_sentence(answer),
        "answer_chars": len(answer),
        "answer_head": answer[:1200],
    }


# ---------------------------------------------------------------------------
# GraphQL
# ---------------------------------------------------------------------------

GQL_FULL = (
    "mutation Ask($input: AskInput!) { ask(input: $input) { runId personaName answer "
    "trustSignal { outcome riskTier grounded message } "
    "citations { sourceUrl source layer } disclosures { __typename } } }"
)


def graphql_ask(tok: str, text: str, session_id: str, depth: str | None = None) -> dict:
    t0 = time.time()
    variables: dict = {"input": {"text": text, "sessionId": session_id}}
    if depth is not None:
        variables["input"]["audienceDepth"] = depth
    status, data = _post_json(
        API + "/graphql", {"query": GQL_FULL, "variables": variables},
        {"Authorization": f"Bearer {tok}"}, timeout=300,
    )
    summary: dict = {"surface": "GraphQL", "question": text, "session_id": session_id,
                     "depth_sent": depth, "http_status": status}
    if data.get("errors"):
        summary["graphql_errors"] = [e.get("message", "")[:300] for e in data["errors"]]
    ask = (data.get("data") or {}).get("ask")
    if ask:
        summary.update(_common(ask["answer"], ask["citations"], ask["trustSignal"]["outcome"]))
        summary["trust_signal"] = ask["trustSignal"]
        summary["persona_name"] = ask.get("personaName")
    summary["wall_s"] = round(time.time() - t0, 1)
    return summary


# ---------------------------------------------------------------------------
# MCP over streamable HTTP, with the MCP Python SDK client
# ---------------------------------------------------------------------------

async def _mcp(tok: str | None, calls: list[tuple[str, dict]], url: str) -> dict:
    import httpx2
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    out: dict = {"url": url}
    headers = {"Authorization": f"Bearer {tok}"} if tok else None
    async with (
        httpx2.AsyncClient(headers=headers, follow_redirects=False, timeout=httpx2.Timeout(300.0)) as http,
        streamable_http_client(url, http_client=http) as (read, write),
        ClientSession(read, write) as session,
    ):
        init = await session.initialize()
        out["server_info"] = {"name": init.server_info.name, "version": init.server_info.version}
        out["protocol_version"] = init.protocol_version
        tools = await session.list_tools()
        out["tools"] = [
            {"name": t.name, "input_schema": t.input_schema, "has_output_schema": t.output_schema is not None}
            for t in tools.tools
        ]
        prompts_resources: dict = {}
        for label, fn in (("prompts", session.list_prompts), ("resources", session.list_resources)):
            try:
                r = await fn()
                prompts_resources[label] = len(getattr(r, label))
            except Exception as exc:  # noqa: BLE001 - recorded, not raised
                prompts_resources[label] = f"{type(exc).__name__}: {str(exc)[:120]}"
        out["prompts_resources"] = prompts_resources
        results = []
        for name, args in calls:
            t0 = time.time()
            try:
                res = await session.call_tool(name, args)
                sc = res.structured_content
                item: dict = {"tool": name, "args": args, "is_error": res.is_error}
                if res.is_error:
                    item["error_text"] = " ".join(getattr(c, "text", "") for c in res.content)[:500]
                elif sc:
                    item.update(_common(sc.get("answer", ""), sc.get("citations", []),
                                        (sc.get("trust_signal") or {}).get("outcome")))
                    item["trust_signal"] = sc.get("trust_signal")
                    item["persona_name"] = sc.get("persona_name")
                    item["structured_keys"] = sorted(sc.keys())
                else:
                    item["content_text"] = " ".join(getattr(c, "text", "") for c in res.content)[:500]
            except Exception as exc:  # noqa: BLE001 - recorded, not raised
                item = {"tool": name, "args": args, "exception": f"{type(exc).__name__}: {str(exc)[:300]}"}
            item["wall_s"] = round(time.time() - t0, 1)
            results.append(item)
        out["calls"] = results
    return out


def mcp_session(tok: str | None, calls: list[tuple[str, dict]], url: str | None = None) -> dict:
    return asyncio.run(_mcp(tok, calls, url or API + "/mcp/"))


# ---------------------------------------------------------------------------
# The `s3` console command, from the wheel installed into <scratch>/int_prefix
# ---------------------------------------------------------------------------

VENV_PY = Path(os.environ.get("AUDIT_VENV_PY", "")) if os.environ.get("AUDIT_VENV_PY") else None
PREFIX = SCRATCH / "int_prefix"


def s3_env(cred_dir: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GRAPH_", "S3_"))}
    site = PREFIX / "lib" / "python3.11" / "site-packages"
    env["PYTHONPATH"] = str(site)
    env["S3_CREDENTIALS_PATH"] = str(cred_dir / "credentials.json")
    return env


def run_cmd(argv: list[str], env: dict, stdin: str | None = None, timeout: float = 300) -> dict:
    t0 = time.time()
    p = subprocess.run(argv, input=stdin, capture_output=True, text=True, env=env,
                       timeout=timeout, check=False)
    scrub = str(SCRATCH)
    return {
        "argv": [a.replace(scrub, "<scratch>") for a in argv],
        "exit": p.returncode,
        "stdout": p.stdout.replace(scrub, "<scratch>")[-4000:],
        "stderr": p.stderr.replace(scrub, "<scratch>")[-3000:],
        "wall_s": round(time.time() - t0, 1),
    }


# ---------------------------------------------------------------------------
# The Integrations page's printed snippets, read from the page's own source
# ---------------------------------------------------------------------------

def page_snippets(source_path: Path, origin: str) -> dict[str, str]:
    """Each `export const NAME = \\`...\\`` template literal, as the Copy button
    puts it on the clipboard: `${API_ORIGIN}` filled in, `\\\\` unescaped."""
    src = source_path.read_text()
    out: dict[str, str] = {}
    for name in ("REST_EXAMPLE", "GRAPHQL_EXAMPLE", "MCP_CONFIG", "CLI_EXAMPLE",
                 "KGX_EXAMPLE", "EVENT_STREAM_EXAMPLE"):
        m = re.search(r"export const " + name + r" = `(.*?)`;", src, re.DOTALL)
        if not m:
            continue
        text = m.group(1).replace("${API_ORIGIN}", origin)
        text = re.sub(r"\\(.)", r"\1", text)
        out[name] = text
    return out


def parse_s3_stdout(stdout: str) -> dict:
    lines = stdout.splitlines()
    outcome = None
    cut = len(lines)
    for i, line in enumerate(lines):
        m = re.fullmatch(r"\[(answer|flag|ask|refuse)\]", line.strip())
        if m:
            outcome, cut = m.group(1), i
            break
    answer = "\n".join(lines[:cut]).strip()
    refs = [ln for ln in lines if re.match(r"^\[\d+\] .* - https://", ln)]
    urls = [ln.rsplit(" - ", 1)[1].strip() for ln in refs]
    return _common(answer, [{"source_url": u} for u in urls], outcome)
