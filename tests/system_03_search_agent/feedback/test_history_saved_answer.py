"""The read path for a saved answer (fix-plan item 10.2), against a real database.

What a person gets: they click a past search and the answer they already got
is there, with no second search charged to them. This file grades the read
side of that, at the `feedback/history.py` function level rather than through
HTTP.

## Coverage: what this file exercises and what it deliberately omits

Exercised:

- `has_saved_answer` on the list: true for an account row that saved one,
  false for the same caller's row that did not, in ONE list so a function
  that returned a constant cannot pass.
- `get_saved_answer` returns the stored answer, its depth, its citations and
  its question for the owner.
- The 404's three causes are indistinguishable at this layer: the function
  returns `None` for a row that is somebody else's, for a `trace_id` that
  does not exist, and for the caller's own row with no saved answer, each
  paired with a successful fetch so `None` cannot mean "nothing works".
- `forget_saved_answers_for_account` clears one account's saved answers,
  leaves another account's alone, and leaves the row itself intact.
- Argument refusals: empty and over-long `owner_id` and `trace_id`.

NOT exercised:

- The HTTP status codes. `tests/system_03_search_agent/adapters/web_sse/
  test_saved_answer_endpoint.py` owns those.
- Anything about the CONTENT of the markdown. `test_capture_saved_answer.py`
  owns that.
- Whether an account delete path calls `forget_saved_answers_for_account`.
  NO SUCH PATH EXISTS (searched 2026-09-22; see `testing/Developer/reports/
  2026-09-23_overnight/findings.md`), so there is nothing to exercise. That
  is precisely why the function is tested here in isolation: a future delete
  path has to keep these arms green.
"""

from __future__ import annotations

import os
import uuid

import pytest
import sqlalchemy as sa

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
    reason=f"user database unreachable at {USER_DB_URL}; the read path needs a real database",
)

_ANSWER = "TP53 is a tumour suppressor [1].\n\n| Gene | Role |\n| --- | --- |\n| TP53 [1] | suppressor |"


def _citation_payload() -> dict:
    """A full, schema-conformant `contracts.events.CitationPayload` dict.

    Copied from `test_history.py`'s helper of the same name rather than
    imported, for the reason that file already gives: it is a unit-test
    module with no public fixture surface.
    """
    return {
        "citation_id": "call-1-1",
        "display_index": 1,
        "source": "NCBIGene",
        "source_id": "NCBIGene:7157",
        "source_url": "https://www.ncbi.nlm.nih.gov/gene/7157",
        "layer": "layer_1_graph",
        "field": "symbol",
        "claim_text": "TP53 is a tumour suppressor.",
        "evidence_kind": "primary_assertion",
        "assertion_confidence": "asserted",
        "population_ancestry_context": None,
        "license": "public_domain_us_gov",
    }


async def _seed(
    *,
    owner_id: str,
    question: str,
    answer_markdown: str | None = None,
    audience_depth: str | None = None,
    user_id: uuid.UUID | None = None,
) -> str:
    """Write one real `interactions` row through the real writer."""
    from system_03_search_agent.feedback.contracts import InteractionRow
    from system_03_search_agent.feedback.writer import write_interaction

    trace_id = f"savedtest-{uuid.uuid4().hex}"
    await write_interaction(
        InteractionRow(
            trace_id=trace_id,
            owner_id=owner_id,
            user_id=user_id,
            query_text=question,
            query_class="lookup",
            trust_signal="answer",
            rubric_outcome="pass",
            citations=[_citation_payload()],
            answer_markdown=answer_markdown,
            audience_depth=audience_depth,  # type: ignore[arg-type]
        )
    )
    return trace_id


def _stored_answer(trace_id: str) -> str | None:
    """Read the column straight from the table.

    The populate check for every clause below: a clause that finds nothing
    through the read path must not be mistaken for one whose seed never
    landed.
    """
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT answer_markdown FROM interactions WHERE trace_id = :t"),
                {"t": trace_id},
            ).first()
    finally:
        engine.dispose()
    assert row is not None, f"the seed for {trace_id} never reached the table"
    return row[0]


def _account() -> str:
    return f"user:{uuid.uuid4()}"


def _create_account() -> uuid.UUID:
    """A real `users` row, so `interactions.user_id` has something to point at.

    Needed only by the forgetting arms, which key on `user_id` because that
    is the key a future account-delete path will hold. Found by this file's
    own populate check on first run: seeding `user_id` with a UUID that had
    no account made the foreign key reject the insert, the writer fall back
    to its payload-dropped row, and that insert fail too, so the row simply
    was not there. The check said so instead of the arm passing vacuously.
    """
    account_id = uuid.uuid4()
    engine = sa.create_engine(USER_DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO users (id, email, password_hash) "
                    "VALUES (:id, :email, :hash)"
                ),
                {
                    "id": account_id,
                    "email": f"saved-answer-{account_id}@example.test",
                    "hash": "not-a-real-hash",
                },
            )
    finally:
        engine.dispose()
    return account_id


# ---------------------------------------------------------------------------
# has_saved_answer on the list.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_has_saved_answer_is_true_only_for_the_row_that_saved_one() -> None:
    """Both values in ONE list, so a function returning a constant fails."""
    from system_03_search_agent.feedback.history import list_history

    owner = _account()
    without = await _seed(owner_id=owner, question=f"no answer {uuid.uuid4().hex[:8]}")
    with_answer = await _seed(
        owner_id=owner,
        question=f"with answer {uuid.uuid4().hex[:8]}",
        answer_markdown=_ANSWER,
        audience_depth="researcher",
    )
    # POPULATE CHECK: the two seeds really landed the two different ways.
    assert _stored_answer(without) is None
    assert _stored_answer(with_answer) == _ANSWER

    by_trace = {entry.trace_id: entry for entry in list_history(owner_id=owner)}
    assert set(by_trace) == {without, with_answer}
    assert by_trace[with_answer].has_saved_answer is True
    assert by_trace[without].has_saved_answer is False


# ---------------------------------------------------------------------------
# get_saved_answer.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_owner_gets_the_answer_they_already_had() -> None:
    from system_03_search_agent.feedback.history import get_saved_answer

    owner = _account()
    question = f"What does TP53 do? {uuid.uuid4().hex[:8]}"
    trace_id = await _seed(
        owner_id=owner,
        question=question,
        answer_markdown=_ANSWER,
        audience_depth="plain_language",
    )
    assert _stored_answer(trace_id) == _ANSWER  # POPULATE CHECK

    saved = get_saved_answer(owner_id=owner, trace_id=trace_id)
    assert saved is not None
    assert saved.trace_id == trace_id
    assert saved.question == question
    assert saved.answer_markdown == _ANSWER
    assert saved.depth == "plain_language"
    assert saved.trust_signal == "answer"
    assert len(saved.citations) == 1
    assert saved.citations[0]["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/7157"


@pytest.mark.asyncio
async def test_the_three_causes_of_nothing_are_indistinguishable() -> None:
    """Somebody else's row, a row that does not exist, and a row with no
    saved answer all return the same `None`.

    A 403 on somebody else's row would confirm that row exists and is
    someone's, which is the leak this shape exists to prevent.
    """
    from system_03_search_agent.feedback.history import get_saved_answer

    owner = _account()
    stranger = _account()
    mine = await _seed(
        owner_id=owner,
        question=f"mine {uuid.uuid4().hex[:8]}",
        answer_markdown=_ANSWER,
        audience_depth="researcher",
    )
    theirs = await _seed(
        owner_id=stranger,
        question=f"theirs {uuid.uuid4().hex[:8]}",
        answer_markdown=_ANSWER,
        audience_depth="researcher",
    )
    mine_unanswered = await _seed(owner_id=owner, question=f"unanswered {uuid.uuid4().hex[:8]}")

    # POPULATE CHECK: the control holds, so the three `None`s below are
    # about the rule and not about a read path that never returns anything.
    assert get_saved_answer(owner_id=owner, trace_id=mine) is not None
    assert _stored_answer(theirs) == _ANSWER

    assert get_saved_answer(owner_id=owner, trace_id=theirs) is None
    assert get_saved_answer(owner_id=owner, trace_id=f"savedtest-{uuid.uuid4().hex}") is None
    assert get_saved_answer(owner_id=owner, trace_id=mine_unanswered) is None


@pytest.mark.asyncio
async def test_a_guest_never_has_one_to_read() -> None:
    """The write-side exclusion, observed from the read side.

    Not a read-side filter: `get_saved_answer` has no guest branch at all.
    This arm exists to show the consequence, and its account twin above is
    what makes it a statement about guests rather than about the function.
    """
    from system_03_search_agent.feedback.history import get_saved_answer

    guest = f"guest:{uuid.uuid4()}"
    trace_id = await _seed(owner_id=guest, question=f"guest asked {uuid.uuid4().hex[:8]}")
    assert _stored_answer(trace_id) is None  # POPULATE CHECK: the row landed

    assert get_saved_answer(owner_id=guest, trace_id=trace_id) is None


# ---------------------------------------------------------------------------
# Forgetting, for the account-delete path that does not exist yet.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgetting_clears_one_accounts_answers_and_nobody_elses() -> None:
    """The function a future account-delete path must call.

    Seeded with `user_id` set directly rather than through a real account,
    because this repository has no account delete path to exercise and
    creating a `users` row here would test the fixture rather than the
    function. `user_id` is the key the delete path will hold.
    """
    from system_03_search_agent.feedback.history import (
        forget_saved_answers_for_account,
        get_saved_answer,
    )

    leaving = _create_account()
    staying = _create_account()
    owner_leaving = f"user:{leaving}"
    owner_staying = f"user:{staying}"

    gone = await _seed(
        owner_id=owner_leaving,
        question=f"leaving {uuid.uuid4().hex[:8]}",
        answer_markdown=_ANSWER,
        audience_depth="researcher",
        user_id=leaving,
    )
    kept = await _seed(
        owner_id=owner_staying,
        question=f"staying {uuid.uuid4().hex[:8]}",
        answer_markdown=_ANSWER,
        audience_depth="researcher",
        user_id=staying,
    )
    # POPULATE CHECK: both accounts really had a saved answer to begin with.
    assert _stored_answer(gone) == _ANSWER
    assert _stored_answer(kept) == _ANSWER

    cleared = forget_saved_answers_for_account(leaving)
    assert cleared == 1

    assert _stored_answer(gone) is None
    assert get_saved_answer(owner_id=owner_leaving, trace_id=gone) is None
    # The other account is untouched.
    assert _stored_answer(kept) == _ANSWER
    assert get_saved_answer(owner_id=owner_staying, trace_id=kept) is not None


@pytest.mark.asyncio
async def test_forgetting_keeps_the_row_itself() -> None:
    """The row carries the cost and latency the daily caps count. Forgetting
    an answer must never erase the record that a query happened."""
    from system_03_search_agent.feedback.history import (
        forget_saved_answers_for_account,
        list_history,
    )

    account = _create_account()
    owner = f"user:{account}"
    question = f"still listed {uuid.uuid4().hex[:8]}"
    trace_id = await _seed(
        owner_id=owner,
        question=question,
        answer_markdown=_ANSWER,
        audience_depth="researcher",
        user_id=account,
    )
    assert _stored_answer(trace_id) == _ANSWER  # POPULATE CHECK

    forget_saved_answers_for_account(account)

    entries = list_history(owner_id=owner)
    assert [entry.question for entry in entries] == [question]
    assert entries[0].has_saved_answer is False


def test_forgetting_an_account_with_nothing_saved_reports_zero() -> None:
    from system_03_search_agent.feedback.history import forget_saved_answers_for_account

    assert forget_saved_answers_for_account(uuid.uuid4()) == 0


# ---------------------------------------------------------------------------
# Argument refusals.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("owner_id", "trace_id"),
    [
        ("", "t"),
        ("u" * 129, "t"),
        ("user:x", ""),
        ("user:x", "t" * 65),
    ],
)
def test_out_of_bounds_arguments_are_refused_before_a_query_is_built(
    owner_id: str, trace_id: str
) -> None:
    from system_03_search_agent.feedback.history import get_saved_answer

    # POPULATE CHECK: an in-bounds pair does NOT raise, so the four
    # rejections below are about the bounds rather than about the function
    # refusing everything.
    assert get_saved_answer(owner_id="user:" + "x" * 8, trace_id="t" * 64) is None

    with pytest.raises(ValueError):
        get_saved_answer(owner_id=owner_id, trace_id=trace_id)
