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

import asyncio
import json
from collections.abc import AsyncIterator
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
    _ChunkSafeLineSplitter,
    _parse_error_detail,
    _parse_retry_after,
)
from system_03_search_agent.adapters.cli.sse import SseFrameTooLargeError
from system_03_search_agent.contracts.events import Event


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

    @pytest.mark.asyncio
    async def test_a_204_success_status_raises_actionable_error_rather_than_crashing(
        self,
    ) -> None:
        """F-4.2-A-24: `_raise_for_status` only checks `>= 400`, so a 204
        would previously reach `response.json()["run_id"]` unguarded and
        crash on a raw `json.JSONDecodeError`."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(204)

        client = _client_with_handler(handler)
        with pytest.raises(CliApiError) as exc_info:
            await client.create_run(text="q", session_id="s1", audience_depth="researcher")

        assert exc_info.value.message.strip() != ""

    @pytest.mark.asyncio
    async def test_a_302_success_status_raises_actionable_error_rather_than_crashing(
        self,
    ) -> None:
        """F-4.2-A-24: a 3xx the transport did not follow is still `< 400`
        and still has no JSON body to parse."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"Location": "http://test/elsewhere"})

        client = _client_with_handler(handler)
        with pytest.raises(CliApiError) as exc_info:
            await client.create_run(text="q", session_id="s1", audience_depth="researcher")

        assert exc_info.value.message.strip() != ""

    @pytest.mark.asyncio
    async def test_never_follows_a_redirect_even_if_the_injected_client_defaults_to_it(
        self,
    ) -> None:
        """F-4.2-A-29: the "exactly one HTTP request" guarantee must hold
        regardless of the injected `httpx.AsyncClient`'s own
        `follow_redirects` setting, which lives outside this module's
        control. With `follow_redirects=True` on the client and a 302
        from the server, a `create_run` that omitted its own explicit
        `follow_redirects=False` would let the transport follow the
        redirect and issue a second create, spending a second allowance
        slot against a run that may already exist.
        """
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(302, headers={"Location": "http://test/v1/query"})
            return httpx.Response(202, json={"run_id": "run-1", "persona_name": "Persona"})

        http = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://test",
            follow_redirects=True,
        )
        client = CliClient(http, _CREDS)

        with pytest.raises(CliApiError):
            await client.create_run(text="q", session_id="s1", audience_depth="researcher")

        # Mutation: drop `follow_redirects=False` from create_run's own
        # POST call -> call_count becomes 2, the redirect gets followed.
        assert call_count == 1


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

    @pytest.mark.asyncio
    async def test_a_204_success_status_raises_actionable_error_rather_than_crashing(
        self,
    ) -> None:
        """F-4.2-A-24: previously `response.json()["stopped"]` would crash
        raw on a 204's absent body."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(204)

        client = _client_with_handler(handler)
        with pytest.raises(CliApiError) as exc_info:
            await client.stop("run-1")
        assert exc_info.value.message.strip() != ""


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

    @pytest.mark.asyncio
    async def test_a_303_success_status_with_no_json_body_raises_actionable_error(
        self,
    ) -> None:
        """F-4.2-A-24: a 303 the transport did not follow is still `< 400`
        and still has no JSON body to parse."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(303, headers={"Location": "http://test/elsewhere"})

        client = _client_with_handler(handler)
        with pytest.raises(CliApiError) as exc_info:
            await client.fetch_citations("run-1")
        assert exc_info.value.message.strip() != ""


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


# ---------------------------------------------------------------------------
# _ChunkSafeLineSplitter, direct unit coverage (F-4.2-RR-04). TestStreamEvents
# below exercises it only through a full SSE round trip; these pin its own
# byte-level recovery contract in isolation.
# ---------------------------------------------------------------------------


class TestChunkSafeLineSplitter:
    def test_an_invalid_byte_mid_stream_is_replaced_not_raised(self) -> None:
        splitter = _ChunkSafeLineSplitter()
        lines = splitter.feed(b"before\xffafter\n")
        # Mutation: revert `feed` to the unguarded
        # `self._buffer += self._decoder.decode(raw_bytes)` -> this line
        # raises `UnicodeDecodeError` instead of returning.
        assert lines == ["before�after"]
        assert splitter.replaced_invalid_utf8 is True
        assert splitter.truncated_utf8 is False

    def test_a_carried_over_incomplete_prefix_is_not_lost_on_recovery(self) -> None:
        """`abc\\xe2` leaves a legitimate, still-incomplete 2-byte lead
        byte buffered inside the incremental decoder (no output for it
        yet). The next `feed()` supplies an invalid continuation byte
        (`0x28`, ASCII `(`, never a valid UTF-8 continuation). Recovery
        must decode `exc.object` (the carried-over `\\xe2` PLUS the new
        bytes), not `raw_bytes` alone, or the `abc` prefix's trailing
        buffered byte would silently vanish from the output entirely
        rather than surface as a visible U+FFFD.
        """
        splitter = _ChunkSafeLineSplitter()
        assert splitter.feed(b"abc\xe2") == []
        lines = splitter.feed(b"\x28def\n")
        # Mutation: recover from `raw_bytes` (this call's own
        # `b"\x28def\n"`) instead of `exc.object` -> the leading `\xe2`
        # byte carried over from the previous feed() is silently dropped,
        # producing "abc(def" (7 chars) instead of "abc�(def" (8
        # chars), with no visible sign the byte was ever there.
        assert lines == ["abc�(def"]
        assert splitter.replaced_invalid_utf8 is True

    def test_a_genuinely_incomplete_trailing_sequence_at_close_is_still_truncated_not_replaced(
        self,
    ) -> None:
        """The pre-existing distinction this fix must not blur: bytes
        that are merely INCOMPLETE at the connection's own end (never
        invalid, just cut short before the sequence's continuation
        bytes arrived) are `truncated_utf8`, never `replaced_invalid_utf8`.
        `feed()`'s own recovery path is never involved here since nothing
        raises until `close()`'s `final=True` finalize call.
        """
        splitter = _ChunkSafeLineSplitter()
        assert splitter.feed(b"trailing \xe2\x82") == []
        lines = splitter.close()
        assert lines == ["trailing "]
        assert splitter.truncated_utf8 is True
        assert splitter.replaced_invalid_utf8 is False


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

    # -----------------------------------------------------------------
    # F-4.2-A-02: U+2028, U+2029, U+0085, and a chunk-split multi-byte
    # character must never corrupt the frame.
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.parametrize("separator", [" ", " ", ""])
    async def test_a_raw_line_or_paragraph_separator_survives_in_a_token_and_a_citation(
        self, separator: str
    ) -> None:
        """`httpx.Response.aiter_lines()`'s own `LineDecoder` splits on
        U+2028/U+2029/U+0085 in addition to LF/CR/CRLF, so a `data:` line
        carrying one of these ordinary biomedical-text characters used to
        be cut in half mid-JSON and lose the whole answer. The server's
        real serializer (`pydantic`'s `model_dump_json`) emits these raw,
        not escaped, so the test body is built the same way
        (`ensure_ascii=False`), not with `json.dumps`'s ASCII-escaping
        default.
        """
        token_text = f"line one{separator}line two"
        citation = _citation_body()
        citation["claim_text"] = f"BRCA1{separator}is a protein-coding gene."
        token_envelope = _event_payload("token", 0, {"text": token_text, "marker_ids": []})
        citation_envelope = _event_payload("citation", 1, citation)
        body = (
            "event: token\n"
            f"data: {json.dumps(token_envelope, ensure_ascii=False)}\n"
            "id: 0\n\n"
            "event: citation\n"
            f"data: {json.dumps(citation_envelope, ensure_ascii=False)}\n"
            "id: 1\n\n"
        ).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        assert [e.type for e in events] == ["token", "citation"]
        assert events[0].payload["text"] == token_text
        assert events[1].payload["claim_text"] == citation["claim_text"]

    @pytest.mark.asyncio
    async def test_a_multi_byte_utf8_character_split_across_a_chunk_boundary_survives(
        self,
    ) -> None:
        """A 4-byte UTF-8 character (U+1F9EC) whose bytes are split
        across two separate network chunks must still decode correctly:
        `_ChunkSafeLineSplitter` buffers the incomplete trailing bytes in
        its incremental decoder rather than either raising or silently
        corrupting the character.
        """
        emoji = "\U0001f9ec"
        token_text = f"BRCA1 {emoji} variant"
        envelope = _event_payload("token", 0, {"text": token_text, "marker_ids": []})
        frame = f"event: token\ndata: {json.dumps(envelope, ensure_ascii=False)}\nid: 0\n\n"
        frame_bytes = frame.encode("utf-8")

        emoji_bytes = emoji.encode("utf-8")
        assert len(emoji_bytes) == 4
        split_index = frame_bytes.index(emoji_bytes) + 2  # land inside the 4-byte sequence
        chunk_one, chunk_two = frame_bytes[:split_index], frame_bytes[split_index:]
        assert chunk_one and chunk_two

        async def gen() -> AsyncIterator[bytes]:
            yield chunk_one
            yield chunk_two

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=gen(), headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        assert len(events) == 1
        assert events[0].payload["text"] == token_text

    # -----------------------------------------------------------------
    # F-4.2-RR-04 (round-3 fix): a byte that is never valid UTF-8 at all,
    # arriving mid-stream, must not raise out of `_ChunkSafeLineSplitter`.
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_an_invalid_utf8_byte_mid_stream_does_not_crash_the_reader(
        self,
    ) -> None:
        """A lone `0xFF` (never a valid UTF-8 lead byte, under any
        continuation) landing inside an otherwise well-formed frame used
        to let `UnicodeDecodeError` escape uncaught from `feed()`, all the
        way to `main.py`'s broad catch-all, which reported a generic "the
        event stream ended unexpectedly" and abandoned a connection that
        was very likely still alive. It must instead survive locally: the
        bad byte is replaced with U+FFFD and the frame still decodes into
        a dispatched SSE tuple, never a raised `UnicodeDecodeError`.

        F-4.2-D-02 (round-4 fix): this test's assertions changed from the
        round-3 shape. The corrupted `data:` body (`bad byte -> <FFFD>
        <- still here`) is not valid JSON, so it offers no positive proof
        of being a benign, forward-compatible frame
        (`_payload_declares_unknown_type` returns `False` for it) no
        matter what its SSE `event:` field says; the round-3 fix used to
        key benign-vs-fatal on `event:` alone (`mystery`, here, is not a
        member of `_KNOWN_EVENT_TYPES`) and silently skipped this exact
        corrupted, fatal-shaped payload, letting the well-formed `done`
        behind it report a false clean success. That is F-4.2-D-02's own
        finding, reproduced directly by this byte-level fixture rather
        than a synthetic one. This test's point, that the byte-level
        recovery never crashes the reader, still holds: the corrupted
        frame reaches `_decode_stream_event` and is turned into a
        rendered, fatal `error` Event instead of an uncaught exception.
        """
        # The invalid byte sits inside an event whose SSE `event:` field
        # is unrecognized (`mystery`), which no longer matters to the
        # classification: `data:` alone decides, and this `data:` is not
        # valid JSON.
        body = b"event: mystery\ndata: bad byte -> \xff <- still here\nid: 0\n\n"

        async def gen() -> AsyncIterator[bytes]:
            yield body

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=gen(), headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        # Mutation: revert `_ChunkSafeLineSplitter.feed` to the
        # unguarded `self._buffer += self._decoder.decode(raw_bytes)`
        # with no try/except -> this raises `UnicodeDecodeError` straight
        # out of `stream_events`, so the `async for` below never
        # completes normally.
        events = [event async for event in client.stream_events("run-1")]

        # Mutation: revert `_decode_stream_event` to key on
        # `event_type in _KNOWN_EVENT_TYPES` instead of
        # `_payload_declares_unknown_type(data)` -> `"mystery"` is not a
        # known type, so this becomes a silent, counted skip and never
        # surfaces as an error at all.
        assert [e.type for e in events] == ["error"]
        assert events[0].payload["fatal"] is True
        assert events[0].payload["error_class"] == "transient"
        assert events[0].payload["source"] == "cli_stream_decode"
        assert client.stream_skipped_frame_count == 0
        assert client.stream_truncated is False

    # -----------------------------------------------------------------
    # F-4.2-A-10: an unknown or malformed frame is skipped, counted, and
    # never aborts the run over a complete, otherwise-valid answer.
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_an_unrecognized_event_type_is_skipped_and_counted_not_raised(
        self,
    ) -> None:
        """Unaffected by the F-4.2-D-02 round-4 fix: `unknown_envelope`
        below is well-formed JSON carrying its own `"type"` key set to a
        genuinely unrecognized value, which is exactly the positive proof
        `_payload_declares_unknown_type` looks for directly in `data:`.
        This is the real rule-10 shape (a well-formed, forward-compatible
        new event type), not the malformed-body shape the sibling tests
        around this one exercise.
        """
        guard_envelope = _event_payload(
            "guard", 0, {"passed": True, "category": "ok", "reason": None}
        )
        unknown_envelope = {
            "type": "a_future_event_type_this_build_has_not_been_taught",
            "version": "v1",
            "trace_id": "t1",
            "seq": 1,
            "ts": "2026-08-16T00:00:00Z",
            "payload": {},
        }
        done_envelope = _event_payload(
            "done",
            2,
            {
                "total_cost_usd": 0.0,
                "total_tool_calls": 0,
                "elapsed_ms": 1,
                "trust_outcome": "answer",
            },
        )
        body = (
            f"event: guard\ndata: {json.dumps(guard_envelope)}\nid: 0\n\n"
            f"event: mystery\ndata: {json.dumps(unknown_envelope)}\nid: 1\n\n"
            f"event: done\ndata: {json.dumps(done_envelope)}\nid: 2\n\n"
        ).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        # Mutation: catch nothing around Event.model_validate_json ->
        # this raises pydantic.ValidationError instead of skipping, and
        # the "done" below (a correct, complete answer) is never reached.
        assert [e.type for e in events] == ["guard", "done"]
        assert client.stream_skipped_frame_count == 1
        assert client.stream_truncated is False

    @pytest.mark.asyncio
    async def test_a_non_json_data_line_is_never_benign_skipped_regardless_of_event_field(
        self,
    ) -> None:
        """F-4.2-D-02 (round-4 fix): renamed and re-asserted from the
        round-3 shape, which was itself the vulnerability. A non-JSON
        `data:` body offers no positive proof of being a well-formed,
        forward-compatible frame no matter what its SSE `event:` field
        claims (`event: mystery` here is not a member of
        `_KNOWN_EVENT_TYPES`, exactly the shape the round-3 fix treated
        as benign-skippable): `event:` is set by the same sender as
        `data:` and can diverge from it, so a benign-looking `event:`
        value next to garbage `data:` is not evidence, it is exactly the
        composition F-4.2-D-02 exploited to hide a fatal frame behind an
        unrecognized-looking label. `data:` alone must now offer positive
        proof, and `not json at all` cannot. See
        `test_a_non_json_data_line_under_a_known_type_is_not_silently_skipped`
        just below for the sibling F-4.2-RR-03 case (a KNOWN `event:`
        type over the same shape of malformed body), which already
        asserted this and is unchanged by this fix.
        """
        done_envelope = _event_payload(
            "done",
            1,
            {
                "total_cost_usd": 0.0,
                "total_tool_calls": 0,
                "elapsed_ms": 1,
                "trust_outcome": "answer",
            },
        )
        body = (
            "event: mystery\ndata: not json at all\nid: 0\n\n"
            f"event: done\ndata: {json.dumps(done_envelope)}\nid: 1\n\n"
        ).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        # Mutation: revert `_decode_stream_event` to key on
        # `event_type in _KNOWN_EVENT_TYPES` instead of
        # `_payload_declares_unknown_type(data)` -> `"mystery"` is not a
        # known type, so the malformed frame is silently skipped and
        # counted, the `done` behind it is reached, and
        # `[e.type for e in events] == ["done"]` with
        # `stream_skipped_frame_count == 1`. That is the exact F-4.2-D-02
        # regression this test exists to catch.
        assert [e.type for e in events] == ["error"]
        assert events[0].payload["fatal"] is True
        assert events[0].payload["error_class"] == "transient"
        assert events[0].payload["source"] == "cli_stream_decode"
        assert client.stream_skipped_frame_count == 0
        assert client.stream_truncated is False

    # -----------------------------------------------------------------
    # F-4.2-RR-03 (round-3 fix): a frame whose SSE `event:` field IS one
    # of the eleven known types, but whose envelope or payload fails to
    # decode, is a defect this build recognizes it should have understood,
    # not a forward-compatibility gap. Round 2's own fix (F-4.2-A-10)
    # silently absorbed this case identically to a genuinely unrecognized
    # type, which let a later well-formed `done` report a clean, trusted
    # success over a dropped fatal frame. It must instead render, exit
    # nonzero, and end the stream, the same as any server-sent fatal
    # `error`.
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_a_non_json_data_line_under_a_known_type_is_not_silently_skipped(
        self,
    ) -> None:
        """Reproduces the round-3 verifier's exact regression shape: a
        `token` (an ordinary answer-content frame, exercising that this
        applies to any of the eleven types, not only `error`) streams some
        real content, a malformed but KNOWN-type frame arrives next, and a
        well-formed `done` follows behind it. The malformed frame must end
        the run right there, as a fatal, rendered `error`, so the `done`
        behind it is never reached and the run can never report a clean
        trust outcome over a defect this build already knows it should
        have understood.
        """
        token_envelope = _event_payload(
            "token", 0, {"text": "BRCA1 is a gene.", "marker_ids": []}
        )
        done_envelope = _event_payload(
            "done",
            2,
            {
                "total_cost_usd": 0.0,
                "total_tool_calls": 0,
                "elapsed_ms": 1,
                "trust_outcome": "answer",
            },
        )
        body = (
            f"event: token\ndata: {json.dumps(token_envelope)}\nid: 0\n\n"
            # A KNOWN type (`guard`) with a non-JSON body: this build
            # understands "guard" perfectly well, so this is a defect,
            # never a forward-compatible skip.
            "event: guard\ndata: not json at all\nid: 1\n\n"
            f"event: done\ndata: {json.dumps(done_envelope)}\nid: 2\n\n"
        ).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        # Mutation observed: reverting `_decode_stream_event` to route
        # every ValidationError through the old two-way (skip and count /
        # truncate) split, with no `_KNOWN_EVENT_TYPES` check at all,
        # turns this into `assert [e.type for e in events] == ["token",
        # "done"]` with `stream_skipped_frame_count == 1`: the malformed
        # `guard` frame vanishes, the `done` behind it is reached, and the
        # run reports success. That is the exact regression this test
        # exists to catch; see this file's own report for the command
        # actually run against that mutation.
        assert [e.type for e in events] == ["token", "error"]
        assert events[1].payload["fatal"] is True
        assert events[1].payload["error_class"] == "transient"
        assert events[1].payload["source"] == "cli_stream_decode"
        # Never silently absorbed into the skip counter: this is a
        # rendered, fatal failure, not a benign, forward-compatible skip.
        assert client.stream_skipped_frame_count == 0
        assert client.stream_truncated is False

    @pytest.mark.asyncio
    async def test_a_frame_that_claims_to_be_error_and_fails_to_decode_is_never_dropped(
        self,
    ) -> None:
        """The narrowest instance of the same rule: a frame that literally
        claims `event: error` and fails to decode must never be dropped in
        a way that lets the run report success. No special-casing exists
        for this in `_decode_stream_event`; it falls out of the same
        `_KNOWN_EVENT_TYPES` check `error` is itself a member of.
        """
        body = b"event: error\ndata: {not even valid json\nid: 0\n\n"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        assert [e.type for e in events] == ["error"]
        assert events[0].payload["fatal"] is True

    # -----------------------------------------------------------------
    # F-4.2-D-02 (round-4 fix): the SAME malformed, fatal-shaped frame as
    # the control case directly above (`event: error` intact), reproduced
    # with only its `event:` line varying, to pin the composition defect
    # between the round-3 classifier (F-4.2-RR-03, keyed on `event:`) and
    # the round-3 byte-recovery fix (F-4.2-RR-04, which keeps the stream
    # alive after a corrupted byte instead of ending it, making a
    # corrupted `event:` line a REACHABLE shape rather than a
    # theoretical one). Both varying-`event:` shapes below must still end
    # the run as a fatal, rendered `error`, exactly like the control
    # case, and never as a silent skip that lets the well-formed `done`
    # behind it report a false clean, cited answer.
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_a_fatal_frame_with_no_event_field_is_not_silently_skipped(self) -> None:
        """Case B. `sse.py`'s own parser (`_SseLineAccumulator.feed`)
        leaves `event_type` as `None` when no `event:` line arrives at
        all. Before F-4.2-D-02, `None not in _KNOWN_EVENT_TYPES` was
        `True`, so a frame with no `event:` line was ALWAYS classified as
        an unrecognized, forward-compatible type, regardless of what its
        `data:` body actually contained, including the exact malformed,
        fatal-shaped body the control case above correctly rejects.
        """
        done_envelope = _event_payload(
            "done",
            1,
            {
                "total_cost_usd": 0.0,
                "total_tool_calls": 0,
                "elapsed_ms": 1,
                "trust_outcome": "answer",
            },
        )
        body = (
            # Same malformed `data:` as the control case, `event:` line
            # omitted entirely.
            "data: {not even valid json\nid: 0\n\n"
            f"event: done\ndata: {json.dumps(done_envelope)}\nid: 1\n\n"
        ).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        # Mutation: revert `_decode_stream_event` to key on
        # `event_type in _KNOWN_EVENT_TYPES` (`event_type` is `None`
        # here) instead of `_payload_declares_unknown_type(data)` ->
        # `None not in _KNOWN_EVENT_TYPES` is `True`, so this is
        # classified as benign and silently skipped; the `done` behind it
        # is reached and `[e.type for e in events] == ["done"]` with
        # `stream_skipped_frame_count == 1`. That is the exact F-4.2-D-02
        # case-B regression this test exists to catch.
        assert [e.type for e in events] == ["error"]
        assert events[0].payload["fatal"] is True
        assert events[0].payload["error_class"] == "transient"
        assert events[0].payload["source"] == "cli_stream_decode"
        assert client.stream_skipped_frame_count == 0
        assert client.stream_truncated is False

    @pytest.mark.asyncio
    async def test_a_fatal_frame_with_a_corrupted_event_field_is_not_silently_skipped(
        self,
    ) -> None:
        """Case C. The same malformed frame again, `event:` present but
        its own bytes corrupted by a single invalid UTF-8 byte
        (`\\xff`), the shape F-4.2-RR-04's own "replace the bad byte with
        U+FFFD and keep going" recovery makes reachable rather than
        stream-ending. `_ChunkSafeLineSplitter.feed` substitutes U+FFFD
        for the invalid byte, so the parsed `event:` value becomes
        `"\\ufffd"`, which, exactly like case B's `None`, is not a member
        of `_KNOWN_EVENT_TYPES`. This is the composition finding
        F-4.2-D-02 names directly: F-4.2-RR-04's "keep going" and
        F-4.2-RR-03's `event:`-keyed classifier, each correct on its own
        and shipped in the same commit (`b264091`), combine to silently
        demote a fatal frame to benign whenever the corruption happens to
        land inside the `event:` line's own bytes.
        """
        done_envelope = _event_payload(
            "done",
            1,
            {
                "total_cost_usd": 0.0,
                "total_tool_calls": 0,
                "elapsed_ms": 1,
                "trust_outcome": "answer",
            },
        )
        body = (
            # `event:`'s value is one invalid byte (never valid UTF-8
            # under any continuation), decoded to U+FFFD by
            # `_ChunkSafeLineSplitter`; `data:` is the SAME malformed
            # body as the control case and case B.
            b"event: \xff\ndata: {not even valid json\nid: 0\n\n"
            + f"event: done\ndata: {json.dumps(done_envelope)}\nid: 1\n\n".encode()
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        # Mutation: same as case B's mutation note above. Here
        # `event_type` decodes to `"�"` rather than `None`, but it
        # is equally absent from `_KNOWN_EVENT_TYPES`, so the reverted
        # classifier silently skips this frame the same way and reaches
        # `done` behind it.
        assert [e.type for e in events] == ["error"]
        assert events[0].payload["fatal"] is True
        assert events[0].payload["error_class"] == "transient"
        assert events[0].payload["source"] == "cli_stream_decode"
        assert client.stream_skipped_frame_count == 0
        assert client.stream_truncated is False

    @pytest.mark.asyncio
    async def test_a_stream_that_ends_mid_frame_sets_truncated_not_skipped(self) -> None:
        """A frame that dispatches via the STREAM-END flush (no closing
        blank line) and fails to decode is a genuinely different shape
        from a mid-stream skip: the connection ended while writing this
        event, not "the server sent one bad, complete frame and kept
        going". `stream_truncated` must be set, and
        `stream_skipped_frame_count` must stay at 0, so a caller can
        distinguish the two. This is deliberately preserved, unaffected by
        F-4.2-RR-03: the trailing frame here claims a KNOWN type (`token`)
        and would trigger the new fatal-synthesis path if it were not
        `is_trailing`, but a truncated connection has nothing after it in
        the same stream that could go on to report a false clean success,
        so `_decode_stream_event` never applies the new path when
        `is_trailing=True`.
        """
        guard_envelope = _event_payload(
            "guard", 0, {"passed": True, "category": "ok", "reason": None}
        )
        good = f"event: guard\ndata: {json.dumps(guard_envelope)}\nid: 0\n\n"
        # No closing blank line, and the JSON itself is incomplete: the
        # connection was cut mid-transmission of this event.
        partial = (
            'event: token\ndata: {"type": "token", "version": "v1", '
            '"trace_id": "t1", "seq": 1, "ts": "2026-08-16T00:00:00Z", '
            '"payload": {"text": "incom'
        )
        body = (good + partial).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        assert [e.type for e in events] == ["guard"]
        assert client.stream_skipped_frame_count == 0
        assert client.stream_truncated is True

    # -----------------------------------------------------------------
    # F-4.2-A-12: the stream ends locally on a fatal terminal event, even
    # if the transport holds the connection open past it.
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ends_locally_on_a_fatal_error_even_if_the_connection_stays_open(
        self,
    ) -> None:
        """Reproduces F-4.2-A-12/F-4.2-01 directly: a server that sends a
        terminal fatal `error` and then holds the connection open (never
        closes the body) must not hang this method. The prior shape
        relied on the server closing the response; this proves the
        client itself now ends the generator on the envelope's own
        terminal shape. Bounded by `asyncio.wait_for` so a regression
        fails this test loudly and fast rather than stalling the suite.
        """
        error_envelope = _event_payload(
            "error",
            0,
            {
                "fatal": True,
                "scope": "run",
                "source": "agent_loop",
                "error_class": "cancelled",
                "message": "the run was stopped",
                "retry_after_s": 0,
            },
        )
        frame = f"event: error\ndata: {json.dumps(error_envelope)}\nid: 0\n\n".encode()

        async def gen() -> AsyncIterator[bytes]:
            yield frame
            # Simulate a server holding the connection open indefinitely
            # past the terminal event.
            await asyncio.sleep(3600)

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=gen(), headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)

        async def _collect() -> list[Event]:
            return [event async for event in client.stream_events("run-1")]

        events = await asyncio.wait_for(_collect(), timeout=5.0)

        assert [e.type for e in events] == ["error"]
        assert events[0].payload["error_class"] == "cancelled"

    @pytest.mark.asyncio
    async def test_ends_locally_on_done_even_if_the_connection_stays_open(self) -> None:
        done_envelope = _event_payload(
            "done",
            0,
            {
                "total_cost_usd": 0.0,
                "total_tool_calls": 0,
                "elapsed_ms": 1,
                "trust_outcome": "answer",
            },
        )
        frame = f"event: done\ndata: {json.dumps(done_envelope)}\nid: 0\n\n".encode()

        async def gen() -> AsyncIterator[bytes]:
            yield frame
            await asyncio.sleep(3600)

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=gen(), headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)

        async def _collect() -> list[Event]:
            return [event async for event in client.stream_events("run-1")]

        events = await asyncio.wait_for(_collect(), timeout=5.0)
        assert [e.type for e in events] == ["done"]

    @pytest.mark.asyncio
    async def test_does_not_end_on_a_non_fatal_error_and_keeps_reading(self) -> None:
        """Negative control for F-4.2-A-12: a non-fatal `error`
        (`error_class` "transient" or "recoverable") must NOT stop the
        generator, since the phase premise reserves ending the run for a
        `done` or a FATAL error only.
        """
        transient_envelope = _event_payload(
            "error",
            0,
            {
                "fatal": False,
                "scope": "tool",
                "source": "cypher_query",
                "error_class": "transient",
                "message": "graph query timed out, retrying",
                "retry_after_s": 1,
            },
        )
        done_envelope = _event_payload(
            "done",
            1,
            {
                "total_cost_usd": 0.0,
                "total_tool_calls": 0,
                "elapsed_ms": 1,
                "trust_outcome": "answer",
            },
        )
        body = (
            f"event: error\ndata: {json.dumps(transient_envelope)}\nid: 0\n\n"
            f"event: done\ndata: {json.dumps(done_envelope)}\nid: 1\n\n"
        ).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        events = [event async for event in client.stream_events("run-1")]

        assert [e.type for e in events] == ["error", "done"]

    # -----------------------------------------------------------------
    # F-4.2-A-25: an oversized single event fails fast rather than
    # buffering unbounded.
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_an_oversized_data_field_fails_fast_rather_than_buffering_unbounded(
        self,
    ) -> None:
        huge_value = "x" * 200_000
        body = f"event: token\ndata: {huge_value}\n".encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        client = _client_with_handler(handler)
        with pytest.raises(SseFrameTooLargeError):
            async for _event in client.stream_events("run-1"):
                pass


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
