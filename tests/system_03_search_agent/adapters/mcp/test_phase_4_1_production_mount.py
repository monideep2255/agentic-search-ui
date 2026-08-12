"""Phase 4.1 production-mount test: `tracker/phase_4.1.md`, F-4.1-J-02.

The judge's finding: `adapters/web_sse/app.py`'s real, shipped `/mcp`
mount (`_mcp_asgi_app`, `_lifespan`, `app.mount("/mcp", _mcp_asgi_app)`) was
exercised by zero tests. `test_phase_4_1_premise.py`'s
`_build_test_mcp_app()` hand-copies the same mount recipe into a fresh
`FastAPI` wrapper on every call instead of importing the real `app` object,
because `MCPServer.streamable_http_app()` builds a brand new
`StreamableHTTPSessionManager` on every call and that manager's `run()`
(entered via a `lifespan=` context manager) may only execute once per
instance for its whole lifetime. That is the right call for a file making
many independent, isolated per-test calls, but it means the shipped mount
itself, `adapters/web_sse/app.py`'s own `app` object with its own
module-level `_mcp_asgi_app` singleton, was never proven to actually work.
This file's own LEARNINGS.md entry ("Mounting the mcp==2.0.0 SDK's
streamable_http_app into FastAPI silently fails three separate ways")
records that this exact recipe already failed three separate silent ways
before being fixed, which is precisely why an unverified duplicate of a
verified recipe is a real gap, not a nitpick.

This file closes that gap by driving one real MCP tool call through the
REAL, module-level `app` singleton from `adapters/web_sse/app.py`, not a
rebuilt copy, entering that singleton's own `_lifespan` (and therefore its
own `_mcp_asgi_app`'s `StreamableHTTPSessionManager.run()`) directly.

One-shot constraint, stated plainly: `_mcp_asgi_app` is a module-level
singleton bound once at import time and shared by every test file that
imports `adapters/web_sse/app.py` (`test_health.py`,
`test_streaming_endpoints.py`, `test_phase_4_0_premise.py`,
`test_phase_4_1_premise.py`, `auth/test_router.py`). Its session
manager's `run()` may only be
entered once for the lifetime of the test process. This file is the one
and only place in the repo that enters it: `test_health.py` uses
`fastapi.testclient.TestClient(app)` WITHOUT the `with` statement (so its
`__enter__`/`__exit__` lifespan handling never fires), and every other
file drives `app` over `httpx.AsyncClient`/`httpx2.AsyncClient` +
`ASGITransport`, which does not send ASGI `lifespan` scope events at all.
Confirmed by grep before this file was written: no other test in the repo
calls `app.router.lifespan_context(app)` or uses `TestClient(app)` as a
context manager. If that ever changes, this test (and whichever one
collides with it) will fail loudly with `RuntimeError: Task group is not
initialized` or a "session manager .run() can only be called once" error
from the SDK, which is itself useful signal that the constraint was
violated, not a flaky test.

Exactly one test function in this file enters the singleton's lifespan and
makes exactly one MCP call, for that reason.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx2
import pytest
import sqlalchemy as sa
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from system_03_search_agent.contracts.events import (
    CitationPayload,
    DonePayload,
    Event,
    GuardPayload,
    TokenPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)

_TEST_AUTH_SECRET = "test-only-auth-secret-for-phase-4-1-production-mount-test-do-not-reuse"
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


if not _can_connect():
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; set "
        "USER_DB_URL and ensure the server is running to run the phase "
        "4.1 production-mount test (the real /mcp mount, end to end)",
        allow_module_level=True,
    )

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.core import run_registry as run_registry_module


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


def _event(event_type: str, trace_id: str, seq: int, payload: object) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),  # type: ignore[attr-defined]
    )


async def _minimal_golden_path_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A minimal, deterministic successful run, the same shape
    `test_phase_4_1_premise.py`'s `_golden_path_stream` uses for its own
    golden-path arm, kept intentionally small here since this file's job is
    proving the real mount answers a real call, not re-exercising the fold
    loop's own logic (already covered by the isolated per-call gate).
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token", trace_id, 1, TokenPayload(text="BRCA1 is a protein-coding gene [1]. ", marker_ids=["c1"])
    )
    yield _event(
        "citation",
        trace_id,
        2,
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
        3,
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
        "done", trace_id, 4, DonePayload(total_cost_usd=0.01, total_tool_calls=1, elapsed_ms=50, trust_outcome="answer")
    )


class TestProductionMount:
    @pytest.mark.asyncio
    async def test_the_real_shipped_app_answers_a_real_mcp_call_end_to_end(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Drives one real `mcp` client session against the REAL,
        module-level `app` object from `adapters/web_sse/app.py`, entering
        its actual production `_lifespan` (not a hand-copied rebuild), to
        prove the shipped mount recipe itself works end to end, not just an
        isolated re-implementation of it.
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _minimal_golden_path_stream)

        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url=_BASE_URL, follow_redirects=True
            ) as auth_client:
                email, password = f"{uuid.uuid4()}@example.com", "Str0ngPassw0rd!"
                signup = await auth_client.post(
                    "/auth/signup", json={"email": email, "password": password}
                )
                assert signup.status_code == 201
                login = await auth_client.post(
                    "/auth/login", json={"email": email, "password": password}
                )
                assert login.status_code == 200
                headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            async with (
                httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=app),
                    base_url=_BASE_URL,
                    headers=headers,
                    follow_redirects=True,
                ) as mcp_http_client,
                streamable_http_client(f"{_BASE_URL}/mcp", http_client=mcp_http_client) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                result = await session.call_tool(
                    "ask_biomedical_question", {"query": "What gene is BRCA1?"}
                )

        assert result.is_error is False
        content = result.structured_content
        assert content["answer"].strip() != ""
        assert len(content["citations"]) >= 1
        assert content["trust_signal"] is not None
        assert content["run_id"]
