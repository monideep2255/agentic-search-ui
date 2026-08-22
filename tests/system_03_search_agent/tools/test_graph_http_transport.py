"""Tests for the client-side HTTPS transport, T-4.11-03.

This is unit-level coverage of `graph_http_transport` itself: request
construction, every failure mapping, the no-retry property, credential
redaction, and pass-through fidelity of the raw agtype wire text. The
dispatch decision inside `graph_connection.execute_cypher` (which transport
runs, and the connection_factory conflict) is covered separately in
`test_graph_connection.py`, mirroring this phase's premise gate arms P7,
P7b, and P8. The end-to-end byte-equality and server-side rejection arms
live in `test_graph_query_service_premise.py` and require a live graph and
deployed service; nothing here does.

Every import of `graph_connection` or `graph_http_transport` below is
deliberately inside the test function bodies rather than at this file's
top level. The two modules have a genuine circular import (see
`graph_http_transport`'s own module docstring for the full explanation and
the resolution), and importing whichever module first at this file's own
top level, before any other test file has touched either module, would be
the one ordering most likely to exercise the lazy-resolution fallback
rather than the direct path. Deferring to function bodies matches the
premise gate test file's own convention and keeps this file's collection
order irrelevant to which import path is taken.

Depends on:
    - system_03_search_agent.tools.graph_http_transport
    - system_03_search_agent.tools.graph_connection (GraphError family,
      re-exported through graph_http_transport)

Reads:
    - Nothing from the real environment; every test sets or deletes
      GRAPH_QUERY_URL and GRAPH_QUERY_TOKEN explicitly via monkeypatch.

Writes:
    - Nothing. All network I/O is monkeypatched at the _post seam.
"""

from __future__ import annotations

from typing import Any

import pytest

_TOKEN_VAR = "GRAPH_QUERY_" + "TOKEN"


class _FakeResponse:
    """A minimal stand-in for an httpx.Response."""

    def __init__(
        self,
        status_code: int,
        body: dict[str, Any] | None = None,
        text: str = "",
        json_raises: bool = False,
    ) -> None:
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = text or str(body)
        self._json_raises = json_raises

    def json(self) -> dict[str, Any]:
        if self._json_raises:
            raise ValueError("not valid JSON")
        return self._body


def _set_transport_env(monkeypatch: pytest.MonkeyPatch, token: str = "s3cr3t-token") -> str:
    monkeypatch.setenv("GRAPH_QUERY_URL", "https://graph.example.invalid")
    monkeypatch.setenv(_TOKEN_VAR, token)
    return token


# ---------------------------------------------------------------------------
# Request construction
# ---------------------------------------------------------------------------


def test_request_carries_the_bearer_header_and_the_five_body_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import system_03_search_agent.tools.graph_http_transport as t

    token = _set_transport_env(monkeypatch)
    seen: dict[str, Any] = {}

    def _fake_post(**kwargs: Any) -> _FakeResponse:
        seen.update(kwargs)
        return _FakeResponse(200, {"rows": [], "total_available": 0})

    monkeypatch.setattr(t, "_post", _fake_post)

    t.execute_cypher_over_http(
        cypher="MATCH (g:Gene) RETURN g",
        params={"seed": "NCBIGene:7157"},
        row_limit=25,
        timeout_s=30.0,
        as_clause="(result agtype)",
    )

    assert seen["url"].endswith("/v1/cypher")
    assert seen["headers"]["Authorization"] == "Bearer " + token
    assert seen["json"] == {
        "cypher": "MATCH (g:Gene) RETURN g",
        "params": {"seed": "NCBIGene:7157"},
        "row_limit": 25,
        "timeout_s": 30.0,
        "as_clause": "(result agtype)",
    }
    assert seen["timeout"] == 30.0


def test_missing_url_raises_before_any_post_is_attempted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import system_03_search_agent.tools.graph_http_transport as t

    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)
    calls = []
    monkeypatch.setattr(t, "_post", lambda **kwargs: calls.append(kwargs))

    with pytest.raises(t.GraphConnectionError):
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )
    assert calls == []


# ---------------------------------------------------------------------------
# Failure mapping: every status/code pair maps to the right typed error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "code", "expected_type_name"),
    [
        (401, "unauthorized", "GraphAuthError"),
        (403, "unauthorized", "GraphAuthError"),
        (504, "timeout", "GraphTimeoutError"),
        (429, "rate_limited", "GraphRateLimitedError"),
        (500, "internal", "GraphConnectionError"),
        (400, "cypher_rejected", "GraphConnectionError"),
    ],
    ids=[
        "401_maps_to_auth_error",
        "403_maps_to_auth_error",
        "504_maps_to_timeout_error",
        "429_maps_to_rate_limited_error",
        "500_maps_to_connection_error",
        "400_cypher_rejected_maps_to_connection_error",
    ],
)
def test_every_status_and_code_maps_to_the_pinned_error_type(
    monkeypatch: pytest.MonkeyPatch, status: int, code: str, expected_type_name: str
) -> None:
    import system_03_search_agent.tools.graph_http_transport as t

    _set_transport_env(monkeypatch)
    response = _FakeResponse(
        status, {"error": {"code": code, "message": "m", "retry_after": 2.5}}
    )
    monkeypatch.setattr(t, "_post", lambda **kwargs: response)

    expected_type = getattr(t, expected_type_name)
    with pytest.raises(expected_type) as excinfo:
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )
    assert str(excinfo.value)


def test_rate_limited_error_carries_the_retry_after_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Act step reads retry_after to decide when to try again, not just
    that it should. A rate_limited error with no retry_after is not
    actionable, per .claude/rules/tool-call-budgets.md.
    """
    import system_03_search_agent.tools.graph_http_transport as t

    _set_transport_env(monkeypatch)
    response = _FakeResponse(
        429, {"error": {"code": "rate_limited", "message": "m", "retry_after": 7.0}}
    )
    monkeypatch.setattr(t, "_post", lambda **kwargs: response)

    with pytest.raises(t.GraphRateLimitedError) as excinfo:
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )
    assert excinfo.value.retry_after == 7.0


def test_a_bare_transport_exception_becomes_a_connection_error_not_a_bare_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every transport-level exception, whatever its type, must arrive at
    the caller as a typed GraphError. Caught by base class, never by an
    enumerated list: this repository had one defect appear four times in
    build phase 4.2 from catchers naming exception types their raisers
    never actually raise.
    """
    import system_03_search_agent.tools.graph_http_transport as t

    _set_transport_env(monkeypatch)

    class _WeirdTransportFailure(RuntimeError):
        pass

    def _boom(**kwargs: Any) -> Any:
        raise _WeirdTransportFailure("socket reset by peer")

    monkeypatch.setattr(t, "_post", _boom)

    with pytest.raises(t.GraphConnectionError):
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )


def test_a_malformed_200_body_becomes_a_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 200 status with a body that does not carry rows/total_available is
    still a transport-layer failure from the caller's point of view, not a
    KeyError escaping this module.
    """
    import system_03_search_agent.tools.graph_http_transport as t

    _set_transport_env(monkeypatch)
    response = _FakeResponse(200, {"unexpected": "shape"})
    monkeypatch.setattr(t, "_post", lambda **kwargs: response)

    with pytest.raises(t.GraphConnectionError):
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )


def test_a_malformed_error_body_still_maps_to_a_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-200 response whose body is not valid JSON at all must still
    reach the caller as a typed GraphError, not an unhandled ValueError
    from response.json() itself.
    """
    import system_03_search_agent.tools.graph_http_transport as t

    _set_transport_env(monkeypatch)
    response = _FakeResponse(500, json_raises=True, text="<html>502 bad gateway</html>")
    monkeypatch.setattr(t, "_post", lambda **kwargs: response)

    with pytest.raises(t.GraphConnectionError):
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )


# ---------------------------------------------------------------------------
# No retry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "failure_mode",
    ["exception", "timeout_status", "rate_limited_status", "connection_status"],
)
def test_a_failure_never_triggers_a_second_post_call(
    monkeypatch: pytest.MonkeyPatch, failure_mode: str
) -> None:
    """A retry here would double a caller's spend against a rate limit the
    service itself enforces. The Act step is the retry layer, not this
    module, per T-4.11-03's own acceptance criteria.
    """
    import system_03_search_agent.tools.graph_http_transport as t

    _set_transport_env(monkeypatch)
    calls: list[Any] = []

    def _counting_post(**kwargs: Any) -> _FakeResponse:
        calls.append(kwargs)
        if failure_mode == "exception":
            raise OSError("connection refused")
        if failure_mode == "timeout_status":
            return _FakeResponse(504, {"error": {"code": "timeout", "message": "m"}})
        if failure_mode == "rate_limited_status":
            return _FakeResponse(
                429, {"error": {"code": "rate_limited", "message": "m", "retry_after": 1}}
            )
        return _FakeResponse(500, {"error": {"code": "internal", "message": "m"}})

    monkeypatch.setattr(t, "_post", _counting_post)

    with pytest.raises(t.GraphError):
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )

    assert len(calls) == 1, (
        "execute_cypher_over_http called _post more than once on failure; "
        "this module must never retry, the Act step already owns that"
    )


# ---------------------------------------------------------------------------
# Credential redaction
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "unauthorized"),
        (504, "timeout"),
        (429, "rate_limited"),
        (500, "internal"),
    ],
)
def test_the_token_never_appears_in_a_raised_message(
    monkeypatch: pytest.MonkeyPatch, status: int, code: str
) -> None:
    import system_03_search_agent.tools.graph_http_transport as t

    token = _set_transport_env(monkeypatch, token="do-not-leak-this-value")
    response = _FakeResponse(
        status, {"error": {"code": code, "message": "m " + token, "retry_after": 3}}
    )
    monkeypatch.setattr(t, "_post", lambda **kwargs: response)

    with pytest.raises(t.GraphError) as excinfo:
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )
    assert token not in str(excinfo.value)


def test_the_token_never_appears_in_a_transport_exception_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import system_03_search_agent.tools.graph_http_transport as t

    token = _set_transport_env(monkeypatch, token="do-not-leak-this-value-either")

    def _boom(**kwargs: Any) -> Any:
        raise OSError("failed for token=" + token)

    monkeypatch.setattr(t, "_post", _boom)

    with pytest.raises(t.GraphConnectionError) as excinfo:
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )
    assert token not in str(excinfo.value)


def test_the_token_length_is_not_a_usable_side_channel_either(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redaction strips the exact value. This checks the module does not
    separately leak the credential's length in a raised message, the same
    side-channel this phase's premise gate arm P4c checks at the service.
    """
    import system_03_search_agent.tools.graph_http_transport as t

    token = _set_transport_env(monkeypatch, token="x" * 47)
    response = _FakeResponse(401, {"error": {"code": "unauthorized", "message": "m"}})
    monkeypatch.setattr(t, "_post", lambda **kwargs: response)

    with pytest.raises(t.GraphAuthError) as excinfo:
        t.execute_cypher_over_http(
            cypher="MATCH (g:Gene) RETURN g",
            params=None,
            row_limit=25,
            timeout_s=30.0,
            as_clause="(result agtype)",
        )
    assert str(len(token)) not in str(excinfo.value)


# ---------------------------------------------------------------------------
# Pass-through fidelity of the raw agtype wire text
# ---------------------------------------------------------------------------


def test_a_row_with_braces_quotes_and_a_vertex_suffix_passes_through_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The central risk this phase can ship: a transport that subtly
    coerces or re-encodes the raw agtype wire text `cypher_provenance`
    parses downstream. Build phase 2.1 shipped 716 passing tests over a
    tool that discarded exactly these strings, so this module must never
    touch a cell's content, only pass the JSON body's rows through.
    """
    import system_03_search_agent.tools.graph_http_transport as t

    _set_transport_env(monkeypatch)
    raw_agtype_row = {
        "result": (
            '{"id": 844424930131969, "label": "Gene", '
            '"properties": {"name": "TP53", "id": "NCBIGene:7157"}}::vertex'
        )
    }
    response = _FakeResponse(200, {"rows": [raw_agtype_row], "total_available": 1})
    monkeypatch.setattr(t, "_post", lambda **kwargs: response)

    rows, total = t.execute_cypher_over_http(
        cypher="MATCH (g:Gene {id: $seed}) RETURN g",
        params={"seed": "NCBIGene:7157"},
        row_limit=25,
        timeout_s=30.0,
        as_clause="(result agtype)",
    )

    assert total == 1
    assert rows == [raw_agtype_row]
    assert rows[0]["result"] == raw_agtype_row["result"], (
        "the raw agtype wire text was altered in transit; it must pass "
        "through byte-identical for cypher_provenance to parse downstream"
    )


def test_multiple_rows_and_a_scalar_column_both_pass_through_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import system_03_search_agent.tools.graph_http_transport as t

    _set_transport_env(monkeypatch)
    rows_in = [
        {"result": "\"BRCA1 DNA repair associated\""},
        {"result": '{"id": 1, "label": "Disease", "properties": {}}::vertex'},
    ]
    response = _FakeResponse(200, {"rows": rows_in, "total_available": 2})
    monkeypatch.setattr(t, "_post", lambda **kwargs: response)

    rows, total = t.execute_cypher_over_http(
        cypher="MATCH (g:Gene {id: $seed}) RETURN g.name",
        params={"seed": "NCBIGene:672"},
        row_limit=25,
        timeout_s=30.0,
        as_clause="(result agtype)",
    )

    assert total == 2
    assert rows == rows_in
