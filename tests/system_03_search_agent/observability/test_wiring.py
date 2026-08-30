"""Tests for T-5.0-05: the wiring itself, not the four modules it wires.

Config, audit, tracing and analytics each have their own test file
(test_config.py, test_audit.py, test_tracing.py, test_analytics.py) proving
those modules work in isolation. This file proves the SEAM T-5.0-05 built:
that the three transport chokepoints (`ncbi_transport.execute_get`,
`graph_connection.execute_cypher`, `pathogen_ftp_transport`) actually call
`record_tool_call`, that the trace_id contextvar is actually bound around a
real run, and that `core/run.py`'s tracing and analytics call sites are
actually reached.

## Coverage: what this file exercises and what it deliberately omits

Per `.claude/rules/goal-contracts.md`, a verify surface must state its own
coverage so a gap is arguable rather than silently assumed away.

Exercised:

- A normal Layer 2 call through `ncbi_transport.execute_get` writes one
  audit line.
- A normal Layer 1 call through `graph_connection.execute_cypher` writes
  one audit line.
- THE BYPASS ARMS, the reason this design exists over an `act_node` hook
  (tracker/phase_5.0.md finding one): a direct `execute_cypher` call with
  no `cypher_query` tool wrapper in between (the exact shape
  `export/traversal.py:558` and `:801` use) still writes a line, and a
  direct `execute_get` call shaped like `think_node`'s symbol-resolution
  path (`core/graph.py:2038/2098/2139`, an `ncbi_efetch` action reaching
  the transport with no `act_node` hook above it) still writes a line.
- `trace_id` is non-null on the written line when a `trace_id_scope` is
  active around the call, and null when it is not, proven through the
  transport chokepoints themselves rather than through `record_tool_call`
  directly (test_audit.py already covers the contextvar in isolation).
- F-5.0-08's reproduction, reproduced again here at the wiring layer: an
  NCBI API key appended to the outbound URL's query string is confirmed
  present in the actual HTTP request (the positive control, proving the
  test's premise), then confirmed absent from the audit line, while the
  host and path ARE present.
- An audit write failure (an unwritable log path) does not fail the
  underlying transport call: the call still returns its real result.
- With no `LANGSMITH_API_KEY` configured, a full `run()` invocation
  completes and `tracing.build_traced_client` is never called, asserted
  against a spy rather than merely "no exception was raised" (the same
  proof-of-absence discipline test_tracing.py already uses for the module
  in isolation, now proven through the actual `core/run.py` call sites).
- The populate-check on every arm above (`.claude/rules/goal-contracts.md`):
  every "a line was written" arm asserts `len(lines) == 1` against a file
  that did not exist before the call, never merely "no exception", and the
  F-5.0-08 arm asserts the secret WAS in the outbound request before
  asserting it is absent from the audit line, so an arm that never
  exercised the credential path at all cannot pass by accident.

NOT exercised, deliberately:

- Every property test_audit.py, test_tracing.py and test_analytics.py
  already prove about their own module in isolation (redaction internals,
  the full PostHog property allowlist, LangSmith's PII allowlist). This
  file only proves those modules are actually CALLED from the right
  places, with the right values, not that they behave correctly once
  called.
- `core/graph.py`'s real `_resolve_symbol_to_curie_uncached` and
  `export/traversal.py`'s real traversal functions are not invoked here.
  The bypass arms call `ncbi_transport.execute_get` and
  `graph_connection.execute_cypher` directly, with the same call shape
  those two real call sites use (no tool wrapper, no `act_node`), which is
  sufficient to prove the chokepoint design's central claim (the same
  function is reached regardless of caller), without standing up either
  module's full dependency graph. `export/test_kgx_traversal.py` and
  `core/test_graph.py` are the tests that exercise those callers'
  own logic; this file is not re-proving that.
- Live LangSmith or PostHog. No test here sends a real request to either
  service; every HTTP boundary is mocked exactly as the modules under test
  already require.
- `AnalyticsEvent.FEEDBACK_SUBMITTED`'s wiring in `adapters/web_sse/app.py`
  is exercised in `tests/system_03_search_agent/adapters/web_sse/
  test_feedback_endpoint.py`, not duplicated here.

Depends on:
    - system_03_search_agent.observability.audit
    - system_03_search_agent.observability.tracing
    - system_03_search_agent.tools.ncbi_transport
    - system_03_search_agent.tools.graph_connection
    - system_03_search_agent.tools.pathogen_ftp_transport
    - system_03_search_agent.core.run (the "no key, zero trace" full-run arm)

Writes:
    - Nothing outside `tmp_path`.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

from system_03_search_agent.observability import audit, tracing
from system_03_search_agent.tools import (
    graph_connection,
    ncbi_transport,
    pathogen_ftp_transport,
)

# ---------------------------------------------------------------------------
# Shared fakes and helpers
# ---------------------------------------------------------------------------


class _FakeCursor:
    """A minimal stand-in for a psycopg2 cursor. See
    test_graph_connection.py's identical class for the fuller rationale;
    this copy is intentionally self-contained rather than imported across
    test files, matching this repository's existing per-file convention.
    """

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
    """A connection_factory returning a fresh fake connection every call,
    exactly the shape `export/traversal.py` and `cypher_query.py` pass in.
    """
    conn = _FakeConnection(_FakeCursor())

    def factory():
        return conn

    return factory


class _FakeHttpClient:
    """A minimal stand-in for `httpx.AsyncClient`, matching exactly the
    call shape `ncbi_transport._execute_with_retry` uses:
    `await client.get(url, timeout=timeout_s)`.
    """

    def __init__(self, response: httpx.Response) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response = response

    async def get(self, url: str, timeout: float | None = None) -> httpx.Response:
        self.calls.append({"url": url, "timeout": timeout})
        return self._response


def _enable_audit(monkeypatch: pytest.MonkeyPatch, log_path: Path) -> None:
    monkeypatch.setattr(audit, "audit_enabled", lambda: True)
    monkeypatch.setattr(audit, "audit_log_path", lambda: log_path)


def _read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(autouse=True)
def _reset_ncbi_transport_state(monkeypatch: pytest.MonkeyPatch):
    """Clean NCBI_* env and rate-limiter state for every test in this file,
    matching test_ncbi_transport.py's own fixture.
    """
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    ncbi_transport.reset_rate_limiters_for_tests()
    yield
    ncbi_transport.reset_rate_limiters_for_tests()


@pytest.fixture(autouse=True)
def _clear_graph_query_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every `execute_cypher` call in this file passes `connection_factory`
    expecting the psycopg2 path; `graph_connection.execute_cypher` raises
    `GraphError` if `GRAPH_QUERY_URL` is also set (two transports named at
    once). Cleared explicitly, matching test_graph_connection.py's own
    fixtures, rather than assumed absent: a full-suite run showed this
    leaking in from elsewhere in the collected environment and turning five
    otherwise-correct arms red for a reason unrelated to what they test.
    """
    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)


# ---------------------------------------------------------------------------
# Normal-path arms: one line per chokepoint.
# ---------------------------------------------------------------------------


class TestLayer2AuditLine:
    @pytest.mark.asyncio
    async def test_execute_get_writes_one_audit_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fails if `execute_get` never calls `record_tool_call` at all, or
        calls it with the wrong layer for an eutils-family call.
        """
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        assert not log_path.exists(), "populate-check: nothing must exist before the call"

        client = _FakeHttpClient(httpx.Response(200, json={"esearchresult": {"count": "0"}}))
        response = await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "gene", "term": "BRCA1"},
            family="eutils",
            client=client,
        )

        assert response.status_code == 200
        entries = _read_entries(log_path)
        assert len(entries) == 1
        assert entries[0]["layer"] == 2
        assert entries[0]["http_status"] == 200
        assert entries[0]["error_code"] is None
        assert entries[0]["latency_ms"] >= 0


class TestLayer1AuditLine:
    def test_execute_cypher_writes_one_audit_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fails if `execute_cypher` (the public wrapper) never calls
        `record_tool_call`, or reports the wrong layer.
        """
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        assert not log_path.exists()

        rows, total = graph_connection.execute_cypher(
            "MATCH (g:Gene {id: $gene_id}) RETURN g LIMIT 1",
            {"gene_id": "NCBIGene:672"},
            connection_factory=_graph_factory(),
        )

        assert rows == []
        assert total == 0
        entries = _read_entries(log_path)
        assert len(entries) == 1
        assert entries[0]["layer"] == 1
        assert entries[0]["tool"] == "cypher_query"
        assert entries[0]["error_code"] is None


# ---------------------------------------------------------------------------
# The bypass arms: THE reason this design exists over an act_node hook.
# ---------------------------------------------------------------------------


class TestBypassArms:
    def test_kgx_export_shaped_direct_execute_cypher_call_is_audited(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reproduces `export/traversal.py:558`/`:801`'s exact call shape: a
        direct `execute_cypher(cypher, params, row_limit=..., timeout_s=...,
        connection_factory=..., as_clause=...)` call with no `cypher_query`
        tool wrapper anywhere above it. Fails if the audit hook lives at
        `act_node` or inside the `cypher_query` tool instead of inside
        `execute_cypher` itself, since either of those would see nothing
        for a call shaped exactly like this one.
        """
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        assert not log_path.exists()

        graph_connection.execute_cypher(
            "MATCH (n:Disease {id: $seed_id}) RETURN n LIMIT 1",
            {"seed_id": "MONDO:0007254"},
            row_limit=100,
            timeout_s=30.0,
            connection_factory=_graph_factory(),
            as_clause="(result agtype)",
        )

        entries = _read_entries(log_path)
        assert len(entries) == 1, "the KGX-export-shaped bypass call must still be audited"

    @pytest.mark.asyncio
    async def test_think_node_shaped_direct_execute_get_call_is_audited(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reproduces `core/graph.py`'s `_resolve_symbol_to_curie_uncached`
        shape: an `ncbi_efetch`-family HTTPS call reaching `execute_get`
        directly during `think_node`'s own symbol resolution, with no
        `act_node` tool dispatch anywhere in the call stack. Fails for the
        identical reason the KGX arm above does.
        """
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        assert not log_path.exists()

        client = _FakeHttpClient(
            httpx.Response(200, json={"reports": [{"gene": {"gene_id": "672"}}]})
        )
        await ncbi_transport.execute_get(
            "https://api.ncbi.nlm.nih.gov/datasets/v2/gene/symbol/BRCA1/taxon/9606",
            {},
            family="datasets",
            client=client,
        )

        entries = _read_entries(log_path)
        assert len(entries) == 1, "the think_node-shaped bypass call must still be audited"


# ---------------------------------------------------------------------------
# trace_id propagation through the transport, not through record_tool_call
# directly (test_audit.py already covers that).
# ---------------------------------------------------------------------------


class TestTraceIdThroughTransport:
    def test_trace_id_present_at_execute_cypher_when_scope_is_active(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)

        with audit.trace_id_scope("wiring-trace-1"):
            graph_connection.execute_cypher(
                "MATCH (g:Gene {id: $gene_id}) RETURN g LIMIT 1",
                {"gene_id": "NCBIGene:672"},
                connection_factory=_graph_factory(),
            )

        entries = _read_entries(log_path)
        assert entries[0]["trace_id"] == "wiring-trace-1"

    def test_trace_id_null_at_execute_cypher_with_no_scope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The s3-kgx-export case named throughout tracker/phase_5.0.md: a
        caller with no run in scope gets a genuine null, never a
        fabricated id.
        """
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        assert audit.current_trace_id() is None

        graph_connection.execute_cypher(
            "MATCH (g:Gene {id: $gene_id}) RETURN g LIMIT 1",
            {"gene_id": "NCBIGene:672"},
            connection_factory=_graph_factory(),
        )

        entries = _read_entries(log_path)
        assert entries[0]["trace_id"] is None

    @pytest.mark.asyncio
    async def test_trace_id_present_at_execute_get_when_scope_is_active(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)

        client = _FakeHttpClient(httpx.Response(200, json={"esearchresult": {"count": "0"}}))
        with audit.trace_id_scope("wiring-trace-2"):
            await ncbi_transport.execute_get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                {"db": "gene", "term": "TP53"},
                family="eutils",
                client=client,
            )

        entries = _read_entries(log_path)
        assert entries[0]["trace_id"] == "wiring-trace-2"


# ---------------------------------------------------------------------------
# F-5.0-08 at the wiring layer: the credential must never leak, host/path
# must survive.
# ---------------------------------------------------------------------------


class TestCredentialNeverLeaksThroughTheTransport:
    @pytest.mark.asyncio
    async def test_api_key_reaches_the_request_but_never_the_audit_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The populate-check for this arm: the secret is first confirmed
        present in the OUTBOUND request (proving `include_api_key=True`
        genuinely exercised `_append_api_key`, so a no-op implementation
        could not pass this test by accident), then confirmed absent from
        the audit line while the host and path survive.
        """
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        secret_value = uuid.uuid4().hex
        monkeypatch.setenv("NCBI_API_KEY", secret_value)

        client = _FakeHttpClient(httpx.Response(200, json={"esearchresult": {"count": "0"}}))
        await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "gene", "id": "7157"},
            family="eutils",
            include_api_key=True,
            client=client,
        )

        # Positive control: the secret really was sent.
        assert secret_value in client.calls[0]["url"]

        raw_text = log_path.read_text(encoding="utf-8")
        assert secret_value not in raw_text
        assert "eutils.ncbi.nlm.nih.gov" in raw_text
        assert "/entrez/eutils/esearch.fcgi" in raw_text


# ---------------------------------------------------------------------------
# Best-effort: an audit write failure never fails the underlying call.
# ---------------------------------------------------------------------------


class TestAuditFailureNeverFailsTheQuery:
    @pytest.mark.asyncio
    async def test_unwritable_audit_path_does_not_fail_execute_get(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A plain file where a directory is expected makes `mkdir` fail
        inside `record_tool_call`, matching test_audit.py's own technique.
        The real transport call must still return its real result.
        """
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        unwritable_path = blocker / "audit.jsonl"
        _enable_audit(monkeypatch, unwritable_path)

        client = _FakeHttpClient(httpx.Response(200, json={"esearchresult": {"count": "0"}}))
        response = await ncbi_transport.execute_get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            {"db": "gene", "term": "BRCA1"},
            family="eutils",
            client=client,
        )

        assert response.status_code == 200, "the real call must succeed despite the audit failure"
        assert not unwritable_path.exists()

    def test_unwritable_audit_path_does_not_fail_execute_cypher(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        unwritable_path = blocker / "audit.jsonl"
        _enable_audit(monkeypatch, unwritable_path)

        rows, total = graph_connection.execute_cypher(
            "MATCH (g:Gene {id: $gene_id}) RETURN g LIMIT 1",
            {"gene_id": "NCBIGene:672"},
            connection_factory=_graph_factory(),
        )

        assert rows == []
        assert total == 0
        assert not unwritable_path.exists()


# ---------------------------------------------------------------------------
# The Pathogen Detection chokepoint: least exercised, per this phase's own
# coverage statement, since it has no production caller today.
# ---------------------------------------------------------------------------


class TestPathogenChokepoint:
    @pytest.mark.asyncio
    async def test_stream_filtered_tsv_rows_writes_one_audit_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)

        body = "PDS_acc\tbiosample_acc\nPDS000012345.1\tSAMN00000001\n"

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text=body)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await pathogen_ftp_transport.stream_filtered_tsv_rows(
                "https://ftp.ncbi.nlm.nih.gov/pathogen/Results/Salmonella/PDG1/"
                "Clusters/cluster_list.tsv",
                key_column="PDS_acc",
                key_values={"PDS000012345.1"},
                deadline=time.monotonic() + 30.0,
                client=client,
            )

        assert len(result.rows) == 1
        entries = _read_entries(log_path)
        assert len(entries) == 1
        assert entries[0]["tool"] == "pathogen_detection"
        assert entries[0]["layer"] == 2
        assert entries[0]["http_status"] == 200


# ---------------------------------------------------------------------------
# With no LANGSMITH_API_KEY, a real run() completes and no trace client is
# ever constructed. Proven through core/run.py's actual call sites, not
# through observability.tracing in isolation (test_tracing.py's job).
# ---------------------------------------------------------------------------


class TestNoLangsmithKeyMeansZeroTraceThroughRun:
    """A full graph invocation, reusing the same stub pattern
    `tests/system_03_search_agent/core/test_run.py` establishes: litellm
    is stubbed per-tier, symbol resolution and ncbi_efetch dispatch inside
    `think_node`/`plan_node` are stubbed, and the two daily-cap DB checks
    are no-ops. This class exists to prove the WIRING (that `core/run.py`
    reaches `traced_graph_run`, which in turn never reaches
    `build_traced_client` with no key configured), not to re-prove
    `run()`'s own event-sequence behaviour, which test_run.py already
    covers exhaustively.
    """

    @pytest.fixture(autouse=True)
    def _clear_langsmith_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in (
            "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY",
            "LANGSMITH_PROJECT", "LANGCHAIN_PROJECT",
            "LANGSMITH_ENDPOINT", "LANGCHAIN_ENDPOINT",
            "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2",
            "LANGSMITH_TRACING", "LANGCHAIN_TRACING",
        ):
            monkeypatch.delenv(name, raising=False)
        # The exact shape of this repository's live critical finding
        # (F-5.0-03): the flag is on, as it is in every real `.env` here,
        # but no key is configured.
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")

    @pytest.fixture(autouse=True)
    def _env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
        monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
        monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
        monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
        monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
        monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
        monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")

    @pytest.fixture(autouse=True)
    def _no_op_daily_caps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from system_03_search_agent.harness import cost_control

        monkeypatch.setattr(
            cost_control, "check_user_daily_query_cap", lambda session, user_id, **kw: None
        )
        monkeypatch.setattr(
            cost_control, "check_system_daily_cost_cap", lambda session, **kw: None
        )

    @pytest.fixture(autouse=True)
    def _stub_symbol_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from system_03_search_agent.core import graph as graph_module

        async def _fake_resolve(symbol: str, **kwargs: object) -> str | None:
            return None

        monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve)

    @pytest.fixture(autouse=True)
    def _mock_litellm(self, monkeypatch: pytest.MonkeyPatch):
        from system_03_search_agent.harness import harness as harness_module
        from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

        return install_dispatching_acompletion(monkeypatch, harness_module)

    @pytest.fixture(autouse=True)
    def _disable_audit_log(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Not this class's concern; the chokepoint tests above already
        # cover it, and leaving it on would write a real file next to the
        # test run for no reason this class cares about.
        monkeypatch.setattr(audit, "audit_enabled", lambda: False)

    @pytest.mark.asyncio
    async def test_run_completes_and_build_traced_client_is_never_called(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.contracts.query import Query, RequestContext
        from system_03_search_agent.core.run import run
        from system_03_search_agent.observability import config as observability_config

        def _fail_if_called() -> Any:
            raise AssertionError(
                "build_traced_client must never be reached with no "
                "LANGSMITH_API_KEY configured"
            )

        monkeypatch.setattr(tracing, "build_traced_client", _fail_if_called)

        # The populate-check for this arm: without this spy, a regression
        # that dropped `traced_graph_run` from `core/run.py` entirely (so
        # neither call site above is ever reached at all) would still pass
        # this test, since `build_traced_client` would then trivially never
        # be called for the wrong reason. Wrapping the REAL
        # `config.tracing_enabled` (not replacing it) proves the tracing
        # code path was actually entered from `core/run.py`, while still
        # returning the real (False, no key configured) answer.
        real_tracing_enabled = observability_config.tracing_enabled
        call_count = {"n": 0}

        def _counting_tracing_enabled() -> bool:
            call_count["n"] += 1
            return real_tracing_enabled()

        monkeypatch.setattr(
            observability_config, "tracing_enabled", _counting_tracing_enabled
        )

        query = Query(
            text="hello",
            session_id="wiring-session-1",
            trace_id="wiring-run-1",
            user_id=None,
            audience_depth="researcher",
        )
        context = RequestContext(surface="web_ui", session_memory=None, operator_mode=False)

        events = [event async for event in run(query, context)]

        # Reaching this line with at least one done event, with the
        # build_traced_client spy above never having raised, is half the
        # assertion: a regression that reaches `build_traced_client` fails
        # this test by raising through the spy, not by a separate assert.
        assert any(event.type == "done" for event in events)
        # The other half: `traced_graph_run` was genuinely entered at least
        # once per call site (`run()` calls `compiled_graph.ainvoke` once).
        assert call_count["n"] >= 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
