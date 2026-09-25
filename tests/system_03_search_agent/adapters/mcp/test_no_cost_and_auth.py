"""Ordinary unit tests for the MCP surface's cost and auth boundary.

Moved out of the deleted `test_phase_4_1_premise.py` (build phase 4.14
bossman redesign, 2026-09-24,
`docs/build/Bossman_redesign_deletion_inventory.md`). This keeps two
properties `.claude/rules/production-standards.md` requires a test for
independent of any premise gate: no response ever carries a cost field,
for any caller including one on the `OPERATOR_USER_IDS` allowlist, and a
caller with a missing, malformed, or invalid bearer token never reaches
the core loop (no run created, no budget spent).

Driven through a real `mcp` client session against the real, mounted
Starlette sub-app, the same in-process pattern the deleted premise gate
used, because the auth check runs at the transport boundary and cannot be
proven by calling a resolver directly.

Needs `search_agent_users` PostgreSQL reachable for real signup/login, and
skips cleanly, not failing, when it is not (matching every other DB-backed
test in this repository).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime

import httpx2
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
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
    TokenPayload,
    ToolResultPayload,
    ToolStartPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)

_TEST_AUTH_SECRET = "test-only-auth-secret-for-mcp-no-cost-and-auth-tests"
_BASE_URL = "http://localhost:8000"


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


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
    yield _event("plan", trace_id, 2, PlanPayload(narrative="dispatch cypher_query", tool_calls=[]))
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
        "token", trace_id, 5, TokenPayload(text="BRCA1 is a protein-coding gene [1]. ", marker_ids=["c1"])
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
        "done", trace_id, 10, DonePayload(total_cost_usd=0.0123, total_tool_calls=1, elapsed_ms=120, trust_outcome="answer")
    )


if not _can_connect():
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; set "
        "USER_DB_URL and ensure the server is running to run the MCP "
        "no-cost and auth tests",
        allow_module_level=True,
    )

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.core import run_registry as run_registry_module


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
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=_BASE_URL) as client:
        return await _signup_and_login(client)


def _build_test_mcp_app() -> FastAPI:
    from system_03_search_agent.adapters.mcp.server import server as mcp_server

    sub_app = mcp_server.streamable_http_app(stateless_http=True, streamable_http_path="/")

    @asynccontextmanager
    async def _test_lifespan(test_app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(sub_app.router.lifespan_context(sub_app))
            yield

    test_app = FastAPI(lifespan=_test_lifespan)
    test_app.mount("/mcp", sub_app)
    return test_app


def _http_client(mcp_app: FastAPI, headers: Mapping[str, str] | None) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=mcp_app),
        base_url=_BASE_URL,
        headers=dict(headers) if headers else None,
        follow_redirects=True,
    )


async def _call_tool(headers: Mapping[str, str] | None, arguments: dict[str, object]) -> CallToolResult:
    mcp_app = _build_test_mcp_app()
    async with (
        mcp_app.router.lifespan_context(mcp_app),
        _http_client(mcp_app, headers) as http_client,
        streamable_http_client(f"{_BASE_URL}/mcp", http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        return await session.call_tool("ask_biomedical_question", arguments)


def _first_mcp_error(eg: BaseExceptionGroup) -> MCPError:
    for exc in eg.exceptions:
        if isinstance(exc, MCPError):
            return exc
        if isinstance(exc, BaseExceptionGroup):
            return _first_mcp_error(exc)
    raise AssertionError(f"no MCPError found inside {eg!r}")


async def _call_tool_expecting_mcp_error(
    headers: Mapping[str, str] | None, arguments: dict[str, object]
) -> MCPError:
    try:
        await _call_tool(headers, arguments)
    except MCPError as exc:
        return exc
    except BaseExceptionGroup as eg:
        return _first_mcp_error(eg)
    raise AssertionError("expected an MCPError, none was raised")


def _find_all(schema_fragment: object, key: str) -> list[object]:
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


_ALLOWED_RESPONSE_KEYS = {
    "answer",
    "citations",
    "trust_signal",
    "run_id",
    "persona_name",
    "assertion_confidence",
    "citation_id",
    "claim_text",
    "display_index",
    "evidence_kind",
    "field",
    "layer",
    "license",
    "population_ancestry_context",
    "source",
    "source_id",
    "source_url",
    "entity_name",
    "snapshot_date",
    "fallback_link",
    "grounded",
    "message",
    "outcome",
    "risk_tier",
    "scope",
    "triangulated",
}


def _all_response_keys(node: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            keys.add(k)
            keys |= _all_response_keys(v)
    elif isinstance(node, list):
        for item in node:
            keys |= _all_response_keys(item)
    return keys


class TestNeverCost:
    @pytest.mark.asyncio
    async def test_an_operator_allowlisted_caller_still_gets_no_cost_field(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        user_id, headers = await _real_user_headers()
        monkeypatch.setenv("OPERATOR_USER_IDS", user_id)

        result = await _call_tool(headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        for cost_key in ("cost", "total_cost_usd", "query_cost_usd", "query_cap_usd", "cap_fraction"):
            assert _find_all(content, cost_key) == []
        assert _all_response_keys(content) <= _ALLOWED_RESPONSE_KEYS


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

        error = await _call_tool_expecting_mcp_error(None, {"query": "What gene is BRCA1?"})
        assert error.message
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

        error = await _call_tool_expecting_mcp_error(
            {"Authorization": "Bearer this.is.not-a-real-jwt"},
            {"query": "What gene is BRCA1?"},
        )
        assert error.message
        assert create_calls == []

    @pytest.mark.asyncio
    async def test_a_valid_token_succeeds_and_the_run_is_owned_by_that_user(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        run_id = result.structured_content["run_id"]
        entry = run_registry_module.default_registry.get_run(run_id)
        assert entry.user_id == user_id
