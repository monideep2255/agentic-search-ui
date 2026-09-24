"""Items 12.9, 12.10 and 12.12 (2026-09-23): quote-anchored synthesis.

The product owner's decision: "It should synthesize and ensure that it is
synthesizing from the paper." A sentence in the model's own words may now
survive the grounding pass when it carries the record's exact supporting
words as `[N: "words"]`, and passes four exact checks
(`grounding.synthesis_is_supported`).

WHAT THIS FILE EXERCISES:

- Acceptance: a reworded sentence with a real quote survives, keeps its
  quote on the claim, and loses the quote from the shown text.
- Every rejection the design names: a quote not in the record, a word the
  quote lacks even when the wider record has it, a flipped negation, an
  invented number, a short record value inside a long invented quote, a
  verdict word, and a reworded sentence with no quote at all.
- A quote containing a full stop, which must not split the sentence.
- Item 12.12's three rules: an orphan connective, an unpaired quote mark, a
  continuation opener with nothing before it; and the lowercase excerpt
  that is capitalised rather than dropped.
- The restatement drop, against the row the listing shows.

WHAT IT DELIBERATELY OMITS: the live model. Whether a real model writes the
quoted form is measured by the live runs recorded in the fix plan, not here.
Reordering the words of one quote to change who does what to whom is the
residual risk the design states, and no arm here pretends to catch it.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.synthesis import grounding
from system_03_search_agent.synthesis.answer_layout import drop_record_restatements
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import (
    extract_evidence_quotes,
    run_grounding_pass,
    synthesis_is_supported,
)

ABSTRACT = (
    "Caffeine consistently enhances endurance performance in trained athletes. "
    "Caffeine had no effect on maximal strength in 12 of the studies reviewed. "
    "It also improves muscular strength in some protocols."
)
URL = "https://pubmed.ncbi.nlm.nih.gov/100/"


def _finding(ref: int, value: str, field: str = "abstract", url: str = URL) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_2_ncbi_api",
        tool="ncbi_efetch",
        field=field,
        field_value=value,
        source_url=url,
        entity_type="Publication",
        curie=f"pubmed:{100 + ref}",
    )


PAPER = _finding(1, ABSTRACT)
# Every real PubMed record carries its title as a finding on the same page;
# since item 12.16 part 4 a reworded sentence is held to naming its record's
# title (`grounding._names_its_record`), so the fixture carries one too.
PAPER_TITLE = _finding(20, "Caffeine and endurance exercise performance", field="title")
QUESTION = "Does coffee help make exercise more effective?"


def _ground(narrative: str, findings: list[SynthFinding] | None = None):
    return run_grounding_pass(narrative, findings or [PAPER, PAPER_TITLE], question=QUESTION)


# --------------------------------------------------------------- acceptance


GOOD = (
    'Studies report that caffeine enhanced endurance performance '
    '[1: "Caffeine consistently enhances endurance performance"].'
)


def test_a_reworded_sentence_with_its_record_words_survives() -> None:
    assert not grounding.ground_claim(
        "Studies report that caffeine enhanced endurance performance", ABSTRACT
    ), "populate-check: the strict path must reject this sentence, or the arm tests nothing new"
    result = _ground(GOOD)
    assert result.grounded, result
    assert result.narrative == "Studies report that caffeine enhanced endurance performance [1]."
    assert result.claims[0].evidence_quote == "Caffeine consistently enhances endurance performance"


def test_the_arm_above_fails_when_the_synthesis_path_is_off(monkeypatch) -> None:
    """Mutation proof: the acceptance arm exercises the new path, not the old."""
    monkeypatch.setattr(grounding, "synthesis_is_supported_by", lambda *a, **k: False)
    assert not _ground(GOOD).grounded


def test_a_strict_claim_carries_no_quote() -> None:
    result = _ground("Caffeine consistently enhances endurance performance in trained athletes [1].")
    assert result.grounded
    assert result.claims[0].evidence_quote is None


# ---------------------------------------------------------------- rejection


@pytest.mark.parametrize(
    ("narrative", "why"),
    [
        (
            'Caffeine enhances endurance performance [1: "caffeine reliably boosts endurance"].',
            "the quote is not in the record",
        ),
        (
            'Caffeine enhances muscular strength [1: "Caffeine consistently enhances endurance performance"].',
            "muscular and strength are in the record but not in the quote",
        ),
        (
            'Caffeine had an effect on maximal strength [1: "Caffeine had no effect on maximal strength"].',
            "the quote denies what the sentence asserts",
        ),
        (
            (
                'Caffeine had no effect on maximal strength in 40 studies '
                '[1: "Caffeine had no effect on maximal strength"].'
            ),
            "40 is not in the quote",
        ),
        (
            (
                'Yes, caffeine enhances endurance performance '
                '[1: "Caffeine consistently enhances endurance performance"].'
            ),
            "yes is a verdict and is not a reporting word",
        ),
        (
            "Studies report that caffeine enhanced endurance performance [1].",
            "a reworded sentence with no quote is judged strictly, as before",
        ),
    ],
)
def test_a_synthesis_the_quote_does_not_carry_is_stripped(narrative: str, why: str) -> None:
    assert not _ground(narrative).grounded, why


def test_the_same_negative_sentence_with_its_negation_survives() -> None:
    """Populate-check for the polarity arm: it is the negation, not the rest."""
    result = _ground(
        'Caffeine had no effect on maximal strength [1: "Caffeine had no effect on maximal strength"].'
    )
    assert result.grounded


def test_a_short_value_inside_a_long_invented_quote_certifies_nothing() -> None:
    gene = _finding(2, "BRCA1", field="symbol", url="https://www.ncbi.nlm.nih.gov/gene/672")
    quote = "BRCA1 causes every cancer known to medicine"
    assert grounding.ground_claim(quote, gene.field_value), (
        "populate-check: the two-way rule WOULD accept this quote, which is why the check is one-way"
    )
    assert not synthesis_is_supported("BRCA1 causes every cancer", quote, gene)


def test_a_quote_with_a_full_stop_does_not_split_the_sentence() -> None:
    narrative = (
        "Caffeine enhanced endurance performance but not maximal strength "
        '[1: "enhances endurance performance in trained athletes. Caffeine had no effect on maximal strength"].'
    )
    rewritten, quotes = extract_evidence_quotes(narrative)
    assert "[1#0]" in rewritten and len(quotes) == 1
    result = _ground(narrative)
    assert result.grounded, result
    assert "trained athletes" not in result.narrative


# ------------------------------------------------------------- item 12.12


def test_the_measured_orphan_fragment_is_dropped() -> None:
    """The caffeine answer's third paragraph, measured on 2026-09-23."""
    value = (
        'The review concluded "caffeine may help; however, recent work suggests no effect '
        'on maximal ability, but enhanced endurance or resistance to fatigue".'
    )
    paper = _finding(3, value)
    fragment = (
        "however, recent work suggests no effect on maximal ability, but enhanced endurance "
        'or resistance to fatigue" [3].'
    )
    assert grounding.ground_claim(fragment.rsplit(" [", 1)[0], value), "populate-check: it is verbatim"
    assert not _ground(fragment, [paper]).grounded


def test_an_unpaired_quote_mark_alone_drops_the_sentence() -> None:
    value = 'enhanced endurance or resistance to fatigue". Caffeine is widely used.'
    paper = _finding(4, value)
    assert not _ground('Enhanced endurance or resistance to fatigue" [4].', [paper]).grounded
    assert _ground("Enhanced endurance or resistance to fatigue [4].", [paper]).grounded


def test_a_list_continuation_goes_as_a_restatement_not_by_its_first_word() -> None:
    """Item 12.16 part 4: the "Another ..." word list is gone.

    "Another is titled X" only repeats a title the list below the answer
    shows, so the restatement rule drops it by structure, whatever word it
    opens on. The records stay cited by their list rows.
    """
    first = _finding(5, "Genetic variants in Ashkenazi Jews", field="title", url="https://pubmed.ncbi.nlm.nih.gov/5/")
    second = _finding(6, "BRCA1 and BRCA2 founder mutations", field="title", url="https://pubmed.ncbi.nlm.nih.gov/6/")
    findings = [first, second]
    alone = _ground("Another is titled BRCA1 and BRCA2 founder mutations [6].", findings)
    assert alone.grounded, "populate-check: the grounding pass no longer judges its first word"
    _, dropped = drop_record_restatements(alone, findings)
    assert dropped == 1
    paired = _ground(
        "One is titled Genetic variants in Ashkenazi Jews [5]. "
        "Another is titled BRCA1 and BRCA2 founder mutations [6].",
        findings,
    )
    _, dropped = drop_record_restatements(paired, findings)
    assert dropped == 2, "a restatement paragraph goes whole, and the list names both papers"


def test_the_back_half_of_a_record_sentence_is_dropped_whatever_word_opens_it() -> None:
    """Item 12.16 part 4: decided by where the words sit in the record.

    The opening words below were never on any list: the rule reads the record,
    so it covers phrasings nobody thought of.
    """
    cases = [
        ("Caffeine may help; however, recent work suggests enhanced endurance in athletes.",
         "however, recent work suggests enhanced endurance in athletes"),
        ("Caffeine may help; however, recent work suggests enhanced endurance in athletes.",
         "recent work suggests enhanced endurance in athletes"),
        ("Statins lower the risk, so that clinical judgment remains necessary.",
         "so that clinical judgment remains necessary"),
        ("Caffeine helps sprinters, particularly those who train in the morning.",
         "particularly those who train in the morning"),
    ]
    for value, excerpt in cases:
        paper = _finding(9, value)
        assert grounding.ground_claim(excerpt, value), f"populate-check: {excerpt!r} is verbatim"
        assert not _ground(f"{excerpt} [9].", [paper]).grounded, excerpt


def test_the_same_words_starting_a_record_sentence_stand_capitalised() -> None:
    """The populate-check for the rule above: words, not position, did NOT decide."""
    paper = _finding(9, "Caffeine may help. Recent work suggests enhanced endurance in athletes.")
    result = _ground("recent work suggests enhanced endurance in athletes [9].", [paper])
    assert result.grounded
    assert result.narrative.startswith("Recent work suggests"), result.narrative


def test_a_whole_record_sentence_written_lowercase_is_capitalised() -> None:
    result = _ground("caffeine consistently enhances endurance performance in trained athletes [1].")
    assert result.grounded
    assert result.narrative.startswith("Caffeine consistently")


def test_a_subjectless_clause_from_mid_record_is_dropped() -> None:
    """It used to be capitalised into "Consistently enhances ...", a fragment."""
    assert not _ground("consistently enhances endurance performance in trained athletes [1].").grounded


def test_the_record_fragment_rule_can_fail(monkeypatch) -> None:
    """Mutation proof: with the rule off, the measured fragment ships."""
    monkeypatch.setattr(grounding, "_starts_inside_record_sentence", lambda *a, **k: False)
    paper = _finding(9, "Statins lower the risk, so that clinical judgment remains necessary.")
    assert _ground("so that clinical judgment remains necessary [9].", [paper]).grounded


# ------------------------------------------------------- restatement drop


def test_a_sentence_from_the_abstract_is_not_a_restatement_of_the_title_row() -> None:
    """The listing shows the TITLE; a sentence from the abstract adds to it."""
    title = _finding(7, "Caffeine and exercise performance", field="title")
    abstract = _finding(8, ABSTRACT)
    result = _ground(
        "Caffeine consistently enhances endurance performance in trained athletes [8].",
        [title, abstract],
    )
    kept, dropped = drop_record_restatements(result, [title, abstract])
    assert dropped == 0 and kept.claims, kept


def test_a_title_restatement_is_still_dropped() -> None:
    title = _finding(7, "Caffeine and exercise performance", field="title")
    abstract = _finding(8, ABSTRACT)
    result = _ground("One is titled Caffeine and exercise performance [7].", [title, abstract])
    assert result.grounded, "populate-check: the sentence must ground before it can be dropped"
    _, dropped = drop_record_restatements(result, [title, abstract])
    assert dropped == 1


def test_a_quoted_synthesis_is_never_a_restatement() -> None:
    result = _ground(GOOD)
    _, dropped = drop_record_restatements(result, [PAPER])
    assert dropped == 0


