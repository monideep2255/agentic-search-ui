"""Tests for `synthesis/snippets.py` (build phase 8.8, "card 44", "answer
on top, evidence below").

Two halves, tested separately per the module's own split:

    `split_abstract_sentences` is pure and deterministic. Every test below
    runs it with nothing but strings in and strings out, no mock needed.

    `pick_snippet` makes exactly one call, to `decide()`. Every test below
    monkeypatches `snippets.decide` (the name imported into this module's
    namespace, the same pattern `test_decide.py` and `core/graph.py`'s own
    tests use for a from-import), so no model and no network is ever
    reached here.

COVERAGE STATEMENT, per `goal-contracts.md`'s "a verify surface must state
its own coverage": this file proves the splitter protects "et al." and a
decimal period (including a "p < 0.05" shape), drops a too-short fragment
and a fragment with no verb-like token, excludes an over-long sentence,
and caps at `MAX_SENTENCES`. It does NOT prove the splitter handles every
abbreviation in English, an ellipsis, or a quoted sentence boundary; the
module's own docstring names that gap. For `pick_snippet`, this file
proves the empty-candidate short-circuit, a chosen sentence returned
verbatim, "none" and an unusable choice both returning `None`, a raised
exception returning `None` rather than propagating, and the
`MAX_CANDIDATE_SENTENCES` truncation actually reaching `decide()`'s
`options` and `criteria`. It does not exercise `decide()`'s own internals
(Jev, the guard tier, the fallback logic); those are `test_decide.py`'s
job.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import DecisionRecord
from system_03_search_agent.synthesis import snippets as snippets_module
from system_03_search_agent.synthesis.snippets import (
    MAX_CANDIDATE_SENTENCES,
    MAX_SENTENCE_CHARS,
    MAX_SENTENCES,
    Snippet,
    candidate_window,
    pick_snippet,
    split_abstract_sentences,
)

# ---------------------------------------------------------------------------
# split_abstract_sentences
# ---------------------------------------------------------------------------


def test_splits_two_plain_sentences() -> None:
    text = (
        "The variant increases transcription of the downstream gene significantly. "
        "This effect was replicated in a second independent cohort of patients."
    )
    result = split_abstract_sentences(text)
    assert result == [
        "The variant increases transcription of the downstream gene significantly.",
        "This effect was replicated in a second independent cohort of patients.",
    ]


def test_et_al_does_not_split_the_sentence() -> None:
    # Catches: a naive `.` split that would cut this into "Smith et al" and
    # "showed that the mutation increases enzymatic activity twofold.",
    # losing the subject of the sentence it belongs to.
    text = (
        "Smith et al. showed that the mutation increases enzymatic activity "
        "twofold in every cell line tested. A larger follow-up study later "
        "confirmed the same effect independently."
    )
    result = split_abstract_sentences(text)
    assert len(result) == 2
    assert result[0].startswith("Smith et al. showed that")
    assert result[0].endswith("twofold in every cell line tested.")
    assert result[1] == "A larger follow-up study later confirmed the same effect independently."


def test_eg_and_ie_do_not_split_the_sentence() -> None:
    text = (
        "Several confounders, e.g. age and smoking status, were adjusted for in "
        "the regression model used across all analyses. Results held regardless "
        "of age or smoking status once the model was applied."
    )
    result = split_abstract_sentences(text)
    assert len(result) == 2
    assert "e.g. age and smoking status" in result[0]
    assert result[1].startswith("Results held regardless")


def test_decimal_number_does_not_split_the_sentence() -> None:
    # "0.05" must never be read as two sentence-ending periods.
    text = (
        "The estimated carrier frequency was 0.05 in the population studied here, "
        "consistent with three prior independent reports on the same cohort."
    )
    result = split_abstract_sentences(text)
    assert len(result) == 1
    assert "0.05" in result[0]


def test_p_value_clause_does_not_split_the_sentence() -> None:
    text = (
        "The association was statistically significant with p < 0.05 across "
        "every cohort tested in this replication study of the original finding."
    )
    result = split_abstract_sentences(text)
    assert len(result) == 1
    assert "p < 0.05" in result[0]


def test_short_fragment_is_dropped() -> None:
    # Under MIN_SENTENCE_WORDS (8): a caption-shaped fragment, not a claim.
    text = (
        "Figure 1 overview. "
        "The gene increases the risk of early disease onset significantly across cohorts."
    )
    result = split_abstract_sentences(text)
    assert len(result) == 1
    assert result[0].startswith("The gene increases")


def test_fragment_with_no_verb_like_token_is_dropped() -> None:
    # Eight words, none a verb by the fixed set or the -s/-ed/-ing heuristic:
    # a running-head shape a real abstract can carry, never a claim.
    text = (
        "Table one title page appendix index annex glossary. "
        "The gene increases risk of disease onset significantly across cohorts."
    )
    result = split_abstract_sentences(text)
    assert len(result) == 1
    assert result[0].startswith("The gene increases")


def test_overlong_sentence_is_excluded() -> None:
    long_sentence = "This finding replicates across a very large number of cohorts " * 10
    long_sentence = long_sentence.strip() + "."
    assert len(long_sentence) > MAX_SENTENCE_CHARS
    text = long_sentence + " A second, ordinary sentence confirms the same result independently."
    result = split_abstract_sentences(text)
    assert len(result) == 1
    assert result[0].startswith("A second, ordinary sentence")


def test_bounded_at_max_sentences() -> None:
    one = "The protein regulates transcription during early development stages. "
    text = one * 60
    result = split_abstract_sentences(text)
    assert len(result) == MAX_SENTENCES


def test_empty_and_whitespace_input_returns_empty_list() -> None:
    assert split_abstract_sentences("") == []
    assert split_abstract_sentences("   \n\t  ") == []


def test_returned_sentences_never_carry_the_shield_character() -> None:
    text = (
        "Smith et al. reported a frequency of 0.05 across three cohorts of "
        "patients enrolled in this multi-site replication study of the finding."
    )
    for sentence in split_abstract_sentences(text):
        assert "" not in sentence


# ---------------------------------------------------------------------------
# pick_snippet
# ---------------------------------------------------------------------------

_CANDIDATES = [
    "The gene increases risk of early onset disease across every cohort tested.",
    "No association was found between the variant and disease severity scores.",
    "Carriers showed a twofold increase in expression relative to non-carriers.",
]


def _record(chosen: str, options: list[str]) -> DecisionRecord:
    return DecisionRecord(name="write.snippet", options=options, chosen=chosen, decided_by="guard")


@pytest.mark.asyncio
async def test_no_candidates_returns_none_without_calling_decide(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_decide = AsyncMock()
    monkeypatch.setattr(snippets_module, "decide", mock_decide)
    result = await pick_snippet(harness=object(), trace_id="t1", question="q", abstract_sentences=[])
    assert result is None
    mock_decide.assert_not_called()


@pytest.mark.asyncio
async def test_chosen_sentence_is_returned_verbatim(monkeypatch: pytest.MonkeyPatch) -> None:
    options = ["s0", "s1", "s2", "none"]
    monkeypatch.setattr(snippets_module, "decide", AsyncMock(return_value=_record("s1", options)))
    result = await pick_snippet(
        harness=object(), trace_id="t1", question="Does the variant affect severity?",
        abstract_sentences=_CANDIDATES,
    )
    assert result == Snippet(text=_CANDIDATES[1])


@pytest.mark.asyncio
async def test_chosen_none_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    options = ["s0", "s1", "s2", "none"]
    monkeypatch.setattr(snippets_module, "decide", AsyncMock(return_value=_record("none", options)))
    result = await pick_snippet(
        harness=object(), trace_id="t1", question="q", abstract_sentences=_CANDIDATES
    )
    assert result is None


@pytest.mark.asyncio
async def test_a_failed_decision_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # "A failed decision returns None (show nothing): silence is honest, a
    # wrong snippet is not." This is the case where the seam itself blows up.
    async def _boom(*_args: object, **_kwargs: object) -> DecisionRecord:
        raise RuntimeError("classifier seam unavailable")

    monkeypatch.setattr(snippets_module, "decide", _boom)
    result = await pick_snippet(
        harness=object(), trace_id="t1", question="q", abstract_sentences=_CANDIDATES
    )
    assert result is None


@pytest.mark.asyncio
async def test_an_out_of_range_choice_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # Defensive: `decide()` should never hand back an option it was not
    # offered, but this function does not trust that blindly either.
    options = ["s0", "s1", "s2", "none"]
    monkeypatch.setattr(snippets_module, "decide", AsyncMock(return_value=_record("s9", options)))
    result = await pick_snippet(
        harness=object(), trace_id="t1", question="q", abstract_sentences=_CANDIDATES
    )
    assert result is None


@pytest.mark.asyncio
async def test_candidates_are_truncated_to_the_options_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    # DecisionRecord.options carries max_length=12 (contracts/events.py):
    # one slot is always "none", so at most MAX_CANDIDATE_SENTENCES
    # sentences may ever reach `decide()`.
    many = [f"Sentence number {i} makes a distinct claim about the finding here." for i in range(15)]
    captured: dict[str, object] = {}

    async def _capture(harness: object, trace_id: str, point: str, state: str, options: list[str], **kwargs: object) -> DecisionRecord:
        captured["options"] = options
        captured["criteria"] = kwargs["criteria"]
        captured["instructions"] = kwargs["instructions"]
        return _record("none", options)

    monkeypatch.setattr(snippets_module, "decide", _capture)
    await pick_snippet(harness=object(), trace_id="t1", question="q", abstract_sentences=many)

    options = captured["options"]
    assert isinstance(options, list)
    assert len(options) == MAX_CANDIDATE_SENTENCES + 1
    assert options[-1] == "none"
    assert set(options) == set(captured["criteria"])  # type: ignore[arg-type]
    assert captured["instructions"]


@pytest.mark.asyncio
async def test_picking_from_the_truncated_set_still_returns_the_right_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    many = [f"Sentence number {i} makes a distinct claim about the finding here." for i in range(15)]
    # A long abstract offers its first three and its last eight sentences
    # (`candidate_window`), so the closing findings are never cut off. The
    # last option names the abstract's own last sentence.
    last_offered_index = MAX_CANDIDATE_SENTENCES - 1
    options = [f"s{i}" for i in range(MAX_CANDIDATE_SENTENCES)] + ["none"]
    monkeypatch.setattr(
        snippets_module, "decide", AsyncMock(return_value=_record(f"s{last_offered_index}", options))
    )
    result = await pick_snippet(harness=object(), trace_id="t1", question="q", abstract_sentences=many)
    assert result == Snippet(text=many[-1])


def test_the_window_keeps_the_first_three_and_the_last_eight_of_a_long_abstract() -> None:
    many = [f"s{i}" for i in range(20)]
    window = candidate_window(many)
    assert len(window) == MAX_CANDIDATE_SENTENCES
    assert window[:3] == ["s0", "s1", "s2"]
    assert window[-1] == "s19"
    assert candidate_window(many[:5]) == many[:5]
