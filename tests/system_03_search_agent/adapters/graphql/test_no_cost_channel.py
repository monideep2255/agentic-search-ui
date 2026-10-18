"""Ordinary unit tests for the GraphQL surface's cost and auth boundary.

Moved out of the deleted `test_phase_4_3_premise.py` (build phase 4.14
bossman redesign, 2026-09-24, `docs/build/Bossman_redesign_deletion_inventory.md`)
because the property is a cost/security control that
`.claude/rules/production-standards.md` requires a test for, even once the
premise-gate file it lived in is gone. `test_security.py` already covers
this surface's document-shape bounds (depth, aliases, size, introspection);
this file covers the two properties that were not duplicated there: no cost
figure can ever reach this surface, and only a registered account (never a
missing or guest credential) can start a run.

Driven over the real FastAPI app via `httpx.ASGITransport`, the same
in-process pattern the deleted premise gate used, because these properties
are about what actually crosses the wire and the schema actually offers,
not about a resolver called in isolation.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from system_03_search_agent.contracts.events import (
    CitationPayload,
    CostPayload,
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

_TEST_AUTH_SECRET = "graphql-no-cost-channel-test-secret"
_BASE_URL = "http://test"
_GRAPHQL_PATH = "/graphql"


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


def _event(event_type: str, trace_id: str, seq: int, payload: Any) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


def _citation(index: int) -> CitationPayload:
    return CitationPayload(
        citation_id=f"c{index}",
        display_index=index,
        source="NCBI Gene",
        source_id=f"{670 + index}",
        source_url=f"https://www.ncbi.nlm.nih.gov/gene/{670 + index}",
        layer="layer_1_graph",
        field="gene_symbol",
        claim_text=f"claim number {index}",
        evidence_kind="curated_assertion",
        assertion_confidence="high",
        population_ancestry_context=None,
        license="public_domain",
        snapshot_date="2026-07-01",
        entity_name="BRCA1",
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
        "token",
        trace_id,
        5,
        TokenPayload(text="BRCA1 is a protein-coding gene [1]. ", marker_ids=["c1"]),
    )
    yield _event("citation", trace_id, 6, _citation(1))
    yield _event(
        "cost",
        trace_id,
        7,
        CostPayload(
            query_cost_usd=0.0123,
            query_cap_usd=0.5,
            cap_fraction=0.0246,
            model_tier="synth",
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
            citation_id="c1",
            scope="answer",
            message=None,
            fallback_link=None,
        ),
    )


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


async def _signup_and_login(client: httpx.AsyncClient) -> tuple[str, dict[str, str]]:
    email, password = _unique_email(), "Str0ngPassw0rd!"
    signup = await client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201, signup.text
    user_id = signup.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _guest_headers(client: httpx.AsyncClient) -> dict[str, str]:
    minted = await client.post("/auth/guest")
    assert minted.status_code == 201, minted.text
    return {"Authorization": f"Bearer {minted.json()['guest_token']}"}


def _client() -> httpx.AsyncClient:
    from system_03_search_agent.adapters.web_sse.app import app

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=_BASE_URL)


async def _post_graphql(
    client: httpx.AsyncClient,
    document: str,
    *,
    headers: dict[str, str] | None = None,
    variables: dict[str, Any] | None = None,
) -> httpx.Response:
    body: dict[str, Any] = {"query": document}
    if variables is not None:
        body["variables"] = variables
    return await client.post(_GRAPHQL_PATH, json=body, headers=headers or {})


_ASK_DOCUMENT = """
mutation Ask($input: AskInput!) {
  ask(input: $input) {
    runId
    answer
    trustSignal { outcome grounded }
    citations { citationId }
  }
}
"""


async def _ask(client: httpx.AsyncClient, headers: dict[str, str]) -> httpx.Response:
    return await _post_graphql(
        client,
        _ASK_DOCUMENT,
        headers=headers,
        variables={"input": {"text": "Which diseases are associated with BRCA1?", "sessionId": "s-cost-test"}},
    )


class TestNeverCost:
    @pytest.mark.asyncio
    async def test_no_cost_figure_appears_anywhere_in_the_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _signup_and_login(client)
            response = await _ask(client, headers)

        serialized = response.text
        for forbidden in ("0.0123", "0.0246", "query_cost_usd", "queryCostUsd", "totalCostUsd"):
            assert forbidden not in serialized

    def test_the_schema_has_no_field_a_cost_figure_could_be_selected_into(self) -> None:
        from system_03_search_agent.adapters.graphql import schema as schema_module

        printed = str(schema_module.schema).lower()
        for forbidden in ("cost", "usd", "spend"):
            assert forbidden not in printed

    @pytest.mark.asyncio
    async def test_operator_mode_is_pinned_false_for_every_caller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core import run_registry as run_registry_module

        seen: list[RequestContext] = []
        real_create_run = run_registry_module.default_registry.create_run

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            seen.append(context)
            return real_create_run(query, context, **kwargs)

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        async with _client() as client:
            user_id, headers = await _signup_and_login(client)
            monkeypatch.setenv("OPERATOR_USER_IDS", user_id)
            await _ask(client, headers)

        assert seen, "create_run was never reached"
        assert all(context.operator_mode is False for context in seen)


class TestRegisteredAccountsOnly:
    @pytest.mark.asyncio
    async def test_a_missing_token_never_reaches_the_core(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from system_03_search_agent.core import run_registry as run_registry_module

        created: list[str] = []

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            created.append(query.trace_id)
            raise AssertionError("create_run must not be reached without a credential")

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        async with _client() as client:
            response = await _ask(client, {})

        assert response.status_code in (400, 401, 403)
        assert created == []

    @pytest.mark.asyncio
    async def test_a_valid_guest_token_is_refused_with_an_actionable_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core import run_registry as run_registry_module

        created: list[str] = []

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            created.append(query.trace_id)
            raise AssertionError("a guest must not reach create_run on this surface")

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        async with _client() as client:
            guest = await _guest_headers(client)
            response = await _ask(client, guest)

        assert response.status_code in (401, 403)
        assert created == []
        body = response.text.lower()
        assert "guest" in body
        assert "account" in body or "sign in" in body or "log in" in body
