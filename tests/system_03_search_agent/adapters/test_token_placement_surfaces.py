"""Every surface that joins answer tokens reads the summary above the listing.

Build phase 8.7, T-8.7-03, card 50. The server may send the record listing
before the written summary. Each surface below is fed listing tokens first
and must put the summary first. Each also has an arm with no `placement`
that must read in arrival order, byte for byte as before the field existed.

F-8.7-A04, card 57: the listing's citations go out with it, and one the
summary also cites is sent again once the summary is checked, with its
checked words grown. Each surface keeps one row per citation id, the later
payload in the first one's place, and drops a repeat that changes anything
else (the end of this file).
"""

from __future__ import annotations

import io
import json
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from system_03_search_agent.adapters.cli.render import JsonRenderer, Renderer
from system_03_search_agent.adapters.graphql import fold as fold_module
from system_03_search_agent.adapters.mcp import server as server_module
from system_03_search_agent.adapters.web_sse import app as app_module
from system_03_search_agent.auth.dependencies import Principal, get_caller
from system_03_search_agent.contracts.events import (
    CitationPayload,
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
    items: list[tuple[str, Any]] | None = None,
) -> Callable[..., AsyncIterator[Event]]:
    items = items if items is not None else _items(tokens)

    async def _stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
        for seq, (event_type, payload) in enumerate(items):
            yield _event(event_type, query.trace_id, seq, payload)

    return _stream


def _registry_run(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    tokens: list[tuple[str, str | None]],
    surface: str,
    items: list[tuple[str, Any]] | None = None,
) -> str:
    registry = RunRegistry()
    monkeypatch.setattr(run_registry_module, "run_streaming", _stream_of(tokens, items))
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


# ---------------------------------------------------------------------------
# F-8.7-A04, card 57: one citation per id on every joining surface.
# ---------------------------------------------------------------------------

_GROWN = "Disease 1 BRCA1 is linked to disease 1"


def _citation(n: int, claim_text: str, **extra: Any) -> CitationPayload:
    fields: dict[str, Any] = {
        "citation_id": f"c{n}",
        "display_index": n,
        "source": "MedGen",
        "source_id": f"MedGen:C{n}",
        "source_url": f"https://www.ncbi.nlm.nih.gov/medgen/C{n}",
        "layer": "layer_1_graph",
        "field": "name",
        "claim_text": claim_text,
        "evidence_kind": "curated assertion",
        "assertion_confidence": "not provided",
        "license": "public_domain_us_gov",
    }
    fields.update(extra)
    return CitationPayload(**fields)


def _resent_items() -> list[tuple[str, Any]]:
    """The server's order with the listing sent early: listing rows and
    their citations, the summary, then record 1's citation again with the
    summary sentence's checked words joined, and a repeat of record 2 that
    changes its number, which is never an update."""
    return [
        ("guard", GuardPayload(passed=True, category="ok", reason=None)),
        (
            "token",
            TokenPayload(text="Disease 1 [1]. ", marker_ids=["c1"], placement="listing"),
        ),
        (
            "token",
            TokenPayload(text="Disease 2 [2]. ", marker_ids=["c2"], placement="listing"),
        ),
        ("citation", _citation(1, "Disease 1")),
        ("citation", _citation(2, "Disease 2")),
        (
            "token",
            TokenPayload(
                text="BRCA1 is linked to disease 1 [1]. ", marker_ids=["c1"], placement="summary"
            ),
        ),
        ("citation", _citation(1, _GROWN)),
        ("citation", _citation(2, "Disease 2", display_index=7)),
        (
            "done",
            DonePayload(
                total_cost_usd=0.0, total_tool_calls=1, elapsed_ms=1, trust_outcome="answer"
            ),
        ),
    ]


def _resent_events() -> list[Event]:
    return [
        _event(event_type, "t-resend", seq, payload)
        for seq, (event_type, payload) in enumerate(_resent_items())
    ]


@pytest.mark.asyncio
async def test_mcp_keeps_one_citation_per_id_with_the_checked_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mutation that turns this red: append every citation event (the fold
    before this fix)."""
    run_id = _registry_run(
        monkeypatch, server_module, [], "mcp", items=_resent_items()
    )
    result = await server_module._fold_run_to_response(run_id, session_id="s-place")
    assert [(c.citation_id, c.display_index) for c in result.citations] == [("c1", 1), ("c2", 2)]
    assert result.citations[0].claim_text == _GROWN
    assert "omitted" not in (result.trust_signal.message or "")


@pytest.mark.asyncio
async def test_graphql_keeps_one_citation_per_id_with_the_checked_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The re-send replaces, with no omission disclosed for it; the
    renumbered repeat is still omitted as a duplicate id (F-4.3-A-07).
    Mutation that turns this red: treat every repeat as a duplicate."""
    run_id = _registry_run(monkeypatch, fold_module, [], "graphql", items=_resent_items())
    result = await fold_module.fold_run(run_id, persona_name="Mendel")
    assert [(c.citation_id, c.display_index) for c in result.citations] == [("c1", 1), ("c2", 2)]
    assert result.citations[0].claim_text == _GROWN
    assert result.disclosures.citations_omitted == 1


def test_graphql_citations_export_keeps_one_citation_per_id() -> None:
    entry = SimpleNamespace(
        run_id="r-resend", finished=True, cancelled=False, events=_resent_events()
    )
    export = fold_module.fold_citations(entry)  # type: ignore[arg-type]
    assert [c.citation_id for c in export.citations] == ["c1", "c2"]
    assert export.citations[0].claim_text == _GROWN


@pytest.mark.asyncio
async def test_rest_citations_export_keeps_one_citation_per_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`GET /v1/query/{run_id}/citations`, which `s3 citations` prints.
    Mutation that turns this red: list every citation event as it came."""
    principal = Principal(owner_id="user:u1", user_id="u1", kind="user")
    app_module.app.dependency_overrides[get_caller] = lambda: principal
    entry = SimpleNamespace(finished=True, cancelled=False, events=_resent_events())
    monkeypatch.setattr(app_module, "_get_owned_run", lambda run_id, caller: entry)
    try:
        transport = ASGITransport(app=app_module.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/query/run-1/citations")
    finally:
        app_module.app.dependency_overrides.pop(get_caller, None)
    assert response.status_code == 200
    body = response.json()
    assert [(c["citation_id"], c["display_index"]) for c in body] == [("c1", 1), ("c2", 2)]
    assert body[0]["claim_text"] == _GROWN
    assert "x-citations-export-truncated" not in response.headers


def test_cli_stream_takes_the_resent_citation_without_a_warning() -> None:
    """Mutation that turns this red: treat the re-send as a conflicting
    redefinition (the first payload kept, a warning printed)."""
    out, err = io.StringIO(), io.StringIO()
    renderer = Renderer(out, err, operator=False)
    for event in _resent_events():
        renderer.handle(event)
    renderer.finish()
    assert renderer._citations["c1"].claim_text == _GROWN
    assert renderer._citations["c2"].display_index == 2
    warnings = err.getvalue()
    assert "'c1' was redefined" not in warnings, warnings
    assert "'c2' was redefined" in warnings, "a renumbered repeat is still a conflict"


def test_cli_json_answer_lists_one_citation_per_id_with_the_checked_words() -> None:
    """`s3 ask --json`. Mutation that turns this red: keep the first
    payload for an id whatever comes later (`setdefault`)."""
    out = io.StringIO()
    renderer = JsonRenderer(out, io.StringIO(), session_id="s", run_id="r")
    for event in _resent_events():
        renderer.handle(event)
    renderer.finish()
    citations = json.loads(out.getvalue())["citations"]
    assert [(c["citation_id"], c["display_index"]) for c in citations] == [("c1", 1), ("c2", 2)]
    assert citations[0]["claim_text"] == _GROWN
