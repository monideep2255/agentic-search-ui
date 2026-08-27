"""Build phase 4.13 premise gate: `tracker/phase_4.13.md`.

The done-when this file pins, in one sentence:

    A person's searches survive closing the browser: a caller who has run
    queries gets exactly their OWN past questions back on a fresh client
    carrying the same identity, never anyone else's, and a guest's searches
    follow them into the account they create.

## Why this gate has two arms

Same shape as build phase 4.10's, for the same reason. A read path over
`interactions` has no safe direction of failure:

- Returning `{"items": []}` to everybody passes every isolation clause that
  will ever be written against this file, and delivers nothing. The whole
  point of the phase is that the list comes back.
- Returning every row to everybody delivers the feature and hands one
  visitor another visitor's questions, which is the critical build phase
  4.5 already shipped once (F-4.5-A-02: `user_id` is NULL for every guest,
  so a check that read it made all guests one principal).

Only the second is caught by an attack test. So `TestDurabilityArm` below
is not decoration: it failing is exactly as much a gate failure as
`TestIsolationArm` failing, and a fix that greens the isolation arm by
emptying the durability arm has fixed nothing.

## The populate-check, on every bound arm

Build phase 4.11's durable lesson, and this file is the shape it was
written for. An isolation clause that asserts "guest B does not see
`marker`" passes trivially when the seed never wrote `marker`, when the
endpoint 404s, when the database rolled back, and when the whole feature
is missing. So every clause here first asserts the control HELD: the row
is in the table under the owner it was seeded for, and the owning caller
actually gets it back. Only then does it assert the other caller does not.

An arm that cannot tell the control holding from nothing having happened
is not an arm.

## What this gate covers

Durability (the admit arm):

- A REAL run driven through `POST /v1/query`, drained, then found in
  `GET /v1/history` from a client constructed after the run finished. That
  is the flagship clause, and it is deliberately the real caller's path
  rather than a seeded row: build phase 4.4's premise gate passed 6 of 6
  while the DEFAULT invocation returned the wrong thing, because five of
  its six cases took a path no real caller takes.
- Newest first. The order being TOTAL is a real requirement and is NOT
  asserted here: no black-box call through this endpoint can force two
  rows onto one timestamp, and an arm that cannot reach the tie cannot
  fail on it (F-4.13-01, measured 10 of 10 green under mutation before it
  was corrected). That property lives in
  `tests/system_03_search_agent/feedback/test_history.py`.
- The question text returned is the question that was asked, not a
  truncation or a normalisation of it.
- A guest's rows follow them into an account created while holding the
  guest token, so "your searches move with you" is asserted rather than
  claimed.

Isolation (the refuse arm):

- Two guests: neither sees the other's question, and BOTH controls are
  asserted, so an implementation that returns nothing to anybody fails
  here rather than passing.
- Two accounts: the same, both directions.
- A row whose `owner_id` is NULL, the pre-alembic-0008 shape, is returned
  to nobody, including a caller whose own rows are returned in the same
  response.
- No credentials at all: 401, not an empty list. An unauthenticated caller
  has no history, and "no history" and "not authenticated" are different
  answers a client must be able to tell apart.

Bounds:

- `limit` is honoured, and a caller holding more rows than the cap gets
  exactly the cap rather than everything.
- A `limit` above the maximum is REFUSED rather than silently clamped, and
  the refusal names what to send instead. A silent clamp is a lie about
  what the caller asked for; `tool-call-budgets` requires the error say
  what to do next.

## What this gate deliberately does NOT cover

Per `goal-contracts`'s coverage-declaration discipline, and stated so a gap
is arguable rather than invisible:

- The ANSWER. Only the question list is durable. `interactions` stores no
  synthesised narrative (`feedback/contracts.py`, `InteractionRow`), so
  nothing here asserts a restored answer, and clicking a restored item
  re-asks the question. Decision D-4.13-01.
- Pagination. The read path is capped, with no cursor, because the rail in
  `docs/build/design/design-system/prototype/app.html` is a flat scrolling
  list with no "load more" control. A caller with more than the cap sees
  their most recent page and nothing tells them there is more. That is a
  real hole, declared rather than excused.
- Capture's own best-effort guarantee. Section 16 permits a run's capture
  row to fail to write, and this gate asserts nothing about the case where
  it does. A run whose capture failed is invisible to history and no UI
  says so.
- Multi-process behaviour, and the browser. What renders the list is
  `frontend/`, graded by its own vitest and Playwright specs, not here.
- WHETHER THE VISITOR STILL HAS THEIR IDENTITY AFTER THE RELOAD, and this
  is the sharpest omission in this file. The durability clause holds one
  bearer token in a Python variable and hands it to a second client, which
  is precisely what no browser does: `App.tsx` keeps the access token in
  React state alone, so a real reload signs an account out and the rail is
  gated on being signed in. This gate proves the SERVER is durable and
  says nothing about the BROWSER being able to identify itself, which is
  the half a person actually experiences. Recorded as F-4.13-02 and owned
  by the product owner, because where a bearer token may be persisted is a
  security decision rather than a build detail. Stated here rather than
  left implicit: build phase 4.16's transferable lesson is that a test can
  be correct, honest, and measuring the wrong property, and that is exactly
  what this clause would be if it did not say so.
- Real Layer 1 answers. The agent loop runs against the same stubbed
  harness every other test in this directory uses (T-3.0-07). What is
  under test is whose questions come back, not what the runs answered.

## How it runs

The real FastAPI app over `httpx.AsyncClient` + `ASGITransport`, against a
real `search_agent_users` PostgreSQL, skipping cleanly rather than failing
when that database is unreachable. Every import of a module this phase has
not built yet is made INSIDE the clause that needs it, so each arm fails on
its own and the failure list is a work list rather than one collection
error hiding eleven of twelve arms.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


pytestmark = pytest.mark.skipif(
    not _can_connect(),
    reason=f"user database unreachable at {USER_DB_URL}; durable history is a server-side read",
)

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module

_TEST_AUTH_KEY = "test-only-value-for-phase-4-13-premise-tests-do-not-reuse"

# The contract this gate pins, written before the endpoint exists. These are
# the gate's own expectations, deliberately NOT imported from the code under
# test: a gate that reads its expected values out of the implementation
# cannot catch those values being wrong.
_HISTORY_PATH = "/v1/history"
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50


@pytest.fixture(autouse=True)
def _harness_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("ANON_DAILY_RUN_CAP", "10000")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch):
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


@pytest.fixture(autouse=True)
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157"}

    async def _fake_resolve_symbol_to_curie(symbol: str, **kwargs: object) -> str | None:
        return known.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve_symbol_to_curie)


@pytest.fixture(autouse=True)
def _stub_ncbi_efetch_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import graph as graph_module
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput

    async def _fake_ncbi_efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty",
            action="dataset_report",
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _fake_ncbi_efetch)


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cost_control, "check_user_daily_query_cap", lambda session, user_id, **kw: None
    )
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda session, **kw: None)


@pytest.fixture(autouse=True)
def _auth_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_KEY)


@pytest.fixture(autouse=True)
def _reset_mint_throttle() -> None:
    """Clear the per-source mint throttle between clauses.

    The throttle is in-memory and per-process, so without this reset the
    suite throttles itself part way through and the durability arm starts
    failing, which is a false red that says nothing about the product.
    """
    from system_03_search_agent.auth import router as auth_router

    auth_router._mint_throttle._hits.clear()


def _client(source_host: str | None = None) -> AsyncClient:
    transport = (
        ASGITransport(app=app)
        if source_host is None
        else ASGITransport(app=app, client=(source_host, 123))
    )
    return AsyncClient(transport=transport, base_url="http://test")


def _unique_source() -> str:
    """A source address no other clause in this file has used.

    `guest_source_daily_usage` is keyed on (day, source) against a real,
    shared database that accumulates across a day, so a fixed address makes
    a clause pass or fail depending on what ran before it.
    """
    return f"203.0.113.{uuid.uuid4().hex}"


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


async def _mint_guest(client: AsyncClient) -> tuple[str, str, dict[str, str]]:
    """`POST /auth/guest`: the guest id, its raw token, and its headers."""
    response = await client.post("/auth/guest")
    assert response.status_code == 201, (
        f"a first-time visitor must be able to mint a guest identity; got "
        f"{response.status_code} {response.text[:200]}"
    )
    body = response.json()
    headers = {"Authorization": f"Bearer {body['guest_token']}"}
    return body["guest_id"], body["guest_token"], headers


async def _account_headers(
    client: AsyncClient, *, guest_token: str | None = None
) -> tuple[str, dict[str, str]]:
    email, password = _unique_email(), "Str0ngPassw0rd!"
    payload: dict[str, object] = {"email": email, "password": password}
    if guest_token is not None:
        payload["guest_token"] = guest_token
    signup = await client.post("/auth/signup", json=payload)
    assert signup.status_code == 201, signup.text[:200]
    user_id = signup.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text[:200]
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _drain_run_task(run_id: str) -> None:
    entry = run_registry_module.default_registry.get_run(run_id)
    await asyncio.wait_for(entry.task, timeout=30.0)


async def _run_and_drain(client: AsyncClient, headers: dict[str, str], text: str) -> str:
    """Take one real run to completion. Returns its run id."""
    response = await client.post(
        "/v1/query",
        json={"text": text, "session_id": f"session-{uuid.uuid4().hex[:8]}"},
        headers=headers,
    )
    assert response.status_code == 202, (
        f"the run had to be admitted for this clause to say anything; got "
        f"{response.status_code} {response.text[:200]}"
    )
    run_id = response.json()["run_id"]
    await _drain_run_task(run_id)
    return run_id


# ---------------------------------------------------------------------------
# Seeding. Used by every clause that needs rows without paying for a run.
# Goes through the real writer, not a hand-rolled INSERT, so a row this gate
# seeds is the same shape as a row real capture writes.
# ---------------------------------------------------------------------------


async def _seed_row(
    *, owner_id: str | None, question: str, user_id: uuid.UUID | None = None
) -> str:
    """Write one `interactions` row for `owner_id`. Returns its trace_id.

    `owner_id=None` is the pre-alembic-0008 shape, which `InteractionRow`
    refuses to construct (the field is required there) and which the table
    still permits. That one case goes through a direct parameterised INSERT
    deliberately: the row shape being tested is one the current write path
    can no longer produce, so seeding it through a model that rejects it is
    impossible.
    """
    from system_03_search_agent.feedback.contracts import InteractionRow
    from system_03_search_agent.feedback.writer import write_interaction

    trace_id = f"phase413-{uuid.uuid4().hex}"
    if owner_id is None:
        engine = sa.create_engine(USER_DB_URL)
        try:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO interactions "
                        "(trace_id, owner_id, user_id, query_text, query_class, route, "
                        " trust_signal, rubric_outcome) "
                        "VALUES (:trace_id, NULL, NULL, :query_text, 'lookup', "
                        " '{}'::jsonb, 'answer', 'pass')"
                    ),
                    {"trace_id": trace_id, "query_text": question},
                )
        finally:
            engine.dispose()
        return trace_id

    await write_interaction(
        InteractionRow(
            trace_id=trace_id,
            owner_id=owner_id,
            user_id=user_id,
            query_text=question,
            query_class="lookup",
            trust_signal="answer",
            rubric_outcome="pass",
        )
    )
    return trace_id


def _row_owner(trace_id: str) -> str | None:
    """Read a seeded row's stored owner straight from the table.

    This is the populate-check every clause below runs before asserting
    anything about isolation. Without it, "guest B cannot see it" is
    satisfied just as well by a seed that never landed.
    """
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT owner_id FROM interactions WHERE trace_id = :trace_id"),
                {"trace_id": trace_id},
            ).first()
    finally:
        engine.dispose()
    assert row is not None, (
        f"the seed for {trace_id} never reached the table, so every assertion "
        f"below this point would pass for the wrong reason"
    )
    return row[0]


async def _history(
    client: AsyncClient, headers: dict[str, str], **params: object
) -> tuple[int, dict]:
    response = await client.get(_HISTORY_PATH, headers=headers, params=params)
    body = response.json() if response.content else {}
    return response.status_code, body


def _questions(body: dict) -> list[str]:
    """The question strings in a history response, in the order returned."""
    assert "items" in body, f"a history response must carry `items`; got {str(body)[:300]}"
    return [item["question"] for item in body["items"]]


# ---------------------------------------------------------------------------
# The admit arm. This failing is a gate failure, exactly as much as the
# isolation arm failing.
# ---------------------------------------------------------------------------


class TestDurabilityArm:
    """The searches come back. Without this the phase delivered nothing."""

    @pytest.mark.asyncio
    async def test_a_real_run_is_visible_from_a_client_built_after_it_finished(self) -> None:
        """The flagship clause: the real caller's path, end to end.

        Deliberately a driven run rather than a seeded row. Build phase
        4.4's gate passed 6 of 6 while the default invocation was wrong,
        because five of six clauses took a path no caller takes.

        The second client is what "closing the browser" means here: a
        different connection, no shared in-process state, the same bearer
        token a browser would have kept.
        """
        question = f"What gene is BRCA1? marker-{uuid.uuid4().hex[:12]}"
        source = _unique_source()
        async with _client(source) as first:
            _, _, headers = await _mint_guest(first)
            await _run_and_drain(first, headers, question)

        async with _client(source) as reloaded:
            status, body = await _history(reloaded, headers)

        assert status == 200, f"GET {_HISTORY_PATH} must serve a guest; got {status} {body}"
        assert question in _questions(body), (
            "a run this caller actually completed is missing from their own "
            f"history, so nothing survived the reload. Got: {_questions(body)}"
        )

    @pytest.mark.asyncio
    async def test_the_list_reads_newest_first(self) -> None:
        """Order is part of the contract, not an accident of the planner.

        This clause proves NEWEST FIRST and nothing more. It used to be
        named for the total order too, and F-4.13-01 is the record of that
        being false: mutation-tested by dropping the `id` tiebreaker from
        the ORDER BY, it stayed green 10 times out of 10, because rows
        written through separate transactions never actually collide on
        `created_at` and the tie the tiebreaker exists for is never
        reached here.

        Measured, not reasoned about. Reversing the sort direction IS
        caught, which is what this clause earns its place on.

        The total order is a real requirement and it is asserted where it
        can actually fail: `tests/system_03_search_agent/feedback/
        test_history.py::test_order_is_total_when_created_at_collides`
        forces six rows onto one explicit timestamp, which no black-box
        call through this endpoint can do.
        """
        async with _client(_unique_source()) as client:
            guest_id, _, headers = await _mint_guest(client)
            owner_id = f"guest:{guest_id}"
            questions = [f"Question {n} marker-{uuid.uuid4().hex[:8]}" for n in range(3)]
            for question in questions:
                trace_id = await _seed_row(owner_id=owner_id, question=question)
                assert _row_owner(trace_id) == owner_id

            status, body = await _history(client, headers)

        assert status == 200, f"got {status} {body}"
        returned = [q for q in _questions(body) if q in questions]
        assert returned == list(reversed(questions)), (
            "history must read newest first (the total order, for rows "
            "sharing a timestamp, is proven separately in "
            "tests/system_03_search_agent/feedback/test_history.py::"
            f"test_order_is_total_when_created_at_collides). Got: {returned}"
        )

    @pytest.mark.asyncio
    async def test_the_question_comes_back_as_it_was_asked(self) -> None:
        """No truncation, no normalisation, no lower-casing of the text."""
        question = f"Which diseases are associated with TP53? marker-{uuid.uuid4().hex[:8]}"
        async with _client(_unique_source()) as client:
            guest_id, _, headers = await _mint_guest(client)
            trace_id = await _seed_row(owner_id=f"guest:{guest_id}", question=question)
            assert _row_owner(trace_id) == f"guest:{guest_id}"
            status, body = await _history(client, headers)

        assert status == 200, f"got {status} {body}"
        assert question in _questions(body), (
            f"the stored question was rewritten on the way out. Got: {_questions(body)}"
        )

    @pytest.mark.asyncio
    async def test_a_guests_searches_follow_them_into_the_account_they_create(self) -> None:
        """The claim "your searches move with you", asserted rather than made.

        The reassignment mechanism already exists
        (`feedback.writer.reassign_interaction_owner`). This clause proves
        the READ path agrees with it, which is the half that did not exist
        before this phase.
        """
        question = f"What gene is BRCA1? marker-{uuid.uuid4().hex[:12]}"
        async with _client(_unique_source()) as client:
            guest_id, guest_token, guest_headers = await _mint_guest(client)
            trace_id = await _seed_row(owner_id=f"guest:{guest_id}", question=question)
            assert _row_owner(trace_id) == f"guest:{guest_id}"

            status_before, body_before = await _history(client, guest_headers)
            assert status_before == 200, f"got {status_before} {body_before}"
            assert question in _questions(body_before), (
                "the control did not hold: the guest could not see their own "
                "row before signing up, so the clause below proves nothing"
            )

            _, account_headers = await _account_headers(client, guest_token=guest_token)
            status_after, body_after = await _history(client, account_headers)

        assert status_after == 200, f"got {status_after} {body_after}"
        assert question in _questions(body_after), (
            "a guest signed up while holding their token and their searches "
            f"did not follow them. Got: {_questions(body_after)}"
        )


# ---------------------------------------------------------------------------
# The refuse arm. The critical build phase 4.5 already shipped once.
# ---------------------------------------------------------------------------


class TestIsolationArm:
    """No caller ever sees another caller's questions."""

    @pytest.mark.asyncio
    async def test_one_guest_never_sees_another_guests_question(self) -> None:
        """The F-4.5-A-02 shape, exactly.

        Both principals have `user_id` NULL. Any implementation that scopes
        on `user_id` returns both rows to both callers and fails here. Both
        controls are asserted, so an implementation that returns an empty
        list to everybody fails here too.
        """
        marker_a = f"marker-{uuid.uuid4().hex[:12]}"
        marker_b = f"marker-{uuid.uuid4().hex[:12]}"
        question_a = f"What gene is BRCA1? {marker_a}"
        question_b = f"Which diseases are associated with TP53? {marker_b}"

        async with _client(_unique_source()) as client_a:
            guest_a, _, headers_a = await _mint_guest(client_a)
            trace_a = await _seed_row(owner_id=f"guest:{guest_a}", question=question_a)
            assert _row_owner(trace_a) == f"guest:{guest_a}"
            status_a, body_a = await _history(client_a, headers_a)

        async with _client(_unique_source()) as client_b:
            guest_b, _, headers_b = await _mint_guest(client_b)
            assert guest_b != guest_a, "the two clauses need two distinct principals"
            trace_b = await _seed_row(owner_id=f"guest:{guest_b}", question=question_b)
            assert _row_owner(trace_b) == f"guest:{guest_b}"
            status_b, body_b = await _history(client_b, headers_b)

        assert status_a == 200, f"got {status_a} {body_a}"
        assert status_b == 200, f"got {status_b} {body_b}"
        assert question_a in _questions(body_a), (
            "the control did not hold: guest A cannot see their own row, so "
            "guest B not seeing it says nothing at all"
        )
        assert question_b in _questions(body_b), (
            "the control did not hold: guest B cannot see their own row, so "
            "the isolation assertion below would pass on an empty response"
        )
        assert marker_a not in " ".join(_questions(body_b)), (
            "one anonymous visitor was handed another anonymous visitor's "
            f"questions. Got: {_questions(body_b)}"
        )
        assert marker_b not in " ".join(_questions(body_a)), (
            "isolation must hold in both directions. Got: " f"{_questions(body_a)}"
        )

    @pytest.mark.asyncio
    async def test_one_account_never_sees_another_accounts_question(self) -> None:
        marker_a = f"marker-{uuid.uuid4().hex[:12]}"
        marker_b = f"marker-{uuid.uuid4().hex[:12]}"
        question_a = f"Which diseases are associated with TP53? {marker_a}"
        question_b = f"What gene is BRCA1? {marker_b}"

        async with _client(_unique_source()) as client:
            user_a, headers_a = await _account_headers(client)
            trace_a = await _seed_row(
                owner_id=f"user:{user_a}", question=question_a, user_id=uuid.UUID(user_a)
            )
            assert _row_owner(trace_a) == f"user:{user_a}"

            user_b, headers_b = await _account_headers(client)
            trace_b = await _seed_row(
                owner_id=f"user:{user_b}", question=question_b, user_id=uuid.UUID(user_b)
            )
            assert _row_owner(trace_b) == f"user:{user_b}"

            status_a, body_a = await _history(client, headers_a)
            status_b, body_b = await _history(client, headers_b)

        assert status_a == 200, f"got {status_a} {body_a}"
        assert status_b == 200, f"got {status_b} {body_b}"
        assert question_a in _questions(body_a), (
            "the control did not hold: account A cannot see its own row"
        )
        assert question_b in _questions(body_b), (
            "the control did not hold: account B cannot see its own row"
        )
        assert marker_a not in " ".join(_questions(body_b)), (
            f"one account was handed another account's questions. Got: {_questions(body_b)}"
        )
        assert marker_b not in " ".join(_questions(body_a)), (
            f"isolation must hold in both directions. Got: {_questions(body_a)}"
        )

    @pytest.mark.asyncio
    async def test_a_row_with_no_owner_is_returned_to_nobody(self) -> None:
        """The pre-alembic-0008 shape.

        NULL never equals a caller's `owner_id`, which is the deny-by-default
        posture `feedback/writer.py`'s `_caller_owns_row` already takes. The
        clause pairs the orphan row with a real one for the SAME caller, so
        an implementation that returns nothing at all cannot pass it.
        """
        marker = f"orphan-{uuid.uuid4().hex[:12]}"
        orphan_trace = await _seed_row(owner_id=None, question=f"An orphaned question {marker}")
        assert _row_owner(orphan_trace) is None, (
            "the orphan seed landed with an owner, so this clause is testing "
            "an ordinary row rather than the pre-migration shape"
        )

        own_question = f"What gene is BRCA1? mine-{uuid.uuid4().hex[:8]}"
        async with _client(_unique_source()) as client:
            guest_id, _, headers = await _mint_guest(client)
            own_trace = await _seed_row(owner_id=f"guest:{guest_id}", question=own_question)
            assert _row_owner(own_trace) == f"guest:{guest_id}"
            status, body = await _history(client, headers)

        assert status == 200, f"got {status} {body}"
        assert own_question in _questions(body), (
            "the control did not hold: this caller cannot see their own row, "
            "so the orphan's absence proves nothing"
        )
        assert marker not in " ".join(_questions(body)), (
            f"a row with no recorded owner was served to a caller. Got: {_questions(body)}"
        )

    @pytest.mark.asyncio
    async def test_an_unauthenticated_caller_is_refused_rather_than_given_an_empty_list(
        self,
    ) -> None:
        """401, not 200 with nothing in it.

        A client must be able to tell "you have no searches yet" from "you
        are not signed in", because it does opposite things with them: the
        first renders the empty state, the second re-authenticates.
        """
        async with _client(_unique_source()) as client:
            response = await client.get(_HISTORY_PATH)

        assert response.status_code == 401, (
            f"an anonymous caller with no token must be refused; got "
            f"{response.status_code} {response.text[:200]}"
        )


# ---------------------------------------------------------------------------
# Bounds.
# ---------------------------------------------------------------------------


class TestBoundsArm:
    @pytest.mark.asyncio
    async def test_limit_is_honoured_rather_than_advisory(self) -> None:
        async with _client(_unique_source()) as client:
            guest_id, _, headers = await _mint_guest(client)
            owner_id = f"guest:{guest_id}"
            for n in range(4):
                trace_id = await _seed_row(
                    owner_id=owner_id, question=f"Question {n} {uuid.uuid4().hex[:8]}"
                )
                assert _row_owner(trace_id) == owner_id

            unbounded_status, unbounded = await _history(client, headers)
            status, body = await _history(client, headers, limit=2)

        assert unbounded_status == 200, f"got {unbounded_status} {unbounded}"
        assert len(_questions(unbounded)) >= 4, (
            "the control did not hold: fewer than the four seeded rows came "
            "back unbounded, so a capped response proves nothing. Got: "
            f"{len(_questions(unbounded))}"
        )
        assert status == 200, f"got {status} {body}"
        assert len(_questions(body)) == 2, f"limit=2 returned {len(_questions(body))} rows"

    @pytest.mark.asyncio
    async def test_a_limit_above_the_maximum_is_refused_and_says_what_to_send(self) -> None:
        """Refused, never silently clamped.

        A clamp answers a question the caller did not ask and tells them
        nothing about it, which is the shape `tool-call-budgets` forbids: an
        error must say what to do next.
        """
        async with _client(_unique_source()) as client:
            _, _, headers = await _mint_guest(client)
            response = await client.get(
                _HISTORY_PATH, headers=headers, params={"limit": _MAX_LIMIT + 1}
            )

        assert response.status_code == 422, (
            f"a limit above {_MAX_LIMIT} must be refused, not clamped; got "
            f"{response.status_code} {response.text[:300]}"
        )
        assert str(_MAX_LIMIT) in response.text, (
            "the refusal must name the maximum the caller should send "
            f"instead. Got: {response.text[:300]}"
        )

    @pytest.mark.asyncio
    async def test_the_default_limit_is_the_one_the_contract_states(self) -> None:
        """A default nobody states drifts. This clause is where it is stated.

        Seeded one past the default so the response can actually be capped:
        a caller holding fewer rows than the default cannot tell a correct
        default from any larger one.
        """
        async with _client(_unique_source()) as client:
            guest_id, _, headers = await _mint_guest(client)
            owner_id = f"guest:{guest_id}"
            for n in range(_DEFAULT_LIMIT + 1):
                await _seed_row(owner_id=owner_id, question=f"Q{n} {uuid.uuid4().hex[:8]}")

            status, body = await _history(client, headers)

        assert status == 200, f"got {status} {body}"
        assert len(_questions(body)) == _DEFAULT_LIMIT, (
            f"the stated default is {_DEFAULT_LIMIT}; got {len(_questions(body))}"
        )
