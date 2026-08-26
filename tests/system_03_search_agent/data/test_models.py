"""Tests for the user-data ORM models: schema shape, CHECK constraints,
unique constraints, delete cascade/set-null behavior, and the
environment-only connection-string discipline.

The CHECK-constraint, unique-constraint, and cascade tests are integration
tests against the real local PostgreSQL `search_agent_users` database, not a
mock: SQLite does not enforce the same CHECK constraint and GIN index
semantics. Those tests skip cleanly (do not fail) when the database is
unreachable, via a connection probe computed once at import time. The
source-hygiene and environment-variable tests below do not touch the
database at all and always run, database or no database.
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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from system_03_search_agent.data import base
from system_03_search_agent.data.models import (
    AuthSession,
    ChatSession,
    CqCandidate,
    Interaction,
    SavedQuery,
    User,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_SRC_DIR = REPO_ROOT / "src" / "system_03_search_agent" / "data"
# Read from the environment, matching the ten sibling test files that already
# do. This file hardcoded the DSN, so on any host whose database needs a
# different one it could not connect and skipped all 25 of its tests silently.
# Found by build phase 4.14's skip guard on CI's fourth run (F-4.14-CI-04),
# where a healthy PostgreSQL service was running and every other
# database-backed test passed against it.
USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")


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
# Source hygiene and environment-variable discipline. No database needed.
# ---------------------------------------------------------------------------


def test_data_module_has_no_graph_references():
    """No module under data/ may reference the AGE graph, its role, or its database."""
    forbidden_terms = ("ncbi_kg", "kg_reader", "apache_age", "cypher_query")
    for path in sorted(DATA_SRC_DIR.glob("*.py")):
        content = path.read_text().lower()
        for term in forbidden_terms:
            assert term not in content, f"{path.name} references forbidden term {term!r}"


def test_data_module_has_no_hardcoded_credentialed_connection_string():
    """No module under data/ may embed a connection string carrying a user:pass@ literal."""
    credentialed_url = re.compile(r"://[^/\s'\"]+:[^/\s@'\"]+@")
    for path in sorted(DATA_SRC_DIR.glob("*.py")):
        content = path.read_text()
        assert not credentialed_url.search(content), (
            f"{path.name} appears to hardcode a credentialed connection string"
        )


def test_get_user_db_url_reads_from_environment(monkeypatch):
    monkeypatch.setenv("USER_DB_URL", USER_DB_URL)
    assert base.get_user_db_url() == USER_DB_URL


def test_get_user_db_url_missing_raises_without_fallback(monkeypatch):
    monkeypatch.delenv("USER_DB_URL", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        base.get_user_db_url()
    # The error names the missing variable; it must never contain a URL value,
    # since there is none to leak, and it must actually mention what to set.
    assert "USER_DB_URL" in str(exc_info.value)


def test_create_user_db_engine_missing_env_raises(monkeypatch):
    monkeypatch.delenv("USER_DB_URL", raising=False)
    with pytest.raises(RuntimeError):
        base.create_user_db_engine()


# ---------------------------------------------------------------------------
# Schema shape, CHECK constraints, unique constraints, delete behavior.
# Requires the real local PostgreSQL database.
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


def _make_user(session: Session, email: str | None = None) -> User:
    user = User(
        email=email or f"{uuid.uuid4()}@example.com",
        password_hash="argon2id$v=19$m=65536,t=3,p=4$not-a-real-hash",
    )
    session.add(user)
    session.flush()
    return user


def _make_interaction(
    session: Session,
    user: User,
    *,
    trace_id: str | None = None,
    session_id: uuid.UUID | None = None,
    query_class: str = "lookup",
    trust_signal: str = "answer",
    rubric_outcome: str = "pass",
    rubric_score: int | None = None,
) -> Interaction:
    interaction = Interaction(
        trace_id=trace_id or str(uuid.uuid4()),
        user_id=user.id,
        session_id=session_id,
        query_text="what is BRCA1",
        query_class=query_class,
        route={"layers": ["graph"], "tools": ["cypher_query"], "model_tiers": {}},
        trust_signal=trust_signal,
        rubric_outcome=rubric_outcome,
        rubric_score=rubric_score,
    )
    session.add(interaction)
    return interaction


@requires_db
def test_user_round_trip_defaults(db_session):
    user = _make_user(db_session)
    db_session.flush()
    assert user.id is not None
    assert user.created_at is not None
    assert user.profile == {}
    assert user.last_login_at is None


@requires_db
def test_duplicate_email_rejected(db_session):
    email = f"{uuid.uuid4()}@example.com"
    _make_user(db_session, email=email)
    db_session.flush()

    dup = User(email=email, password_hash="another-hash")
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
def test_duplicate_trace_id_rejected(db_session):
    user = _make_user(db_session)
    trace_id = str(uuid.uuid4())
    _make_interaction(db_session, user, trace_id=trace_id)
    db_session.flush()

    _make_interaction(db_session, user, trace_id=trace_id)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
@pytest.mark.parametrize("bad_query_class", ["not_a_real_class", "", "LOOKUP"])
def test_interactions_query_class_check(db_session, bad_query_class):
    user = _make_user(db_session)
    _make_interaction(db_session, user, query_class=bad_query_class)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
def test_interactions_trust_signal_check(db_session):
    user = _make_user(db_session)
    _make_interaction(db_session, user, trust_signal="not_a_signal")
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
def test_interactions_rubric_outcome_check(db_session):
    user = _make_user(db_session)
    _make_interaction(db_session, user, rubric_outcome="not_an_outcome")
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
def test_interactions_rubric_score_out_of_range_rejected(db_session):
    user = _make_user(db_session)
    _make_interaction(db_session, user, rubric_score=17)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
def test_interactions_rubric_score_null_passes_check(db_session):
    """rubric_score is nullable; NULL must satisfy the CHECK, not violate it."""
    user = _make_user(db_session)
    interaction = _make_interaction(db_session, user, rubric_score=None)
    db_session.flush()
    assert interaction.rubric_score is None


@requires_db
def test_interactions_rubric_score_boundary_values_accepted(db_session):
    user = _make_user(db_session)
    low = _make_interaction(db_session, user, rubric_score=0)
    high = _make_interaction(db_session, user, rubric_score=16)
    db_session.flush()
    assert low.rubric_score == 0
    assert high.rubric_score == 16


@requires_db
def test_cq_candidates_status_check(db_session):
    bad = CqCandidate(representative_query="q", status="not_a_status")
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
def test_cq_candidates_default_status_is_proposed(db_session):
    candidate = CqCandidate(representative_query="what is the pathogen behind outbreak X")
    db_session.add(candidate)
    db_session.flush()
    assert candidate.status == "proposed"


@requires_db
def test_cq_candidates_wedge_type_check(db_session):
    bad = CqCandidate(representative_query="q", wedge_type="not_a_wedge_type")
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
def test_cq_candidates_moat_rank_check(db_session):
    bad = CqCandidate(representative_query="q", moat_rank="not_a_rank")
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
def test_cq_candidates_review_decision_check(db_session):
    bad = CqCandidate(representative_query="q", review_decision="not_a_decision")
    db_session.add(bad)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@requires_db
def test_delete_user_cascades_auth_sessions_and_saved_queries(db_session):
    user = _make_user(db_session)

    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash="sha256:not-a-real-hash",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(auth_session)
    db_session.flush()
    auth_session_id = auth_session.id

    saved = SavedQuery(user_id=user.id, query_text="BRCA1 pathogenic variants")
    db_session.add(saved)
    db_session.flush()
    saved_id = saved.id

    db_session.delete(user)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(AuthSession, auth_session_id) is None
    assert db_session.get(SavedQuery, saved_id) is None


@requires_db
def test_delete_user_sets_null_on_sessions_and_interactions(db_session):
    user = _make_user(db_session)

    chat_session = ChatSession(user_id=user.id)
    db_session.add(chat_session)
    db_session.flush()
    session_id = chat_session.id

    interaction = _make_interaction(db_session, user, session_id=session_id)
    db_session.flush()
    interaction_id = interaction.id

    db_session.delete(user)
    db_session.flush()
    db_session.expire_all()

    persisted_session = db_session.get(ChatSession, session_id)
    persisted_interaction = db_session.get(Interaction, interaction_id)

    assert persisted_session is not None
    assert persisted_session.user_id is None
    assert persisted_interaction is not None
    assert persisted_interaction.user_id is None
    # The row itself must still exist, only the FK is nulled.
    assert persisted_interaction.trace_id == interaction.trace_id


@requires_db
def test_delete_interaction_sets_null_on_saved_query_last_run(db_session):
    user = _make_user(db_session)
    interaction = _make_interaction(db_session, user)
    db_session.flush()

    saved = SavedQuery(
        user_id=user.id,
        query_text="BRCA1 pathogenic variants",
        last_run_interaction_id=interaction.id,
    )
    db_session.add(saved)
    db_session.flush()
    saved_id = saved.id

    db_session.delete(interaction)
    db_session.flush()
    db_session.expire_all()

    persisted_saved = db_session.get(SavedQuery, saved_id)
    assert persisted_saved is not None
    assert persisted_saved.last_run_interaction_id is None
