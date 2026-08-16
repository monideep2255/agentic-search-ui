"""Unit coverage for `adapters/cli/client.py`'s `CliClient`.

Direct, fixture-free coverage over `httpx.MockTransport`, the same
accepted pattern `test_phase_4_2_premise.py`'s own `TestCreateIsNeverRetried`
uses for a property that is small, pure, and awkward to force through the
full app (that file's own docstring names this precedent). This file pins
`CliClient`'s contract in isolation: request shape (headers, body, method,
path), the mixed error-body parsing, the typed exception per status code,
the two citations-export disclosure headers, and the SSE decode path,
independent of a running server or a database. The premise gate is the
end-to-end proof this module actually satisfies the phase's done-when;
this file is the unit-level proof of the module's own stated contract.

Depends on:
    - system_03_search_agent.adapters.cli.client (CliClient and every
      exported error type)
    - system_03_search_agent.contracts.events (Event, CitationPayload)

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations

import json
from typing import NamedTuple

import httpx
import pytest

from system_03_search_agent.adapters.cli.client import (
    AuthExpiredError,
    CliApiError,
    CliClient,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitedError,
    _parse_error_detail,
    _parse_retry_after,
)


# A local, structurally-identical stand-in for `credentials.Credentials`
# (T-4.2-02, a sibling module built in parallel this phase and not
# guaranteed to exist yet in every environment this file runs in).
# `client.py` only ever reads `.access_token` off whatever it is given
# (see that module's own docstring on why the real type is a
# TYPE_CHECKING-only import), so a duck-typed stand-in is a faithful unit
# double, not a weaker one.
class _FakeCredentials(NamedTuple):
    base_url: str
    access_token: str | None
    refresh_token: str


_CREDS = _FakeCredentials(base_url="http://test", access_token="tok-abc", refresh_token="r1")


def _client_with_handler(handler) -> CliClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    return CliClient(http, _CREDS)


def _citation_body(citation_id: str = "c1") -> dict:
    return {
        "citation_id": citation_id,
        "display_index": 1,
        "source": "ncbi_gene",
        "source_id": "672",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "layer": "layer_1_graph",
        "field": "symbol",
        "claim_text": "BRCA1 is a protein-coding gene.",
        "evidence_kind": "direct",
        "assertion_confidence": "high",
        "population_ancestry_context": None,
        "license": "public-domain",
        "snapshot_date": None,
        "entity_name": None,
    }


# ---------------------------------------------------------------------------
# create_run
# ---------------------------------------------------------------------------


class TestCreateRun:
    @pytest.mark.asyncio
    async def test_sends_the_right_method_path_body_and_auth_header(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            seen["authorization"] = request.headers.get("authorization")
            seen["body"] = json.loads(request.content)
            return httpx.Response(202, json={"run_id": "run-1", "persona_name": "Persona"})

        client = _client_with_handler(handler)
        run_id, persona_name = await client.create_run(
            text="What gene is BRCA1?", session_id="s1", audience_depth="researcher"
        )

        assert run_id == "run-1"
        assert persona_name == "Persona"
        assert seen["method"] == "POST"
        assert seen["path"] == "/v1/query"
        assert seen["authorization"] == "Bearer tok-abc"
        assert seen["body"] == {
            "text": "What gene is BRCA1?",
            "session_id": "s1",
            "audience_depth": "researcher",
        }

    @pytest.mark.asyncio
    async def test_a_bare_string_401_body_raises_auth_expired_with_the_servers_message(
        self,
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": "invalid or expired credentials"})

        client = _client_with_handler(handler)
        with pytest.raises(AuthExpiredError) as exc_info:
            await client.create_run(text="q", session_id="s1", audience_depth="researcher")

        assert exc_info.value.status_code == 401
        assert exc_info.value.reason is None
        assert exc_info.value.message == "invalid or expired credentials"

    @pytest.mark.asyncio
    async def test_a_structured_429_body_raises_rate_limited_with_reason_message_and_retry_after(
        self,
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                json={
                    "detail": {
                        "reason": "concurrent_run_cap_exceeded",
                        "message": "wait for an existing run to finish, or stop one",
                    }
                },
                headers={"Retry-After": "30"},
            )

        client = _client_with_handler(handler)
        with pytest.raises(RateLimitedError) as exc_info:
            await client.create_run(text="q", session_id="s1", audience_depth="researcher")

        assert exc_info.value.status_code == 429
        assert exc_info.value.reason == "concurrent_run_cap_exceeded"
        assert "wait" in exc_info.value.message
        assert exc_info.value.retry_after_s == 30

    @pytest.mark.asyncio
    async def test_a_network_error_propagates_uncaught_with_exactly_one_attempt(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("simulated connection failure", request=request)

        client = _client_with_handler(handler)
        with pytest.raises(httpx.ConnectError):
            await client.create_run(text="q", session_id="s1", audience_depth="researcher")

        # Mutation: wrap create_run in any retry-on-transient-failure
        # helper -> call_count becomes 2 or more.
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_a_404_with_no_json_body_still_produces_a_message_not_a_crash(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, content=b"not json at all")

        client = _client_with_handler(handler)
        with pytest.raises(NotFoundError) as exc_info:
            await client.create_run(text="q", session_id="s1", audience_depth="researcher")

        assert exc_info.value.message.strip() != ""

    @pytest.mark.asyncio
    async def test_an_unmapped_status_code_raises_the_generic_cli_api_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "internal server error"})

        client = _client_with_handler(handler)
        with pytest.raises(CliApiError) as exc_info:
            await client.create_run(text="q", session_id="s1", audience_depth="researcher")

        assert type(exc_info.value) is CliApiError
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


class TestStop:
    @pytest.mark.asyncio
    async def test_a_successful_stop_returns_the_servers_stopped_field(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/v1/query/run-1/stop"
            return httpx.Response(200, json={"stopped": True})

        client = _client_with_handler(handler)
        assert await client.stop("run-1") is True

    @pytest.mark.asyncio
    async def test_stopping_someone_elses_run_raises_forbidden(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"detail": "you do not own this run"})

        client = _client_with_handler(handler)
        with pytest.raises(ForbiddenError) as exc_info:
            await client.stop("run-1")
        assert exc_info.value.message == "you do not own this run"


# ---------------------------------------------------------------------------
# fetch_citations
# ---------------------------------------------------------------------------


class TestFetchCitations:
    @pytest.mark.asyncio
    async def test_a_completed_run_returns_typed_citations_with_both_flags_false(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/query/run-1/citations"
            return httpx.Response(200, json=[_citation_body()])

        client = _client_with_handler(handler)
        citations = await client.fetch_citations("run-1")

        assert len(citations) == 1
        assert citations[0].citation_id == "c1"
        assert citations[0].source_url == "https://www.ncbi.nlm.nih.gov/gene/672"
        assert client.citations_run_cancelled is False
        assert client.citations_export_truncated is False

    @pytest.mark.asyncio
    async def test_the_two_disclosure_headers_are_surfaced_as_attributes_when_present(
        self,
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[_citation_body()],
                headers={
                    "X-Run-Cancelled": "true",
                    "X-Citations-Export-Truncated": "true",
                },
            )

        client = _client_with_handler(handler)
        await client.fetch_citations("run-1")

        assert client.citations_run_cancelled is True
        assert client.citations_export_truncated is True

    @pytest.mark.asyncio
    async def test_a_run_not_yet_terminal_raises_conflict(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                409, json={"detail": "run has not reached a terminal state yet"}
            )

        client = _client_with_handler(handler)
        with pytest.raises(ConflictError) as exc_info:
            await client.fetch_citations("run-1")
        assert "terminal state" in exc_info.value.message


# ---------------------------------------------------------------------------
# stream_events
# ---------------------------------------------------------------------------


def _sse_body(*frames: tuple[str, dict, str]) -> bytes:
    """Build a raw SSE body from (event_type, payload_dict, seq_id)
    triples, with a keepalive comment inserted between each frame,
    mirroring the shape sse_starlette actually writes and the CLI must
    tolerate."""
    out = ""
    for event_type, payload, seq_id in frames:
        out += f"event: {event_type}\n"
        out += f"data: {json.dumps(payload)}\n"
        out += f"id: {seq_id}\n\n"
        out += ": ping - keepalive\n\n"
    return out.encode()


def _event_payload(event_type: str, seq: int, payload: dict) -> dict:
    return {
        "type": event_type,
        "version": "v1",
        "trace_id": "t1",
        "seq": seq,
        "ts": "2026-08-16T00:00:00Z",
        "payload": payload,
    }


class TestStreamEvents:
    @pytest.mark.asyncio
    async def test_decodes_the_full_envelope_and_skips_keepalive_comments(self) -> None:
        body = _sse_body(
            ("guard", _event_payload("guard", 0, {"passed": True, "category": "ok", "reason": None}), "0"),
            (
                "done",
                _event_payload(
                    "done",
                    2,
                    {
                        "total_cost_usd": 0.0,
                        "total_tool_calls": 0,
                        "elapsed_ms": 1,
                        "trust_outcome": "answer",
                    },
                ),
                "2",
            ),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        assert [e.type for e in events] == ["guard", "done"]
        assert [e.seq for e in events] == [0, 2]

    @pytest.mark.asyncio
    async def test_sends_last_event_id_as_a_request_header_never_a_query_param(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["header"] = request.headers.get("last-event-id")
            seen["query"] = dict(request.url.params)
            return httpx.Response(200, content=b"", headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        async for _event in client.stream_events("run-1", last_event_id="4"):
            pass  # pragma: no cover - empty stream, nothing to iterate

        assert seen["header"] == "4"
        assert seen["query"] == {}

    @pytest.mark.asyncio
    async def test_an_error_status_before_the_stream_opens_raises_before_yielding_anything(
        self,
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"detail": "Last-Event-ID 'garbage' is not a valid seq cursor"},
            )

        client = _client_with_handler(handler)

        async def _collect() -> list:
            return [event async for event in client.stream_events("run-1", last_event_id="garbage")]

        with pytest.raises(CliApiError) as exc_info:
            await _collect()
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# _parse_error_detail / _parse_retry_after (module-internal helpers, unit
# coverage in their own right since every public method routes through
# them and their edge cases are otherwise only indirectly exercised above)
# ---------------------------------------------------------------------------


class TestParseErrorDetail:
    def test_a_detail_that_is_neither_dict_nor_string_falls_back_to_response_text(self) -> None:
        response = httpx.Response(422, json={"detail": ["a", "list", "is", "neither"]})
        reason, message = _parse_error_detail(response)
        assert reason is None
        assert message != ""

    def test_no_detail_key_at_all_falls_back_to_response_text(self) -> None:
        response = httpx.Response(500, json={"something_else": "value"})
        reason, message = _parse_error_detail(response)
        assert reason is None
        assert message != ""

    def test_a_structured_detail_missing_the_message_key_falls_back_to_str_of_the_dict(
        self,
    ) -> None:
        response = httpx.Response(429, json={"detail": {"reason": "x"}})
        reason, message = _parse_error_detail(response)
        assert reason == "x"
        assert "x" in message


class TestParseRetryAfter:
    def test_a_missing_header_returns_none(self) -> None:
        assert _parse_retry_after(None) is None

    def test_a_non_numeric_header_returns_none_rather_than_raising(self) -> None:
        assert _parse_retry_after("not-a-number") is None

    def test_a_valid_integer_header_parses(self) -> None:
        assert _parse_retry_after("42") == 42
