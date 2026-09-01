"""Build phase 6.2, T-6.2-15: a stripped clause must not leave a broken sentence.

The defect, observed live on develop before this change:

    BRCA1 (gene symbol: BRCA1 [1]. breast-ovarian cancer, familial,
    susceptibility to, 1 [2], pancreatic cancer ...

An unbalanced parenthetical and no verb. A clause runs from one marker to
the next, so the segment holding the second marker was
") is associated with familial cancer of breast ". Stripping it took the
closing bracket and the sentence's only verb with it.

The product-owner decision on 2026-09-01: drop the whole sentence. The cost
was weighed rather than discovered, and it is real, so the second arm below
pins the case where the rule must NOT fire, which is what stops the fix from
quietly deleting good answers.

These arms are OFFLINE and deterministic. They drive `run_grounding_pass`
directly with hand-built findings, so the behaviour is pinned regardless of
what a model happens to write on a given run. The live premise gate cannot
do that: F-6.2-04 recorded what happens when an arm waits for a defect to
show up on its own.
"""

from __future__ import annotations

from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import run_grounding_pass

# Passed to every call below, and NOT optional dressing.
# `claim_introduces_no_new_content` licenses a claim's words from the finding
# it cites PLUS the open part of the question the user asked. Omitting the
# question strips any clause containing the gene name, because "BRCA1" then
# comes from nowhere the checker recognises. The first draft of this file
# omitted it and its own control arm went red, which is what a control is
# for: the harness was wrong, not the product.
QUESTION = "Which diseases are associated with BRCA1?"


def _finding(ref: int, value: str) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field="name",
        field_value=value,
        source_url=f"https://www.ncbi.nlm.nih.gov/medgen/C{ref}",
        entity_type="Disease",
        curie=f"MedGen:C{ref}",
    )


def test_a_clause_stripped_from_the_middle_takes_its_sentence() -> None:
    """The reported defect, reproduced and then required not to happen.

    The narrative cites three findings. Only the first and third are given
    to the call, so the MIDDLE clause fails step 2 and is stripped, which is
    exactly the shape that produced the broken sentence live.

    What must NOT come back is a sentence that has lost its middle and kept
    its edges.
    """
    narrative = (
        "BRCA1 (gene symbol BRCA1 [1]) is associated with familial cancer "
        "of breast [2], and with Fanconi anemia [3]."
    )
    result = run_grounding_pass(
        narrative,
        [_finding(1, "BRCA1"), _finding(3, "Fanconi anemia")],
        core_ask_required=False,
        question=QUESTION,
    )

    assert "(" not in result.narrative or ")" in result.narrative, (
        f"an unbalanced parenthetical survived: {result.narrative!r}"
    )
    assert result.narrative.strip() == "", (
        f"the sentence lost a clause from its middle and should have been "
        f"dropped whole, got {result.narrative!r}"
    )
    assert result.claims == [], (
        "a dropped sentence must contribute no claims, or a citation chip "
        "points at prose nobody will read"
    )


def test_a_clause_stripped_from_the_end_keeps_the_sentence() -> None:
    """The case the rule must NOT fire on, and the reason it is narrow.

    "A [1], B [2], and C [3]" losing only C leaves "A [1], B [2]", which is
    a grammatical prefix. Dropping the sentence here would throw away two
    good, grounded claims to fix nothing.

    Without this arm the obvious over-broad implementation, drop the
    sentence whenever ANYTHING was stripped, would pass the arm above and
    silently make every partial answer smaller. That is the failure this
    file exists to prevent as much as the broken sentence is.
    """
    narrative = (
        "BRCA1 is associated with familial cancer of breast [1], "
        "Fanconi anemia [2], and pancreatic cancer [3]."
    )
    result = run_grounding_pass(
        narrative,
        [_finding(1, "familial cancer of breast"), _finding(2, "Fanconi anemia")],
        core_ask_required=False,
        question=QUESTION,
    )

    assert "familial cancer of breast" in result.narrative, (
        f"a surviving claim was discarded by a strip that came AFTER it: "
        f"{result.narrative!r}"
    )
    assert "Fanconi anemia" in result.narrative, result.narrative
    assert len(result.claims) == 2, (
        f"both grounded claims must survive a trailing strip, got "
        f"{[c.claim_text for c in result.claims]}"
    )


def test_a_dropped_sentence_leaves_no_gap_in_the_numbering() -> None:
    """Section 9.4 requires the display numbering to be dense.

    A sentence dropped AFTER its claims had been numbered would leave a
    hole: the reader sees [1] and [3] with no [2] anywhere. This is why the
    display slot is assigned at commit rather than as each clause is
    matched, and it is the half of the change least likely to be noticed if
    it regressed.
    """
    narrative = (
        "BRCA1 (gene symbol BRCA1 [1]) is associated with familial cancer "
        "of breast [2], and with Fanconi anemia [3]. "
        "Pancreatic cancer is also associated [4]."
    )
    result = run_grounding_pass(
        narrative,
        [
            _finding(1, "BRCA1"),
            _finding(3, "Fanconi anemia"),
            _finding(4, "Pancreatic cancer"),
        ],
        core_ask_required=False,
        question=QUESTION,
    )

    # The first sentence is dropped whole; the second stands on its own.
    assert "Pancreatic cancer" in result.narrative, result.narrative
    assert "[1]" in result.narrative, (
        f"the surviving sentence must be renumbered from 1, got {result.narrative!r}"
    )
    assert "[2]" not in result.narrative and "[3]" not in result.narrative, (
        f"a dropped sentence left a gap in the numbering: {result.narrative!r}"
    )


def test_a_fully_grounded_sentence_is_untouched() -> None:
    """The control. Nothing stripped, nothing dropped, nothing renumbered.

    Without this, every arm above is satisfiable by a change that simply
    discards more prose, which is the direction this fix could most easily
    go wrong in.
    """
    narrative = (
        "BRCA1 is associated with familial cancer of breast [1] "
        "and Fanconi anemia [2]."
    )
    result = run_grounding_pass(
        narrative,
        [_finding(1, "familial cancer of breast"), _finding(2, "Fanconi anemia")],
        core_ask_required=False,
        question=QUESTION,
    )

    assert "familial cancer of breast" in result.narrative
    assert "Fanconi anemia" in result.narrative
    assert len(result.claims) == 2
    assert result.stripped_count == 0, (
        f"nothing should have been stripped, got {result.stripped_count}"
    )
