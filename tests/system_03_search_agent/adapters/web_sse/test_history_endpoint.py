"""Tests for `GET /v1/history` (T-4.13-02, `tracker/phase_4.13.md`).

`system_03_search_agent.feedback.history.list_history` is monkeypatched to
a fake, in-memory store for every test here, keyed by `owner_id`, so this
file only exercises what T-4.13-02 itself owns: caller derivation (via
`get_caller`, admitting both a guest and an account principal, and 401 for
neither), the `limit` query parameter's Pydantic validation (`ge=1,
le=MAX_LIMIT`, default `DEFAULT_LIMIT`), the response shape
(`HistoryResponse`'s `{items, count}`), and that the endpoint passes the
caller's own `owner_id`, and only that value, through to `list_history`.

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

import pytest
from httpx import ASGITransport, AsyncClient

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.auth.dependencies import Principal, get_caller
from system_03_search_agent.feedback.history import DEFAULT_LIMIT, MAX_LIMIT, HistoryEntry

_LIST_HISTORY_TARGET = "system_03_search_agent.adapters.web_sse.app.list_history"
_HISTORY_PATH = "/v1/history"


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class _FakeHistoryStore:
    """Stand-in for `feedback.history.list_history`, keyed by `owner_id`.

    `calls` records every invocation (`owner_id`, `limit`) so a test can
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

    def __call__(self, *, owner_id: str, limit: int = DEFAULT_LIMIT) -> list[HistoryEntry]:
        self.calls.append({"owner_id": owner_id, "limit": limit})
        return self.rows.get(owner_id, [])[:limit]


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
