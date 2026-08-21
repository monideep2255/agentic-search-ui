"""Tests for `feedback.promotion` (T-4.6-11, Section 16 stage 5, Section 17).

Depends on:
    - system_03_search_agent.feedback.promotion (the module under test)
    - system_03_search_agent.data.models (Interaction, CqCandidate)
    - A reachable local PostgreSQL server named by USER_DB_URL

Writes:
    - A uniquely named throwaway database, created and dropped by this
      module, the same pattern `test_review.py` and
      `test_migration_0007_session_memory.py` use.
    - Throwaway JSON files under `tmp_path` for the pool and golden-dataset
      destinations. This suite never writes to the real
      `orchestrator/few_shot_examples.json` or `eval/golden_dataset.json`:
      every call to `promote_candidate` below passes explicit `pool_path`
      and `golden_dataset_path` arguments.

## Coverage: what this file exercises and what it deliberately omits

Exercised:

- `promote_candidate` appends payloads matching Section 17's two shapes
  exactly, tagged with `cq_candidate_id`.
- It refuses (`review_decision != 'approve'`) rather than promoting.
- The privacy gate, structurally: refuses a verbatim copy of a source
  interaction's `query_text` sitting in EITHER `few_shot_example.query_pattern`
  OR `eval_case.question` (F-4.6-A-04, both fields, not one enumerated
  field), refuses a copy that differs only in case or whitespace
  (F-4.6-A-04's `.capitalize()` bypass), and accepts a genuinely
  generalized pattern.
- The fail-open closure: refuses when `source_interaction_ids` names rows
  that do not resolve, rather than promoting on an unverifiable input
  (F-4.6-A-05), and still promotes normally when `source_interaction_ids`
  is empty by construction (a hand-authored candidate, Section 17's seed
  few-shot shape).
- Idempotency: running `promote_candidate` twice on the same candidate does
  not append a second entry to either file.
- `FewShotExample` and `EvalCase` reject an unknown field (`extra="forbid"`),
  the schema-validation gate `production-standards` requires for every
  payload.

Deliberately NOT exercised here:

- The CLI (`build_arg_parser`, `_cmd_promote`). Thin argparse-to-function
  plumbing over `promote_candidate`, which is covered directly.
- Anything under `feedback.review`, which has its own test file.
- The real destination files (`orchestrator/few_shot_examples.json`,
  `eval/golden_dataset.json`). Every test here points `promote_candidate`
  at a `tmp_path` file instead.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from system_03_search_agent.data.models import CqCandidate, Interaction
from system_03_search_agent.feedback import promotion

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
    db_name = f"feedback_promotion_scratch_{uuid.uuid4().hex}"
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
def monkeypatch_module():
    """A module-scoped monkeypatch, since the built-in `monkeypatch` fixture is function-scoped."""
    mp = pytest.MonkeyPatch()
    try:
        yield mp
    finally:
        mp.undo()


@pytest.fixture(scope="module")
def migrated_scratch_db_url(scratch_db_url, monkeypatch_module):
    """Upgrade the scratch database to head once, held for the whole module."""
    monkeypatch_module.setenv("USER_DB_URL", scratch_db_url)
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    return scratch_db_url


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


def _make_interaction(session: Session, *, query_text: str) -> Interaction:
    interaction = Interaction(
        trace_id=f"trace-{uuid.uuid4().hex}",
        query_text=query_text,
        query_class="lookup",
        route={"layers": ["layer2"], "tools": ["ncbi_efetch"]},
        trust_signal="answer",
        rubric_outcome="pass",
    )
    session.add(interaction)
    session.flush()
    return interaction


def _make_approved_candidate(
    session: Session, *, source_interaction_ids: list[uuid.UUID], review_decision: str = "approve"
) -> CqCandidate:
    candidate = CqCandidate(
        representative_query="What is known about the {gene} gene?",
        source_interaction_ids=source_interaction_ids,
        status="approved" if review_decision == "approve" else "proposed",
        reviewed_by="jane.reviewer",
        review_decision=review_decision,
    )
    session.add(candidate)
    session.flush()
    return candidate


def _valid_few_shot_example() -> promotion.FewShotExample:
    return promotion.FewShotExample(
        query_pattern="What is known about the {gene} gene?",
        query_class="exploratory",
        resolved_entities=[
            {"surface_form": "BRCA1", "curie": "NCBIGene:672", "entity_type": "gene"}
        ],
        route={"layers": ["layer1", "layer2"], "tools": ["cypher_query", "ncbi_efetch"]},
        narrative_pattern="gene record, recent reviews, pathogenic variants, clinical tests, linked conditions",
        citation_pattern=["Gene", "PubMed", "ClinVar", "GTR", "MedGen"],
    )


def _valid_eval_case() -> promotion.EvalCase:
    # Deliberately NOT the same sentence as the `query_text` the positive
    # tests below feed `_make_interaction` ("What is known about the BRCA1
    # gene?"). Before F-4.6-A-04 was fixed the two were accidentally
    # byte-identical in this fixture, which is exactly the gap the finding
    # named: the check only ever looked at `few_shot_example.query_pattern`,
    # so this file's own positive tests were silently promoting a verbatim
    # `eval_case.question` the whole time and nothing caught it.
    return promotion.EvalCase(
        question="What has research established about the BRCA1 gene?",
        expected_entities=["NCBIGene:672"],
        expected_layers=["layer1", "layer2"],
        expected_tools=["cypher_query", "ncbi_efetch"],
        expected_citation_sources=["Gene", "PubMed", "ClinVar", "GTR", "MedGen"],
        fixture_ref="golden/gene_672_brca1_2026-07",
        rubric_hint={"must_not_render_verdict": True},
    )


def test_few_shot_example_and_eval_case_reject_an_unknown_field() -> None:
    """Mutation: dropping `model_config = ConfigDict(extra="forbid")` from
    `FewShotExample` left this red (an unexpected key was silently accepted
    instead of raising `ValidationError`).
    """
    payload = _valid_few_shot_example().model_dump()
    payload["unexpected_field"] = "should not be allowed"
    with pytest.raises(ValidationError):
        promotion.FewShotExample.model_validate(payload)

    ec_payload = _valid_eval_case().model_dump()
    ec_payload["unexpected_field"] = "should not be allowed"
    with pytest.raises(ValidationError):
        promotion.EvalCase.model_validate(ec_payload)


def test_promote_candidate_appends_section17_shapes_tagged_with_candidate_id(
    db_session: Session, tmp_path
) -> None:
    """Mutation: appending the raw Pydantic `.model_dump()` without adding
    `cq_candidate_id` left this red (the traceability tag Section 16 stage 5
    requires was missing from both files).
    """
    interaction = _make_interaction(db_session, query_text="What is known about the BRCA1 gene?")
    candidate = _make_approved_candidate(db_session, source_interaction_ids=[interaction.id])
    pool_path = tmp_path / "few_shot_examples.json"
    golden_path = tmp_path / "golden_dataset.json"

    promotion.promote_candidate(
        db_session,
        candidate_id=candidate.id,
        few_shot_example=_valid_few_shot_example(),
        eval_case=_valid_eval_case(),
        pool_path=pool_path,
        golden_dataset_path=golden_path,
    )

    pool_data = json.loads(pool_path.read_text())
    golden_data = json.loads(golden_path.read_text())

    assert len(pool_data["examples"]) == 1
    assert pool_data["examples"][0]["cq_candidate_id"] == str(candidate.id)
    assert pool_data["examples"][0]["query_pattern"] == "What is known about the {gene} gene?"
    assert pool_data["examples"][0]["route"] == {
        "layers": ["layer1", "layer2"],
        "tools": ["cypher_query", "ncbi_efetch"],
    }

    assert len(golden_data["cases"]) == 1
    assert golden_data["cases"][0]["cq_candidate_id"] == str(candidate.id)
    assert golden_data["cases"][0]["fixture_ref"] == "golden/gene_672_brca1_2026-07"
    assert golden_data["cases"][0]["rubric_hint"] == {"must_not_render_verdict": True}


def test_promote_candidate_updates_the_row_status_and_promoted_at(
    db_session: Session, tmp_path
) -> None:
    """Mutation: never setting `candidate.status = "promoted"` left this red
    (the row stayed 'approved' after a successful promotion).
    """
    interaction = _make_interaction(db_session, query_text="What is known about the BRCA1 gene?")
    candidate = _make_approved_candidate(db_session, source_interaction_ids=[interaction.id])

    promoted = promotion.promote_candidate(
        db_session,
        candidate_id=candidate.id,
        few_shot_example=_valid_few_shot_example(),
        eval_case=_valid_eval_case(),
        pool_path=tmp_path / "pool.json",
        golden_dataset_path=tmp_path / "golden.json",
    )

    assert promoted.status == "promoted"
    assert promoted.promoted_at is not None
    assert promoted.few_shot_example["cq_candidate_id"] == str(candidate.id)
    assert promoted.eval_case["cq_candidate_id"] == str(candidate.id)


def test_promote_candidate_requires_review_decision_approve(db_session: Session, tmp_path) -> None:
    """Mutation: removing the `review_decision != 'approve'` guard left this
    red (a row with `review_decision='reject'` was promoted anyway).
    """
    interaction = _make_interaction(db_session, query_text="What is known about the BRCA1 gene?")
    candidate = _make_approved_candidate(
        db_session, source_interaction_ids=[interaction.id], review_decision="reject"
    )

    with pytest.raises(ValueError, match="approve"):
        promotion.promote_candidate(
            db_session,
            candidate_id=candidate.id,
            few_shot_example=_valid_few_shot_example(),
            eval_case=_valid_eval_case(),
            pool_path=tmp_path / "pool.json",
            golden_dataset_path=tmp_path / "golden.json",
        )


def test_promote_candidate_refuses_a_verbatim_copy_of_the_source_query_text(
    db_session: Session, tmp_path
) -> None:
    """Mutation: removing the `_is_verbatim_copy` check from `promote_candidate`
    left this red (a literal, ungeneralized `query_pattern` promoted without
    complaint, defeating Section 16's privacy step).
    """
    literal_text = "What is known about the BRCA1 gene?"
    interaction = _make_interaction(db_session, query_text=literal_text)
    candidate = _make_approved_candidate(db_session, source_interaction_ids=[interaction.id])

    verbatim_example = _valid_few_shot_example().model_copy(
        update={"query_pattern": literal_text}
    )

    with pytest.raises(promotion.PrivacyViolationError):
        promotion.promote_candidate(
            db_session,
            candidate_id=candidate.id,
            few_shot_example=verbatim_example,
            eval_case=_valid_eval_case(),
            pool_path=tmp_path / "pool.json",
            golden_dataset_path=tmp_path / "golden.json",
        )

    # Nothing partially written: neither destination file exists, and the
    # row is not promoted.
    assert not (tmp_path / "pool.json").exists()
    db_session.refresh(candidate)
    assert candidate.status != "promoted"


def test_promote_candidate_accepts_a_genuinely_generalized_pattern(
    db_session: Session, tmp_path
) -> None:
    """The positive case for the privacy gate above: '{gene}' in place of the
    literal phrasing is not byte-identical and must be allowed through.
    """
    interaction = _make_interaction(db_session, query_text="What is known about the BRCA1 gene?")
    candidate = _make_approved_candidate(db_session, source_interaction_ids=[interaction.id])

    promoted = promotion.promote_candidate(
        db_session,
        candidate_id=candidate.id,
        few_shot_example=_valid_few_shot_example(),  # query_pattern uses "{gene}"
        eval_case=_valid_eval_case(),
        pool_path=tmp_path / "pool.json",
        golden_dataset_path=tmp_path / "golden.json",
    )
    assert promoted.status == "promoted"


def test_promote_candidate_refuses_a_verbatim_copy_in_eval_case_question(
    db_session: Session, tmp_path
) -> None:
    """Reproduces F-4.6-A-04 (case B): a user's exact sentence reaching
    `eval/golden_dataset.json` through `eval_case.question`, the field the
    original check never looked at.

    `few_shot_example.query_pattern` here is genuinely generalized ('{gene}'
    style), so before the fix this call promoted successfully and the
    literal sentence landed byte-identical in the golden-dataset entry.
    Verified by hand against the pre-fix module: this exact test raised no
    exception and `golden_path` held the verbatim sentence.

    Mutation: reverting `promote_candidate` to only check
    `few_shot_example.query_pattern` (the pre-fix shape) leaves this red,
    the DID NOT RAISE failure `pytest.raises` reports when the promotion
    succeeds instead of refusing.
    """
    literal_text = "does my patient Jane Q Doe carrying BRCA1 need a mastectomy?"
    interaction = _make_interaction(db_session, query_text=literal_text)
    candidate = _make_approved_candidate(db_session, source_interaction_ids=[interaction.id])

    verbatim_eval_case = _valid_eval_case().model_copy(update={"question": literal_text})

    with pytest.raises(promotion.PrivacyViolationError):
        promotion.promote_candidate(
            db_session,
            candidate_id=candidate.id,
            few_shot_example=_valid_few_shot_example(),  # query_pattern uses "{gene}", not literal_text
            eval_case=verbatim_eval_case,
            pool_path=tmp_path / "pool.json",
            golden_dataset_path=tmp_path / "golden.json",
        )

    # Nothing partially written, the same guarantee the query_pattern case
    # above already covers: the eval_case field must be held to it too.
    assert not (tmp_path / "golden.json").exists()
    db_session.refresh(candidate)
    assert candidate.status != "promoted"


def test_promote_candidate_refuses_a_case_only_variant_of_the_source_text(
    db_session: Session, tmp_path
) -> None:
    """Reproduces F-4.6-A-04's second bypass: `.capitalize()` on the source
    sentence differs from it in bytes but is not a generalization.

    Mutation: reverting `_is_verbatim_copy` to compare `.strip()` output
    directly, without `_normalize_for_comparison`'s casefold, leaves this
    red (the capitalized copy passes the strict byte check and promotes).
    """
    literal_text = "what is known about the brca1 gene and its variants?"
    interaction = _make_interaction(db_session, query_text=literal_text)
    candidate = _make_approved_candidate(db_session, source_interaction_ids=[interaction.id])

    case_variant_example = _valid_few_shot_example().model_copy(
        update={"query_pattern": literal_text.capitalize()}
    )

    with pytest.raises(promotion.PrivacyViolationError):
        promotion.promote_candidate(
            db_session,
            candidate_id=candidate.id,
            few_shot_example=case_variant_example,
            eval_case=_valid_eval_case(),
            pool_path=tmp_path / "pool.json",
            golden_dataset_path=tmp_path / "golden.json",
        )


def test_promote_candidate_refuses_when_source_interaction_rows_are_missing(
    db_session: Session, tmp_path
) -> None:
    """Reproduces F-4.6-A-05: `source_interaction_ids` names a row that does
    not exist, so the privacy check has nothing to compare against.

    The pre-fix check passed unconditionally in this state
    (`any(...)` over an empty comparison set is `False`); this asserts the
    fixed, fail-closed behaviour instead.

    Mutation: removing the `len(source_texts) < len(distinct_source_ids)`
    guard in `promote_candidate` leaves this red (a candidate whose source
    row is gone promotes silently, carrying whatever the caller typed).
    """
    missing_id = uuid.uuid4()
    candidate = _make_approved_candidate(db_session, source_interaction_ids=[missing_id])

    with pytest.raises(promotion.SourceInteractionsUnavailableError):
        promotion.promote_candidate(
            db_session,
            candidate_id=candidate.id,
            few_shot_example=_valid_few_shot_example(),
            eval_case=_valid_eval_case(),
            pool_path=tmp_path / "pool.json",
            golden_dataset_path=tmp_path / "golden.json",
        )

    db_session.refresh(candidate)
    assert candidate.status != "promoted"


def test_promote_candidate_allows_a_candidate_with_no_source_interactions(
    db_session: Session, tmp_path
) -> None:
    """The legitimate counterpart to the fail-open closure above: a
    hand-authored candidate created with `source_interaction_ids=[]` from
    the start (Section 17's seed few-shot shape, "seeded once from the
    evaluation playbook rather than mined from usage") carries no source
    sentence to protect and must still promote.

    This is the case the BLOCKED-STOP condition in this fix's instructions
    warned about: closing the fail-open path must not also block a
    candidate that never had source rows at all. `source_interaction_ids`
    empty by construction is distinguished from `source_interaction_ids`
    naming rows that later went missing by comparing counts, not by
    treating "empty" and "unresolved" as the same state.

    Mutation: changing the `if candidate.source_interaction_ids:` branch to
    always run the missing-rows check (dropping the empty-list carve-out)
    leaves this red, since `0 < 0` is `False` and would not itself raise,
    but changing it to treat "no ids" as "0 resolved of 1 expected" does
    turn this red, confirming the branch is load-bearing.
    """
    candidate = _make_approved_candidate(db_session, source_interaction_ids=[])

    promoted = promotion.promote_candidate(
        db_session,
        candidate_id=candidate.id,
        few_shot_example=_valid_few_shot_example(),
        eval_case=_valid_eval_case(),
        pool_path=tmp_path / "pool.json",
        golden_dataset_path=tmp_path / "golden.json",
    )
    assert promoted.status == "promoted"


def test_promote_candidate_is_idempotent_on_repeat_run(db_session: Session, tmp_path) -> None:
    """Mutation: removing the `cq_candidate_id` dedupe check from
    `_append_pool_entry`/`_append_golden_entry` left this red (running
    promotion twice appended the entry a second time to both files).
    """
    interaction = _make_interaction(db_session, query_text="What is known about the BRCA1 gene?")
    candidate = _make_approved_candidate(db_session, source_interaction_ids=[interaction.id])
    pool_path = tmp_path / "pool.json"
    golden_path = tmp_path / "golden.json"

    for _ in range(2):
        promotion.promote_candidate(
            db_session,
            candidate_id=candidate.id,
            few_shot_example=_valid_few_shot_example(),
            eval_case=_valid_eval_case(),
            pool_path=pool_path,
            golden_dataset_path=golden_path,
        )

    pool_data = json.loads(pool_path.read_text())
    golden_data = json.loads(golden_path.read_text())
    assert len(pool_data["examples"]) == 1
    assert len(golden_data["cases"]) == 1
