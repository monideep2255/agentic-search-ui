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
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

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
    is_operator_user,
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
# F-2.0-09 (adversary, confirmed high, 2026-07-28): a cap env var set to
# "inf"/"nan"/a non-positive number must be rejected at read time, never
# silently accepted. "inf" disables the cap outright (nothing is ever
# greater than infinity) while still reporting cap_fraction=0.0 forever;
# "nan" makes every comparison against it False, so the cap silently
# never fires.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["inf", "-inf", "nan", "1e400", "0", "-1", "-0.5"])
def test_per_query_cost_cap_usd_rejects_non_finite_and_non_positive(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", value)
    with pytest.raises(RuntimeError, match="PER_QUERY_COST_CAP_USD"):
        per_query_cost_cap_usd()


@pytest.mark.parametrize("value", ["inf", "-inf", "nan", "0"])
def test_system_daily_cap_usd_rejects_non_finite_and_non_positive(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", value)
    with pytest.raises(RuntimeError, match="SYSTEM_DAILY_CAP_USD"):
        system_daily_cap_usd()


@pytest.mark.parametrize("value", ["0", "-1", "-100"])
def test_per_user_daily_query_cap_rejects_non_positive(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", value)
    with pytest.raises(RuntimeError, match="PER_USER_DAILY_QUERY_CAP"):
        per_user_daily_query_cap()


def test_per_query_cost_cap_usd_still_accepts_a_normal_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "0.10")
    assert per_query_cost_cap_usd() == pytest.approx(0.10)


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


# ---------------------------------------------------------------------------
# is_operator_user: the OPERATOR_USER_IDS allowlist (Section 19.4). A
# security review of the operator_mode wiring flagged that honoring a
# client-supplied flag with no server-side check is an authorization
# bypass; these tests cover the allowlist gate itself, independent of the
# endpoint that calls it.
# ---------------------------------------------------------------------------


def test_is_operator_user_false_when_allowlist_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPERATOR_USER_IDS", raising=False)
    assert is_operator_user("11111111-1111-1111-1111-111111111111") is False


def test_is_operator_user_false_when_user_id_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPERATOR_USER_IDS", "11111111-1111-1111-1111-111111111111")
    assert is_operator_user(None) is False


def test_is_operator_user_true_for_an_allowlisted_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "OPERATOR_USER_IDS",
        "11111111-1111-1111-1111-111111111111,22222222-2222-2222-2222-222222222222",
    )
    assert is_operator_user("22222222-2222-2222-2222-222222222222") is True


def test_is_operator_user_false_for_a_non_allowlisted_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPERATOR_USER_IDS", "11111111-1111-1111-1111-111111111111")
    assert is_operator_user("99999999-9999-9999-9999-999999999999") is False


def test_is_operator_user_tolerates_whitespace_around_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "OPERATOR_USER_IDS", " 11111111-1111-1111-1111-111111111111 , 22222222-2222-2222-2222-222222222222"
    )
    assert is_operator_user("22222222-2222-2222-2222-222222222222") is True


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


# ---------------------------------------------------------------------------
# F-2.0-05 (judge, filed 2026-07-28; resolved by product-owner decision the
# same day: cost and token usage are internal-only data). filter_events_for_
# end_user must redact done.total_cost_usd to 0.0, never merely pass a real
# dollar figure through to an end-user-facing adapter.
# ---------------------------------------------------------------------------


def test_filter_events_for_end_user_redacts_done_total_cost_usd() -> None:
    done_payload = DonePayload(
        total_cost_usd=0.0512, total_tool_calls=2, elapsed_ms=340, trust_outcome="answer"
    )
    original = Event(
        type="done", version="v1", trace_id="t", seq=0, ts=datetime.now(UTC),
        payload=done_payload.model_dump(),
    )

    filtered = filter_events_for_end_user([original])

    assert len(filtered) == 1
    redacted = filtered[0]
    assert redacted.payload["total_cost_usd"] == 0.0
    # Every other done field survives untouched.
    assert redacted.payload["total_tool_calls"] == 2
    assert redacted.payload["elapsed_ms"] == 340
    assert redacted.payload["trust_outcome"] == "answer"
    # The original Event, e.g. still held by an internal/operator caller,
    # is never mutated: Event and DonePayload are immutable Pydantic
    # models, so this also holds by construction, not just by convention.
    assert original.payload["total_cost_usd"] == 0.0512


def test_filter_events_for_end_user_redaction_produces_a_schema_valid_done_event() -> None:
    done_payload = DonePayload(
        total_cost_usd=1.23, total_tool_calls=0, elapsed_ms=1, trust_outcome="refuse"
    )
    original = Event(
        type="done", version="v1", trace_id="t", seq=0, ts=datetime.now(UTC),
        payload=done_payload.model_dump(),
    )

    redacted = filter_events_for_end_user([original])[0]

    # Constructing a fresh Event from the redacted payload must not raise:
    # the redaction produces a payload that still validates against
    # DonePayload, it does not merely delete or null out a required field.
    DonePayload.model_validate(redacted.payload)


class TestTheTwoAnonymousCeilingsBoundSpendTogether:
    """F-4.10-R-11 (lead, verifying the F-4.10-R-01 fix).

    Neither anonymous ceiling bounds spend alone. The per-guest attempt
    ceiling stops one identity; the shared daily ceiling stops the day. They
    only work together, and only while the first is materially smaller than
    the second. Raise `ATTEMPT_ALLOWANCE` above the shipped
    `ANON_DAILY_RUN_CAP`, or drop that cap near it, and one guest token takes
    the whole day again, which is precisely the denial of service R-01
    measured at 200 pipelines in 1.68 seconds.

    Nothing tested that relationship, and the premise gate structurally
    could not: its attack clause imports `ATTEMPT_ALLOWANCE` and scales its
    own daily cap to four times whatever it finds, so it proves a bound
    EXISTS while staying blind to both values. Changing the constant from 10
    to 40 left all 32 of its clauses green.

    That is the trap the premise gate's own header warns about, in its
    `_EXPECTED_FREE_SEARCHES` comment: "a gate that reads its expected value
    out of the code it grades cannot catch that value being wrong." The gate
    stated the principle and then imported the next constant one screen
    later.

    Why this is a test over the SHIPPED defaults rather than a check inside
    `anon_daily_run_cap()`, which is where it was first written: enforcing
    the ratio at read time makes the daily ceiling untestable, because every
    clause that exercises it sets a deliberately tiny cap so the boundary is
    reachable in a few requests. That version turned 7 legitimate tests red.
    A control that forces the tests exercising a bound to stop exercising it
    is a bad control, whatever it catches.

    Stated cost of the choice, so nobody reads this as stronger than it is:
    this catches the shipped defaults drifting, not an operator setting a
    bad value in a real `.env`. Closing that needs a startup-time config
    validation this service does not have. Carried in `tracker/phase_4.10.md`.
    """

    def test_the_shipped_default_daily_cap_dwarfs_the_per_guest_attempt_ceiling(self) -> None:
        import re
        from pathlib import Path

        from system_03_search_agent.data.guest_sessions import ATTEMPT_ALLOWANCE
        from system_03_search_agent.harness.cost_control import (
            _MIN_ANON_DAILY_CAP_MULTIPLE,
        )

        env_example = Path(__file__).resolve().parents[3] / "env.example"
        match = re.search(r"^ANON_DAILY_RUN_CAP=(\d+)$", env_example.read_text(), re.MULTILINE)
        assert match is not None, (
            "env.example must ship a concrete ANON_DAILY_RUN_CAP; it is the only "
            "bound on total anonymous spend, and an empty value means the app "
            "refuses every anonymous run rather than bounding it"
        )
        shipped_cap = int(match.group(1))

        assert shipped_cap >= ATTEMPT_ALLOWANCE * _MIN_ANON_DAILY_CAP_MULTIPLE, (
            f"the shipped ANON_DAILY_RUN_CAP ({shipped_cap}) is less than "
            f"{_MIN_ANON_DAILY_CAP_MULTIPLE}x the per-guest attempt ceiling "
            f"({ATTEMPT_ALLOWANCE}), so one anonymous caller could take "
            f"{ATTEMPT_ALLOWANCE / shipped_cap:.0%} of the day's whole budget "
            f"and deny the product to everyone else (F-4.10-R-01). Raise the "
            f"cap, or lower ATTEMPT_ALLOWANCE."
        )


class TestTheAnonymousSourceShareIsMateriallyBelowTheDay:
    """F-4.10-V-01 (verifier, grading the F-4.10-R-01 fix).

    The ratio invariant, one bound further out than
    `TestTheTwoAnonymousCeilingsBoundSpendTogether` above, and for the same
    reason that class exists: a bound whose value is not materially below
    the thing it subdivides is not a bound at all, and nothing in a
    behavioural gate notices, because the code still refuses at SOME number.

    The measured failure this pins. `ATTEMPT_ALLOWANCE` bounds an identity
    and `POST /auth/guest` mints identities for free; the daily ceiling
    bounds the day and says nothing about who spent it; the mint throttle
    bounds the RATE of minting at 60 per minute per source and cannot go
    lower, because the premise gate's own admit arm requires 25 consecutive
    mints from one shared address to succeed. With all three live and the
    throttle refusing nothing, 20 identities from ONE source took all 200 of
    the day's runs in 1.84 seconds. `anon_daily_source_share` is what bounds
    that, and it only bounds it while it stays a small fraction of the cap.

    Both directions are asserted, because this control has no safe direction
    of failure either. A share that creeps up toward the cap stops bounding
    a caller; a share that drops toward zero refuses an ordinary shared
    address, which is the exact failure the mint throttle's first version
    shipped (F-4.10-04) and the reason every control in this phase is graded
    on two arms.

    COVERAGE, per `goal-contracts`. Exercised: the shipped `env.example`
    value, the share's arithmetic at that value, the floor at a cap small
    enough to divide to zero, and the input validation. NOT exercised here:
    that the share is actually ENFORCED, which is
    `TestOneSourceCannotTakeTheWholeAnonymousDay` in the premise gate and is
    named rather than duplicated; and an operator setting a bad
    `ANON_DAILY_RUN_CAP` in a real `.env`, which needs the startup-time
    config validation this service does not have and which
    `TestTheTwoAnonymousCeilingsBoundSpendTogether` already carries.
    """

    @staticmethod
    def _shipped_cap() -> int:
        import re
        from pathlib import Path

        env_example = Path(__file__).resolve().parents[3] / "env.example"
        match = re.search(r"^ANON_DAILY_RUN_CAP=(\d+)$", env_example.read_text(), re.MULTILINE)
        assert match is not None, (
            "env.example must ship a concrete ANON_DAILY_RUN_CAP; the source "
            "share is derived from it, so an absent value leaves no bound to "
            "derive"
        )
        return int(match.group(1))

    def test_one_source_cannot_take_a_material_fraction_of_the_shipped_day(self) -> None:
        from system_03_search_agent.harness.cost_control import anon_daily_source_share

        shipped_cap = self._shipped_cap()
        share = anon_daily_source_share(shipped_cap)

        assert share * 4 <= shipped_cap, (
            f"one source may take {share} of the shipped {shipped_cap}-run day "
            f"({share / shipped_cap:.0%}), which is not materially below the day "
            f"and therefore not a bound on one caller (F-4.10-V-01). At this "
            f"ratio a handful of sources, or one source across a fixed-window "
            f"boundary, is the whole day again."
        )

    def test_the_shipped_share_still_serves_several_whole_visitors(self) -> None:
        """The admit arm of the same invariant.

        A share below one visitor's answer allowance would refuse the second
        person behind an office address, which is a control that has
        destroyed the product to protect it. Five is the floor; the shipped
        value must clear it with room for more than one visitor, because the
        shared-address case is the ordinary case, not the attack.
        """
        from system_03_search_agent.data.guest_sessions import FREE_RUN_ALLOWANCE
        from system_03_search_agent.harness.cost_control import anon_daily_source_share

        shipped_cap = self._shipped_cap()
        share = anon_daily_source_share(shipped_cap)

        assert share >= FREE_RUN_ALLOWANCE * 2, (
            f"the shipped source share is {share}, under two complete visitors "
            f"at {FREE_RUN_ALLOWANCE} answers each; several people behind one "
            f"office, campus or conference address is the ordinary case and is "
            f"the room this product gets demonstrated in (F-4.10-04's lesson, "
            f"one bound further out)"
        )

    def test_the_share_is_a_tenth_of_the_cap_at_the_shipped_value(self) -> None:
        """The arithmetic itself, stated as the gate's own expectation
        rather than recomputed from the constants it grades.

        `TestTheTwoAnonymousCeilingsBoundSpendTogether` above records why
        that matters: the premise gate imported `ATTEMPT_ALLOWANCE` and
        scaled its own cap to it, so changing the constant from 10 to 40 left
        all 32 of its clauses green. Writing 20 here means changing the
        divisor is a red test rather than a silently rescaled one.
        """
        from system_03_search_agent.harness.cost_control import anon_daily_source_share

        assert anon_daily_source_share(200) == 20
        assert anon_daily_source_share(1000) == 100

    def test_a_small_configured_cap_never_divides_the_share_to_zero(self) -> None:
        """The floor, and the failure it exists to stop.

        A share of zero refuses EVERY anonymous caller whose source is
        known, which scores perfectly against every attack test that will
        ever be written and destroys the phase's entire deliverable. Small
        caps are not hypothetical: every clause in the premise gate that
        exercises the daily ceiling sets one deliberately, so this is the
        configuration the test suite itself runs in most often.
        """
        from system_03_search_agent.harness.cost_control import anon_daily_source_share

        for tiny_cap in (1, 2, 3, 9):
            assert anon_daily_source_share(tiny_cap) >= 1, (
                f"a cap of {tiny_cap} produced a source share of "
                f"{anon_daily_source_share(tiny_cap)}; a share of zero refuses "
                f"every anonymous caller whose source is known"
            )

    @pytest.mark.parametrize("bad_cap", [0, -1, -200])
    def test_a_non_positive_cap_is_rejected_rather_than_silently_bounded(
        self, bad_cap: int
    ) -> None:
        from system_03_search_agent.harness.cost_control import anon_daily_source_share

        with pytest.raises(ValueError):
            anon_daily_source_share(bad_cap)

    @pytest.mark.parametrize("bad_cap", [True, 1.5, "200", None])
    def test_a_non_int_cap_is_rejected(self, bad_cap: object) -> None:
        """`True` is in this list deliberately: `isinstance(True, int)` is
        True in Python, so a bool would otherwise sail through and produce a
        share of 5 from a value that is not a cap at all."""
        from system_03_search_agent.harness.cost_control import anon_daily_source_share

        with pytest.raises(TypeError):
            anon_daily_source_share(bad_cap)  # type: ignore[arg-type]
