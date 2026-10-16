"""Card 101, the last slices (2026-10-15): where a record sentence ends.

The design is `testing/Developer/reports/2026-10-15_card101/design.md`. Develop's
record units stay exactly as they are; each break between two of them is
graded `hard`, `mark` (inside a quotation or bracket the record opens and
closes) or `abbrev` (after an abbreviation-shaped token). A copy after a soft
break is a cut. The run the sentence check reads is glued across soft breaks.
When no run within 600 characters exists, the sentence is held, never checked
against a bare quote.

Every case is a fixture from the 8 October judge's and adversary's own
reproductions (their ids are in each case's id), run through the real
`run_grounding_pass` on its first pass with a `candidate_sink` and no model.
They are fixtures, not prompts: no test question reaches a prompt.

Each case states what is SHOWN with the check approving nothing, what is SENT
to the check, and the exact run each item carries.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.synthesis import grounding
from system_03_search_agent.synthesis.findings import SynthFinding
from system_03_search_agent.synthesis.grounding import (
    SynthesisCandidate,
    run_grounding_pass,
)

QUESTION = "What does the paper say?"


def _finding(value: str, ref: int = 1) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c-{ref}",
        layer="layer_2_ncbi_api",
        tool="ncbi_efetch",
        field="abstract",
        field_value=value,
        source_url=f"https://pubmed.ncbi.nlm.nih.gov/{ref}/",
        entity_type="Publication",
        curie=f"pubmed:{ref}",
    )


def _first_pass(narrative: str, value: str):
    sink: list[SynthesisCandidate] = []
    result = run_grounding_pass(
        narrative, [_finding(value)], core_ask_required=False, question=QUESTION, candidate_sink=sink
    )
    return sink, result


def _copy(copy: str, value: str):
    """Copy `copy` as a marked clause of its record, first pass."""
    assert copy in value, "populate-check: the copy is in the record"
    return _first_pass(f"{copy} [1].", value)


def _develop_unit_count(value: str) -> int:
    return len([p for p in grounding._RECORD_SENTENCE_BOUNDARY.split(value) if p.strip()])


def _longest_develop_unit(value: str) -> int:
    return max(len(p) for p in grounding._RECORD_SENTENCE_BOUNDARY.split(value) if p.strip())


def _assert_units_are_develops(value: str) -> None:
    units = grounding._record_units(value)
    assert len(units) == _develop_unit_count(value)
    assert max(len(text) for text, _ in units) == _longest_develop_unit(value)


# ------------------------------------------------ slice 2: marks grade a break

QUOTATION = (
    'Advertisers claimed that "this drug is a miracle. Drug X cures cancer. It is safe." '
    "Regulators found every claim false."
)
BRACKET = (
    "An early uncontrolled report (since retracted. Ribavirin cured every infant. "
    "No controls were used.) prompted this trial. The outcome was null."
)
INCH = (
    'A 5" needle was used. The company claimed "Drug X cures cancer. Drug X is safe in children. '
    'It is cheap" but trials disagreed.'
)


@pytest.mark.parametrize(
    ("value", "copy", "frame"),
    [
        (QUOTATION, "Drug X cures cancer", "Advertisers claimed that"),
        (BRACKET, "Ribavirin cured every infant", "since retracted"),
        (INCH, "Drug X is safe in children", "The company claimed"),
    ],
    ids=["A4-101-02 quotation", "A4-101-02 bracket", "A-101N-01 inch mark before the quotation"],
)
def test_a_copy_inside_a_quotation_or_bracket_is_a_cut_read_with_its_frame(
    value: str, copy: str, frame: str
) -> None:
    """The person's words: a claim a paper only quotes, to reject it, is never
    printed as the paper's finding, and the check reads the quotation it sits in.

    MUTATION PROOF: `_record_breaks` grading every break `hard` (marks
    ignored) turns all three red: the copy is shown with no item."""
    _assert_units_are_develops(value)
    sink, result = _copy(copy, value)
    assert result.sentences == (), result.sentences
    assert len(sink) == 1, sink
    assert frame in sink[0].quotes[0], sink[0].quotes
    assert copy in sink[0].quotes[0]


@pytest.mark.parametrize(
    ("opener", "closer"),
    [("'", "'"), ("‘", "’"), ("«", "»"), ("“", "”")],
    ids=["straight single", "curly single", "guillemets", "curly double"],
)
def test_every_quote_style_that_pairs_grades_its_breaks_and_a_later_whole_copy_still_shows(
    opener: str, closer: str
) -> None:
    """A-101N-02 and A-101N-03: the category rule covers a style nobody
    listed, and develop's later whole copy is not lost.

    MUTATION PROOF: `_mark_spans` reading only the double straight quote
    (the Ps and Pi branch removed) turns the three non-straight-double
    styles red."""
    value = (
        f"The company claimed {opener}Drug X cures cancer. Drug X is safe in children. "
        f"It is cheap{closer} but trials disagreed. Mortality was unchanged in the trial."
    )
    _assert_units_are_develops(value)
    sink, result = _copy("Drug X is safe in children", value)
    assert result.sentences == () and len(sink) == 1
    assert "The company claimed" in sink[0].quotes[0]
    sink, result = _copy("Mortality was unchanged in the trial", value)
    assert sink == [] and len(result.sentences) == 1, (sink, result.sentences)


@pytest.mark.parametrize(
    ("opener", "closer"), [("„", "“"), ("”", "”")], ids=["German", "Swedish"]
)
def test_the_two_styles_that_cannot_pair_stay_as_develop_shows_them(opener: str, closer: str) -> None:
    """The named residual: „ is an opener and “ an opener too, ” closes twice.
    The claim shows as on develop. Pinned so a later change is seen."""
    value = (
        f"The company claimed {opener}Drug X cures cancer. Drug X is safe in children. "
        f"It is cheap{closer} but trials disagreed. Mortality was unchanged in the trial."
    )
    _assert_units_are_develops(value)
    sink, result = _copy("Drug X is safe in children", value)
    assert sink == [] and len(result.sentences) == 1, (sink, result.sentences)


COHORTS = " ".join(
    f"Cohort {i} enrolled {100 + i} infants in the second phase of the trial." for i in range(9)
)


@pytest.mark.parametrize(
    "head",
    [
        "Background (see the 2019 guideline. ",
        'Background: "the 2019 guideline. ',
        "Background: “the 2019 guideline. ",
        "Background: the 2019 guideline. ",
    ],
    ids=["open bracket", "open straight quote", "open curly quote", "no mark"],
)
def test_a_stray_unclosed_mark_holds_nothing_and_a_later_whole_copy_shows(head: str) -> None:
    """A-101N-13 and A-101N-06: an opener the record never closes changes
    nothing; develop's later whole copy still shows, with no check.

    MUTATION PROOF: `_mark_spans` returning on the first pass without
    ignoring the unclosed openers turns the three marked heads red."""
    value = head + COHORTS + " Mortality was unchanged in the treated group."
    _assert_units_are_develops(value)
    assert _develop_unit_count(value) == 11
    sink, result = _copy("Mortality was unchanged in the treated group", value)
    assert sink == [] and len(result.sentences) == 1, (sink, result.sentences)


def test_apostrophes_possessives_and_a_half_open_interval_open_nothing() -> None:
    """Principle 4: ambiguity falls back to develop's reading."""
    value = "The patients' outcomes didn't change. Children's doses were lower. The 'gold standard' test was used."
    sink, result = _copy("Children's doses were lower", value)
    assert sink == [] and len(result.sentences) == 1
    value = "Risk fell in the [0.5, 1.2) group. Mortality was unchanged in the trial."
    sink, result = _copy("Mortality was unchanged in the trial", value)
    assert sink == [] and len(result.sentences) == 1


def test_the_unit_that_opens_a_quotation_follows_a_hard_break_the_tail_units_follow_soft_ones() -> None:
    """Only the tail is dangerous (design, `is_whole_record_sentence`): the
    unit that holds the opening mark is a head and keeps develop's grade."""
    grades = [grade for _, grade in grounding._record_units(QUOTATION)]
    assert grades == ["start", "mark", "mark"], grades


# ------------------------------------- slice 3: abbreviations grade a break

SALMONELLA = "No isolates of S. Typhimurium carried the blaCTX-M gene. Resistance was rare."
VACCINE = "It is unproven that the U.S. FDA-approved vaccine prevents bronchiolitis in infants. Trials continue."
DENIAL = "There is no evidence that aspirin prevents colorectal cancer in adults."
HEPATITIS = (
    "Patients were screened for hepatitis B. Many had hepatitis A. Some had hepatitis C. "
    "Controls were tested for hepatitis B. Levels were low for vitamin D. "
    f"The cohort lacked vitamin D. {DENIAL} Treatment is usually symptomatic."
)
ARMS = " ".join(
    f"Infants in cohort {i} were randomized to treatment arm {letter}."
    for i, letter in enumerate("ABCDEFGHIJKL")
)
ARMS_DENIAL = (
    "There was no evidence that azithromycin shortened the illness in infants with bronchiolitis."
)


@pytest.mark.parametrize(
    ("value", "copy", "frame"),
    [
        (SALMONELLA, "Typhimurium carried the blaCTX-M gene", "No isolates of S. Typhimurium carried"),
        (VACCINE, "FDA-approved vaccine prevents bronchiolitis in infants", "It is unproven that"),
        (HEPATITIS, DENIAL.rstrip("."), "The cohort lacked vitamin D. There is no evidence that"),
        ("The cohort was tested for vitamin D. Then the drug cured nobody.", "Then the drug cured nobody", "vitamin D. Then"),
    ],
    ids=["A4-101-01 S.", "A4-101-01 U.S.", "J-101N-04 the denial after vitamin D.", "vitamin D. Then"],
)
def test_a_copy_after_an_abbreviation_shaped_break_is_a_cut_read_with_its_head(
    value: str, copy: str, frame: str
) -> None:
    """The tail of a sentence that an abbreviation seemed to end shows only
    after the check read the paper's whole sentence, its negation included.

    MUTATION PROOF: `_record_breaks` never grading `abbrev` turns all four
    red: the tail is shown with no item."""
    _assert_units_are_develops(value)
    sink, result = _copy(copy, value)
    assert result.sentences == (), result.sentences
    assert len(sink) == 1, sink
    assert frame in sink[0].quotes[0], sink[0].quotes


def test_a_chain_of_abbreviation_breaks_never_grows_the_run_and_the_faithful_half_is_sent_not_held() -> None:
    """J-101N-04: a chain stays 8 units, the denial's run carries "no
    evidence", the faithful half is sent as a three-unit run of 95 characters.

    MUTATION PROOF: the abbreviation glue iterated (a loop in place of the
    single step) makes the faithful half's run longer than three units."""
    assert len(grounding._record_units(HEPATITIS)) == _develop_unit_count(HEPATITIS) == 8
    sink, result = _copy("Levels were low for vitamin D", HEPATITIS)
    assert result.sentences == () and len(sink) == 1, (sink, result.sentences)
    assert sink[0].quotes == (
        "Controls were tested for hepatitis B. Levels were low for vitamin D. The cohort lacked vitamin D.",
    ), sink[0].quotes
    assert len(sink[0].quotes[0]) <= 100


def test_a_reworded_sentence_over_a_lettered_chain_reads_the_denial() -> None:
    """A-101N-08: twelve "arm A." to "arm L." sentences, then the paper's
    denial. The reworded sentence's run carries the negation, and the record
    is 14 units as on develop."""
    value = f"{ARMS} {ARMS_DENIAL} Results were consistent."
    _assert_units_are_develops(value)
    assert len(grounding._record_units(value)) == _develop_unit_count(value) == 14
    sink, result = _first_pass(
        'Azithromycin cut the illness in infants with bronchiolitis [1: "azithromycin shortened '
        'the illness in infants with bronchiolitis"].',
        value,
    )
    assert result.sentences == () and len(sink) == 1, (sink, result.sentences)
    assert "There was no evidence that azithromycin shortened" in sink[0].quotes[0]
    assert sink[0].quotes[0].count("treatment arm") == 1, sink[0].quotes  # one unit, not a chain


def test_a_whole_copy_after_a_lettered_chain_is_sent_with_two_units_not_held() -> None:
    """A-101N-08, the copy half: A-101N-05's cost, bounded. One extra item
    with a two-unit run; never a hold past 600 and never a chain."""
    value = f"{ARMS} Mortality was unchanged in the treated group."
    _assert_units_are_develops(value)
    sink, result = _copy("Mortality was unchanged in the treated group", value)
    assert result.sentences == () and len(sink) == 1
    assert sink[0].quotes == (
        (
            "Infants in cohort 11 were randomized to treatment arm L. "
            "Mortality was unchanged in the treated group."
        ),
    ), sink[0].quotes


def test_a_two_letter_word_before_a_full_stop_is_not_an_abbreviation() -> None:
    """A-101N-11: "Dr. A. Smith." keeps develop's reading. The copy after
    "Smith." follows a hard break and shows.

    MUTATION PROOF: `_ABBREVIATION_SHAPE` widened to any word turns it red."""
    value = "Samples were sent to Dr. A. Smith. Results were negative."
    _assert_units_are_develops(value)
    assert len(grounding._record_units(value)) == 4
    sink, result = _copy("Results were negative", value)
    assert sink == [] and len(result.sentences) == 1, (sink, result.sentences)


def test_a_sentence_that_ends_on_a_lowercase_or_long_word_is_a_hard_break() -> None:
    value = "Aspirin was given with food. Mortality was unchanged in the trial."
    sink, result = _copy("Mortality was unchanged in the trial", value)
    assert sink == [] and len(result.sentences) == 1


# --------------------------- slice 4: the writer's reply names the cut

ST_JUDE = "No children treated at St. Jude developed the infection. Follow-up was complete."
VS = "Survival in patients given drug X vs. Placebo-treated patients improved by 20%. No other outcome differed."


@pytest.mark.parametrize(
    ("value", "narrative", "whole"),
    [
        (ST_JUDE, "No children treated at St. Jude developed the infection [1].",
         "No children treated at St. Jude developed the infection."),
        (VS, "Survival in patients given drug X vs. Placebo-treated patients improved by 20% [1].",
         "Survival in patients given drug X vs. Placebo-treated patients improved by 20%."),
    ],
    ids=["J-101N-06 St. Jude", "A-101N-15 vs. Placebo"],
)
def test_a_faithful_copy_the_writers_splitter_cut_at_an_abbreviation_is_read_whole(
    value: str, narrative: str, whole: str
) -> None:
    """The writer copied one paper sentence; the writer's splitter cut it at
    "St." or "vs.", stripped the head, and left a tail that looks like a
    whole record sentence. The tail is sent with the paper's whole sentence
    and not shown. Develop showed "Jude developed the infection".

    MUTATION PROOF: `_joined_to_cut_head` returning None turns both red: the
    tail is shown with no item."""
    sink, result = _first_pass(narrative, value)
    assert result.sentences == (), result.sentences
    assert len(sink) == 1, sink
    assert sink[0].quotes == (whole,), sink[0].quotes


def test_an_unmarked_reply_sentence_that_is_not_in_the_record_joins_to_nothing() -> None:
    """Framing control: "The trial was large." is stripped, but joined to the
    copy it is not one stretch of the record, so the whole copy shows.

    MUTATION PROOF: the contiguity test in `_joined_to_cut_head` removed
    (always joined) turns this red."""
    sink, result = _first_pass(
        "The trial was large. Jude developed the infection [1].",
        "No children treated at St. Jude developed the infection. Follow-up was complete.",
    )
    assert sink == [] and len(result.sentences) == 1, (sink, result.sentences)


def test_two_marked_whole_copies_in_a_row_both_show() -> None:
    """The previous reply sentence carried a marker: it is no cut head."""
    sink, result = _first_pass(
        "Resistance was rare [1]. Mortality was unchanged in the trial [1].",
        "Resistance was rare. Mortality was unchanged in the trial.",
    )
    assert sink == [] and len(result.sentences) == 2, (sink, result.sentences)


# ----------------------------- slice 5: the clause's own run comes first

ADULT_THEN_INFANT = (
    "Azithromycin shortened the illness in adults with asthma. "
    "There was no evidence that azithromycin shortened the illness in infants with bronchiolitis."
)


def test_a_valid_quote_in_another_sentence_does_not_win_over_the_clauses_own_words() -> None:
    """A-101N-10: the writer's quote is found first in an adult sentence; the
    copied clause is the infant sentence's words. The check must read the
    sentence the clause was cut from, with its denial.

    MUTATION PROOF: trying the quote before the clause's own words (the old
    order) turns this red: the item carries the adult sentence."""
    sink, result = _first_pass(
        "Azithromycin shortened the illness in infants with bronchiolitis "
        '[1: "azithromycin shortened the illness"].',
        ADULT_THEN_INFANT,
    )
    assert result.sentences == () and len(sink) == 1, (sink, result.sentences)
    assert sink[0].quotes == (
        "There was no evidence that azithromycin shortened the illness in infants with bronchiolitis.",
    ), sink[0].quotes
