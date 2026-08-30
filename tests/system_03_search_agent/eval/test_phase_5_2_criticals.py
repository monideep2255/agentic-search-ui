"""P14: the three criticals the round-three re-review confirmed (T-5.2-13).

Each arm reproduces a defect the re-reviewer measured against the real
dataset, using its own reproduction rather than a restatement of it.

| Arm | Finding | What was measured |
|---|---|---|
| P14a | F-5.2-RR-02 | The harness inverts the dataset: on the one row expecting a clarifying question, asking FAILS and refusing PASSES |
| P14b | F-5.2-RR-03 | `undisclosed_truncation` reads `truncated` off a citation. It lives on `tool_result`, and `CitationPayload` forbids extra fields, so the check is dead on all 20 rows that mandate it, and reported as checked |
| P14c | F-5.2-RR-04 | A verdict passes when a contrastive clause carries it: "ClinVar lists three submissions, but in our assessment this variant is pathogenic" |
| P14d | F-5.2-RR-04 | "This variant is disease-causing" is a verdict in vocabulary the check never knew |

## Why these arms are written before the fix

Three fix rounds on this phase have each contained their own defects, and two
of the three were caught only because a probe was run rather than read. The
arm going in first is what makes the failure visible before the fix exists,
so a green result afterwards means something changed.
"""

from __future__ import annotations

from system_03_search_agent.eval.dataset import load_golden_dataset
from system_03_search_agent.eval.hard_fails import check_forbidden, renders_a_verdict
from system_03_search_agent.eval.rubric_grader import grade_run
from system_03_search_agent.eval.trace_source import RunRecord


def _rows():
    return [q.as_dict() for q in load_golden_dataset().queries]


def _judge(value: int):
    def judge(*, criterion, record, query):
        return value

    return judge


def _non_answer(row, outcome: str, text: str) -> RunRecord:
    return RunRecord(
        trace_id="t-" + row["id"] + outcome,
        query_id=row["id"],
        question=row["question"],
        outcome=outcome,
        answer_text=text,
        retrieval_hit_count=0,
    )


def test_p14a_asking_is_not_punished_where_the_dataset_expects_it():
    """F-5.2-RR-02. The harness graded the right answer as a failure.

    G-008's question is the single word "334". The dataset expects a
    clarifying question and accepts a refusal. The grader treated only
    `refuse` as a non-answering outcome, so `ask` fell through to the score
    path, could not reach 13, and failed with EMPTY notes while a refusal on
    the same row passed.

    Both must pass. Both are correct behaviour, and the dataset says so.
    """
    row = next(r for r in _rows() if r["expected_outcome"] == "ask")
    asked = grade_run(
        record=_non_answer(row, "ask", "Which record does 334 refer to?"),
        query=row,
        judge=_judge(0),
    )
    refused = grade_run(
        record=_non_answer(row, "refuse", "I could not find information on this"),
        query=row,
        judge=_judge(0),
    )
    assert asked.counts_as_pass, (
        f"{row['id']} expects {row['expected_outcome']!r} and asking scored "
        f"{asked.outcome} with notes {asked.notes}"
    )
    assert refused.counts_as_pass, "the row also accepts a refusal"
    assert asked.outcome == refused.outcome == "abstain"


def test_p14b_asking_where_an_answer_was_required_still_fails():
    """The inverse, so P14a cannot be satisfied by accepting every `ask`.

    Asking for clarification on a question the dataset says is answerable is
    not correct behaviour, and must not pass.
    """
    row = next(
        r for r in _rows() if r["acceptable_outcomes"] == ["answer"] and r["must_cite"]
    )
    asked = grade_run(
        record=_non_answer(row, "ask", "Could you clarify what you mean?"),
        query=row,
        judge=_judge(2),
    )
    assert not asked.counts_as_pass
    assert asked.outcome == "abstain"


def test_p14c_truncation_is_read_from_where_it_actually_lives():
    """F-5.2-RR-03. The check read a field a citation can never carry.

    `truncated` is on the `tool_result` payload. `CitationPayload` is
    `extra="forbid"`, so a citation carrying it would be rejected by the
    contract. The check was dead on all 20 KISSES rows that mandate it, and
    reported as checked rather than as unchecked, which is the worse half:
    a row read as clean on a constraint nothing evaluated.
    """
    row = next(r for r in _rows() if "undisclosed_truncation" in r["forbidden"])
    record = RunRecord(
        trace_id="t-trunc",
        query_id=row["id"],
        question=row["question"],
        outcome="answer",
        answer_text="Here are the results [1].",
        resolved_curies=list(row["must_resolve"]),
        citations=[
            {
                "source": "ncbi_gene",
                "source_id": "672",
                "source_url": u,
                "layer": 1,
                "entity_name": "BRCA1",
            }
            for u in row["must_cite"]
        ],
        claims=[{"text": "c", "citation_ids": ["1"]}],
        truncated=True,
        retrieval_hit_count=500,
    )
    violations, unchecked = check_forbidden(record=record, query=row)
    assert "undisclosed_truncation" in violations, (
        "a truncated result set with no disclosure must violate the constraint"
    )
    assert "undisclosed_truncation" not in unchecked


def test_p14d_disclosing_the_truncation_satisfies_the_constraint():
    """The populate-check for P14c. Without it, an always-violating checker passes."""
    row = next(r for r in _rows() if "undisclosed_truncation" in r["forbidden"])
    record = RunRecord(
        trace_id="t-trunc-ok",
        query_id=row["id"],
        question=row["question"],
        outcome="answer",
        answer_text="Showing the first 25 of 500 matching records [1].",
        citations=[{"source": "x", "source_id": "672", "source_url": "u", "layer": 1}],
        claims=[{"text": "c", "citation_ids": ["1"]}],
        truncated=True,
        retrieval_hit_count=500,
    )
    violations, _ = check_forbidden(record=record, query=row)
    assert "undisclosed_truncation" not in violations


def test_p14e_a_verdict_in_a_contrastive_clause_is_still_a_verdict():
    """F-5.2-RR-04, the reviewer's exact sentence.

    Sentence-level scoping let the attribution in the first clause launder
    the verdict in the second. The system is plainly the one classifying
    after "but in our assessment".
    """
    assert renders_a_verdict(
        "ClinVar lists three submissions, but in our assessment this variant "
        "is pathogenic."
    )


def test_p14f_a_verdict_in_other_words_is_still_a_verdict():
    """F-5.2-RR-04's second half. The vocabulary was too narrow."""
    for sentence in (
        "This variant is disease-causing.",
        "This variant is deleterious.",
        "The mutation is damaging.",
    ):
        assert renders_a_verdict(sentence), sentence


def test_p14g_attributed_reporting_is_still_admitted():
    """The populate-check for P14e and P14f, and the direction that matters.

    Widening the verdict vocabulary without checking this is how the check
    starts refusing the reporting the system exists to do. A grader that
    flags every ClinVar report is as broken as one that flags none, and it
    fails in a way nobody notices until the scores are inexplicable.
    """
    for sentence in (
        "ClinVar classifies this variant as Pathogenic.",
        "According to ClinVar, the variant is pathogenic.",
        "The variant is reported as pathogenic in ClinVar.",
        "BRCA1 is associated with hereditary breast and ovarian cancer.",
    ):
        assert not renders_a_verdict(sentence), sentence
