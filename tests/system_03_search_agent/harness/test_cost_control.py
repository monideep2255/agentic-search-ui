"""Tests for cost_control.py (T-2.0-03): the three cap checks, the cost
event builder, the end-user event filter, and the no-dollar-figure scan.

Env-var reading, the per-query pre-flight estimate, decline-message shape,
the cost-event builder, and the adapter filter need no database and always
run. The per-user daily query count and the system-wide daily dollar total
are read live against the `interactions` table (Section 15), so those
tests are integration tests against the real local PostgreSQL
`search_agent_users` database, matching the pattern in
`tests/system_03_search_agent/data/test_models.py`: they skip cleanly (do
not fail) when the database is unreachable.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.orm import Session

from alembic import command
from system_03_search_agent.contracts.events import CostPayload, DonePayload, Event
from system_03_search_agent.data.models import Interaction, User
from system_03_search_agent.harness.cost_control import (
    PER_QUERY_CAP_PARTIAL_RESULT_NOTE,
    SYSTEM_DAILY_CAP_DECLINE_MESSAGE,
    QueryCapExceededError,
    SystemDailyCostCapExceededError,
    UserDailyQueryCapExceededError,
    build_cost_event_payload,
    check_per_query_cap,
    check_system_daily_cost_cap,
    check_user_daily_query_cap,
    estimate_call_cost_usd,
    filter_events_for_end_user,
    get_system_daily_cost_usd,
    get_user_daily_query_count,
    is_end_user_visible_event_type,
    per_query_cost_cap_usd,
    per_user_daily_query_cap,
    system_daily_cap_usd,
    user_daily_cap_decline_message,
)
from system_03_search_agent.harness.harness import Harness
from system_03_search_agent.harness.tiers import UnknownTierError

REPO_ROOT = Path(__file__).resolve().parents[3]
USER_DB_URL = "postgresql://localhost:5432/search_agent_users"


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


_DB_REACHABLE = _can_connect()
requires_db = pytest.mark.skipif(
    not _DB_REACHABLE,
    reason="search_agent_users PostgreSQL database is not reachable",
)


# ---------------------------------------------------------------------------
# Environment-configured caps: no default, raise a clear error when unset.
# ---------------------------------------------------------------------------


def test_per_query_cost_cap_usd_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.10")
    assert per_query_cost_cap_usd() == pytest.approx(0.10)


def test_per_query_cost_cap_usd_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PER_QUERY_COST_CAP_USD", raising=False)
    with pytest.raises(RuntimeError, match="PER_QUERY_COST_CAP_USD"):
        per_query_cost_cap_usd()


def test_per_user_daily_query_cap_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    assert per_user_daily_query_cap() == 100


def test_per_user_daily_query_cap_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PER_USER_DAILY_QUERY_CAP", raising=False)
    with pytest.raises(RuntimeError, match="PER_USER_DAILY_QUERY_CAP"):
        per_user_daily_query_cap()


def test_system_daily_cap_usd_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "10")
    assert system_daily_cap_usd() == pytest.approx(10.0)


def test_system_daily_cap_usd_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYSTEM_DAILY_CAP_USD", raising=False)
    with pytest.raises(RuntimeError, match="SYSTEM_DAILY_CAP_USD"):
        system_daily_cap_usd()


# ---------------------------------------------------------------------------
# estimate_call_cost_usd: a positive, tier-differentiated, invalid-tier-raises estimate.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tier", ["guard", "plan", "synth"])
def test_estimate_call_cost_usd_positive_for_every_tier(tier: str) -> None:
    assert estimate_call_cost_usd(tier) > 0.0  # type: ignore[arg-type]


def test_estimate_call_cost_usd_synth_costs_more_than_guard() -> None:
    # Synth's typical token profile (retrieved passages, citation assembly)
    # is the longest of the three tiers, so its estimate must be the largest.
    assert estimate_call_cost_usd("synth") > estimate_call_cost_usd("plan")
    assert estimate_call_cost_usd("plan") > estimate_call_cost_usd("guard")


def test_estimate_call_cost_usd_unknown_tier_raises() -> None:
    with pytest.raises(UnknownTierError):
        estimate_call_cost_usd("bogus")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# check_per_query_cap: the pre-flight refusal, before any call is dispatched.
# ---------------------------------------------------------------------------


def test_check_per_query_cap_allows_call_when_well_under_cap() -> None:
    harness = Harness(trace_id="trace-1")
    # No cost tracked yet; a generous cap must not raise.
    check_per_query_cap(harness, "trace-1", "guard", query_cap_usd=1.0)


def test_check_per_query_cap_refuses_when_projected_cost_exceeds_cap() -> None:
    harness = Harness(trace_id="trace-1")
    harness.track_cost("trace-1", "synth", 0.099)
    cap = 0.10

    with pytest.raises(QueryCapExceededError) as exc_info:
        check_per_query_cap(harness, "trace-1", "synth", query_cap_usd=cap)

    err = exc_info.value
    assert err.query_cost_usd == pytest.approx(0.099)
    assert err.query_cap_usd == pytest.approx(cap)
    assert err.estimated_call_cost_usd > 0.0


def test_check_per_query_cap_refuses_before_any_call_is_dispatched() -> None:
    """A cap check that already exceeds the cap must refuse even with zero
    tracked cost so far, since the pre-flight estimate alone can exceed a
    very small cap: the check never requires a call to have already fired."""
    harness = Harness(trace_id="trace-1")
    tiny_cap = 0.0001  # smaller than any tier's conservative estimate

    with pytest.raises(QueryCapExceededError):
        check_per_query_cap(harness, "trace-1", "synth", query_cap_usd=tiny_cap)


def test_check_per_query_cap_uses_env_cap_when_not_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.0001")
    harness = Harness(trace_id="trace-1")
    with pytest.raises(QueryCapExceededError):
        check_per_query_cap(harness, "trace-1", "synth")


def test_check_per_query_cap_reads_harness_accumulator_not_a_duplicate() -> None:
    """The pre-flight check must reflect Harness.track_cost's own running
    total, proving cost_control does not keep a second, divergent counter."""
    harness = Harness(trace_id="trace-1")
    harness.track_cost("trace-1", "guard", 0.05)
    harness.track_cost("trace-1", "plan", 0.03)
    assert harness.get_query_cost_usd("trace-1") == pytest.approx(0.08)

    # A cap just above the harness's own total (plus a tiny tier estimate)
    # must allow the call; a cap below it must refuse. Either outcome
    # proves the check reads the harness's live total, not a stale copy.
    with pytest.raises(QueryCapExceededError) as exc_info:
        check_per_query_cap(harness, "trace-1", "guard", query_cap_usd=0.08)
    assert exc_info.value.query_cost_usd == pytest.approx(0.08)


# ---------------------------------------------------------------------------
# Decline messages: no dollar figure or currency symbol, ever.
# ---------------------------------------------------------------------------

_COST_LIKE_NUMBER = re.compile(r"\d+\.\d+")  # a decimal, e.g. "0.10" -- a dollar shape
_CURRENCY_TOKEN = re.compile(r"\$|usd|dollar", re.IGNORECASE)


def _all_decline_and_cap_messages() -> list[str]:
    """Every user-facing string this ticket's decline/note paths can produce."""
    sample_reset = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    return [
        SYSTEM_DAILY_CAP_DECLINE_MESSAGE,
        PER_QUERY_CAP_PARTIAL_RESULT_NOTE,
        user_daily_cap_decline_message(100, sample_reset),
        user_daily_cap_decline_message(0, sample_reset),
        user_daily_cap_decline_message(1, sample_reset),
    ]


@pytest.mark.parametrize("message", _all_decline_and_cap_messages())
def test_decline_messages_have_no_dollar_figure_or_currency_symbol(message: str) -> None:
    assert not _CURRENCY_TOKEN.search(message), f"currency token found in: {message!r}"
    assert not _COST_LIKE_NUMBER.search(message), f"cost-like decimal found in: {message!r}"
    assert "$" not in message


def test_user_daily_cap_decline_message_states_count_and_reset_time() -> None:
    reset_at = datetime(2026, 1, 2, 0, 0, tzinfo=UTC)
    message = user_daily_cap_decline_message(100, reset_at)
    assert "100" in message
    assert "00:00" in message
    assert "UTC" in message


def test_system_daily_cap_decline_message_names_no_technical_cause() -> None:
    # Section 19.5: "no technical cause named beyond 'operating budget'."
    lowered = SYSTEM_DAILY_CAP_DECLINE_MESSAGE.lower()
    for forbidden in ("timeout", "rate limit", "error", "exception", "database"):
        assert forbidden not in lowered


# ---------------------------------------------------------------------------
# check_user_daily_query_cap / check_system_daily_cost_cap: restart-safe,
# read live from the interactions table. Integration tests, real database.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _schema_at_head():
    if not _DB_REACHABLE:
        pytest.skip("search_agent_users PostgreSQL database is not reachable")
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    os.environ.setdefault("USER_DB_URL", USER_DB_URL)
    command.upgrade(cfg, "head")
    yield


@pytest.fixture()
def engine(_schema_at_head):
    eng = sa.create_engine(USER_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    session = Session(bind=engine, future=True)
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _make_user(session: Session) -> User:
    user = User(
        email=f"{uuid.uuid4()}@example.com",
        password_hash="argon2id$v=19$m=65536,t=3,p=4$not-a-real-hash",
    )
    session.add(user)
    session.flush()
    return user


def _make_interaction(
    session: Session,
    user: User,
    *,
    cost_usd: float | None = None,
    created_at: datetime | None = None,
) -> Interaction:
    interaction = Interaction(
        trace_id=str(uuid.uuid4()),
        user_id=user.id,
        query_text="what is BRCA1",
        query_class="lookup",
        route={"layers": ["graph"], "tools": ["cypher_query"], "model_tiers": {}},
        trust_signal="answer",
        rubric_outcome="pass",
        cost_usd=cost_usd,
    )
    session.add(interaction)
    session.flush()
    if created_at is not None:
        # created_at carries a server_default; override it directly for a
        # deterministic "already happened yesterday" or "just now" fixture.
        session.execute(
            sa.update(Interaction)
            .where(Interaction.id == interaction.id)
            .values(created_at=created_at)
        )
        session.flush()
        session.refresh(interaction)
    return interaction


@requires_db
def test_get_user_daily_query_count_counts_only_todays_rows(db_session) -> None:
    user = _make_user(db_session)
    now = datetime(2031, 3, 3, 12, 0, tzinfo=UTC)
    yesterday = now - timedelta(days=1)

    _make_interaction(db_session, user, created_at=now)
    _make_interaction(db_session, user, created_at=now)
    _make_interaction(db_session, user, created_at=yesterday)

    count = get_user_daily_query_count(db_session, user.id, now=now)
    assert count == 2


@requires_db
def test_check_user_daily_query_cap_declines_at_the_cap(db_session) -> None:
    """The "100th+1" case, scaled down to 3 for test speed: a user who has
    already COMPLETED `cap` queries today has their NEXT (cap+1'th) query
    declined; a user who has completed fewer than `cap` is still allowed."""
    user = _make_user(db_session)
    now = datetime(2031, 3, 3, 12, 0, tzinfo=UTC)
    for _ in range(2):
        _make_interaction(db_session, user, created_at=now)

    # 2 completed, cap 3: the 3rd query attempt is still allowed.
    check_user_daily_query_cap(db_session, user.id, cap=3, now=now)

    # A 3rd completed interaction lands (this ticket does not own writing
    # interactions rows; some other component, the Write step, persists
    # one per completed query). Count is now at the cap, so the NEXT
    # (4th) query attempt must be declined.
    _make_interaction(db_session, user, created_at=now)
    with pytest.raises(UserDailyQueryCapExceededError) as exc_info:
        check_user_daily_query_cap(db_session, user.id, cap=3, now=now)

    err = exc_info.value
    assert err.count == 3
    assert err.cap == 3
    assert err.reset_at == datetime(2031, 3, 4, 0, 0, tzinfo=UTC)
    assert "$" not in str(err)


@requires_db
def test_check_user_daily_query_cap_isolated_per_user(db_session) -> None:
    user_a = _make_user(db_session)
    user_b = _make_user(db_session)
    now = datetime(2031, 3, 3, 12, 0, tzinfo=UTC)
    for _ in range(5):
        _make_interaction(db_session, user_a, created_at=now)

    # user_a is over cap, user_b (zero interactions today) is not.
    with pytest.raises(UserDailyQueryCapExceededError):
        check_user_daily_query_cap(db_session, user_a.id, cap=3, now=now)
    check_user_daily_query_cap(db_session, user_b.id, cap=3, now=now)


@requires_db
def test_get_system_daily_cost_usd_sums_only_todays_rows(db_session) -> None:
    user = _make_user(db_session)
    now = datetime(2031, 3, 3, 12, 0, tzinfo=UTC)
    yesterday = now - timedelta(days=1)

    _make_interaction(db_session, user, cost_usd=0.02, created_at=now)
    _make_interaction(db_session, user, cost_usd=0.03, created_at=now)
    _make_interaction(db_session, user, cost_usd=1.00, created_at=yesterday)
    _make_interaction(db_session, user, cost_usd=None, created_at=now)

    total = get_system_daily_cost_usd(db_session, now=now)
    assert total == pytest.approx(0.05)


@requires_db
def test_check_system_daily_cost_cap_declines_at_the_cap(db_session) -> None:
    user = _make_user(db_session)
    now = datetime(2031, 3, 3, 12, 0, tzinfo=UTC)
    _make_interaction(db_session, user, cost_usd=9.99, created_at=now)

    check_system_daily_cost_cap(db_session, cap=10.0, now=now)  # under cap: fine

    _make_interaction(db_session, user, cost_usd=0.02, created_at=now)
    with pytest.raises(SystemDailyCostCapExceededError) as exc_info:
        check_system_daily_cost_cap(db_session, cap=10.0, now=now)
    assert "$" not in str(exc_info.value)
    assert str(exc_info.value) == SYSTEM_DAILY_CAP_DECLINE_MESSAGE


@requires_db
def test_system_and_user_caps_are_restart_safe_via_a_fresh_session(engine) -> None:
    """Simulates a process restart: write interactions, discard every
    in-process reference, then open a brand-new Session on a fresh engine
    connection and confirm the counters reflect the persisted rows rather
    than resetting to zero. There is no in-process counter object carried
    across this boundary at all, which is the restart-safety property
    itself (see the cost_control module docstring).

    Uses the real current time (not the fixed historical `now` the other
    tests in this module use for their rollback-only fixtures) because
    this is the one test in the file that actually commits: a fixed
    shared date would accumulate real, permanent rows across repeated
    suite runs and eventually break the other tests' exact-equality
    assertions, which assume a date nothing else ever commits to."""
    now = datetime.now(UTC)

    setup_session = Session(bind=engine, future=True)
    try:
        user = _make_user(setup_session)
        user_id = user.id
        _make_interaction(setup_session, user, cost_usd=0.04, created_at=now)
        _make_interaction(setup_session, user, cost_usd=0.04, created_at=now)
        setup_session.commit()
    finally:
        setup_session.close()

    # A brand-new session, standing in for a fresh process with no
    # in-memory state left over from the writes above.
    fresh_session = Session(bind=engine, future=True)
    try:
        count = get_user_daily_query_count(fresh_session, user_id, now=now)
        total = get_system_daily_cost_usd(fresh_session, now=now)
        assert count == 2
        assert total >= 0.08  # >= since other tests in this module may share the day
    finally:
        fresh_session.rollback()
        fresh_session.close()


# ---------------------------------------------------------------------------
# build_cost_event_payload: running totals, cap_fraction computed here.
# ---------------------------------------------------------------------------


def test_build_cost_event_payload_shape_and_cap_fraction() -> None:
    harness = Harness(trace_id="trace-1")
    harness.track_cost("trace-1", "guard", 0.02)
    harness.track_cost("trace-1", "plan", 0.03)

    payload = build_cost_event_payload(harness, "trace-1", "plan", query_cap_usd=0.10)

    assert isinstance(payload, CostPayload)
    assert payload.query_cost_usd == pytest.approx(0.05)
    assert payload.query_cap_usd == pytest.approx(0.10)
    assert payload.cap_fraction == pytest.approx(0.5)
    assert payload.model_tier == "plan"


def test_build_cost_event_payload_is_a_running_total_not_a_delta() -> None:
    harness = Harness(trace_id="trace-1")
    harness.track_cost("trace-1", "guard", 0.01)
    first = build_cost_event_payload(harness, "trace-1", "guard", query_cap_usd=1.0)

    harness.track_cost("trace-1", "plan", 0.02)
    second = build_cost_event_payload(harness, "trace-1", "plan", query_cap_usd=1.0)

    assert first.query_cost_usd == pytest.approx(0.01)
    # The second event reflects the FULL running total (0.03), not just the
    # 0.02 delta from the second call alone.
    assert second.query_cost_usd == pytest.approx(0.03)


def test_build_cost_event_payload_validates_against_event_envelope() -> None:
    """The payload this ticket builds must actually satisfy Event's
    model_validator binding `type="cost"` to CostPayload (contracts/events.py)."""
    harness = Harness(trace_id="trace-1")
    harness.track_cost("trace-1", "synth", 0.01)
    payload = build_cost_event_payload(harness, "trace-1", "synth", query_cap_usd=0.10)

    event = Event(
        type="cost",
        version="v1",
        trace_id="trace-1",
        seq=0,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )
    assert event.payload["query_cost_usd"] == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# End-user event filter: cost events never reach an end-user surface.
# ---------------------------------------------------------------------------


def test_is_end_user_visible_event_type_hides_cost() -> None:
    assert is_end_user_visible_event_type("cost") is False


@pytest.mark.parametrize(
    "event_type",
    ["guard", "think", "plan", "tool_start", "tool_result", "token", "citation",
     "trust_signal", "error", "done"],
)
def test_is_end_user_visible_event_type_shows_everything_else(event_type: str) -> None:
    assert is_end_user_visible_event_type(event_type) is True


def test_filter_events_for_end_user_drops_only_cost_events() -> None:
    done_payload = DonePayload(
        total_cost_usd=0.05, total_tool_calls=0, elapsed_ms=10, trust_outcome="answer"
    )
    cost_payload = CostPayload(
        query_cost_usd=0.05, query_cap_usd=0.10, cap_fraction=0.5, model_tier="synth"
    )
    ts = datetime.now(UTC)
    events = [
        Event(type="done", version="v1", trace_id="t", seq=0, ts=ts,
              payload=done_payload.model_dump()),
        Event(type="cost", version="v1", trace_id="t", seq=1, ts=ts,
              payload=cost_payload.model_dump()),
    ]

    filtered = filter_events_for_end_user(events)

    assert len(filtered) == 1
    assert filtered[0].type == "done"
    assert all(event.type != "cost" for event in filtered)
