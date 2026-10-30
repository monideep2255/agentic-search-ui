"""Tests for `GET /v1/history` (T-4.13-02, `tracker/phase_4.13.md`).

`system_03_search_agent.feedback.history.list_history_page` is monkeypatched
to a fake, in-memory store for every test here, keyed by `owner_id`, so this
file only exercises what T-4.13-02 itself owns: caller derivation (via
`get_caller`, admitting both a guest and an account principal, and 401 for
neither), the `limit` query parameter's Pydantic validation (`ge=1,
le=MAX_LIMIT`, default `DEFAULT_LIMIT`), the response shape
(`HistoryResponse`'s `{items, count, omitted_count}`), and that the
endpoint passes the caller's own `owner_id`, and only that value, through
to `list_history`.

F-4.13-J-04's fix added the class below this file previously had none of:
`HistoryItem` and `HistoryResponse`'s own `max_length` and `extra="forbid"`
bounds, asserted directly against the Pydantic models rather than only
against the endpoint, since a comment in `adapters/web_sse/app.py` invokes
`production-standards`' multi-agent pipeline gate by name for these bounds
and nothing tested that the invocation was true. F-4.13-A-02's fix added
the endpoint-level tests for the graceful-degradation path (one
non-conforming row omitted and counted, never a 500 for the whole
response). F-4.13-A-08's fix added the duplicate-`limit` refusal.

Card 136.1 added the `before` cursor and `has_more`: the endpoint passes the
caller's own `owner_id` with the cursor, refuses a duplicate, empty,
over-long or control-character cursor with a 422 before or instead of any
query, and carries `has_more` from the read function even when the page's
last row is withheld. "A stranger's cursor and a cursor that never existed
answer identically" is only meaningful against the real owner filter, so
that clause runs through this endpoint and the REAL `list_history_page`
against a real database in `tests/system_03_search_agent/feedback/
test_history.py`, not here.

The real owner-scoping SQL, the NULL-owner exclusion, the real `LIMIT`
clause and the total order are `feedback/history.py`'s own contract,
covered against a real database by `tests/system_03_search_agent/
feedback/test_history.py`. The end-to-end property, a real run's row
surviving a reload through this exact endpoint, is
`test_phase_4_13_premise.py`'s job. Matching `test_feedback_endpoint.py`'s
own documented choice for the same reason: no skip-if-database-unreachable
guard is needed here, and none is used.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pydantic
import pytest
from httpx import ASGITransport, AsyncClient

from system_03_search_agent.adapters.web_sse.app import HistoryItem, HistoryResponse, app
from system_03_search_agent.auth.dependencies import Principal, get_caller
from system_03_search_agent.feedback.history import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    HistoryEntry,
    HistoryPage,
)

_LIST_HISTORY_TARGET = "system_03_search_agent.adapters.web_sse.app.list_history_page"
_HISTORY_PATH = "/v1/history"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class _FakeHistoryStore:
    """Stand-in for `feedback.history.list_history_page`, keyed by `owner_id`.

    `calls` records every invocation (`owner_id`, `limit`, and `before` only
    when one was sent, so the clauses written before card 136.1 still read
    exactly what they always asserted) so a test can
    assert exactly what the endpoint passed through, the strongest
    available proof that it derived the caller's OWN `owner_id` rather than
    something else, per `.claude/rules/goal-contracts.md`'s "assert on the
    stored value" discipline.
    """

    def __init__(self) -> None:
        self.rows: dict[str, list[HistoryEntry]] = {}
        self.calls: list[dict[str, object]] = []

    def seed(self, owner_id: str, entries: list[HistoryEntry]) -> None:
        self.rows[owner_id] = entries

    def __call__(
        self, *, owner_id: str, limit: int = DEFAULT_LIMIT, before: str | None = None
    ) -> HistoryPage:
        call: dict[str, object] = {"owner_id": owner_id, "limit": limit}
        if before is not None:
            call["before"] = before
        self.calls.append(call)
        rows = self.rows.get(owner_id, [])
        if before is not None:
            # The real function's owner-scoped cursor lookup, in miniature:
            # a cursor not among THIS owner's rows is an empty page.
            positions = [n for n, row in enumerate(rows) if row.trace_id == before]
            if not positions:
                return HistoryPage(entries=[], next_before=None)
            rows = rows[positions[0] + 1 :]
        return HistoryPage(
            entries=rows[:limit],
            next_before=rows[limit - 1].trace_id if len(rows) > limit else None,
        )


@pytest.fixture
def fake_history(monkeypatch: pytest.MonkeyPatch) -> _FakeHistoryStore:
    store = _FakeHistoryStore()
    monkeypatch.setattr(_LIST_HISTORY_TARGET, store)
    return store


@pytest.fixture(autouse=True)
def _clear_caller_override() -> AsyncIterator[None]:
    yield
    app.dependency_overrides.pop(get_caller, None)


def _set_caller(principal: Principal) -> None:
    app.dependency_overrides[get_caller] = lambda: principal


def _guest_principal(owner_id: str | None = None) -> Principal:
    return Principal(
        owner_id=owner_id or f"guest:{uuid.uuid4()}", user_id=None, kind="guest"
    )


def _account_principal(owner_id: str | None = None) -> Principal:
    user_id = str(uuid.uuid4())
    return Principal(owner_id=owner_id or f"user:{user_id}", user_id=user_id, kind="user")


def _entry(question: str, *, trace_id: str | None = None) -> HistoryEntry:
    return HistoryEntry(
        trace_id=trace_id or f"trace-{uuid.uuid4().hex[:8]}",
        question=question,
        asked_at=datetime.now(UTC),
        trust_signal="answer",
        citation_count=1,
    )


# ---------------------------------------------------------------------------
# Missing input: no credential at all.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_authorization_header_is_401_not_an_empty_200(
    fake_history: _FakeHistoryStore,
) -> None:
    async with _client() as client:
        response = await client.get(_HISTORY_PATH)

    assert response.status_code == 401, response.text
    assert fake_history.calls == [], "list_history must not be reached with no credential"


# ---------------------------------------------------------------------------
# Valid input: a guest and an account, each served their own rows.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_guest_principal_is_served(fake_history: _FakeHistoryStore) -> None:
    guest = _guest_principal()
    fake_history.seed(guest.owner_id, [_entry("What gene is BRCA1?")])
    _set_caller(guest)

    async with _client() as client:
        response = await client.get(_HISTORY_PATH)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["question"] == "What gene is BRCA1?"
    assert fake_history.calls == [{"owner_id": guest.owner_id, "limit": DEFAULT_LIMIT}]


@pytest.mark.asyncio
async def test_an_account_principal_is_served(fake_history: _FakeHistoryStore) -> None:
    account = _account_principal()
    fake_history.seed(account.owner_id, [_entry("Which diseases are associated with TP53?")])
    _set_caller(account)

    async with _client() as client:
        response = await client.get(_HISTORY_PATH)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["question"] == "Which diseases are associated with TP53?"
    assert fake_history.calls == [{"owner_id": account.owner_id, "limit": DEFAULT_LIMIT}]


@pytest.mark.asyncio
async def test_the_response_shape_carries_every_declared_field(
    fake_history: _FakeHistoryStore,
) -> None:
    guest = _guest_principal()
    entry = _entry("What gene is BRCA1?", trace_id="trace-shape-check")
    fake_history.seed(guest.owner_id, [entry])
    _set_caller(guest)

    async with _client() as client:
        response = await client.get(_HISTORY_PATH)

    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["trace_id"] == "trace-shape-check"
    assert item["question"] == "What gene is BRCA1?"
    assert item["trust_signal"] == "answer"
    assert item["citation_count"] == 1
    assert "asked_at" in item


# ---------------------------------------------------------------------------
# Cross-principal isolation, at the endpoint's own dispatch layer: the
# endpoint must derive and pass the CALLING principal's `owner_id`, never a
# fixed or leaked one.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_principals_never_see_each_others_seeded_rows(
    fake_history: _FakeHistoryStore,
) -> None:
    guest_a = _guest_principal()
    guest_b = _guest_principal()
    assert guest_a.owner_id != guest_b.owner_id
    fake_history.seed(guest_a.owner_id, [_entry("Question from A")])
    fake_history.seed(guest_b.owner_id, [_entry("Question from B")])

    _set_caller(guest_a)
    async with _client() as client:
        response_a = await client.get(_HISTORY_PATH)
    assert response_a.status_code == 200, response_a.text
    assert [item["question"] for item in response_a.json()["items"]] == ["Question from A"]

    _set_caller(guest_b)
    async with _client() as client:
        response_b = await client.get(_HISTORY_PATH)
    assert response_b.status_code == 200, response_b.text
    assert [item["question"] for item in response_b.json()["items"]] == ["Question from B"]


# ---------------------------------------------------------------------------
# The `limit` query parameter: valid, invalid, and its default.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_limit_is_passed_through_to_list_history(fake_history: _FakeHistoryStore) -> None:
    guest = _guest_principal()
    fake_history.seed(guest.owner_id, [_entry(f"Q{n}") for n in range(10)])
    _set_caller(guest)

    async with _client() as client:
        response = await client.get(_HISTORY_PATH, params={"limit": 3})

    assert response.status_code == 200, response.text
    assert response.json()["count"] == 3
    assert fake_history.calls == [{"owner_id": guest.owner_id, "limit": 3}]


@pytest.mark.asyncio
async def test_the_default_limit_matches_the_contract(fake_history: _FakeHistoryStore) -> None:
    guest = _guest_principal()
    _set_caller(guest)

    async with _client() as client:
        await client.get(_HISTORY_PATH)

    assert fake_history.calls == [{"owner_id": guest.owner_id, "limit": DEFAULT_LIMIT}]


@pytest.mark.asyncio
async def test_a_limit_above_the_maximum_is_refused_with_422_naming_the_maximum(
    fake_history: _FakeHistoryStore,
) -> None:
    guest = _guest_principal()
    _set_caller(guest)

    async with _client() as client:
        response = await client.get(_HISTORY_PATH, params={"limit": MAX_LIMIT + 1})

    assert response.status_code == 422, response.text
    assert str(MAX_LIMIT) in response.text, (
        f"the refusal must name the maximum the caller should send instead. "
        f"Got: {response.text[:300]}"
    )
    assert fake_history.calls == [], "an invalid limit must never reach list_history"


@pytest.mark.asyncio
async def test_a_limit_of_zero_is_refused(fake_history: _FakeHistoryStore) -> None:
    guest = _guest_principal()
    _set_caller(guest)

    async with _client() as client:
        response = await client.get(_HISTORY_PATH, params={"limit": 0})

    assert response.status_code == 422, response.text
    assert fake_history.calls == []


@pytest.mark.asyncio
async def test_a_non_integer_limit_is_refused(fake_history: _FakeHistoryStore) -> None:
    guest = _guest_principal()
    _set_caller(guest)

    async with _client() as client:
        response = await client.get(_HISTORY_PATH, params={"limit": "not-a-number"})

    assert response.status_code == 422, response.text
    assert fake_history.calls == []


@pytest.mark.asyncio
async def test_the_maximum_limit_itself_is_accepted(fake_history: _FakeHistoryStore) -> None:
    guest = _guest_principal()
    fake_history.seed(guest.owner_id, [])
    _set_caller(guest)

    async with _client() as client:
        response = await client.get(_HISTORY_PATH, params={"limit": MAX_LIMIT})

    assert response.status_code == 200, response.text
    assert fake_history.calls == [{"owner_id": guest.owner_id, "limit": MAX_LIMIT}]


# ---------------------------------------------------------------------------
# F-4.13-A-08's fix: a `limit` query parameter presented more than once is
# refused, never silently resolved to one occurrence's value.
# ---------------------------------------------------------------------------


class TestDuplicateLimitIsRefused:
    @pytest.mark.asyncio
    async def test_two_valid_but_different_limits_are_both_refused(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        """Neither occurrence wins silently; the request is refused outright.

        Before the fix, FastAPI's own scalar coercion read only the LAST
        occurrence, so `?limit=1&limit=50` served page-50's worth and
        `?limit=50&limit=1` served page-1's, with no signal to the caller
        that the other value it sent was discarded.
        """
        guest = _guest_principal()
        fake_history.seed(guest.owner_id, [_entry(f"Q{n}") for n in range(6)])
        _set_caller(guest)

        async with _client() as client:
            first_then_last = await client.get(
                _HISTORY_PATH, params=[("limit", "1"), ("limit", "50")]
            )
            last_then_first = await client.get(
                _HISTORY_PATH, params=[("limit", "50"), ("limit", "1")]
            )

        for label, response in (
            ("limit=1 then limit=50", first_then_last),
            ("limit=50 then limit=1", last_then_first),
        ):
            assert response.status_code == 422, f"{label}: {response.text}"
            assert "limit" in response.text, (
                f"{label}: the refusal must name the parameter it refused. "
                f"Got: {response.text[:300]}"
            )
        assert fake_history.calls == [], "a refused request must never reach list_history"

    @pytest.mark.asyncio
    async def test_one_malformed_occurrence_does_not_let_the_other_win(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        """Before the fix, `?limit=abc&limit=2` succeeded on `2` (the last,
        individually-valid occurrence), while `?limit=2&limit=abc` was
        refused on `abc`. Both must now be refused identically: which
        occurrence happens to be syntactically valid must not decide the
        outcome of an ambiguous request.
        """
        guest = _guest_principal()
        _set_caller(guest)

        async with _client() as client:
            invalid_then_valid = await client.get(
                _HISTORY_PATH, params=[("limit", "abc"), ("limit", "2")]
            )
            valid_then_invalid = await client.get(
                _HISTORY_PATH, params=[("limit", "2"), ("limit", "abc")]
            )

        assert invalid_then_valid.status_code == 422, invalid_then_valid.text
        assert valid_then_invalid.status_code == 422, valid_then_invalid.text
        assert fake_history.calls == []

    @pytest.mark.asyncio
    async def test_a_single_limit_occurrence_is_unaffected(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        """The fix must not refuse the ordinary, single-occurrence case."""
        guest = _guest_principal()
        fake_history.seed(guest.owner_id, [_entry("Q")])
        _set_caller(guest)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH, params={"limit": 5})

        assert response.status_code == 200, response.text
        assert fake_history.calls == [{"owner_id": guest.owner_id, "limit": 5}]


# ---------------------------------------------------------------------------
# F-4.13-A-02's fix: a row that no longer fits `HistoryItem`'s own bounds is
# dropped and DISCLOSED (`omitted_count`), never a 500 for the whole page.
# ---------------------------------------------------------------------------


class TestGracefulDegradationOnAnOversizedRow:
    @pytest.mark.asyncio
    async def test_an_oversized_row_is_omitted_and_disclosed_not_a_500(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        guest = _guest_principal()
        oversized = _entry("x" * 2001, trace_id="trace-oversized")
        well_formed = _entry("What gene is BRCA1?", trace_id="trace-fine")
        fake_history.seed(guest.owner_id, [oversized, well_formed])
        _set_caller(guest)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH)

        assert response.status_code == 200, (
            f"one non-conforming row must not turn the whole page into a "
            f"500; got {response.status_code} {response.text[:300]}"
        )
        body = response.json()
        assert body["omitted_count"] == 1, (
            f"the dropped row must be disclosed, not silently absorbed. Got: {body}"
        )
        assert body["count"] == 1
        assert [item["question"] for item in body["items"]] == ["What gene is BRCA1?"], (
            "the control did not hold: the well-formed sibling row must "
            f"still be served. Got: {body}"
        )

    @pytest.mark.asyncio
    async def test_a_row_with_no_honest_citation_count_is_omitted_and_disclosed(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        """F-4.13-RV-02's fix, the handler half.

        `list_history` reports `citation_count is None` for a row whose
        stored `citations` value is not a list, which the JSONB column
        permits (a scalar, a string, an object, or the JSON literal `null`).
        That row must cost the caller THAT ROW and nothing more, and the
        loss must be disclosed. It must never be published with a
        substituted count, and it must never take the caller's whole page
        down, which is exactly what the pre-fix `len()` did by raising
        `TypeError` one layer above this guard.

        WHAT THIS CLAUSE DOES NOT PROVE, stated rather than left to be
        rediscovered: it does not distinguish the handler's explicit
        `citation_count is None` branch from `HistoryItem.citation_count`'s
        own non-nullable `int` refusing the same row. Measured: replacing
        that branch with `if False` leaves this clause, and all 28 others
        in this file, green, because the two paths produce byte-identical
        responses and no black-box arm can tell them apart. The branch is
        kept because it states the DECISION at the point the decision is
        made rather than leaving it as a side effect of a type annotation,
        and `test_citation_count_is_not_nullable` below pins the fallback
        the redundancy rests on.
        """
        guest = _guest_principal()
        unknown_count = HistoryEntry(
            trace_id="trace-unknown-count",
            question="Which variant is pathogenic in CFTR?",
            asked_at=datetime.now(UTC),
            trust_signal="answer",
            citation_count=None,
        )
        well_formed = _entry("What gene is BRCA1?", trace_id="trace-fine")
        fake_history.seed(guest.owner_id, [unknown_count, well_formed])
        _set_caller(guest)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH)

        assert response.status_code == 200, (
            f"an unreadable citations value must cost one row, not the page; "
            f"got {response.status_code} {response.text[:300]}"
        )
        body = response.json()
        assert body["omitted_count"] == 1, (
            f"the withheld row must be disclosed, not silently absorbed. Got: {body}"
        )
        assert [item["question"] for item in body["items"]] == ["What gene is BRCA1?"], (
            "the control did not hold: the well-formed sibling row must still "
            f"be served, and the unreadable one must not appear. Got: {body}"
        )
        assert body["count"] == 1

    @pytest.mark.asyncio
    async def test_every_row_conforming_reports_zero_omitted(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        """`omitted_count` defaults to, and stays, 0 in the ordinary case,
        so an existing client that has never seen a non-zero value is
        unaffected (additive per `system-design-patterns` pattern 10)."""
        guest = _guest_principal()
        fake_history.seed(guest.owner_id, [_entry("What gene is BRCA1?")])
        _set_caller(guest)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH)

        assert response.status_code == 200, response.text
        assert response.json()["omitted_count"] == 0


# ---------------------------------------------------------------------------
# F-4.13-J-04's fix: the response models' own `max_length` and
# `extra="forbid"` bounds, asserted directly rather than left to a comment
# in `adapters/web_sse/app.py` that invoked `production-standards` by name
# with no test behind it. Each of these previously passed with the bound
# it asserts fully removed from the model (measured by the judge's mutation
# sweep, `tracker/phase_4.13_judge_report.md`'s M20 to M22).
# ---------------------------------------------------------------------------


class TestResponseModelBoundsAreEnforced:
    def _valid_item_kwargs(self, **overrides: object) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "trace_id": "trace-1",
            "question": "What gene is BRCA1?",
            "asked_at": datetime.now(UTC),
            "trust_signal": "answer",
            "citation_count": 1,
        }
        kwargs.update(overrides)
        return kwargs

    def test_question_over_max_length_is_refused(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            HistoryItem(**self._valid_item_kwargs(question="x" * 2001))

    def test_question_at_max_length_is_accepted(self) -> None:
        HistoryItem(**self._valid_item_kwargs(question="x" * 2000))

    def test_trace_id_over_max_length_is_refused(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            HistoryItem(**self._valid_item_kwargs(trace_id="t" * 65))

    def test_trace_id_at_max_length_is_accepted(self) -> None:
        """F-4.13-RV-03. The clause above proves a bound EXISTS, not that it
        is 64: narrowing `max_length` from 64 to 63 left all 49 of this
        phase's tests green (the re-verify round's mutation N9). `question`
        and `items` each got an at-the-boundary control in F-4.13-J-04's own
        fix and each catches its narrowing (N3, N4); `trace_id` was the one
        left out. 64 is not an arbitrary number: it mirrors
        `feedback.contracts.InteractionRow.trace_id`'s own `max_length`, so a
        `trace_id` the write path accepts must be one this response can
        carry, and a narrowed bound here would silently omit real rows
        through the `omitted_count` path instead of serving them.
        """
        HistoryItem(**self._valid_item_kwargs(trace_id="t" * 64))

    def test_trust_signal_over_max_length_is_refused(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            HistoryItem(**self._valid_item_kwargs(trust_signal="s" * 21))

    def test_citation_count_is_not_nullable(self) -> None:
        """F-4.13-RV-02. The handler withholds a row whose `citation_count`
        is `None` with an explicit branch, and this model refusing `None`
        is the SECOND, independent reason the same row never reaches a
        caller. Measured: removing the handler's explicit branch leaves all
        28 clauses in this file green, because both paths produce the
        identical response.

        That measurement is why this arm exists. The redundancy is only
        safe while this field stays non-nullable, and nothing else in the
        suite said so: widening it to `int | None` would make the handler's
        branch the single control, and if that branch were ever removed
        too, a row with no honest count would ship as `"citation_count":
        null` with `omitted_count: 0`. This arm turns that widening into a
        failing test rather than a silent change of who is guarding what.
        """
        with pytest.raises(pydantic.ValidationError):
            HistoryItem(**self._valid_item_kwargs(citation_count=None))

    def test_citation_count_below_zero_is_refused(self) -> None:
        """F-4.13-RV-03. `citation_count`'s `ge=0` was asserted by nothing:
        dropping it left all 49 of this phase's tests green (mutation M-M).

        Unreachable through the shipped read path, which computes the value
        with `len()` over a list and therefore cannot produce a negative,
        and pinned anyway for the same reason the bound is written down at
        all: this is a response CONTRACT, and a future writer of this field
        (a cursor-paged total, a cached count, a differently-sourced
        surface) has nothing else telling it that a negative source count is
        not publishable. A bound no arm can distinguish from its own absence
        is documentation, not a control.
        """
        with pytest.raises(pydantic.ValidationError):
            HistoryItem(**self._valid_item_kwargs(citation_count=-1))

    def test_citation_count_at_zero_is_accepted(self) -> None:
        """The populate-check for the clause above: without it, a mutation
        that tightened `ge=0` into `gt=0` would keep that clause green while
        refusing every honestly answered question that cited nothing, which
        `trust_signal` `refuse` and `ask` rows legitimately are."""
        HistoryItem(**self._valid_item_kwargs(citation_count=0))

    def test_an_unknown_field_on_history_item_is_refused(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            HistoryItem(**self._valid_item_kwargs(), answer_narrative="not part of the contract")

    def test_history_response_items_over_max_length_is_refused(self) -> None:
        too_many = [HistoryItem(**self._valid_item_kwargs(trace_id=f"t{n}")) for n in range(MAX_LIMIT + 1)]
        with pytest.raises(pydantic.ValidationError):
            HistoryResponse(items=too_many, count=len(too_many))

    def test_history_response_items_at_max_length_is_accepted(self) -> None:
        exactly = [HistoryItem(**self._valid_item_kwargs(trace_id=f"t{n}")) for n in range(MAX_LIMIT)]
        HistoryResponse(items=exactly, count=len(exactly))

    def test_an_unknown_field_on_history_response_is_refused(self) -> None:
        with pytest.raises(pydantic.ValidationError):
            HistoryResponse(items=[], count=0, answer="not part of the contract")


# ---------------------------------------------------------------------------
# Card 136.1: the `before` cursor and `has_more`.
# ---------------------------------------------------------------------------


def _entries(count: int, prefix: str = "t") -> list[HistoryEntry]:
    return [_entry(f"Question {n}", trace_id=f"{prefix}-{n}") for n in range(count)]


class TestOlderPages:
    @pytest.mark.asyncio
    async def test_has_more_is_true_when_an_older_row_exists(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        guest = _guest_principal()
        fake_history.seed(guest.owner_id, _entries(DEFAULT_LIMIT + 1))
        _set_caller(guest)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["count"] == DEFAULT_LIMIT
        assert body["has_more"] is True
        # J-136S4-01: the server names the cursor, the oldest row it read.
        assert body["next_before"] == f"t-{DEFAULT_LIMIT - 1}"

    @pytest.mark.asyncio
    async def test_has_more_is_false_at_exactly_one_page(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        guest = _guest_principal()
        fake_history.seed(guest.owner_id, _entries(DEFAULT_LIMIT))
        _set_caller(guest)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH)

        assert response.status_code == 200, response.text
        assert response.json()["has_more"] is False
        assert response.json()["next_before"] is None

    @pytest.mark.asyncio
    async def test_before_reaches_the_read_function_with_the_callers_own_owner_id(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        account = _account_principal()
        fake_history.seed(account.owner_id, _entries(25))
        _set_caller(account)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH, params={"before": "t-19"})

        assert response.status_code == 200, response.text
        assert fake_history.calls == [
            {"owner_id": account.owner_id, "limit": DEFAULT_LIMIT, "before": "t-19"}
        ]
        body = response.json()
        assert [item["trace_id"] for item in body["items"]] == [f"t-{n}" for n in range(20, 25)]
        assert body["has_more"] is False
        assert body["next_before"] is None

    @pytest.mark.asyncio
    async def test_has_more_survives_a_withheld_last_row(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        """`has_more` comes from the rows the database returned, not from
        the rows that survived the per-row guard, so a withheld row at the
        foot of a page never hides the page after it."""
        guest = _guest_principal()
        rows = _entries(DEFAULT_LIMIT + 1)
        rows[DEFAULT_LIMIT - 1] = HistoryEntry(
            trace_id="t-unreadable",
            question="Unreadable row",
            asked_at=datetime.now(UTC),
            trust_signal="answer",
            citation_count=None,
        )
        fake_history.seed(guest.owner_id, rows)
        _set_caller(guest)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH)

        body = response.json()
        assert body["omitted_count"] == 1
        assert body["count"] == DEFAULT_LIMIT - 1
        assert body["has_more"] is True
        # The cursor is the withheld row itself, so the next page starts
        # below it and never reads, or counts, it again (J-136S4-03's cause).
        assert body["next_before"] == "t-unreadable"

    @pytest.mark.asyncio
    async def test_a_page_of_only_withheld_rows_still_names_the_next_cursor(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        """A-136S4-01: every row of the page fails the per-row guard. The
        response must still say where the next page starts, or paging
        stops for good at an empty page that claims more."""
        guest = _guest_principal()
        rows = [
            HistoryEntry(
                trace_id=f"w-{n}",
                question="Unreadable row",
                asked_at=datetime.now(UTC),
                trust_signal="answer",
                citation_count=None,
            )
            for n in range(DEFAULT_LIMIT)
        ] + _entries(5, prefix="old")
        fake_history.seed(guest.owner_id, rows)
        _set_caller(guest)

        async with _client() as client:
            first = (await client.get(_HISTORY_PATH)).json()
            second = (
                await client.get(_HISTORY_PATH, params={"before": first["next_before"]})
            ).json()

        assert (first["count"], first["omitted_count"], first["has_more"]) == (0, 20, True)
        assert first["next_before"] == f"w-{DEFAULT_LIMIT - 1}"
        assert [item["trace_id"] for item in second["items"]] == [f"old-{n}" for n in range(5)]
        assert (second["has_more"], second["next_before"]) == (False, None)

    @pytest.mark.asyncio
    async def test_the_history_response_is_never_stored_by_a_cache(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        """A-136S4-03: the same `no-store` `/auth/login` sends, on the first
        page and on an older one."""
        guest = _guest_principal()
        fake_history.seed(guest.owner_id, _entries(25))
        _set_caller(guest)

        async with _client() as client:
            first = await client.get(_HISTORY_PATH)
            older = await client.get(_HISTORY_PATH, params={"before": "t-19"})

        assert first.headers.get("cache-control") == "no-store"
        assert older.headers.get("cache-control") == "no-store"

    @pytest.mark.asyncio
    async def test_a_cursor_from_another_owner_returns_an_empty_page(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        """At this layer: the endpoint passes the CALLER's owner with the
        cursor, so the read function scopes the lookup to them. The real
        owner filter is proven against a database in `test_history.py`."""
        owner = _guest_principal()
        stranger = _guest_principal()
        fake_history.seed(owner.owner_id, _entries(5, prefix="mine"))
        fake_history.seed(stranger.owner_id, _entries(5, prefix="theirs"))
        _set_caller(owner)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH, params={"before": "theirs-0"})

        assert response.status_code == 200, response.text
        assert response.json() == {
            "items": [],
            "count": 0,
            "omitted_count": 0,
            "has_more": False,
            "next_before": None,
        }
        assert fake_history.calls == [
            {"owner_id": owner.owner_id, "limit": DEFAULT_LIMIT, "before": "theirs-0"}
        ]


class TestTheCursorIsValidated:
    @pytest.mark.asyncio
    async def test_a_duplicate_before_is_refused(self, fake_history: _FakeHistoryStore) -> None:
        guest = _guest_principal()
        fake_history.seed(guest.owner_id, _entries(30))
        _set_caller(guest)

        async with _client() as client:
            response = await client.get(
                _HISTORY_PATH, params=[("before", "t-1"), ("before", "t-5")]
            )

        assert response.status_code == 422, response.text
        assert "before" in response.text
        assert fake_history.calls == []

    @pytest.mark.asyncio
    async def test_an_over_long_before_is_refused_before_any_query(
        self, fake_history: _FakeHistoryStore
    ) -> None:
        _set_caller(_guest_principal())

        async with _client() as client:
            response = await client.get(_HISTORY_PATH, params={"before": "t" * 65})

        assert response.status_code == 422, response.text
        assert "64" in response.text, "the refusal must name the bound"
        assert fake_history.calls == []

    @pytest.mark.asyncio
    async def test_a_before_at_the_bound_is_accepted(self, fake_history: _FakeHistoryStore) -> None:
        guest = _guest_principal()
        _set_caller(guest)

        async with _client() as client:
            response = await client.get(_HISTORY_PATH, params={"before": "t" * 64})

        assert response.status_code == 200, response.text
        assert fake_history.calls == [
            {"owner_id": guest.owner_id, "limit": DEFAULT_LIMIT, "before": "t" * 64}
        ]

    @pytest.mark.asyncio
    async def test_an_empty_before_is_refused(self, fake_history: _FakeHistoryStore) -> None:
        _set_caller(_guest_principal())

        async with _client() as client:
            response = await client.get(_HISTORY_PATH, params={"before": ""})

        assert response.status_code == 422, response.text
        assert fake_history.calls == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cursor", ["abc\x00def", "\x00", "line\nbreak", "tab\there", "del\x7f"])
    async def test_a_control_character_in_before_is_a_422_never_a_500(self, cursor: str) -> None:
        """Through the REAL `list_history_page`, no fake: its cursor check
        refuses before any session opens, so no database is needed. A NUL
        byte reaching the driver raises inside psycopg2, which would be a
        500; this pins that it never gets that far."""
        _set_caller(_guest_principal())

        async with _client() as client:
            response = await client.get(_HISTORY_PATH, params={"before": cursor})

        assert response.status_code == 422, response.text
        # J-136S4-04: pinned whole, so internal text or anything about
        # whether a row exists can never be added to it unnoticed.
        assert response.json() == {
            "detail": (
                "`before` must be the `trace_id` of one of your own searches, "
                "as returned in `next_before`"
            )
        }
