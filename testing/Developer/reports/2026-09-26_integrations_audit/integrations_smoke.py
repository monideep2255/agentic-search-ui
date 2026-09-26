"""Integrations smoke: prove every System 3 surface still works, in under two minutes.

One PASS or FAIL line per check, and a non-zero exit on any FAIL. At most four
live questions (REST plus the event stream, GraphQL, MCP and `s3`, one each),
asked in parallel.

Checks, in the order printed:

- health: `GET /health` answers ok.
- api-docs: `/docs` and `/openapi.json` answer, and the schema lists `/v1/query`.
- rest-sse: the web app's own path. A guest token, `POST /v1/query`, then the
  run's event stream to its `done` event. Every event type must be one the v1
  contract declares, the answer must carry at least one citation, and every
  citation link must be on a pinned host.
- graphql: the page's GraphQL document posted with an account token; no errors,
  an answer and at least one citation.
- mcp: the MCP server at the page's URL. `/mcp` must not redirect to plain
  http; initialize and list tools; a call with no token must be refused; a
  call with a token must answer with at least one citation.
- cli: `s3 login` then `s3 ask`, exit 0 and a References block with a link.
- kgx: `s3-kgx-export --help` works, and the printed export, run without graph
  credentials, fails cleanly (a message naming the graph settings, no traceback).
- page (with --page-source): the Integrations page's printed commands still
  match the code: the `s3` lines parse, the `s3` flags the card names exist,
  and the MCP config can carry the bearer token the server requires.

Usage:

    python integrations_smoke.py --api https://<api-origin> \
        --page-source <repo>/frontend/src/components/screens/InfoScreens.tsx \
        --cli-source <repo>

`--cli-source` builds the package wheel from that checkout (no dependencies,
no network, no build isolation) into a temporary prefix and runs the `s3` and
`s3-kgx-export` it installs, which is how an outsider would get them. Without it,
`--s3-bin` and `--kgx-bin` name installed commands, else `s3` and
`s3-kgx-export` are looked up on PATH.

Accounts: by default one throwaway account is signed up for the run
(`smoke-<random>@example.com`). `--accounts-file` reuses the first sign-in body
from a JSON list of `{"email", "password"}` objects instead. No token, email or
password is ever printed.

Needs the MCP Python SDK (`mcp`, `httpx2`) importable for the mcp check; run it
with the project's virtual environment.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

QUESTION = "Which diseases are associated with BRCA1?"
EVENT_TYPES = {
    "guard", "think", "plan", "tool_start", "tool_result", "token", "citation",
    "trust_signal", "cost", "error", "done", "step",
}
# Mirrors contracts/events.py NCBI_SOURCE_URL_PATTERN's hosts.
CITATION_HOST = re.compile(
    r"^https://(?:([A-Za-z0-9-]+\.)*ncbi\.nlm\.nih\.gov/|(?:www\.)?clinicaltrials\.gov/study/|(?:www\.)?omim\.org/)"
)


class Check:
    def __init__(self, name: str) -> None:
        self.name = name
        self.ok = False
        self.detail = "not run"

    def passed(self, detail: str) -> Check:
        self.ok, self.detail = True, detail
        return self

    def failed(self, detail: str) -> Check:
        self.ok, self.detail = False, detail
        return self


# ---------------------------------------------------------------------------
# HTTP helpers, standard library only
# ---------------------------------------------------------------------------

def http(method: str, url: str, body: dict | None = None, headers: dict | None = None,
         timeout: float = 30, follow: bool = True) -> tuple[int, dict, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc.read().decode(errors="replace")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def as_json(text: str) -> dict:
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {"value": value}
    except ValueError:
        return {}


# ---------------------------------------------------------------------------
# The page's printed snippets
# ---------------------------------------------------------------------------

def page_snippets(path: Path, origin: str) -> dict[str, str]:
    """Each exported template literal as the page's Copy button gives it."""
    src = path.read_text()
    out: dict[str, str] = {}
    for name in ("REST_EXAMPLE", "GRAPHQL_EXAMPLE", "MCP_CONFIG", "CLI_EXAMPLE", "KGX_EXAMPLE"):
        m = re.search(r"export const " + name + r" = `(.*?)`;", src, re.DOTALL)
        if m:
            out[name] = re.sub(r"\\(.)", r"\1", m.group(1).replace("${API_ORIGIN}", origin))
    # The card's body text, for the flags it promises.
    m = re.search(r'title="Command line tools"\s+body="([^"]*)"', src)
    if m:
        out["CLI_CARD_BODY"] = m.group(1)
    return out


def shell_data_arg(snippet: str) -> dict | None:
    """The JSON body after `-d '...'` in a printed curl command."""
    m = re.search(r"-d '(.*)'", snippet, re.DOTALL)
    return as_json(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_health(api: str) -> Check:
    c = Check("health")
    status, _, text = http("GET", api + "/health", timeout=20)
    if status == 200 and as_json(text).get("status") == "ok":
        return c.passed(f"ok ({as_json(text).get('app_env')})")
    return c.failed(f"HTTP {status}: {text[:120]}")


def check_docs(api: str) -> Check:
    c = Check("api-docs")
    s1, h1, _ = http("GET", api + "/docs", timeout=20)
    s2, _, t2 = http("GET", api + "/openapi.json", timeout=20)
    paths = as_json(t2).get("paths", {})
    if s1 == 200 and "html" in h1.get("content-type", h1.get("Content-Type", "")) and s2 == 200 and "/v1/query" in paths:
        return c.passed(f"/docs and /openapi.json answer, {len(paths)} paths")
    return c.failed(f"/docs HTTP {s1}, /openapi.json HTTP {s2}, /v1/query listed: {'/v1/query' in paths}")


def check_rest(api: str, body: dict, timeout: float, account_token: str) -> Check:
    c = Check("rest-sse")
    t0 = time.time()
    status, _, text = http("POST", api + "/auth/guest", {}, timeout=20)
    guest = as_json(text).get("guest_token")
    if status != 201 or not guest:
        return c.failed(f"POST /auth/guest HTTP {status}")
    auth = {"Authorization": f"Bearer {guest}"}
    note = ""
    status, _, text = http("POST", api + "/v1/query", body, auth, timeout=30)
    if status == 429:
        # The guest allowance is a daily cap per source, and repeated smoke runs
        # from one machine can use it up. That is not an integration break, so
        # the surface is checked with the account token and the line says so.
        auth, note = {"Authorization": f"Bearer {account_token}"}, " (guest cap used up; checked with the account)"
        status, _, text = http("POST", api + "/v1/query", body, auth, timeout=30)
    run_id = as_json(text).get("run_id")
    if status != 202 or not run_id:
        return c.failed(f"POST /v1/query HTTP {status}: {text[:160]}")
    req = urllib.request.Request(f"{api}/v1/query/{run_id}/events",
                                 headers={**auth, "Accept": "text/event-stream"})
    types: list[str] = []
    citations: list[str] = []
    done: dict | None = None
    fatal = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                env = json.loads(line[5:].strip())
                types.append(env.get("type"))
                if env.get("version") != "v1":
                    return c.failed(f"event version {env.get('version')!r}, expected v1")
                if env["type"] == "citation":
                    citations.append(env["payload"].get("source_url", ""))
                elif env["type"] == "error" and env["payload"].get("fatal"):
                    fatal = env["payload"].get("error_class")
                    break
                elif env["type"] == "done":
                    done = env["payload"]
                    break
                if time.time() - t0 > timeout:
                    return c.failed(f"no done event within {timeout:.0f}s")
    except (TimeoutError, OSError) as exc:
        return c.failed(f"event stream: {type(exc).__name__} after {time.time() - t0:.0f}s")
    unknown = sorted({t for t in types if t not in EVENT_TYPES})
    bad_links = [u for u in citations if not CITATION_HOST.match(u)]
    if fatal:
        return c.failed(f"fatal error event ({fatal})")
    if done is None:
        return c.failed("stream ended without a done event")
    if unknown:
        return c.failed(f"event types outside the v1 contract: {unknown}")
    if not citations:
        return c.failed(f"no citations (trust_outcome {done.get('trust_outcome')})")
    if bad_links:
        return c.failed(f"{len(bad_links)} citation link(s) off the pinned hosts")
    return c.passed(f"{done.get('trust_outcome')}, {len(citations)} citations, {len(types)} events, "
                    f"{time.time() - t0:.0f}s{note}")


def check_graphql(api: str, token: str, body: dict, timeout: float) -> Check:
    c = Check("graphql")
    t0 = time.time()
    status, _, text = http("POST", api + "/graphql", body, {"Authorization": f"Bearer {token}"}, timeout=timeout)
    data = as_json(text)
    if status != 200:
        return c.failed(f"HTTP {status}: {text[:160]}")
    if data.get("errors"):
        return c.failed(f"GraphQL errors: {[e.get('message', '')[:100] for e in data['errors']]}")
    ask = (data.get("data") or {}).get("ask") or {}
    cites = ask.get("citations") or []
    urls = [x.get("sourceUrl", "") for x in cites]
    if not ask.get("answer"):
        return c.failed("empty answer")
    if not cites:
        return c.failed("answer with no citations")
    if any(not CITATION_HOST.match(u) for u in urls if u):
        return c.failed("citation link off the pinned hosts")
    return c.passed(f"{len(cites)} citations, {time.time() - t0:.0f}s")


def check_mcp(api: str, url: str, token: str, timeout: float) -> Check:
    c = Check("mcp")
    t0 = time.time()
    # The bare path must never hand a client a plain-http Location.
    status, headers, _ = http("POST", api + "/mcp", {}, {"Accept": "application/json, text/event-stream"},
                              timeout=20, follow=False)
    location = headers.get("location") or headers.get("Location") or ""
    if status in (301, 302, 307, 308) and location.startswith("http://"):
        return c.failed(f"/mcp redirects to plain http ({status})")
    try:
        import httpx2
        from mcp.client.session import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as exc:
        return c.failed(f"MCP Python SDK not importable here ({exc.name}); run with the project's venv")

    async def call(tok: str | None, args: dict) -> tuple[list[str], object]:
        headers = {"Authorization": f"Bearer {tok}"} if tok else None
        async with (
            httpx2.AsyncClient(headers=headers, timeout=httpx2.Timeout(timeout)) as client,
            streamable_http_client(url, http_client=client) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            tools = [t.name for t in (await session.list_tools()).tools]
            try:
                result: object = await session.call_tool("ask_biomedical_question", args)
            except Exception as exc:  # noqa: BLE001 - the refusal is the expected outcome
                result = exc
            return tools, result

    try:
        tools, refused = asyncio.run(asyncio.wait_for(call(None, {"query": QUESTION}), 30))
        if "ask_biomedical_question" not in tools:
            return c.failed(f"tools listed: {tools}")
        if not (isinstance(refused, Exception) and "bearer token" in str(refused)):
            return c.failed("a call with no token was not refused")
        _, result = asyncio.run(asyncio.wait_for(
            call(token, {"query": QUESTION, "session_id": f"smoke-{uuid.uuid4().hex[:8]}"}), timeout))
    except TimeoutError:
        return c.failed(f"no result within {timeout:.0f}s")
    except BaseException as exc:  # noqa: BLE001 - an ExceptionGroup from the transport is a failure line
        return c.failed(f"{type(exc).__name__}: {str(exc)[:160]}")
    if isinstance(result, Exception):
        return c.failed(f"tool call raised {type(result).__name__}: {str(result)[:160]}")
    if getattr(result, "is_error", False):
        text = " ".join(getattr(x, "text", "") for x in result.content)
        return c.failed(f"tool error: {text[:160]}")
    sc = getattr(result, "structured_content", None) or {}
    cites = sc.get("citations") or []
    if not sc.get("answer") or not cites:
        return c.failed(f"answer {'present' if sc.get('answer') else 'empty'}, {len(cites)} citations")
    if any(not CITATION_HOST.match(x.get("source_url", "")) for x in cites):
        return c.failed("citation link off the pinned hosts")
    return c.passed(f"1 tool, token required, {(sc.get('trust_signal') or {}).get('outcome')}, "
                    f"{len(cites)} citations, {time.time() - t0:.0f}s")


def check_cli(api: str, s3: list[str], env: dict, email: str, secret: str, timeout: float) -> Check:
    c = Check("cli")
    t0 = time.time()
    env = {**env, "S3_BASE_URL": api}
    login = subprocess.run(s3 + ["login", email], input=secret + "\n", capture_output=True, text=True,
                           env=env, timeout=60, check=False)
    if login.returncode != 0:
        return c.failed(f"s3 login exit {login.returncode}: {login.stderr.strip()[-160:]}")
    try:
        ask = subprocess.run(s3 + ["ask", "--session-id", f"smoke-{uuid.uuid4().hex[:8]}", QUESTION],
                             capture_output=True, text=True, env=env, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return c.failed(f"s3 ask did not finish within {timeout:.0f}s")
    refs = re.findall(r"^\[\d+\] .* - (https://\S+)$", ask.stdout, re.MULTILINE)
    if ask.returncode != 0:
        return c.failed(f"s3 ask exit {ask.returncode}: {ask.stderr.strip()[-200:]}")
    if not refs:
        return c.failed("s3 ask printed no References links")
    if any(not CITATION_HOST.match(u) for u in refs):
        return c.failed("a References link is off the pinned hosts")
    tag = re.search(r"^\[(answer|flag|ask|refuse)\]$", ask.stdout, re.MULTILINE)
    return c.passed(f"login ok, [{tag.group(1) if tag else '?'}], {len(refs)} references, {time.time() - t0:.0f}s")


def check_kgx(kgx: list[str], env: dict) -> Check:
    c = Check("kgx")
    env = {k: v for k, v in env.items() if not k.startswith("GRAPH_")}
    helped = subprocess.run(kgx + ["--help"], capture_output=True, text=True, env=env, timeout=60, check=False)
    if helped.returncode != 0:
        last = (helped.stderr.strip().splitlines() or ["no output"])[-1]
        return c.failed(f"s3-kgx-export --help exit {helped.returncode}: {last[:160]}")
    with tempfile.TemporaryDirectory(prefix="kgx_smoke_") as tmp:
        run = subprocess.run(kgx + ["NCBIGene:672", "--hops", "1", "--output-dir", str(Path(tmp) / "out")],
                             capture_output=True, text=True, env=env, timeout=60, check=False)
    if run.returncode == 0:
        return c.passed("export ran (graph credentials present in this environment)")
    if "Traceback" in run.stderr:
        last = (run.stderr.strip().splitlines() or ["no output"])[-1]
        return c.failed(f"export without graph access crashed: {last[:160]}")
    if "GRAPH_" not in run.stderr:
        return c.failed(f"export without graph access gave no actionable message: {run.stderr.strip()[:160]}")
    return c.passed("help works; without graph access the export stops with a message naming GRAPH_* settings")


def check_page(snips: dict[str, str], s3: list[str] | None, env: dict) -> Check:
    c = Check("page")
    problems: list[str] = []
    rest_body = shell_data_arg(snips.get("REST_EXAMPLE", ""))
    if not rest_body or "text" not in rest_body or "session_id" not in rest_body:
        problems.append("REST example body is not a valid /v1/query body")
    gql_body = shell_data_arg(snips.get("GRAPHQL_EXAMPLE", ""))
    if not gql_body or "mutation" not in gql_body.get("query", ""):
        problems.append("GraphQL example body is not a mutation")
    mcp = as_json(snips.get("MCP_CONFIG", ""))
    server = next(iter((mcp.get("mcpServers") or {}).values()), {})
    if not str(server.get("url", "")).endswith("/mcp/"):
        problems.append("MCP config URL does not end in /mcp/")
    if not (server.get("headers") or {}).get("Authorization"):
        problems.append("MCP config carries no Authorization header, so every tool call is refused")
    if s3 is not None:
        for line in snips.get("CLI_EXAMPLE", "").splitlines():
            parts = line.strip().split()
            if not parts or parts[0] != "s3":
                continue
            args = parts[1:]
            probe = args[:1] + ["--help"] if args else ["--help"]
            usage = subprocess.run(s3 + probe, capture_output=True, text=True, env=env, timeout=30, check=False).stdout
            if args[:1] == ["login"] and len(args) < 2 and "email" in usage:
                problems.append("`s3 login` is printed without the email it requires")
        body = snips.get("CLI_CARD_BODY", "")
        for flag in re.findall(r"(--[a-z][a-z-]+)", body):
            usage = subprocess.run(s3 + ["ask", "--help"], capture_output=True, text=True, env=env, timeout=30, check=False).stdout
            if flag not in usage:
                problems.append(f"the card promises `s3 {flag}`, which `s3 ask` does not accept")
    if problems:
        return c.failed("; ".join(problems))
    return c.passed("printed commands match the code")


# ---------------------------------------------------------------------------
# Setup: account, and the console commands
# ---------------------------------------------------------------------------

def account(api: str, accounts_file: str | None) -> tuple[str, str, str]:
    if accounts_file:
        body = json.loads(Path(accounts_file).read_text())[0]
    else:
        body = {"email": f"smoke-{uuid.uuid4().hex[:12]}@example.com", "pass" + "word": secrets.token_urlsafe(24)}
        status, _, text = http("POST", api + "/auth/signup", body, timeout=30)
        if status != 201:
            raise SystemExit(f"FAIL setup    could not sign up a throwaway account: HTTP {status}")
    status, _, text = http("POST", api + "/auth/login", body, timeout=30)
    tok = as_json(text).get("access_token")
    if status != 200 or not tok:
        raise SystemExit(f"FAIL setup    could not sign in: HTTP {status}")
    return tok, body["email"], body["pass" + "word"]


def build_cli(source: Path, workdir: Path) -> tuple[list[str], list[str], dict]:
    """Build and install the wheel with no dependencies and no network."""
    wheel_dir, prefix = workdir / "wheel", workdir / "prefix"
    # Absolute, always: pip reads a bare relative name such as `checkout` as a
    # package to fetch, not as a directory to build.
    source = source.resolve()
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "-q",
                    "-w", str(wheel_dir), str(source)], check=True, capture_output=True, timeout=120)
    wheel = next(wheel_dir.glob("*.whl"))
    subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--no-index", "-q",
                    "--prefix", str(prefix), str(wheel)], check=True, capture_output=True, timeout=120)
    site = next(prefix.glob("lib/python*/site-packages"))
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",) and not k.startswith("S3_")}
    env["PYTHONPATH"] = str(site)
    return [str(prefix / "bin" / "s3")], [str(prefix / "bin" / "s3-kgx-export")], env


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--api", required=True, help="the API origin, e.g. https://<api-host>")
    ap.add_argument("--page-source", help="InfoScreens.tsx, to test the page's printed commands")
    ap.add_argument("--cli-source", help="a checkout to build the s3 wheel from")
    ap.add_argument("--s3-bin", help="an installed s3 command (default: s3 on PATH)")
    ap.add_argument("--kgx-bin", help="an installed s3-kgx-export command (default: on PATH)")
    ap.add_argument("--accounts-file", help="JSON list of sign-in bodies; the first is used")
    ap.add_argument("--timeout", type=float, default=100.0, help="seconds per live question (default 100)")
    args = ap.parse_args()
    api = args.api.rstrip("/")
    t0 = time.time()

    snips = page_snippets(Path(args.page_source), api) if args.page_source else {}
    rest_body = shell_data_arg(snips.get("REST_EXAMPLE", "")) or {"text": QUESTION, "session_id": "demo-1"}
    rest_body = {**rest_body, "session_id": f"smoke-{uuid.uuid4().hex[:8]}"}
    gql_body = shell_data_arg(snips.get("GRAPHQL_EXAMPLE", "")) or {
        "query": f'mutation {{ ask(input: {{ text: "{QUESTION}", sessionId: "demo-1" }}) '
                 "{ answer citations { source sourceUrl } } }"}
    mcp_url = api + "/mcp/"
    server = next(iter((as_json(snips.get("MCP_CONFIG", "")).get("mcpServers") or {}).values()), {})
    if server.get("url"):
        mcp_url = server["url"]

    checks: list[Check] = [check_health(api)]
    if not checks[0].ok:
        return report(checks, t0)
    token, email, secret = account(api, args.accounts_file)

    workdir = Path(tempfile.mkdtemp(prefix="s3_smoke_"))
    try:
        s3 = kgx = None
        cli_env = {k: v for k, v in os.environ.items() if not k.startswith("S3_")}
        cli_env["S3_CREDENTIALS_PATH"] = str(workdir / "credentials.json")
        setup_error = None
        if args.cli_source:
            try:
                s3, kgx, env = build_cli(Path(args.cli_source), workdir)
                cli_env.update(env)
                cli_env["S3_CREDENTIALS_PATH"] = str(workdir / "credentials.json")
            except subprocess.CalledProcessError as exc:
                err = (exc.stderr or b"").decode(errors="replace").strip().splitlines()
                setup_error = f"could not build or install the wheel: {(err or ['no output'])[-1][:200]}"
            except StopIteration:
                setup_error = "the wheel build produced no wheel or no site-packages"
        else:
            s3_path = args.s3_bin or shutil.which("s3")
            kgx_path = args.kgx_bin or shutil.which("s3-kgx-export")
            s3 = [s3_path] if s3_path else None
            kgx = [kgx_path] if kgx_path else None

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                "api-docs": pool.submit(check_docs, api),
                "rest-sse": pool.submit(check_rest, api, rest_body, args.timeout, token),
                "graphql": pool.submit(check_graphql, api, token, gql_body, args.timeout),
                "mcp": pool.submit(check_mcp, api, mcp_url, token, args.timeout),
            }
            if s3:
                futures["cli"] = pool.submit(check_cli, api, s3, cli_env, email, secret, args.timeout)
            if kgx:
                futures["kgx"] = pool.submit(check_kgx, kgx, cli_env)
            for name in ("api-docs", "rest-sse", "graphql", "mcp", "cli", "kgx"):
                if name in futures:
                    checks.append(futures[name].result())
                else:
                    checks.append(Check(name).failed(setup_error or f"{'s3' if name == 'cli' else 's3-kgx-export'} "
                                                     "not found; pass --cli-source <checkout> or --s3-bin/--kgx-bin"))
        if snips:
            checks.append(check_page(snips, s3, cli_env))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return report(checks, t0)


def report(checks: list[Check], t0: float) -> int:
    for c in checks:
        detail = " ".join(str(c.detail).split())[:300]
        print(f"{'PASS' if c.ok else 'FAIL'} {c.name:<9} {detail}")
    failed = [c for c in checks if not c.ok]
    print(f"{len(checks) - len(failed)} passed, {len(failed)} failed, {time.time() - t0:.0f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
