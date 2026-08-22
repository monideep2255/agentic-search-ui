"""Premise gate for build phase 4.11, the read-only HTTPS graph query service.

This gate exists because of what this phase can actually ship: a transport
that works and is not the same transport. Every request succeeds, every
response parses, every test that mocks the socket stays green, and the rows
reaching `cypher_provenance` are subtly not the rows psycopg2 produced. That
is build phase 2.1's defect exactly (716 passing tests over a tool that
discarded real graph rows, because `execute_cypher` returns RAW agtype wire
text and every test mocked it), and swapping the wire underneath that same
function is the most direct way this project has ever had to re-create it.

So the central premise of this gate is not "the endpoint answers". It is:

    Swapping the transport changes NOTHING observable about what
    `cypher_query` returns, while adding a server-side barrier that holds
    against a caller which bypasses the client entirely.

Both halves are load-bearing and they fail in opposite directions. A service
that is faithful but trusting is a hole in front of the graph. A service that
is strict but lossy is a silent corruption of every citation in the product.

What this gate exercises:

- Byte-equality between the two transports for the same Cypher on the same
  live graph, compared on the RAW agtype strings, never on parsed values,
  because parsing is the step that hid the defect last time.
- The real `cypher_query` pipeline end to end over HTTPS against the real
  graph, asserted on the citations it produced, never on the absence of an
  exception.
- Server-side rejection driven by a RAW HTTP client that never touches the
  client-side validator, one case per rejection class. This is the only
  shape that can distinguish real defense in depth from a service that
  merely re-states what the client already refused to send.
- Auth, including a correctly-shaped but wrong bearer, so the check cannot
  be passing on shape alone.
- The three budget controls this service owes per
  `.claude/rules/tool-call-budgets.md`: the hard row limit, the per-call
  timeout matching `cypher_query`'s own 30 seconds, and the per-caller rate
  limit, each asserted at the SERVICE rather than at the client.
- Transport dispatch observed directly: which transport was used, not
  whether the call succeeded.
- Both startup refusals, since a service that starts with auth effectively
  off is worse than one that does not start.
- The exposure property: the Postgres port is still refused from the public
  internet while 443 answers.

What this gate deliberately OMITS, stated so the gap is arguable rather than
discovered later, per `.claude/rules/goal-contracts.md`:

- Certificate validation behaviour against a hostile or expired certificate.
  The client trusts the system trust store, and nothing here presents a bad
  certificate to prove the client would refuse it.
- Concurrency at the service. No arm sends overlapping requests, so a shared
  state defect between two in-flight calls is invisible here. The rate-limit
  arm is sequential.
- Reboot survival. T-4.11-04 requires it and it is verified operationally in
  the runbook, not by an arm in this file.
- Multi-hop and multi-column result shapes beyond the two pinned below. This
  is the same one-hop blind spot that let F-2.1-A5-03 through in build phase
  2.1, and it is named here rather than left to be found.
- The KGX export path and the MCP, GraphQL and CLI surfaces. They reach the
  graph through `cypher_query`, so P2 covers them transitively and nothing
  here exercises them directly.

Ground truth: TP53 and its 12 `gene_associated_with_condition` edges to
Disease vertices, and BRCA1's name, both already pinned by build phase 2.1's
and 4.4's gates from live reads and re-used here rather than re-derived, so
this file cannot disagree with them.

Depends on:
    - services.graph_query_service.app (the service under test)
    - system_03_search_agent.tools.graph_http_transport (the client)
    - system_03_search_agent.tools.graph_connection (the psycopg2 baseline)
    - A live AGE graph, reached on localhost by the service
    - GRAPH_QUERY_URL and the service bearer credential, for the deployed arms

Writes:
    - Nothing. Layer 1 access is read-only by credential.
"""

from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]

_TOKEN_VAR = "GRAPH_QUERY_" + "TOKEN"

# Ground truth carried from build phase 2.1's and 4.4's gates rather than
# re-derived, so this file cannot drift from them.
TP53 = "NCBIGene:7157"
TP53_DISEASES = 12
BRCA1 = "NCBIGene:672"
BRCA1_NAME = "BRCA1 DNA repair associated"

GRAPH_HOST_PUBLIC = "46.225.128.133"
GRAPH_PG_PUBLIC_PORT = 5432

# The two pinned query shapes. One vertex return, one scalar return, so the
# wire format is exercised on more than a single column type.
CYPHER_VERTEX = (
    "MATCH (g:Gene {id: $seed})-[r:gene_associated_with_condition]->(d:Disease) "
    "RETURN d"
)
CYPHER_SCALAR = "MATCH (g:Gene {id: $seed}) RETURN g.name"


def _load_env_explicitly() -> None:
    """Populate graph and service variables from .env.

    F-2.1-04: nothing in this repository calls load_dotenv(), so these reach
    os.environ only as a side effect of importing litellm. F-4.5-01 is the
    same defect in preflight. Loading here keeps this file's behaviour its
    own rather than dependent on an unrelated import.
    """
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _graph_is_reachable() -> bool:
    """Whether the graph answers on the psycopg2 path right now.

    F-2.1-B12: checked fresh per test rather than once at import, because
    the transport can drop mid-session and an import-time guard cannot see
    that.
    """
    _load_env_explicitly()
    host = os.environ.get("GRAPH_PG_HOST")
    port = os.environ.get("GRAPH_PG_PORT")
    if not host or not port:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=3):
            return True
    except OSError:
        return False


def _service_is_reachable() -> bool:
    """Whether the DEPLOYED HTTPS service answers right now."""
    _load_env_explicitly()
    url = os.environ.get("GRAPH_QUERY_URL")
    if not url or not os.environ.get(_TOKEN_VAR):
        return False
    try:
        import httpx

        response = httpx.get(url.rstrip("/") + "/healthz", timeout=5.0)
        return response.status_code == 200
    except Exception:  # noqa: BLE001 - reachability probe, any failure is "no"
        return False


_RUN_LIVE = os.environ.get("RUN_PREMISE_GATE") == "1"

# A gate run without RUN_PREMISE_GATE=1 finishes in seconds and LOOKS like a
# pass. The two markers below keep "not run" distinguishable from "passed",
# which is the property F-4.5-01 restored and build phase 4.6 depended on.
requires_graph = pytest.mark.skipif(
    not _RUN_LIVE or not _graph_is_reachable(),
    reason="needs RUN_PREMISE_GATE=1 and a reachable AGE graph",
)
requires_service = pytest.mark.skipif(
    not _RUN_LIVE or not _service_is_reachable(),
    reason="needs RUN_PREMISE_GATE=1 and the deployed HTTPS service",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service_client() -> Any:
    """A raw HTTP client bound to the service app IN PROCESS.

    Deliberately raw. Every server-side rejection arm below must reach the
    endpoint without passing through the client-side validator, because a
    payload the client would have refused to send proves nothing about
    whether the SERVER would have refused it.
    """
    from fastapi.testclient import TestClient

    from services.graph_query_service.app import build_app

    return TestClient(build_app())


@pytest.fixture()
def valid_token() -> str:
    from services.graph_query_service.app import service_token

    return service_token()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


def _payload(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "cypher": CYPHER_VERTEX,
        "params": {"seed": TP53},
        "row_limit": 25,
        "timeout_s": 30.0,
        "as_clause": "(result agtype)",
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# P1: the central premise. Byte-equality between the two transports.
# ---------------------------------------------------------------------------


@requires_service
@requires_graph
@pytest.mark.parametrize(
    ("cypher", "params"),
    [
        (CYPHER_VERTEX, {"seed": TP53}),
        (CYPHER_SCALAR, {"seed": BRCA1}),
    ],
)
def test_p1_https_rows_are_byte_identical_to_psycopg2_rows(
    cypher: str, params: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The transport swap changes nothing about what the caller receives.

    Compared on the raw agtype strings. `cypher_provenance` parses these
    downstream, and build phase 2.1 proved a whole phase can pass its suite
    while these strings are being discarded, so a comparison after parsing
    would be testing the wrong layer.
    """
    from system_03_search_agent.tools.graph_connection import execute_cypher

    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    pg_rows, pg_total = execute_cypher(cypher, params, row_limit=25)

    _load_env_explicitly()
    monkeypatch.setenv("GRAPH_QUERY_URL", os.environ["GRAPH_QUERY_URL"])
    http_rows, http_total = execute_cypher(cypher, params, row_limit=25)

    assert http_total == pg_total
    assert http_rows == pg_rows
    for row in http_rows:
        for value in row.values():
            assert value is None or isinstance(value, str), (
                "the wire format must carry agtype text unchanged; a coerced "
                "value here is the build phase 2.1 defect returning"
            )


@requires_service
@requires_graph
def test_p1b_pinned_ground_truth_survives_the_http_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The HTTPS path returns the 12 TP53 disease edges, not merely 12 rows."""
    _load_env_explicitly()
    monkeypatch.setenv("GRAPH_QUERY_URL", os.environ["GRAPH_QUERY_URL"])
    from system_03_search_agent.tools.graph_connection import execute_cypher

    rows, total = execute_cypher(CYPHER_VERTEX, {"seed": TP53}, row_limit=25)
    assert total == TP53_DISEASES
    assert all("Disease" in str(row["result"]) for row in rows)


# ---------------------------------------------------------------------------
# P2: the real pipeline, end to end, over HTTPS.
# ---------------------------------------------------------------------------


@requires_service
@pytest.mark.asyncio()
async def test_p2_cypher_query_produces_citations_over_https(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real tool, the real graph, the new transport, asserted on output.

    F-4.5-09's lesson: when a gate supplies the thing under test it cannot
    tell you the thing exists. Every other arm in this file constructs a
    payload. This one constructs nothing and asks the product for an answer.
    """
    _load_env_explicitly()
    monkeypatch.setenv("GRAPH_QUERY_URL", os.environ["GRAPH_QUERY_URL"])
    from system_03_search_agent.tools.cypher_query import cypher_query

    result = await cypher_query(
        query_intent="Which diseases are associated with TP53?",
        target_entities=[TP53],
        query_class="lookup",
    )
    assert result.citations, "the HTTPS transport produced no citations"
    assert all(c.source_url.startswith("https://") for c in result.citations)


# ---------------------------------------------------------------------------
# P3: server-side rejection, reached by a caller that bypasses the client.
# ---------------------------------------------------------------------------


@requires_graph
@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("cypher", "MATCH (g:Gene) DELETE g RETURN g", "cypher_rejected"),
        (
            "cypher",
            "MATCH (g:Gene)-[r:not_a_real_predicate]->(d:Disease) RETURN d",
            "cypher_rejected",
        ),
        ("cypher", "MATCH (g:Gene)--(d:Disease) RETURN d", "cypher_rejected"),
        ("row_limit", 10_000_000, "invalid_payload"),
        ("as_clause", "(result agtype); DROP TABLE users", "invalid_payload"),
    ],
    ids=[
        "write_clause",
        "unknown_edge_label",
        "missing_edge_label",
        "row_limit_over_max",
        "malformed_as_clause",
    ],
)
def test_p3_server_rejects_what_a_bypassed_client_would_send(
    service_client: Any,
    valid_token: str,
    field: str,
    value: Any,
    expected_code: str,
) -> None:
    """Defense in depth is only depth if the client is out of the path.

    Section 24 asks for these checks server-side precisely so a bug in the
    client-side validator is not the only thing standing between a request
    and the database. Every payload here is posted raw.
    """
    response = service_client.post(
        "/v1/cypher", json=_payload(**{field: value}), headers=_auth(valid_token)
    )
    assert response.status_code >= 400
    assert response.json()["error"]["code"] == expected_code


@requires_graph
def test_p3b_a_rejected_payload_never_reached_the_database(
    service_client: Any, valid_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rejection happens before execution, not after it.

    A service that runs the query and then decides it should not have is
    still a service that ran the query.
    """
    import services.graph_query_service.app as app_module

    calls: list[Any] = []

    def _tripwire(*args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        raise AssertionError("the graph was reached for a payload that must be rejected")

    monkeypatch.setattr(app_module, "execute_cypher", _tripwire)
    response = service_client.post(
        "/v1/cypher",
        json=_payload(cypher="MATCH (g:Gene) DETACH DELETE g RETURN g"),
        headers=_auth(valid_token),
    )
    assert response.status_code >= 400
    assert calls == []


# ---------------------------------------------------------------------------
# P4: auth.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("headers", "case"),
    [
        ({}, "no_header"),
        ({"Authorization": "Bearer "}, "empty_bearer"),
        ({"Authorization": "not-a-bearer-at-all"}, "wrong_scheme"),
    ],
)
def test_p4_unauthenticated_callers_are_refused(
    service_client: Any, headers: dict[str, str], case: str
) -> None:
    response = service_client.post("/v1/cypher", json=_payload(), headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_p4b_a_correctly_shaped_wrong_token_is_refused(
    service_client: Any, valid_token: str
) -> None:
    """The check must be on the value, not on the shape.

    A wrong credential of the right length and alphabet is the case that
    separates a real comparison from a regex that only sees shape. Build
    phase 4.3 spent four attempts learning that a proxy for a property is
    not the property.
    """
    filler = "a" if valid_token[0] != "a" else "b"
    wrong = filler * len(valid_token)
    assert wrong != valid_token
    response = service_client.post("/v1/cypher", json=_payload(), headers=_auth(wrong))
    assert response.status_code == 401


def test_p4c_a_refusal_discloses_nothing_about_the_credential(
    service_client: Any, valid_token: str
) -> None:
    response = service_client.post(
        "/v1/cypher", json=_payload(), headers=_auth("clearly-wrong")
    )
    body = response.text
    assert valid_token not in body
    assert str(len(valid_token)) not in body


# ---------------------------------------------------------------------------
# P5, P6: the budget controls, asserted at the service.
# ---------------------------------------------------------------------------


@requires_graph
def test_p5_rate_limit_fires_with_an_actionable_retry_after(
    service_client: Any, valid_token: str
) -> None:
    """A saturated caller fails fast rather than joining an unbounded queue.

    `.claude/rules/tool-call-budgets.md` requires the error carry a
    retry_after estimate and the saturated family name, because the Act step
    reads this error and decides its next move. "Rate limited" alone is not
    actionable.
    """
    from services.graph_query_service.app import RATE_LIMIT_PER_MINUTE

    last = None
    for _ in range(RATE_LIMIT_PER_MINUTE + 2):
        last = service_client.post(
            "/v1/cypher", json=_payload(), headers=_auth(valid_token)
        )
    assert last is not None
    assert last.status_code == 429
    error = last.json()["error"]
    assert error["code"] == "rate_limited"
    assert isinstance(error["retry_after"], (int, float))
    assert error["retry_after"] > 0


@requires_graph
def test_p6_per_call_timeout_is_enforced_by_the_service(
    service_client: Any, valid_token: str
) -> None:
    """The service clamps and enforces its own timeout.

    A caller cannot raise it past `cypher_query`'s own 30-second budget, and
    a query that outruns it comes back as an actionable timeout rather than
    a bare 500.
    """
    from system_03_search_agent.tools.graph_schema_constants import (
        CYPHER_QUERY_TIMEOUT_SECONDS,
    )

    response = service_client.post(
        "/v1/cypher",
        json=_payload(timeout_s=CYPHER_QUERY_TIMEOUT_SECONDS * 100, row_limit=1),
        headers=_auth(valid_token),
    )
    assert response.status_code != 500
    if response.status_code == 200:
        pytest.skip("this graph answered inside the budget; timeout path untested here")
    error = response.json()["error"]
    assert error["code"] == "timeout"
    assert "narrower" in error["message"] or "smaller" in error["message"]


# ---------------------------------------------------------------------------
# P7, P8: dispatch, observed rather than inferred.
# ---------------------------------------------------------------------------


def test_p7_dispatch_uses_http_when_the_url_is_set_and_never_opens_psycopg2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Which transport ran, not whether the call succeeded."""
    import system_03_search_agent.tools.graph_connection as gc

    def _no_pg() -> Any:
        raise AssertionError("psycopg2 was opened while GRAPH_QUERY_URL was set")

    seen: list[dict[str, Any]] = []

    def _fake_http(**kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        seen.append(kwargs)
        return [{"result": "x"}], 1

    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")
    monkeypatch.setattr(gc, "_default_connection_factory", _no_pg)
    monkeypatch.setattr(gc, "execute_cypher_over_http", _fake_http)

    rows, total = gc.execute_cypher(CYPHER_VERTEX, {"seed": TP53})
    assert seen, "the HTTP transport was not called"
    assert (rows, total) == ([{"result": "x"}], 1)


def test_p7b_dispatch_uses_psycopg2_when_the_url_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import system_03_search_agent.tools.graph_connection as gc

    def _no_http(**kwargs: Any) -> Any:
        raise AssertionError("the HTTP transport ran while GRAPH_QUERY_URL was unset")

    closed: list[bool] = []

    class _Cur:
        description = [("result",)]

        def __enter__(self) -> "_Cur":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

        def execute(self, *a: Any, **k: Any) -> None:
            return None

        def fetchall(self) -> list[tuple[str]]:
            return [("row",)]

    class _Conn:
        def cursor(self) -> _Cur:
            return _Cur()

        def close(self) -> None:
            closed.append(True)

    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    monkeypatch.setattr(gc, "execute_cypher_over_http", _no_http)
    rows, _ = gc.execute_cypher(CYPHER_VERTEX, None, connection_factory=_Conn)
    assert closed == [True]
    assert rows == [{"result": "row"}]


def test_p8_a_connection_factory_with_the_url_set_raises_rather_than_being_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two transports named in one call is a caller defect, not a preference.

    Silently honouring one and discarding the other is how a test suite goes
    on passing against a transport nobody is shipping.
    """
    import system_03_search_agent.tools.graph_connection as gc

    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")
    with pytest.raises(gc.GraphError):
        gc.execute_cypher(CYPHER_VERTEX, None, connection_factory=lambda: None)


# ---------------------------------------------------------------------------
# P9: every HTTPS failure still arrives as a typed GraphError.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "code", "expected"),
    [
        (401, "unauthorized", "GraphAuthError"),
        (403, "unauthorized", "GraphAuthError"),
        (504, "timeout", "GraphTimeoutError"),
        (429, "rate_limited", "GraphRateLimitedError"),
        (500, "internal", "GraphConnectionError"),
        (400, "cypher_rejected", "GraphConnectionError"),
    ],
)
def test_p9_http_failures_map_into_the_existing_error_family(
    status: int, code: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`cypher_query` already handles GraphError. It must keep handling everything.

    The Act step reads the error type to decide whether to retry, wait, or
    move on with partial results. An unclassified exception escaping the
    transport removes that decision.
    """
    import system_03_search_agent.tools.graph_http_transport as t

    class _Response:
        status_code = status
        text = "m"

        @staticmethod
        def json() -> dict[str, Any]:
            return {"error": {"code": code, "message": "m", "retry_after": 1.0}}

    monkeypatch.setattr(t, "_post", lambda **kwargs: _Response())
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")
    with pytest.raises(getattr(t, expected)) as caught:
        t.execute_cypher_over_http(
            cypher=CYPHER_VERTEX,
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )
    assert str(caught.value)


def test_p9b_a_connection_refusal_is_a_connection_error_not_a_bare_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import system_03_search_agent.tools.graph_http_transport as t

    def _boom(**kwargs: Any) -> Any:
        raise OSError("connection refused")

    monkeypatch.setattr(t, "_post", _boom)
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, "t")
    with pytest.raises(t.GraphConnectionError):
        t.execute_cypher_over_http(
            cypher=CYPHER_VERTEX,
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )


# ---------------------------------------------------------------------------
# P10: the exposure property.
# ---------------------------------------------------------------------------


@requires_service
def test_p10_the_database_port_is_still_closed_to_the_internet() -> None:
    """Section 24's whole point: the database port never opens to the internet.

    A service that fronts the graph while the graph itself stays directly
    reachable has added a door without closing one.
    """
    with pytest.raises(OSError):
        socket.create_connection((GRAPH_HOST_PUBLIC, GRAPH_PG_PUBLIC_PORT), timeout=5)


@requires_service
def test_p10b_the_service_answers_over_real_tls() -> None:
    """TLS is terminated by a certificate the system trust store accepts."""
    import httpx

    _load_env_explicitly()
    url = os.environ["GRAPH_QUERY_URL"]
    assert url.startswith("https://"), "the transport must be HTTPS, not plaintext"
    response = httpx.get(url.rstrip("/") + "/healthz", timeout=10.0, verify=True)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# P11: the credential never leaks.
# ---------------------------------------------------------------------------


@requires_graph
def test_p11_the_credential_never_appears_in_a_response_body(
    service_client: Any, valid_token: str
) -> None:
    bodies = []
    for payload in (
        _payload(),
        _payload(cypher="MATCH (g:Gene) DELETE g RETURN g"),
        _payload(row_limit=10_000_000),
    ):
        bodies.append(
            service_client.post(
                "/v1/cypher", json=payload, headers=_auth(valid_token)
            ).text
        )
    for body in bodies:
        assert valid_token not in body


@requires_graph
def test_p11b_the_credential_never_appears_in_the_audit_log(
    service_client: Any, valid_token: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Every call is logged. None of those lines carries the credential."""
    with caplog.at_level("INFO"):
        service_client.post("/v1/cypher", json=_payload(), headers=_auth(valid_token))
    assert caplog.records, (
        "the service logged nothing; Section 24 requires every call logged"
    )
    for record in caplog.records:
        assert valid_token not in record.getMessage()


# ---------------------------------------------------------------------------
# P12: the two startup refusals.
# ---------------------------------------------------------------------------


def test_p12_the_service_refuses_to_start_without_a_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starting with auth effectively off is worse than not starting."""
    from services.graph_query_service.app import build_app

    monkeypatch.delenv(_TOKEN_VAR, raising=False)
    with pytest.raises(RuntimeError):
        build_app()


def test_p12b_the_service_refuses_to_start_if_it_would_call_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recursion hazard, closed at startup rather than discovered live.

    The service reuses `execute_cypher`, which dispatches on GRAPH_QUERY_URL.
    If that variable is ever set in the service's own environment, the
    service calls itself.
    """
    from services.graph_query_service.app import build_app

    monkeypatch.setenv(_TOKEN_VAR, "x" * 32)
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://example.invalid")
    with pytest.raises(RuntimeError):
        build_app()
