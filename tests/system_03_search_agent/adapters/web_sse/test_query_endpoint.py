"""Tests for the POST /query endpoint (Section 2.1 run() wired to the API).

T-2.0-08 (closes F-1.1-17): `POST /query` now requires a valid Bearer
access token via `get_current_user`, and the `user_id` on the `Query`
passed to `run()` is always the server-derived token subject, never a
client-supplied value.

Hits the real local PostgreSQL `search_agent_users` database through the
actual FastAPI app, the same pattern `tests/system_03_search_agent/auth/
test_router.py` already uses: `get_current_user` resolves a real `User`
row via the session dependency, which cannot be verified against a mock.
The whole module skips cleanly (does not fail) when USER_DB_URL is
unreachable.

Every test uses a freshly generated email (uuid4-based) so reruns never
collide with rows a prior run left behind, the same convention
test_router.py already uses for this database.

T-2.0-07: `run()` is now backed by the real five-node LangGraph loop
instead of the phase 1.0 no-model-call scaffold, so every test in this
file that actually invokes `POST /query` now goes through a real (mocked)
`Harness.call_tier` for guardrail/think/plan/write. `_mock_litellm` (an
autouse fixture below) monkeypatches `litellm.acompletion`/
`get_model_info` on `harness_module` the same way `test_run.py` and
`test_graph.py` do, so this file's pre-existing tests, none of which
anticipated a real model call, keep passing unchanged. The daily-cap DB
checks are NOT mocked here (unlike test_run.py/test_graph.py): every
request in this file authenticates as a real, freshly-signed-up `User`
row, so `check_user_daily_query_cap`/`check_system_daily_cost_cap`
running for real against the already-required `search_agent_users`
database is exactly the integration-test value this file exists for.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)


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
        "search_agent_users PostgreSQL database is not reachable; "
        "set USER_DB_URL and ensure the server is running to run this suite",
        allow_module_level=True,
    )

import system_03_search_agent.adapters.web_sse.app as app_module
from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.contracts.events import Event
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core.run import run as real_run
from system_03_search_agent.harness import harness as harness_module

_TEST_AUTH_SECRET = "test-only-auth-secret-for-query-endpoint-tests-do-not-reuse"


def _fake_response(content: str = "ok", prompt_tokens: int = 10, completion_tokens: int = 5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@pytest.fixture(autouse=True)
def _harness_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-2.0-07: run() now drives real Harness.call_tier invocations
    through the five-node graph; pin every tier's model and cap so this
    file's pre-existing tests, none of which anticipated a real model
    call, keep passing unchanged."""
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    # T-3.0-06: dispatches per tier. See `tests/system_03_search_agent/
    # model_stub.py`.
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


@pytest.fixture(autouse=True)
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-3.1-11: `_valid_body`'s default query text names BRCA1 by symbol,
    and `core.graph.resolve_symbol_to_curie` is now a live NCBI call. This
    file goes through `real_run`, the genuine graph loop, so without a
    stand-in every test that keeps the default text would reach out to a
    real external API from what is otherwise an HTTP/DB integration test.
    Same fix `test_graph.py` and `test_run.py` apply, for the same reason.
    """
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157"}

    async def _fake_resolve_symbol_to_curie(symbol: str, **kwargs: object) -> str | None:
        return known.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve_symbol_to_curie)


@pytest.fixture(autouse=True)
def _stub_ncbi_efetch_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """T-3.4-05/T-3.1-28: `plan_node` now also dispatches a second, Layer 2
    `ncbi_efetch` call whenever a resolved target entity is Gene-shaped,
    and `_valid_body`'s default query text names BRCA1 (a Gene) by
    symbol. Same rationale and fix as `_stub_symbol_resolution` above:
    without a stand-in, every test that keeps the default text would
    reach out to a real external API from what is otherwise an HTTP/DB
    integration test. Stubbed to a genuine, never-fabricated "empty"
    result, which `build_synth_findings`/citations/trust all skip (only
    an "ok" finding contributes), so no pre-existing assertion here is
    affected.
    """
    from system_03_search_agent.core import graph as graph_module
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput

    async def _fake_ncbi_efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty",
            action="dataset_report",
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _fake_ncbi_efetch)


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


def _signup_and_login(client: TestClient) -> tuple[str, dict[str, str]]:
    """Create a fresh user, log in, and return (user_id, tokens)."""
    email = _unique_email()
    password = "Str0ngPassw0rd!"
    signup = client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return user_id, login.json()


def _auth_headers(client: TestClient) -> tuple[str, dict[str, str]]:
    """Create a fresh authenticated user and return (user_id, headers)."""
    user_id, tokens = _signup_and_login(client)
    return user_id, {"Authorization": f"Bearer {tokens['access_token']}"}


def _spy_on_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Patch app_module.run with a spy that records the Query it receives.

    Delegates to the real run() so the response is still a valid typed
    event stream; only the Query actually passed to run() is captured.
    """
    captured: dict[str, object] = {}

    async def _spy_run(query: Query, context: RequestContext) -> AsyncIterator[Event]:
        captured["user_id"] = query.user_id
        captured["query"] = query
        async for event in real_run(query, context):
            yield event

    monkeypatch.setattr(app_module, "run", _spy_run)
    return captured


def _valid_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "query": {
            "text": "What gene is BRCA1?",
            "session_id": "session-1",
            "trace_id": "trace-1",
            "user_id": None,
            "audience_depth": "researcher",
        },
        "context": {
            "surface": "web_ui",
            "session_memory": None,
            "operator_mode": False,
        },
    }
    body.update(overrides)
    return body


class TestPostQueryValidRequest:
    def test_valid_request_returns_200(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        response = client.post("/query", json=_valid_body(), headers=headers)
        assert response.status_code == 200

    def test_response_body_is_a_json_array(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        response = client.post("/query", json=_valid_body(), headers=headers)
        assert isinstance(response.json(), list)

    def test_response_contains_guard_and_done_events(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        response = client.post("/query", json=_valid_body(), headers=headers)
        events = response.json()
        types = [event["type"] for event in events]
        assert "guard" in types
        assert "done" in types
        assert types[-1] == "done"

    def test_response_events_carry_the_request_trace_id(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        body["query"]["trace_id"] = "trace-abc-123"
        response = client.post("/query", json=body, headers=headers)
        events = response.json()
        assert len(events) > 0
        for event in events:
            assert event["trace_id"] == "trace-abc-123"

    def test_response_events_declare_v1_version(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        response = client.post("/query", json=_valid_body(), headers=headers)
        events = response.json()
        for event in events:
            assert event["version"] == "v1"


class TestPostQueryValidation:
    """Body-validation tests. Each request authenticates first so a 422
    proves a body problem, never a masked 401."""

    def test_missing_query_text_returns_422(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        del body["query"]["text"]
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 422

    def test_query_text_over_max_length_returns_422(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        body["query"]["text"] = "x" * 2001
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 422

    def test_query_text_at_max_length_is_accepted(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        body["query"]["text"] = "x" * 2000
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 200

    def test_missing_query_object_returns_422(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        del body["query"]
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 422

    def test_missing_context_object_returns_422(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        del body["context"]
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 422

    def test_invalid_surface_value_returns_422(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        body["context"]["surface"] = "carrier_pigeon"
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 422

    def test_invalid_audience_depth_returns_422(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        body["query"]["audience_depth"] = "not_a_real_depth"
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 422

    def test_unknown_top_level_field_rejected(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body(extra_field="nope")
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 422

    def test_unknown_query_field_rejected(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        body["query"]["unexpected"] = "nope"
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 422

    def test_empty_body_returns_422_not_500(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        response = client.post("/query", json={}, headers=headers)
        assert response.status_code == 422


class TestPostQueryAuth:
    """T-2.0-08: auth is required, and the server-derived user_id wins."""

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        response = client.post("/query", json=_valid_body())
        assert response.status_code == 401

    def test_missing_token_never_invokes_run(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called = {"value": False}

        async def _spy_run(query: Query, context: RequestContext) -> AsyncIterator[Event]:
            called["value"] = True
            return
            yield  # pragma: no cover - unreachable, keeps this an async generator

        monkeypatch.setattr(app_module, "run", _spy_run)

        response = client.post("/query", json=_valid_body())
        assert response.status_code == 401
        assert called["value"] is False

    def test_invalid_token_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/query",
            json=_valid_body(),
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert response.status_code == 401

    def test_missing_bearer_scheme_returns_401(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        raw_token = headers["Authorization"].removeprefix("Bearer ")
        response = client.post(
            "/query", json=_valid_body(), headers={"Authorization": raw_token}
        )
        assert response.status_code == 401

    def test_attacker_supplied_user_id_is_ignored_for_the_query_passed_to_run(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-1.1-17 reproduction, closed: the value run() sees is always the
        verified token's subject, never whatever the client wrote into
        query.user_id in the request body."""
        user_id, headers = _auth_headers(client)
        captured = _spy_on_run(monkeypatch)

        body = _valid_body()
        body["query"]["user_id"] = "attacker-chosen-user-id"
        response = client.post("/query", json=body, headers=headers)

        assert response.status_code == 200
        assert captured["user_id"] == user_id
        assert captured["user_id"] != "attacker-chosen-user-id"

    def test_omitted_client_user_id_still_resolves_to_the_authenticated_user(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user_id, headers = _auth_headers(client)
        captured = _spy_on_run(monkeypatch)

        response = client.post("/query", json=_valid_body(), headers=headers)

        assert response.status_code == 200
        assert captured["user_id"] == user_id

    def test_two_different_users_each_get_their_own_server_derived_id(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first_user_id, first_headers = _auth_headers(client)
        captured = _spy_on_run(monkeypatch)
        first_response = client.post("/query", json=_valid_body(), headers=first_headers)
        assert first_response.status_code == 200
        assert captured["user_id"] == first_user_id

        second_user_id, second_headers = _auth_headers(client)
        assert second_user_id != first_user_id
        second_response = client.post("/query", json=_valid_body(), headers=second_headers)
        assert second_response.status_code == 200
        assert captured["user_id"] == second_user_id


class TestPostQueryFiltersCostEvents:
    """T-2.0-07 (Section 19.4): now that run() is the real five-node graph
    and genuinely emits a `cost` event after every metered model call, the
    response `POST /query` returns must never include one, even though the
    harness's internal state (and `_spy_on_run`'s capture of the real,
    unfiltered event stream) does see it."""

    def test_response_body_never_contains_a_cost_event(self, client: TestClient) -> None:
        _user_id, headers = _auth_headers(client)
        response = client.post("/query", json=_valid_body(), headers=headers)
        assert response.status_code == 200
        events = response.json()
        assert all(event["type"] != "cost" for event in events)

    def test_the_real_unfiltered_run_did_emit_a_cost_event(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Proves the filter is doing real work, not passing vacuously
        because run() never produced a cost event in the first place."""
        _user_id, headers = _auth_headers(client)
        captured_events: list[Event] = []

        async def _capturing_run(query: Query, context: RequestContext) -> AsyncIterator[Event]:
            async for event in real_run(query, context):
                captured_events.append(event)
                yield event

        monkeypatch.setattr(app_module, "run", _capturing_run)

        response = client.post("/query", json=_valid_body(), headers=headers)

        assert response.status_code == 200
        assert any(event.type == "cost" for event in captured_events)
        response_types = [event["type"] for event in response.json()]
        assert "cost" not in response_types


class TestPostQueryOperatorMode:
    """`RequestContext.operator_mode` (a phase 1.0 contract field, unwired
    until now): when true AND the caller is on the OPERATOR_USER_IDS
    allowlist, /query skips filter_events_for_end_user entirely, so cost
    events and the real done.total_cost_usd both reach the response.
    This is the lightweight way to see cost and token usage today, ahead
    of a real operator dashboard (phase 5.0/13).

    A security review of the first version of this endpoint flagged that
    honoring `operator_mode: true` purely on the client's say-so, with no
    server-side authorization check, is an authorization bypass. Every
    test below exercises the allowlist gate, not just the flag."""

    def test_operator_mode_false_still_redacts_cost_by_default(
        self, client: TestClient
    ) -> None:
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        body["context"]["operator_mode"] = False
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 200
        events = response.json()
        assert all(event["type"] != "cost" for event in events)
        done_event = next(event for event in events if event["type"] == "done")
        assert done_event["payload"]["total_cost_usd"] == 0.0

    def test_operator_mode_true_but_not_on_the_allowlist_still_redacts(
        self, client: TestClient
    ) -> None:
        """The authorization-bypass regression test: operator_mode alone,
        with no matching OPERATOR_USER_IDS entry, must never expose cost
        data. OPERATOR_USER_IDS is left unset (the default, fail-closed
        per env.example), so no caller is on the allowlist."""
        _user_id, headers = _auth_headers(client)
        body = _valid_body()
        body["context"]["operator_mode"] = True
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 200
        events = response.json()
        assert all(event["type"] != "cost" for event in events)
        done_event = next(event for event in events if event["type"] == "done")
        assert done_event["payload"]["total_cost_usd"] == 0.0

    def test_operator_mode_true_and_on_the_allowlist_exposes_real_data(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user_id, headers = _auth_headers(client)
        monkeypatch.setenv("OPERATOR_USER_IDS", user_id)
        body = _valid_body()
        body["context"]["operator_mode"] = True
        response = client.post("/query", json=body, headers=headers)
        assert response.status_code == 200
        events = response.json()
        assert any(event["type"] == "cost" for event in events)
        done_event = next(event for event in events if event["type"] == "done")
        assert done_event["payload"]["total_cost_usd"] > 0.0

    def test_allowlist_is_per_user_not_all_or_nothing(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two different authenticated users, only one on the allowlist:
        the other still gets the redacted response even with
        operator_mode: true, proving the check is per-caller."""
        operator_user_id, operator_headers = _auth_headers(client)
        monkeypatch.setenv("OPERATOR_USER_IDS", operator_user_id)
        _other_user_id, other_headers = _auth_headers(client)

        body = _valid_body()
        body["context"]["operator_mode"] = True

        operator_response = client.post("/query", json=body, headers=operator_headers)
        other_response = client.post("/query", json=body, headers=other_headers)

        operator_events = operator_response.json()
        other_events = other_response.json()
        assert any(event["type"] == "cost" for event in operator_events)
        assert all(event["type"] != "cost" for event in other_events)
