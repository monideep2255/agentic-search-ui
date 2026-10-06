"""Build phase 8.10, T-8.10-05: MCP does what the web does.

The product owner's decision of 2026-09-26 (`DECISIONS.md`, "The MCP server
gets full parity with the web app") and the ledger `tracker/phase_8.10.md`.
Each class below is one of the ticket's acceptance lines, in the words a
person would use, and each test names the mutation that turns it red.

Two halves, so the fold rules are proven everywhere and the ownership rules
are proven against a real database:

- DATABASE-FREE. The fold (`_fold_run_to_response`) against a fresh,
  test-local `RunRegistry` with `run_streaming` replaced at its source
  module, the seam every adapter test here uses. These run on any machine.
- DATABASE-BACKED. Every new tool driven through a real MCP client session
  against the real, mounted Starlette sub-app, with two real accounts made
  through `/auth/signup` and `/auth/login`. They skip without the user
  database, and CI provides one (`gate04b` fails the build on a database
  skip), so they always run there.

WHAT THIS FILE DOES NOT COVER, stated so a green run is not over-read:

- A live model. Every run here is a fixed stream of contract-valid events.
  Whether the core emits the ask-back or the trust line on a real question
  is the core's own suites' job and the audit's live smoke run's.
- The REST routes themselves. The web_sse suites own those.
- `persona_name` and the fatal-error and truncation disclosures, which
  `test_no_cost_and_auth.py` and the phase 4.1 history already cover.
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import pytest
import sqlalchemy as sa

from system_03_search_agent.adapters.mcp import server as server_module
from system_03_search_agent.contracts.events import (
    CitationPayload,
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
    PlanPayload,
    ThinkPayload,
    TokenPayload,
    TrustSignalPayload,
)
from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.core.run_registry import RunRegistry

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)

_TEST_AUTH_SECRET = "test-only-auth-secret-for-mcp-parity-tool-tests"
_BASE_URL = "http://localhost:8000"

_GERD_QUESTION = "What would you like to know about GERD?"
_GERD_OPTIONS = [
    "What is GERD?",
    "Which genetic variants are associated with GERD?",
    "Are there clinical trials on GERD treatments?",
    "What does recent research say about GERD?",
]
_TRUST_LINE = "Based on 3 sources, not yet confirmed"


# ---------------------------------------------------------------------------
# Event builders.
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


def _citation(index: int) -> CitationPayload:
    return CitationPayload(
        citation_id=f"c{index}",
        display_index=index,
        source="NCBIGene",
        source_id=f"NCBIGene:{670 + index}",
        source_url=f"https://www.ncbi.nlm.nih.gov/gene/{670 + index}",
        layer="layer_1_graph",
        field="symbol",
        claim_text=f"Feature number {index}.",
        evidence_kind="primary_assertion",
        assertion_confidence="asserted",
        population_ancestry_context=None,
        license="public_domain_us_gov",
    )


def _answer_trust(outcome: str = "answer", **overrides: Any) -> TrustSignalPayload:
    fields: dict[str, Any] = {
        "outcome": outcome,
        "risk_tier": "low",
        "grounded": outcome == "answer",
        "triangulated": None,
        "citation_id": None,
        "scope": "answer",
    }
    fields.update(overrides)
    return TrustSignalPayload(**fields)


def _done(outcome: str, *, trust_line: str | None = None) -> DonePayload:
    return DonePayload(
        total_cost_usd=0.01,
        total_tool_calls=1,
        elapsed_ms=100,
        trust_outcome=outcome,  # type: ignore[arg-type]
        trust_line=trust_line,
    )


def _think(question: str | None = None, options: list[str] | None = None) -> ThinkPayload:
    return ThinkPayload(
        narrative="classified",
        query_class="lookup",
        resolved_entities=[],
        clarifying_question=question,
        clarifying_options=options,
    )


def _stream_of(*items: tuple[str, Any]) -> Callable[..., AsyncIterator[Event]]:
    """An async `run_streaming` stand-in yielding `items` in order, each a
    `(type, payload)` pair, numbered from seq 0."""

    async def _stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
        for seq, (event_type, payload) in enumerate(items):
            yield _event(event_type, query.trace_id, seq, payload)

    return _stream


_GUARD_OK = ("guard", GuardPayload(passed=True, category="ok", reason=None))


def _ask_back_stream(*, citation: bool = False, fatal: bool = False, guard_refused: bool = False):
    """The GERD run as develop emitted it on 2026-09-26
    (`testing/Developer/reports/2026-09-26_integrations_audit/evidence/
    runs/rest_05_gerd.json`), with three optional distortions used to prove
    the relabel's limits."""
    guard = (
        ("guard", GuardPayload(passed=False, category="off_topic", reason="off topic"))
        if guard_refused
        else _GUARD_OK
    )
    items: list[tuple[str, Any]] = [
        guard,
        ("think", _think(_GERD_QUESTION, list(_GERD_OPTIONS))),
        ("plan", PlanPayload(narrative="no tool", tool_calls=[])),
        ("token", TokenPayload(text=_GERD_QUESTION + " ", marker_ids=[])),
    ]
    if citation:
        items.append(("citation", _citation(1)))
    if fatal:
        items.append(
            (
                "error",
                ErrorPayload(
                    fatal=True,
                    scope="run",
                    source="write",
                    error_class="unexpected",
                    message="internal detail",
                    retry_after_s=0,
                ),
            )
        )
    else:
        items.append(
            (
                "trust_signal",
                _answer_trust(
                    "refuse",
                    risk_tier="unknown",
                    grounded=False,
                    message=_GERD_QUESTION,
                    fallback_link="https://www.ncbi.nlm.nih.gov/search/all/?term=GERD",
                ),
            )
        )
        items.append(("done", _done("refuse")))
    return _stream_of(*items)


def _long_answer_stream(count: int, *, trust_line: str | None = _TRUST_LINE):
    """An answer citing `count` records, one marker per sentence, the shape
    of the Marfan answer that lost 35 of its 85 citations on this surface."""
    items: list[tuple[str, Any]] = [_GUARD_OK]
    for index in range(1, count + 1):
        items.append(
            ("token", TokenPayload(text=f"Feature {index} [{index}]. ", marker_ids=[f"c{index}"]))
        )
    for index in range(1, count + 1):
        items.append(("citation", _citation(index)))
    items.append(("trust_signal", _answer_trust("answer")))
    items.append(("done", _done("answer", trust_line=trust_line)))
    return _stream_of(*items)


async def _fold(monkeypatch: pytest.MonkeyPatch, stream: Callable[..., AsyncIterator[Event]]):
    """Run `stream` through a fresh registry and the real MCP fold."""
    registry = RunRegistry()
    monkeypatch.setattr(run_registry_module, "run_streaming", stream)
    monkeypatch.setattr(server_module, "default_registry", registry)
    run_id = str(uuid.uuid4())
    registry.create_run(
        Query(text="GERD", session_id="s-parity", trace_id=run_id, user_id="u1"),
        RequestContext(surface="mcp", operator_mode=False),
        run_id=run_id,
    )
    return await server_module._fold_run_to_response(run_id, session_id="s-parity")


_MARKER = re.compile(r"\[(\d+)\]")


# ---------------------------------------------------------------------------
# "A long answer keeps every citation it points at."
# ---------------------------------------------------------------------------


class TestEveryMarkerKeepsItsCitation:
    @pytest.mark.asyncio
    async def test_a_ninety_three_citation_answer_keeps_all_ninety_three(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: put `_MAX_CITATIONS` back to 50. The
        # fold then returns 50 citations, the answer still carries [51] to
        # [93], and the marker check below names them.
        result = await _fold(monkeypatch, _long_answer_stream(93))

        markers = {int(number) for number in _MARKER.findall(result.answer)}
        returned = {citation.display_index for citation in result.citations}
        assert len(markers) == 93, "populate check: the answer must carry 93 markers"
        assert markers - returned == set(), f"markers with no citation: {sorted(markers - returned)}"
        assert len(result.citations) == 93
        assert "omitted" not in (result.trust_signal.message or "")

    @pytest.mark.asyncio
    async def test_a_bound_remains_and_what_it_cuts_is_disclosed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # `production-standards.md` requires a bound on every array. Mutation
        # that turns this red: drop the cap in the fold (more than the cap
        # comes back) or drop its disclosure (the cut goes unsaid).
        cap = server_module._MAX_CITATIONS
        result = await _fold(monkeypatch, _long_answer_stream(cap + 3))

        assert len(result.citations) == cap
        assert f"3 citation(s) beyond this surface's {cap}-citation limit" in (
            result.trust_signal.message or ""
        )
        schema = server_module.AskBiomedicalQuestionOutput.model_json_schema()
        assert schema["properties"]["citations"]["maxItems"] == cap

    def test_the_citation_cap_is_the_runs_own_bound(self) -> None:
        # The run bounds one answer's citations at `core/graph.py`'s
        # `_MAX_FINDINGS_FOR_DISPLAY` (one citation per display slot). The
        # event contract bounds none, since every citation is its own event.
        # Mutation that turns this red: raise the run's display cap past this
        # surface's cap without moving this one, which is how the 50 cap
        # silently started dropping citations once the run could exceed it.
        from system_03_search_agent.core import graph

        assert server_module._MAX_CITATIONS >= graph._MAX_FINDINGS_FOR_DISPLAY, (
            "the run can now emit more citations than this surface returns; raise "
            "_MAX_CITATIONS in adapters/mcp/server.py to match"
        )
        assert server_module._MAX_CITATIONS == 100


# ---------------------------------------------------------------------------
# "A bare topic gives the agent the clarifying options, and it is not
# labelled a refusal."
# ---------------------------------------------------------------------------


class TestAskBackIsNotARefusal:
    @pytest.mark.asyncio
    async def test_gerd_comes_back_as_a_question_with_its_four_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: delete the `if ask_back:` relabel in
        # `_fold_run_to_response` (outcome reads "refuse", as develop did on
        # 2026-09-26), or stop reading `think` (question and options None).
        result = await _fold(monkeypatch, _ask_back_stream())

        assert result.trust_signal.outcome == "ask"
        assert result.trust_signal.outcome != "refuse"
        assert result.clarifying_question == _GERD_QUESTION
        assert result.clarifying_options == _GERD_OPTIONS
        assert result.answer == _GERD_QUESTION
        # Nothing else about the verdict is raised: it was not grounded and
        # no risk assessment ran, and it still says so.
        assert result.trust_signal.grounded is False
        assert result.trust_signal.risk_tier == "unknown"
        assert result.citations == []

    @pytest.mark.asyncio
    async def test_a_guardrail_refusal_stays_a_refusal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop the guard clause from
        # `_is_ask_back`. The web shows a guardrail refusal's own wording
        # over any clarifying question, and so must this surface.
        result = await _fold(monkeypatch, _ask_back_stream(guard_refused=True))

        assert result.trust_signal.outcome == "refuse"
        assert result.clarifying_question is None
        assert result.clarifying_options is None

    @pytest.mark.asyncio
    async def test_a_run_that_cited_something_is_never_relabelled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop the zero-citation clause from
        # `_is_ask_back`, which would let the relabel touch an answer.
        result = await _fold(monkeypatch, _ask_back_stream(citation=True))

        assert result.trust_signal.outcome == "refuse"
        assert result.clarifying_options is None

    @pytest.mark.asyncio
    async def test_a_crashed_run_is_never_dressed_as_a_question(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop the fatal-error clause from
        # `_is_ask_back`.
        result = await _fold(monkeypatch, _ask_back_stream(fatal=True))

        assert result.trust_signal.outcome != "ask"
        assert result.clarifying_question is None
        assert result.clarifying_options is None

    @pytest.mark.asyncio
    async def test_an_answer_carries_no_clarifying_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: emit the options on every run.
        result = await _fold(monkeypatch, _long_answer_stream(2))

        assert result.trust_signal.outcome == "answer"
        assert result.clarifying_question is None
        assert result.clarifying_options is None


# ---------------------------------------------------------------------------
# "The agent gets the same trust line the web shows."
# ---------------------------------------------------------------------------


class TestTrustLine:
    @pytest.mark.asyncio
    async def test_the_done_events_trust_line_reaches_the_agent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: stop reading `DonePayload.trust_line`
        # in the fold, which is what develop does today.
        result = await _fold(monkeypatch, _long_answer_stream(3))

        assert result.trust_line == _TRUST_LINE

    @pytest.mark.asyncio
    async def test_a_blank_trust_line_is_none_as_on_the_web(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The web trims and treats blank as absent (`useRunView.ts`).
        # Mutation that turns this red: pass the raw value through.
        result = await _fold(monkeypatch, _long_answer_stream(3, trust_line="   "))

        assert result.trust_line is None


# ---------------------------------------------------------------------------
# "An agent knows how to continue a conversation": the schema half. The
# returned-session half needs the auth path and is further down.
# ---------------------------------------------------------------------------


class TestTheSchemaTellsAnAgentHowToContinue:
    def test_session_id_and_audience_depth_are_described_in_words(self) -> None:
        # Mutation that turns this red: drop the `description=` from either
        # parameter, which is the state the audit found (gap 8).
        tools = {tool.name: tool for tool in asyncio.run(server_module.server.list_tools())}
        ask = tools["ask_biomedical_question"]
        properties = ask.input_schema["properties"]

        assert "follow-up" in properties["session_id"]["description"]
        assert "plain_language" in properties["audience_depth"]["description"]
        assert "session_id" in ask.description
        assert "session_id" in ask.output_schema["properties"]
        assert "follow-up" in ask.output_schema["properties"]["session_id"]["description"]

    def test_the_server_advertises_the_three_parity_tools(self) -> None:
        # Mutation that turns this red: unregister any of the three.
        names = {tool.name for tool in asyncio.run(server_module.server.list_tools())}

        assert names == {
            "ask_biomedical_question",
            "list_past_searches",
            "reopen_past_answer",
            "send_answer_feedback",
        }

    def test_no_new_tool_takes_an_owner_from_its_arguments(self) -> None:
        # The ownership design in one assertion: every read and write is
        # scoped by the bearer token, so no argument may name an account.
        # Mutation that turns this red: add an `owner_id`, `user_id` or
        # `account` parameter to any tool.
        for tool in asyncio.run(server_module.server.list_tools()):
            arguments = set(tool.input_schema.get("properties", {}))
            assert not arguments & {"owner_id", "user_id", "account", "account_id", "email"}, (
                tool.name
            )


# ---------------------------------------------------------------------------
# "A reopened answer says how many of its markers point at nothing." Fix
# round, F-8.10-J02 and A02: capture stores at most 50 citations (card 54's
# cap), and `citations_omitted` used to count only stored entries that
# failed validation, so it said 0 for markers [51] to [60].
# ---------------------------------------------------------------------------


class TestAReopenedAnswerCountsWhatItCannotShow:
    def test_markers_past_the_stored_citations_are_counted(self) -> None:
        # The judge's shape. Mutation that turns this red: count only stored
        # entries left out again -> 0.
        stored = [_citation(index).model_dump() for index in range(1, 51)]
        markdown = " ".join(f"Record {index} is relevant [{index}]." for index in range(1, 61))

        citations, omitted = server_module._reopened_citations(stored, markdown)

        assert [c.display_index for c in citations] == list(range(1, 51))
        assert omitted == 10

    def test_a_left_out_entry_is_counted_once_not_twice(self) -> None:
        # [2] was stored but no longer validates, [3] was never stored: two
        # omissions. Mutation that turns this red: count a left-out entry's
        # own marker a second time (3), or stop counting it at all (1).
        invalid = {**_citation(2).model_dump(), "source_url": "https://elsewhere.example/2"}
        stored = [_citation(1).model_dump(), invalid]

        citations, omitted = server_module._reopened_citations(stored, "One [1]. Two [2]. Three [3].")

        assert [c.display_index for c in citations] == [1]
        assert omitted == 2

    def test_an_answer_with_every_citation_stored_omits_nothing(self) -> None:
        stored = [_citation(index).model_dump() for index in (1, 2)]

        citations, omitted = server_module._reopened_citations(stored, "A [1][2]. B [2].")

        assert len(citations) == 2
        assert omitted == 0


def test_past_answer_timestamps_are_bounded_in_both_output_schemas() -> None:
    asked_at = datetime(2026, 10, 6, 12, 30, tzinfo=UTC)
    models = (
        server_module.PastSearch(
            trace_id="t1", question="BRCA1?", asked_at=asked_at,
            trust_signal="answer", citation_count=1,
        ),
        server_module.ReopenedAnswerOutput(
            trace_id="t1", question="BRCA1?", asked_at=asked_at,
            audience_depth="researcher", answer_markdown="BRCA1 [1].",
            trust_signal="answer",
        ),
    )
    for model in models:
        schema = type(model).model_json_schema()["properties"]["asked_at"]
        assert schema["maxLength"] == 40
        assert model.model_dump(mode="json")["asked_at"].startswith("2026-10-06T12:30")


# ---------------------------------------------------------------------------
# DATABASE-BACKED from here on: the auth path and the three new tools.
# ---------------------------------------------------------------------------


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


_needs_database = pytest.mark.skipif(
    not _can_connect(),
    reason=(
        "search_agent_users PostgreSQL database is not reachable; set USER_DB_URL and "
        "ensure the server is running to run the MCP parity tool tests"
    ),
)


@pytest.fixture
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


async def _new_account() -> tuple[str, dict[str, str]]:
    """Sign up and sign in one throwaway account through the real routes."""
    import httpx2

    from system_03_search_agent.adapters.web_sse.app import app

    email, password = f"{uuid.uuid4()}@example.com", "Str0ngPassw0rd!"
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url=_BASE_URL
    ) as client:
        signup = await client.post("/auth/signup", json={"email": email, "password": password})
        assert signup.status_code == 201
        login = await client.post("/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200
        return signup.json()["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}


def _build_test_mcp_app():
    from fastapi import FastAPI

    sub_app = server_module.server.streamable_http_app(stateless_http=True, streamable_http_path="/")

    @asynccontextmanager
    async def _test_lifespan(test_app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(sub_app.router.lifespan_context(sub_app))
            yield

    test_app = FastAPI(lifespan=_test_lifespan)
    test_app.mount("/mcp", sub_app)
    return test_app


async def _call(headers: Mapping[str, str] | None, name: str, arguments: dict[str, object]):
    """One real MCP client call to tool `name`, returning its `CallToolResult`."""
    import httpx2
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    mcp_app = _build_test_mcp_app()
    async with (
        mcp_app.router.lifespan_context(mcp_app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=mcp_app),
            base_url=_BASE_URL,
            headers=dict(headers) if headers else None,
            follow_redirects=True,
        ) as http_client,
        streamable_http_client(f"{_BASE_URL}/mcp", http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        return await session.call_tool(name, arguments)


async def _call_expecting_error(
    headers: Mapping[str, str] | None, name: str, arguments: dict[str, object]
) -> str:
    """Call `name` and return the MCP error message it raised."""
    from mcp.shared.exceptions import MCPError

    def _first(group: BaseExceptionGroup) -> MCPError | None:
        for exc in group.exceptions:
            if isinstance(exc, MCPError):
                return exc
            if isinstance(exc, BaseExceptionGroup):
                found = _first(exc)
                if found is not None:
                    return found
        return None

    try:
        result = await _call(headers, name, arguments)
    except MCPError as exc:
        return exc.message
    except BaseExceptionGroup as group:
        found = _first(group)
        if found is None:
            raise
        return found.message
    raise AssertionError(f"expected {name} to refuse, it returned {result.structured_content!r}")


async def _seed_row(
    *,
    owner_id: str,
    trace_id: str | None = None,
    question: str = "Which diseases are associated with BRCA1?",
    answer_markdown: str | None = None,
    audience_depth: str | None = None,
) -> str:
    """One real `interactions` row through the real writer, the same shape a
    capture produces. Returns its trace id."""
    from system_03_search_agent.feedback.contracts import InteractionRow
    from system_03_search_agent.feedback.writer import write_interaction

    trace_id = trace_id or f"paritytest-{uuid.uuid4().hex}"
    await write_interaction(
        InteractionRow(
            trace_id=trace_id,
            owner_id=owner_id,
            query_text=question,
            query_class="lookup",
            trust_signal="answer",
            rubric_outcome="pass",
            citations=[_citation(1).model_dump()],
            answer_markdown=answer_markdown,
            audience_depth=audience_depth,  # type: ignore[arg-type]
            answer_trust_line=_TRUST_LINE if answer_markdown else None,
        )
    )
    return trace_id


def _stored_feedback(trace_id: str) -> Any:
    """`interactions.user_feedback` straight from the table, never through
    the code under test, so a refusal that writes anyway is caught."""
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.connect() as conn:
            return conn.execute(
                sa.text("SELECT user_feedback FROM interactions WHERE trace_id = :t"),
                {"t": trace_id},
            ).scalar_one()
    finally:
        engine.dispose()


async def _ask(monkeypatch: pytest.MonkeyPatch, headers: Mapping[str, str], arguments: dict):
    """Ask through the real tool over a fixed stream; return the result and
    the `Query` the core received."""
    received: list[Query] = []

    async def _recording(query: Query, context: RequestContext) -> AsyncIterator[Event]:
        received.append(query)
        async for event in _long_answer_stream(1)(query, context):
            yield event

    monkeypatch.setattr(run_registry_module, "run_streaming", _recording)
    result = await _call(headers, "ask_biomedical_question", arguments)
    return result, received[-1]


@_needs_database
@pytest.mark.usefixtures("_auth_secret")
class TestAConversationCanContinue:
    @pytest.mark.asyncio
    async def test_the_session_id_comes_back_and_carries_the_follow_up(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: stop returning `session_id` (the
        # first assertion), or build the follow-up's `Query` without the
        # caller's session id (the last).
        _user_id, headers = await _new_account()

        first, first_query = await _ask(monkeypatch, headers, {"query": "What gene is BRCA1?"})
        assert first.is_error is False
        session_id = first.structured_content["session_id"]
        assert session_id == first_query.session_id
        assert session_id, "an answer must name the conversation it belongs to"

        second, second_query = await _ask(
            monkeypatch,
            headers,
            {"query": "What variants of it are pathogenic?", "session_id": session_id},
        )
        assert second.structured_content["session_id"] == session_id
        assert second_query.session_id == session_id
        assert second.structured_content["run_id"] != first.structured_content["run_id"]

    @pytest.mark.asyncio
    async def test_plain_language_reaches_the_core(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # "An AI agent can ask for Plain language." Mutation that turns this
        # red: drop `plain_language` from `AudienceDepth` (refused before any
        # run) or stop passing the depth through to `Query`.
        _user_id, headers = await _new_account()

        result, query = await _ask(
            monkeypatch, headers, {"query": "What gene is BRCA1?", "audience_depth": "plain_language"}
        )
        assert result.is_error is False
        assert query.audience_depth == "plain_language"

        _result, default_query = await _ask(monkeypatch, headers, {"query": "What gene is BRCA1?"})
        assert default_query.audience_depth == "researcher"


@_needs_database
@pytest.mark.usefixtures("_auth_secret")
class TestPastSearchesAreYoursAlone:
    @pytest.mark.asyncio
    async def test_one_account_never_sees_anothers_searches(self) -> None:
        # Mutation that turns this red: key `list_history` on anything but
        # the token's own account, for example a hardcoded or argument
        # owner, and B's list shows A's row.
        a_id, a_headers = await _new_account()
        b_id, b_headers = await _new_account()
        a_trace = await _seed_row(owner_id=f"user:{a_id}", question="A's own question")
        b_trace = await _seed_row(owner_id=f"user:{b_id}", question="B's own question")

        a_list = (await _call(a_headers, "list_past_searches", {})).structured_content
        b_list = (await _call(b_headers, "list_past_searches", {})).structured_content

        a_traces = {item["trace_id"] for item in a_list["items"]}
        b_traces = {item["trace_id"] for item in b_list["items"]}
        assert a_trace in a_traces, "populate check: A must see A's own row"
        assert b_trace in b_traces, "populate check: B must see B's own row"
        assert a_trace not in b_traces
        assert b_trace not in a_traces
        assert a_list["count"] == len(a_list["items"])

    @pytest.mark.asyncio
    async def test_a_limit_over_the_rest_bound_is_refused(self) -> None:
        # The REST route refuses `limit` above `MAX_LIMIT` rather than
        # clamping it. Mutation that turns this red: drop `le=MAX_LIMIT`.
        from system_03_search_agent.feedback.history import MAX_LIMIT

        _a_id, a_headers = await _new_account()
        result = await _call(a_headers, "list_past_searches", {"limit": MAX_LIMIT + 1})
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_no_token_lists_nothing(self) -> None:
        message = await _call_expecting_error(None, "list_past_searches", {})
        assert message == server_module._NO_TOKEN_MESSAGE


@_needs_database
@pytest.mark.usefixtures("_auth_secret")
class TestGuestsGetNoMoreThanRest:
    @pytest.mark.asyncio
    async def test_a_real_guest_token_is_refused_by_every_parity_tool(self) -> None:
        # This surface is registered accounts only, so a guest gets less here
        # than on REST, never more. Mutation that turns this red: resolve the
        # caller with a resolver that also accepts guest tokens, for example
        # `auth.dependencies.resolve_caller_from_bearer_token`.
        import httpx2

        from system_03_search_agent.adapters.web_sse.app import app

        async with httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), base_url=_BASE_URL
        ) as client:
            minted = await client.post("/auth/guest")
        assert minted.status_code == 201, "populate check: a real guest token was minted"
        guest = {"Authorization": f"Bearer {minted.json()['guest_token']}"}

        for name, arguments in (
            ("list_past_searches", {}),
            ("reopen_past_answer", {"trace_id": f"paritytest-{uuid.uuid4().hex}"}),
            ("send_answer_feedback", {"run_id": str(uuid.uuid4()), "rating": "up"}),
        ):
            message = await _call_expecting_error(guest, name, arguments)
            # Card 62: a guest token fails to verify as an account's, so it
            # gets the invalid-token words, which say an account is needed.
            assert message == server_module._INVALID_TOKEN_MESSAGE, name


@_needs_database
@pytest.mark.usefixtures("_auth_secret")
class TestReopeningIsYoursAlone:
    @pytest.mark.asyncio
    async def test_the_owner_reopens_the_answer_they_got(self) -> None:
        a_id, a_headers = await _new_account()
        trace = await _seed_row(
            owner_id=f"user:{a_id}",
            answer_markdown="BRCA1 is a protein-coding gene [1].",
            audience_depth="plain_language",
        )

        result = await _call(a_headers, "reopen_past_answer", {"trace_id": trace})

        assert result.is_error is False
        content = result.structured_content
        assert content["answer_markdown"] == "BRCA1 is a protein-coding gene [1]."
        assert content["audience_depth"] == "plain_language"
        assert content["trust_line"] == _TRUST_LINE
        assert [c["citation_id"] for c in content["citations"]] == ["c1"]
        assert content["citations_omitted"] == 0

    @pytest.mark.asyncio
    async def test_a_sixty_marker_answer_says_ten_of_its_markers_point_at_nothing(self) -> None:
        # Fix round, F-8.10-J02: the judge's `probe_capture60.py`, end to end.
        # The answer goes through the real capture and the real writer, which
        # keep 50 of its 60 citations (card 54's cap), and comes back through
        # the real tool. Mutation that turns this red: count only stored
        # entries left out again -> `citations_omitted` is 0.
        from system_03_search_agent.feedback.capture import assemble_interaction
        from system_03_search_agent.feedback.writer import write_interaction

        a_id, a_headers = await _new_account()
        trace = f"paritytest-{uuid.uuid4().hex}"
        items: list[tuple[str, Any]] = [_GUARD_OK]
        for index in range(1, 61):
            items.append(
                ("token", TokenPayload(text=f"Record {index} is relevant [{index}]. ", marker_ids=[f"c{index}"]))
            )
        items.extend(("citation", _citation(index)) for index in range(1, 61))
        items.append(("trust_signal", _answer_trust("answer")))
        items.append(("done", _done("answer", trust_line=_TRUST_LINE)))
        events = [_event(kind, trace, seq, payload) for seq, (kind, payload) in enumerate(items)]
        row = assemble_interaction(
            Query(
                text="Sixty records",
                session_id="s-sixty",
                trace_id=trace,
                user_id=None,
                owner_id=f"user:{a_id}",
                audience_depth="researcher",
            ),
            events,
        )
        assert len(row.citations) == 50, "populate check: capture keeps 50 of the 60"
        await write_interaction(row)

        result = await _call(a_headers, "reopen_past_answer", {"trace_id": trace})

        assert result.is_error is False
        content = result.structured_content
        assert len(content["citations"]) == 50
        assert content["citations_omitted"] == 10

    @pytest.mark.asyncio
    async def test_another_account_cannot_reopen_it_and_learns_nothing(self) -> None:
        # Mutation that turns this red: fetch the saved answer by trace id
        # alone, or answer "not yours" differently from "no such search",
        # which would confirm to a stranger that the trace id exists.
        a_id, _a_headers = await _new_account()
        _b_id, b_headers = await _new_account()
        trace = await _seed_row(
            owner_id=f"user:{a_id}",
            answer_markdown="A's private answer [1].",
            audience_depth="researcher",
        )

        refused = await _call_expecting_error(b_headers, "reopen_past_answer", {"trace_id": trace})
        missing = await _call_expecting_error(
            b_headers, "reopen_past_answer", {"trace_id": f"paritytest-{uuid.uuid4().hex}"}
        )

        assert refused == server_module._NO_SAVED_ANSWER_MESSAGE
        assert refused == missing
        assert "A's private answer" not in refused


@_needs_database
@pytest.mark.usefixtures("_auth_secret")
class TestFeedbackIsYoursAlone:
    @pytest.mark.asyncio
    async def test_another_account_cannot_rate_your_run_and_nothing_is_written(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: skip `resolve_owned_run` AND pass the
        # run's own owner to `record_feedback` instead of the caller's.
        # Skipping `resolve_owned_run` alone does NOT, because
        # `record_feedback`'s own check on the stored row still refuses
        # (F-8.10-J07); `test_the_registry_check_refuses_on_its_own` below is
        # the test for that one. Asserted on the STORED value, because a
        # refusal that writes anyway passes an error assertion.
        _a_id, a_headers = await _new_account()
        _b_id, b_headers = await _new_account()
        asked, _query = await _ask(monkeypatch, a_headers, {"query": "What gene is BRCA1?"})
        run_id = asked.structured_content["run_id"]
        await _seed_row(owner_id=f"user:{_a_id}", trace_id=run_id)

        message = await _call_expecting_error(
            b_headers, "send_answer_feedback", {"run_id": run_id, "rating": "down"}
        )

        assert message == server_module._NOT_YOUR_RUN_MESSAGE
        assert _stored_feedback(run_id) is None

    @pytest.mark.asyncio
    async def test_the_owner_rates_their_own_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        a_id, a_headers = await _new_account()
        asked, _query = await _ask(monkeypatch, a_headers, {"query": "What gene is BRCA1?"})
        run_id = asked.structured_content["run_id"]
        await _seed_row(owner_id=f"user:{a_id}", trace_id=run_id)

        result = await _call(
            a_headers,
            "send_answer_feedback",
            {
                "run_id": run_id,
                "rating": "down",
                "comment": "The second sentence is wrong.",
                "citation_flags": [{"citation_id": "c1", "reason": "Citation does not support the claim"}],
            },
        )

        assert result.is_error is False
        assert result.structured_content == {"run_id": run_id, "recorded": True}
        stored = _stored_feedback(run_id)
        assert stored["rating"] == "down"
        assert stored["comment"] == "The second sentence is wrong."
        assert stored["citation_flags"] == [
            {"citation_id": "c1", "reason": "Citation does not support the claim"}
        ]

    @pytest.mark.asyncio
    async def test_a_call_with_nothing_to_record_is_refused_and_keeps_earlier_feedback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Fix round, F-8.10-A08: a call with no rating, comment, flag or
        # citation flag reported `recorded: True` and replaced the earlier
        # feedback with nothing. Mutation that turns this red: drop the
        # nothing-to-record check -> the call succeeds and the stored rating
        # is gone.
        a_id, a_headers = await _new_account()
        asked, _query = await _ask(monkeypatch, a_headers, {"query": "What gene is BRCA1?"})
        run_id = asked.structured_content["run_id"]
        await _seed_row(owner_id=f"user:{a_id}", trace_id=run_id)
        first = await _call(
            a_headers, "send_answer_feedback", {"run_id": run_id, "rating": "down", "comment": "Wrong gene."}
        )
        assert first.is_error is False, "populate check: the first feedback is stored"

        for empty in (
            {"run_id": run_id},
            {"run_id": run_id, "comment": "   ", "flagged_reason": ""},
            {"run_id": run_id, "citation_flags": []},
            {"run_id": run_id, "comment": "\u200b"},
            {"run_id": run_id, "flagged_reason": "\u200b\u200c"},
        ):
            message = await _call_expecting_error(a_headers, "send_answer_feedback", empty)
            assert message == server_module._NOTHING_TO_RECORD_MESSAGE, empty

        stored = _stored_feedback(run_id)
        assert stored["rating"] == "down"
        assert stored["comment"] == "Wrong gene."

    @pytest.mark.asyncio
    async def test_the_stored_rows_own_owner_is_checked_too(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The second of REST's two checks. The registry says A owns the run,
        # the stored row says someone else does: `record_feedback` refuses
        # under its row lock and nothing is written. Mutation that turns
        # this red: catch `FeedbackOwnershipError` and report success.
        _a_id, a_headers = await _new_account()
        c_id, _c_headers = await _new_account()
        asked, _query = await _ask(monkeypatch, a_headers, {"query": "What gene is BRCA1?"})
        run_id = asked.structured_content["run_id"]
        await _seed_row(owner_id=f"user:{c_id}", trace_id=run_id)

        message = await _call_expecting_error(
            a_headers, "send_answer_feedback", {"run_id": run_id, "rating": "up"}
        )

        assert message == server_module._NOT_YOUR_RUN_MESSAGE
        assert _stored_feedback(run_id) is None

    @pytest.mark.asyncio
    async def test_the_registry_check_refuses_on_its_own(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Fix round, F-8.10-J07: the first of REST's two checks, with the
        # second out of the way. A asked the question, so the registry says A
        # owns the run; the stored row says B does, so `record_feedback`'s
        # own check would let B write. Only `resolve_owned_run` stands
        # between B and A's run. Mutation that turns this red: skip
        # `resolve_owned_run`, for example by looking the run up with
        # `default_registry.get_run(run_id)` -> B's rating is stored.
        _a_id, a_headers = await _new_account()
        b_id, b_headers = await _new_account()
        asked, _query = await _ask(monkeypatch, a_headers, {"query": "What gene is BRCA1?"})
        run_id = asked.structured_content["run_id"]
        await _seed_row(owner_id=f"user:{b_id}", trace_id=run_id)

        message = await _call_expecting_error(
            b_headers, "send_answer_feedback", {"run_id": run_id, "rating": "down"}
        )

        assert message == server_module._NOT_YOUR_RUN_MESSAGE
        assert _stored_feedback(run_id) is None

    @pytest.mark.asyncio
    async def test_an_unknown_run_says_what_to_do_next(self) -> None:
        _a_id, a_headers = await _new_account()
        message = await _call_expecting_error(
            a_headers, "send_answer_feedback", {"run_id": str(uuid.uuid4()), "rating": "up"}
        )
        assert message == server_module._NO_SUCH_RUN_MESSAGE

    @pytest.mark.asyncio
    async def test_an_argument_the_tool_does_not_declare_is_refused(self) -> None:
        # F-4.1-A-13's rule, per tool. Mutation that turns this red: check
        # the new tools against the ask tool's names, or not at all.
        _a_id, a_headers = await _new_account()
        message = await _call_expecting_error(
            a_headers,
            "send_answer_feedback",
            {"run_id": str(uuid.uuid4()), "owner_id": "user:someone-else"},
        )
        assert "owner_id" in message
