"""Unit tests for the graph query service application, T-4.11-02.

These tests never touch a live graph. Every arm that would otherwise reach
`execute_cypher` uses a fake, injected by monkeypatching this service
module's own `execute_cypher` global, the same seam the premise gate's
tripwire arm (P3b) depends on. The live half, byte-equality against the
real psycopg2 path, the real end-to-end pipeline, and the deployed
service's exposure and TLS properties, is covered by
`tests/system_03_search_agent/tools/test_graph_query_service_premise.py`
and is out of scope here.

Depends on:
    - services.graph_query_service.app (the module under test)
    - system_03_search_agent.tools.graph_connection (GraphError family,
      for raising the fakes)
    - system_03_search_agent.tools.graph_schema_constants (MAX_ROW_LIMIT,
      CYPHER_QUERY_TIMEOUT_SECONDS, used to compute clamp boundaries)

Writes:
    - Nothing.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import services.graph_query_service.app as app_module
from services.graph_query_service.app import (
    RATE_LIMIT_PER_MINUTE,
    ServiceError,
    build_app,
    service_token,
)
from system_03_search_agent.tools.graph_connection import (
    GraphAuthError,
    GraphConnectionError,
    GraphTimeoutError,
)
from system_03_search_agent.tools.graph_schema_constants import (
    CYPHER_QUERY_TIMEOUT_SECONDS,
    MAX_ROW_LIMIT,
)

_TOKEN_ENV_VAR = "GRAPH_QUERY_" + "TOKEN"
_TEST_TOKEN = "unit-test-token-not-a-real-secret-0123456789"


@pytest.fixture()
def configured_env(monkeypatch: pytest.MonkeyPatch) -> str:
    """A minimally valid environment: a token set, GRAPH_QUERY_URL unset."""
    monkeypatch.setenv(_TOKEN_ENV_VAR, _TEST_TOKEN)
    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    return _TEST_TOKEN


@pytest.fixture()
def client(configured_env: str) -> TestClient:
    return TestClient(build_app())


def _auth(token: str = _TEST_TOKEN) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def _payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "cypher": "MATCH (g:Gene {id: $seed}) RETURN g.name",
        "params": {"seed": "NCBIGene:7157"},
        "row_limit": 25,
        "timeout_s": 30.0,
        "as_clause": "(result agtype)",
    }
    body.update(overrides)
    return body


def _install_fake_execute_cypher(
    monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]], total: int
) -> list[dict[str, Any]]:
    """Monkeypatch this module's own execute_cypher global to a fake.

    Returns the list every call's kwargs get appended to, so a test can
    assert what execute_cypher was actually called with (row_limit and
    timeout_s after clamping, the normalized cypher, and so on).
    """
    calls: list[dict[str, Any]] = []

    def _fake(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        calls.append(kwargs | {"_cypher": args[0] if args else kwargs.get("cypher")})
        return rows, total

    monkeypatch.setattr(app_module, "execute_cypher", _fake)
    return calls


def _install_raising_execute_cypher(
    monkeypatch: pytest.MonkeyPatch, exc: Exception
) -> None:
    def _fake(*args: Any, **kwargs: Any) -> Any:
        raise exc

    monkeypatch.setattr(app_module, "execute_cypher", _fake)


# ---------------------------------------------------------------------------
# Startup refusals
# ---------------------------------------------------------------------------


def test_build_app_refuses_to_start_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_TOKEN_ENV_VAR, raising=False)
    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    with pytest.raises(RuntimeError):
        build_app()


def test_build_app_refuses_to_start_with_an_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_TOKEN_ENV_VAR, "")
    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    with pytest.raises(RuntimeError):
        build_app()


def test_build_app_refuses_to_start_if_graph_query_url_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(_TOKEN_ENV_VAR, _TEST_TOKEN)
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    with pytest.raises(RuntimeError):
        build_app()


def test_build_app_starts_with_a_valid_configuration(configured_env: str) -> None:
    app = build_app()
    assert app is not None


# ---------------------------------------------------------------------------
# healthz
# ---------------------------------------------------------------------------


def test_healthz_needs_no_auth_and_reveals_nothing(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok"}


# ---------------------------------------------------------------------------
# Auth: valid, invalid, and missing input on the credential itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer "},
        {"Authorization": "not-a-bearer-at-all"},
        {"Authorization": "Bearer wrong-token-same-ish-length-as-real-one"},
    ],
    ids=["no_header", "empty_bearer", "wrong_scheme", "wrong_value"],
)
def test_auth_rejects_every_invalid_credential_shape(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.post("/v1/cypher", json=_payload(), headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_auth_accepts_the_configured_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_execute_cypher(monkeypatch, [{"result": "BRCA1"}], 1)
    response = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert response.status_code == 200


def test_auth_rejection_never_discloses_the_token_or_its_length(client: TestClient) -> None:
    response = client.post(
        "/v1/cypher", json=_payload(), headers={"Authorization": "Bearer nope"}
    )
    body = response.text
    assert _TEST_TOKEN not in body
    assert str(len(_TEST_TOKEN)) not in body


# ---------------------------------------------------------------------------
# Request shape: valid, invalid, and null/missing input
# ---------------------------------------------------------------------------


def test_valid_request_returns_200_with_the_rows_and_total(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_execute_cypher(monkeypatch, [{"result": "BRCA1 DNA repair associated"}], 1)
    response = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert response.status_code == 200
    body = response.json()
    assert body == {"rows": [{"result": "BRCA1 DNA repair associated"}], "total_available": 1}


def test_extra_field_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/cypher", json=_payload(unexpected_field="x"), headers=_auth()
    )
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "invalid_payload"


@pytest.mark.parametrize("field", ["cypher", "row_limit", "timeout_s", "as_clause"])
def test_missing_required_field_is_rejected(client: TestClient, field: str) -> None:
    body = _payload()
    del body[field]
    response = client.post("/v1/cypher", json=body, headers=_auth())
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "invalid_payload"


def test_null_cypher_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/cypher", json=_payload(cypher=None), headers=_auth())
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "invalid_payload"


def test_malformed_json_body_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/cypher",
        content=b"{not valid json",
        headers=_auth() | {"Content-Type": "application/json"},
    )
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "invalid_payload"


def test_params_may_be_null(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_execute_cypher(monkeypatch, [{"result": "x"}], 1)
    response = client.post("/v1/cypher", json=_payload(params=None), headers=_auth())
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# The clamp-versus-reject boundary
# ---------------------------------------------------------------------------


def test_row_limit_inside_the_band_but_over_max_is_clamped_not_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_execute_cypher(monkeypatch, [{"result": "x"}], 1)
    response = client.post(
        "/v1/cypher", json=_payload(row_limit=MAX_ROW_LIMIT * 3), headers=_auth()
    )
    assert response.status_code == 200
    assert calls[0]["row_limit"] == MAX_ROW_LIMIT


def test_row_limit_far_outside_the_band_is_rejected_not_clamped(client: TestClient) -> None:
    response = client.post("/v1/cypher", json=_payload(row_limit=10_000_000), headers=_auth())
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "invalid_payload"


def test_row_limit_below_one_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/cypher", json=_payload(row_limit=0), headers=_auth())
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "invalid_payload"


def test_timeout_far_over_budget_is_clamped_not_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _install_fake_execute_cypher(monkeypatch, [{"result": "x"}], 1)
    response = client.post(
        "/v1/cypher",
        json=_payload(timeout_s=CYPHER_QUERY_TIMEOUT_SECONDS * 100),
        headers=_auth(),
    )
    assert response.status_code == 200
    assert calls[0]["timeout_s"] == CYPHER_QUERY_TIMEOUT_SECONDS


def test_timeout_at_or_below_zero_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/cypher", json=_payload(timeout_s=0), headers=_auth())
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "invalid_payload"


def test_malformed_as_clause_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/v1/cypher",
        json=_payload(as_clause="(result agtype); DROP TABLE users"),
        headers=_auth(),
    )
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "invalid_payload"


# ---------------------------------------------------------------------------
# Server-side cypher re-validation, and the tripwire
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cypher",
    [
        "MATCH (g:Gene) DELETE g RETURN g",
        "MATCH (g:Gene)-[r:not_a_real_predicate]->(d:Disease) RETURN d",
        "MATCH (g:Gene)--(d:Disease) RETURN d",
    ],
    ids=["write_clause", "unknown_edge_label", "missing_edge_label"],
)
def test_server_side_validation_rejects_unsafe_cypher(client: TestClient, cypher: str) -> None:
    response = client.post("/v1/cypher", json=_payload(cypher=cypher), headers=_auth())
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == "cypher_rejected"


def test_a_rejected_cypher_never_reaches_execute_cypher(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Any] = []

    def _tripwire(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        raise AssertionError("execute_cypher was called for a query that must be rejected")

    monkeypatch.setattr(app_module, "execute_cypher", _tripwire)
    response = client.post(
        "/v1/cypher",
        json=_payload(cypher="MATCH (g:Gene) DETACH DELETE g RETURN g"),
        headers=_auth(),
    )
    assert response.status_code >= 400
    assert calls == []


# ---------------------------------------------------------------------------
# The wire encoding
# ---------------------------------------------------------------------------


def test_string_and_null_cells_pass_through_unchanged(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_execute_cypher(
        monkeypatch,
        [{"result": '{"id": 844424930131969, "label": "Gene"}::vertex'}, {"result": None}],
        2,
    )
    response = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert rows[0]["result"] == '{"id": 844424930131969, "label": "Gene"}::vertex'
    assert rows[1]["result"] is None


@pytest.mark.parametrize(
    "bad_value", [42, 3.14, True, ["nested"], {"nested": "dict"}], ids=["int", "float", "bool", "list", "dict"]
)
def test_a_non_string_non_null_cell_is_rejected_not_coerced(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, bad_value: Any
) -> None:
    _install_fake_execute_cypher(monkeypatch, [{"result": bad_value}], 1)
    response = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert response.status_code >= 400
    error = response.json()["error"]
    assert error["code"] == "graph_wire_encoding"
    # The coerced string form must never appear: a str(bad_value) anywhere
    # in the body would mean the value was silently stringified rather
    # than rejected, which is exactly the defect this arm exists to catch.
    assert str(bad_value) not in response.text or isinstance(bad_value, str)


# ---------------------------------------------------------------------------
# GraphError mapping
# ---------------------------------------------------------------------------


def test_graph_timeout_error_maps_to_timeout_504(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_raising_execute_cypher(
        monkeypatch,
        GraphTimeoutError("graph query exceeded 90s, retry with a narrower query_intent"),
    )
    response = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert response.status_code == 504
    error = response.json()["error"]
    assert error["code"] == "timeout"
    assert "narrower" in error["message"] or "smaller" in error["message"]


def test_graph_auth_error_maps_to_graph_unavailable_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_raising_execute_cypher(monkeypatch, GraphAuthError("kg_reader auth failed"))
    response = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "graph_unavailable"


def test_graph_connection_error_maps_to_graph_unavailable_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_raising_execute_cypher(
        monkeypatch, GraphConnectionError("graph connection refused")
    )
    response = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "graph_unavailable"


def test_an_unexpected_exception_is_not_leaked_as_a_bare_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_raising_execute_cypher(monkeypatch, ValueError("something unrelated broke"))
    response = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "graph_unavailable"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def test_rate_limit_fires_with_a_positive_retry_after(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_execute_cypher(monkeypatch, [{"result": "x"}], 1)
    last = None
    for _ in range(RATE_LIMIT_PER_MINUTE + 2):
        last = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert last is not None
    assert last.status_code == 429
    error = last.json()["error"]
    assert error["code"] == "rate_limited"
    assert isinstance(error["retry_after"], (int, float))
    assert error["retry_after"] > 0


def test_rate_limit_is_scoped_per_caller(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A flood of wrong-token attempts never consumes the real caller's budget.

    Auth is checked before the rate limiter is ever consulted, so a wrong
    token is rejected with 401 and never reaches `_rate_limiter.check` at
    all. This asserts that property holds: the real caller's request still
    succeeds after a flood of failed-auth attempts larger than the limit.
    """
    _install_fake_execute_cypher(monkeypatch, [{"result": "x"}], 1)
    for _ in range(RATE_LIMIT_PER_MINUTE + 5):
        client.post(
            "/v1/cypher", json=_payload(), headers={"Authorization": "Bearer wrong"}
        )
    response = client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Logging: caller identified by digest, credential never present
# ---------------------------------------------------------------------------


def test_every_call_is_logged_without_the_credential(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _install_fake_execute_cypher(monkeypatch, [{"result": "x"}], 1)
    with caplog.at_level("INFO"):
        client.post("/v1/cypher", json=_payload(), headers=_auth())
    assert caplog.records, "the service logged nothing for a valid authenticated call"
    for record in caplog.records:
        assert _TEST_TOKEN not in record.getMessage()


def test_the_logged_caller_identity_is_a_digest_not_the_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _install_fake_execute_cypher(monkeypatch, [{"result": "x"}], 1)
    with caplog.at_level("INFO"):
        client.post("/v1/cypher", json=_payload(), headers=_auth())
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "caller=" in messages
    assert _TEST_TOKEN not in messages


def test_a_rejected_call_is_still_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    """The audit trail covers rejected queries too, not only successes."""
    with caplog.at_level("INFO"):
        client.post(
            "/v1/cypher",
            json=_payload(cypher="MATCH (g:Gene) DELETE g RETURN g"),
            headers=_auth(),
        )
    assert caplog.records


# ---------------------------------------------------------------------------
# ServiceError itself
# ---------------------------------------------------------------------------


def test_service_error_carries_code_message_and_retry_after() -> None:
    exc = ServiceError("rate_limited", "too many calls", retry_after=1.5)
    assert exc.code == "rate_limited"
    assert exc.message == "too many calls"
    assert exc.retry_after == 1.5


def test_service_token_reads_the_environment_fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_TOKEN_ENV_VAR, "first")
    assert service_token() == "first"
    monkeypatch.setenv(_TOKEN_ENV_VAR, "second")
    assert service_token() == "second"
    monkeypatch.delenv(_TOKEN_ENV_VAR, raising=False)
    assert service_token() == ""
