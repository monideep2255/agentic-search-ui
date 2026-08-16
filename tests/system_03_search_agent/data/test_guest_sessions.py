"""Integration tests for `data/guest_sessions.py`'s creation and atomic spend (T-4.10-02).

Hits real local PostgreSQL, mirroring test_migration.py's scratch-database
pattern (create a uniquely named throwaway database, migrate it to head,
drop it when the module's tests are done), because the property under
test, that at most FREE_RUN_ALLOWANCE of several concurrent spends against
the same guest ever succeed, cannot be observed against SQLite or a mock:
it is a guarantee about how a real Postgres row lock resolves two
transactions racing the same UPDATE.

Skips cleanly (does not fail) when USER_DB_URL is unreachable, matching
every other live-database suite in this repo.

What this file covers: `create_guest_session`'s shape, `spend_one_run`'s
four states (spent, exhausted, attempts-exhausted, revoked-or-unknown), its
valid/invalid/null input handling, and the concurrency guarantee design
decision 3 exists for.

Added for F-4.10-R-01 and F-4.10-R-03: that the ATTEMPT counter advances
with every spend and is never given back by a refund, that a caller
refunded on every single run still stops at ATTEMPT_ALLOWANCE, that a
refusal ordering puts a spent answer allowance ahead of a spent attempt
allowance, that `refund_one_run` gives the SHARED daily budget back only
when asked to, and that `spend_one_anonymous_run` leaves the guest
completely uncharged when the daily statement RAISES rather than merely
refuses, which is the case design decision 8's constraint 1 names and the
shipped compensating statement could not cover.

What it deliberately does not cover: HTTP-level behavior (`POST
/auth/guest`, `GET /v1/allowance`), which is T-4.10-04's, and is exercised
by the phase 4.10 premise gate instead; the daily ceiling across a UTC
midnight boundary or across more than one process, which are the premise
gate's own declared non-coverage for the same reasons.
"""

from __future__ import annotations

import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from alembic import command
from system_03_search_agent.data import guest_sessions as guest_sessions_module
from system_03_search_agent.data.guest_sessions import (
    ATTEMPT_ALLOWANCE,
    FREE_RUN_ALLOWANCE,
    SpendState,
    create_guest_session,
    refund_one_run,
    spend_one_anonymous_run,
    spend_one_run,
)
from system_03_search_agent.data.models import GuestSession

REPO_ROOT = Path(__file__).resolve().parents[3]
USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")


def _can_connect(url: str) -> bool:
    try:
        probe_engine = sa.create_engine(url)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


if not _can_connect(USER_DB_URL):
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; "
        "set USER_DB_URL and ensure the server is running to run this suite",
        allow_module_level=True,
    )


def _with_db_name(url: str, db_name: str) -> str:
    """Return `url` with its path database name replaced by `db_name`,
    keeping the same host, port, and credentials."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment))


def _alembic_config() -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


@pytest.fixture(scope="module")
def scratch_db_url():
    """A uniquely named, throwaway database, migrated to head once for this
    module and dropped once every test in this module has finished.

    Never the database USER_DB_URL names: only this freshly created,
    randomly named database is a migration or write target anywhere below.
    USER_DB_URL itself is only touched transiently, and only so
    `alembic/env.py` (which reads it to resolve its target) points at the
    scratch database while `command.upgrade` runs; it is restored to
    whatever it held before, in a `finally` block, whether or not the
    upgrade succeeds. Every function-scoped fixture and test in this
    module then talks to the scratch database directly through an engine
    built from `url`, never by reading the environment, so nothing else in
    this file depends on that transient mutation.
    """
    db_name = f"guest_sessions_scratch_{uuid.uuid4().hex}"
    # Program-generated, never user input, but asserted anyway so this name
    # can never carry anything but a safe, quotable Postgres identifier.
    assert re.fullmatch(r"[a-z0-9_]+", db_name)
    admin_url = _with_db_name(USER_DB_URL, "postgres")

    creator_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with creator_engine.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
    finally:
        creator_engine.dispose()

    url = _with_db_name(USER_DB_URL, db_name)
    previous_env_value = os.environ.get("USER_DB_URL")
    os.environ["USER_DB_URL"] = url
    try:
        command.upgrade(_alembic_config(), "head")
    finally:
        if previous_env_value is None:
            os.environ.pop("USER_DB_URL", None)
        else:
            os.environ["USER_DB_URL"] = previous_env_value

    try:
        yield url
    finally:
        dropper_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with dropper_engine.connect() as conn:
                # Drop any lingering connections first; Postgres refuses to
                # drop a database with active connections.
                conn.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": db_name},
                )
                conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        finally:
            dropper_engine.dispose()


@pytest.fixture()
def db_session(scratch_db_url):
    """A fresh Session bound to the already-migrated scratch database,
    closed after the test. Built directly from `scratch_db_url`, never by
    reading USER_DB_URL from the environment."""
    engine = sa.create_engine(scratch_db_url, future=True)
    factory = sessionmaker(bind=engine, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# create_guest_session
# ---------------------------------------------------------------------------


def test_create_guest_session_returns_a_row_with_zero_allowance_used(db_session) -> None:
    guest = create_guest_session(db_session)
    assert isinstance(guest.id, uuid.UUID)
    assert guest.runs_used == 0
    assert guest.revoked_at is None
    assert guest.migrated_to_user_id is None


def test_create_guest_session_persists_and_is_visible_to_a_fresh_lookup(db_session) -> None:
    guest = create_guest_session(db_session)
    reloaded = db_session.get(GuestSession, guest.id)
    assert reloaded is not None
    assert reloaded.runs_used == 0


def test_create_guest_session_two_calls_produce_two_distinct_ids(db_session) -> None:
    first = create_guest_session(db_session)
    second = create_guest_session(db_session)
    assert first.id != second.id


def test_create_guest_session_invalid_input_non_session_raises(db_session) -> None:
    with pytest.raises(TypeError):
        create_guest_session("not-a-session")  # type: ignore[arg-type]


def test_create_guest_session_missing_input_none_raises(db_session) -> None:
    with pytest.raises(TypeError):
        create_guest_session(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# spend_one_run: valid input, the SPENT path
# ---------------------------------------------------------------------------


def test_spend_one_run_first_call_returns_spent_with_count_one(db_session) -> None:
    guest = create_guest_session(db_session)
    result = spend_one_run(db_session, str(guest.id))
    assert result.state == SpendState.SPENT
    assert result.runs_used == 1


def test_spend_one_run_accepts_a_uuid_object_directly(db_session) -> None:
    guest = create_guest_session(db_session)
    result = spend_one_run(db_session, guest.id)
    assert result.state == SpendState.SPENT
    assert result.runs_used == 1


def test_spend_one_run_up_to_the_cap_all_succeed_in_order(db_session) -> None:
    guest = create_guest_session(db_session)
    for expected in range(1, FREE_RUN_ALLOWANCE + 1):
        result = spend_one_run(db_session, guest.id)
        assert result.state == SpendState.SPENT
        assert result.runs_used == expected


def test_spend_one_run_honors_a_caller_supplied_cap(db_session) -> None:
    guest = create_guest_session(db_session)
    assert spend_one_run(db_session, guest.id, cap=1).state == SpendState.SPENT
    assert spend_one_run(db_session, guest.id, cap=1).state == SpendState.EXHAUSTED


# ---------------------------------------------------------------------------
# spend_one_run: the EXHAUSTED path
# ---------------------------------------------------------------------------


def test_spend_one_run_past_the_cap_returns_exhausted_with_the_final_count(db_session) -> None:
    guest = create_guest_session(db_session)
    for _ in range(FREE_RUN_ALLOWANCE):
        assert spend_one_run(db_session, guest.id).state == SpendState.SPENT
    result = spend_one_run(db_session, guest.id)
    assert result.state == SpendState.EXHAUSTED
    assert result.runs_used == FREE_RUN_ALLOWANCE


def test_spend_one_run_exhausted_call_does_not_advance_the_stored_count(db_session) -> None:
    guest = create_guest_session(db_session)
    for _ in range(FREE_RUN_ALLOWANCE):
        spend_one_run(db_session, guest.id)
    spend_one_run(db_session, guest.id)
    reloaded = db_session.get(GuestSession, guest.id)
    assert reloaded.runs_used == FREE_RUN_ALLOWANCE


# ---------------------------------------------------------------------------
# spend_one_run: the REVOKED_OR_UNKNOWN path
# ---------------------------------------------------------------------------


def test_spend_one_run_on_a_revoked_session_returns_revoked_or_unknown(db_session) -> None:
    guest = create_guest_session(db_session)
    db_session.execute(
        sa.text("UPDATE guest_sessions SET revoked_at = now() WHERE id = :id"),
        {"id": guest.id},
    )
    db_session.commit()
    result = spend_one_run(db_session, guest.id)
    assert result.state == SpendState.REVOKED_OR_UNKNOWN
    assert result.runs_used is None


def test_spend_one_run_on_an_unknown_guest_id_returns_revoked_or_unknown(db_session) -> None:
    result = spend_one_run(db_session, str(uuid.uuid4()))
    assert result.state == SpendState.REVOKED_OR_UNKNOWN
    assert result.runs_used is None


def test_spend_one_run_a_revoked_session_gains_no_count(db_session) -> None:
    guest = create_guest_session(db_session)
    db_session.execute(
        sa.text("UPDATE guest_sessions SET revoked_at = now() WHERE id = :id"),
        {"id": guest.id},
    )
    db_session.commit()
    spend_one_run(db_session, guest.id)
    reloaded = db_session.get(GuestSession, guest.id)
    assert reloaded.runs_used == 0


# ---------------------------------------------------------------------------
# spend_one_run: invalid and null input
# ---------------------------------------------------------------------------


def test_spend_one_run_invalid_guest_id_string_raises_value_error(db_session) -> None:
    with pytest.raises(ValueError):
        spend_one_run(db_session, "not-a-uuid")


def test_spend_one_run_missing_guest_id_none_raises_type_error(db_session) -> None:
    with pytest.raises(TypeError):
        spend_one_run(db_session, None)  # type: ignore[arg-type]


def test_spend_one_run_empty_guest_id_raises_value_error(db_session) -> None:
    with pytest.raises(ValueError):
        spend_one_run(db_session, "")


def test_spend_one_run_non_positive_cap_raises_value_error(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(ValueError):
        spend_one_run(db_session, guest.id, cap=0)


def test_spend_one_run_negative_cap_raises_value_error(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(ValueError):
        spend_one_run(db_session, guest.id, cap=-1)


def test_spend_one_run_non_int_cap_raises_type_error(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(TypeError):
        spend_one_run(db_session, guest.id, cap="5")  # type: ignore[arg-type]


def test_spend_one_run_bool_cap_raises_type_error(db_session) -> None:
    """bool is a subclass of int; excluded explicitly, matching guest.py's
    own exclusion of bool from its numeric `exp` check."""
    guest = create_guest_session(db_session)
    with pytest.raises(TypeError):
        spend_one_run(db_session, guest.id, cap=True)  # type: ignore[arg-type]


def test_spend_one_run_non_session_raises_type_error() -> None:
    with pytest.raises(TypeError):
        spend_one_run("not-a-session", str(uuid.uuid4()))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Concurrency: the property a read-then-write implementation silently fails
# ---------------------------------------------------------------------------


def test_the_allowance_holds_under_concurrent_spends(scratch_db_url) -> None:
    """FREE_RUN_ALLOWANCE + 1 threads race the cap boundary on one guest.

    Runs against genuinely separate connections and separate SQLAlchemy
    Sessions, one per thread pulled from a pooled engine, so it is a real
    Postgres row lock under test, not Python-level locking: psycopg2
    releases the GIL during blocking network I/O, so these threads issue
    overlapping UPDATE statements against the database, and the property
    under test is how Postgres resolves that overlap.

    If `spend_one_run` ever regressed to a SELECT-then-UPDATE, more than
    FREE_RUN_ALLOWANCE threads could read a pre-increment count under the
    cap before any of their UPDATEs land, and all of them would proceed to
    write, which is exactly the bug design decision 3 exists to prevent.
    True concurrency is achieved here, so no SQL-shape-only fallback is
    needed for this test.
    """
    engine = sa.create_engine(scratch_db_url, future=True)
    factory = sessionmaker(bind=engine, future=True)
    setup_session = factory()
    try:
        guest_id = create_guest_session(setup_session).id
    finally:
        setup_session.close()

    def _attempt(_: int) -> SpendState:
        thread_session = factory()
        try:
            return spend_one_run(thread_session, guest_id).state
        finally:
            thread_session.close()

    try:
        with ThreadPoolExecutor(max_workers=FREE_RUN_ALLOWANCE + 1) as pool:
            results = list(pool.map(_attempt, range(FREE_RUN_ALLOWANCE + 1)))
    finally:
        engine.dispose()

    spent = [state for state in results if state == SpendState.SPENT]
    exhausted = [state for state in results if state == SpendState.EXHAUSTED]
    assert len(spent) <= FREE_RUN_ALLOWANCE, (
        f"{len(spent)} of {FREE_RUN_ALLOWANCE + 1} concurrent spends succeeded; "
        f"the allowance is not being enforced atomically"
    )
    assert len(spent) + len(exhausted) == FREE_RUN_ALLOWANCE + 1


# ---------------------------------------------------------------------------
# The ATTEMPT counter (F-4.10-R-01). The per-identity bound the F-4.10-A-04
# refund removed, and the reason one guest token could drain the shared
# anonymous day in under two seconds.
# ---------------------------------------------------------------------------


def test_spend_one_run_advances_the_attempt_counter_alongside_the_answer(db_session) -> None:
    guest = create_guest_session(db_session)
    result = spend_one_run(db_session, guest.id)
    assert result.state == SpendState.SPENT
    assert result.runs_used == 1
    assert result.attempts_used == 1


def test_spend_one_run_stores_the_attempt_count_on_the_row(db_session) -> None:
    guest = create_guest_session(db_session)
    for _ in range(3):
        spend_one_run(db_session, guest.id)
    reloaded = db_session.get(GuestSession, guest.id)
    db_session.refresh(reloaded)
    assert reloaded.attempts_used == 3


def test_a_refund_gives_back_the_answer_and_never_the_attempt(db_session) -> None:
    """The asymmetry that IS the F-4.10-R-01 fix, at the statement level.

    Refunding both counters is what left a caller who only ever triggers
    refusals completely unbounded: no counter they advanced ever stopped
    them, so the only one still moving was the SHARED daily ceiling. This
    clause fails the moment `_UNSPEND_STATEMENT` learns about
    `attempts_used`.
    """
    guest = create_guest_session(db_session)
    spend_one_run(db_session, guest.id)
    assert refund_one_run(db_session, guest.id) is True

    reloaded = db_session.get(GuestSession, guest.id)
    db_session.refresh(reloaded)
    assert reloaded.runs_used == 0, "the answer must be given back"
    assert reloaded.attempts_used == 1, (
        "the attempt was given back too, which removes the only per-identity "
        "bound on a caller who sends nothing but refusable text (F-4.10-R-01)"
    )


def test_a_caller_who_is_refunded_every_time_still_stops_at_the_attempt_ceiling(
    db_session,
) -> None:
    """R-01's attack, at the data layer: refund every single run and count.

    Under the pre-fix statements this loop never terminates in any
    meaningful sense; every spend succeeds forever because `runs_used` is
    always back at zero by the next call.
    """
    guest = create_guest_session(db_session)
    spent = 0
    for _ in range(ATTEMPT_ALLOWANCE * 3):
        result = spend_one_run(db_session, guest.id)
        if result.state is not SpendState.SPENT:
            break
        spent += 1
        refund_one_run(db_session, guest.id)

    assert spent == ATTEMPT_ALLOWANCE, (
        f"{spent} runs were spent by a caller refunded every time; the "
        f"attempt ceiling of {ATTEMPT_ALLOWANCE} must bound them regardless "
        f"of how each run ended (F-4.10-R-01)"
    )
    refused = spend_one_run(db_session, guest.id)
    assert refused.state == SpendState.ATTEMPTS_EXHAUSTED
    assert refused.attempts_used == ATTEMPT_ALLOWANCE
    assert refused.runs_used == 0


def test_attempts_exhausted_is_reported_only_while_answers_remain(db_session) -> None:
    """The refusal ordering, at the one state where the two answers differ.

    A guest who genuinely used all five answers is the sign-in wall's own
    sentence, and that refusal is the more informative of the two, so it
    wins. Getting this backwards would show "you have asked as many
    questions as a guest can" to somebody who received five answers.

    THE STATE IS BUILT DELIBERATELY, and building it wrong is how this
    clause reads as a pass while proving nothing. A guest who simply spends
    five answers sits at `attempts_used = 5`, well under the ceiling of ten,
    so BOTH orderings return EXHAUSTED and inverting the code changes
    nothing: the mutation reaches the branch and cannot alter the outcome.
    Measured, not assumed: the inverted-ordering mutation left this file
    with 42 of 42 passing until this clause was rewritten.

    So the setup drives the guest to BOTH ceilings at once, five refunded
    runs followed by five kept ones, which is the only state where the two
    branches disagree.
    """
    guest = create_guest_session(db_session)
    for _ in range(ATTEMPT_ALLOWANCE - FREE_RUN_ALLOWANCE):
        assert spend_one_run(db_session, guest.id).state == SpendState.SPENT
        refund_one_run(db_session, guest.id)
    for _ in range(FREE_RUN_ALLOWANCE):
        assert spend_one_run(db_session, guest.id).state == SpendState.SPENT

    reloaded = db_session.get(GuestSession, guest.id)
    db_session.refresh(reloaded)
    assert (reloaded.runs_used, reloaded.attempts_used) == (
        FREE_RUN_ALLOWANCE,
        ATTEMPT_ALLOWANCE,
    ), "the setup did not reach both ceilings, so this clause cannot tell the two orderings apart"

    result = spend_one_run(db_session, guest.id)
    assert result.state == SpendState.EXHAUSTED, (
        "a guest with five answers delivered must be told their allowance is "
        "spent, not that they asked too many questions"
    )


def test_a_revoked_session_is_reported_as_revoked_even_at_the_attempt_ceiling(
    db_session,
) -> None:
    guest = create_guest_session(db_session)
    for _ in range(ATTEMPT_ALLOWANCE):
        spend_one_run(db_session, guest.id)
        refund_one_run(db_session, guest.id)
    db_session.execute(
        sa.text("UPDATE guest_sessions SET revoked_at = now() WHERE id = :id"),
        {"id": guest.id},
    )
    db_session.commit()
    assert spend_one_run(db_session, guest.id).state == SpendState.REVOKED_OR_UNKNOWN


def test_spend_one_run_non_positive_attempt_cap_raises_value_error(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(ValueError):
        spend_one_run(db_session, guest.id, attempt_cap=0)


def test_spend_one_run_non_int_attempt_cap_raises_type_error(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(TypeError):
        spend_one_run(db_session, guest.id, attempt_cap="10")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# refund_one_run's SHARED daily half (F-4.10-R-01 part B), and its input
# handling.
# ---------------------------------------------------------------------------


def _daily_used(session, day) -> int:
    """Today's shared anonymous count, with a missing row read as zero.

    Every clause below measures a DELTA against this rather than an absolute
    value. The scratch database is module-scoped, so `guest_daily_usage`
    accumulates across the tests in this file; an absolute assertion would
    pass or fail on execution order, which is the shape of green that says
    nothing.
    """
    return int(
        session.execute(
            sa.text("SELECT runs_used FROM guest_daily_usage WHERE day = :day"), {"day": day}
        ).scalar_one_or_none()
        or 0
    )


def test_a_refund_with_a_daily_day_gives_back_the_shared_budget(db_session) -> None:
    """Part B: a refusal that made NO model call must not charge the day.

    Charging the shared ceiling for a free refusal is what made the drain
    cheap: the caller paid nothing and everyone else lost a slot.
    """
    guest = create_guest_session(db_session)
    today = datetime.now(UTC).date()
    before = _daily_used(db_session, today)
    spend_one_anonymous_run(
        db_session, guest.id, daily_cap=10_000, source_hash=None, source_cap=1_000
    )
    assert _daily_used(db_session, today) == before + 1

    refund_one_run(db_session, guest.id, daily_day=today)
    assert _daily_used(db_session, today) == before, (
        "a refusal that made no model call still cost the shared day a slot; "
        "that is what let one caller take the anonymous product offline "
        "(F-4.10-R-01 part B)"
    )


def test_a_refund_without_a_daily_day_leaves_the_shared_budget_charged(db_session) -> None:
    """The other half, and it is not decoration.

    A refusal that came after a real Guard-tier call DID spend money, the
    day's budget is what bounds money, and refunding it there is the
    free-compute path F-4.10-A-04's decision was right to avoid.
    """
    guest = create_guest_session(db_session)
    today = datetime.now(UTC).date()
    before = _daily_used(db_session, today)
    spend_one_anonymous_run(
        db_session, guest.id, daily_cap=10_000, source_hash=None, source_cap=1_000
    )

    refund_one_run(db_session, guest.id)
    assert _daily_used(db_session, today) == before + 1, (
        "a paid refusal gave the day's budget back, which makes unlimited "
        "refusable traffic free compute"
    )


def test_a_daily_refund_can_never_drive_the_shared_counter_negative(db_session) -> None:
    today = datetime.now(UTC).date()
    guest = create_guest_session(db_session)
    spend_one_anonymous_run(
        db_session, guest.id, daily_cap=10_000, source_hash=None, source_cap=1_000
    )
    for _ in range(50):
        refund_one_run(db_session, guest.id, daily_day=today)
    assert _daily_used(db_session, today) == 0


def test_a_daily_refund_for_an_unknown_day_is_a_clean_no_op(db_session) -> None:
    guest = create_guest_session(db_session)
    spend_one_run(db_session, guest.id)
    long_ago = date(2000, 1, 1)
    refund_one_run(db_session, guest.id, daily_day=long_ago)
    assert _daily_used(db_session, long_ago) == 0


def test_refund_one_run_rejects_a_non_date_daily_day(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(TypeError):
        refund_one_run(db_session, guest.id, daily_day="2026-08-15")  # type: ignore[arg-type]


def test_refund_one_run_rejects_a_malformed_guest_id(db_session) -> None:
    with pytest.raises(ValueError):
        refund_one_run(db_session, "not-a-uuid")


def test_refund_one_run_rejects_a_null_guest_id(db_session) -> None:
    with pytest.raises(TypeError):
        refund_one_run(db_session, None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# spend_one_anonymous_run: ONE transaction (F-4.10-R-03, design decision 8's
# constraint 1).
# ---------------------------------------------------------------------------


def test_a_daily_ceiling_refusal_leaves_the_guest_uncharged(db_session) -> None:
    today = datetime.now(UTC).date()
    # Put the day at a known, non-zero count first, then set the cap to
    # exactly that. The scratch database is module-scoped, so the day's
    # count depends on what ran before; deriving the cap from the measured
    # count is what makes this clause independent of that ordering.
    burner = create_guest_session(db_session)
    assert (
        spend_one_anonymous_run(
            db_session, burner.id, daily_cap=10_000, source_hash=None, source_cap=1_000
        ).state
        == SpendState.SPENT
    )
    at_ceiling = _daily_used(db_session, today)

    victim = create_guest_session(db_session)
    result = spend_one_anonymous_run(
        db_session, victim.id, daily_cap=at_ceiling, source_hash=None, source_cap=1_000
    )
    assert result.state == SpendState.DAILY_CAP_REACHED

    reloaded = db_session.get(GuestSession, victim.id)
    db_session.refresh(reloaded)
    assert reloaded.runs_used == 0
    assert reloaded.attempts_used == 0, (
        "a run the system-wide ceiling refused must not cost the visitor an "
        "attempt either; they were never allowed to start it"
    )
    assert _daily_used(db_session, today) == at_ceiling


def test_a_raising_daily_statement_leaves_the_guest_uncharged(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-4.10-R-03, the case that had no test and no compensation path.

    Design decision 8's constraint 1 is verbatim: "The two spends, per-guest
    and per-day, happen in ONE transaction. A per-guest spend that commits
    while the daily spend fails charges a visitor for a run they never got."
    The shipped code committed the per-guest increment first and compensated
    with a second statement, which covered a ceiling REFUSAL and could not
    cover a FAILURE. The re-review measured the result: `guest runs_used
    after the failed daily spend: 1`, plus a 500 to the caller.

    The exact exception class the broken statement raises is not the point
    and is not asserted; that the transaction never committed is.
    """
    guest = create_guest_session(db_session)
    today = datetime.now(UTC).date()
    before = _daily_used(db_session, today)

    monkeypatch.setattr(
        guest_sessions_module,
        "_DAILY_SPEND_STATEMENT",
        sa.text("INSERT INTO guest_daily_usage (day, runs_used) VALUES (:day, :daily_cap / 0)"),
    )

    with pytest.raises(sa.exc.DBAPIError):
        spend_one_anonymous_run(
            db_session, guest.id, daily_cap=50, source_hash=_SOURCE_A, source_cap=50
        )
    db_session.rollback()

    reloaded = db_session.get(GuestSession, guest.id)
    db_session.refresh(reloaded)
    assert reloaded.runs_used == 0, (
        "the per-guest spend committed while the daily spend failed, so the "
        "visitor lost a free search for a run they never got AND received a "
        "500; that is exactly what constraint 1 forbids (F-4.10-R-03)"
    )
    assert reloaded.attempts_used == 0
    assert _daily_used(db_session, today) == before


def test_spend_one_anonymous_run_rejects_a_non_positive_daily_cap(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(ValueError):
        spend_one_anonymous_run(
            db_session, guest.id, daily_cap=0, source_hash=None, source_cap=10
        )


def test_spend_one_anonymous_run_rejects_a_null_session(db_session) -> None:
    with pytest.raises(TypeError):
        spend_one_anonymous_run(
            None,  # type: ignore[arg-type]
            str(uuid.uuid4()),
            daily_cap=5,
            source_hash=None,
            source_cap=5,
        )


# ---------------------------------------------------------------------------
# The per-SOURCE share of the day (F-4.10-V-01), at the data layer. The
# end-to-end attack is `TestOneSourceCannotTakeTheWholeAnonymousDay` in
# `tests/.../adapters/web_sse/test_phase_4_10_premise.py`; what is pinned here
# is the counter's own arithmetic, its refund symmetry with the day, and that
# it stays inside the one transaction the other two counters already share.
# ---------------------------------------------------------------------------


def _source_used(session, day, source_hash) -> int:
    """One source's count for `day`, with a missing row read as zero.

    A delta measure for the same reason `_daily_used` above is one: the
    scratch database is module-scoped and the table accumulates across this
    file, so an absolute assertion would pass or fail on execution order.
    Each clause below uses its own source hash, which makes that mostly moot
    and is stated rather than relied on silently.
    """
    return int(
        session.execute(
            sa.text(
                "SELECT runs_used FROM guest_source_daily_usage"
                " WHERE day = :day AND source_hash = :source_hash"
            ),
            {"day": day, "source_hash": source_hash},
        ).scalar_one_or_none()
        or 0
    )


# Distinct 64-character hashes, the shape `auth.router._hash_ip` actually
# produces, rather than short strings: the column is sized to a SHA-256 hex
# digest and a clause that only ever passes "src-a" would not notice a
# length regression.
_SOURCE_A = "a" * 64
_SOURCE_B = "b" * 64


def test_one_source_cannot_spend_past_its_share_of_the_day(db_session) -> None:
    """The bound itself, with the day deliberately left wide open.

    The daily cap is 10,000 here so that nothing but the source counter can
    refuse. With the two caps close together this clause would pass for the
    wrong reason, reporting on the ceiling it exists to protect, which is the
    trap F-4.10-R-11 recorded one bound down.
    """
    today = datetime.now(UTC).date()
    source = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    accepted, refusals = 0, []
    for _ in range(8):
        guest = create_guest_session(db_session)
        result = spend_one_anonymous_run(
            db_session, guest.id, daily_cap=10_000, source_hash=source, source_cap=3
        )
        if result.state is SpendState.SPENT:
            accepted += 1
        else:
            refusals.append(result.state)

    assert accepted == 3, (
        f"{accepted} runs were accepted against a source share of 3, from eight "
        f"freshly minted identities; a bound keyed on the identity is a bound "
        f"keyed on something the caller mints for free (F-4.10-V-01)"
    )
    assert refusals == [SpendState.SOURCE_DAILY_CAP_REACHED] * 5
    assert _source_used(db_session, today, source) == 3


def test_a_source_refusal_leaves_the_guest_and_the_day_uncharged(db_session) -> None:
    """The compensating half, the same one the daily ceiling already has.

    The per-guest spend and the day's spend both commit BEFORE the source
    statement is consulted, so a source refusal must reverse both or a
    visitor behind a busy address quietly loses searches they were never
    allowed to use, and the shared day counts runs that never happened.
    """
    today = datetime.now(UTC).date()
    source = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    burner = create_guest_session(db_session)
    assert (
        spend_one_anonymous_run(
            db_session, burner.id, daily_cap=10_000, source_hash=source, source_cap=1
        ).state
        is SpendState.SPENT
    )
    day_before = _daily_used(db_session, today)

    victim = create_guest_session(db_session)
    result = spend_one_anonymous_run(
        db_session, victim.id, daily_cap=10_000, source_hash=source, source_cap=1
    )
    assert result.state is SpendState.SOURCE_DAILY_CAP_REACHED

    reloaded = db_session.get(GuestSession, victim.id)
    db_session.refresh(reloaded)
    assert reloaded.runs_used == 0
    assert reloaded.attempts_used == 0, (
        "a run the source share refused must not cost the visitor an attempt "
        "either; they were never allowed to start it"
    )
    assert _daily_used(db_session, today) == day_before, (
        "the shared day was left advanced by a run nobody was allowed to "
        "start, so a caller whose source is spent could still burn down the "
        "day's budget for everyone else just by retrying"
    )
    assert _source_used(db_session, today, source) == 1


def test_two_sources_have_independent_shares(db_session) -> None:
    """The admit arm at the data layer: one address exhausting its share
    must not refuse a different address. A bound that leaks across sources
    is a global bound wearing a per-source name."""
    today = datetime.now(UTC).date()
    source_a = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    source_b = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    for _ in range(2):
        guest = create_guest_session(db_session)
        spend_one_anonymous_run(
            db_session, guest.id, daily_cap=10_000, source_hash=source_a, source_cap=2
        )
    spent_out = create_guest_session(db_session)
    assert (
        spend_one_anonymous_run(
            db_session, spent_out.id, daily_cap=10_000, source_hash=source_a, source_cap=2
        ).state
        is SpendState.SOURCE_DAILY_CAP_REACHED
    )

    neighbour = create_guest_session(db_session)
    assert (
        spend_one_anonymous_run(
            db_session, neighbour.id, daily_cap=10_000, source_hash=source_b, source_cap=2
        ).state
        is SpendState.SPENT
    )
    assert _source_used(db_session, today, source_b) == 1


def test_an_unknown_source_is_allowed_and_bounded_only_by_the_day(db_session) -> None:
    """`source_hash=None` means the connection address could not be
    determined. Allowed rather than refused, matching `_MintThrottle.allow`'s
    existing choice for the same input, because refusing every request whose
    source is unknown turns a missing value into an outage while the day's
    ceiling still holds the money.

    This is the residual gap, asserted so it is on the record rather than
    discovered: a deployment that strips `request.client` loses this bound.
    """
    today = datetime.now(UTC).date()
    before = _daily_used(db_session, today)
    guest = create_guest_session(db_session)
    result = spend_one_anonymous_run(
        db_session, guest.id, daily_cap=10_000, source_hash=None, source_cap=1
    )
    assert result.state is SpendState.SPENT, (
        "a caller whose source cannot be determined was refused; the source "
        "share is defense keyed on the source, and the day is what bounds the "
        "money when there is no source to key on"
    )
    assert _daily_used(db_session, today) == before + 1


def test_the_spend_reports_the_day_it_actually_charged(db_session) -> None:
    """F-4.10-V-04. The refund must land on the day the spend charged, and
    the only way a caller can know that day is for the spend to report it.
    Recomputing `datetime.now(UTC).date()` at refusal time satisfies the
    signature and not the argument: across a UTC midnight between the two,
    the charge lands on D and the refund on D+1."""
    guest = create_guest_session(db_session)
    result = spend_one_anonymous_run(
        db_session, guest.id, daily_cap=10_000, source_hash=_SOURCE_A, source_cap=1_000
    )
    assert result.state is SpendState.SPENT
    assert result.charged_day is not None, (
        "the spend did not report the day it charged, so every caller has to "
        "read the clock a second time, which is F-4.10-V-04 exactly"
    )
    assert _daily_used(db_session, result.charged_day) > 0, (
        "the reported day is not the day the shared counter actually moved"
    )


def test_a_refusal_reports_no_charged_day(db_session) -> None:
    """The other direction: nothing was charged, so there is no day to
    refund against, and a caller that got one would decrement a counter this
    run never advanced."""
    today = datetime.now(UTC).date()
    burner = create_guest_session(db_session)
    spend_one_anonymous_run(
        db_session, burner.id, daily_cap=10_000, source_hash=None, source_cap=1_000
    )
    at_ceiling = _daily_used(db_session, today)
    victim = create_guest_session(db_session)
    result = spend_one_anonymous_run(
        db_session, victim.id, daily_cap=at_ceiling, source_hash=None, source_cap=1_000
    )
    assert result.state is SpendState.DAILY_CAP_REACHED
    assert result.charged_day is None


def test_a_refund_gives_back_the_source_share_with_the_day(db_session) -> None:
    """The two shared counters move in LOCKSTEP.

    A day given back while the source's share stays charged makes the share
    bound tighter than the thing it subdivides: an office visitor's clumsy,
    free-refused question would permanently cost that office part of its
    budget for work the system never did.
    """
    today = datetime.now(UTC).date()
    source = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    guest = create_guest_session(db_session)
    spend_one_anonymous_run(
        db_session, guest.id, daily_cap=10_000, source_hash=source, source_cap=100
    )
    assert _source_used(db_session, today, source) == 1

    refund_one_run(db_session, guest.id, daily_day=today, source_hash=source)
    assert _source_used(db_session, today, source) == 0, (
        "the day was refunded and this source's share of it was not, so a free "
        "refusal permanently costs a shared address part of its budget for "
        "work that never happened (F-4.10-V-01)"
    )


def test_a_paid_refusal_leaves_both_shared_counters_charged(db_session) -> None:
    """The other half, and it is not decoration: a refusal that came after a
    real Guard-tier call spent money, and refunding either shared counter
    there is the free-compute path F-4.10-A-04's decision was right to
    avoid."""
    today = datetime.now(UTC).date()
    source = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    day_before = _daily_used(db_session, today)
    guest = create_guest_session(db_session)
    spend_one_anonymous_run(
        db_session, guest.id, daily_cap=10_000, source_hash=source, source_cap=100
    )

    refund_one_run(db_session, guest.id)
    assert _daily_used(db_session, today) == day_before + 1
    assert _source_used(db_session, today, source) == 1


def test_a_source_refund_can_never_drive_the_counter_negative(db_session) -> None:
    today = datetime.now(UTC).date()
    source = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    guest = create_guest_session(db_session)
    spend_one_anonymous_run(
        db_session, guest.id, daily_cap=10_000, source_hash=source, source_cap=100
    )
    for _ in range(50):
        refund_one_run(db_session, guest.id, daily_day=today, source_hash=source)
    assert _source_used(db_session, today, source) == 0


def test_a_raising_source_statement_leaves_every_counter_uncharged(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Design decision 8's constraint 1, extended to the third counter.

    F-4.10-R-03 measured a per-guest spend committing while the daily spend
    failed. Adding a counter after that one is the obvious way to reintroduce
    it, so the property is re-proved with the new statement rather than
    assumed to have survived: a raise here must leave the guest, the day and
    the source exactly where they were.
    """
    today = datetime.now(UTC).date()
    source = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    guest = create_guest_session(db_session)
    day_before = _daily_used(db_session, today)

    monkeypatch.setattr(
        guest_sessions_module,
        "_SOURCE_DAILY_SPEND_STATEMENT",
        sa.text(
            "INSERT INTO guest_source_daily_usage (day, source_hash, runs_used)"
            " VALUES (:day, :source_hash, :source_cap / 0)"
        ),
    )

    with pytest.raises(sa.exc.DBAPIError):
        spend_one_anonymous_run(
            db_session, guest.id, daily_cap=10_000, source_hash=source, source_cap=50
        )
    db_session.rollback()

    reloaded = db_session.get(GuestSession, guest.id)
    db_session.refresh(reloaded)
    assert reloaded.runs_used == 0, (
        "the per-guest spend committed while the source spend failed, so the "
        "visitor lost a free search for a run they never got; that is what "
        "constraint 1 forbids (F-4.10-R-03, re-proved with the third counter)"
    )
    assert reloaded.attempts_used == 0
    assert _daily_used(db_session, today) == day_before
    assert _source_used(db_session, today, source) == 0


def test_spend_one_anonymous_run_rejects_a_non_positive_source_cap(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(ValueError):
        spend_one_anonymous_run(
            db_session, guest.id, daily_cap=10, source_hash=_SOURCE_A, source_cap=0
        )


def test_spend_one_anonymous_run_rejects_a_non_string_source_hash(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(TypeError):
        spend_one_anonymous_run(
            db_session,
            guest.id,
            daily_cap=10,
            source_hash=12345,  # type: ignore[arg-type]
            source_cap=10,
        )


def test_refund_one_run_rejects_a_non_string_source_hash(db_session) -> None:
    guest = create_guest_session(db_session)
    with pytest.raises(TypeError):
        refund_one_run(
            db_session,
            guest.id,
            daily_day=datetime.now(UTC).date(),
            source_hash=12345,  # type: ignore[arg-type]
        )


def test_a_source_hash_without_a_daily_day_refunds_nothing_shared(db_session) -> None:
    """`source_hash` alone is accepted and does nothing, which is stated
    rather than left implicit: there is no state in which refunding one
    source's share while leaving the day charged is correct, since the share
    is a share OF the day."""
    today = datetime.now(UTC).date()
    source = f"{uuid.uuid4().hex}{uuid.uuid4().hex}"
    guest = create_guest_session(db_session)
    spend_one_anonymous_run(
        db_session, guest.id, daily_cap=10_000, source_hash=source, source_cap=100
    )
    day_before = _daily_used(db_session, today)

    refund_one_run(db_session, guest.id, source_hash=source)
    assert _daily_used(db_session, today) == day_before
    assert _source_used(db_session, today, source) == 1
