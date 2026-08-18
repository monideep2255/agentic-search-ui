"""Phase 4.3 premise gate: `tracker/phase_4.3.md`.

The done-when this file pins (the phase's own "Phase premise" section): a
caller holding a valid bearer access token for its own `User` account POSTs
a GraphQL document to `/graphql` and gets back the same cited answer the
REST surface produces for the same question, as typed fields it selected,
HTTP 200, no `errors` array. The answer carries its trust signal, its
citations field-for-field from `CitationPayload` with `sourceUrl` validated
by the identical host-pinned end-anchored pattern, and the run id. A
guardrail refusal is a SUCCESSFUL response carrying a refusal outcome,
never a transport error, because a refusal is the system working. No cost
figure ever reaches this surface. Anything the surface drops or shortens,
it discloses. A hostile DOCUMENT, not merely a hostile value, is bounded:
depth, aliases, token count and run-creating operations per document are
all capped, introspection and the interactive IDE are off, and one document
can never start many runs. A run id is never an authorization bypass, and a
caller who does not own a run learns nothing about its content. Every run
this surface starts is attributed to it.

Driven through the REAL Strawberry schema on the REAL router mounted on the
REAL FastAPI app (`adapters/web_sse/app.py`), over `httpx.ASGITransport`,
speaking raw HTTP with a GraphQL body. No resolver is called directly and
no schema is rebuilt for the test, because a gate that assembles its own
schema proves the resolvers work and proves nothing about the surface a
caller actually reaches. This is the same in-process pattern
`test_phase_4_0_premise.py` established for REST/SSE and
`test_phase_4_1_premise.py` extended for MCP.

Fake event streams (`_golden_path_stream`, `_guardrail_refusal_stream`, and
so on) monkeypatch `run_streaming` at `system_03_search_agent.core.
run_registry`, the seam every adapter gate in this repository already uses,
for the reason stated in both: the real `cypher_query` tool reaches the
live Hetzner AGE graph over an SSH tunnel this environment cannot open, and
a controlled fake is also the more correct design for exercising what this
surface does with a given event sequence rather than re-proving any one
live NCBI answer.

Every clause below names, in a comment beside itself, the mutation that
turns it red. A clause nobody can make fail is not evidence, and build
phase 4.2 measured this discipline surfacing three integration defects at
first assembly instead of at review.

Not covered by this gate, stated per `.claude/rules/goal-contracts.md`'s
coverage-declaration discipline, and stated as a real limit rather than as
an excuse, per the correction `tracker/phase_4.10.md` recorded when an
earlier version of one of these sections explained a gap away:

    - A live model and a live graph. Grounding itself is build phase 2.2's
      and 3.4's gate territory; this gate proves folding and bounding.
    - A real socket. Every arm runs over `ASGITransport` in-process, so
      genuine network behavior, TCP resets and slow-client backpressure are
      NOT exercised.
    - Load. The depth, alias, token, complexity and timeout bounds are
      proven by rejection of a crafted document, never by measuring
      resource use under many concurrent documents. Whether the configured
      numbers are the RIGHT numbers under real load is build phase 6.0's
      territory, and this gate would pass with numbers that are far too
      generous, as long as they bound something.
    - Persisted queries and an operation allowlist. Not built, not claimed.
    - Any GraphQL client library's behavior. This gate speaks raw HTTP.
      Apollo, Relay and urql assumptions are untested.
    - Subscriptions. Not built, per `tracker/phase_4.3.md`'s scope reading
      3, so not covered. The WS-protocol arm proves the transport is not
      advertised, which is a different claim from proving a subscription
      works.
    - Whether the answer text is GOOD. Every arm asserts on structure,
      provenance and disclosure. None grades an answer's quality, which is
      `eval-harness` territory against the golden dataset.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

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

_TEST_AUTH_SECRET = "phase-4-3-premise-gate-secret-value"
_BASE_URL = "http://test"
_GRAPHQL_PATH = "/graphql"


# ---------------------------------------------------------------------------
# Import guard. Every test in this file fails with the SAME
# `ModuleNotFoundError` until the surface exists, rather than a mix of
# import errors, HTTP 404s and assertion failures. Both prior adapter
# phases landed this fixture for the same reason: a gate whose failures
# are heterogeneous cannot be read as "not built yet" at a glance, and
# build phase 4.1 had to correct exactly this after the fact.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _require_graphql_surface_modules() -> None:
    import system_03_search_agent.adapters.graphql.context
    import system_03_search_agent.adapters.graphql.fold
    import system_03_search_agent.adapters.graphql.router
    import system_03_search_agent.adapters.graphql.schema
    import system_03_search_agent.adapters.graphql.security
    import system_03_search_agent.adapters.graphql.types  # noqa: F401


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


# ---------------------------------------------------------------------------
# Fake event streams.
# ---------------------------------------------------------------------------


def _event(event_type: str, trace_id: str, seq: int, payload: Any) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


def _citation(index: int, *, citation_id: str | None = None) -> CitationPayload:
    return CitationPayload(
        citation_id=citation_id or f"c{index}",
        display_index=index,
        source="NCBI Gene",
        source_id=f"{670 + index}",
        source_url=f"https://www.ncbi.nlm.nih.gov/gene/{670 + index}",
        layer="layer_1_graph",
        field="gene_symbol",
        claim_text=f"claim number {index}",
        evidence_kind="curated_assertion",
        assertion_confidence="high",
        population_ancestry_context=None,
        license="public_domain",
        snapshot_date="2026-07-01",
        entity_name="BRCA1",
    )


async def _golden_path_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A full, successful run emitting every one of the eleven event types,
    including the `think`/`plan`/`tool_start`/`tool_result`/`cost` events
    this non-streaming surface folds out entirely. A run that DOES emit
    them must still complete without the fold hanging or crashing.
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
    yield _event("plan", trace_id, 2, PlanPayload(narrative="dispatch cypher_query", tool_calls=[]))
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
    yield _event("citation", trace_id, 6, _citation(1))
    yield _event(
        "cost",
        trace_id,
        7,
        CostPayload(
            query_cost_usd=0.0123,
            query_cap_usd=0.5,
            cap_fraction=0.0246,
            model_tier="synth",
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
            citation_id="c1",
            scope="answer",
            message=None,
            fallback_link=None,
        ),
    )
    yield _event(
        "done",
        trace_id,
        9,
        DonePayload(
            total_cost_usd=0.0123,
            total_tool_calls=1,
            elapsed_ms=812,
            trust_outcome="answer",
        ),
    )


async def _guardrail_refusal_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """The guardrail refuses at admission. This is the system WORKING, so
    it must reach the caller as a successful response carrying a refusal,
    never as a transport-level error.
    """
    trace_id = query.trace_id
    yield _event(
        "guard",
        trace_id,
        0,
        GuardPayload(
            passed=False,
            category="off_topic",
            reason="This looks outside biomedical research.",
        ),
    )
    yield _event(
        "trust_signal",
        trace_id,
        1,
        TrustSignalPayload(
            outcome="refuse",
            risk_tier="unknown",
            grounded=False,
            triangulated=None,
            citation_id=None,
            scope="answer",
            message="This looks outside biomedical research.",
            fallback_link=None,
        ),
    )
    yield _event(
        "done",
        trace_id,
        2,
        DonePayload(
            total_cost_usd=0.0,
            total_tool_calls=0,
            elapsed_ms=41,
            trust_outcome="refuse",
        ),
    )


async def _uncited_answer_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """Answer tokens with NO citation event anywhere. The cite-or-refuse
    rule means this surface must never present such a run as a grounded
    answer. This is the shape MCP's F-4.1 review rounds had to correct.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "token",
        trace_id,
        1,
        TokenPayload(text="BRCA1 causes every known disease.", marker_ids=[]),
    )
    yield _event(
        "trust_signal",
        trace_id,
        2,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=False,
            triangulated=None,
            citation_id=None,
            scope="answer",
            message=None,
            fallback_link=None,
        ),
    )
    yield _event(
        "done",
        trace_id,
        3,
        DonePayload(
            total_cost_usd=0.004,
            total_tool_calls=1,
            elapsed_ms=210,
            trust_outcome="answer",
        ),
    )


async def _claim_scoped_trust_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """Several claim-scoped trust signals and no answer-scoped one. The
    aggregate this surface reports must not silently pick the first, or the
    most favourable, of them. MCP's fold had to be corrected for exactly
    this.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event("token", trace_id, 1, TokenPayload(text="Claim one [1]. ", marker_ids=["c1"]))
    yield _event("citation", trace_id, 2, _citation(1))
    yield _event(
        "trust_signal",
        trace_id,
        3,
        TrustSignalPayload(
            outcome="answer",
            risk_tier="low",
            grounded=True,
            triangulated=None,
            citation_id="c1",
            scope="claim",
            message=None,
            fallback_link=None,
        ),
    )
    yield _event("token", trace_id, 4, TokenPayload(text="Claim two [2]. ", marker_ids=["c2"]))
    yield _event("citation", trace_id, 5, _citation(2, citation_id="c2"))
    yield _event(
        "trust_signal",
        trace_id,
        6,
        TrustSignalPayload(
            outcome="flag",
            risk_tier="high",
            grounded=True,
            triangulated=False,
            citation_id="c2",
            scope="claim",
            message="a second source disagrees",
            fallback_link=None,
        ),
    )
    yield _event(
        "done",
        trace_id,
        7,
        DonePayload(
            total_cost_usd=0.02,
            total_tool_calls=2,
            elapsed_ms=1400,
            trust_outcome="flag",
        ),
    )


# The warning set `_many_trust_warnings_stream` emits AND the disclosure arm
# asserts on, defined once. Two copies drifted at the fifth review round: the
# fixture emitted three warnings and the assertion checked only the first and
# last, so dropping the middle one passed (F-R5-09, the thirteenth vacuous arm
# in this phase). A shared constant makes "assert on every one" structural
# rather than a thing the next reader has to remember.
_EXPECTED_TRUST_WARNINGS = (
    "WARNING-ALPHA " + ("a" * 200),
    "WARNING-BETA " + ("b" * 200),
    "WARNING-OMEGA " + ("z" * 200),
)


async def _many_trust_warnings_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """Several claim-scoped trust signals, each carrying its own long warning,
    so the fold must MERGE their messages and the merge overruns
    `TrustSignalPayload.message`'s own 500-character bound (R-04).

    The two markers asserted by the arm sit in the FIRST and LAST warning
    deliberately: the last is the one a silent tail-cut discards, and the
    first proves the arm is reading real merged content rather than passing
    because everything was dropped.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event("token", trace_id, 1, TokenPayload(text="an answer", marker_ids=["c1"]))
    yield _event("citation", trace_id, 2, _citation(1, citation_id="c1"))
    warnings = list(_EXPECTED_TRUST_WARNINGS)
    seq = 3
    for index, warning in enumerate(warnings):
        yield _event(
            "trust_signal",
            trace_id,
            seq,
            TrustSignalPayload(
                outcome="flag",
                risk_tier="high",
                grounded=True,
                triangulated=None,
                citation_id=f"c{index + 1}",
                scope="claim",
                message=warning,
            ),
        )
        seq += 1
    yield _event(
        "done",
        trace_id,
        seq,
        DonePayload(
            total_cost_usd=0.0, total_tool_calls=1, elapsed_ms=5, trust_outcome="flag"
        ),
    )


async def _oversized_answer_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """More answer text and more citations than this surface's own caps
    allow, so the truncation-disclosure arms have something to disclose.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    seq = 1
    for chunk in range(40):
        yield _event(
            "token",
            trace_id,
            seq,
            TokenPayload(text=("x" * 900) + f" chunk{chunk} ", marker_ids=[]),
        )
        seq += 1
    for index in range(1, 71):
        yield _event("citation", trace_id, seq, _citation(index, citation_id=f"c{index}"))
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
            citation_id="c1",
            scope="answer",
            message=None,
            fallback_link=None,
        ),
    )
    seq += 1
    yield _event(
        "done",
        trace_id,
        seq,
        DonePayload(
            total_cost_usd=0.4,
            total_tool_calls=6,
            elapsed_ms=9000,
            trust_outcome="answer",
        ),
    )


async def _busy_fatal_error_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A run that dies fatally AFTER generating more disclosures than the note
    cap can hold: an over-cap answer, an over-cap citation list, and many
    trust warnings.

    This is F-R5-07's repro. The fatal-error disclosure was carried only as a
    note, notes are capped, and on a run like this one it was evicted, so the
    caller was shown an answer, citations and an outcome combination reachable
    on a perfectly healthy run, with nothing anywhere saying the run had died.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    seq = 1
    for chunk in range(40):
        yield _event(
            "token", trace_id, seq, TokenPayload(text=("x" * 900) + f" c{chunk} ", marker_ids=[])
        )
        seq += 1
    for index in range(1, 71):
        yield _event("citation", trace_id, seq, _citation(index, citation_id=f"c{index}"))
        seq += 1
    for index, warning in enumerate(_EXPECTED_TRUST_WARNINGS):
        yield _event(
            "trust_signal",
            trace_id,
            seq,
            TrustSignalPayload(
                outcome="flag",
                risk_tier="high",
                grounded=True,
                triangulated=None,
                citation_id=f"c{index + 1}",
                scope="claim",
                message=warning,
            ),
        )
        seq += 1
    # Enough of the surface's OWN disclosures to overflow `MAX_DISCLOSURE_
    # NOTES` before the fatal error arrives. Without these the cap never
    # fires, the eviction never happens, and the arm below passes for the
    # wrong reason: measured, an earlier version of this fixture left the
    # arm GREEN under the exact mutation it names.
    for index in range(12):
        yield _event(
            "tool_result",
            trace_id,
            seq,
            ToolResultPayload(
                call_id=f"call{index}",
                tool="cypher_query",
                layer="layer_1_graph",
                status="ok",
                summary=f"tool call {index} returned a truncated row set",
                result_count=25,
                truncated=True,
            ),
        )
        seq += 1
    yield _event(
        "error",
        trace_id,
        seq,
        ErrorPayload(
            fatal=True,
            scope="run",
            source="graph_connection",
            error_class="unexpected",
            message="could not connect to host db-internal.example:5432 as user kg_reader",
            retry_after_s=0,
        ),
    )
    yield _event(
        "done",
        trace_id,
        seq + 1,
        DonePayload(
            total_cost_usd=0.0, total_tool_calls=1, elapsed_ms=42, trust_outcome="refuse"
        ),
    )


async def _fatal_error_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A fatal error whose internal message carries text that must never
    reach a caller. F-4.1-A-09 measured a live database host, port and
    username leaking through exactly this field.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event(
        "error",
        trace_id,
        1,
        ErrorPayload(
            fatal=True,
            scope="run",
            source="graph_connection",
            error_class="unexpected",
            message="could not connect to host db-internal.example:5432 as user kg_reader",
            retry_after_s=0,
        ),
    )
    yield _event(
        "done",
        trace_id,
        2,
        DonePayload(
            total_cost_usd=0.001,
            total_tool_calls=0,
            elapsed_ms=95,
            trust_outcome="refuse",
        ),
    )


async def _no_trust_signal_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """A run that completes and emits NO `trust_signal` of any scope.

    This is the only shape that reaches the fold's own synthetic fallback,
    the branch where THIS SURFACE invents a trust signal from nothing. Judge
    finding J-04: every other arm supplies a real trust signal from the core,
    so that branch was covered by nothing, even though it is the exact
    F-4.1-J3-02 shape the phase claims to be closing. The core's equivalent
    was protected by a source grep while this surface's own was not.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    yield _event("token", trace_id, 1, TokenPayload(text="a partial answer", marker_ids=[]))
    yield _event(
        "done",
        trace_id,
        2,
        DonePayload(
            total_cost_usd=0.002,
            total_tool_calls=1,
            elapsed_ms=120,
            trust_outcome="refuse",
        ),
    )


async def _never_terminating_stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
    """Emits a guard event and then never terminates, so the per-request
    timeout bound has something to bound. Without a timeout this hangs the
    request, and on a shared event loop it hangs the worker.
    """
    trace_id = query.trace_id
    yield _event("guard", trace_id, 0, GuardPayload(passed=True, category="ok", reason=None))
    import asyncio

    while True:  # pragma: no cover - the timeout is what ends this
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Client helpers.
# ---------------------------------------------------------------------------


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


async def _signup_and_login(client: httpx.AsyncClient) -> tuple[str, dict[str, str]]:
    email, password = _unique_email(), "Str0ngPassw0rd!"
    signup = await client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201, signup.text
    user_id = signup.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _client() -> httpx.AsyncClient:
    from system_03_search_agent.adapters.web_sse.app import app

    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=_BASE_URL)


async def _real_user_headers(client: httpx.AsyncClient) -> tuple[str, dict[str, str]]:
    return await _signup_and_login(client)


async def _guest_headers(client: httpx.AsyncClient) -> dict[str, str]:
    minted = await client.post("/auth/guest")
    assert minted.status_code == 201, minted.text
    # `GuestTokenResponse` names the field `guest_token`, not `access_token`
    # (`auth/schemas.py`). A guest credential is a different token family
    # from a user's access token, signed with a domain-separated key, and
    # the wire shape says so rather than blurring the two.
    return {"Authorization": f"Bearer {minted.json()['guest_token']}"}


async def _post_graphql(
    client: httpx.AsyncClient,
    document: str,
    *,
    headers: dict[str, str] | None = None,
    variables: dict[str, Any] | None = None,
) -> httpx.Response:
    body: dict[str, Any] = {"query": document}
    if variables is not None:
        body["variables"] = variables
    return await client.post(_GRAPHQL_PATH, json=body, headers=headers or {})


_ASK_DOCUMENT = """
mutation Ask($input: AskInput!) {
  ask(input: $input) {
    runId
    personaName
    answer
    trustSignal {
      outcome
      riskTier
      grounded
      triangulated
      scope
      message
      fallbackLink
    }
    citations {
      citationId
      displayIndex
      source
      sourceId
      sourceUrl
      layer
      field
      claimText
      evidenceKind
      assertionConfidence
      populationAncestryContext
      license
      snapshotDate
      entityName
    }
    disclosures {
      answerTruncated
      citationsOmitted
      runFailed
      notes
    }
  }
}
"""

_CITATION_FIELDS = (
    "citationId",
    "displayIndex",
    "source",
    "sourceId",
    "sourceUrl",
    "layer",
    "field",
    "claimText",
    "evidenceKind",
    "assertionConfidence",
    "license",
)


async def _ask(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    text: str = "Which diseases are associated with BRCA1?",
) -> httpx.Response:
    return await _post_graphql(
        client,
        _ASK_DOCUMENT,
        headers=headers,
        variables={"input": {"text": text, "sessionId": "s-premise-4-3"}},
    )


def _payload(response: httpx.Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("errors") is None, body["errors"]
    assert body.get("data") is not None, body
    return body["data"]


def _serialized(response: httpx.Response) -> str:
    """The whole response as one string, for arms that assert a value is
    ABSENT everywhere rather than absent from one named field. A leak that
    moves to a different field is still a leak.
    """
    return response.text


# ---------------------------------------------------------------------------
# Arm 1: the golden path.
# ---------------------------------------------------------------------------


class TestGoldenPath:
    @pytest.mark.asyncio
    async def test_a_real_question_returns_a_grounded_cited_answer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop any field from the fold, or
        # return an empty citation list on a run that emitted one.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        data = _payload(response)["ask"]
        assert data["runId"]
        assert data["answer"].strip() != ""
        assert data["trustSignal"]["outcome"] == "answer"
        assert data["trustSignal"]["grounded"] is True
        assert len(data["citations"]) >= 1
        for field in _CITATION_FIELDS:
            assert data["citations"][0][field] not in (None, "")

    @pytest.mark.asyncio
    async def test_the_folded_answer_carries_the_token_text_it_was_sent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: fold the token events into an empty
        # string, or reverse their order.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        assert "protein-coding gene" in _payload(response)["ask"]["answer"]

    @pytest.mark.asyncio
    async def test_internal_step_events_are_folded_out_entirely(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: expose a think/plan/tool narrative
        # field on the result type. This surface is not a reasoning trace.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        serialized = _serialized(response)
        assert "single-hop lookup" not in serialized
        assert "dispatch cypher_query" not in serialized


# ---------------------------------------------------------------------------
# Arm 2: a refusal is a successful response.
# ---------------------------------------------------------------------------


class TestRefusalIsASuccess:
    @pytest.mark.asyncio
    async def test_a_guardrail_refusal_is_http_200_with_no_errors_array(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: raise on a refusal so it lands in
        # the GraphQL `errors` array. A refusal is the product working, and
        # a caller must not have to parse an error to learn it was refused.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _guardrail_refusal_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers, text="What is the capital of France?")

        data = _payload(response)["ask"]
        assert data["trustSignal"]["outcome"] == "refuse"
        assert data["citations"] == []
        assert data["trustSignal"]["message"]

    @pytest.mark.asyncio
    async def test_an_uncited_answer_is_never_reported_as_grounded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: report `grounded: true` whenever a
        # trust_signal event says so, without checking that any citation
        # actually arrived. This is MCP's uncited-answer finding, arriving
        # on a third surface.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _uncited_answer_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        data = _payload(response)["ask"]
        assert data["citations"] == []
        assert data["trustSignal"]["grounded"] is False
        assert data["trustSignal"]["outcome"] != "answer"

    @pytest.mark.asyncio
    async def test_claim_scoped_trust_is_aggregated_not_first_wins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: take the first trust_signal event
        # and ignore the rest, which reports `answer`/low on a run whose
        # second claim was flagged high-risk.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _claim_scoped_trust_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        trust = _payload(response)["ask"]["trustSignal"]
        assert trust["outcome"] == "flag"
        assert trust["riskTier"] == "high"


# ---------------------------------------------------------------------------
# Arm 3: cost can never appear.
# ---------------------------------------------------------------------------


class TestNeverCost:
    @pytest.mark.asyncio
    async def test_no_cost_figure_appears_anywhere_in_the_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: skip `sanitize_event_for_end_user`,
        # or add a cost field to any result type. Asserted over the WHOLE
        # serialized body, not one field, so a leak that moves fields is
        # still caught.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        serialized = _serialized(response)
        for forbidden in ("0.0123", "0.0246", "query_cost_usd", "queryCostUsd", "totalCostUsd"):
            assert forbidden not in serialized

    @pytest.mark.asyncio
    async def test_the_schema_has_no_field_a_cost_figure_could_be_selected_into(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: add a cost field to any type. The
        # first arm proves no cost VALUE is emitted today; this one proves
        # the schema offers no PLACE for one, which is the durable half.
        from system_03_search_agent.adapters.graphql import schema as schema_module

        printed = str(schema_module.schema).lower()
        for forbidden in ("cost", "usd", "spend"):
            assert forbidden not in printed

    @pytest.mark.asyncio
    async def test_operator_mode_is_pinned_false_for_every_caller(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: derive operator_mode from the
        # caller's role here the way the SSE surface does. This surface
        # pins it false in code, matching MCP, so an operator allowlist
        # entry can never open a cost channel through GraphQL.
        from system_03_search_agent.core import run_registry as run_registry_module

        seen: list[RequestContext] = []
        real_create_run = run_registry_module.default_registry.create_run

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            seen.append(context)
            return real_create_run(query, context, **kwargs)

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        async with _client() as client:
            user_id, headers = await _real_user_headers(client)
            monkeypatch.setenv("OPERATOR_USER_IDS", user_id)
            await _ask(client, headers)

        assert seen, "create_run was never reached"
        assert all(context.operator_mode is False for context in seen)


# ---------------------------------------------------------------------------
# Arm 4: auth. Registered accounts only, and a guest is refused actionably.
# ---------------------------------------------------------------------------


class TestAuth:
    @pytest.mark.asyncio
    async def test_a_missing_token_never_reaches_the_core(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: resolve auth inside a resolver
        # instead of ahead of execution, so a run is created before the
        # credential is checked and budget is spent on an anonymous caller.
        from system_03_search_agent.core import run_registry as run_registry_module

        created: list[str] = []

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            created.append(query.trace_id)
            raise AssertionError("create_run must not be reached without a credential")

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        async with _client() as client:
            response = await _ask(client, {})

        assert response.status_code in (400, 401, 403)
        assert created == []

    @pytest.mark.asyncio
    async def test_an_invalid_token_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mutation that turns this red: accept an unverifiable token.
        async with _client() as client:
            response = await _ask(client, {"Authorization": "Bearer not-a-real-token"})

        assert response.status_code in (400, 401, 403)

    @pytest.mark.asyncio
    async def test_a_valid_guest_token_is_refused_with_an_actionable_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: swap the registered-only auth path
        # for `get_caller`, which resolves a guest happily and would open a
        # second, unhardened anonymous-allowance path on this surface.
        # `tracker/phase_4.3.md` scope reading 2 is what this pins.
        from system_03_search_agent.core import run_registry as run_registry_module

        created: list[str] = []

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            created.append(query.trace_id)
            raise AssertionError("a guest must not reach create_run on this surface")

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        async with _client() as client:
            guest = await _guest_headers(client)
            response = await _ask(client, guest)

        assert response.status_code in (401, 403)
        assert created == []
        body = response.text.lower()
        # Actionable, per tool-call-budgets.md: it must say what to do, not
        # only that something failed. The generic invalid-credential string
        # would not distinguish a revoked token from a wrong account type.
        assert "guest" in body
        assert "account" in body or "sign in" in body or "log in" in body

    @pytest.mark.asyncio
    async def test_a_guest_refusal_is_distinguishable_from_an_invalid_token(self) -> None:
        # Mutation that turns this red: collapse both refusals into one
        # message. A developer holding a guest token would then debug a
        # credential problem that does not exist.
        async with _client() as client:
            guest = await _guest_headers(client)
            guest_response = await _ask(client, guest)
            invalid_response = await _ask(client, {"Authorization": "Bearer nope"})

        assert guest_response.text != invalid_response.text


# ---------------------------------------------------------------------------
# Arm 5: ownership. 404 before 403, so a run id is not an existence oracle.
# ---------------------------------------------------------------------------


_RUN_DOCUMENT = """
query Run($runId: ID!) {
  run(runId: $runId) {
    runId
    finished
    answer
    trustSignal { outcome riskTier grounded }
    citations { citationId sourceUrl }
    disclosures { answerTruncated citationsOmitted runFailed notes }
  }
}
"""

_STOP_DOCUMENT = """
mutation Stop($runId: ID!) {
  stopRun(runId: $runId) {
    runId
    stopped
  }
}
"""


class TestOwnership:
    @pytest.mark.asyncio
    async def test_another_callers_run_leaks_nothing_about_that_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: return the run's folded content to a
        # caller who does not own it, or drop the ownership comparison so
        # any authenticated caller can read any run by id.
        #
        # AMENDED 2026-08-17 by the lead, and the reason matters more than
        # the change. This arm originally asserted that a FOREIGN run and an
        # UNKNOWN run are byte-identical in their response, on the stated
        # grounds that the surface must not be an existence oracle. That
        # premise was wrong on its own terms: the REST surface's
        # `_get_owned_run` deliberately answers 404 for unknown and 403 for
        # foreign, per T-1.2-02's acceptance criteria, and that distinction
        # IS an existence oracle. The original arm therefore demanded this
        # surface be strictly more private than every surface that already
        # shipped, which is drift dressed as hardening: a second, different
        # authorization semantic is exactly what this phase exists not to
        # build. Run ids are uuid4, so the oracle has no enumeration value,
        # and the distinct answers are the more actionable ones ("not yours"
        # and "gone" are different problems with different fixes).
        #
        # This is NOT a gate weakened to let code pass, which
        # `.claude/rules/goal-contracts.md` forbids outright. What the arm
        # protects is unchanged and is asserted below: a non-owner learns
        # nothing about the run's CONTENT, and ownership is enforced. Only
        # the incorrect claim about indistinguishability is withdrawn.
        # Whether the 403-versus-404 distinction should be closed at all is
        # a real question, filed as F-4.3-L-01 against every surface at
        # once rather than fixed on the newest one in a surface phase.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _owner_id, owner_headers = await _real_user_headers(client)
            owned_response = await _ask(client, owner_headers)
            owned = _payload(owned_response)["ask"]["runId"]

            _other_id, other_headers = await _real_user_headers(client)
            foreign = await _post_graphql(
                client, _RUN_DOCUMENT, headers=other_headers, variables={"runId": owned}
            )

        foreign_body = foreign.json()
        assert (foreign_body.get("data") or {}).get("run") is None
        # The owner's own answer text and citation urls must appear nowhere
        # in a non-owner's response, asserted over the whole serialized
        # body so a leak that moves to a different field is still caught.
        serialized = _serialized(foreign)
        assert "protein-coding gene" not in serialized
        assert "ncbi.nlm.nih.gov" not in serialized

    @pytest.mark.asyncio
    async def test_a_caller_can_read_its_own_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mutation that turns this red: reject every run read, which would
        # make the arm above pass vacuously. A control that refuses
        # everything passes every attack test and destroys the product,
        # which is why this gate is two-armed here, per build phase 3.0's
        # guardrail precedent and 4.10's allowance gate.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            run_id = _payload(await _ask(client, headers))["ask"]["runId"]
            response = await _post_graphql(
                client, _RUN_DOCUMENT, headers=headers, variables={"runId": run_id}
            )

        run = _payload(response)["run"]
        assert run["runId"] == run_id
        assert run["finished"] is True

    @pytest.mark.asyncio
    async def test_stopping_a_run_is_idempotent_and_owner_checked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: error on a second stop, or let a
        # different caller stop someone else's run.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            run_id = _payload(await _ask(client, headers))["ask"]["runId"]

            first = await _post_graphql(
                client, _STOP_DOCUMENT, headers=headers, variables={"runId": run_id}
            )
            second = await _post_graphql(
                client, _STOP_DOCUMENT, headers=headers, variables={"runId": run_id}
            )
            _other_id, other_headers = await _real_user_headers(client)
            foreign = await _post_graphql(
                client, _STOP_DOCUMENT, headers=other_headers, variables={"runId": run_id}
            )

        assert _payload(first)["stopRun"]["stopped"] is not None
        assert _payload(second)["stopRun"]["stopped"] is not None
        assert (foreign.json().get("data") or {}).get("stopRun") is None


def _error_messages(body: dict[str, Any]) -> list[str]:
    return sorted(error.get("message", "") for error in (body.get("errors") or []))


# ---------------------------------------------------------------------------
# Arm 6: the document itself is bounded.
# ---------------------------------------------------------------------------


def _deeply_nested_document(depth: int) -> str:
    """A legal document nested past any sane limit, built by repeating the
    one recursive path the schema offers. Depth is what bounds a query that
    is small in bytes but enormous in resolution.
    """
    opening = "".join("citations { " for _ in range(depth))
    closing = "".join(" }" for _ in range(depth))
    return "query Deep { run(runId: \"x\") { " + opening + "citationId" + closing + " } }"


class TestDocumentBounds:
    """Each arm asserts the SPECIFIC bound's own error message, never merely
    that some error came back.

    CORRECTED 2026-08-17 after a mutation sweep. All three of these arms
    originally asserted `body.get("errors")` alone, and all three were
    VACUOUS: each stayed green with the bound it names deleted, because some
    OTHER error always arrived to satisfy the assertion. The 40-deep document
    is also independently invalid (`citations` is not a field on `Citation`),
    the 60-alias document resolves 60 unknown runs into 60 errors, and the
    oversized document trips the alias limiter once the token limiter is
    gone. Every one of them "passed" for a reason unrelated to the control it
    claimed to prove. Asserting the bound's own message is what makes each
    arm about its own bound.
    """

    @pytest.mark.asyncio
    async def test_a_document_nested_past_the_limit_is_rejected(self) -> None:
        # Mutation that turns this red: drop QueryDepthLimiter, or raise
        # max_depth above the crafted depth.
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(client, _deeply_nested_document(40), headers=headers)

        messages = " ".join(_error_messages(response.json())).lower()
        assert "depth" in messages, f"the depth limiter did not fire: {messages}"

    @pytest.mark.asyncio
    async def test_a_document_repeating_a_field_under_many_aliases_is_rejected(self) -> None:
        # Mutation that turns this red: drop MaxAliasesLimiter. Aliases are
        # the amplification lever: one small document, many resolutions.
        aliases = " ".join(f"a{i}: run(runId: \"x\") {{ runId }}" for i in range(60))
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(client, "query { " + aliases + " }", headers=headers)

        messages = " ".join(_error_messages(response.json())).lower()
        assert "alias" in messages, f"the alias limiter did not fire: {messages}"

    @pytest.mark.asyncio
    async def test_an_oversized_document_is_rejected(self) -> None:
        # Mutation that turns this red: drop MaxTokensLimiter.
        padding = " ".join(f"f{i}: __typename" for i in range(5000))
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(client, "query { " + padding + " }", headers=headers)

        messages = " ".join(_error_messages(response.json())).lower()
        assert "token" in messages, f"the token limiter did not fire: {messages}"

    @pytest.mark.asyncio
    async def test_one_document_can_never_start_more_than_one_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # THE arm this whole section exists for. Mutation that turns it
        # red: allow more than one run-creating field per document. Every
        # other bound here limits work; this one limits MONEY, because each
        # `ask` spends a real model budget. Aliases are the only way to
        # repeat a field, so this must be enforced as its own rule rather
        # than left to the alias cap, whose limit is necessarily above one.
        from system_03_search_agent.core import run_registry as run_registry_module

        created: list[str] = []
        real_create_run = run_registry_module.default_registry.create_run

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            created.append(query.trace_id)
            return real_create_run(query, context, **kwargs)

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)

        document = """
        mutation Many($input: AskInput!) {
          one: ask(input: $input) { runId }
          two: ask(input: $input) { runId }
          three: ask(input: $input) { runId }
        }
        """
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(
                client,
                document,
                headers=headers,
                variables={"input": {"text": "BRCA1?", "sessionId": "s-multi"}},
            )

        assert response.json().get("errors"), "a multi-ask document must be refused"
        assert len(created) == 0, f"{len(created)} runs were started by one document"

    @pytest.mark.asyncio
    async def test_a_single_ask_document_still_works(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The second arm of the bound above. Mutation that turns it red:
        # reject every mutation document, which would make the previous arm
        # pass while the product does nothing.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        assert _payload(response)["ask"]["runId"]

    @pytest.mark.asyncio
    async def test_a_request_exceeding_the_time_budget_is_bounded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop the timeout extension. Without
        # it a hung run hangs the request, and because Strawberry runs
        # resolvers on the event loop rather than in FastAPI's sync thread
        # pool, a hung resolver degrades every concurrent caller on that
        # worker, not only this one.
        from system_03_search_agent.adapters.graphql import security as security_module
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _never_terminating_stream)
        monkeypatch.setattr(security_module, "REQUEST_TIMEOUT_S", 0.5, raising=True)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        body = response.json()
        assert body.get("errors"), "a hung run must be bounded by the request timeout"
        # Actionable, not merely "failed", per tool-call-budgets.md.
        assert any(
            "time" in message.lower() or "timeout" in message.lower()
            for message in _error_messages(body)
        )


# ---------------------------------------------------------------------------
# Arm 7: the surface's own configuration.
# ---------------------------------------------------------------------------


class TestSurfaceConfiguration:
    @pytest.mark.asyncio
    async def test_introspection_is_refused(self) -> None:
        # Mutation that turns this red: drop DisableIntrospection.
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(
                client, "query { __schema { types { name } } }", headers=headers
            )

        assert response.json().get("errors"), "introspection must be refused"

    @pytest.mark.asyncio
    async def test_field_suggestions_do_not_leak_the_schema(self) -> None:
        # Mutation that turns this red: leave `disable_field_suggestions`
        # at its default False. GraphQL's "Did you mean ...?" enumerates
        # fields one guess at a time even with introspection fully off, so
        # disabling introspection alone is a locked door beside an open
        # window.
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(client, "query { rnu(runId: \"x\") { runId } }", headers=headers)

        body = response.json()
        assert body.get("errors")
        for message in _error_messages(body):
            assert "did you mean" not in message.lower()

    @pytest.mark.asyncio
    async def test_the_interactive_ide_is_not_served(self) -> None:
        # Mutation that turns this red: leave graphql_ide at its default
        # 'graphiql'.
        #
        # CORRECTED 2026-08-17 after a mutation sweep. This arm previously
        # sent NO credentials, so the request was refused with 401 before the
        # IDE could ever render, and the arm passed with GraphiQL fully
        # enabled. It was testing auth, not the IDE setting. An authenticated
        # caller is exactly who WOULD be served the IDE, so the credentials
        # are what make this arm about its own subject.
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await client.get(
                _GRAPHQL_PATH, headers={**headers, "Accept": "text/html"}
            )

        assert "graphiql" not in response.text.lower()
        assert "<html" not in response.text.lower()

    @pytest.mark.asyncio
    async def test_a_query_over_get_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mutation that turns this red: leave allow_queries_via_get at its
        # default True. A GET-able operation is cacheable, ends up in
        # referrer logs and proxy logs, and is reachable cross-site by a
        # plain navigation.
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await client.get(
                _GRAPHQL_PATH, params={"query": "query { __typename }"}, headers=headers
            )

        assert response.status_code >= 400

    @pytest.mark.asyncio
    async def test_no_subscription_protocol_is_advertised(self) -> None:
        # Mutation that turns this red: leave subscription_protocols at its
        # default. This phase builds no subscription, so the surface must
        # not offer a WebSocket upgrade path nobody designed, tested, or
        # bounded.
        #
        # CORRECTED 2026-08-17: this arm previously read a `subscription_
        # protocols` attribute off the router via `getattr(..., ())`. No such
        # attribute exists on the constructed router, so the default kicked
        # in, `() == ()` held, and the arm passed WITHOUT TESTING ANYTHING.
        # It would have passed just as happily with both default protocols
        # enabled. That is the vacuous-assertion class LEARNINGS.md counts as
        # its single most repeated failure, caught here by printing what the
        # router actually exposes instead of trusting the name the
        # constructor argument uses. The real attributes are `protocols` and
        # `websocket_subprotocols`, asserted below, and a `getattr` default
        # is deliberately NOT used, so a future rename fails loudly rather
        # than silently passing again.
        from system_03_search_agent.adapters.graphql import router as router_module

        assert router_module.graphql_router.protocols == ()
        assert router_module.graphql_router.websocket_subprotocols == []

    @pytest.mark.asyncio
    async def test_an_internal_exception_is_masked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mutation that turns this red: drop MaskErrors, which puts raw
        # exception text in the errors array. F-4.1-A-09 measured a live
        # database host, port and username reaching a caller this way.
        from system_03_search_agent.adapters.graphql import fold as fold_module

        async def _explode(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("db-internal.example:5432 user=kg_reader password-ish")

        monkeypatch.setattr(fold_module, "fold_run", _explode, raising=True)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        serialized = _serialized(response)
        assert "db-internal.example" not in serialized
        assert "kg_reader" not in serialized

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_a_failed_run_says_so_even_when_disclosures_overflow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # F-R5-07, the CRITICAL the fifth review round found. "This run died"
        # was carried ONLY as a note, and `_cap_notes` keeps just the first
        # `MAX_DISCLOSURE_NOTES`, so a run that also truncated its answer,
        # omitted citations and raised several warnings evicted the one
        # disclosure that mattered most. The caller then saw an answer, 50
        # citations and a trust signal reachable on a healthy run, with the
        # failure erased.
        #
        # Mutation that turns this red: drop `run_failed` from `Disclosures`,
        # or hardcode it `False`. That is the structured field which cannot be
        # evicted, and it is what actually closes the critical.
        #
        # COVERAGE, STATED HONESTLY because the alternative is a clause that
        # implies more than it proves. This arm does NOT prove the note
        # ordering (`notes.insert(0, ...)` rather than `.append(...)`).
        # Measured: restoring the append leaves this arm GREEN, because the
        # surface cannot currently produce more than four distinct notes of
        # its own (the twelve truncated tool results aggregate into ONE note),
        # so `_cap_notes` never fires on them and there is nothing to evict.
        # The eviction the fifth review round demonstrated was reachable only
        # while the preserved trust warnings still lived INSIDE `notes`, which
        # is what the RR2-03 fix changed.
        #
        # So the ordering is defence in depth against a future disclosure
        # source, deliberately kept and deliberately not claimed as tested.
        # If a later phase adds enough distinct note kinds to reach the cap,
        # this arm should grow a second clause that actually exercises it.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _busy_fatal_error_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        data = _payload(response)["ask"]
        disclosures = data["disclosures"]
        notes = disclosures["notes"]

        # The undroppable half.
        assert disclosures["runFailed"] is True, (
            "a run that died fatally reported nothing structured to say so"
        )
        # And the human-readable half survived the cap alongside it.
        assert any("fail" in note.lower() or "unexpected" in note.lower() for note in notes), (
            "the fatal-error disclosure was evicted from notes by the cap"
        )
        # The internal detail still never reaches the caller.
        serialized = _serialized(response)
        assert "db-internal.example" not in serialized
        assert "kg_reader" not in serialized

    @pytest.mark.asyncio
    async def test_a_fatal_run_error_is_disclosed_as_a_fixed_literal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: interpolate ErrorPayload.message
        # into the response. That field carries raw internal text; MCP
        # fixed this with a fixed literal per error_class and this surface
        # inherits the requirement, not the code.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _fatal_error_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        serialized = _serialized(response)
        assert "db-internal.example" not in serialized
        assert "kg_reader" not in serialized


# ---------------------------------------------------------------------------
# Arm 8: every disclosure survives the transport.
# ---------------------------------------------------------------------------


_CITATIONS_DOCUMENT = """
query Citations($runId: ID!) {
  citations(runId: $runId) {
    runId
    exportTruncated
    runCancelled
    citations { citationId sourceUrl }
  }
}
"""


class TestCallerInputIsNeverAnInternalError:
    """R-09. A caller's own malformed request must never be reported as our
    fault, and must carry a code the caller can branch on.

    The first input-bounds fix only reached fields carrying a CUSTOM SCALAR,
    because only those raise one of this surface's allowlisted exceptions.
    Every other caller mistake collapsed to "This request could not be
    completed due to an internal error" with no code. An internal error reads
    as transient, so a well-behaved client retries forever a request that can
    never succeed.

    Driven through VARIABLES rather than inline literals deliberately: the two
    take different paths through graphql-core, and only the variables path was
    broken. An inline-literal probe reports these correctly and would have
    shown a false green, which is how this survived the first fix.
    """

    @pytest.mark.parametrize(
        ("label", "variables"),
        [
            ("a value outside an enum", {"text": "hi", "sessionId": "s", "audienceDepth": "NOPE"}),
            ("a missing required field", {"sessionId": "s"}),
            ("an explicit null", {"text": None, "sessionId": "s"}),
        ],
    )
    @pytest.mark.asyncio
    async def test_a_malformed_request_is_named_not_masked(
        self, label: str, variables: dict[str, Any]
    ) -> None:
        # Mutation that turns this red: drop the `isinstance(original,
        # GraphQLError)` branch from `security._should_mask_error`, which is
        # the exact state R-09 found.
        document = "mutation A($input: AskInput!) { ask(input: $input) { runId } }"
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(
                client, document, headers=headers, variables={"input": variables}
            )

        body = response.json()
        errors = body.get("errors") or []
        assert errors, f"{label} must be reported, not silently accepted"
        message = errors[0].get("message") or ""
        code = (errors[0].get("extensions") or {}).get("code")

        assert "internal error" not in message.lower(), (
            f"{label} is the CALLER's mistake and must never be reported as ours"
        )
        assert code == "BAD_USER_INPUT", (
            f"{label} must carry a code a client can branch on, not prose alone"
        )

    @pytest.mark.parametrize(
        ("label", "document"),
        [
            ("unknown argument", 'mutation { ask(inpt: {text: "hi", sessionId: "s"}) { runId } }'),
            ("unknown type", "mutation A($i: AskInpt!) { ask(input: $i) { runId } }"),
            ("unknown output field", 'mutation { ask(input: {text: "x", sessionId: "s"}) { nope } }'),
            ("unknown input field", 'mutation { ask(input: {tex: "x", sessionId: "s"}) { runId } }'),
        ],
    )
    @pytest.mark.asyncio
    async def test_a_rejected_token_never_names_its_real_neighbours(
        self, label: str, document: str
    ) -> None:
        # F-R5-04. Disclosing validation errors reopened schema enumeration:
        # graphql-core appends "Did you mean 'x' or 'y'?", which names real
        # fields, arguments and types. That is introspection one guess at a
        # time, and it worked with introspection fully disabled. Strawberry's
        # own `disable_field_suggestions` covers only messages beginning
        # "Cannot query field", so arguments and types were still enumerable.
        #
        # Both arms matter: the suggestion is gone AND the caller is still
        # told which of their own tokens was rejected, since stripping the
        # whole message would trade one defect for a useless error.
        #
        # Mutation that turns this red: remove either
        # `_strip_schema_suggestions` call from `security._should_mask_error`.
        # There are two, on different branches, and these cases arrive on the
        # `original is None` branch specifically.
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(client, document, headers=headers)

        errors = response.json().get("errors") or []
        assert errors, f"{label} must be rejected"
        message = errors[0].get("message") or ""
        assert "Did you mean" not in message, (
            f"{label} enumerated the schema: {message}"
        )
        assert message.strip(), f"{label} was stripped to nothing, which is not actionable"

    @pytest.mark.asyncio
    async def test_a_resolver_raising_a_graphql_error_still_masks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # THE arm for the critical that has now been introduced TWICE: once by
        # the original package-origin allowlist, and again by the first R-09
        # fix, which disclosed any `GraphQLError` on the reasoning that our own
        # code only ever raises plain Python exceptions. That was false. A
        # resolver can raise a bare `GraphQLError`, and graphql-core raises one
        # itself for a server-side bug, and both were being handed to the
        # caller verbatim, the second stamped BAD_USER_INPUT so our defect was
        # blamed on them.
        #
        # The distinction that makes this safe is the PHASE the error came
        # from, not its class: an error raised while resolving a field carries
        # a `path`, and one from coercion or validation does not.
        #
        # Mutation that turns this red: drop `and error.path is None` from
        # `security._should_mask_error`, which is exactly the state the
        # re-review found.
        from graphql import GraphQLError

        from system_03_search_agent.adapters.graphql import fold as fold_module

        secret = "AGE_DSN=postgresql://kg_reader:hunter2@10.0.0.1:5432/kg"

        async def _leak(*_args: Any, **_kwargs: Any) -> Any:
            raise GraphQLError(f"{secret} at /Users/secret/path/fold.py:912")

        monkeypatch.setattr(fold_module, "fold_run", _leak)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        serialized = _serialized(response)
        for probe in ("postgresql://", "kg_reader", "hunter2", "10.0.0.1", "/Users/secret"):
            assert probe not in serialized, f"{probe} reached the caller"
        # And it must not be mislabelled as the caller's mistake.
        errors = response.json().get("errors") or []
        codes = [(error.get("extensions") or {}).get("code") for error in errors]
        assert "BAD_USER_INPUT" not in codes, (
            "a failure inside our own resolver was blamed on the caller"
        )

    @pytest.mark.asyncio
    async def test_an_internal_failure_is_still_masked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The converse arm, and the one that stops the fix above from being a
        # hole. Disclosing caller-input errors must not disclose OUR errors:
        # a plain Python exception raised inside a resolver still masks.
        # Without this arm, `_should_mask_error` could return False
        # unconditionally and every arm above would still pass.
        #
        # Mutation that turns this red: return False unconditionally from
        # `_should_mask_error`.
        from system_03_search_agent.adapters.graphql import fold as fold_module

        async def _leak(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("AGE_DSN=postgresql://kg_reader:secret@10.0.0.1:5432/kg")

        monkeypatch.setattr(fold_module, "fold_run", _leak)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        serialized = _serialized(response)
        assert "postgresql://" not in serialized
        assert "kg_reader" not in serialized
        assert "secret" not in serialized
        assert "10.0.0.1" not in serialized


class TestDisclosuresSurvive:
    @pytest.mark.asyncio
    async def test_merged_trust_warnings_are_never_cut_without_saying_so(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # R-04, the last hole in premise clause C5, and the worst place in
        # the module to have had one: what gets cut here is WARNING text, so
        # the run whose tail is discarded is exactly the run carrying the
        # most warnings. Unlike every other truncation site, this text
        # survived in no other field, so nothing could recover it.
        #
        # Mutation that turns this red: restore the silent
        # `" ".join(messages)[:MAX_DISCLOSURE_NOTE_LENGTH]` in
        # `fold._floor_trust_payloads`, or drop the `notes.extend(...)` that
        # preserves each warning in full.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _many_trust_warnings_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        data = _payload(response)["ask"]
        notes = data["disclosures"]["notes"]

        # EVERY distinct warning, not a sample of the ends.
        #
        # The corrected version of this clause asserted only ALPHA and OMEGA,
        # the first and last, so a mutation that dropped every MIDDLE warning
        # left it green. That was the thirteenth vacuous arm in this phase and
        # the sixth of the lead's: the first correction fixed the assertion's
        # DEPTH (full text, not a prefix) and left its BREADTH untouched.
        # Asserting on a sample of a collection tests the sample.
        for full_text in _EXPECTED_TRUST_WARNINGS:
            assert any(full_text in note for note in notes), (
                f"a warning was dropped or preserved only in part: {full_text[:24]}..."
            )

        # The FULL text of every distinct warning survives, so nothing a merge
        # had to cut is lost.
        #
        # This asserted only that a PREFIX MARKER appeared somewhere in notes,
        # and was vacuous: cutting every preserved warning to 20 characters,
        # undisclosed, left it green, because the marker sits in the first 14.
        # Preserving the first 20 characters of a warning is not preserving
        # the warning. Proven by running exactly that mutation; corrected to
        # compare full text.


        # And the merge itself discloses its own cut, asserted DIRECTLY on
        # the floor rather than on the response.
        #
        # This second assertion was end-to-end in its first version and was
        # VACUOUS: `disclosures.notes` are merged into `trust_signal.message`
        # a second time downstream, and that second merge appends the
        # truncation marker whatever the first one did, so restoring the
        # silent cut left the arm green. Proven by running exactly that
        # mutation. Checking the floor directly is what makes the clause
        # sensitive to the code it names.
        #
        # Mutation that turns this red: restore
        # `" ".join(messages)[:MAX_DISCLOSURE_NOTE_LENGTH]` in
        # `fold._floor_trust_payloads`.
        from system_03_search_agent.adapters.graphql import fold as fold_module

        payloads = [
            TrustSignalPayload(
                outcome="flag",
                risk_tier="high",
                grounded=True,
                triangulated=None,
                citation_id="c1",
                scope="claim",
                message=text,
            )
            for text in ("WARNING-ALPHA " + "a" * 200, "WARNING-BETA " + "b" * 200,
                         "WARNING-OMEGA " + "z" * 200)
        ]
        floored = fold_module._floor_trust_payloads(payloads, "flag")
        assert floored.message is not None
        assert "omitted" in floored.message.lower(), (
            "the merge cut warning text and did not say so; that text has no "
            "other channel to survive in, which is exactly R-04"
        )

    @pytest.mark.asyncio
    async def test_a_truncated_answer_says_so(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mutation that turns this red: truncate silently. The withholding
        # rule decided 2026-08-15 is one line: if the system drops or
        # shortens anything, it discloses that it did.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _oversized_answer_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        data = _payload(response)["ask"]
        assert data["disclosures"]["answerTruncated"] is True
        assert data["disclosures"]["notes"], "a truncation must be named, not just flagged"

    @pytest.mark.asyncio
    async def test_an_over_cap_citation_list_says_how_many_were_omitted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: cap the citation list without
        # counting what was dropped, which is F-3.3-A-12's shape.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _oversized_answer_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        data = _payload(response)["ask"]
        assert data["disclosures"]["citationsOmitted"] > 0
        assert len(data["citations"]) < 70

    @pytest.mark.asyncio
    async def test_an_untruncated_answer_does_not_claim_truncation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The second arm. Mutation that turns it red: hardcode
        # answerTruncated true, which would make the arm above pass while
        # every honest answer lies about itself.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        disclosures = _payload(response)["ask"]["disclosures"]
        assert disclosures["answerTruncated"] is False
        assert disclosures["citationsOmitted"] == 0

    @pytest.mark.asyncio
    async def test_the_citations_export_carries_its_header_only_disclosures_as_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop exportTruncated or
        # runCancelled. On REST both facts travel as HTTP response headers
        # (X-Citations-Export-Truncated, X-Run-Cancelled). GraphQL has no
        # header channel, so without explicit fields these two disclosures
        # vanish silently on this surface, which is exactly how F-4.0-A-12
        # went wrong once already.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            run_id = _payload(await _ask(client, headers))["ask"]["runId"]
            response = await _post_graphql(
                client, _CITATIONS_DOCUMENT, headers=headers, variables={"runId": run_id}
            )

        export = _payload(response)["citations"]
        assert export["exportTruncated"] is False
        assert export["runCancelled"] is False
        assert export["citations"]


# ---------------------------------------------------------------------------
# Arm 9: provenance integrity and surface attribution.
# ---------------------------------------------------------------------------


class TestProvenanceAndAttribution:
    @pytest.mark.asyncio
    async def test_a_run_started_here_is_attributed_to_this_surface(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: reuse "rest_sse" rather than adding
        # a "graphql" member, which misattributes every run this surface
        # starts and makes per-surface analysis silently wrong.
        from system_03_search_agent.core import run_registry as run_registry_module

        seen: list[str] = []
        real_create_run = run_registry_module.default_registry.create_run

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            seen.append(context.surface)
            return real_create_run(query, context, **kwargs)

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            await _ask(client, headers)

        assert seen == ["graphql"]

    @pytest.mark.asyncio
    async def test_the_run_id_returned_is_the_trace_id_threaded_through_events(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: let create_run mint its own id
        # independently of Query.trace_id, so the id the caller holds is
        # not the id in the audit trail.
        from system_03_search_agent.core import run_registry as run_registry_module

        seen: list[str] = []
        real_create_run = run_registry_module.default_registry.create_run

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            seen.append(query.trace_id)
            return real_create_run(query, context, **kwargs)

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            run_id = _payload(await _ask(client, headers))["ask"]["runId"]

        assert seen == [run_id]

    @pytest.mark.asyncio
    async def test_an_off_host_source_url_can_never_be_returned(self) -> None:
        # Mutation that turns this red: type sourceUrl as a plain String
        # with no pattern, or validate only the `https://` prefix. The
        # end-anchored host-pinned pattern is the fix F-4.2-A-01 landed for
        # every surface after F-3.4-A-06 sat "not exploitable" for two
        # phases and then became exploitable the moment a new surface
        # appeared. This surface is the next new surface.
        from system_03_search_agent.adapters.graphql import types as types_module

        for hostile in (
            "https://evil.example/gene/672",
            "https://www.ncbi.nlm.nih.gov.evil.example/gene/672",
            "https://www.ncbi.nlm.nih.gov/gene/672 https://evil.example",
            "https://www.ncbi.nlm.nih.gov/gene/672\nSource: evil",
        ):
            with pytest.raises(Exception):  # noqa: B017 - any rejection is a pass here
                types_module.Citation.from_payload(  # type: ignore[attr-defined]
                    _citation(1).model_copy(update={"source_url": hostile})
                )

    @pytest.mark.asyncio
    async def test_a_real_ncbi_source_url_is_accepted(self) -> None:
        # The second arm. Mutation that turns it red: reject everything,
        # which would make the arm above pass while no citation can ever be
        # returned. A control that refuses every URL destroys the product.
        from system_03_search_agent.adapters.graphql import types as types_module

        accepted = types_module.Citation.from_payload(_citation(1))  # type: ignore[attr-defined]
        assert accepted.source_url.startswith("https://www.ncbi.nlm.nih.gov/")


# ---------------------------------------------------------------------------
# Arm 10: the concurrent-run cap, and the message that says which bound hit.
# ---------------------------------------------------------------------------


class TestConcurrencyBound:
    @pytest.mark.asyncio
    async def test_the_concurrent_run_cap_sits_above_the_attempt_allowance(self) -> None:
        # Mutation that turns this red: set the cap to any value at or below
        # ATTEMPT_ALLOWANCE, for example 6.
        #
        # CORRECTED 2026-08-17 (judge finding J-03). This arm previously
        # asserted only `!= FREE_RUN_ALLOWANCE`, which any value other than 5
        # satisfies, INCLUDING 6. But 6 sits below ATTEMPT_ALLOWANCE and so
        # reintroduces exactly the ambiguous-refusal shape this phase claims
        # to have closed structurally. The property the phase file is
        # proudest of was the one property nothing tested.
        #
        # The real invariant: a guest identity must always meet the honest
        # allowance refusal BEFORE it can hit the concurrency cap, which
        # holds only while the cap is strictly above the attempt allowance.
        from system_03_search_agent.core.run_registry import DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER
        from system_03_search_agent.data.guest_sessions import (
            ATTEMPT_ALLOWANCE,
            FREE_RUN_ALLOWANCE,
        )

        assert DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER != FREE_RUN_ALLOWANCE
        assert DEFAULT_MAX_ACTIVE_RUNS_PER_OWNER > ATTEMPT_ALLOWANCE, (
            "a guest must exhaust its attempt allowance before it can reach the "
            "concurrency cap, or the refusal it gets is untrue advice"
        )

    @pytest.mark.asyncio
    async def test_the_cap_refusal_names_which_bound_was_hit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: return a bare "failed" or a message
        # that cannot distinguish a concurrency bound from an allowance
        # bound. tool-call-budgets.md forbids exactly this: an error must
        # say what to do next, not only that something failed.
        from system_03_search_agent.core import run_registry as run_registry_module

        def _at_cap(query: Query, context: RequestContext, **kwargs: Any) -> str:
            raise run_registry_module.ConcurrentRunCapExceededError(
                "too many active runs for this owner"
            )

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _at_cap)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        body = response.json()
        messages = " ".join(_error_messages(body)).lower() + _serialized(response).lower()
        assert "concurrent" in messages or "in flight" in messages or "active" in messages
        assert "retry" in messages or "wait" in messages

    @pytest.mark.asyncio
    async def test_a_refusal_never_leaks_the_internal_cap_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: stringify the exception, whose own
        # message embeds the internal cap. The REST surface already had to
        # avoid this at app.py's catch site.
        from system_03_search_agent.core import run_registry as run_registry_module

        def _at_cap(query: Query, context: RequestContext, **kwargs: Any) -> str:
            raise run_registry_module.ConcurrentRunCapExceededError(
                "owner user:abc has 5 active runs, cap is 5, internal-detail-leak"
            )

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _at_cap)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        assert "internal-detail-leak" not in _serialized(response)


# ---------------------------------------------------------------------------
# Arm 11: the risk tier is not asserted from nothing.
# ---------------------------------------------------------------------------


class TestTransportBounds:
    """The bounds that live in the ASGI layer rather than in the schema.

    Specified by the fix agent that owns `router.py` and written here by the
    lead, since that agent was correctly barred from this file. Each arm
    names the mutation that turns it red, and each bound is two-armed: it
    must refuse the hostile request AND admit an ordinary one, because a
    bound that refuses everything passes every attack arm and destroys the
    product.

    These bounds run BEFORE authentication, which is a deliberate change to
    the unauthenticated response shape: a request cannot be authenticated
    without being read, so bounding what the server is willing to read
    cannot wait behind a privilege check. The refusal discloses only the cap.
    """

    @pytest.mark.asyncio
    async def test_an_oversized_request_body_is_refused_and_starts_no_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: raise MAX_REQUEST_BODY_BYTES above
        # the probe size. F-4.3-A-15: 20 MB of unused variables was accepted
        # and served, and the document token limiter does not bound
        # variables at all, so this is the cheap-to-send expensive-to-serve
        # vector the token bound cannot see.
        from system_03_search_agent.adapters.graphql import router as router_module
        from system_03_search_agent.core import run_registry as run_registry_module

        created: list[str] = []

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            created.append(query.trace_id)
            raise AssertionError("an over-cap body must not reach run creation")

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        # A FIXED size, deliberately not derived from the cap.
        #
        # CORRECTED at the re-review round (finding R-03). This probe was
        # `MAX_REQUEST_BODY_BYTES + 4096`, so it scaled with the constant and
        # NO cap value could ever fail it: raising the cap to 20 MB left the
        # arm green, which means F-4.3-A-15's fix was unpinned by the very
        # arm written to pin it. A probe sized from the thing it tests proves
        # only that the arithmetic is consistent.
        #
        # 2 MB is well above any legitimate GraphQL request to this surface
        # and well below the 20 MB the adversary actually sent.
        oversized = "x" * (2 * 1024 * 1024)
        assert router_module.MAX_REQUEST_BODY_BYTES < len(oversized), (
            "the probe must exceed the cap by construction, or this arm proves nothing"
        )
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(
                client,
                _ASK_DOCUMENT,
                headers=headers,
                variables={"input": {"text": "BRCA1?", "sessionId": "s"}, "padding": oversized},
            )

        body = response.json()
        codes = [(e.get("extensions") or {}).get("code") for e in (body.get("errors") or [])]
        assert router_module.BODY_TOO_LARGE_CODE in codes, body
        assert created == []

    @pytest.mark.asyncio
    async def test_an_ordinary_body_still_creates_a_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The converse. Mutation that turns this red: set
        # MAX_REQUEST_BODY_BYTES to 0, which would make the arm above pass
        # while refusing every real question.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        assert _payload(response)["ask"]["runId"]

    @pytest.mark.asyncio
    async def test_an_oversized_body_without_a_content_length_is_still_refused(self) -> None:
        # Mutation that turns this red: keep only the `content-length` fast
        # path and drop the counting drain. A sender that omits the header,
        # or lies in it, would then walk straight past the bound.
        from system_03_search_agent.adapters.graphql import router as router_module

        # Fixed size, not derived from the cap. See the sibling arm above:
        # a probe built as `cap + n` cannot fail for any cap (R-03).
        oversized = b"x" * (2 * 1024 * 1024)
        assert router_module.MAX_REQUEST_BODY_BYTES < len(oversized)

        async def _chunks() -> AsyncIterator[bytes]:
            for start in range(0, len(oversized), 16384):
                yield oversized[start : start + 16384]

        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await client.post(
                _GRAPHQL_PATH,
                content=_chunks(),
                headers={**headers, "Content-Type": "application/json"},
            )

        codes = [
            (e.get("extensions") or {}).get("code") for e in (response.json().get("errors") or [])
        ]
        assert router_module.BODY_TOO_LARGE_CODE in codes, response.text

    @pytest.mark.asyncio
    async def test_the_nesting_bound_is_monotonic_in_the_attack_size(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # THE property F-4.3-A-14 was actually about, and the reason this arm
        # tests three depths rather than one: before the fix, a BIGGER attack
        # produced a WORSE outcome (the parser crashed with an unhandled
        # recursion failure reported as a generic internal error). A bound
        # that degrades as the attack grows is not a bound.
        #
        # Mutation that turns this red: remove the pre-parser nesting scan.
        from system_03_search_agent.adapters.graphql import router as router_module
        from system_03_search_agent.core import run_registry as run_registry_module

        created: list[str] = []

        def _spy(query: Query, context: RequestContext, **kwargs: Any) -> str:
            created.append(query.trace_id)
            raise AssertionError("a too-deeply-nested document must not reach run creation")

        monkeypatch.setattr(run_registry_module.default_registry, "create_run", _spy)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            observed: list[list[str | None]] = []
            for depth in (200, 400, 2000):
                document = "query D { " + "... on Query { " * depth + "__typename" + " }" * depth + " }"
                response = await _post_graphql(client, document, headers=headers)
                observed.append(
                    [
                        (e.get("extensions") or {}).get("code")
                        for e in (response.json().get("errors") or [])
                    ]
                )

        for codes in observed:
            assert router_module.DOCUMENT_TOO_DEEPLY_NESTED_CODE in codes, observed
        assert created == []

    @pytest.mark.asyncio
    async def test_the_transport_bound_has_not_swallowed_the_schema_depth_bound(self) -> None:
        # Mutation that turns this red: lower MAX_DOCUMENT_NESTING_DEPTH
        # below the schema's own limit, which would make the coarse transport
        # bound fire first and silently retire QueryDepthLimiter. The two
        # bounds are deliberately at different layers and both must remain
        # reachable.
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _post_graphql(client, _deeply_nested_document(40), headers=headers)

        messages = " ".join(_error_messages(response.json())).lower()
        assert "depth" in messages, messages

    @pytest.mark.asyncio
    async def test_the_nesting_scan_is_not_fooled_by_braces_inside_strings(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: count every `{` in the raw body
        # rather than skipping strings, block strings and comments. A user
        # legitimately asking about a sequence full of braces would then be
        # refused, which is the false-positive half of this bound.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            # The braces must sit in the DOCUMENT, inside a string literal.
            #
            # CORRECTED at the re-review round (finding R-05). They were in
            # `variables`, which the nesting scanner never reads, so the arm
            # passed without exercising the string-skipping it exists to
            # prove. An inline literal is what actually reaches the scanner.
            document = (
                "mutation { ask(input: {text: "
                + '"' + "{" * 500 + '"'
                + ', sessionId: "s"}) { runId } }'
            )
            response = await _post_graphql(client, document, headers=headers)

        assert _payload(response)["ask"]["runId"], response.text

    @pytest.mark.asyncio
    async def test_the_trailing_slash_spelling_is_served_not_redirected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop the trailing-slash spelling from
        # the served paths. F-4.3-A-10: it used to 307-redirect, and the
        # redirect DROPPED the request body, so a caller who added a slash
        # silently lost their query rather than being told anything.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _golden_path_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await client.post(
                _GRAPHQL_PATH + "/",
                json={
                    "query": _ASK_DOCUMENT,
                    "variables": {"input": {"text": "BRCA1?", "sessionId": "s"}},
                },
                headers=headers,
            )

        assert response.status_code == 200, response.text
        assert _payload(response)["ask"]["runId"]

    @pytest.mark.asyncio
    async def test_the_timeout_bound_matches_this_surface_exactly(self) -> None:
        # Mutation that turns this red: restore the `startswith` prefix
        # match. F-4.3-A-11: a prefix match also bounds unrelated paths that
        # merely begin with the same string, so `/graphql-admin` would
        # silently inherit this surface's timeout.
        from system_03_search_agent.adapters.graphql.router import RequestTimeoutMiddleware

        seen: list[str] = []

        async def _inner(scope: dict[str, Any], receive: Any, send: Any) -> None:
            seen.append(scope["path"])

        middleware = RequestTimeoutMiddleware(_inner)

        async def _receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def _send(_message: dict[str, Any]) -> None:
            return None

        for path in ("/graphql", "/graphql/", "/graphqlXYZ", "/graphql-admin", "/other"):
            await middleware({"type": "http", "path": path, "headers": []}, _receive, _send)

        assert seen[2:] == ["/graphqlXYZ", "/graphql-admin", "/other"], seen

    @pytest.mark.asyncio
    async def test_the_timeout_message_does_not_claim_the_run_was_stopped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: restore the "was aborted" wording.
        # F-4.3-A-17: the request is abandoned but the RUN keeps going and
        # keeps billing, so telling a caller it was aborted is untrue, and a
        # caller who then retries starts a SECOND billed run believing the
        # first is gone.
        from system_03_search_agent.adapters.graphql import security as security_module
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _never_terminating_stream)
        monkeypatch.setattr(security_module, "REQUEST_TIMEOUT_S", 0.5, raising=True)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        messages = " ".join(_error_messages(response.json())).lower()
        assert "abort" not in messages, messages
        assert "still" in messages or "continue" in messages or "second" in messages, messages


class TestRiskTierHonesty:
    @pytest.mark.asyncio
    async def test_a_refusal_reports_an_unassessed_risk_tier_as_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: restore the hardcoded "low" at
        # core/graph.py's two refusal sites. On a refusal no assessment
        # ran, so "low" is a safety-relevant claim made from nothing, which
        # is F-4.1-J3-02 already open on the MCP surface. This surface is
        # the third to expose the field, so the value gets fixed rather
        # than propagated again.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _guardrail_refusal_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        trust = _payload(response)["ask"]["trustSignal"]
        assert trust["outcome"] == "refuse"
        assert trust["riskTier"] == "unknown"

    @pytest.mark.asyncio
    async def test_the_folds_own_invented_trust_signal_says_unknown_not_low(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: change `fold.py`'s synthetic
        # no-signal fallback back to `risk_tier="low"`.
        #
        # ADDED 2026-08-17 (judge finding J-04). Every other risk-tier arm
        # drives a stream carrying a real answer-scope trust signal from the
        # core, so the fold takes that branch and NEVER reaches the fallback
        # where it invents a signal itself. That fallback is this surface's
        # own instance of asserting a safety-relevant value from nothing, and
        # it was ungated while the core's equivalent was grep-protected.
        from system_03_search_agent.core import run_registry as run_registry_module

        monkeypatch.setattr(run_registry_module, "run_streaming", _no_trust_signal_stream)
        async with _client() as client:
            _user_id, headers = await _real_user_headers(client)
            response = await _ask(client, headers)

        trust = _payload(response)["ask"]["trustSignal"]
        assert trust["riskTier"] != "low", (
            "no assessment ran on this run, so reporting the benign tier asserts "
            "a safety-relevant value from nothing"
        )
        assert trust["grounded"] is False

    def test_no_refusal_site_in_the_core_still_hardcodes_a_low_risk_tier(self) -> None:
        # Mutation that turns this red: fix only the value this surface
        # happens to observe and leave a sibling site hardcoded. This is
        # the fix-by-category rule build phase 4.2 paid for four times: an
        # enumerated fix grows a gap at the first case nobody listed.
        # NARROWED 2026-08-17, on a report from the fix agent that owns
        # `core/graph.py`. The grep matched ANY line containing the literal,
        # including a comment quoting it to explain the rule and a severity
        # table deriving from it. That is a blunt proxy for the arm's real
        # intent, and it punishes exactly the code that documents the
        # invariant. The intent is narrower: no site that EMITS a
        # `TrustSignalPayload` may hardcode the benign tier.
        #
        # Deliberately still a source grep rather than a behavioural test,
        # because the point is to catch a NEW emit site that nobody wired a
        # behavioural arm for. Judge finding J-04's companion arm covers the
        # behaviour on the surface this phase owns.
        #
        # Mutation that turns this red: hardcode the benign tier at either
        # refusal site in `core/graph.py`.
        # The scan walks each `TrustSignalPayload(` call to its MATCHING
        # close paren and looks inside that span, rather than looking back a
        # fixed number of lines. The first attempt at narrowing this arm used
        # a six-line lookback and was itself VACUOUS: these emit sites carry
        # long explanatory comments between the constructor and the field, so
        # the window never reached the argument and the arm passed under its
        # own mutation. Caught by running that mutation, which is the whole
        # discipline this phase kept failing to apply to itself.
        from pathlib import Path

        source = Path("src/system_03_search_agent/core/graph.py").read_text(encoding="utf-8")
        lines = source.splitlines()

        def _emit_site_spans() -> list[str]:
            spans: list[str] = []
            for index, line in enumerate(lines):
                if "TrustSignalPayload(" not in line:
                    continue
                depth = 0
                collected: list[str] = []
                for candidate in lines[index:]:
                    code = candidate.split("#", 1)[0]  # a comment is documentation
                    collected.append(code)
                    depth += code.count("(") - code.count(")")
                    if depth <= 0 and collected:
                        break
                spans.append("".join(collected))
            return spans

        offending = [
            span for span in _emit_site_spans() if 'risk_tier="low"' in span.replace(" ", "")
        ]
        assert offending == [], (
            f"a trust-signal emit site still hardcodes the benign tier: {offending}"
        )
