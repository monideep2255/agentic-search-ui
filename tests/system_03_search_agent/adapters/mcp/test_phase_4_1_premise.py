"""Phase 4.1 premise gate: `tracker/phase_4.1.md`.

The done-when this file pins (the phase's own "Phase premise" section): a
caller holding a valid bearer token for its own `User` account calls the
single advertised MCP tool, `ask_biomedical_question`, and gets back one
JSON result, never a stream, folded from the same core agent loop every
other surface drives. No `think`, `plan`, or `tool_start` event ever
reaches it. A query with no groundable answer gets the honest refusal
string with no fabricated citations, the identical cite-or-refuse rule
every other surface already gets. No response ever carries a cost field,
for any caller, in any role, `operator_mode` hard-pinned false regardless
of `OPERATOR_USER_IDS` allowlist status. A caller with a missing,
malformed, or invalid bearer token never reaches the core loop at all: no
run is created, no budget is spent, and the caller gets a protocol-level
auth failure. `list_tools()` advertises exactly one tool; no internal tool
is ever separately reachable.

Driven through a REAL `mcp` client session (`mcp.client.streamable_http`,
`mcp.client.session.ClientSession`) against the real, mounted Starlette
sub-app inside the real FastAPI app, over `httpx2.ASGITransport`
(`httpx2` is the `mcp` SDK's own vendored httpx fork; see `pip show mcp`),
never a hand-rolled JSON-RPC payload. This is the same in-process pattern
`test_phase_4_0_premise.py` established for the REST/SSE surface
(`httpx.AsyncClient` + `ASGITransport` against the real app), extended for
the MCP transport's own requirements, two of which differ from that file's
convention and are surprising enough to be worth stating up front (full
account in `LEARNINGS.md`'s 2026-08-11 "Mounting the mcp==2.0.0 SDK's
streamable_http_app into FastAPI silently fails three separate ways"
entry):

    - `base_url` cannot be the REST/SSE gate's own `http://test`
      convention. The SDK auto-enables DNS-rebinding `Host`-header
      protection whenever `streamable_http_app()`'s `host` parameter is
      left at its default `127.0.0.1`, and the allowlist it builds
      (`127.0.0.1:*`, `localhost:*`, `[::1]:*`) requires an explicit port
      to match the wildcard suffix. `http://localhost:8000` (an arbitrary
      port) is used below instead.
    - A caller-built `httpx2.AsyncClient` passed as `http_client=` to
      `streamable_http_client` (needed here to inject a per-test bearer
      token via a custom `Authorization` header) bypasses the SDK's own
      `create_mcp_http_client()` default entirely, including its
      `follow_redirects=True`. Every helper below sets
      `follow_redirects=True` explicitly, since mounting the sub-app at
      `/mcp` with its own internal route at `/` (this phase's mount
      shape, `adapters/web_sse/app.py`) means a bare `POST /mcp` 307s to
      `/mcp/` before reaching the handler.

Fake event streams (`_golden_path_stream`, `_refusal_path_stream`, and so
on) monkeypatch `run_streaming` at `system_03_search_agent.core.
run_registry`, the exact seam `test_phase_4_0_premise.py` already
established this repo's tests use, for the same reason stated there: the
real `cypher_query` tool reaches the live Hetzner AGE graph over an SSH
tunnel this environment cannot open, and a controlled fake is also the
more correct test design for exercising the fold loop's own behavior
(what it does with a given event sequence), not any one live NCBI answer.

Not covered by this gate, stated per `.claude/rules/goal-contracts.md`'s
coverage-declaration discipline (mirrors `tracker/phase_4.1.md`'s own "Not
covered by this gate" note): real interop against an external MCP host
(Claude Desktop or another live MCP client); true multi-process behavior
and load-scale concurrency across many simultaneous MCP clients (build
phase 6.0's territory); and OAuth 2.0/OIDC alignment, since this phase
deliberately keeps the SDK's own OAuth provider machinery unwired in favor
of the existing bearer-JWT mechanism.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Any

import httpx2
import pytest
import sqlalchemy as sa
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from mcp_types import CallToolResult

from system_03_search_agent.contracts.events import (
    CitationPayload,
    CostPayload,
    DonePayload,
    Event,
    GuardPayload,
    PlanPayload,
    ThinkPayload,
    ToolResultPayload,
    ToolStartPayload,
    TokenPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)

_TEST_AUTH_SECRET = "test-only-auth-secret-for-phase-4-1-premise-tests-do-not-reuse"
_BASE_URL = "http://localhost:8000"
_INTERNAL_TOOL_NAMES = {
    "cypher_query",
    "ncbi_efetch",
    "ncbi_dbsnp",
    "pubtator_annotate",
    "litvar2_lookup",
    "pathogen_detection",
    "clinicaltrials_search",
}


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


# ---------------------------------------------------------------------------
# Fake event-stream fixtures: monkeypatch `run_streaming` so the fold loop
# is exercised against a controlled, deterministic sequence rather than a
# live graph/API call this environment cannot reach.
# ---------------------------------------------------------------------------


def _event(event_type: str, trace_id: str, seq: int, payload: object) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),  # type: ignore[attr-defined]
    )


async def _golden_path_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A full, successful run: every one of the eleven event types fires,
    including `think`/`plan`/`tool_start`/`tool_result`/`cost`, the ones
    Section 13.2 requires the MCP adapter to fold OUT entirely. Also pins
    the "Event folding" arm's second half: a run that DOES emit them must
    still complete without the fold loop hanging or crashing.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "think",
        trace_id,
        1,
        ThinkPayload(
            narrative="classified as a single-hop lookup",
            query_class="single_hop",
            resolved_entities=[],
            clarifying_question=None,
        ),
    )
    yield _event(
        "plan",
        trace_id,
        2,
        PlanPayload(narrative="dispatch cypher_query", tool_calls=[]),
    )
    yield _event(
        "tool_start",
        trace_id,
        3,
        ToolStartPayload(call_id="call-1", tool="cypher_query", layer="layer_1_graph", status="ok"),
    )
    yield _event(
        "tool_result",
        trace_id,
        4,
        ToolResultPayload(
            call_id="call-1",
            tool="cypher_query",
            layer="layer_1_graph",
            status="ok",
            summary="found 1 row",
            result_count=1,
            truncated=False,
        ),
    )
    yield _event(
        "token",
        trace_id,
        5,
        TokenPayload(text="BRCA1 is a protein-coding gene [1]. ", marker_ids=["c1"]),
    )
    yield _event(
        "citation",
        trace_id,
        6,
        CitationPayload(
            citation_id="c1",
            display_index=1,
            source="ncbi_gene",
            source_id="672",
            source_url="https://www.ncbi.nlm.nih.gov/gene/672",
            layer="layer_1_graph",
            field="symbol",
            claim_text="BRCA1 is a protein-coding gene.",
            evidence_kind="direct",
            assertion_confidence="high",
            population_ancestry_context=None,
            license="public-domain",
        ),
    )
    yield _event(
        "trust_signal",
        trace_id,
        7,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id="c1",
            scope="claim",
        ),
    )
    yield _event(
        "trust_signal",
        trace_id,
        8,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id=None,
            scope="answer",
        ),
    )
    yield _event(
        "cost",
        trace_id,
        9,
        CostPayload(query_cost_usd=0.0123, query_cap_usd=1.0, cap_fraction=0.0123, model_tier="synth"),
    )
    yield _event(
        "done",
        trace_id,
        10,
        DonePayload(total_cost_usd=0.0123, total_tool_calls=1, elapsed_ms=120, trust_outcome="answer"),
    )


async def _refusal_path_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A run that reaches Write but has nothing groundable to cite: the
    same cite-or-refuse shape `core/graph.py`'s `write_node` itself emits
    on its refusal branch (a `token` carrying the refusal text, an
    answer-scope `trust_signal` with `outcome="refuse"`), never a
    different or weaker refusal wording for this surface.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token",
        trace_id,
        1,
        TokenPayload(text="I could not find information on this in the available sources. ", marker_ids=[]),
    )
    yield _event(
        "trust_signal",
        trace_id,
        2,
        TrustSignalPayload(
            outcome="refuse",
            risk_tier="low",
            grounded=False,
            triangulated=None,
            citation_id=None,
            scope="answer",
            message="No groundable citation was found for this query.",
            fallback_link="https://www.ncbi.nlm.nih.gov/gene/",
        ),
    )
    yield _event(
        "cost",
        trace_id,
        3,
        CostPayload(query_cost_usd=0.0050, query_cap_usd=1.0, cap_fraction=0.005, model_tier="synth"),
    )
    yield _event(
        "done",
        trace_id,
        4,
        DonePayload(total_cost_usd=0.0050, total_tool_calls=1, elapsed_ms=90, trust_outcome="refuse"),
    )


# ---------------------------------------------------------------------------
# MCP client helpers: a real client session against the real mounted app.
# ---------------------------------------------------------------------------


def _http_client(app: object, headers: Mapping[str, str] | None) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app),
        base_url=_BASE_URL,
        headers=dict(headers) if headers else None,
        follow_redirects=True,
    )


async def _list_tools(app: object, headers: Mapping[str, str] | None = None) -> list[Any]:
    async with app.router.lifespan_context(app):  # type: ignore[attr-defined]
        async with _http_client(app, headers) as http_client:
            async with streamable_http_client(f"{_BASE_URL}/mcp", http_client=http_client) as (
                read,
                write,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return list(result.tools)


async def _call_tool(
    app: object, headers: Mapping[str, str] | None, arguments: dict[str, object]
) -> CallToolResult:
    async with app.router.lifespan_context(app):  # type: ignore[attr-defined]
        async with _http_client(app, headers) as http_client:
            async with streamable_http_client(f"{_BASE_URL}/mcp", http_client=http_client) as (
                read,
                write,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool("ask_biomedical_question", arguments)


def _find_all(schema_fragment: object, key: str) -> list[object]:
    """Recursively collect every value found under `key` anywhere in a
    JSON-schema-shaped dict/list structure, since Pydantic's exact
    `anyOf`/`$ref` shape for an optional or nested field is an
    implementation detail this gate should not overfit to.
    """
    found: list[object] = []
    if isinstance(schema_fragment, dict):
        for k, v in schema_fragment.items():
            if k == key:
                found.append(v)
            found.extend(_find_all(v, key))
    elif isinstance(schema_fragment, list):
        for item in schema_fragment:
            found.extend(_find_all(item, key))
    return found


def _resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    assert ref.startswith("#/$defs/"), ref
    return schema["$defs"][ref.removeprefix("#/$defs/")]


# ---------------------------------------------------------------------------
# DB-independent arms: tool surface and schema fidelity need no HTTP call,
# no auth, and no live database, so they run unconditionally (mirrors
# `test_phase_4_0_premise.py`'s split between registry-only tests above its
# DB-reachability skip and HTTP-driven tests below it).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _require_mcp_server_module() -> None:
    """Every test in this file depends on `adapters/mcp/server.py`
    existing, whether it imports the module directly (`TestToolSurface`,
    `TestSchemaFidelity`) or drives it indirectly through the mounted app
    (every HTTP-driven class below). Importing it explicitly here means
    every test in this file fails uniformly with `ModuleNotFoundError`
    before that module exists, never a downstream symptom (an HTTP 404
    through an app that has nothing mounted at `/mcp` yet) that is
    accurate but not the clean, uniform signal this repo's failing-first
    discipline requires (LEARNINGS.md row 43: "every failure a
    ModuleNotFoundError, never a network fault or a fixture bug").
    """
    import system_03_search_agent.adapters.mcp.server  # noqa: F401


class TestToolSurface:
    @pytest.mark.asyncio
    async def test_exactly_one_tool_is_advertised(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        tools = await server.list_tools()
        assert [tool.name for tool in tools] == ["ask_biomedical_question"]

    @pytest.mark.asyncio
    async def test_no_internal_tool_name_is_separately_advertised(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        tools = await server.list_tools()
        advertised = {tool.name for tool in tools}
        assert advertised.isdisjoint(_INTERNAL_TOOL_NAMES)

    @pytest.mark.asyncio
    async def test_no_internal_tool_is_separately_callable(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        for internal_name in _INTERNAL_TOOL_NAMES:
            with pytest.raises(Exception):  # noqa: B017, PT011 - any rejection is correct here
                await server.call_tool(internal_name, {})


class TestSchemaFidelity:
    @pytest.mark.asyncio
    async def test_input_schema_matches_section_13_2(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        tools = await server.list_tools()
        input_schema = tools[0].input_schema

        assert input_schema["required"] == ["query"]
        assert input_schema["properties"]["query"]["maxLength"] == 2000
        assert set(input_schema["properties"]["audience_depth"]["enum"]) == {
            "clinical_brief",
            "researcher",
            "deep_technical",
        }
        assert 64 in _find_all(input_schema["properties"]["session_id"], "maxLength")

    @pytest.mark.asyncio
    async def test_output_schema_matches_section_13_2(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        tools = await server.list_tools()
        output_schema = tools[0].output_schema

        assert set(output_schema["required"]) == {"answer", "citations", "trust_signal", "run_id"}
        assert output_schema["properties"]["answer"]["maxLength"] == 8000
        assert output_schema["properties"]["run_id"]["maxLength"] == 64
        citations_prop = output_schema["properties"]["citations"]
        assert citations_prop["maxItems"] == 50
        assert citations_prop["type"] == "array"

        trust_signal_prop = output_schema["properties"]["trust_signal"]
        if "$ref" in trust_signal_prop:
            trust_signal_schema = _resolve_ref(output_schema, trust_signal_prop["$ref"])
        else:
            trust_signal_schema = trust_signal_prop
        assert trust_signal_schema["type"] == "object"


# ---------------------------------------------------------------------------
# HTTP-driven arms: golden path, refusal path, event folding, never-cost,
# and every auth arm. Needs `search_agent_users` PostgreSQL reachable for
# real signup/login (the same bearer-JWT mechanism every other surface
# uses; T-4.1-03 reuses `get_current_user`'s own decode-then-lookup logic,
# never a second auth system), and skips cleanly, not failing, when it is
# not.
# ---------------------------------------------------------------------------

if not _can_connect():
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; set "
        "USER_DB_URL and ensure the server is running to run the "
        "HTTP-driven half of the phase 4.1 premise gate (golden path, "
        "refusal path, event folding, never-cost, and every auth arm)",
        allow_module_level=True,
    )

from system_03_search_agent.adapters.web_sse.app import app  # noqa: E402
from system_03_search_agent.core import run_registry as run_registry_module  # noqa: E402


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


async def _signup_and_login(client: httpx2.AsyncClient) -> tuple[str, dict[str, str]]:
    email, password = _unique_email(), "Str0ngPassw0rd!"
    signup = await client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _real_user_headers() -> tuple[str, dict[str, str]]:
    """Sign up and log in a fresh throwaway `User` against the real app's
    own `/auth` router, over a plain (non-MCP) ASGI client, since `/auth`
    is not part of the MCP surface. Returns the new user's id and a
    ready-to-use `Authorization` header.
    """
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url=_BASE_URL
    ) as client:
        return await _signup_and_login(client)


class TestGoldenPath:
    @pytest.mark.asyncio
    async def test_a_real_question_returns_a_grounded_cited_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(app, headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        assert content["answer"].strip() != ""
        assert len(content["citations"]) >= 1
        citation = content["citations"][0]
        for field in (
            "citation_id",
            "source",
            "source_id",
            "source_url",
            "layer",
            "field",
            "claim_text",
            "evidence_kind",
            "assertion_confidence",
            "license",
        ):
            assert field in citation
        assert content["trust_signal"] is not None
        assert content["run_id"]


class TestRefusalPath:
    @pytest.mark.asyncio
    async def test_a_zero_groundable_result_query_refuses_honestly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _refusal_path_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(app, headers, {"query": "an unanswerable question"})

        assert result.is_error is False
        content = result.structured_content
        assert content["citations"] == []
        assert content["trust_signal"]["outcome"] == "refuse"
        assert "could not find" in content["answer"].lower()


class TestEventFolding:
    @pytest.mark.asyncio
    async def test_folded_response_has_no_field_for_excluded_event_types(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Section 13.2's fold rule is a structural guarantee: the response
        object has no field named after any of the folded-out or folded-in
        event types, and a run emitting all eleven event types (the golden
        path fixture) still completes cleanly rather than hanging.
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(app, headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        assert set(content.keys()) == {"answer", "citations", "trust_signal", "run_id"}
        for excluded_key in ("think", "plan", "tool_start", "token", "tool_result", "guard", "cost"):
            assert excluded_key not in _find_all(content, excluded_key), (
                f"{excluded_key!r} leaked into the folded response"
            )


class TestNeverCost:
    @pytest.mark.asyncio
    async def test_an_operator_allowlisted_caller_still_gets_no_cost_field(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`operator_mode` is hard-pinned false for this surface: even a
        caller on the `OPERATOR_USER_IDS` allowlist gets a response with
        no cost-shaped field anywhere, proving the pin, not merely a
        default that happens to read false for a non-allowlisted caller.
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        user_id, headers = await _real_user_headers()
        monkeypatch.setenv("OPERATOR_USER_IDS", user_id)

        result = await _call_tool(app, headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        assert set(content.keys()) == {"answer", "citations", "trust_signal", "run_id"}
        for cost_key in ("cost", "total_cost_usd", "query_cost_usd", "query_cap_usd", "cap_fraction"):
            assert cost_key not in _find_all(content, cost_key)


class TestAuth:
    @pytest.mark.asyncio
    async def test_missing_token_is_rejected_before_any_run_is_created(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_calls: list[object] = []
        original_create_run = run_registry_module.default_registry.create_run

        def _spy_create_run(*args: object, **kwargs: object) -> str:
            create_calls.append((args, kwargs))
            return original_create_run(*args, **kwargs)

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy_create_run)

        with pytest.raises(MCPError):
            await _call_tool(app, None, {"query": "What gene is BRCA1?"})

        assert create_calls == []

    @pytest.mark.asyncio
    async def test_malformed_token_is_rejected_before_any_run_is_created(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_calls: list[object] = []
        original_create_run = run_registry_module.default_registry.create_run

        def _spy_create_run(*args: object, **kwargs: object) -> str:
            create_calls.append((args, kwargs))
            return original_create_run(*args, **kwargs)

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy_create_run)

        with pytest.raises(MCPError):
            await _call_tool(
                app, {"Authorization": "not-a-bearer-token"}, {"query": "What gene is BRCA1?"}
            )

        assert create_calls == []

    @pytest.mark.asyncio
    async def test_invalid_token_is_rejected_before_any_run_is_created(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_calls: list[object] = []
        original_create_run = run_registry_module.default_registry.create_run

        def _spy_create_run(*args: object, **kwargs: object) -> str:
            create_calls.append((args, kwargs))
            return original_create_run(*args, **kwargs)

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy_create_run)

        with pytest.raises(MCPError):
            await _call_tool(
                app,
                {"Authorization": "Bearer this.is.not-a-real-jwt"},
                {"query": "What gene is BRCA1?"},
            )

        assert create_calls == []

    @pytest.mark.asyncio
    async def test_a_valid_token_succeeds_and_the_run_is_owned_by_that_user(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        user_id, headers = await _real_user_headers()

        result = await _call_tool(app, headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        run_id = result.structured_content["run_id"]
        entry = run_registry_module.default_registry.get_run(run_id)
        assert entry.user_id == user_id
