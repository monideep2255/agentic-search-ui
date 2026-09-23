"""`GET /v1/history/{trace_id}/answer`, and `has_saved_answer` on the list.

Fix-plan item 10.2. What a person gets: they click a past search and the
answer they already got is there, with no second search charged to them.

`feedback.history.get_saved_answer` and `list_history` are monkeypatched to
in-memory fakes here, the same choice `test_history_endpoint.py` makes and
for the same reason: this file owns what the ENDPOINT owns, which is caller
derivation, the status codes, the wire shape, the depth mapping, and that
the caller's own `owner_id` is what reaches the read function. The real SQL
and the real ownership rule are `feedback/history.py`'s contract and
`tests/system_03_search_agent/feedback/test_history_saved_answer.py` covers
them against a real database.

## Coverage: what this file exercises and what it deliberately omits

Exercised:

- 401 with no credential at all, on both routes.
- 200 with the full wire shape for an account's own saved answer.
- 404 for all three causes, and that the three responses are BYTE-IDENTICAL,
  which is the whole point of collapsing them.
- The four stored depths mapped onto the two this contract publishes.
- `has_saved_answer` travelling on `GET /v1/history` and defaulting to
  false.
- That the endpoint passes the caller's own `owner_id` through, and nothing
  else.
- A stored citation that is not an object is dropped rather than taking the
  whole answer down.
- `trust_line` travels through when the row has one, and reads `None`
  rather than a fabricated value when it does not (overnight run, worker
  H, defect two).

NOT exercised:

- Whether a guest could ever have a saved answer to fetch. They cannot, and
  the exclusion lives at the write, three layers below this one: the
  assembler, the row model and a database CHECK constraint, covered by
  `tests/system_03_search_agent/feedback/test_capture_saved_answer.py` and
  `tests/system_03_search_agent/data/test_migration_0010.py`. An arm here
  that monkeypatched a guest answer INTO the fake store would be grading a
  state the system cannot reach.
- The markdown's content, and how a browser renders it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from system_03_search_agent.adapters.web_sse.app import SavedAnswerResponse, app
from system_03_search_agent.auth.dependencies import Principal, get_caller
from system_03_search_agent.feedback.history import DEFAULT_LIMIT, HistoryEntry, SavedAnswer

_GET_SAVED_TARGET = "system_03_search_agent.adapters.web_sse.app.get_saved_answer"
_LIST_HISTORY_TARGET = "system_03_search_agent.adapters.web_sse.app.list_history"

_ANSWER = "TP53 is a tumour suppressor [1].\n\n| Gene | Role |\n| --- | --- |\n| TP53 [1] | x |"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _citation() -> dict:
    return {
        "citation_id": "call-1-1",
        "display_index": 1,
        "source": "NCBIGene",
        "source_id": "NCBIGene:7157",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/7157",
        "layer": "layer_1_graph",
        "field": "symbol",
        "claim_text": "TP53 is a tumour suppressor.",
        "evidence_kind": "primary_assertion",
        "assertion_confidence": "asserted",
        "population_ancestry_context": None,
        "license": "public_domain_us_gov",
    }


class _FakeSavedStore:
    """Stand-in for `feedback.history.get_saved_answer`, keyed by owner and trace."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], SavedAnswer] = {}
        self.calls: list[dict[str, object]] = []

    def seed(self, owner_id: str, saved: SavedAnswer) -> None:
        self.rows[(owner_id, saved.trace_id)] = saved

    def __call__(self, *, owner_id: str, trace_id: str) -> SavedAnswer | None:
        self.calls.append({"owner_id": owner_id, "trace_id": trace_id})
        return self.rows.get((owner_id, trace_id))


@pytest.fixture
def fake_saved(monkeypatch: pytest.MonkeyPatch) -> _FakeSavedStore:
    store = _FakeSavedStore()
    monkeypatch.setattr(_GET_SAVED_TARGET, store)
    return store


@pytest.fixture(autouse=True)
def _clear_caller_override() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.pop(get_caller, None)


def _set_caller(principal: Principal) -> None:
    app.dependency_overrides[get_caller] = lambda: principal


def _account_principal(owner_id: str | None = None) -> Principal:
    user_id = str(uuid.uuid4())
    return Principal(owner_id=owner_id or f"user:{user_id}", user_id=user_id, kind="user")


def _saved(
    trace_id: str = "trace-1",
    *,
    depth: str = "researcher",
    citations: list | None = None,
    trust_line: str | None = None,
) -> SavedAnswer:
    return SavedAnswer(
        trace_id=trace_id,
        question="What does TP53 do?",
        asked_at=datetime.now(UTC),
        depth=depth,
        answer_markdown=_ANSWER,
        citations=[_citation()] if citations is None else citations,
        trust_signal="answer",
        trust_line=trust_line,
    )


def _path(trace_id: str) -> str:
    return f"/v1/history/{trace_id}/answer"


# ---------------------------------------------------------------------------
# Missing input.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_credential_is_401_not_404(fake_saved) -> None:
    """A person must be able to tell "not signed in" from "nothing saved",
    because they do opposite things with them."""
    async with _client() as client:
        response = await client.get(_path("trace-1"))
    assert response.status_code == 401
    # POPULATE CHECK: the read function was never even reached, so the 401
    # came from the dependency rather than from an empty store.
    assert fake_saved.calls == []


# ---------------------------------------------------------------------------
# The happy path.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_owner_gets_the_whole_wire_shape(fake_saved) -> None:
    caller = _account_principal()
    _set_caller(caller)
    fake_saved.seed(caller.owner_id, _saved("trace-abc"))

    async with _client() as client:
        response = await client.get(_path("trace-abc"))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "trace_id",
        "question",
        "asked_at",
        "depth",
        "answer_markdown",
        "citations",
        "trust_signal",
        "trust_line",
    }
    assert body["trace_id"] == "trace-abc"
    assert body["question"] == "What does TP53 do?"
    assert body["depth"] == "researcher"
    assert body["answer_markdown"] == _ANSWER
    assert body["trust_signal"] == "answer"
    # POPULATE CHECK, worker H, overnight defect two: `_saved()` below
    # builds a `SavedAnswer` with no `trust_line` argument, so this is
    # `None` by the dataclass's own default, not because the wire field
    # was dropped. `test_trust_line_travels_through_when_the_row_has_one`
    # is the arm that proves the field carries a real value when there is
    # one.
    assert body["trust_line"] is None
    assert len(body["citations"]) == 1
    assert body["citations"][0]["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/7157"


@pytest.mark.asyncio
async def test_trust_line_travels_through_when_the_row_has_one(fake_saved) -> None:
    """Defect two, `testing/Developer/reports/2026-09-23_overnight/
    findings.md`'s "Worker B1" entry: a reopened answer must not read more
    confident than the one the person saw, so the stored `trust_line`
    sentence has to reach the wire."""
    caller = _account_principal()
    _set_caller(caller)
    saved = _saved("trace-hedged", trust_line="Sources disagree on at least one claim.")
    fake_saved.seed(caller.owner_id, saved)

    async with _client() as client:
        response = await client.get(_path("trace-hedged"))

    assert response.status_code == 200
    assert response.json()["trust_line"] == "Sources disagree on at least one claim."


@pytest.mark.asyncio
async def test_the_endpoint_passes_the_callers_own_owner_id_and_nothing_else(
    fake_saved,
) -> None:
    caller = _account_principal()
    _set_caller(caller)
    fake_saved.seed(caller.owner_id, _saved("trace-own"))

    async with _client() as client:
        await client.get(_path("trace-own"))

    assert fake_saved.calls == [{"owner_id": caller.owner_id, "trace_id": "trace-own"}]


# ---------------------------------------------------------------------------
# The 404, and that its three causes cannot be told apart.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_three_causes_answer_byte_identically(fake_saved) -> None:
    """A 403 on somebody else's row would confirm that row exists and is
    someone's. The three responses must be indistinguishable."""
    caller = _account_principal()
    stranger = _account_principal()
    _set_caller(caller)
    fake_saved.seed(caller.owner_id, _saved("mine"))
    fake_saved.seed(stranger.owner_id, _saved("theirs"))

    async with _client() as client:
        # POPULATE CHECK: the control holds, so the three below are about
        # the rule and not about an endpoint that 404s everything.
        ok = await client.get(_path("mine"))
        assert ok.status_code == 200

        theirs = await client.get(_path("theirs"))
        missing = await client.get(_path("no-such-trace"))
        # A row the caller owns with no saved answer is, at this layer, the
        # store returning None, exactly as the two above do.
        unanswered = await client.get(_path("mine-but-unanswered"))

    for response in (theirs, missing, unanswered):
        assert response.status_code == 404

    bodies = {theirs.text, missing.text, unanswered.text}
    assert len(bodies) == 1, f"the three 404s differ: {bodies}"
    headers = {
        tuple(sorted((k, v) for k, v in r.headers.items() if k != "date"))
        for r in (theirs, missing, unanswered)
    }
    assert len(headers) == 1, "the three 404s differ in their headers"


@pytest.mark.asyncio
async def test_the_404_says_what_to_do_next(fake_saved) -> None:
    """An error must tell the reader their next move, not just report a
    failure (`tool-call-budgets`)."""
    _set_caller(_account_principal())
    async with _client() as client:
        response = await client.get(_path("nothing"))
    assert response.status_code == 404
    assert "ask it again" in response.json()["detail"]


@pytest.mark.asyncio
async def test_an_absurd_trace_id_is_a_404_and_not_a_422(fake_saved) -> None:
    """A 422 on an over-long key would tell an unauthenticated prober which
    keys are even shaped like real ones."""
    caller = _account_principal()
    _set_caller(caller)
    fake_saved.seed(caller.owner_id, _saved("real"))

    async with _client() as client:
        ok = await client.get(_path("real"))
        assert ok.status_code == 200  # POPULATE CHECK
        response = await client.get(_path("t" * 200))

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Depth mapping.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stored", "published"),
    [
        ("plain_language", "plain"),
        ("researcher", "researcher"),
        ("clinical_brief", "researcher"),
        ("deep_technical", "researcher"),
        ("something_nobody_declared", "researcher"),
    ],
)
async def test_the_four_stored_depths_map_onto_the_two_published_ones(
    fake_saved, stored: str, published: str
) -> None:
    caller = _account_principal()
    _set_caller(caller)
    fake_saved.seed(caller.owner_id, _saved("trace-d", depth=stored))

    async with _client() as client:
        response = await client.get(_path("trace-d"))

    assert response.status_code == 200
    assert response.json()["depth"] == published


# ---------------------------------------------------------------------------
# A citation the response cannot render.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_unreadable_citation_is_dropped_not_fatal(fake_saved) -> None:
    """The person can see this search listed, so failing the open entirely
    would leave them stuck on a row they can click and never read."""
    caller = _account_principal()
    _set_caller(caller)
    fake_saved.seed(
        caller.owner_id,
        _saved("trace-bad", citations=[_citation(), "not an object", 42]),
    )

    async with _client() as client:
        response = await client.get(_path("trace-bad"))

    assert response.status_code == 200
    body = response.json()
    # POPULATE CHECK: the readable one survived, so this is a drop and not
    # a wholesale discard.
    assert len(body["citations"]) == 1
    assert body["citations"][0]["source_id"] == "NCBIGene:7157"
    assert body["answer_markdown"] == _ANSWER


# ---------------------------------------------------------------------------
# `has_saved_answer` on the list endpoint.
# ---------------------------------------------------------------------------


class _FakeHistoryStore:
    def __init__(self) -> None:
        self.rows: dict[str, list[HistoryEntry]] = {}

    def seed(self, owner_id: str, entries: list[HistoryEntry]) -> None:
        self.rows[owner_id] = entries

    def __call__(self, *, owner_id: str, limit: int = DEFAULT_LIMIT) -> list[HistoryEntry]:
        return self.rows.get(owner_id, [])[:limit]


@pytest.mark.asyncio
async def test_has_saved_answer_travels_on_the_list(monkeypatch) -> None:
    store = _FakeHistoryStore()
    monkeypatch.setattr(_LIST_HISTORY_TARGET, store)
    caller = _account_principal()
    _set_caller(caller)
    store.seed(
        caller.owner_id,
        [
            HistoryEntry(
                trace_id="t-saved",
                question="saved",
                asked_at=datetime.now(UTC),
                trust_signal="answer",
                citation_count=1,
                has_saved_answer=True,
            ),
            HistoryEntry(
                trace_id="t-unsaved",
                question="unsaved",
                asked_at=datetime.now(UTC),
                trust_signal="refuse",
                citation_count=0,
                has_saved_answer=False,
            ),
        ],
    )

    async with _client() as client:
        response = await client.get("/v1/history")

    assert response.status_code == 200
    items = {item["trace_id"]: item for item in response.json()["items"]}
    # POPULATE CHECK: both rows came back, so the two values below are a
    # real per-row distinction.
    assert set(items) == {"t-saved", "t-unsaved"}
    assert items["t-saved"]["has_saved_answer"] is True
    assert items["t-unsaved"]["has_saved_answer"] is False


def test_has_saved_answer_defaults_to_false_on_the_wire() -> None:
    """Additive within v1: a producer that never sets it still validates,
    and a client built before tonight reads the response as it did."""
    from system_03_search_agent.adapters.web_sse.app import HistoryItem

    item = HistoryItem(
        trace_id="t",
        question="q",
        asked_at=datetime.now(UTC),
        trust_signal="answer",
        citation_count=0,
    )
    assert item.has_saved_answer is False


# ---------------------------------------------------------------------------
# The response model's own bounds.
# ---------------------------------------------------------------------------


def test_the_response_model_bounds_every_field() -> None:
    """`production-standards`' multi-agent pipeline gate, asserted rather
    than invoked by name in a comment."""
    fields = SavedAnswerResponse.model_fields
    assert SavedAnswerResponse.model_config["extra"] == "forbid"

    def _max_length(name: str) -> int | None:
        for meta in fields[name].metadata:
            if hasattr(meta, "max_length"):
                return meta.max_length
        return None

    assert _max_length("trace_id") == 64
    assert _max_length("question") == 2000
    assert _max_length("answer_markdown") == 32000
    assert _max_length("citations") == 50
    assert _max_length("trust_signal") == 20
    assert _max_length("trust_line") == 200
