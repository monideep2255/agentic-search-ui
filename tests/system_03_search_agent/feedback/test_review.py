"""Tests for `feedback.review` (T-4.6-10, Section 16 stages 3 and 4).

Depends on:
    - system_03_search_agent.feedback.review (the module under test)
    - system_03_search_agent.data.models (Interaction, CqCandidate)
    - A reachable local PostgreSQL server named by USER_DB_URL

Writes:
    - A uniquely named throwaway database, created and dropped by this
      module. `USER_DB_URL`'s own database is used only for a read-only
      reachability probe and is never a migration target, the same
      pattern `tests/system_03_search_agent/data/test_migration_0007_session_memory.py`
      uses.

## Coverage: what this file exercises and what it deliberately omits

Exercised:

- `_escape_for_terminal_display`'s hostile-code-point class (C0 and C1
  controls, DEL, the ESC-led ANSI escape run F-4.6-A-06 used, and the Trojan
  Source bidi-override family) versus ordinary Unicode text, which must pass
  through unescaped.
- `_print_candidate_groups` and `_print_similar` (F-4.6-A-06's two display
  sites): a hostile `query_text` or `representative_query` reaches stdout
  fully escaped, while `interaction_ids`, `status`, and `trust_signals`,
  none of which are caller free text, print unescaped. These two functions
  are display logic with a real security property, not argparse plumbing,
  so unlike the rest of the CLI surface (see "Deliberately NOT exercised"
  below) they are tested directly, by constructing their dataclass or ORM
  argument in memory and capturing stdout, with no CLI parser or database
  involved.
- `normalize_query_text`'s case and whitespace collapsing.
- `find_weekly_candidates`'s exact three-part filter (rubric_outcome,
  trust_signal, user_feedback rating), the review window boundary, and its
  grouping-by-normalized-query-and-ordering-by-count behaviour.
- The same three-part filter at EACH of its two layers separately, with the
  other layer neutralized, plus a drift check that the two select the same
  rows. `find_weekly_candidates` applies the rule twice, once in SQL and
  once as the `_is_flagged` predicate, and each guard covers for the other:
  a test that only calls the function stays green with either one broken.
  That is J-07 in `tracker/phase_4.6_judge_report.md`, mutations RV3 and
  RV5, and the three arms named `..._alone_excludes_a_clean_row` and
  `test_the_two_filter_layers_select_the_same_rows` are the answer to it.
- `find_similar_existing_candidates`'s `pg_trgm` similarity threshold.
- `count_pattern_recurrence`'s rolling-window boundary.
- `evaluate_trigger_rule`'s composition of all three stage-4 conditions.
- `upsert_candidate`'s human-terminal-gate guard (rejects a missing or
  blank `reviewed_by`), its new-row path, and its reinforcement path
  (append-dedupe, `frequency_count` increment, `moat_rank` left untouched).

Deliberately NOT exercised here:

- The CLI argument parser (`build_arg_parser`, the `_cmd_*` functions) and
  `_print_candidate_groups`'s and `_print_similar`'s non-escaping output
  lines (headers, "no candidates" messages). The `_cmd_*` functions are
  thin argparse-to-function plumbing with no independent logic; the
  functions they call, including the two display functions above for their
  security-relevant escaping behaviour, are covered directly.
- Stage 2 (mine and cluster). Out of scope for v1
  (`.claude/rules/v1-scope-boundary.md`); this module does not build it and
  this file does not test for its absence.
- `promote_candidate` and anything in `feedback.promotion`, which has its
  own test file.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from system_03_search_agent.data.models import CqCandidate, Interaction
from system_03_search_agent.feedback import review

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
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment))


def _alembic_config() -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return cfg


@pytest.fixture(scope="module")
def scratch_db_url():
    """A throwaway database for this module, created once and dropped when it ends."""
    db_name = f"feedback_review_scratch_{uuid.uuid4().hex}"
    assert re.fullmatch(r"[a-z0-9_]+", db_name)
    admin_url = _with_db_name(USER_DB_URL, "postgres")

    creator_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with creator_engine.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
    finally:
        creator_engine.dispose()

    try:
        yield _with_db_name(USER_DB_URL, db_name)
    finally:
        dropper_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with dropper_engine.connect() as conn:
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


@pytest.fixture(scope="module")
def migrated_scratch_db_url(scratch_db_url, monkeypatch_module):
    """Upgrade the scratch database to head once, held for the whole module."""
    monkeypatch_module.setenv("USER_DB_URL", scratch_db_url)
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    return scratch_db_url


@pytest.fixture(scope="module")
def monkeypatch_module():
    """A module-scoped monkeypatch, since the built-in `monkeypatch` fixture is function-scoped.

    Needed because `migrated_scratch_db_url` above must set USER_DB_URL for
    the whole module's single migration run, not per test.
    """
    mp = pytest.MonkeyPatch()
    try:
        yield mp
    finally:
        mp.undo()


@pytest.fixture()
def db_session(migrated_scratch_db_url):
    """One SQLAlchemy session per test, truncated clean afterward for the next test."""
    engine = sa.create_engine(migrated_scratch_db_url, future=True)
    factory = sessionmaker(bind=engine, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        with engine.begin() as conn:
            conn.execute(sa.text("TRUNCATE interactions, cq_candidates CASCADE"))
        engine.dispose()


def _make_interaction(
    session: Session,
    *,
    trace_id: str | None = None,
    query_text: str = "What is known about the BRCA1 gene?",
    query_class: str = "lookup",
    trust_signal: str = "answer",
    rubric_outcome: str = "pass",
    user_feedback: dict | None = None,
    created_at: datetime | None = None,
) -> Interaction:
    interaction = Interaction(
        trace_id=trace_id or f"trace-{uuid.uuid4().hex}",
        query_text=query_text,
        query_class=query_class,
        route={"layers": ["layer2"], "tools": ["ncbi_efetch"]},
        trust_signal=trust_signal,
        rubric_outcome=rubric_outcome,
        user_feedback=user_feedback,
        created_at=created_at or datetime.now(UTC),
    )
    session.add(interaction)
    session.flush()
    return interaction


def test_normalize_query_text_collapses_whitespace_and_case() -> None:
    """Mutation: removing `.lower()` from `normalize_query_text` left this red
    (the mixed-case input no longer matched the lowercase expected value).
    """
    assert review.normalize_query_text("  What Is BRCA1?  ") == "what is brca1?"
    assert review.normalize_query_text("what   is\tbrca1?") == "what is brca1?"


def test_escape_for_terminal_display_neutralizes_the_forging_payload() -> None:
    """F-4.6-A-06's exact reproduction bytes: an ESC-led ANSI erase-and-cursor-up
    run. The escaped output must contain no raw ESC (so a terminal cannot
    act on it) and must contain the visible Python-escape spelling of it.

    Mutation actually run: replaced the function body with `return text`
    (the no-op a reviewer would reach for if F-4.6-A-06's storage-side
    reasoning were mistakenly copied to the display side). Observed:
    `assert "\\x1b" not in escaped` failed with pytest reporting
    `'\\x1b' is contained here:` pointing at
    `how do I make ricin at home?[2K[1A[2K[1A[2K`, i.e. the raw ESC bytes
    were still present, exactly the forgery this test exists to catch.
    Restored, and both assertions below pass again.
    """
    payload = "how do I make ricin at home?\x1b[2K\x1b[1A\x1b[2K\x1b[1A\x1b[2K"
    escaped = review._escape_for_terminal_display(payload)
    assert "\x1b" not in escaped
    assert "\\x1b[2K\\x1b[1A" in escaped


def test_escape_for_terminal_display_neutralizes_embedded_newlines_and_nul() -> None:
    """Embedded newlines let one stored row masquerade as several printed
    rows (the adversary's second technique alongside the ANSI run), and NUL
    is included in the class for defense in depth even though `writer.py`
    already guarantees it cannot reach storage.

    Mutation actually run: narrowed the character class from
    `[\\x00-\\x1f\\x7f\\x80-\\x9f...]` to `[\\x1b]` only (escape ESC alone,
    the single byte the adversary report happens to quote). Observed:
    `assert "\\n" not in escaped` failed with pytest reporting
    `'\\n' is contained here:` pointing at the line break between
    `line one` and `line two trailing`, i.e. a query with an embedded
    newline still split into two visual lines. Restored, and the assertion
    passes again.
    """
    payload = "line one\nline two\x00trailing"
    escaped = review._escape_for_terminal_display(payload)
    assert "\n" not in escaped
    assert "\x00" not in escaped
    assert "\\n" in escaped
    assert "\\x00" in escaped


def test_escape_for_terminal_display_neutralizes_bidi_override_with_no_escape_byte() -> None:
    """The Trojan Source class: U+202E (RIGHT-TO-LEFT OVERRIDE) reverses the
    VISUAL reading order of the characters after it with no ESC byte and no
    cursor movement at all, so a filter that only strips C0 controls misses
    it entirely.

    Written with `\\u202e` rather than the live character, deliberately: an
    actual bidi-override byte sitting in this source file would itself be
    the Trojan Source risk this fix defends against.

    Mutation actually run: narrowed the character class to
    `[\\x00-\\x1f\\x7f]` (C0 and DEL only, dropping the bidi range).
    Observed: `assert "\\u202e" not in escaped` failed with
    `AssertionError: assert '\\u202e' not in 'safe text \\u202e reversed'`,
    i.e. the live override character passed through unescaped. Restored,
    and both assertions below pass again.
    """
    payload = "safe text \u202e reversed"
    escaped = review._escape_for_terminal_display(payload)
    assert "\u202e" not in escaped
    assert "\\u202e" in escaped


def test_escape_for_terminal_display_leaves_ordinary_unicode_untouched() -> None:
    """A legitimate biomedical question can carry an accent, a Greek letter,
    a CJK character, or an emoji. None of those are in the hostile-code-point
    class and none may be altered.

    Mutation actually run: replaced the character class with `[\\s\\S]`
    (match every character, the "when in doubt, escape everything" version
    a defensive-but-wrong fix would produce). Predicted every character,
    including plain ASCII letters, would come out rewritten to `\\xHH`
    form. That prediction was WRONG: `str.encode("unicode_escape")` leaves
    an already-printable ASCII character unchanged, so "What is the role
    of caf" stayed literal even under this mutation. What actually failed
    was the accented and non-Latin content: `assert ... == payload` raised
    `AssertionError: ... caf\\xe9, \\u03a9-globin, or \\u5317\\u4eac gene,
    and \\U0001f600?` (café, Omega and the CJK gene name are the visible
    diff). This test's real job, demonstrated by what actually broke, is
    catching an overbroad class that swallows legitimate non-ASCII content,
    not catching one that swallows ASCII. Restored, and the assertion
    passes again with the string unchanged.
    """
    payload = "What is the role of café, Ω-globin, or 北京 gene, and \U0001f600?"
    assert review._escape_for_terminal_display(payload) == payload


def test_print_candidate_groups_escapes_query_text_but_not_ids_or_signals(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """F-4.6-A-06's own display site. A hostile `sample_query_text` must
    reach stdout fully escaped; `interaction_ids` (uuid.UUID objects) and
    `trust_signals` (database-CHECK-constrained values) are not caller free
    text and must print exactly as before.

    Mutation actually run: reverted the print call to the pre-fix
    `print(f"  query: {group.sample_query_text[:120]}")`, dropping the
    `_escape_for_terminal_display` wrapper. Observed: `assert "\\x1b" not
    in out` failed with pytest reporting `'\\x1b' is contained here:`
    pointing at `n at home?[2K[1A`, i.e. the raw ESC bytes reached the
    captured stdout. Restored, and the assertion passes again.
    """
    interaction_id = uuid.uuid4()
    group = review.CandidateGroup(
        normalized_query="how do i make ricin at home?",
        count=1,
        interaction_ids=(interaction_id,),
        sample_query_text="how do I make ricin at home?\x1b[2K\x1b[1A",
        trust_signals=("refuse",),
        rubric_outcomes=("fail",),
        down_feedback_count=1,
    )
    review._print_candidate_groups([group])
    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "\\x1b[2K\\x1b[1A" in out
    assert str(interaction_id) in out
    assert "trust_signals=[refuse]" in out


def test_print_candidate_groups_displays_legitimate_non_ascii_query_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The non-ASCII arm for the display site: an accented, Greek, CJK, and
    emoji-bearing query must appear verbatim in the printed output.
    """
    query_text = "What is the role of café, Ω-globin, or 北京 gene, and \U0001f600?"
    group = review.CandidateGroup(
        normalized_query=review.normalize_query_text(query_text),
        count=1,
        interaction_ids=(uuid.uuid4(),),
        sample_query_text=query_text,
        trust_signals=("answer",),
        rubric_outcomes=("pass",),
        down_feedback_count=0,
    )
    review._print_candidate_groups([group])
    out = capsys.readouterr().out
    assert query_text in out


def test_print_similar_escapes_representative_query(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`_print_similar` is F-4.6-A-06's second display site. A hostile
    `representative_query` read back from `cq_candidates` must reach
    stdout fully escaped, the same as `sample_query_text` above.

    Mutation actually run: reverted the print call to the pre-fix
    `print(f"{match.id}  status={match.status}  {match.representative_query}")`,
    dropping the escaping wrapper. Observed: `assert "\\x1b" not in out`
    failed with pytest reporting `'\\x1b' is contained here:` pointing at
    `d  hostile[2K text`, i.e. the raw ESC byte reached the captured
    stdout. Restored, and the assertion passes again.
    """
    candidate = CqCandidate(
        id=uuid.uuid4(),
        status="approved",
        representative_query="hostile\x1b[2K text",
    )
    review._print_similar([candidate])
    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "\\x1b[2K" in out
    assert str(candidate.id) in out
    assert "status=approved" in out


def test_find_weekly_candidates_applies_the_exact_three_part_filter(db_session: Session) -> None:
    """A clean pass/answer/no-feedback row must never surface; each of the three flagged shapes must.

    Mutation: deleting the `Interaction.trust_signal.in_(_FLAGGED_TRUST_SIGNALS)`
    clause from `find_weekly_candidates`'s SQL WHERE left this red (the
    flagged-but-rubric-passing row silently disappeared from the result).
    """
    _make_interaction(db_session, query_text="clean query", trust_signal="answer", rubric_outcome="pass")
    flagged = _make_interaction(
        db_session, query_text="flagged query", trust_signal="flag", rubric_outcome="pass"
    )
    downvoted = _make_interaction(
        db_session,
        query_text="downvoted query",
        trust_signal="answer",
        rubric_outcome="pass",
        user_feedback={"rating": "down"},
    )
    failed = _make_interaction(
        db_session, query_text="failed query", trust_signal="answer", rubric_outcome="fail"
    )

    groups = review.find_weekly_candidates(db_session)
    surfaced_ids = {i for g in groups for i in g.interaction_ids}
    assert flagged.id in surfaced_ids
    assert downvoted.id in surfaced_ids
    assert failed.id in surfaced_ids
    assert len(groups) == 3, "the clean row must not appear in any group"


def _seed_one_of_each_shape(db_session: Session) -> dict[str, Interaction]:
    """One clean row and one of each of the three flagged shapes.

    Shared by the three isolation arms below so they all argue over the
    identical corpus; the clean row is the one every layer must exclude.
    """
    return {
        "clean": _make_interaction(
            db_session, query_text="clean query", trust_signal="answer", rubric_outcome="pass"
        ),
        "flagged": _make_interaction(
            db_session, query_text="flagged query", trust_signal="flag", rubric_outcome="pass"
        ),
        "downvoted": _make_interaction(
            db_session,
            query_text="downvoted query",
            trust_signal="answer",
            rubric_outcome="pass",
            user_feedback={"rating": "down"},
        ),
        "failed": _make_interaction(
            db_session, query_text="failed query", trust_signal="answer", rubric_outcome="fail"
        ),
    }


def _surfaced_ids(groups) -> set:
    return {i for g in groups for i in g.interaction_ids}


def test_the_sql_prefilter_alone_excludes_a_clean_row(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The SQL half of the three-part filter, with the Python half neutralized.

    Filed as J-07 in `tracker/phase_4.6_judge_report.md` (mutation RV3):
    widening `find_weekly_candidates`'s SQL `or_(...)` so it selects every
    row left this file at `10 passed`. T-4.6-10's first acceptance criterion,
    "exactly per stage 3 step 1", was untested at the SQL layer, and the
    reason is that `_is_flagged` re-applies the identical rule in Python over
    the returned rows and quietly covers for it. The two guards mask each
    other, so a suite that only calls `find_weekly_candidates` cannot see
    either one fail alone.

    This arm neutralizes `_is_flagged` (always True) so the SQL WHERE clause
    is the only thing deciding, then asserts the clean row is still excluded.

    Control: the `or_(...)` clause in `find_weekly_candidates`'s SQL.
    Mutation run and confirmed red: replacing `review.or_` with one that
    returns `sa.true()`, which is the judge's RV3 exactly, surfaces the clean
    row and fails the assertion below. What ACTUALLY happened, recorded
    rather than predicted: the failure is on the clean-row assertion, not on
    the group count, because the clean row forms its OWN group and the count
    assertion would also have moved, so both were kept and the named one
    fires first.
    """
    rows = _seed_one_of_each_shape(db_session)
    monkeypatch.setattr(review, "_is_flagged", lambda interaction: True)

    surfaced = _surfaced_ids(review.find_weekly_candidates(db_session))
    assert rows["clean"].id not in surfaced, (
        "with the Python re-assertion neutralized the SQL WHERE clause let a "
        "clean pass/answer/no-feedback row through, so the prefilter is no "
        "longer stage 3 step 1's three-part filter"
    )
    for name in ("flagged", "downvoted", "failed"):
        assert rows[name].id in surfaced, (
            f"the SQL prefilter dropped the {name} row, which stage 3 step 1 "
            "requires it to surface"
        )


def test_the_python_reassertion_alone_excludes_a_clean_row(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The Python half of the same filter, with the SQL half neutralized.

    Filed as J-07 in `tracker/phase_4.6_judge_report.md` (mutation RV5):
    deleting the `_is_flagged(row)` re-assertion left this file at `10
    passed`. `review.py`'s own docstring says the double-check exists so the
    SQL and the Python "can never silently drift apart", and nothing asserted
    the Python half did anything at all, so the guard could not detect the
    drift it was written for.

    This arm neutralizes the SQL `or_(...)` so every row inside the window is
    returned, leaving `_is_flagged` as the only thing deciding.

    Control: the `if _is_flagged(row)` re-assertion in
    `find_weekly_candidates`. Mutation run and confirmed red: replacing
    `review._is_flagged` with one that always returns True, which is the
    judge's RV5 exactly, surfaces the clean row and fails the assertion
    below.
    """
    rows = _seed_one_of_each_shape(db_session)
    monkeypatch.setattr(review, "or_", lambda *conditions: sa.true())

    surfaced = _surfaced_ids(review.find_weekly_candidates(db_session))
    assert rows["clean"].id not in surfaced, (
        "with the SQL prefilter neutralized the Python re-assertion let a "
        "clean pass/answer/no-feedback row through, so `_is_flagged` is not "
        "applying stage 3 step 1's rule"
    )
    for name in ("flagged", "downvoted", "failed"):
        assert rows[name].id in surfaced, (
            f"the Python re-assertion dropped the {name} row, which stage 3 "
            "step 1 requires it to surface"
        )


def test_the_two_filter_layers_select_the_same_rows(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The drift check `review.py` claims and nothing asserted.

    `_is_flagged`'s docstring: kept as a Python predicate re-applied over
    rows the SQL already narrowed "so the two can never silently drift
    apart: this is the same rule, asserted twice, not two different rules
    that happen to agree today". Whether they agree was never measured. This
    arm measures it, by running each layer alone over one corpus and
    comparing the two sets.

    Control: either layer. Mutation run and confirmed red under BOTH of the
    judge's mutations, which is what makes this the drift detector rather
    than a third copy of the arms above: `or_` returning `sa.true()` (RV3)
    grows the SQL-only set by the clean row, and `_is_flagged` returning
    True (RV5) grows the Python-only set by the clean row. Each leaves the
    other set untouched, so the sets differ and this arm fails, naming which
    layer moved in its message.
    """
    _seed_one_of_each_shape(db_session)

    with pytest.MonkeyPatch.context() as sql_only:
        sql_only.setattr(review, "_is_flagged", lambda interaction: True)
        sql_layer = _surfaced_ids(review.find_weekly_candidates(db_session))

    with pytest.MonkeyPatch.context() as python_only:
        python_only.setattr(review, "or_", lambda *conditions: sa.true())
        python_layer = _surfaced_ids(review.find_weekly_candidates(db_session))

    assert sql_layer == python_layer, (
        "the SQL WHERE clause and the `_is_flagged` predicate no longer "
        "select the same rows, which is the silent drift the double-check "
        "exists to prevent. Only the SQL selects: "
        f"{sorted(str(i) for i in sql_layer - python_layer)}; only the "
        f"predicate selects: {sorted(str(i) for i in python_layer - sql_layer)}"
    )


def test_find_weekly_candidates_excludes_rows_outside_the_window(db_session: Session) -> None:
    """Mutation: removing the `Interaction.created_at >= window_start` clause
    left this red (a 40-day-old row appeared inside a 7-day review window).
    """
    stale = _make_interaction(
        db_session,
        query_text="ancient failure",
        trust_signal="flag",
        created_at=datetime.now(UTC) - timedelta(days=40),
    )
    fresh = _make_interaction(db_session, query_text="recent failure", trust_signal="flag")

    groups = review.find_weekly_candidates(db_session, window_days=7)
    surfaced_ids = {i for g in groups for i in g.interaction_ids}
    assert fresh.id in surfaced_ids
    assert stale.id not in surfaced_ids


def test_find_weekly_candidates_groups_by_normalized_query_and_orders_by_count(
    db_session: Session,
) -> None:
    """Mutation: grouping by the raw `row.query_text` instead of
    `normalize_query_text(row.query_text)` left this red (three
    differently-cased and -spaced phrasings of one question formed three
    separate count=1 groups instead of one count=3 group).
    """
    for text in ("What is BRCA1?", "what is brca1?", "  What   is BRCA1?  "):
        _make_interaction(db_session, query_text=text, trust_signal="flag")
    _make_interaction(db_session, query_text="unrelated question", trust_signal="flag")

    groups = review.find_weekly_candidates(db_session)
    assert groups[0].count == 3
    assert groups[0].normalized_query == "what is brca1?"
    assert groups[1].count == 1


def test_find_similar_existing_candidates_uses_pg_trgm_similarity(db_session: Session) -> None:
    """Mutation: hardcoding the comparison to `>= 1.1` (an unreachable
    similarity score) left this red (no candidate ever matched, including
    the near-duplicate).
    """
    close = CqCandidate(
        representative_query="What is known about the BRCA1 gene?", source_interaction_ids=[]
    )
    far = CqCandidate(
        representative_query="How many pathogenic ClinVar variants exist for TP53?",
        source_interaction_ids=[],
    )
    db_session.add_all([close, far])
    db_session.flush()

    matches = review.find_similar_existing_candidates(
        db_session, "What is known about the BRCA1 gene today?", threshold=0.4
    )
    matched_ids = {m.id for m in matches}
    assert close.id in matched_ids
    assert far.id not in matched_ids


def test_count_pattern_recurrence_counts_within_window_only(db_session: Session) -> None:
    """Mutation: removing the `Interaction.created_at >= window_start` filter
    from the underlying select left this red (the count included a
    60-day-old duplicate that a 30-day window must exclude).
    """
    for _ in range(2):
        _make_interaction(db_session, query_text="What is BRCA1?", trust_signal="answer")
    _make_interaction(
        db_session,
        query_text="What is BRCA1?",
        trust_signal="answer",
        created_at=datetime.now(UTC) - timedelta(days=60),
    )

    count = review.count_pattern_recurrence(db_session, "what is brca1?", window_days=30)
    assert count == 2


def test_evaluate_trigger_rule_composes_frequency_moat_and_novelty(db_session: Session) -> None:
    """Mutation: computing `moat_met` with `or` instead of `and` left this red
    (a candidate with only one of the two boolean gates passing still
    reported `moat_met=True`).
    """
    for _ in range(3):
        _make_interaction(db_session, query_text="What is BRCA1?", trust_signal="flag")

    result = review.evaluate_trigger_rule(
        db_session,
        normalized_query="what is brca1?",
        representative_query="What is BRCA1?",
        moat_gate_provenance=True,
        moat_gate_deterministic=False,
        moat_partial_or_better=True,
    )
    assert result.frequency_count == 3
    assert result.frequency_met is True
    assert result.moat_met is False
    assert result.is_novel is True


def test_upsert_candidate_rejects_missing_reviewed_by(db_session: Session) -> None:
    """Mutation: replacing the `if not reviewed_by or not reviewed_by.strip()`
    guard with `pass` left this red (a blank reviewer identity silently
    created a `cq_candidates` row instead of raising).
    """
    with pytest.raises(ValueError, match="reviewed_by"):
        review.upsert_candidate(
            db_session,
            representative_query="What is BRCA1?",
            source_interaction_ids=[],
            wedge_type=None,
            moat_gate_provenance=None,
            moat_gate_deterministic=None,
            moat_rank=None,
            reviewed_by="   ",
            review_decision="approve",
        )


def test_upsert_candidate_creates_new_row_with_human_supplied_review_fields(
    db_session: Session,
) -> None:
    """Mutation: hardcoding `status="promoted"` in the new-row branch left
    this red (an 'approve' decision must land the row on 'approved'; only
    `promote_candidate` in `feedback.promotion` may ever set 'promoted').
    """
    interaction = _make_interaction(db_session, query_text="What is BRCA1?", trust_signal="flag")
    candidate = review.upsert_candidate(
        db_session,
        representative_query="What is known about the {gene} gene?",
        source_interaction_ids=[interaction.id],
        wedge_type="gene-variant-literature",
        moat_gate_provenance=True,
        moat_gate_deterministic=True,
        moat_rank="tier_1",
        reviewed_by="jane.reviewer",
        review_decision="approve",
    )
    assert candidate.status == "approved"
    assert candidate.reviewed_by == "jane.reviewer"
    assert candidate.review_decision == "approve"
    assert candidate.source_interaction_ids == [interaction.id]


def test_upsert_candidate_reinforces_existing_row_without_touching_moat_rank(
    db_session: Session,
) -> None:
    """Mutation: the reinforcement branch overwriting `candidate.moat_rank`
    with the caller's new value left this red (`moat_rank` flipped from
    'tier_1' to 'tier_2', which Section 16 stage 4 explicitly forbids:
    "leaves `moat_rank` as is").
    """
    interaction1 = _make_interaction(db_session, query_text="What is BRCA1?", trust_signal="flag")
    interaction2 = _make_interaction(db_session, query_text="What is BRCA1?", trust_signal="flag")

    first = review.upsert_candidate(
        db_session,
        representative_query="What is known about the {gene} gene?",
        source_interaction_ids=[interaction1.id],
        wedge_type="gene-variant-literature",
        moat_gate_provenance=True,
        moat_gate_deterministic=True,
        moat_rank="tier_1",
        reviewed_by="jane.reviewer",
        review_decision="approve",
    )
    db_session.flush()

    reinforced = review.upsert_candidate(
        db_session,
        representative_query="irrelevant on the reinforcement path",
        source_interaction_ids=[interaction1.id, interaction2.id],
        wedge_type="other",
        moat_gate_provenance=False,
        moat_gate_deterministic=False,
        moat_rank="tier_2",
        reviewed_by="jane.reviewer",
        review_decision="approve",
        existing_candidate_id=first.id,
    )

    assert reinforced.id == first.id
    assert reinforced.moat_rank == "tier_1"
    assert set(reinforced.source_interaction_ids) == {interaction1.id, interaction2.id}
    assert reinforced.frequency_count == 2
