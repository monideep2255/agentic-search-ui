"""P13: the grader distinguishes grounded answers from fabricated ones.

Written before the implementation and watched failing, per cadence stage 5.

## The arm this file exists for

`test_p13a_the_paired_probe` is the check that finding F-5.2-RR-01 showed was
missing, and it is deliberately the FIRST arm here rather than the last.

That finding: the previous "a fabricated answer passes 0 of 50" arm graded
with a judge returning 0 for all three judged criteria. The five
deterministic criteria cap at 10 and the threshold is 13, so NOTHING could
pass under it. The arm proved arithmetic, not grading, and its result was
reported to the product owner as evidence that the fix worked.

The paired probe cannot be written that way. It grades a fabricated answer
and a correct answer with THE SAME judge and requires their scores to
DIFFER. A constant judge makes both sides equal and fails the arm, whatever
constant is chosen. That is the one shape of check a hollow judge cannot
satisfy.

## What "grounded" means here, and what it deliberately does not mean

The product owner's framing, 2026-08-30: the answer will always be
non-deterministic, but the content pulled must be consistent, current, and
USED in the answer, "not word for word".

So grounding is measured on ANCHORS, not on phrasing: the entity names,
identifiers and distinctive terms carried by the records that were actually
retrieved. An answer that says the same thing in different words still
anchors. An answer that says nothing about what was retrieved anchors on
nothing.

## Coverage: what these arms do NOT prove

- THEY DO NOT PROVE AN ANSWER IS TRUE. An answer repeating the retrieved
  entity names while drawing a false conclusion from them anchors perfectly
  and scores well here. Grounding is a correctness FLOOR, not a ceiling, and
  the judged criteria own what sits above it. Anyone reading a green run of
  this file as "the answer is right" has read it wrong.
- THEY DO NOT PROVE THE JUDGE IS ANY GOOD. There is still no judge
  implementation (T-5.2-09).
"""

from __future__ import annotations

from system_03_search_agent.eval.dataset import load_golden_dataset
from system_03_search_agent.eval.rubric_grader import RUBRIC_CRITERIA, grade_run
from system_03_search_agent.eval.trace_source import RunRecord


def _rows():
    return [q.as_dict() for q in load_golden_dataset().queries]


def _answer_row():
    return next(
        r
        for r in _rows()
        if r["acceptable_outcomes"] == ["answer"] and r["must_cite"] and r["must_resolve"]
    )


def _citations(row):
    """Citations carrying the record content a real trace supplies."""
    return [
        {
            "source": "ncbi_gene",
            "source_id": "672",
            "source_url": url,
            "layer": "layer_1_graph",
            "entity_name": "BRCA1",
            "claim_text": 'BRCA1 (NCBIGene:672), named "BRCA1 DNA repair associated"',
            "snapshot_date": "2026-04-22",
        }
        for url in row["must_cite"]
    ]


def _record(row, *, answer_text: str) -> RunRecord:
    """Identical in every respect except the prose. That is the point."""
    return RunRecord(
        trace_id="t-" + row["id"],
        query_id=row["id"],
        question=row["question"],
        outcome="answer",
        answer_text=answer_text,
        resolved_curies=list(row["must_resolve"]),
        citations=_citations(row),
        claims=[{"text": "a claim", "citation_ids": ["1"]}],
        assembly_context="GRCh38.p14",
        retrieval_hit_count=5,
    )


_FABRICATED = "Fabricated. [1]"
_GROUNDED = (
    "BRCA1, the gene known as BRCA1 DNA repair associated, is linked to "
    "hereditary breast and ovarian cancer syndrome [1]."
)
# Same facts, different words. Grounding must not require matching phrasing.
_PARAPHRASED = (
    "The DNA repair associated gene BRCA1 carries variants implicated in "
    "inherited breast and ovarian cancer risk [1]."
)


def _constant_judge(value: int):
    def judge(*, criterion, record, query):
        return value

    return judge


def test_p13a_the_paired_probe():
    """THE ARM THIS FILE EXISTS FOR.

    Same question, same judge, two answers. Their scores must differ.

    A constant judge cannot satisfy this, whatever constant it returns,
    because it contributes the same amount to both sides. So this arm cannot
    be made green by choosing a convenient judge, which is exactly how
    F-5.2-RR-01 came about.
    """
    row = _answer_row()
    for constant in (0, 1, 2):
        judge = _constant_judge(constant)
        fabricated = grade_run(
            record=_record(row, answer_text=_FABRICATED), query=row, judge=judge
        )
        grounded = grade_run(
            record=_record(row, answer_text=_GROUNDED), query=row, judge=judge
        )
        assert grounded.total > fabricated.total, (
            f"with a judge returning {constant} for every criterion, a grounded "
            f"answer scored {grounded.total} and a fabricated one scored "
            f"{fabricated.total}. The grader cannot tell them apart."
        )


def test_p13b_a_fabricated_answer_scores_zero_on_evidence_quality():
    """Asserted on the CRITERION, not the total.

    Asserting on the total lets a threshold change mask a grounding
    regression. The criterion is the thing that must be zero.
    """
    row = _answer_row()
    result = grade_run(
        record=_record(row, answer_text=_FABRICATED),
        query=row,
        judge=_constant_judge(2),
    )
    assert result.criteria["evidence_quality"] == 0


def test_p13c_a_grounded_answer_scores_two_on_evidence_quality():
    row = _answer_row()
    result = grade_run(
        record=_record(row, answer_text=_GROUNDED),
        query=row,
        judge=_constant_judge(2),
    )
    assert result.criteria["evidence_quality"] == 2


def test_p13d_grounding_does_not_require_matching_phrasing():
    """The product owner's "not word for word" made into an assertion.

    The paraphrase shares no sentence with the record's own wording. It
    anchors on the entity and the record's name, which is what grounding is
    supposed to key on.
    """
    row = _answer_row()
    result = grade_run(
        record=_record(row, answer_text=_PARAPHRASED),
        query=row,
        judge=_constant_judge(2),
    )
    assert result.criteria["evidence_quality"] == 2


def test_p13e_the_deterministic_half_alone_separates_them():
    """The separation must survive with NO judge contribution at all.

    If the deterministic criteria cannot tell the two apart on their own,
    then the judge is still load-bearing for correctness and the whole point
    of this round is unmet.
    """
    row = _answer_row()
    judged = {"intent_understanding", "cross_database_synthesis", "safety_and_limits"}
    deterministic = [c for c in RUBRIC_CRITERIA if c not in judged]

    judge = _constant_judge(0)
    fabricated = grade_run(
        record=_record(row, answer_text=_FABRICATED), query=row, judge=judge
    )
    grounded = grade_run(
        record=_record(row, answer_text=_GROUNDED), query=row, judge=judge
    )
    fab_sub = sum(fabricated.criteria[c] for c in deterministic)
    gnd_sub = sum(grounded.criteria[c] for c in deterministic)
    assert gnd_sub > fab_sub, (
        f"deterministic subtotal: grounded {gnd_sub}, fabricated {fab_sub}. "
        "The judge is still deciding correctness."
    )
