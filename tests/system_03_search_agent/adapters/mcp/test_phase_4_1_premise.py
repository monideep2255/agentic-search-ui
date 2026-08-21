"""Phase 4.1 premise gate: `tracker/phase_4.1.md`.

The done-when this file pins (the phase's own "Phase premise" section): a
caller holding a valid bearer token for its own `User` account calls the
single advertised MCP tool, `ask_biomedical_question`, and gets back one
JSON result, never a stream, folded from the same core agent loop every
other surface drives. No `think`, `plan`, or `tool_start` event ever
reaches it. A query with no groundable answer gets the honest refusal
string with no fabricated citations, the identical cite-or-refuse rule
every other surface already gets. No response ever carries a cost field,
for any caller, in any role, `operator_mode` hard-pinned false regardless
of `OPERATOR_USER_IDS` allowlist status. A caller with a missing,
malformed, or invalid bearer token never reaches the core loop at all: no
run is created, no budget is spent, and the caller gets a protocol-level
auth failure. `list_tools()` advertises exactly one tool; no internal tool
is ever separately reachable.

Driven through a REAL `mcp` client session (`mcp.client.streamable_http`,
`mcp.client.session.ClientSession`) against the real, mounted Starlette
sub-app inside the real FastAPI app, over `httpx2.ASGITransport`
(`httpx2` is the `mcp` SDK's own vendored httpx fork; see `pip show mcp`),
never a hand-rolled JSON-RPC payload. This is the same in-process pattern
`test_phase_4_0_premise.py` established for the REST/SSE surface
(`httpx.AsyncClient` + `ASGITransport` against the real app), extended for
the MCP transport's own requirements, two of which differ from that file's
convention and are surprising enough to be worth stating up front (full
account in `LEARNINGS.md`'s 2026-08-11 "Mounting the mcp==2.0.0 SDK's
streamable_http_app into FastAPI silently fails three separate ways"
entry):

    - `base_url` cannot be the REST/SSE gate's own `http://test`
      convention. The SDK auto-enables DNS-rebinding `Host`-header
      protection whenever `streamable_http_app()`'s `host` parameter is
      left at its default `127.0.0.1`, and the allowlist it builds
      (`127.0.0.1:*`, `localhost:*`, `[::1]:*`) requires an explicit port
      to match the wildcard suffix. `http://localhost:8000` (an arbitrary
      port) is used below instead.
    - A caller-built `httpx2.AsyncClient` passed as `http_client=` to
      `streamable_http_client` (needed here to inject a per-test bearer
      token via a custom `Authorization` header) bypasses the SDK's own
      `create_mcp_http_client()` default entirely, including its
      `follow_redirects=True`. Every helper below sets
      `follow_redirects=True` explicitly, since mounting the sub-app at
      `/mcp` with its own internal route at `/` (this phase's mount
      shape, `adapters/web_sse/app.py`) means a bare `POST /mcp` 307s to
      `/mcp/` before reaching the handler.

Fake event streams (`_golden_path_stream`, `_refusal_path_stream`, and so
on) monkeypatch `run_streaming` at `system_03_search_agent.core.
run_registry`, the exact seam `test_phase_4_0_premise.py` already
established this repo's tests use, for the same reason stated there: the
real `cypher_query` tool reaches the live Hetzner AGE graph over an SSH
tunnel this environment cannot open, and a controlled fake is also the
more correct test design for exercising the fold loop's own behavior
(what it does with a given event sequence), not any one live NCBI answer.

Not covered by this gate, stated per `.claude/rules/goal-contracts.md`'s
coverage-declaration discipline (mirrors `tracker/phase_4.1.md`'s own "Not
covered by this gate" note): real interop against an external MCP host
(Claude Desktop or another live MCP client); true multi-process behavior
and load-scale concurrency across many simultaneous MCP clients (build
phase 6.0's territory); and OAuth 2.0/OIDC alignment, since this phase
deliberately keeps the SDK's own OAuth provider machinery unwired in favor
of the existing bearer-JWT mechanism.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx2
import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from mcp_types import REQUEST_TIMEOUT, CallToolResult

from system_03_search_agent.contracts.events import (
    CitationPayload,
    CostPayload,
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
    PlanPayload,
    ThinkPayload,
    TokenPayload,
    ToolResultPayload,
    ToolStartPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)

_TEST_AUTH_SECRET = "test-only-auth-secret-for-phase-4-1-premise-tests-do-not-reuse"
_BASE_URL = "http://localhost:8000"
_INTERNAL_TOOL_NAMES = {
    "cypher_query",
    "ncbi_efetch",
    "ncbi_dbsnp",
    "pubtator_annotate",
    "litvar2_lookup",
    "pathogen_detection",
    "clinicaltrials_search",
}


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


# ---------------------------------------------------------------------------
# Fake event-stream fixtures: monkeypatch `run_streaming` so the fold loop
# is exercised against a controlled, deterministic sequence rather than a
# live graph/API call this environment cannot reach.
# ---------------------------------------------------------------------------


def _event(event_type: str, trace_id: str, seq: int, payload: object) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),  # type: ignore[attr-defined]
    )


async def _golden_path_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A full, successful run: every one of the eleven event types fires,
    including `think`/`plan`/`tool_start`/`tool_result`/`cost`, the ones
    Section 13.2 requires the MCP adapter to fold OUT entirely. Also pins
    the "Event folding" arm's second half: a run that DOES emit them must
    still complete without the fold loop hanging or crashing.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "think",
        trace_id,
        1,
        ThinkPayload(
            narrative="classified as a single-hop lookup",
            query_class="single_hop",
            resolved_entities=[],
            clarifying_question=None,
        ),
    )
    yield _event(
        "plan",
        trace_id,
        2,
        PlanPayload(narrative="dispatch cypher_query", tool_calls=[]),
    )
    yield _event(
        "tool_start",
        trace_id,
        3,
        ToolStartPayload(call_id="call-1", tool="cypher_query", layer="layer_1_graph", status="ok"),
    )
    yield _event(
        "tool_result",
        trace_id,
        4,
        ToolResultPayload(
            call_id="call-1",
            tool="cypher_query",
            layer="layer_1_graph",
            status="ok",
            summary="found 1 row",
            result_count=1,
            truncated=False,
        ),
    )
    yield _event(
        "token",
        trace_id,
        5,
        TokenPayload(text="BRCA1 is a protein-coding gene [1]. ", marker_ids=["c1"]),
    )
    yield _event(
        "citation",
        trace_id,
        6,
        CitationPayload(
            citation_id="c1",
            display_index=1,
            source="ncbi_gene",
            source_id="672",
            source_url="https://www.ncbi.nlm.nih.gov/gene/672",
            layer="layer_1_graph",
            field="symbol",
            claim_text="BRCA1 is a protein-coding gene.",
            evidence_kind="direct",
            assertion_confidence="high",
            population_ancestry_context=None,
            license="public-domain",
        ),
    )
    yield _event(
        "trust_signal",
        trace_id,
        7,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id="c1",
            scope="claim",
        ),
    )
    yield _event(
        "trust_signal",
        trace_id,
        8,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id=None,
            scope="answer",
        ),
    )
    yield _event(
        "cost",
        trace_id,
        9,
        CostPayload(query_cost_usd=0.0123, query_cap_usd=1.0, cap_fraction=0.0123, model_tier="synth"),
    )
    yield _event(
        "done",
        trace_id,
        10,
        DonePayload(total_cost_usd=0.0123, total_tool_calls=1, elapsed_ms=120, trust_outcome="answer"),
    )


async def _refusal_path_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A run that reaches Write but has nothing groundable to cite: the
    same cite-or-refuse shape `core/graph.py`'s `write_node` itself emits
    on its refusal branch (a `token` carrying the refusal text, an
    answer-scope `trust_signal` with `outcome="refuse"`), never a
    different or weaker refusal wording for this surface.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token",
        trace_id,
        1,
        TokenPayload(text="I could not find information on this in the available sources. ", marker_ids=[]),
    )
    yield _event(
        "trust_signal",
        trace_id,
        2,
        TrustSignalPayload(
            outcome="refuse",
            risk_tier="low",
            grounded=False,
            triangulated=None,
            citation_id=None,
            scope="answer",
            message="No groundable citation was found for this query.",
            fallback_link="https://www.ncbi.nlm.nih.gov/gene/",
        ),
    )
    yield _event(
        "cost",
        trace_id,
        3,
        CostPayload(query_cost_usd=0.0050, query_cap_usd=1.0, cap_fraction=0.005, model_tier="synth"),
    )
    yield _event(
        "done",
        trace_id,
        4,
        DonePayload(total_cost_usd=0.0050, total_tool_calls=1, elapsed_ms=90, trust_outcome="refuse"),
    )


async def _guardrail_refusal_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """F-4.1-J-03 (judge round 1): the exact shape `core/graph.py`'s
    `_decline_for_guardrail` emits (verified against that function
    directly): a `guard` event with `passed=False`, then `done` with
    `trust_outcome="refuse"`. The graph never reaches `write_node` on this
    path, so there is no `token` event at all, which is what makes
    `_fallback_answer_text`'s guard-failure branch (`server.py` lines
    183-188) and the synthetic answer-scope `trust_signal` fallback
    (lines 248-257) the only way this run shape can produce a response.
    """
    trace_id = query.trace_id
    yield _event(
        "guard",
        trace_id,
        0,
        GuardPayload(passed=False, category="off_topic", reason="not a biomedical question"),
    )
    yield _event(
        "done",
        trace_id,
        1,
        DonePayload(total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=15, trust_outcome="refuse"),
    )


async def _daily_cap_decline_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """F-4.1-J-03: the exact shape `core/graph.py`'s `_decline_for_daily_cap`
    emits (verified against that function directly): a fatal `error` event,
    then `done` with `trust_outcome="refuse"`. No `guard` event and no
    `token` event fire on this path, so this is the run shape that reaches
    `_fallback_answer_text`'s fatal-error branch (`server.py` lines
    189-190), not its guard-failure branch, and it is also the only fake
    stream in this file that exercises the fold loop's fatal-error capture
    (`server.py` lines 239-241).
    """
    trace_id = query.trace_id
    yield _event(
        "error",
        trace_id,
        0,
        ErrorPayload(
            fatal=True,
            scope="run",
            source="guardrail",
            error_class="recoverable",
            message="daily query cap exceeded for this account",
            retry_after_s=0,
        ),
    )
    yield _event(
        "done",
        trace_id,
        1,
        DonePayload(total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=10, trust_outcome="refuse"),
    )


def _citation(citation_id: str, display_index: int, source_id: str = "672") -> CitationPayload:
    """Shared citation builder for the fixtures below, since several of
    them need one or many well-formed `CitationPayload`s and only
    `citation_id`/`display_index` genuinely vary between them."""
    return CitationPayload(
        citation_id=citation_id,
        display_index=display_index,
        source="ncbi_gene",
        source_id=source_id,
        source_url=f"https://www.ncbi.nlm.nih.gov/gene/{source_id}",
        layer="layer_1_graph",
        field="symbol",
        claim_text="BRCA1 is a protein-coding gene.",
        evidence_kind="direct",
        assertion_confidence="high",
        population_ancestry_context=None,
        license="public-domain",
    )


async def _fatal_error_after_partial_answer_stream(
    query: Query, context: RequestContext
) -> AsyncIterator[Event]:
    """F-4.1-A-01 (adversary round 1): the adversary's own exact repro
    shape, a run that dies on a fatal error AFTER already emitting a
    partial, confidently-grounded `token`/`citation`/answer-scope
    `trust_signal`. `fatal=True` ends the stream (`RunRegistry.subscribe`
    stops on the first fatal error, no `done` follows), the same shape
    `core/run.py`'s `_crash_fallback_events` and a cancellation
    (`_drive_run`'s `except asyncio.CancelledError` branch,
    `core/run_registry.py`) both produce.

    `error_payload.message` below deliberately carries fabricated internal
    detail (a DB host, user, and secret marker) so this fixture doubles as
    F-4.1-A-09's repro: none of it may reach the caller.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token",
        trace_id,
        1,
        TokenPayload(text="Tamoxifen is contraindicated ", marker_ids=["c1"]),
    )
    yield _event("citation", trace_id, 2, _citation("c1", 1))
    yield _event(
        "trust_signal",
        trace_id,
        3,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id=None,
            scope="answer",
        ),
    )
    yield _event(
        "error",
        trace_id,
        4,
        ErrorPayload(
            fatal=True,
            scope="run",
            source="synth_model",
            error_class="unexpected",
            message="OperationalError: host=10.0.0.5 user=age_reader SECRET_MARKER_XYZ",
            retry_after_s=0,
        ),
    )


async def _slow_answer_then_hang_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """F-4.1-A-05: emits a partial, confidently-grounded answer, then
    hangs (rather than completing) so a test can cancel the run from
    outside mid-flight, the same interleaving the adversary used
    (`default_registry.cancel_run(run_id)` called while the fold loop is
    still awaiting `subscribe()`).
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token",
        trace_id,
        1,
        TokenPayload(text="The recommended dose is 20 mg ", marker_ids=[]),
    )
    yield _event(
        "trust_signal",
        trace_id,
        2,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id=None,
            scope="answer",
        ),
    )
    await asyncio.sleep(3600)
    yield _event(  # pragma: no cover - never reached, cancelled first
        "done",
        trace_id,
        3,
        DonePayload(total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=1000, trust_outcome="answer"),
    )


async def _claim_scoped_only_high_risk_stream(
    query: Query, context: RequestContext
) -> AsyncIterator[Event]:
    """F-4.1-A-02: the adversary's own exact repro shape, two claim-scoped
    `trust_signal` events (`flag`/`high`/ungrounded/non-triangulated) and
    NO answer-scope one, with a `done.trust_outcome="answer"` that must
    never be allowed to win over what the claims actually said.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token",
        trace_id,
        1,
        TokenPayload(
            text="Tamoxifen is indicated for this BRCA1 carrier at 20 mg daily [1][2]. ",
            marker_ids=["c1", "c2"],
        ),
    )
    yield _event("citation", trace_id, 2, _citation("c1", 1))
    yield _event("citation", trace_id, 3, _citation("c2", 2, source_id="7157"))
    yield _event(
        "trust_signal",
        trace_id,
        4,
        TrustSignalPayload(
            outcome="flag",
            risk_tier="high",
            grounded=False,
            triangulated=False,
            citation_id="c1",
            scope="claim",
        ),
    )
    yield _event(
        "trust_signal",
        trace_id,
        5,
        TrustSignalPayload(
            outcome="flag",
            risk_tier="high",
            grounded=False,
            triangulated=False,
            citation_id="c2",
            scope="claim",
        ),
    )
    yield _event(
        "done",
        trace_id,
        6,
        DonePayload(total_cost_usd=0.01, total_tool_calls=1, elapsed_ms=100, trust_outcome="answer"),
    )


async def _uncited_confident_answer_stream(
    query: Query, context: RequestContext
) -> AsyncIterator[Event]:
    """F-4.1-A-03: the adversary's own exact repro shape, a confident
    `token` with ZERO `citation` events and ZERO `trust_signal` events,
    ending in `done.trust_outcome="answer"`. Nothing here was verified;
    `grounded` must not claim otherwise.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token",
        trace_id,
        1,
        TokenPayload(
            text="The recommended starting dose of tamoxifen for this indication is 20 mg daily.",
            marker_ids=[],
        ),
    )
    yield _event(
        "done",
        trace_id,
        2,
        DonePayload(total_cost_usd=0.0, total_tool_calls=0, elapsed_ms=50, trust_outcome="answer"),
    )


async def _oversized_answer_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """F-4.1-A-04: emits over 8000 characters of pure whole-word content
    (`"ABCDE "` repeated), so a hard mid-word cut at exactly 8000 chars is
    trivially distinguishable from a word-boundary cut: a hard cut leaves
    a trailing fragment shorter than 5 characters, a word-boundary cut
    never does.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    word_chunk = "ABCDE " * 100  # 600 chars, whole words only
    seq = 1
    for _ in range(14):  # 14 * 600 = 8400 > 8000
        yield _event("token", trace_id, seq, TokenPayload(text=word_chunk, marker_ids=[]))
        seq += 1
    yield _event("citation", trace_id, seq, _citation("c1", 1))
    seq += 1
    yield _event(
        "trust_signal",
        trace_id,
        seq,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id=None,
            scope="answer",
        ),
    )
    seq += 1
    yield _event(
        "done",
        trace_id,
        seq,
        DonePayload(total_cost_usd=0.01, total_tool_calls=1, elapsed_ms=100, trust_outcome="answer"),
    )


async def _oversized_citation_list_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """F-4.1-A-08: emits 60 `citation` events, 10 over this surface's
    50-citation cap, so the fold loop must silently drop 10 but disclose
    that it did.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token", trace_id, 1, TokenPayload(text="Many findings support this. ", marker_ids=[])
    )
    seq = 2
    for i in range(60):
        yield _event("citation", trace_id, seq, _citation(f"c{i}", i + 1, source_id=str(i)))
        seq += 1
    yield _event(
        "trust_signal",
        trace_id,
        seq,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id=None,
            scope="answer",
        ),
    )
    seq += 1
    yield _event(
        "done",
        trace_id,
        seq,
        DonePayload(total_cost_usd=0.01, total_tool_calls=1, elapsed_ms=100, trust_outcome="answer"),
    )


async def _never_terminating_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """F-4.1-A-06: emits one event, then hangs forever. Neither `done` nor
    a fatal `error` ever arrives, so `RunRegistry.subscribe` never
    terminates on its own; only the fold loop's own wall-clock bound can
    end this.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    await asyncio.sleep(3600)


# ---------------------------------------------------------------------------
# MCP client helpers: a real client session against the real mounted app.
# ---------------------------------------------------------------------------


def _build_test_mcp_app() -> FastAPI:
    """Build a throwaway FastAPI app mounting the real `mcp_server`
    singleton at `/mcp`, using the exact same recipe
    `adapters/web_sse/app.py` uses in production: `streamable_http_path
    ="/"`, an explicit `lifespan=` entering the sub-app's own lifespan via
    `AsyncExitStack` (see that module's comment for why both are
    required, and `LEARNINGS.md`'s 2026-08-11 entry for the full account).

    Built fresh per call rather than reusing the production `app`
    object's own already-mounted sub-app instance: `MCPServer.
    streamable_http_app()` builds a brand new `StreamableHTTPSessionManager`
    on every call, and that manager's `run()` (entered via the lifespan
    below) may only execute once per instance for its whole lifetime, the
    same one-shot startup/shutdown a real server's single long-lived
    process also only does once. A production server enters it exactly
    once and serves many requests through that one instance; this test
    file makes many independent, isolated calls across many separate test
    functions, so each call gets its own fresh instance instead, matching
    the isolation every other fixture in this file already provides
    (`run_streaming` monkeypatched fresh per test, a fresh `User` signed
    up fresh per test). This still exercises the real, singleton
    `mcp_server` object (the real registered tool, the real auth code
    path via `Context.headers`), just mounted through a fresh wrapper
    each call instead of reusing `adapters/web_sse/app.py`'s literal
    module-level `app` object for the MCP calls specifically.
    """
    from system_03_search_agent.adapters.mcp.server import server as mcp_server

    sub_app = mcp_server.streamable_http_app(stateless_http=True, streamable_http_path="/")

    @asynccontextmanager
    async def _test_lifespan(test_app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(sub_app.router.lifespan_context(sub_app))
            yield

    test_app = FastAPI(lifespan=_test_lifespan)
    test_app.mount("/mcp", sub_app)
    return test_app


def _http_client(mcp_app: FastAPI, headers: Mapping[str, str] | None) -> httpx2.AsyncClient:
    return httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=mcp_app),
        base_url=_BASE_URL,
        headers=dict(headers) if headers else None,
        follow_redirects=True,
    )


async def _list_tools(headers: Mapping[str, str] | None = None) -> list[Any]:
    mcp_app = _build_test_mcp_app()
    async with (
        mcp_app.router.lifespan_context(mcp_app),
        _http_client(mcp_app, headers) as http_client,
        streamable_http_client(f"{_BASE_URL}/mcp", http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.list_tools()
        return list(result.tools)


async def _call_tool(
    headers: Mapping[str, str] | None, arguments: dict[str, object]
) -> CallToolResult:
    mcp_app = _build_test_mcp_app()
    async with (
        mcp_app.router.lifespan_context(mcp_app),
        _http_client(mcp_app, headers) as http_client,
        streamable_http_client(f"{_BASE_URL}/mcp", http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        return await session.call_tool("ask_biomedical_question", arguments)


async def _call_tool_with_raw_headers(
    raw_headers: list[tuple[str, str]], arguments: dict[str, object]
) -> CallToolResult:
    """F-4.1-A-11: like `_call_tool`, but takes a raw list of `(name,
    value)` pairs rather than a `Mapping`, so a genuine DUPLICATE header
    (two `Authorization` entries, not merely two different casings of the
    same one) can actually be sent. `_http_client`'s `dict(headers)`
    conversion cannot express this: a `dict` can only ever hold one value
    per key.
    """
    mcp_app = _build_test_mcp_app()
    async with (
        mcp_app.router.lifespan_context(mcp_app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=mcp_app), base_url=_BASE_URL, follow_redirects=True
        ) as http_client,
    ):
        http_client.headers = httpx2.Headers(raw_headers)
        async with (
            streamable_http_client(f"{_BASE_URL}/mcp", http_client=http_client) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            return await session.call_tool("ask_biomedical_question", arguments)


def _find_all(schema_fragment: object, key: str) -> list[object]:
    """Recursively collect every value found under `key` anywhere in a
    JSON-schema-shaped dict/list structure, since Pydantic's exact
    `anyOf`/`$ref` shape for an optional or nested field is an
    implementation detail this gate should not overfit to.
    """
    found: list[object] = []
    if isinstance(schema_fragment, dict):
        for k, v in schema_fragment.items():
            if k == key:
                found.append(v)
            found.extend(_find_all(v, key))
    elif isinstance(schema_fragment, list):
        for item in schema_fragment:
            found.extend(_find_all(item, key))
    return found


def _resolve_ref(schema: dict[str, Any], ref: str) -> dict[str, Any]:
    assert ref.startswith("#/$defs/"), ref
    return schema["$defs"][ref.removeprefix("#/$defs/")]


def _first_mcp_error(exc: BaseException) -> MCPError:
    """Recursively unwrap however many levels of `anyio.TaskGroup`-induced
    `BaseExceptionGroup` separate an `MCPError` from the caller, regardless
    of depth.

    T-4.1-01's original premise gate found exactly one level of nesting
    (auth failures, raised before `RunRegistry.create_run` is ever
    reached) and unwrapped it with a single `except* MCPError`. Fix round
    2 (F-4.1-A-06, F-4.1-A-13) added `MCPError`-raising checks that run
    LATER in the same call, after auth has already succeeded and the tool
    body is deeper into its own `async with`/task-group nesting; those
    raise through one MORE level of `BaseExceptionGroup` than the original
    helper assumed (confirmed directly: `_call_tool_expecting_mcp_error`'s
    old single-level `except*` returned a still-wrapped `ExceptionGroup`
    for these two new cases, not a bare `MCPError`). Rather than
    special-case a second exact depth, this walks the tree until it finds
    a bare `MCPError` leaf, so it is correct for either shape.
    """
    if isinstance(exc, MCPError):
        return exc
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            try:
                return _first_mcp_error(sub)
            except AssertionError:
                continue
    raise AssertionError(f"no MCPError found in exception tree: {exc!r}")


async def _call_tool_expecting_mcp_error(
    headers: Mapping[str, str] | None, arguments: dict[str, object]
) -> MCPError:
    """Call the tool and return the underlying `MCPError`, however many
    `anyio.TaskGroup`-induced `BaseExceptionGroup` layers separate it from
    the caller. See `_first_mcp_error` for why this recurses to whatever
    depth is actually present, rather than assuming one fixed depth.
    """
    try:
        await _call_tool(headers, arguments)
    except MCPError as exc:
        return exc
    except BaseExceptionGroup as eg:
        return _first_mcp_error(eg)
    raise AssertionError("expected an MCPError, none was raised")


async def _call_tool_with_raw_headers_expecting_mcp_error(
    raw_headers: list[tuple[str, str]], arguments: dict[str, object]
) -> MCPError:
    """`_call_tool_expecting_mcp_error`'s sibling for `_call_tool_with_raw_
    headers` (F-4.1-A-11), same recursive unwrap, same reason."""
    try:
        await _call_tool_with_raw_headers(raw_headers, arguments)
    except MCPError as exc:
        return exc
    except BaseExceptionGroup as eg:
        return _first_mcp_error(eg)
    raise AssertionError("expected an MCPError, none was raised")


# Section 13.2's own response shape, restated here as an explicit ALLOWLIST
# (F-4.1-A-07, adversary round 1, fix round 2): the resolved key set of the
# WHOLE response tree, not a fixed list of forbidden names. A denylist
# only catches a leak shaped like something someone already thought to
# name; an allowlist catches ANY key outside this pinned set, including a
# renamed cost field a denylist was never updated to include. Keys are
# deduplicated across the three models (`AskBiomedicalQuestionOutput`,
# `CitationPayload`, `TrustSignalPayload`) since `citation_id` is a real
# field on both the latter two.
# The TOP-LEVEL response keys, stated once and used by every arm that pins
# the whole shape. Three separate copies of this set existed and adding one
# optional field to Section 13.2's response had to be made in all three, which
# is drift waiting to happen: an arm holding a stale copy fails for a reason
# that has nothing to do with the property it guards, and the pressure is then
# to "just update it", which is how a real leak gets waved through.
#
# Still hand-maintained, deliberately. Deriving it from the response models is
# the weakening the allowlist comment below warns against, because a leak added
# to a model would then be added to its own expected set automatically.
_EXPECTED_TOP_LEVEL_KEYS = {
    "answer",
    "citations",
    "trust_signal",
    "run_id",
    # F-4.5-A-21, optional, so `output_schema["required"]` stays exactly the
    # four fields Section 13.2 locks. See the allowlist entry below.
    "persona_name",
}

_ALLOWED_RESPONSE_KEYS = {
    # AskBiomedicalQuestionOutput
    "answer",
    "citations",
    "trust_signal",
    "run_id",
    # Build phase 4.5's post-merge review round, F-4.5-A-21. Added by the
    # LEAD, not by the agent that added the field to the output model, and
    # with the product owner's explicit approval on 2026-08-20, because
    # this allowlist is a deliberate manual control and editing a gate to
    # make your own change pass is what `goal-contracts.md` forbids. The
    # agent that wrote the source change stopped here and escalated rather
    # than edit it, which is the control working.
    #
    # The same three tests the phase 4.10 entry below had to pass:
    #
    # 1. The property is unchanged: no cost data, and no key outside
    #    Section 13.2's pinned shape. MCP was the one surface of four left
    #    without a persona though the phase's ticket said all four, so the
    #    pinned shape genuinely grew rather than the assertion going stale.
    # 2. Additive and therefore v1-legal under Section 2.6: a new OPTIONAL
    #    field, so Section 13.2's four required fields are untouched.
    # 3. Not cost-adjacent, so the renamed-cost-field leak F-4.1-A-07
    #    exists to catch is still caught. The value is a server-side name
    #    drawn from a checked-in file of 32 deceased scientists: no user
    #    data, no cost data, no identifier.
    "persona_name",
    # CitationPayload
    "assertion_confidence",
    "citation_id",
    "claim_text",
    "display_index",
    "evidence_kind",
    "field",
    "layer",
    "license",
    "population_ancestry_context",
    "source",
    "source_id",
    "source_url",
    # Build phase 4.10, T-4.10-07. Added by the LEAD, not by the builder
    # that widened `CitationPayload`, and added deliberately rather than
    # mechanically, because editing a gate to make it pass is the exact
    # shape `goal-contracts.md` forbids. Three things make this contract
    # maintenance instead of a weakening, and all three had to hold:
    #
    # 1. The property this allowlist guarantees is unchanged: no cost data,
    #    and no key outside Section 13.2's pinned response shape. Section
    #    13.2's `CitationV1` IS `CitationPayload`, "reused verbatim, never
    #    redefined" (adapters/mcp/server.py's own docstring), so the pinned
    #    shape genuinely grew. An allowlist asserting a stale contract
    #    tests nothing; it just fails.
    # 2. The growth is additive and therefore v1-legal under Section 2.6
    #    (a new optional field), not a breaking change needing v2.
    # 3. Neither field is cost-adjacent, so the renamed-cost-field leak
    #    F-4.1-A-07 exists to catch is still caught. The negative test
    #    below (`spend_usd`/`tokens_billed`) still fails the allowlist,
    #    and was re-run to confirm it.
    #
    # This set stays a hand-maintained literal rather than being derived
    # from the three Pydantic models, which would have made this edit
    # unnecessary. Deriving it would be the real weakening: a cost field
    # added to a model would then be auto-accepted by the very check that
    # exists to catch it. The manual step IS the control.
    #
    # Pinned positively by `test_the_two_phase_4_10_citation_fields_are_
    # really_on_the_wire` below, so this entry cannot silently become
    # permission for fields that are not actually sent.
    "entity_name",
    "snapshot_date",
    # TrustSignalPayload
    "fallback_link",
    "grounded",
    "message",
    "outcome",
    "risk_tier",
    "scope",
    "triangulated",
}


def _all_response_keys(node: object) -> set[str]:
    """Recursively collect every DICT KEY (not value, unlike `_find_all`
    above) anywhere in a structured-content-shaped dict/list tree, so the
    allowlist check below can assert "nothing outside this set", not just
    "these five names are absent".
    """
    keys: set[str] = set()
    if isinstance(node, dict):
        for k, v in node.items():
            keys.add(k)
            keys |= _all_response_keys(v)
    elif isinstance(node, list):
        for item in node:
            keys |= _all_response_keys(item)
    return keys


# ---------------------------------------------------------------------------
# DB-independent arms: tool surface and schema fidelity need no HTTP call,
# no auth, and no live database, so they run unconditionally (mirrors
# `test_phase_4_0_premise.py`'s split between registry-only tests above its
# DB-reachability skip and HTTP-driven tests below it).
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _require_mcp_server_module() -> None:
    """Every test in this file depends on `adapters/mcp/server.py`
    existing, whether it imports the module directly (`TestToolSurface`,
    `TestSchemaFidelity`) or drives it indirectly through the mounted app
    (every HTTP-driven class below). Importing it explicitly here means
    every test in this file fails uniformly with `ModuleNotFoundError`
    before that module exists, never a downstream symptom (an HTTP 404
    through an app that has nothing mounted at `/mcp` yet) that is
    accurate but not the clean, uniform signal this repo's failing-first
    discipline requires (LEARNINGS.md row 43: "every failure a
    ModuleNotFoundError, never a network fault or a fixture bug").
    """
    import system_03_search_agent.adapters.mcp.server  # noqa: F401


class TestToolSurface:
    @pytest.mark.asyncio
    async def test_exactly_one_tool_is_advertised(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        tools = await server.list_tools()
        assert [tool.name for tool in tools] == ["ask_biomedical_question"]

    @pytest.mark.asyncio
    async def test_no_internal_tool_name_is_separately_advertised(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        tools = await server.list_tools()
        advertised = {tool.name for tool in tools}
        assert advertised.isdisjoint(_INTERNAL_TOOL_NAMES)

    @pytest.mark.asyncio
    async def test_no_internal_tool_is_separately_callable(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        for internal_name in _INTERNAL_TOOL_NAMES:
            with pytest.raises(Exception):  # noqa: B017 - any rejection is correct here
                await server.call_tool(internal_name, {})


class TestSchemaFidelity:
    @pytest.mark.asyncio
    async def test_input_schema_matches_section_13_2(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        tools = await server.list_tools()
        input_schema = tools[0].input_schema

        assert input_schema["required"] == ["query"]
        assert input_schema["properties"]["query"]["maxLength"] == 2000
        assert set(input_schema["properties"]["audience_depth"]["enum"]) == {
            "clinical_brief",
            "researcher",
            "deep_technical",
        }
        assert 64 in _find_all(input_schema["properties"]["session_id"], "maxLength")

    @pytest.mark.asyncio
    async def test_output_schema_matches_section_13_2(self) -> None:
        from system_03_search_agent.adapters.mcp.server import server

        tools = await server.list_tools()
        output_schema = tools[0].output_schema

        assert set(output_schema["required"]) == {"answer", "citations", "trust_signal", "run_id"}
        assert output_schema["properties"]["answer"]["maxLength"] == 8000
        assert output_schema["properties"]["run_id"]["maxLength"] == 64
        citations_prop = output_schema["properties"]["citations"]
        assert citations_prop["maxItems"] == 50
        assert citations_prop["type"] == "array"

        trust_signal_prop = output_schema["properties"]["trust_signal"]
        if "$ref" in trust_signal_prop:
            trust_signal_schema = _resolve_ref(output_schema, trust_signal_prop["$ref"])
        else:
            trust_signal_schema = trust_signal_prop
        assert trust_signal_schema["type"] == "object"


class TestFallbackAnswerText:
    """F-4.1-J-03 (judge round 1): direct unit coverage of `server.py`'s
    `_extract_bearer_header` (the `headers is None` branch, line 141) and
    `_fallback_answer_text` (its whole body, lines 183-191), the two
    smallest units the fold loop's defensive branches decompose into.
    Needs no HTTP call, no MCP client session, and no database, so these
    run unconditionally alongside `TestToolSurface`/`TestSchemaFidelity`
    above.
    """

    @pytest.mark.asyncio
    async def test_ctx_with_no_headers_attribute_value_returns_none(self) -> None:
        """`Context.headers` returns `None` "when the transport has them"
        is false (the SDK's own docstring, `mcpserver/context.py:279`), for
        example a non-HTTP transport. `_extract_bearer_header` must not
        raise on that shape and must simply report no bearer value found,
        covers `server.py` line 141.
        """
        from system_03_search_agent.adapters.mcp.server import _extract_bearer_header

        class _CtxWithNoHeaders:
            headers = None

        assert _extract_bearer_header(_CtxWithNoHeaders()) is None  # type: ignore[arg-type]

    def test_guard_failure_produces_guard_specific_refusal_wording(self) -> None:
        """Covers `server.py` lines 183-188: the branch used for a
        guardrail-level refusal (`_decline_for_guardrail`'s run shape,
        which emits no `token` event)."""
        from system_03_search_agent.adapters.mcp.server import _fallback_answer_text

        text = _fallback_answer_text(
            guard_payload=GuardPayload(passed=False, category="off_topic", reason="not biomedical"),
            error_payload=None,
        )
        assert "guardrail" in text.lower()
        assert "not biomedical" in text

    def test_fatal_error_produces_error_specific_wording(self) -> None:
        """Covers `server.py`'s fatal-error branch: the branch used for a
        fatal step-level error before Write ever ran (`_decline_for_daily_
        cap`'s run shape, which also emits no `token` event).

        F-4.1-A-09 (adversary round 1, fix round 2): the raw `ErrorPayload.
        message` (internal text; the adversary demonstrated a real DB
        host, port, username, and database name leaking this way in a
        different repro) must never reach the returned text verbatim. The
        sanitized, `error_class`-keyed sentence is asserted instead, and
        the raw message is asserted ABSENT, not merely that some text is
        present.
        """
        from system_03_search_agent.adapters.mcp.server import _fallback_answer_text

        text = _fallback_answer_text(
            guard_payload=None,
            error_payload=ErrorPayload(
                fatal=True,
                scope="run",
                source="guardrail",
                error_class="recoverable",
                message="daily query cap exceeded for this account",
                retry_after_s=0,
            ),
        )
        assert "daily query cap exceeded for this account" not in text
        assert text == "This query could not complete as requested."

    def test_no_guard_and_no_error_produces_the_generic_catch_all_wording(self) -> None:
        """Covers `server.py` line 191: the final defensive fallback for a
        run that terminates with no `token`, no guard failure, and no
        fatal error captured, a shape no named run path in `core/graph.py`
        currently produces but that this function still guards against."""
        from system_03_search_agent.adapters.mcp.server import _fallback_answer_text

        text = _fallback_answer_text(guard_payload=None, error_payload=None)
        assert text == "This query could not be completed: the run ended before producing an answer."


class TestTrustSignalHelpers:
    """Fix round 2 (adversary round 1's F-4.1-A-01/02/04): direct unit
    coverage of the new pure helper functions `_fold_run_to_response`
    delegates to, since each is small, has no loop context, and is
    cheapest to pin exactly the way `TestFallbackAnswerText` above
    already pins `_fallback_answer_text`. Needs no HTTP call, no MCP
    client session, and no database.
    """

    def test_claim_aggregation_floors_at_the_worst_claim_not_a_default(self) -> None:
        """F-4.1-A-02's core property, at the unit level: two `flag`/
        `high`/ungrounded/non-triangulated claims must never average or
        default to anything better than what they actually said."""
        from system_03_search_agent.adapters.mcp.server import _aggregate_claim_trust_signals

        claims = [
            TrustSignalPayload(
                outcome="flag", risk_tier="high", grounded=False, triangulated=False,
                citation_id="c1", scope="claim",
            ),
            TrustSignalPayload(
                outcome="flag", risk_tier="high", grounded=False, triangulated=False,
                citation_id="c2", scope="claim",
            ),
        ]
        result = _aggregate_claim_trust_signals(claims, terminal_trust_outcome="answer")
        assert result.outcome == "flag"
        assert result.risk_tier == "high"
        assert result.grounded is False
        assert result.triangulated is False
        assert result.scope == "answer"

    def test_claim_aggregation_outcome_is_the_most_restrictive_present(self) -> None:
        """`aggregate`'s own most-restrictive-wins rule, exercised through
        this function: `refuse` outranks `ask` outranks `flag` outranks
        `answer`, so a mix picks the worst regardless of order."""
        from system_03_search_agent.adapters.mcp.server import _aggregate_claim_trust_signals

        claims = [
            TrustSignalPayload(
                outcome="answer", risk_tier="low", grounded=True, triangulated=True,
                citation_id="c1", scope="claim",
            ),
            TrustSignalPayload(
                outcome="ask", risk_tier="low", grounded=True, triangulated=None,
                citation_id="c2", scope="claim",
            ),
        ]
        result = _aggregate_claim_trust_signals(claims, terminal_trust_outcome="answer")
        assert result.outcome == "ask"
        # grounded floors on ANY ungrounded claim; both claims here are
        # grounded, so it stays True (not force-lowered with no reason).
        assert result.grounded is True
        # triangulated floors at the worst of {True, None}: None (not
        # evaluated) is worse than True (evaluated, concords).
        assert result.triangulated is None

    def test_fatal_error_floor_never_raises_a_refuse_or_ask_outcome_to_flag(self) -> None:
        """F-4.1-A-01's floor must only ever LOWER `outcome`, never raise
        an already-more-restrictive one (`refuse`/`ask`) up to `flag`."""
        from system_03_search_agent.adapters.mcp.server import _floor_trust_signal_for_fatal_error

        already_refused = TrustSignalPayload(
            outcome="refuse", risk_tier="low", grounded=False, triangulated=None,
            citation_id=None, scope="answer",
        )
        floored = _floor_trust_signal_for_fatal_error(already_refused)
        assert floored.outcome == "refuse"
        assert floored.grounded is False
        assert floored.risk_tier == "high"

    def test_fatal_error_floor_lowers_a_confident_answer_to_flag(self) -> None:
        from system_03_search_agent.adapters.mcp.server import _floor_trust_signal_for_fatal_error

        confident = TrustSignalPayload(
            outcome="answer", risk_tier="low", grounded=True, triangulated=True,
            citation_id=None, scope="answer",
        )
        floored = _floor_trust_signal_for_fatal_error(confident)
        assert floored.outcome == "flag"
        assert floored.grounded is False
        assert floored.risk_tier == "high"

    def test_truncate_on_word_boundary_never_leaves_a_partial_word(self) -> None:
        from system_03_search_agent.adapters.mcp.server import _truncate_on_word_boundary

        text = "ABCDE " * 100  # 600 chars
        truncated = _truncate_on_word_boundary(text, 503)  # mid-word at a hard cut
        assert truncated.split(" ")[-1] == "ABCDE"
        assert len(truncated) <= 503

    def test_truncate_on_word_boundary_is_a_no_op_under_the_cap(self) -> None:
        from system_03_search_agent.adapters.mcp.server import _truncate_on_word_boundary

        assert _truncate_on_word_boundary("short answer", 8000) == "short answer"

    def test_merge_disclosure_messages_appends_and_caps_at_500(self) -> None:
        from system_03_search_agent.adapters.mcp.server import _merge_disclosure_messages

        merged = _merge_disclosure_messages("existing note.", ["new note one.", "new note two."])
        assert merged.startswith("existing note.")
        assert "new note one." in merged
        assert "new note two." in merged
        assert len(_merge_disclosure_messages(None, ["x" * 600])) == 500

    def test_reject_control_bytes_raises_on_nul_and_esc_never_on_ordinary_whitespace(self) -> None:
        from system_03_search_agent.adapters.mcp.server import _reject_control_bytes

        with pytest.raises(ValueError, match="control characters"):
            _reject_control_bytes("BRCA1" + chr(0))
        with pytest.raises(ValueError, match="control characters"):
            _reject_control_bytes("BRCA1" + chr(27) + "[31m")
        # Tab, newline, carriage return: never rejected.
        assert _reject_control_bytes("line one\nline two\ttabbed\rcr") == "line one\nline two\ttabbed\rcr"

    def test_allowlist_catches_a_renamed_cost_leak_the_old_denylist_missed(self) -> None:
        """F-4.1-A-07 (adversary round 1, fix round 2): proves the
        allowlist check below is not merely differently worded, it
        actually catches a leak shape the old fixed five-name denylist
        missed. Reconstructs the adversary's own exact mutation
        (`spend_usd`, `tokens_billed` one level down inside
        `trust_signal`) as a synthetic response dict, the same method
        judge round 2 used to prove F-4.1-J-01's own repair (a
        before/after comparison against the identical input), rather than
        mutating `contracts/events.py` itself, which would be a much
        larger blast radius for a test file to carry.
        """
        leaking_content = {
            "answer": "x",
            "citations": [],
            "run_id": "r1",
            "trust_signal": {
                "outcome": "answer",
                "risk_tier": "low",
                "grounded": True,
                "spend_usd": 7.77,
                "tokens_billed": 4242,
            },
        }
        old_denylist = ("cost", "total_cost_usd", "query_cost_usd", "query_cap_usd", "cap_fraction")
        assert all(_find_all(leaking_content, key) == [] for key in old_denylist), (
            "the renamed leak must not match any OLD denylist name, or this "
            "test would not demonstrate the gap the allowlist closes"
        )
        assert not _all_response_keys(leaking_content) <= _ALLOWED_RESPONSE_KEYS

    def test_the_two_phase_4_10_citation_fields_are_really_on_the_wire(self) -> None:
        """Build phase 4.10 widened `CitationPayload`, and therefore
        Section 13.2's `CitationV1`. This pins that the allowlist entries
        added for it are real rather than merely permissive.

        Without this, the two names added to `_ALLOWED_RESPONSE_KEYS`
        would be indistinguishable from permission granted to fields that
        no longer exist, and deleting them from the model would leave the
        allowlist quietly stale in the other direction. An allowlist entry
        with no positive counterpart is a hole waiting to be widened.
        """
        from system_03_search_agent.contracts.events import CitationPayload

        model_fields = set(CitationPayload.model_fields)
        assert {"snapshot_date", "entity_name"} <= model_fields, (
            "the allowlist permits these two keys; if the model no longer "
            "declares them, remove them from the allowlist rather than "
            "leaving it permissive"
        )
        assert model_fields <= _ALLOWED_RESPONSE_KEYS, (
            "every CitationPayload field must be on the allowlist, since "
            "Section 13.2's CitationV1 IS CitationPayload; a field on the "
            "model and off the allowlist fails the gate at runtime instead "
            "of here, which is a worse place to find out"
        )

    def test_allowlist_is_satisfied_by_a_genuinely_clean_response(self) -> None:
        """No false positives: a real golden-path-shaped response (every
        field `AskBiomedicalQuestionOutput`/`CitationPayload`/
        `TrustSignalPayload` can actually produce) must satisfy the
        allowlist with no unexpected key."""
        clean_content = {
            "answer": "x",
            "citations": [
                {
                    "citation_id": "c1",
                    "display_index": 1,
                    "source": "ncbi_gene",
                    "source_id": "672",
                    "source_url": "https://www.ncbi.nlm.nih.gov/gene/672",
                    "layer": "layer_1_graph",
                    "field": "symbol",
                    "claim_text": "x",
                    "evidence_kind": "direct",
                    "assertion_confidence": "high",
                    "population_ancestry_context": None,
                    "license": "public-domain",
                }
            ],
            "run_id": "r1",
            "trust_signal": {
                "outcome": "answer",
                "risk_tier": "low",
                "grounded": True,
                "triangulated": None,
                "citation_id": None,
                "scope": "answer",
                "message": None,
                "fallback_link": None,
            },
        }
        assert _all_response_keys(clean_content) <= _ALLOWED_RESPONSE_KEYS

    def test_reject_unknown_arguments_is_a_no_op_when_params_carry_no_arguments_dict(
        self,
    ) -> None:
        """`_reject_unknown_arguments`'s own defensive branch: a `Context`
        whose `request_context.params` is absent or not shaped like a real
        `tools/call` request (a shape this SDK does not produce today,
        confirmed by direct empirical probe against the installed wheel
        before this fix was written) must be treated as "nothing to
        check", never raised on. Duck-typed rather than a real `Context`,
        the same pattern `TestFallbackAnswerText`'s own `_CtxWithNoHeaders`
        already uses for the analogous `_extract_bearer_header` branch.
        """
        from system_03_search_agent.adapters.mcp.server import _reject_unknown_arguments

        class _RequestContextWithNoParams:
            params = None

        class _CtxWithNoParams:
            request_context = _RequestContextWithNoParams()

        _reject_unknown_arguments(_CtxWithNoParams())  # type: ignore[arg-type]

        class _RequestContextWithNoneArgs:
            params: ClassVar = {"name": "ask_biomedical_question"}  # no "arguments" key

        class _CtxWithNoArgumentsKey:
            request_context = _RequestContextWithNoneArgs()

        _reject_unknown_arguments(_CtxWithNoArgumentsKey())  # type: ignore[arg-type]

    def test_extra_forbid_structurally_rejects_an_undeclared_field(self) -> None:
        """F-4.1-A-07's stated structural fix, proven directly rather than
        only inferred from `model_config = ConfigDict(extra="forbid")`
        being present in the source: constructing any of the three output
        models with a field the schema does not declare must raise
        `ValidationError`, never silently accept and carry it along.
        """
        from pydantic import ValidationError

        from system_03_search_agent.adapters.mcp.server import AskBiomedicalQuestionOutput

        with pytest.raises(ValidationError):
            TrustSignalPayload(
                outcome="answer", risk_tier="low", grounded=True, triangulated=None,
                citation_id=None, scope="answer",
                spend_usd=7.77,  # type: ignore[call-arg]
            )
        with pytest.raises(ValidationError):
            CitationPayload(
                citation_id="c1", display_index=1, source="ncbi_gene", source_id="672",
                source_url="https://www.ncbi.nlm.nih.gov/gene/672", layer="layer_1_graph",
                field="symbol", claim_text="x", evidence_kind="direct",
                assertion_confidence="high", population_ancestry_context=None,
                license="public-domain",
                total_cost_usd=1.0,  # type: ignore[call-arg]
            )
        with pytest.raises(ValidationError):
            AskBiomedicalQuestionOutput(
                answer="x",
                citations=[],
                trust_signal=TrustSignalPayload(
                    outcome="answer", risk_tier="low", grounded=True, triangulated=None,
                    citation_id=None, scope="answer",
                ),
                run_id="r1",
                total_cost_usd=1.0,  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# HTTP-driven arms: golden path, refusal path, event folding, never-cost,
# and every auth arm. Needs `search_agent_users` PostgreSQL reachable for
# real signup/login (the same bearer-JWT mechanism every other surface
# uses; T-4.1-03 reuses `get_current_user`'s own decode-then-lookup logic,
# never a second auth system), and skips cleanly, not failing, when it is
# not.
# ---------------------------------------------------------------------------

if not _can_connect():
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; set "
        "USER_DB_URL and ensure the server is running to run the "
        "HTTP-driven half of the phase 4.1 premise gate (golden path, "
        "refusal path, event folding, never-cost, and every auth arm)",
        allow_module_level=True,
    )

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.core import run_registry as run_registry_module


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


async def _signup_and_login(client: httpx2.AsyncClient) -> tuple[str, dict[str, str]]:
    email, password = _unique_email(), "Str0ngPassw0rd!"
    signup = await client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    user_id = signup.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _real_user_headers() -> tuple[str, dict[str, str]]:
    """Sign up and log in a fresh throwaway `User` against the real app's
    own `/auth` router, over a plain (non-MCP) ASGI client, since `/auth`
    is not part of the MCP surface. Returns the new user's id and a
    ready-to-use `Authorization` header.
    """
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url=_BASE_URL
    ) as client:
        return await _signup_and_login(client)


class TestGoldenPath:
    @pytest.mark.asyncio
    async def test_a_real_question_returns_a_grounded_cited_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        assert content["answer"].strip() != ""
        assert len(content["citations"]) >= 1
        citation = content["citations"][0]
        for field in (
            "citation_id",
            "source",
            "source_id",
            "source_url",
            "layer",
            "field",
            "claim_text",
            "evidence_kind",
            "assertion_confidence",
            "license",
        ):
            assert field in citation
        assert content["trust_signal"] is not None
        assert content["run_id"]


class TestRefusalPath:
    @pytest.mark.asyncio
    async def test_a_zero_groundable_result_query_refuses_honestly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _refusal_path_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "an unanswerable question"})

        assert result.is_error is False
        content = result.structured_content
        assert content["citations"] == []
        assert content["trust_signal"]["outcome"] == "refuse"
        assert "could not find" in content["answer"].lower()


class TestEventFolding:
    @pytest.mark.asyncio
    async def test_folded_response_has_no_field_for_excluded_event_types(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Section 13.2's fold rule is a structural guarantee: the response
        object has no field named after any of the folded-out or folded-in
        event types, and a run emitting all eleven event types (the golden
        path fixture) still completes cleanly rather than hanging.
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        assert set(content.keys()) == _EXPECTED_TOP_LEVEL_KEYS
        for excluded_key in ("think", "plan", "tool_start", "token", "tool_result", "guard", "cost"):
            # F-4.1-J-01 (judge round 1): `_find_all(content, key)` returns
            # the VALUES found under `key` anywhere in the structure, not
            # the key names, so `excluded_key not in _find_all(...)` was
            # comparing a key name against a list of unrelated values and
            # could never be false. The correct check is that no value was
            # ever found under that key at all: the list itself is empty.
            assert _find_all(content, excluded_key) == [], (
                f"{excluded_key!r} leaked into the folded response"
            )


class TestNeverCost:
    @pytest.mark.asyncio
    async def test_an_operator_allowlisted_caller_still_gets_no_cost_field(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`operator_mode` is hard-pinned false for this surface: even a
        caller on the `OPERATOR_USER_IDS` allowlist gets a response with
        no cost-shaped field anywhere, proving the pin, not merely a
        default that happens to read false for a non-allowlisted caller.
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        user_id, headers = await _real_user_headers()
        monkeypatch.setenv("OPERATOR_USER_IDS", user_id)

        result = await _call_tool(headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        assert set(content.keys()) == _EXPECTED_TOP_LEVEL_KEYS
        for cost_key in ("cost", "total_cost_usd", "query_cost_usd", "query_cap_usd", "cap_fraction"):
            # F-4.1-J-01 (judge round 1): same fix as `TestEventFolding`
            # above. `_find_all` returns values found under `cost_key`, so
            # the assertion must check that list is empty, not that the
            # key name string is absent from that list of values.
            assert _find_all(content, cost_key) == []
        # F-4.1-A-07 (adversary round 1, fix round 2): the denylist loop
        # above only ever catches the five names someone already thought
        # to write down. Added rather than substituted (goal-contracts.md:
        # a verify surface may gain checks, never lose one), the allowlist
        # below catches ANY key outside Section 13.2's pinned response
        # shape, a renamed cost field included, over the REAL response
        # this live call actually produced.
        assert _all_response_keys(content) <= _ALLOWED_RESPONSE_KEYS


class TestUngroundedRunShapesFoldCorrectly:
    """F-4.1-J-03 (judge round 1): end-to-end coverage, through the real
    fold loop and a real MCP client call, of the two named run shapes that
    never reach `write_node` and therefore never emit a `token` event:
    `_decline_for_guardrail` and `_decline_for_daily_cap` (both in
    `core/graph.py`). These are the only run shapes that exercise
    `server.py`'s synthetic answer-scope `trust_signal` fallback (lines
    248-257), the empty-answer path that invokes `_fallback_answer_text`
    (line 261), and, for the daily-cap shape specifically, the fatal-error
    capture branch (lines 239-241).
    """

    @pytest.mark.asyncio
    async def test_guardrail_refusal_run_folds_to_a_fallback_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _guardrail_refusal_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "what is the capital of France"})

        assert result.is_error is False
        content = result.structured_content
        assert content["citations"] == []
        assert "guardrail" in content["answer"].lower()
        assert content["trust_signal"]["outcome"] == "refuse"
        assert content["trust_signal"]["scope"] == "answer"
        assert content["run_id"]

    @pytest.mark.asyncio
    async def test_daily_cap_decline_run_folds_to_a_fallback_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.1-A-09 (adversary round 1, fix round 2): the raw internal
        `ErrorPayload.message` ("daily query cap exceeded for this
        account") must never reach the answer text verbatim; the
        sanitized, generic sentence is asserted instead, and the raw
        message is asserted ABSENT end to end through the real fold loop
        and a real MCP client call, not just at the unit level.
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _daily_cap_decline_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        assert content["citations"] == []
        assert "daily query cap exceeded for this account" not in content["answer"]
        assert content["answer"] == "This query could not complete as requested."
        assert content["trust_signal"]["outcome"] == "refuse"
        assert content["trust_signal"]["scope"] == "answer"
        assert content["run_id"]


class TestFatalErrorDisclosure:
    """F-4.1-A-01, F-4.1-A-05, F-4.1-A-09 (adversary round 1, fix round
    2): a run that dies mid-flight must never come back as a complete,
    grounded, low-risk answer with no signal anything went wrong.
    """

    @pytest.mark.asyncio
    async def test_a_fatal_error_after_partial_text_floors_trust_and_discloses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.1-A-01's own exact repro, end to end through the real fold
        loop and a real MCP client call. Before this fix: `answer=
        'Tamoxifen is contraindicated'`, `trust_signal={'outcome':
        'answer', 'risk_tier': 'low', 'grounded': True}`, `is_error:
        False`, no disclosure anywhere. Also proves F-4.1-A-09 end to end:
        the fabricated internal detail in this fixture's `ErrorPayload.
        message` (a DB host, user, and secret marker) must not reach the
        caller in ANY field of the response.
        """
        monkeypatch.setattr(
            run_registry_module, "run_streaming", _fatal_error_after_partial_answer_stream
        )
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(
            headers, {"query": "Is tamoxifen contraindicated for this patient?"}
        )

        assert result.is_error is False
        content = result.structured_content
        # The partial text is preserved, not discarded: this is a
        # disclosure fix, not a silent-refusal fix.
        assert "Tamoxifen is contraindicated" in content["answer"]
        trust_signal = content["trust_signal"]
        assert trust_signal["outcome"] != "answer"
        assert trust_signal["grounded"] is False
        assert trust_signal["risk_tier"] == "high"
        assert trust_signal["message"]
        response_text = str(content)
        assert "10.0.0.5" not in response_text
        assert "age_reader" not in response_text
        assert "SECRET_MARKER_XYZ" not in response_text
        assert "OperationalError" not in response_text

    @pytest.mark.asyncio
    async def test_a_cancelled_run_floors_trust_and_discloses_the_stop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.1-A-05's own exact repro: `default_registry.cancel_run`
        called from OUTSIDE while `_fold_run_to_response` is still
        awaiting `subscribe()`, the interleaving the adversary used and
        the same path `POST /v1/query/{run_id}/stop` drives in production.
        Drives `_fold_run_to_response` directly against the real
        `default_registry` (no MCP client layer needed to prove this
        property, and the direct call is what lets this test control the
        exact interleaving), the same registry `adapters/web_sse/app.py`
        and the real tool handler both share.
        """
        from system_03_search_agent.adapters.mcp.server import _fold_run_to_response

        monkeypatch.setattr(run_registry_module, "run_streaming", _slow_answer_then_hang_stream)

        query_obj = Query(
            text="What is the recommended dose?",
            session_id="s-cancel-1",
            trace_id="t-cancel-1",
            user_id="u-cancel-1",
            audience_depth="researcher",
        )
        context = RequestContext(surface="mcp", operator_mode=False)
        run_id = run_registry_module.default_registry.create_run(
            query_obj, context, run_id="t-cancel-1"
        )

        fold_task = asyncio.create_task(_fold_run_to_response(run_id))
        await asyncio.sleep(0.2)
        run_registry_module.default_registry.cancel_run(run_id)

        response = await asyncio.wait_for(fold_task, timeout=5.0)

        assert "The recommended dose is 20 mg" in response.answer
        assert response.trust_signal.outcome != "answer"
        assert response.trust_signal.grounded is False
        assert response.trust_signal.risk_tier == "high"
        assert response.trust_signal.message is not None
        assert "stopped" in response.trust_signal.message.lower()


class TestClaimScopedTrustAggregation:
    """F-4.1-A-02 (adversary round 1, fix round 2), end to end."""

    @pytest.mark.asyncio
    async def test_claim_scoped_only_signals_never_synthesize_a_cheerful_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Before this fix: two `flag`/`high`/ungrounded/non-triangulated
        claim signals folded to a top-level `outcome: 'answer', risk_tier:
        'low', grounded: true`, the exact inversion of what the claims
        said. `done.trust_outcome="answer"` in this fixture must not win.
        """
        monkeypatch.setattr(
            run_registry_module, "run_streaming", _claim_scoped_only_high_risk_stream
        )
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(
            headers, {"query": "Is tamoxifen indicated for this BRCA1 carrier?"}
        )

        assert result.is_error is False
        content = result.structured_content
        assert len(content["citations"]) == 2
        trust_signal = content["trust_signal"]
        assert trust_signal["outcome"] == "flag"
        assert trust_signal["risk_tier"] == "high"
        assert trust_signal["grounded"] is False
        assert trust_signal["triangulated"] is False
        assert trust_signal["scope"] == "answer"


class TestUncitedAnswerGrounding:
    """F-4.1-A-03 (adversary round 1, fix round 2), end to end."""

    @pytest.mark.asyncio
    async def test_a_zero_citation_answer_is_never_reported_grounded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Before this fix: a confident `token`, zero citations, zero
        trust_signal events, `done.trust_outcome="answer"`, folded to
        `citations: [], trust_signal: {'grounded': True, ...}`. `grounded`
        must reflect whether a citation actually exists.
        """
        monkeypatch.setattr(
            run_registry_module, "run_streaming", _uncited_confident_answer_stream
        )
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "What is the recommended tamoxifen dose?"})

        assert result.is_error is False
        content = result.structured_content
        assert content["citations"] == []
        assert content["trust_signal"]["grounded"] is False
        # T-4.3-05, build phase 4.3 (closes F-4.1-J3-02): this run hits
        # `_fold_run_to_response`'s fully-silent fallback branch (zero
        # `trust_signal` events of any scope, and no fatal error to floor
        # it to "high"), so no risk assessment ever ran. "low" was the
        # other unearned assertion that same branch used to make; this
        # asserts the honest replacement. Mutation that turns this red:
        # restore the hardcoded `risk_tier="low"` in that branch.
        assert content["trust_signal"]["risk_tier"] == "unknown"


class TestAnswerAndCitationTruncationDisclosure:
    """F-4.1-A-04, F-4.1-A-08 (adversary round 1, fix round 2): a silent
    cap is a defect on a surface whose entire premise is trust, per the
    carried `F-4.0-A-12/A-13` precedent this phase did not originally
    pick up.
    """

    @pytest.mark.asyncio
    async def test_an_oversized_answer_is_truncated_on_a_word_boundary_and_disclosed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _oversized_answer_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        assert len(content["answer"]) <= 8000
        # Word-boundary, not a hard mid-word cut: the trailing token is a
        # complete "ABCDE", never a partial fragment.
        assert content["answer"].split(" ")[-1] == "ABCDE"
        assert "truncat" in content["trust_signal"]["message"].lower()

    @pytest.mark.asyncio
    async def test_an_oversized_citation_list_is_capped_and_disclosed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            run_registry_module, "run_streaming", _oversized_citation_list_stream
        )
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        content = result.structured_content
        assert len(content["citations"]) == 50
        message = content["trust_signal"]["message"].lower()
        assert "10" in content["trust_signal"]["message"]
        assert "omitted" in message


class TestFoldLoopWallClockBound:
    """F-4.1-A-06 (adversary round 1, fix round 2): a run that never
    reaches a terminal event must not hang this surface's single
    request/response call forever, and must not leak a permanently-
    watched registry entry.
    """

    @pytest.mark.asyncio
    async def test_a_never_terminating_run_times_out_with_an_actionable_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end proof through the real MCP client: the caller gets a
        protocol-level `MCPError`, never a hang and never a silent empty
        response (`.claude/rules/tool-call-budgets.md`'s "actionable
        error" rule). `_FOLD_LOOP_TIMEOUT_S` is monkeypatched down from
        its real 240s so this test does not itself hang.
        """
        import system_03_search_agent.adapters.mcp.server as mcp_server_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _never_terminating_stream)
        monkeypatch.setattr(mcp_server_module, "_FOLD_LOOP_TIMEOUT_S", 0.3)
        _user_id, headers = await _real_user_headers()

        error = await asyncio.wait_for(
            _call_tool_expecting_mcp_error(headers, {"query": "What gene is BRCA1?"}),
            timeout=10.0,
        )
        assert error.code == REQUEST_TIMEOUT
        assert error.message

    @pytest.mark.asyncio
    async def test_timeout_unsubscribes_so_the_registry_can_reclaim_the_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The stronger, direct proof: drives `_fold_run_to_response`
        against the REAL `default_registry` so `entry.subscriber_count`
        can be inspected after the timeout fires. Before this fix existed,
        there was no timeout to unsubscribe from at all; this also proves
        the specific mechanism (unsubscribing is an ordinary side effect
        of the timeout's `CancelledError` propagating through `RunRegistry.
        subscribe`'s own `try`/`finally`), the same mechanism verified in
        a standalone scratch probe before this fix was written.
        """
        import system_03_search_agent.adapters.mcp.server as mcp_server_module
        from system_03_search_agent.adapters.mcp.server import _fold_run_to_response

        monkeypatch.setattr(run_registry_module, "run_streaming", _never_terminating_stream)
        monkeypatch.setattr(mcp_server_module, "_FOLD_LOOP_TIMEOUT_S", 0.3)

        query_obj = Query(
            text="What gene is BRCA1?",
            session_id="s-timeout-1",
            trace_id="t-timeout-1",
            user_id="u-timeout-1",
            audience_depth="researcher",
        )
        context = RequestContext(surface="mcp", operator_mode=False)
        run_id = run_registry_module.default_registry.create_run(
            query_obj, context, run_id="t-timeout-1"
        )

        with pytest.raises(MCPError) as excinfo:
            await asyncio.wait_for(_fold_run_to_response(run_id), timeout=5.0)
        assert excinfo.value.code == REQUEST_TIMEOUT

        entry = run_registry_module.default_registry.get_run(run_id)
        assert entry.subscriber_count == 0

        # Cleanup: the underlying fake stream is still asleep for another
        # hour of wall-clock time; cancel its background task so it does
        # not outlive this test process.
        entry.task.cancel()


class TestAuth:
    @pytest.mark.asyncio
    async def test_missing_token_is_rejected_before_any_run_is_created(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_calls: list[object] = []
        original_create_run = run_registry_module.default_registry.create_run

        def _spy_create_run(*args: object, **kwargs: object) -> str:
            create_calls.append((args, kwargs))
            return original_create_run(*args, **kwargs)

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy_create_run)

        error = await _call_tool_expecting_mcp_error(None, {"query": "What gene is BRCA1?"})
        assert error.message

        assert create_calls == []

    @pytest.mark.asyncio
    async def test_malformed_token_is_rejected_before_any_run_is_created(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_calls: list[object] = []
        original_create_run = run_registry_module.default_registry.create_run

        def _spy_create_run(*args: object, **kwargs: object) -> str:
            create_calls.append((args, kwargs))
            return original_create_run(*args, **kwargs)

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy_create_run)

        error = await _call_tool_expecting_mcp_error(
            {"Authorization": "not-a-bearer-token"}, {"query": "What gene is BRCA1?"}
        )
        assert error.message

        assert create_calls == []

    @pytest.mark.asyncio
    async def test_invalid_token_is_rejected_before_any_run_is_created(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_calls: list[object] = []
        original_create_run = run_registry_module.default_registry.create_run

        def _spy_create_run(*args: object, **kwargs: object) -> str:
            create_calls.append((args, kwargs))
            return original_create_run(*args, **kwargs)

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy_create_run)

        error = await _call_tool_expecting_mcp_error(
            {"Authorization": "Bearer this.is.not-a-real-jwt"},
            {"query": "What gene is BRCA1?"},
        )
        assert error.message

        assert create_calls == []

    @pytest.mark.asyncio
    async def test_a_valid_token_succeeds_and_the_run_is_owned_by_that_user(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "What gene is BRCA1?"})

        assert result.is_error is False
        run_id = result.structured_content["run_id"]
        entry = run_registry_module.default_registry.get_run(run_id)
        assert entry.user_id == user_id

    @pytest.mark.asyncio
    async def test_duplicate_authorization_headers_are_rejected_outright(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.1-A-11 (adversary round 1, fix round 2): a genuine
        duplicate `Authorization` header (two distinct values, not a
        casing variant) must be rejected outright, never resolved
        first-wins. Both orderings are checked: a valid token first with
        garbage second, and garbage first with a valid token second, since
        a first-wins bug would only be caught by the first ordering.
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        create_calls: list[object] = []
        original_create_run = run_registry_module.default_registry.create_run

        def _spy_create_run(*args: object, **kwargs: object) -> str:
            create_calls.append((args, kwargs))
            return original_create_run(*args, **kwargs)

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy_create_run)
        _user_id, headers = await _real_user_headers()
        valid_value = headers["Authorization"]

        error_valid_first = await _call_tool_with_raw_headers_expecting_mcp_error(
            [("Authorization", valid_value), ("Authorization", "Bearer garbage")],
            {"query": "What gene is BRCA1?"},
        )
        assert error_valid_first.message

        error_garbage_first = await _call_tool_with_raw_headers_expecting_mcp_error(
            [("Authorization", "Bearer garbage"), ("Authorization", valid_value)],
            {"query": "What gene is BRCA1?"},
        )
        assert error_garbage_first.message

        assert create_calls == []

    @pytest.mark.asyncio
    async def test_bearer_scheme_is_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """F-4.1-A-12 (adversary round 1, fix round 2): RFC 7235 section
        2.1 makes the auth-scheme token case-insensitive. Before this fix,
        only the exact literal `Bearer ` (capital B) succeeded; `bearer`
        and `BEARER` were rejected as if the header were missing entirely.
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        _user_id, headers = await _real_user_headers()
        token = headers["Authorization"].removeprefix("Bearer ")

        for scheme in ("bearer", "BEARER", "BeArEr"):
            result = await _call_tool(
                {"Authorization": f"{scheme} {token}"}, {"query": "What gene is BRCA1?"}
            )
            assert result.is_error is False, f"scheme {scheme!r} was wrongly rejected"

    @pytest.mark.asyncio
    async def test_missing_header_does_not_open_a_database_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.1-A-14 (adversary round 1, fix round 2): a request with no
        chance of authenticating (no header at all) must not still open a
        pooled DB connection to find that out. Spies on `server.py`'s own
        imported `session_scope` name (what `_authenticate_mcp_caller`
        actually calls), not the original `data.session.session_scope`,
        since patching the origin would not affect the name already bound
        in `server.py`'s module namespace.
        """
        import system_03_search_agent.adapters.mcp.server as mcp_server_module

        calls: list[bool] = []
        original_session_scope = mcp_server_module.session_scope

        @contextmanager
        def _spy_session_scope() -> Any:
            calls.append(True)
            with original_session_scope() as session:
                yield session

        monkeypatch.setattr(mcp_server_module, "session_scope", _spy_session_scope)

        error = await _call_tool_expecting_mcp_error(None, {"query": "What gene is BRCA1?"})
        assert error.message
        assert calls == [], "a missing header must not open a database session"

    @pytest.mark.asyncio
    async def test_malformed_scheme_does_not_open_a_database_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.1-A-14's other cheap-rejection shape: a header present but
        with no recognizable `Bearer` scheme at all."""
        import system_03_search_agent.adapters.mcp.server as mcp_server_module

        calls: list[bool] = []
        original_session_scope = mcp_server_module.session_scope

        @contextmanager
        def _spy_session_scope() -> Any:
            calls.append(True)
            with original_session_scope() as session:
                yield session

        monkeypatch.setattr(mcp_server_module, "session_scope", _spy_session_scope)

        error = await _call_tool_expecting_mcp_error(
            {"Authorization": "not-a-bearer-token"}, {"query": "What gene is BRCA1?"}
        )
        assert error.message
        assert calls == [], "a malformed scheme must not open a database session"


class TestArgumentHardening:
    """F-4.1-A-13, F-4.1-A-16 (adversary round 1, fix round 2): the MCP
    boundary is the one place in this phase that accepts arbitrary input
    from a party this repo does not control.
    """

    @pytest.mark.asyncio
    async def test_an_unknown_argument_is_rejected_not_silently_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.1-A-13's own exact repro: before this fix, `operator_mode:
        true` alongside `query` returned a normal success response with no
        signal the extra argument was ignored rather than honored. Also
        checked: no run is created (the rejection happens before `create_
        run`, the same auth-first discipline T-4.1-03 already established
        for a bad token).
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        create_calls: list[object] = []
        original_create_run = run_registry_module.default_registry.create_run

        def _spy_create_run(*args: object, **kwargs: object) -> str:
            create_calls.append((args, kwargs))
            return original_create_run(*args, **kwargs)

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy_create_run)
        _user_id, headers = await _real_user_headers()

        error = await _call_tool_expecting_mcp_error(
            headers, {"query": "What gene is BRCA1?", "operator_mode": True}
        )
        assert "operator_mode" in error.message
        assert create_calls == []

    @pytest.mark.asyncio
    async def test_known_arguments_alone_are_never_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No false positives: all three declared arguments together must
        still succeed."""
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(
            headers,
            {"query": "What gene is BRCA1?", "audience_depth": "researcher", "session_id": "s1"},
        )
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_control_bytes_in_query_are_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """F-4.1-A-16's own exact repro: a NUL byte, a BEL, and an ANSI
        escape sequence opener, all inside an otherwise-ordinary,
        length-legal `query`. The SDK converts the `AfterValidator`'s
        `ValueError` into a `CallToolResult(is_error=True)`, the same
        shape the adversary's own confirmed-clean `max_length`/enum/
        empty-query checks already use, never a protocol-level
        `MCPError`.
        """
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        _user_id, headers = await _real_user_headers()

        hostile_query = "BRCA1" + chr(0) + chr(7) + chr(27) + "[31m"
        result = await _call_tool(headers, {"query": hostile_query})
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_ordinary_whitespace_in_query_is_never_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No false positives: tab, newline, and carriage return are legal
        content in a real question and must never be rejected."""
        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        _user_id, headers = await _real_user_headers()

        result = await _call_tool(headers, {"query": "line one\nline two\ttabbed"})
        assert result.is_error is False


class TestConcurrentRunCapOnTheMcpSurface:
    """F-4.10-J-04 / F-4.10-A-08 (judge and adversary round 1, build phase
    4.10).

    Build phase 4.10 gave `RunRegistry.create_run` a per-principal
    concurrent-run cap and a new `ConcurrentRunCapExceededError`, and did
    not touch this module. So this surface's one `create_run` call site
    was the only place in the codebase where a `RuntimeError` could
    escape a tool handler that converts every other failure into a typed
    `MCPError`. Nothing exercised the MCP surface at that cap, which is
    exactly why it stayed invisible.

    The bucket is shared with the web surface on purpose (with `owner_id`
    omitted, `create_run` derives `user:<uuid>` from `query.user_id`, the
    same string `get_caller` builds), so this is reachable by an ordinary
    caller with a browser tab open, not only by an MCP client hammering
    itself.
    """

    @pytest.mark.asyncio
    async def test_hitting_the_cap_returns_a_structured_error_not_a_raw_runtimeerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from system_03_search_agent.core.run_registry import (
            DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER,
        )

        monkeypatch.setattr(run_registry_module, "run_streaming", _never_terminating_stream)
        user_id, headers = await _real_user_headers()

        # Fill this user's cap through the same registry every surface
        # shares, with runs that never finish so all of them stay active.
        held: list[str] = []
        for _ in range(DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER):
            held.append(
                run_registry_module.default_registry.create_run(
                    Query(
                        text="holding a slot",
                        session_id="cap-hold",
                        trace_id=str(uuid.uuid4()),
                        user_id=user_id,
                    ),
                    RequestContext(surface="rest_sse"),
                    owner_id=f"user:{user_id}",
                )
            )
        try:
            error = await _call_tool_expecting_mcp_error(
                headers, {"query": "What gene is BRCA1?"}
            )
        finally:
            for run_id in held:
                run_registry_module.default_registry.cancel_run(run_id)

        assert error.message, "the cap must produce a real, non-empty MCP error message"
        assert "in flight" in error.message, (
            "the error must say what actually happened and what frees it, per "
            "production-standards' retry-safety gate"
        )
        assert f"user:{user_id}" not in error.message, (
            "F-4.1-J3-01's defect shape: the internal namespaced owner id must "
            "never be stringified into an external-facing message"
        )
        assert user_id not in error.message, (
            "no internal identifier at all belongs in this message"
        )
