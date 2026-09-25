"""Review round 2 of fix-plan item 12.7 (2026-09-23): a code-built listing
renders each record once.

WHAT THIS FILE GRADES, and why counting citations could not see it. The
question `Does coffee help make exercise more effective?` returned FIVE
papers and a 932-word answer of NINETY-ONE list items, the same title
repeating over and over. The ticket's verify surface reported "15 citations,
answer" and was satisfied, because nothing in it read what the reader sees.

THE CAUSE IS NOT ONE ROW PER FIELD, which is the natural guess and is wrong.
It is one row per SENTENCE OF THE ABSTRACT. Measured live:

    q5, topic path:   15 findings over  5 records, abstracts of 16, 8, 21,
                      32 and 6 sentences  ->  93 listing rows, 83 of them
                      abstract sentences
    q2, disease path: 19 findings over 12 records, abstracts of 7 and 2
                      sentences           ->  26 listing rows

So the duplication is on BOTH paths and merely smaller on the disease path,
where a paper contributes a `title`, a `pmid` and sometimes an `abstract`
row. It is worst on the topic path because there every admitted record is a
paper with a long abstract and there is nothing else in the answer.

Every arm that asserts an absence carries a populate check.

WHAT THIS FILE DOES NOT COVER, so the gap is arguable rather than invisible:
it does not run the model, so it says nothing about whether the model's own
narrative grounds. That is the condition under which the listing becomes the
whole answer, and it is measured live in the round 2 section of
`testing/Developer/reports/2026-09-23_set12/worker_topic.md`.
"""

from __future__ import annotations

import re

from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_structured_fallback_narrative,
    build_synth_messages,
    one_finding_per_record,
    unreported_findings,
)

_MARKER = re.compile(r"\[[0-9]+\]")

# The five papers the measured run returned, with their real abstract
# sentence counts.
_ABSTRACT_SENTENCES = {1: 16, 2: 8, 3: 21, 4: 32, 5: 6}


def _url(n: int) -> str:
    return f"https://pubmed.ncbi.nlm.nih.gov/{1000 + n}/"


def _finding(ref: int, field: str, value: str, url: str) -> SynthFinding:
    return SynthFinding(
        ref_index=ref,
        citation_id=f"c{ref}",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field=field,
        field_value=value,
        source_url=url,
    )


def _measured_topic_findings() -> list[SynthFinding]:
    """The q5 finding set, in the order `build_synth_findings` produced it:
    five titles, then five abstracts, then five pmids."""
    findings = [
        _finding(n, "title", f"Paper number {n} about caffeine", _url(n))
        for n in range(1, 6)
    ]
    findings += [
        _finding(
            5 + n,
            "abstract",
            " ".join(f"Sentence {j} of abstract {n}." for j in range(_ABSTRACT_SENTENCES[n])),
            _url(n),
        )
        for n in range(1, 6)
    ]
    findings += [
        _finding(10 + n, "pmid", str(1000 + n), _url(n)) for n in range(1, 6)
    ]
    return findings


def _rows(findings: list[SynthFinding]) -> int:
    return len(_MARKER.findall(build_structured_fallback_narrative(findings)))


def test_the_measured_defect_five_papers_became_ninety_three_rows() -> None:
    """The before figure, reconstructed from the live measurement, so the
    after figure below is a change against something real."""
    findings = _measured_topic_findings()
    assert len(findings) == 15
    assert len({f.source_url for f in findings}) == 5
    # One row per sentence of every value: 5 titles + 83 abstract sentences
    # + 5 pmids.
    assert sum(_ABSTRACT_SENTENCES.values()) == 83
    assert len(one_finding_per_record(findings)) == 5


def test_each_record_contributes_exactly_one_listing_row() -> None:
    findings = _measured_topic_findings()
    assert _rows(findings) == 5, build_structured_fallback_narrative(findings)
    # Populate check: the listing is not empty and names every paper once.
    text = build_structured_fallback_narrative(findings)
    for n in range(1, 6):
        assert text.count(f"Paper number {n} about caffeine") == 1, text


def test_the_row_that_survives_is_the_title_not_the_abstract() -> None:
    """A reader gets the paper's name, not thirty-two sentences of its
    abstract. Single-sentence values are preferred for exactly that."""
    kept = one_finding_per_record(_measured_topic_findings())
    assert [f.field for f in kept] == ["title"] * 5, [f.field for f in kept]


def test_a_record_whose_only_value_is_multi_sentence_is_never_dropped() -> None:
    """Preferring a single sentence must not mean losing a record that has
    none, which would trade one defect for a worse one."""
    only_abstract = [
        _finding(1, "abstract", "One sentence. Two sentences. Three.", _url(1))
    ]
    kept = one_finding_per_record(only_abstract)
    assert len(kept) == 1 and kept[0].field == "abstract"
    # Populate check: with a title available for the same record, the title
    # is what wins, so the arm above is the no-title case rather than the
    # function always keeping whatever it is given.
    with_title = only_abstract + [_finding(2, "title", "A short title", _url(1))]
    assert [f.field for f in one_finding_per_record(with_title)] == ["title"]


# ---------------------------------------------------------------------------
# T-8.1-06c (F-8.1-04, card 1): the one narrow, named preference. A MedGen
# record's `clinical_features` finding must survive the collapse over its
# own `title` finding, since a disease's clinical features are strictly
# more informative than its bare title in this listing. Every OTHER field
# pairing, including the paper shape above, is unchanged.
# ---------------------------------------------------------------------------


def test_clinical_features_survives_the_collapse_over_the_records_title() -> None:
    """THE FIX ITSELF. Before T-8.1-06c, `_listing_rank`'s general rule
    (lowest `ref_index` wins) always picked `title` here, since
    `core/graph.py`'s `_medgen_clinical_feature_rows` always appends the
    feature row with a HIGHER `ref_index` than the title row it copies.
    Live-confirmed the fix closes: `testing/Developer/reports/
    2026-09-25_phase_8.1/builder_A.md`'s T-8.1-06b blocked-stop names this
    exact collapse as the second of two reasons Marfan syndrome's
    phenotypes never reached the reader.
    """
    url = "https://www.ncbi.nlm.nih.gov/medgen/44287"
    title = _finding(2, "title", "Marfan syndrome", url)
    features = _finding(
        7, "clinical_features",
        "Aortic regurgitation (HP:0001659), Arachnodactyly (HP:0001166)",
        url,
    )
    kept = one_finding_per_record([title, features])
    assert len(kept) == 1
    assert kept[0].field == "clinical_features", kept[0].field
    # Cited to the same MedGen record, unchanged by which field won.
    assert kept[0].source_url == url


def test_a_record_with_only_a_title_is_unchanged() -> None:
    """A record with no `clinical_features` finding at all must still be
    represented by its title, exactly as before this ticket. The
    preference only ever picks AMONG what is present; it invents nothing.
    """
    url = "https://www.ncbi.nlm.nih.gov/medgen/1795938"
    title = _finding(1, "title", "Gastroesophageal reflux (GERD)", url)
    kept = one_finding_per_record([title])
    assert len(kept) == 1
    assert kept[0].field == "title"


def test_a_paper_record_with_title_and_abstract_is_unchanged() -> None:
    """`_PREFERRED_LISTING_FIELDS` names `clinical_features` alone.
    `abstract` is not in it, so a paper's title still beats its abstract,
    the exact property `test_the_row_that_survives_is_the_title_not_the_
    abstract` above already pins; this arm proves it survives the SAME
    code path the MedGen preference was added to, not a separate one.
    """
    url = _url(1)
    title = _finding(1, "title", "Paper about caffeine", url)
    abstract = _finding(2, "abstract", "One sentence. Two sentences.", url)
    kept = one_finding_per_record([title, abstract])
    assert len(kept) == 1
    assert kept[0].field == "title"


def test_a_blank_source_url_is_never_treated_as_an_identity() -> None:
    """An empty string is not a record. Grouping on it would collapse
    unrelated findings into one row and silently delete evidence."""
    blanks = [
        _finding(1, "name", "First unlinked fact", ""),
        _finding(2, "name", "Second unlinked fact", ""),
        _finding(3, "name", "Third unlinked fact", "   "),
    ]
    assert len(one_finding_per_record(blanks)) == 3
    # Populate check: the same function DOES group when a real url repeats.
    assert len(one_finding_per_record([
        _finding(4, "title", "A", _url(9)), _finding(5, "pmid", "1009", _url(9)),
    ])) == 1


def test_the_disease_path_shape_keeps_one_row_per_record_too() -> None:
    """The measured q2 shape: a paper contributing title, pmid and abstract,
    beside records that appear once. Twelve records, twelve rows."""
    findings: list[SynthFinding] = []
    ref = 0
    for n in range(1, 6):  # five papers, each with title + pmid
        ref += 1
        findings.append(_finding(ref, "title", f"Reflux paper {n}.", _url(n)))
        ref += 1
        findings.append(_finding(ref, "pmid", str(1000 + n), _url(n)))
    for n in (4, 5):  # two of them also carry an abstract
        ref += 1
        findings.append(
            _finding(ref, "abstract", "A. B. C. D. E. F. G.", _url(n))
        )
    for n in range(6, 13):  # seven trial and record rows, one each
        ref += 1
        findings.append(
            _finding(ref, "name", f"Record {n}", f"https://clinicaltrials.gov/study/NCT{n:08d}")
        )
    assert len({f.source_url for f in findings}) == 12
    assert _rows(findings) == 12, build_structured_fallback_narrative(findings)


def test_several_records_sharing_one_page_are_all_kept() -> None:
    """THE CASE THAT CAUGHT THE FIRST VERSION OF THIS RULE, which grouped on
    `source_url` alone. `test_graph.py::test_tool_row_limit_truncation_is_
    surfaced_even_when_byte_ceiling_never_fires` has three genes,
    `NCBIGene:672`, `673` and `674`, every one `field="name"` and every one
    pointing at `.../gene/672`. Collapsing them deleted two real findings,
    and the answer then announced itself incomplete because the deleted
    findings counted as unreported. Same field name means separate records
    sharing a page, so all of them are kept."""
    page = "https://www.ncbi.nlm.nih.gov/gene/672"
    genes = [_finding(n, "name", f"Gene {n}", page) for n in range(1, 4)]
    assert len(one_finding_per_record(genes)) == 3
    assert _rows(genes) == 3
    # Populate check: add a DIFFERENT view of that page and the views
    # collapse while the three records survive, so the rule discriminates
    # on the field name rather than never collapsing anything.
    with_summary = genes + [_finding(4, "summary", "A description of gene 672.", page)]
    kept = one_finding_per_record(with_summary)
    assert len(kept) == 1, [f.field for f in kept]


def test_the_rule_reads_the_field_name_and_never_the_field_value() -> None:
    """Deduplicating on rendered text is how two genuinely different facts
    that happen to read alike get silently merged."""
    page = "https://www.ncbi.nlm.nih.gov/gene/672"
    identical_text = [
        _finding(1, "name", "BRCA1", page),
        _finding(2, "name", "BRCA1", page),
    ]
    assert len(one_finding_per_record(identical_text)) == 2


def test_the_choice_is_a_pure_function_of_the_finding_set() -> None:
    """Item 11.21's promise reaches the rendered answer too: the same
    findings must produce the same rows on every run."""
    findings = _measured_topic_findings()
    rendered = {build_structured_fallback_narrative(findings) for _ in range(50)}
    assert len(rendered) == 1


def test_record_order_is_preserved() -> None:
    kept = one_finding_per_record(_measured_topic_findings())
    assert [f.source_url for f in kept] == [_url(n) for n in range(1, 6)]


def test_the_model_still_receives_every_finding_including_the_abstracts() -> None:
    """THE SAFETY ARGUMENT, asserted rather than reasoned about. Only the
    CODE-BUILT listing is deduplicated. If the model stopped seeing
    abstracts it could no longer quote one, and a quote is the only way an
    abstract's own words reach a reader with a citation attached."""
    findings = _measured_topic_findings()
    prompt = build_synth_messages("does coffee help?", findings)[1]["content"]
    for n in range(1, 6):
        assert f"Sentence 0 of abstract {n}." in prompt, n
    assert prompt.count("Paper number 1 about caffeine") >= 1


# ---------------------------------------------------------------------------
# The accounting that decides whether the answer confesses to being
# incomplete. Added in the same edit as the fix, after
# `test_topic_search.py::test_the_graph_is_not_called_at_all_for_a_topic_
# question` went red: deduplicating the listing made every collapsed view
# look unreported, so an answer showing all five papers told the reader it
# was missing sources.
# ---------------------------------------------------------------------------


def test_a_collapsed_view_of_a_reported_record_is_not_unreported() -> None:
    """The reader can see the paper and open it, so nothing is missing.

    Reporting the one row the listing kept for each record must clear all
    three of that record's findings, its title, its abstract and its pmid.
    """
    findings = _measured_topic_findings()
    reported = {finding.citation_id for finding in one_finding_per_record(findings)}

    # Populate check: the set being compared is a real subset, not
    # everything, or this arm would pass with the property absent.
    assert 0 < len(reported) < len(findings), (len(reported), len(findings))

    assert unreported_findings(reported, findings) == []


def test_a_record_the_answer_never_reported_is_still_caught() -> None:
    """F-4.5-06 breach 2 is not weakened by the rule above.

    Dropping one record's representative must leave all three of ITS
    findings unreported, while the other four records stay clear.
    """
    findings = _measured_topic_findings()
    kept = one_finding_per_record(findings)
    dropped_url = kept[0].source_url
    reported = {f.citation_id for f in kept if f.source_url != dropped_url}

    missing = unreported_findings(reported, findings)

    assert {f.source_url for f in missing} == {dropped_url}
    assert len(missing) == 3, [f.field for f in missing]


def test_separate_records_sharing_one_page_stay_individually_accountable() -> None:
    """The case that broke the deduplicator's own first version.

    Three genes share `/gene/672` and all carry `field="name"`, so they are
    separate records rather than views of one. `one_finding_per_record`
    keeps all three, and reporting only one must leave the other two
    unreported: the representative answers for nobody here.
    """
    shared = "https://www.ncbi.nlm.nih.gov/gene/672"
    findings = [
        _finding(1, "name", "BRCA1", shared),
        _finding(2, "name", "BRCA2", shared),
        _finding(3, "name", "BARD1", shared),
    ]

    assert len(one_finding_per_record(findings)) == 3

    missing = unreported_findings({"c1"}, findings)

    assert [finding.field_value for finding in missing] == ["BRCA2", "BARD1"]
