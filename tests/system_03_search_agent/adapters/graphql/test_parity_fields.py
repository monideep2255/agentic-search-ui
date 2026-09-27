"""Build phase 8.10, T-8.10-06: GraphQL keeps every citation and the
clarifying options.

The ledger `tracker/phase_8.10.md` and the integrations audit of 2026-09-26
(gaps 6 and 9). Each class is one acceptance line in the words a person
would use; each test names the mutation that turns it red.

- Fold-level arms run against a fresh, test-local `RunRegistry`, the seam
  `test_fold.py` uses, so they run on any machine.
- The schema arm reads the real printed schema, database-free.
- One end-to-end arm drives the real app over HTTP with a real account, so
  it needs the user database; CI provides one.

WHAT THIS FILE DOES NOT COVER: a live model (every run is a fixed stream of
contract-valid events), and the trust outcome of an ask-back, which this
surface deliberately keeps as the run reported it; see `types.py`'s comment
above `AskResult`.
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
import sqlalchemy as sa

from system_03_search_agent.adapters.graphql import fold as fold_module
from system_03_search_agent.adapters.graphql.types import MAX_CITATIONS
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

_GERD_QUESTION = "What would you like to know about GERD?"
_GERD_OPTIONS = [
    "What is GERD?",
    "Which genetic variants are associated with GERD?",
    "Are there clinical trials on GERD treatments?",
    "What does recent research say about GERD?",
]
_TRUST_LINE = "Based on 3 sources, not yet confirmed"
_MARKER = re.compile(r"\[(\d+)\]")


def _event(event_type: str, trace_id: str, seq: int, payload: Any) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=trace_id,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


def _citation(index: int, *, source_url: str | None = None) -> CitationPayload:
    return CitationPayload(
        citation_id=f"c{index}",
        display_index=index,
        source="NCBIGene",
        source_id=f"NCBIGene:{670 + index}",
        source_url=source_url or f"https://www.ncbi.nlm.nih.gov/gene/{670 + index}",
        layer="layer_1_graph",
        field="symbol",
        claim_text=f"Feature number {index}.",
        evidence_kind="primary_assertion",
        assertion_confidence="asserted",
        population_ancestry_context=None,
        license="public_domain_us_gov",
    )


def _trust(outcome: str = "answer", **overrides: Any) -> TrustSignalPayload:
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


def _stream_of(*items: tuple[str, Any]) -> Callable[..., AsyncIterator[Event]]:
    async def _stream(query: Query, context: RequestContext) -> AsyncIterator[Event]:
        for seq, (event_type, payload) in enumerate(items):
            if isinstance(payload, _RawPayload):
                # `Event`'s own validator would refuse a malformed payload at
                # construction; `model_construct` is how a hostile or drifted
                # producer's event reaches the fold, as in `test_fold.py`.
                yield Event.model_construct(
                    type=event_type,
                    version="v1",
                    trace_id=query.trace_id,
                    seq=seq,
                    ts=datetime.now(UTC),
                    payload=payload.model_dump(),
                )
            else:
                yield _event(event_type, query.trace_id, seq, payload)

    return _stream


_GUARD_OK = ("guard", GuardPayload(passed=True, category="ok", reason=None))


def _ask_back_stream(*, citation: bool = False, fatal: bool = False, guard_refused: bool = False):
    """The GERD run as develop emitted it on 2026-09-26, with optional
    distortions that must each switch the clarifying fields off."""
    guard = (
        ("guard", GuardPayload(passed=False, category="off_topic", reason="off topic"))
        if guard_refused
        else _GUARD_OK
    )
    items: list[tuple[str, Any]] = [
        guard,
        (
            "think",
            ThinkPayload(
                narrative="asks which aspect",
                query_class="lookup",
                resolved_entities=[],
                clarifying_question=_GERD_QUESTION,
                clarifying_options=list(_GERD_OPTIONS),
            ),
        ),
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
        return _stream_of(*items)
    items.append(
        (
            "trust_signal",
            _trust(
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


def _long_answer_stream(count: int, *, trust_line: str | None = _TRUST_LINE, bad_url_at: int = 0):
    """An answer citing `count` records, one marker per sentence. With
    `bad_url_at`, that citation carries an off-host URL the fold rejects."""
    items: list[tuple[str, Any]] = [_GUARD_OK]
    for index in range(1, count + 1):
        items.append(
            ("token", TokenPayload(text=f"Feature {index} [{index}]. ", marker_ids=[f"c{index}"]))
        )
    for index in range(1, count + 1):
        citation = _citation(index)
        if index == bad_url_at:
            raw = citation.model_dump()
            raw["source_url"] = "https://evil.example/gene/1"
            items.append(("citation", _RawPayload(raw)))
        else:
            items.append(("citation", citation))
    items.append(("trust_signal", _trust("answer")))
    items.append(("done", _done("answer", trust_line=trust_line)))
    return _stream_of(*items)


class _RawPayload:
    """A payload `_event` can dump that skipped model validation, the way a
    hostile or drifted producer would send it."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw

    def model_dump(self) -> dict[str, Any]:
        return dict(self._raw)


def _uncited_answer_stream():
    """A run that claims `answer` with a trust line and cites nothing; the
    fold's cite-or-refuse floor lowers it to `refuse`."""
    return _stream_of(
        _GUARD_OK,
        ("token", TokenPayload(text="BRCA1 causes every known disease.", marker_ids=[])),
        ("trust_signal", _trust("answer")),
        ("done", _done("answer", trust_line=_TRUST_LINE)),
    )


def _isolated_run(monkeypatch: pytest.MonkeyPatch, stream: Any) -> tuple[RunRegistry, str]:
    registry = RunRegistry()
    monkeypatch.setattr(run_registry_module, "run_streaming", stream)
    monkeypatch.setattr(fold_module, "default_registry", registry)
    run_id = str(uuid.uuid4())
    registry.create_run(
        Query(text="GERD", session_id="s-parity", trace_id=run_id, user_id="u1"),
        RequestContext(surface="graphql"),
        run_id=run_id,
    )
    return registry, run_id


async def _ask_and_run(monkeypatch: pytest.MonkeyPatch, stream: Any):
    """Fold one run through `ask` (`fold_run`) and `run` (`fold_run_snapshot`)."""
    registry, run_id = _isolated_run(monkeypatch, stream)
    ask = await fold_module.fold_run(run_id, persona_name="Mendel")
    for _ in range(200):
        if registry.get_run(run_id).finished:
            break
        await asyncio.sleep(0.01)
    run = await fold_module.fold_run_snapshot(run_id)
    return ask, run


# ---------------------------------------------------------------------------
# "A long answer keeps every citation it points at."
# ---------------------------------------------------------------------------


class TestEveryMarkerKeepsItsCitation:
    @pytest.mark.asyncio
    async def test_an_eighty_four_citation_answer_keeps_all_eighty_four(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The Marfan answer that lost 34 of 84 here on 2026-09-26. Mutation
        # that turns this red: put `MAX_CITATIONS` back to 50.
        ask, run = await _ask_and_run(monkeypatch, _long_answer_stream(84))

        for result in (ask, run):
            markers = {int(number) for number in _MARKER.findall(result.answer)}
            returned = {citation.display_index for citation in result.citations}
            assert len(markers) == 84, "populate check: the answer must carry 84 markers"
            assert markers - returned == set(), f"markers with no citation: {sorted(markers - returned)}"
            assert result.disclosures.citations_omitted == 0

    def test_the_citation_cap_is_the_runs_own_bound(self) -> None:
        # Mutation that turns this red: raise the run's display cap past this
        # surface's cap without moving this one.
        from system_03_search_agent.core import graph

        assert MAX_CITATIONS >= graph._MAX_FINDINGS_FOR_DISPLAY, (
            "the run can now emit more citations than GraphQL returns; raise "
            "MAX_CITATIONS in adapters/graphql/types.py to match"
        )
        assert MAX_CITATIONS == 100


# ---------------------------------------------------------------------------
# "A bare topic gives the clarifying options": the `ask` result carries them.
# ---------------------------------------------------------------------------


class TestClarifyingOptions:
    @pytest.mark.asyncio
    async def test_gerd_carries_its_question_and_four_options_on_ask_and_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: stop reading `think` in
        # `_consume_event`, or return None from `_parity_fields`.
        ask, run = await _ask_and_run(monkeypatch, _ask_back_stream())

        for result in (ask, run):
            assert result.clarifying_question == _GERD_QUESTION
            assert result.clarifying_options == _GERD_OPTIONS
            # This fold never raises a verdict, so the outcome is the run's.
            assert result.trust_signal.outcome == "refuse"
            assert result.citations == []

    @pytest.mark.asyncio
    async def test_a_guardrail_refusal_carries_no_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop the guard clause in
        # `_parity_fields`.
        ask, _run = await _ask_and_run(monkeypatch, _ask_back_stream(guard_refused=True))

        assert ask.clarifying_question is None
        assert ask.clarifying_options is None

    @pytest.mark.asyncio
    async def test_options_never_ride_on_a_run_that_cited_something(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: drop the citation clauses in
        # `_parity_fields`.
        ask, _run = await _ask_and_run(monkeypatch, _ask_back_stream(citation=True))

        assert ask.clarifying_question is None
        assert ask.clarifying_options is None

    @pytest.mark.asyncio
    async def test_a_crashed_run_carries_no_options(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mutation that turns this red: drop the fatal-error clause in
        # `_parity_fields`.
        ask, _run = await _ask_and_run(monkeypatch, _ask_back_stream(fatal=True))

        assert ask.disclosures.run_failed is True
        assert ask.clarifying_question is None
        assert ask.clarifying_options is None

    @pytest.mark.asyncio
    async def test_an_answer_carries_no_options(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ask, _run = await _ask_and_run(monkeypatch, _long_answer_stream(2))

        assert ask.clarifying_question is None
        assert ask.clarifying_options is None


# ---------------------------------------------------------------------------
# "The same trust line the web shows."
# ---------------------------------------------------------------------------


class TestTrustLine:
    @pytest.mark.asyncio
    async def test_the_done_events_trust_line_reaches_ask_and_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: stop reading `DonePayload.trust_line`.
        ask, run = await _ask_and_run(monkeypatch, _long_answer_stream(3))

        assert ask.trust_line == _TRUST_LINE
        assert run.trust_line == _TRUST_LINE

    @pytest.mark.asyncio
    async def test_a_blank_trust_line_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        ask, _run = await _ask_and_run(monkeypatch, _long_answer_stream(3, trust_line="  "))

        assert ask.trust_line is None

    @pytest.mark.asyncio
    async def test_no_trust_line_beside_a_verdict_the_fold_lowered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The run said "answer" with a trust line and cited nothing; the
        # cite-or-refuse floor reports "refuse". A line saying "Based on 3
        # sources" beside that refusal would read more confident than the
        # result. Mutation that turns this red: return `acc.trust_line`
        # without comparing the final outcome.
        ask, _run = await _ask_and_run(monkeypatch, _uncited_answer_stream())

        assert ask.trust_signal.outcome == "refuse"
        assert ask.trust_line is None

    @pytest.mark.asyncio
    async def test_no_trust_line_when_the_fold_dropped_a_citation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # One of three citations carries an off-host URL and is rejected, so
        # the result returns two while the line counts three. Mutation that
        # turns this red: drop the `omitted_total` clause.
        ask, _run = await _ask_and_run(monkeypatch, _long_answer_stream(3, bad_url_at=2))

        assert ask.disclosures.citations_omitted == 1, "populate check: one citation rejected"
        assert ask.trust_line is None


# ---------------------------------------------------------------------------
# "All additive. No existing field changes name or type."
# ---------------------------------------------------------------------------


class TestAllAdditive:
    def test_every_existing_field_keeps_its_name_and_type_and_the_new_ones_are_nullable(
        self,
    ) -> None:
        # Read off the real printed schema, the contract a client sees.
        # Mutation that turns this red: rename or retype any existing field,
        # or make a new one non-null (`String!`). The new fields must be
        # nullable, because most runs carry no question back and many carry
        # no trust line.
        from system_03_search_agent.adapters.graphql.schema import schema

        printed = str(schema)
        for type_name, existing in (
            (
                "AskResult",
                (
                    "runId: String!",
                    "personaName: String!",
                    "answer: String!",
                    "trustSignal: TrustSignal!",
                    "citations: [Citation!]!",
                    "disclosures: Disclosures!",
                ),
            ),
            (
                "RunResult",
                (
                    "runId: String!",
                    "finished: Boolean!",
                    "answer: String!",
                    "trustSignal: TrustSignal!",
                    "citations: [Citation!]!",
                    "disclosures: Disclosures!",
                ),
            ),
        ):
            block = re.search(r"type " + type_name + r" \{(.*?)\}", printed, re.DOTALL)
            assert block is not None, type_name
            lines = {line.strip() for line in block.group(1).splitlines() if line.strip()}
            assert set(existing) <= lines, (type_name, set(existing) - lines)
            assert {
                "trustLine: String",
                "clarifyingQuestion: String",
                "clarifyingOptions: [String!]",
            } <= lines, type_name


# ---------------------------------------------------------------------------
# End to end: the real app, a real account, the new fields selected.
# ---------------------------------------------------------------------------


def _can_connect() -> bool:
    url = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
    try:
        probe_engine = sa.create_engine(url)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


_ASK_DOCUMENT = """
mutation Ask($input: AskInput!) {
  ask(input: $input) {
    runId
    answer
    trustLine
    clarifyingQuestion
    clarifyingOptions
    trustSignal { outcome }
    citations { displayIndex }
    disclosures { citationsOmitted }
  }
}
"""


@pytest.mark.skipif(
    not _can_connect(),
    reason=(
        "search_agent_users PostgreSQL database is not reachable; set USER_DB_URL and "
        "ensure the server is running to run the GraphQL parity end-to-end test"
    ),
)
class TestThroughTheRealSchema:
    @pytest.mark.asyncio
    async def test_a_client_selects_the_new_fields_and_gets_every_citation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: leave the new fields off `AskResult`
        # (the document fails validation), or cap citations below 84.
        import httpx

        from system_03_search_agent.adapters.web_sse.app import app

        monkeypatch.setenv("AUTH_SECRET", "graphql-parity-fields-test-secret")
        monkeypatch.setattr(run_registry_module, "run_streaming", _long_answer_stream(84))
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            email, password = f"{uuid.uuid4()}@example.com", "Str0ngPassw0rd!"
            signup = await client.post("/auth/signup", json={"email": email, "password": password})
            assert signup.status_code == 201, signup.text
            login = await client.post("/auth/login", json={"email": email, "password": password})
            assert login.status_code == 200, login.text
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            response = await client.post(
                "/graphql",
                json={
                    "query": _ASK_DOCUMENT,
                    "variables": {"input": {"text": "What are the clinical features of Marfan syndrome?", "sessionId": "s-parity"}},
                },
                headers=headers,
            )

        body = response.json()
        assert "errors" not in body, body.get("errors")
        ask = body["data"]["ask"]
        markers = {int(number) for number in _MARKER.findall(ask["answer"])}
        returned = {citation["displayIndex"] for citation in ask["citations"]}
        assert len(markers) == 84
        assert markers - returned == set()
        assert ask["disclosures"]["citationsOmitted"] == 0
        assert ask["trustLine"] == _TRUST_LINE
        assert ask["clarifyingQuestion"] is None
        assert ask["clarifyingOptions"] is None
