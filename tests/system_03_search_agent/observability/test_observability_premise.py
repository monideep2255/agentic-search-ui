"""T-5.0-07: the premise gate for build phase 5.0 (observability).

## The central gap this file exists to close

`test_wiring.py`'s own coverage statement names it directly: its
`TestBypassArms` calls `graph_connection.execute_cypher` and
`ncbi_transport.execute_get` DIRECTLY, with the same call SHAPE
`export/traversal.py:558`/`:801` and `core/graph.py`'s
`_resolve_symbol_to_curie_uncached` use, but does not stand up either
module's own dependency graph. That is sufficient to prove the chokepoint
design's central claim (the same function is reached regardless of
caller, because there is only one function to reach); it does NOT prove
the two REAL bypass callers still reach that function with the arguments
they actually build. `TestRealBypassCallersAreAudited` below is that
missing half: it calls `core.graph._resolve_symbol_to_curie_uncached` and
`export.traversal.traverse_subgraph` themselves, unmodified, faking only
the one genuine external boundary each has (an HTTP transport for the
first, a psycopg2-shaped connection for the second).

Build phase 4.4's premise gate passed 6 of 6 while the default path it
never exercised returned a wrong answer, and its coverage statement had
already named that omission. The lesson this file exists to apply: a
"the chokepoint works" proof and a "the real caller reaches the
chokepoint" proof are different claims, and only the second closes the
finding (tracker/phase_5.0.md's finding one) this whole phase was
designed around.

## Coverage: what this file exercises and what it deliberately omits

Per `.claude/rules/goal-contracts.md`, a verify surface must state its own
coverage so a gap is arguable rather than silently assumed away.

Exercised:

- `core.graph._resolve_symbol_to_curie_uncached("BRCA1", "human")`,
  called directly, with only `httpx.AsyncClient.get` faked. Reproduces
  the exact shape of tracker/phase_5.0.md's live end-to-end evidence:
  `gene/symbol/BRCA1/taxon/human` was the first audit line a real
  production run ever wrote, from inside this exact function, with no
  `act_node` hook anywhere above it.
- `export.traversal.traverse_subgraph(["MONDO:0007254"], hops=0,
  connection_factory=...)`, called directly, with only the psycopg2-shaped
  connection faked. Reproduces `export/traversal.py:558`'s seed-lookup
  call shape, the KGX export path's own real entry point.
- With no `LANGSMITH_API_KEY` configured (the exact F-5.0-03 shape: the
  tracing flag on, no key), `tracing.traced_graph_run` never attempts to
  construct a client, asserted against a call-counting spy rather than
  merely "no exception was raised", with a populate-check proving
  `tracing_enabled()` was genuinely consulted rather than the whole
  code path having been skipped for an unrelated reason.
- Every field Section 20.3 names, checked against Section 20.3's own text
  in `requirements/Technical_specification.md` (quoted in
  `TestAuditLineCarriesEverySection20_3Field`'s docstring), not against
  `audit.py`'s own docstring or `record_tool_call`'s own parameter names,
  driven through the real transport chokepoint.
- An NCBI API key never reaches the audit line, WITH a positive control
  (the secret is first confirmed present in the outbound request, so a
  no-op `include_api_key` implementation could not pass this test by
  accident) and an assertion that `authorization` records `"ncbi_api_key"`
  BY IDENTIFIER, tying this arm to Section 20.3's first bullet ("every
  Layer 2 and Layer 3 access logged with its authorization").
- `trace_id` is non-null on a written line when a `trace_id_scope` is
  active, and null when it is not, driven through the real transport
  chokepoint rather than through `record_tool_call` directly.
- The audit log is append-only: two real calls through the transport
  chokepoint produce two lines, and the RAW BYTES of the first line are
  unchanged after the second lands.
- One live, opt-in, read-only arm against the real LangSmith service
  (`TestLiveLangSmithReachability`), gated behind `RUN_PREMISE_GATE=1`
  AND a real `LANGSMITH_API_KEY`, following
  `test_ncbi_efetch_premise.py`'s precedent for an expensive, live gate
  being dormant by decision rather than by an unrelated tunnel happening
  to be closed. It reads `Client.info`, a property read with no write
  side effect, so it authenticates and confirms reachability without
  creating or mutating any real trace.

NOT exercised, deliberately:

- POSTHOG IS NEVER CONTACTED BY THIS FILE, live or otherwise, under any
  gate. F-5.0-12: the provisioned `POSTHOG_API_KEY` is a personal,
  account-wide read-write credential, not the write-only project token
  capture is built to send, so no arm anywhere in this file may POST to
  PostHog. `analytics.py`'s own no-credential and property-allowlist
  properties are covered by `test_analytics.py`, not duplicated here.
- THE KGX BYPASS ARM DOES NOT PROVE THE SEED RESOLVES. `_lookup_seed`
  tries every candidate vertex label in turn against the fake connection,
  which returns no rows for any of them, so `MONDO:0007254` never
  actually resolves to a vertex inside this test. This arm proves the
  AUDIT HOOK fires from the real caller with the real call shape, not
  that the traversal's seed-resolution logic is correct;
  `export/test_kgx_traversal.py` owns that property.
- FIVE OF THE SEVEN TOOLS HAVE NO PRODUCTION CALL SITE (unchanged from
  the phase-level coverage statement in tracker/phase_5.0.md): this file
  cannot drive a "real bypass caller" for `ncbi_dbsnp`, `pubtator_
  annotate`, `litvar2_lookup`, `pathogen_detection` or
  `clinicaltrials_search` beyond what `test_wiring.py` already covers by
  direct chokepoint invocation, because `plan_node`'s planned-call union
  has no caller for them to be reached from at all.
- MUTATION COVERAGE LIVES IN A SEPARATE FILE, `test_observability_
  mutation.py`, per this repository's convention (`test_cq_routing_
  mutation.py`, `test_release_environments_mutation.py`) of keeping the
  premise arms and the harness that proves they can fail in different
  files.
- The redaction, allowlist, and PII-boundary INTERNALS of each of the
  four observability modules are `test_audit.py`'s, `test_tracing.py`'s
  and `test_analytics.py`'s job. This file proves those modules are
  reached, with the right values, from the real callers named above; it
  does not re-prove their own internal correctness once called.

Depends on:
    - system_03_search_agent.observability.audit
    - system_03_search_agent.observability.config
    - system_03_search_agent.observability.tracing
    - system_03_search_agent.core.graph (_resolve_symbol_to_curie_uncached)
    - system_03_search_agent.export.traversal (traverse_subgraph)
    - system_03_search_agent.tools.ncbi_transport
    - system_03_search_agent.tools.graph_connection

Reads:
    - .env, explicitly, only for the live opt-in gate (RUN_PREMISE_GATE,
      LANGSMITH_API_KEY), matching test_ncbi_efetch_premise.py's own
      technique rather than an import-time dotenv side effect.

Writes:
    - Nothing outside tmp_path. The one live arm writes nothing to any
      real service; it performs a single read-only property access.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.export import traversal
from system_03_search_agent.observability import audit, config, tracing
from system_03_search_agent.tools import graph_connection, ncbi_transport

# ---------------------------------------------------------------------------
# Shared fakes and helpers. Self-contained rather than imported from
# test_wiring.py, matching that file's own stated convention ("this copy
# is intentionally self-contained rather than imported across test
# files").
# ---------------------------------------------------------------------------


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
    import json

    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(autouse=True)
def _reset_ncbi_transport_state(monkeypatch: pytest.MonkeyPatch):
    """Clean NCBI_* env and rate-limiter state for every test in this file,
    matching test_wiring.py's and test_ncbi_transport.py's own fixture.
    """
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    ncbi_transport.reset_rate_limiters_for_tests()
    yield
    ncbi_transport.reset_rate_limiters_for_tests()


@pytest.fixture(autouse=True)
def _clear_graph_query_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """`graph_connection.execute_cypher` raises `GraphError` if
    `GRAPH_QUERY_URL` is also set alongside a `connection_factory` (two
    transports named at once). This machine's own `.env` has a live
    `GRAPH_QUERY_URL` (tracker/phase_5.0.md: all three transports green
    at phase open), so this must be cleared explicitly rather than
    assumed absent, matching test_wiring.py's identical fixture.
    """
    monkeypatch.delenv("GRAPH_QUERY_URL", raising=False)


# ---------------------------------------------------------------------------
# The central gap: the two real bypass callers, driven directly.
# ---------------------------------------------------------------------------


class TestRealBypassCallersAreAudited:
    @pytest.mark.asyncio
    async def test_think_node_symbol_resolution_is_audited_by_its_real_caller(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Calls `core.graph._resolve_symbol_to_curie_uncached` itself,
        the exact function `think_node`'s symbol resolution calls with no
        `act_node` hook anywhere in the stack. Only `httpx.AsyncClient.get`
        is faked (the one genuine external boundary this function has);
        `ncbi_efetch`'s own dispatch and `dataset_report`'s own response
        parsing run for real.
        """
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

        curie, cacheable = await graph_module._resolve_symbol_to_curie_uncached(
            "BRCA1", "human"
        )

        # Not merely "an audit line appeared": the resolution itself must
        # have genuinely succeeded through the real dispatch, or a defect
        # earlier in the chain (dataset_report never actually calling
        # execute_get) could still leave an audit line from some other,
        # unrelated call.
        assert curie == "NCBIGene:672"
        assert cacheable is True

        entries = _read_entries(log_path)
        assert len(entries) == 1, (
            "the real think_node symbol-resolution call must write exactly "
            "one audit line: the Datasets leg resolves confidently on its "
            "first attempt for this input, so the ESearch fallback is never "
            "reached"
        )
        assert entries[0]["tool"] == "ncbi_transport:datasets"
        assert entries[0]["layer"] == 2
        assert entries[0]["endpoint"] == (
            "api.ncbi.nlm.nih.gov/datasets/v2/gene/symbol/BRCA1/taxon/human"
        ), "reproduces tracker/phase_5.0.md's live evidence line verbatim"
        assert entries[0]["http_status"] == 200

    def test_kgx_export_traversal_is_audited_by_its_real_caller(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Calls `export.traversal.traverse_subgraph` itself, the real
        entry point `s3-kgx-export` calls, with no `cypher_query` tool
        wrapper and no `act_node` dispatch anywhere in the stack. `hops=0`
        exercises the seed-lookup call `export/traversal.py:558` issues
        without also exercising the hop-expansion query at `:801`, which
        is a separate call site sharing the identical `execute_cypher`
        chokepoint and is not separately proven here.
        """
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        assert not log_path.exists()

        result = traversal.traverse_subgraph(
            ["MONDO:0007254"],
            hops=0,
            connection_factory=_graph_factory(),
        )

        # The seed genuinely does not resolve against this fake connection
        # (see this file's own coverage statement); asserting that
        # explicitly is the populate-check that this call actually ran the
        # real seed-lookup loop rather than short-circuiting before it.
        assert result.seeds_requested == ["MONDO:0007254"]
        assert result.seeds_resolved == []

        entries = _read_entries(log_path)
        assert len(entries) >= 1, (
            "the real KGX-export traversal entry point must write at "
            "least one audit line while attempting to resolve its seed"
        )
        assert entries[0]["tool"] == "cypher_query"
        assert entries[0]["layer"] == 1
        assert entries[0]["http_status"] is None, (
            "a graph query carries no HTTP semantics (record_tool_call's "
            "own documented case)"
        )


# ---------------------------------------------------------------------------
# With no LANGSMITH_API_KEY, zero outbound tracing attempts, proven
# against tracing.traced_graph_run directly (test_wiring.py proves the
# same property through a full core.run.run() invocation; this arm
# isolates it to the tracing module's own on/off boundary).
# ---------------------------------------------------------------------------


class TestNoLangsmithCredentialMeansZeroOutboundAttempts:
    def test_build_traced_client_is_never_attempted_with_no_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in (
            "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY",
            "LANGSMITH_PROJECT", "LANGCHAIN_PROJECT",
            "LANGSMITH_ENDPOINT", "LANGCHAIN_ENDPOINT",
            "LANGSMITH_TRACING_V2", "LANGCHAIN_TRACING_V2",
            "LANGSMITH_TRACING", "LANGCHAIN_TRACING",
        ):
            monkeypatch.delenv(name, raising=False)
        # The exact shape of this repository's live critical finding
        # (F-5.0-03): the flag is on, as every real .env in this project
        # sets it, but no key is configured.
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")

        attempts: list[None] = []

        def _spy_build_traced_client() -> Any:
            attempts.append(None)
            raise AssertionError(
                "build_traced_client must never be attempted with no "
                "LANGSMITH_API_KEY configured"
            )

        monkeypatch.setattr(tracing, "build_traced_client", _spy_build_traced_client)

        # Populate-check: wraps the REAL tracing_enabled rather than
        # replacing it, so a regression that drops the on/off check
        # entirely (and therefore never reaches build_traced_client for
        # an unrelated reason) is not mistaken for this arm passing.
        real_tracing_enabled = config.tracing_enabled
        calls = {"n": 0}

        def _counting_tracing_enabled() -> bool:
            calls["n"] += 1
            return real_tracing_enabled()

        monkeypatch.setattr(config, "tracing_enabled", _counting_tracing_enabled)

        with tracing.traced_graph_run(run_name="premise-gate-no-key-check"):
            pass

        assert attempts == [], "zero outbound tracing attempts must be made with no key"
        assert calls["n"] >= 1, "populate-check: tracing_enabled() was never even consulted"


# ---------------------------------------------------------------------------
# Section 20.3's own field list, not audit.py's.
# ---------------------------------------------------------------------------


class TestAuditLineCarriesEverySection20_3Field:
    """`requirements/Technical_specification.md` Section 20.3, quoted
    directly rather than paraphrased from the code:

        "the audit requirement (every Layer 2 and Layer 3 access logged
        with its authorization, Step 1.12 decision)"

        "One line per tool call ...: trace_id, tool name, endpoint or
        database called, redacted params (no API keys, production-
        standards secrets gate), returned record ids, HTTP status or the
        body-level error and empty signal for E-utilities calls, latency
        in milliseconds, and timestamp."

    `authorization` is named in the FIRST bullet, not the second's own
    enumerated list, which is why this required-fields tuple is built by
    hand from both bullets together rather than by regex-extracting the
    second bullet alone. Driven through the real transport chokepoint,
    not through `record_tool_call` directly.

    The error field is `error_code` rather than `error`, changed when the
    audit sink stopped accepting free text (F-5.0-13, F-5.0-14, F-5.0-19,
    and the design change that closed them).

    What this class proves, and what it does not (F-5.0-23):

    - Proved here: every field Section 20.3 names is PRESENT on a line
      written through the real transport chokepoint. Presence only. This
      class asserts nothing about any field's value.
    - Covered by the design: every failure that reaches a chokepoint as an
      EXCEPTION. `http_status` carries the numeric status wherever one
      exists, and `error_code` carries a classified reason drawn from
      `audit.AUDIT_ERROR_CODES` wherever the failure had no HTTP semantics
      at all, which is every graph call and every connection-level
      failure. The spec never required the reason to be a message, and a
      code is more machine-readable than the prose it replaced.
    - NOT covered, stated rather than implied: Section 20.3's "body-level
      error and empty signal for E-utilities calls". `classify_eutils_
      response` runs in the ACTION modules above the transport, none of
      which calls `record_tool_call`, so an E-utilities body-level error
      and a genuine empty result are both indistinguishable from a success
      on the audit line (`http_status 200, error_code None, error_class
      None`). The vocabulary members reserved for that case, `http_error`
      and `empty`, are DECLARED AND UNEXERCISED: they have no producer
      anywhere in `src/`. `audit.py`'s own comment on `AUDIT_ERROR_CODES`
      says the same thing, and this docstring is written to agree with it
      rather than contradict it.

    - NOT covered either, and in exactly the same state as the two members
      above (J-01): `record_ids` has NO PRODUCER anywhere in `src/`. Every
      audit line the running system writes carries `[]`, including for an
      E-utilities response body that carried an `idlist`, because no
      chokepoint passes the argument. The field is a Section 20.3
      requirement, so its presence on the line is real and this class does
      assert it; what nobody asserts is that anything ever fills it.
      `test_audit.TestRoundTrip.test_written_line_carries_every_contract_
      field` passes a value in itself and therefore exercises the field's
      SHAPE rather than its production, and that arm now says so in its own
      docstring. This entry exists because the coverage statement above
      named `http_error` and `empty` and omitted the third field in the
      identical condition, which is the same class of omission it was
      written to prevent.

    The gap is pre-existing rather than introduced by the error-field
    change: before it, the same success path wrote `error=None`. It is
    open with an owner (F-5.0-23) and is not closed by this class.
    """

    _SECTION_20_3_REQUIRED_FIELDS: tuple[str, ...] = (
        "trace_id",
        "tool",
        "endpoint",
        "authorization",
        "params",
        "record_ids",
        "http_status",
        "error_code",
        "latency_ms",
        "timestamp",
    )

    @pytest.mark.asyncio
    async def test_every_section_20_3_field_is_present_on_a_real_transport_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)

        client = _FakeHttpClient(httpx.Response(200, json={"esearchresult": {"count": "0"}}))
        with audit.trace_id_scope("field-coverage-check"):
            await ncbi_transport.execute_get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                {"db": "gene", "term": "BRCA1"},
                family="eutils",
                client=client,
            )

        entries = _read_entries(log_path)
        assert len(entries) == 1
        entry = entries[0]
        missing = [
            field for field in self._SECTION_20_3_REQUIRED_FIELDS if field not in entry
        ]
        assert missing == [], f"Section 20.3 names these fields, entry is missing: {missing}"


# ---------------------------------------------------------------------------
# The credential-leak positive control.
# ---------------------------------------------------------------------------


class TestCredentialNeverReachesTheAuditLog:
    @pytest.mark.asyncio
    async def test_ncbi_api_key_reaches_the_request_but_never_the_audit_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The populate-check for this arm: the secret is first confirmed
        PRESENT in the outbound request (proving `include_api_key=True`
        genuinely exercised `_append_api_key`, so a no-op implementation
        could not pass this test by accident), then confirmed absent from
        the audit line while `authorization` records the credential BY
        IDENTIFIER (Section 20.3's first bullet), never by value.
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

        # Positive control.
        assert secret_value in client.calls[0]["url"]

        raw_text = log_path.read_text(encoding="utf-8")
        assert secret_value not in raw_text
        assert "eutils.ncbi.nlm.nih.gov" in raw_text

        entries = _read_entries(log_path)
        assert len(entries) == 1
        assert entries[0]["authorization"] == "ncbi_api_key"


# ---------------------------------------------------------------------------
# trace_id present in scope, null out of scope.
# ---------------------------------------------------------------------------


class TestTraceIdPresentInScopeNullOutOfScope:
    def test_trace_id_present_when_scope_is_active(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)

        with audit.trace_id_scope("premise-gate-trace"):
            graph_connection.execute_cypher(
                "MATCH (g:Gene {id: $gene_id}) RETURN g LIMIT 1",
                {"gene_id": "NCBIGene:672"},
                connection_factory=_graph_factory(),
            )

        entries = _read_entries(log_path)
        assert len(entries) == 1
        assert entries[0]["trace_id"] == "premise-gate-trace"

    def test_trace_id_null_with_no_scope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The s3-kgx-export case: a caller with no run in scope gets a
        genuine null, never a fabricated id.
        """
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)
        assert audit.current_trace_id() is None, "populate-check: no scope must be active yet"

        graph_connection.execute_cypher(
            "MATCH (g:Gene {id: $gene_id}) RETURN g LIMIT 1",
            {"gene_id": "NCBIGene:672"},
            connection_factory=_graph_factory(),
        )

        entries = _read_entries(log_path)
        assert len(entries) == 1
        assert entries[0]["trace_id"] is None


# ---------------------------------------------------------------------------
# Append-only, proven through a real caller rather than record_tool_call
# called twice by hand.
# ---------------------------------------------------------------------------


class TestAuditLogAppendOnlyThroughRealCallers:
    def test_second_write_leaves_first_line_byte_identical(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_path = tmp_path / "audit.jsonl"
        _enable_audit(monkeypatch, log_path)

        graph_connection.execute_cypher(
            "MATCH (g:Gene {id: $gene_id}) RETURN g LIMIT 1",
            {"gene_id": "NCBIGene:672"},
            connection_factory=_graph_factory(),
        )
        lines_after_first = log_path.read_bytes().splitlines()
        assert len(lines_after_first) == 1, "populate-check: exactly one line after one call"
        first_line_bytes = lines_after_first[0]

        graph_connection.execute_cypher(
            "MATCH (g:Gene {id: $gene_id}) RETURN g LIMIT 1",
            {"gene_id": "NCBIGene:7157"},
            connection_factory=_graph_factory(),
        )
        lines_after_second = log_path.read_bytes().splitlines()
        assert len(lines_after_second) == 2
        assert lines_after_second[0] == first_line_bytes, (
            "the first written line must be byte-identical after a second append"
        )


# ---------------------------------------------------------------------------
# The one live arm. Opt-in, read-only, never PostHog.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPT_IN_VAR = "RUN_PREMISE_GATE"


def _load_env_explicitly() -> None:
    """Matches test_ncbi_efetch_premise.py's own technique exactly: an
    explicit read of `.env`, not an import-time dotenv side effect, which
    that gate's own history records as order-dependent and having broken
    once already (F-2.1-04).
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


def _opted_in() -> bool:
    _load_env_explicitly()
    return os.environ.get(_OPT_IN_VAR, "").strip().lower() in {"1", "true", "yes"}


def _langsmith_key_is_configured() -> bool:
    _load_env_explicitly()
    return config.langsmith_api_key() is not None


live_langsmith_gate = pytest.mark.skipif(
    not (_opted_in() and _langsmith_key_is_configured()),
    reason="needs RUN_PREMISE_GATE=1 and a real LANGSMITH_API_KEY; dormant by decision, "
    "following test_ncbi_efetch_premise.py's precedent for an expensive live gate",
)


class TestLiveLangSmithReachability:
    """The one arm in this file allowed to reach a real third party, and
    it is LangSmith only. NEVER PostHog: F-5.0-12 records the provisioned
    `POSTHOG_API_KEY` as a personal, account-wide read-write credential
    rather than the write-only project token capture is built to send, so
    no arm anywhere in this file may POST to PostHog, live-gated or not.

    `Client.info` is a property read against the configured LangSmith
    endpoint. It authenticates and confirms reachability without
    creating, writing, or mutating any real trace, run, or project.
    """

    @live_langsmith_gate
    def test_a_real_client_authenticates_and_reads_server_info(self) -> None:
        client = tracing.build_traced_client()
        info = client.info
        assert info is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
