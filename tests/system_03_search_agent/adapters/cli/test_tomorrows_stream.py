"""An `s3` installed today keeps answering after the server adds to the stream.

Build phase 8.10, T-8.10-02 (`tracker/phase_8.10.md`). The event contract is
additive within v1 (`system-design-patterns` pattern 10): the server may add
an optional field to a payload, a key to the envelope, or a whole new event
type. The integrations audit of 2026-09-26 measured that every `s3` built
before 2026-09-25 failed every answer at its last frame, because the client
validated received frames against the server's own `extra="forbid"` models.

These tests drive the REAL `CliClient` and the REAL `Renderer` together over
an in-process transport, so "the answer still prints" is checked the way a
person sees it: answer text and references on stdout, and exit code 0.

What this file covers:
    - A frame of every kind an answer needs, each carrying a field this build
      does not know, at the envelope, the payload and a nested model.
    - A frame of a type this build does not know: skipped and counted.
    - The safety half: a known field with a wrong value still ends the run
      with an error, since dropping keys must never repair a real defect.
    - The same leniency on `fetch_citations`.

What it does not cover: a new VALUE of a closed enum in a known field. That
frame still fails, by design, and `client.py`'s T-8.10-02 comment says why.
"""

from __future__ import annotations

import io
import json

import httpx
import pytest

from system_03_search_agent.adapters.cli import client as client_module
from system_03_search_agent.adapters.cli.client import CliClient
from system_03_search_agent.adapters.cli.credentials import Credentials
from system_03_search_agent.adapters.cli.render import Renderer

_CREDS = Credentials(base_url="http://test", access_token="a", refresh_token="r")

_ANSWER_TEXT = "BRCA1 is associated with familial breast cancer [1]."


def _envelope(event_type: str, seq: int, payload: dict, **extra_envelope_keys: object) -> dict:
    return {
        "type": event_type,
        "version": "v1",
        "trace_id": "t1",
        "seq": seq,
        "ts": "2026-09-26T00:00:00Z",
        "payload": payload,
        **extra_envelope_keys,
    }


def _citation(**extra: object) -> dict:
    return {
        "citation_id": "c1",
        "display_index": 1,
        "source": "ncbi_gene",
        "source_id": "672",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
        "layer": "layer_1_graph",
        "field": "symbol",
        "claim_text": "BRCA1 is a protein-coding gene.",
        "evidence_kind": "curated",
        "assertion_confidence": "high",
        "license": "public domain",
        **extra,
    }


def _tomorrows_frames() -> list[dict]:
    """One answer as a server one release ahead of this build would send it."""
    return [
        _envelope("guard", 0, {"passed": True, "category": "ok", "reason": None}),
        _envelope(
            "think",
            1,
            {
                "narrative": "looking up BRCA1",
                "query_class": "lookup",
                "resolved_entities": [
                    {
                        "text": "BRCA1",
                        "curie": "NCBIGene:672",
                        "confidence": 1.0,
                        "a_future_entity_field": "nested and unknown",
                    }
                ],
                "a_future_think_field": {"anything": [1, 2, 3]},
            },
        ),
        _envelope(
            "a_future_event_type_this_build_has_not_been_taught",
            2,
            {"whatever": True},
        ),
        _envelope("step", 3, {"step": "write", "status": "started", "a_future_step_field": 1}),
        _envelope(
            "token",
            4,
            {"text": _ANSWER_TEXT, "marker_ids": ["c1"], "a_future_token_field": "x"},
            a_future_envelope_key="the envelope grew too",
        ),
        _envelope("citation", 5, _citation(a_future_citation_field="y")),
        _envelope(
            "trust_signal",
            6,
            {
                "outcome": "answer",
                "risk_tier": "low",
                "grounded": True,
                "scope": "answer",
                "a_future_trust_field": 0.5,
            },
        ),
        _envelope(
            "done",
            7,
            {
                "total_cost_usd": 0.0,
                "total_tool_calls": 1,
                "elapsed_ms": 10,
                "trust_outcome": "answer",
                "decisions": [
                    {
                        "name": "guardrail.relevancy",
                        "options": ["relevant", "off_topic"],
                        "chosen": "relevant",
                        "decided_by": "jev",
                        "a_future_decision_field": "nested in a list",
                    }
                ],
                "a_future_done_field": {"nested": "object"},
            },
        ),
    ]


def _sse_body(frames: list[dict]) -> bytes:
    return "".join(
        f"event: {frame['type']}\ndata: {json.dumps(frame)}\nid: {frame['seq']}\n\n"
        for frame in frames
    ).encode()


def _client_serving(body: bytes) -> CliClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
    return CliClient(http, _CREDS)


async def _render(frames: list[dict]) -> tuple[CliClient, list, str, str, int]:
    client = _client_serving(_sse_body(frames))
    out, err = io.StringIO(), io.StringIO()
    renderer = Renderer(out, err, operator=False)
    events = []
    async for event in client.stream_events("run-1"):
        events.append(event)
        renderer.handle(event)
    exit_code = renderer.finish()
    return client, events, out.getvalue(), err.getvalue(), exit_code


class TestAnInstalledClientReadsTomorrowsStream:
    @pytest.mark.asyncio
    async def test_the_answer_still_prints_and_the_unknown_frame_is_skipped(self) -> None:
        # Mutation: make `_decode_ignoring_unknown_fields` return None (the
        # pre-8.10 behaviour) -> the think frame becomes a fatal decode error,
        # the stream ends there, no answer prints and the exit code is 1.
        client, events, out, err, exit_code = await _render(_tomorrows_frames())

        assert exit_code == 0, err
        assert _ANSWER_TEXT in out
        assert "[answer]" in out
        assert "References:" in out
        assert "https://www.ncbi.nlm.nih.gov/gene/672" in out
        assert "could not decode" not in err
        assert [e.type for e in events] == [
            "guard", "think", "step", "token", "citation", "trust_signal", "done"
        ]
        assert client.stream_skipped_frame_count == 1
        assert client.stream_truncated is False

    @pytest.mark.asyncio
    async def test_unknown_keys_never_reach_the_renderer(self) -> None:
        """Dropped, not passed through: an unknown key is never displayed."""
        _, events, _, _, _ = await _render(_tomorrows_frames())
        dumped = json.dumps([e.model_dump(mode="json") for e in events])
        assert "a_future" not in dumped

    @pytest.mark.asyncio
    async def test_todays_frames_still_decode_exactly_as_before(self) -> None:
        """No unknown key anywhere: the strict path is taken and nothing is
        dropped, so a frame from today's server is byte-for-byte what it was."""
        frames = [
            _envelope("token", 0, {"text": _ANSWER_TEXT, "marker_ids": ["c1"]}),
            _envelope(
                "done",
                1,
                {
                    "total_cost_usd": 0.0,
                    "total_tool_calls": 0,
                    "elapsed_ms": 1,
                    "trust_outcome": "answer",
                },
            ),
        ]
        _, events, _, _, _ = await _render(frames)
        assert [e.payload for e in events] == [f["payload"] for f in frames]


class TestDroppingKeysNeverRepairsARealDefect:
    @pytest.mark.asyncio
    async def test_a_known_field_with_a_wrong_value_still_ends_the_run(self) -> None:
        """An unknown key beside a WRONG value in a known field: dropping the
        key must not make the frame pass. Mutation: validate the stripped
        envelope with `extra="ignore"` and no strict re-check, or accept the
        frame when anything was dropped -> this becomes a clean answer."""
        frames = _tomorrows_frames()
        trust_signal = frames[6]
        assert trust_signal["type"] == "trust_signal"
        trust_signal["payload"]["outcome"] = "a_value_no_build_knows"
        _, events, out, _err, exit_code = await _render(frames)

        assert exit_code == 1
        assert events[-1].type == "error"
        assert events[-1].payload["source"] == "cli_stream_decode"
        assert [e.type for e in events][-2:] == ["citation", "error"]
        assert "[answer]" not in out

    @pytest.mark.asyncio
    async def test_a_bound_on_a_known_field_still_holds(self) -> None:
        """`token.text` is capped at 1000 characters by the contract. An
        over-long value beside an unknown key must still be refused."""
        frames = [
            _envelope("token", 0, {"text": "x" * 1001, "marker_ids": [], "new_field": 1}),
        ]
        _, events, _, _, exit_code = await _render(frames)
        assert exit_code == 1
        assert [e.type for e in events] == ["error"]

    def test_an_unknown_type_is_left_to_the_benign_skip_path(self) -> None:
        """The lenient decoder only ever handles KNOWN types; an unknown one is
        the existing skip path's call, never silently turned into an event."""
        frame = json.dumps(_envelope("brand_new_type", 0, {"a": 1}, extra_key=1))
        assert client_module._decode_ignoring_unknown_fields(frame) is None

    def test_non_json_is_never_decoded_leniently(self) -> None:
        assert client_module._decode_ignoring_unknown_fields("{not json") is None


class TestFetchCitationsReadsTomorrowsCitation:
    @pytest.mark.asyncio
    async def test_a_citation_with_a_new_field_is_read(self) -> None:
        # Mutation: revert to `CitationPayload.model_validate(item)` -> this
        # raises a pydantic ValidationError instead of returning the citation.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[_citation(a_future_citation_field="z")])

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
        citations = await CliClient(http, _CREDS).fetch_citations("run-1")
        assert [c.source_url for c in citations] == ["https://www.ncbi.nlm.nih.gov/gene/672"]


class TestCreateRunWithNoRunId:
    @pytest.mark.asyncio
    async def test_a_missing_run_id_is_a_typed_error_not_a_type_error(self) -> None:
        """Found while building 8.10: the raise passed one argument to a
        three-argument constructor, so the person saw "unexpected error
        (TypeError)" instead of the actionable message."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(202, json={"persona_name": "Franklin"})

        http = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")
        with pytest.raises(client_module.CliApiError) as caught:
            await CliClient(http, _CREDS).create_run("q", "s1", None)
        assert "no run_id" in caught.value.message
        assert caught.value.status_code == 202
