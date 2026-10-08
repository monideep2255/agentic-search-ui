"""`GET /v1/query/{run_id}/citations` keeps every citation one answer can show.

Card 54. The export used to stop at 50 while a live answer shows up to 100,
so a long answer's markers such as [77] pointed at nothing in the export.
`_get_owned_run` is replaced with an in-memory run, so no database is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from system_03_search_agent.adapters.web_sse import app as app_module
from system_03_search_agent.auth.dependencies import Principal, get_caller
from system_03_search_agent.contracts.events import Event
from system_03_search_agent.feedback.contracts import MAX_CITATIONS_PER_ANSWER


def _citation_event(index: int, seq: int) -> Event:
    return Event(
        type="citation",
        version="v1",
        trace_id="trace-1",
        seq=seq,
        ts=datetime.now(UTC),
        payload={
            "citation_id": f"call-1-{index}",
            "display_index": index,
            "source": "NCBIGene",
            "source_id": f"NCBIGene:{index}",
            "source_url": f"https://www.ncbi.nlm.nih.gov/gene/{index}",
            "layer": "layer_1_graph",
            "field": "symbol",
            "claim_text": "A gene.",
            "evidence_kind": "primary_assertion",
            "assertion_confidence": "asserted",
            "population_ancestry_context": None,
            "license": "public_domain_us_gov",
        },
    )


@pytest.fixture
def _caller():
    principal = Principal(owner_id="user:u1", user_id="u1", kind="user")
    app_module.app.dependency_overrides[get_caller] = lambda: principal
    yield
    app_module.app.dependency_overrides.pop(get_caller, None)


async def _export(monkeypatch: pytest.MonkeyPatch, count: int):
    events = [_citation_event(i, i) for i in range(1, count + 1)]
    entry = SimpleNamespace(finished=True, cancelled=False, events=events)
    monkeypatch.setattr(app_module, "_get_owned_run", lambda run_id, caller: entry)
    transport = ASGITransport(app=app_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/v1/query/run-1/citations")


@pytest.mark.asyncio
async def test_the_export_returns_every_citation_of_a_long_answer(_caller, monkeypatch) -> None:
    response = await _export(monkeypatch, 77)
    assert response.status_code == 200
    assert len(response.json()) == 77
    assert "x-citations-export-truncated" not in response.headers


@pytest.mark.asyncio
async def test_the_export_is_still_bounded_above_the_ceiling(_caller, monkeypatch) -> None:
    response = await _export(monkeypatch, MAX_CITATIONS_PER_ANSWER + 20)
    assert response.status_code == 200
    assert len(response.json()) == MAX_CITATIONS_PER_ANSWER
    assert response.headers["x-citations-export-truncated"] == "true"


@pytest.mark.asyncio
async def test_the_export_keeps_the_live_order_and_its_first_hundred(_caller, monkeypatch) -> None:
    """A-54-06: numbers 1 to 100, in order, when 120 were emitted. Mutation:
    reversing the events or keeping the last 100 turns this red."""
    response = await _export(monkeypatch, MAX_CITATIONS_PER_ANSWER + 20)
    assert [c["display_index"] for c in response.json()] == list(range(1, 101))
