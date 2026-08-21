"""The two cap bypasses, graded where they were measured: at the caps.

F-4.6-A-01 and F-4.6-A-02 are one defect seen twice. Section 16 makes
capture best-effort ("Losing a row is an acceptable failure mode; blocking
the response is not"), and F-2.0-04 made the two daily caps count captured
rows. Composed, ANY condition that stops a row existing raises that
caller's cap to infinity. The adversary round found two such conditions,
one in the payload and one in the control flow, and measured each of them
turning a cap of three into no cap at all:

- One `chr(0)` appended to a question: twelve queries, twelve full answers,
  zero refusals.
- Stopping each run through `POST /v1/query/{run_id}/stop`: twelve
  accepted, twelve ran, zero rows.

## Why this file exists beside the others

Three files could each have claimed this and none of them can actually make
the claim:

- `feedback/test_writer.py` counts ROWS. "A row exists" and "the cap can see
  it" are two statements, and the second is the one the finding is about.
- `core/test_run_capture.py` mocks `capture_run`, so it grades the dispatch
  and never a database.
- The phase's premise gate owns the end-to-end path, and its P7 arm already
  grades that the cap fires on the ordinary path. It is a merged blocking
  gate that a fix round does not edit.

So this file drives real `run()` calls against a throwaway database and then
asks `get_user_daily_query_count` and `get_system_daily_cost_usd`, the two
functions the caps actually call, exactly as the adversary's probe did. An
honest control runs beside each attack, because an attack that leaves three
rows proves nothing unless three honest queries also leave three.

## Coverage: what this file exercises and what it deliberately omits

Exercised:

- The per-user daily query count, measured before and after a payload that
  the `interactions` columns cannot store.
- The system-wide daily cost, over the same runs, because F-4.6-A-01 names
  both caps and a fix that restores the count while leaving the money
  invisible closes half of it.
- The stopped-run path through a real `RunRegistry`, cancelled the way
  `POST /v1/query/{run_id}/stop` cancels it, including a run stopped late
  enough to have made real model calls.
- The abandoned-run path, which needs no attacker at all: the registry's own
  abandonment timer cancels a run nobody ever subscribed to.

NOT exercised, deliberately:

- The HTTP surfaces themselves. These arms call `run()` and drive
  `RunRegistry` directly; no arm posts to `/v1/query` or `/v1/query/{id}/
  stop`. If an endpoint ever stopped routing to either, this file could not
  see it, and `adapters/web_sse/test_streaming_endpoints.py` is where that
  would have to be caught.
- The guest allowance (build phase 4.10). A guest's `interactions.user_id`
  is NULL by design, so `get_user_daily_query_count` does not apply to them
  and their own allowance is a different mechanism with its own suite.
  Every arm here uses a registered account for that reason.
- Concurrency. Every run here finishes before the next begins.
- Whether the caps DECLINE at the boundary. That is
  `harness/test_cost_control.py`'s subject and the premise gate's P7. This
  file grades what the counters can see, which is the thing the bypasses
  changed.

Skips cleanly, never fails, when the PostgreSQL server is unreachable, the
same as every other database-backed module here.

Depends on:
    - system_03_search_agent.core.run (run)
    - system_03_search_agent.core.run_registry (RunRegistry)
    - system_03_search_agent.harness.cost_control (the two counters)
    - tests.system_03_search_agent.model_stub (the offline tier dispatch)

Writes:
    - A uniquely named throwaway database, created and dropped by this
      module. Never the shared development database: every arm here counts
      rows, and a shared table already carries other suites' residue.
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[3]
USER_DB_URL = os.environ.get(
    "USER_DB_URL", "postgresql://localhost:5432/search_agent_users"
)


def _can_connect(url: str) -> bool:
    try:
        probe = sa.create_engine(url)
        with probe.connect():
            pass
        probe.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


if not _can_connect(USER_DB_URL):
    pytest.skip(
        "search_agent_users PostgreSQL is not reachable; set USER_DB_URL and "
        "start the server to run this suite",
        allow_module_level=True,
    )


def _with_db_name(url: str, db_name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment)
    )


@pytest.fixture(scope="module")
def scratch_db_url():
    """A throwaway database for this module, dropped when the module ends."""
    from alembic.config import Config

    from alembic import command

    db_name = f"capture_bypass_{uuid.uuid4().hex}"
    assert re.fullmatch(r"[a-z0-9_]+", db_name)
    admin_url = _with_db_name(USER_DB_URL, "postgres")

    creator = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with creator.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        creator.dispose()

    url = _with_db_name(USER_DB_URL, db_name)
    previous = os.environ.get("USER_DB_URL")
    os.environ["USER_DB_URL"] = url
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    command.upgrade(cfg, "head")

    try:
        yield url
    finally:
        if previous is None:
            os.environ.pop("USER_DB_URL", None)
        else:
            os.environ["USER_DB_URL"] = previous
        dropper = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with dropper.connect() as conn:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": db_name},
                )
                conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        finally:
            dropper.dispose()


@pytest.fixture()
def scratch_db(scratch_db_url, monkeypatch):
    """Point the application's own engine at the scratch database.

    `data/base.py` memoises one engine per process, so setting the
    environment variable alone changes nothing for code that has already
    created it. Both resets are required, and the teardown repeats them.
    """
    from system_03_search_agent.data import base as base_module
    from system_03_search_agent.data import session as session_module

    monkeypatch.setenv("USER_DB_URL", scratch_db_url)
    base_module.reset_engine()
    session_module.reset_session_factory()
    try:
        yield scratch_db_url
    finally:
        base_module.reset_engine()
        session_module.reset_session_factory()


@pytest.fixture()
def offline_model(monkeypatch):
    """The real loop with the tier dispatch captured, reaching no network.

    A captured dispatch, never a mocked capture path: `run()`,
    `core/graph.py` and the whole write step execute for real.
    """
    from system_03_search_agent.harness import harness as harness_module
    from tests.system_03_search_agent.model_stub import (
        install_dispatching_acompletion,
    )

    return install_dispatching_acompletion(monkeypatch, harness_module)


def _insert_account(url: str) -> uuid.UUID:
    """A real `users` row, because `get_user_daily_query_count` keys on the
    account UUID and `interactions.user_id` is a foreign key to it."""
    account_id = uuid.uuid4()
    engine = sa.create_engine(url, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash) "
                    "VALUES (:id, :email, :ph)"
                ),
                {
                    "id": str(account_id),
                    "email": f"{account_id}@example.test",
                    "ph": "not-a-real-hash",
                },
            )
    finally:
        engine.dispose()
    return account_id


def _daily_query_count(account: uuid.UUID) -> int:
    from system_03_search_agent.data.session import session_scope
    from system_03_search_agent.harness.cost_control import (
        get_user_daily_query_count,
    )

    with session_scope() as db:
        return get_user_daily_query_count(db, account)


def _daily_system_cost() -> float:
    from system_03_search_agent.data.session import session_scope
    from system_03_search_agent.harness.cost_control import (
        get_system_daily_cost_usd,
    )

    with session_scope() as db:
        return get_system_daily_cost_usd(db)


async def _ask(question: str, *, owner_id: str, session_id: str) -> list:
    """Ask the way a real caller asks, naming nothing this fix owns."""
    from system_03_search_agent.contracts.query import Query, RequestContext
    from system_03_search_agent.core.run import run

    query = Query(
        text=question,
        session_id=session_id,
        trace_id=str(uuid.uuid4()),
        owner_id=owner_id,
    )
    return [event async for event in run(query, RequestContext(surface="rest_sse"))]


# ---------------------------------------------------------------------------
# F-4.6-A-01: a payload the columns cannot store.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_nul_bearing_question_is_counted_exactly_like_an_honest_one(
    scratch_db, offline_model
) -> None:
    """The finding, restated as its own regression test, control included.

    The control is not decoration. The adversary's own report leads with it
    for a reason: an attack run that ends with a count of three proves
    nothing unless three honest queries also end with three. Without the
    control, a fix that broke capture entirely would read identically to a
    fix that worked.

    Mutation: replace `_storable`'s body in `feedback/writer.py` with
    `return value`. Ran it. What ACTUALLY happened is not the count reading
    3: the degraded-row fallback catches the failed insert and still writes
    a countable row, so the count read 6 and stayed correct, and the arm
    went red on the `query_text` assertion instead. Recorded because it is
    the second layer of the fix masking the first, and because a version of
    this arm that only asserted the count would have passed with the
    sanitizer deleted.
    """
    account = _insert_account(scratch_db)
    owner_id = f"user:{account}"
    session_id = f"bypass-nul-{uuid.uuid4().hex[:8]}"

    for index in range(3):
        await _ask(f"What is BRCA{index}?", owner_id=owner_id, session_id=session_id)

    honest_count = _daily_query_count(account)
    honest_cost = _daily_system_cost()
    assert honest_count == 3, (
        "three honest queries did not leave three countable rows, so this arm "
        f"cannot measure the attack against anything; got {honest_count}"
    )
    assert honest_cost > 0.0

    for index in range(3):
        await _ask(
            f"What is BRCA{index}?{chr(0)}", owner_id=owner_id, session_id=session_id
        )

    attacked_count = _daily_query_count(account)
    assert attacked_count == 6, (
        "one NUL byte in the question made three queries invisible to the "
        f"per-user daily query cap; count read {attacked_count}, expected 6 "
        "(F-4.6-A-01)"
    )
    assert _daily_system_cost() > honest_cost, (
        "the NUL-bearing queries left no cost behind, so the system-wide "
        "daily cost cap is still blind to them (F-4.6-A-01)"
    )

    engine = sa.create_engine(scratch_db, future=True)
    try:
        with engine.connect() as conn:
            stored = [
                row.query_text
                for row in conn.execute(
                    text(
                        "SELECT query_text FROM interactions WHERE user_id = :uid "
                        "ORDER BY created_at"
                    ),
                    {"uid": str(account)},
                )
            ]
    finally:
        engine.dispose()
    assert stored[3:] == ["What is BRCA0?�", "What is BRCA1?�",
                          "What is BRCA2?�"], (
        "the unstorable code point was not replaced, so these rows landed "
        f"through the degraded-payload fallback rather than intact: {stored[3:]}"
    )


# ---------------------------------------------------------------------------
# F-4.6-A-02: a run that ends without reaching the end.
# ---------------------------------------------------------------------------


async def _await_cancelled(task) -> None:
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_a_stopped_run_is_counted(scratch_db, offline_model) -> None:
    """The Stop button, driven through a real `RunRegistry`.

    `POST /v1/query/{run_id}/stop` calls `cancel_run`, which cancels the
    background task draining the run. Three stopped runs must leave three
    countable rows, exactly as three completed ones do.

    Mutation: move `_capture_interaction` out of `run_streaming()`'s
    `finally` and back to the end of its body, which is where it sat when
    the finding was filed. This arm goes red with a count of 0.
    """
    from system_03_search_agent.contracts.query import Query, RequestContext
    from system_03_search_agent.core.run_registry import RunRegistry

    account = _insert_account(scratch_db)
    owner_id = f"user:{account}"
    registry = RunRegistry()

    for index in range(3):
        query = Query(
            text=f"What is TP5{index}?",
            session_id=f"bypass-stop-{uuid.uuid4().hex[:8]}",
            trace_id=str(uuid.uuid4()),
            owner_id=owner_id,
        )
        run_id = registry.create_run(
            query,
            RequestContext(surface="rest_sse"),
            run_id=query.trace_id,
            owner_id=owner_id,
        )
        await asyncio.sleep(0)
        registry.cancel_run(run_id)
        await _await_cancelled(registry.get_run(run_id).task)

    count = _daily_query_count(account)
    assert count == 3, (
        "stopping a run made it invisible to the per-user daily query cap, so "
        f"the Stop button is an unlimited free-query button; count {count} "
        "(F-4.6-A-02)"
    )


@pytest.mark.asyncio
async def test_a_run_stopped_after_real_model_calls_records_what_it_spent(
    scratch_db, offline_model
) -> None:
    """The expensive half of the same bypass.

    The adversary measured a late-cancelled run making three real model
    calls and capturing nothing, so the cost was spent and no cap could see
    it. A row that existed but reported zero cost would close the query-cap
    half and leave this half open, which is why the assertion is on the
    money and not only on the count.

    Mutation: hardcode `total_cost_usd=0.0` in
    `core/run._terminal_events_for_capture`. This arm goes red on the cost
    assertion while the count assertion above it stays green, which is the
    asymmetry it exists for.
    """
    from system_03_search_agent.contracts.query import Query, RequestContext
    from system_03_search_agent.core.run_registry import RunRegistry

    account = _insert_account(scratch_db)
    owner_id = f"user:{account}"
    registry = RunRegistry()

    query = Query(
        text="What is BRCA1?",
        session_id=f"bypass-late-{uuid.uuid4().hex[:8]}",
        trace_id=str(uuid.uuid4()),
        owner_id=owner_id,
    )
    run_id = registry.create_run(
        query,
        RequestContext(surface="rest_sse"),
        run_id=query.trace_id,
        owner_id=owner_id,
    )
    entry = registry.get_run(run_id)
    # Long enough for the guard and think steps to have really run and
    # really billed, which is what makes this the expensive case.
    for _ in range(40):
        await asyncio.sleep(0.01)
        if any(event.type == "cost" for event in entry.events):
            break
    assert any(event.type == "cost" for event in entry.events), (
        "the run was stopped before it spent anything, so this arm is not "
        "measuring what it claims to"
    )

    registry.cancel_run(run_id)
    await _await_cancelled(entry.task)

    assert _daily_query_count(account) == 1
    engine = sa.create_engine(scratch_db, future=True)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT cost_usd, trust_signal, rubric_outcome FROM "
                    "interactions WHERE trace_id = :tid"
                ),
                {"tid": query.trace_id},
            ).one()
    finally:
        engine.dispose()
    assert float(row.cost_usd) > 0.0, (
        "a run stopped after real model calls recorded zero cost, so the "
        "system-wide daily cost cap cannot see what it paid for (F-4.6-A-02)"
    )
    assert (row.trust_signal, row.rubric_outcome) == ("refuse", "abstain"), (
        "a run that never produced an answer must be recorded as one, so the "
        "weekly review ritual is not reading it as a successful answer"
    )


@pytest.mark.asyncio
async def test_an_abandoned_run_is_counted(scratch_db, offline_model) -> None:
    """The half that needs no attacker.

    A caller who posts a query and closes the tab never subscribes, and the
    registry's own abandonment timer cancels the run after the grace
    window. That is the same lost row as the Stop button and it happens to
    ordinary users by accident.

    Mutation: the same one as the stopped-run arm. This arm goes red with a
    count of 0 for the same reason and by a different route, which is why
    both are here rather than one standing in for the other.
    """
    from system_03_search_agent.contracts.query import Query, RequestContext
    from system_03_search_agent.core.run_registry import RunRegistry

    account = _insert_account(scratch_db)
    owner_id = f"user:{account}"
    # A grace window short enough to expire during this test, which is the
    # only thing this value changes: the mechanism under test is the
    # registry's own `_cancel_if_still_abandoned`, unmodified.
    registry = RunRegistry(abandon_grace_seconds=0.01)

    query = Query(
        text="What is BRCA1?",
        session_id=f"bypass-abandon-{uuid.uuid4().hex[:8]}",
        trace_id=str(uuid.uuid4()),
        owner_id=owner_id,
    )
    run_id = registry.create_run(
        query,
        RequestContext(surface="rest_sse"),
        run_id=query.trace_id,
        owner_id=owner_id,
    )
    entry = registry.get_run(run_id)
    for _ in range(200):
        await asyncio.sleep(0.01)
        if entry.task.done():
            break
    await _await_cancelled(entry.task)

    assert entry.cancelled, (
        "the run was never actually abandoned, so this arm is not measuring "
        "what it claims to"
    )
    assert _daily_query_count(account) == 1, (
        "a run abandoned by a client that never subscribed left no row, so "
        "neither daily cap can see it (F-4.6-A-02)"
    )
