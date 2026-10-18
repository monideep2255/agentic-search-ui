"""Ordinary unit test: the two real bypass callers are audited.

Moved out of the deleted `test_observability_premise.py` and
`test_observability_mutation.py` (build phase 4.14 bossman redesign,
2026-09-24, `docs/build/Bossman_redesign_deletion_inventory.md`). The rest
of that file's properties (PII redaction, secret redaction, field
completeness) already have dense ordinary coverage in `test_tracing.py`
and `test_audit.py`. What was unique to the deleted premise gate, and
would otherwise have no ordinary test at all, is this: `think_node`'s
symbol resolution and `s3-kgx-export`'s traversal entry point reach a
data layer with NO `act_node` hook anywhere in their call stack, so the
audit chokepoint has to sit at the TRANSPORT layer
(`ncbi_transport`/`graph_connection`) rather than at `act_node`, or these
two real call sites go unaudited. This test drives both real functions
directly (never `record_tool_call` called by hand) and proves each writes
a real audit line.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.export import traversal
from system_03_search_agent.observability import audit
from system_03_search_agent.tools import ncbi_transport


class _FakeCursor:
    def __init__(self) -> None:
        self.executed: list[str] = []

    @property
    def description(self):
        return [("result",)]

    def execute(self, sql, params=None):
        self.executed.append(sql)

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.autocommit = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


def _graph_factory():
    conn = _FakeConnection(_FakeCursor())

    def factory():
        return conn

    return factory


def _enable_audit(monkeypatch: pytest.MonkeyPatch, log_path: Path) -> None:
    monkeypatch.setattr(audit, "audit_enabled", lambda: True)
    monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)


def _read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(autouse=True)
def _reset_ncbi_transport_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    ncbi_transport.reset_rate_limiters_for_tests()
    yield
    ncbi_transport.reset_rate_limiters_for_tests()


@pytest.fixture(autouse=True)
def _clear_graph_query_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)


class TestRealBypassCallersAreAudited:
    @pytest.mark.asyncio
    async def test_think_node_symbol_resolution_is_audited_by_its_real_caller(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        assert not log_path.exists(), "populate-check: nothing must exist before the call"

        ok_response = httpx.Response(
            200,
            json={
                "reports": [
                    {
                        "gene": {
                            "gene_id": "672",
                            "symbol": "BRCA1",
                            "taxname": "Homo sapiens",
                        }
                    }
                ]
            },
        )

        async def _fake_get(
            _self: httpx.AsyncClient, _url: str, timeout: float | None = None
        ) -> httpx.Response:
            return ok_response

        monkeypatch.setattr(httpx.AsyncClient, "get", _fake_get)

        curie, cacheable = await graph_module._resolve_symbol_to_curie_uncached("BRCA1", "human")

        assert curie == "NCBIGene:672"
        assert cacheable is True

        entries = _read_entries(log_path)
        assert len(entries) == 1, (
            "the real think_node symbol-resolution call must write exactly one audit line"
        )
        assert entries[0]["tool"] == "ncbi_transport:datasets"
        assert entries[0]["layer"] == 2
        assert entries[0]["http_status"] == 200

    def test_kgx_export_traversal_is_audited_by_its_real_caller(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        assert not log_path.exists()

        result = traversal.traverse_subgraph(
            ["MONDO:0007254"],
            hops=0,
            connection_factory=_graph_factory(),
        )

        assert result.seeds_requested == ["MONDO:0007254"]
        assert result.seeds_resolved == []

        entries = _read_entries(log_path)
        assert len(entries) >= 1, (
            "the real KGX-export traversal entry point must write at least one audit line"
        )
        assert entries[0]["tool"] == "cypher_query"
        assert entries[0]["layer"] == 1
        assert entries[0]["http_status"] is None
