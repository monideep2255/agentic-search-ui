"""Every surface that joins answer tokens reads the summary above the listing.

Build phase 8.7, T-8.7-03, card 50. The server may send the record listing
before the written summary. Each surface below is fed listing tokens first
and must put the summary first. Each also has an arm with no `placement`
that must read in arrival order, byte for byte as before the field existed.
"""

from __future__ import annotations

import io
import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from system_03_search_agent.adapters.cli.render import JsonRenderer, Renderer
from system_03_search_agent.adapters.graphql import fold as fold_module
from system_03_search_agent.adapters.mcp import server as server_module
from system_03_search_agent.contracts.events import (
    DonePayload,
    Event,
    GuardPayload,
    TokenPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.core.run_registry import RunRegistry

_LISTING_FIRST = [
    ("Record A. ", "listing"),
    ("Record B. ", "listing"),
    ("Summary one. ", "summary"),
    ("Summary two. ", None),
]
_NO_PLACEMENT = [("First. ", None), ("Second. ", None), ("Third. ", None)]


def _token_payload(text: str, placement: str | None) -> TokenPayload:
    if placement is None:
        return TokenPayload(text=text, marker_ids=[])
    return TokenPayload(text=text, marker_ids=[], placement=placement)  # type: ignore[arg-type]


def _event(event_type: str, trace_id: str, seq: int, payload: Any) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


def _items(tokens: list[tuple[str, str | None]]) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = [
        ("guard", GuardPayload(passed=True, category="ok", reason=None))
    ]
    items += [("token", _token_payload(t, p)) for t, p in tokens]
    items.append(
        (
            "done",
            DonePayload(
                total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=1, trust_outcome="answer"
            ),
        )
    )
    return items


def _stream_of(
    tokens: list[tuple[str, str | None]],
) -> Callable[..., AsyncIterator[Event]]:
    items = _items(tokens)

    async def _stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
        for seq, (event_type, payload) in enumerate(items):
            yield _event(event_type, query.trace_id, seq, payload)

    return _stream


def _registry_run(
    monkeypatch: pytest.MonkeyPatch, module: Any, tokens: list[tuple[str, str | None]], surface: str
) -> str:
    registry = RunRegistry()
    monkeypatch.setattr(run_registry_module, "run_streaming", _stream_of(tokens))
    monkeypatch.setattr(module, "default_registry", registry)
    run_id = str(uuid.uuid4())
    registry.create_run(
        Query(text="q", session_id="s-place", trace_id=run_id, user_id="u1"),
        RequestContext(surface=surface),  # type: ignore[arg-type]
        run_id=run_id,
    )
    return run_id


@pytest.mark.asyncio
async def test_mcp_puts_summary_before_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mutation that turns this red: join answer_parts in arrival order.
    run_id = _registry_run(monkeypatch, server_module, _LISTING_FIRST, "mcp")
    result = await server_module._fold_run_to_response(run_id, session_id="s-place")
    assert result.answer == "Summary one. Summary two. Record A. Record B."


@pytest.mark.asyncio
async def test_mcp_without_placement_is_arrival_order(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = _registry_run(monkeypatch, server_module, _NO_PLACEMENT, "mcp")
    result = await server_module._fold_run_to_response(run_id, session_id="s-place")
    assert result.answer == "First. Second. Third."


@pytest.mark.asyncio
async def test_graphql_fold_puts_summary_before_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mutation that turns this red: join acc.answer_parts in arrival order.
    run_id = _registry_run(monkeypatch, fold_module, _LISTING_FIRST, "graphql")
    result = await fold_module.fold_run(run_id, persona_name="Mendel")
    assert result.answer == "Summary one. Summary two. Record A. Record B."


@pytest.mark.asyncio
async def test_graphql_fold_without_placement_is_arrival_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = _registry_run(monkeypatch, fold_module, _NO_PLACEMENT, "graphql")
    result = await fold_module.fold_run(run_id, persona_name="Mendel")
    assert result.answer == "First. Second. Third."


def _feed(renderer: Any, tokens: list[tuple[str, str | None]]) -> None:
    for seq, (event_type, payload) in enumerate(_items(tokens)):
        renderer.handle(_event(event_type, "t-place", seq, payload))


def test_cli_stream_writes_summary_before_listing() -> None:
    # Mutation that turns this red: write listing tokens as they arrive.
    out = io.StringIO()
    renderer = Renderer(out, io.StringIO(), operator=False)
    _feed(renderer, _LISTING_FIRST)
    renderer.finish()
    text = out.getvalue()
    assert text.index("Summary one.") < text.index("Summary two.") < text.index("Record A.")
    assert text.index("Record A.") < text.index("Record B.")


def test_cli_stream_without_placement_is_arrival_order() -> None:
    out = io.StringIO()
    renderer = Renderer(out, io.StringIO(), operator=False)
    _feed(renderer, _NO_PLACEMENT)
    renderer.finish()
    assert "First. Second. Third." in out.getvalue()


def test_cli_stream_flushes_a_listing_with_no_summary_at_finish() -> None:
    out = io.StringIO()
    renderer = Renderer(out, io.StringIO(), operator=False)
    renderer.handle(_event("token", "t", 0, _token_payload("Only records. ", "listing")))
    renderer.finish()
    assert "Only records." in out.getvalue()


def test_cli_json_answer_puts_summary_before_listing() -> None:
    # Mutation that turns this red: join the JSON renderer's parts as they arrived.
    out = io.StringIO()
    renderer = JsonRenderer(out, io.StringIO(), session_id="s", run_id="r")
    _feed(renderer, _LISTING_FIRST)
    renderer.finish()
    assert json.loads(out.getvalue())["answer"] == "Summary one. Summary two. Record A. Record B. "


def test_cli_json_answer_without_placement_is_arrival_order() -> None:
    out = io.StringIO()
    renderer = JsonRenderer(out, io.StringIO(), session_id="s", run_id="r")
    _feed(renderer, _NO_PLACEMENT)
    renderer.finish()
    assert json.loads(out.getvalue())["answer"] == "First. Second. Third. "
