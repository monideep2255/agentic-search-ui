"""Tests for `core.accession`, the NCBI accession parsing and call planning helpers.

No network and no model anywhere in this file: every function under test is a
pure function of its arguments, the same discipline `test_coordinate_window.py`
and `test_breadth_plan.py` pin for their own modules.

Coverage statement, per `goal-contracts`: each public function gets a valid,
an invalid and a null arm where the function's own shape admits one, plus at
least one populate check, an assertion that fails if the behaviour it names
were removed, not merely one that happens to pass. The clearest instances:
`test_parse_finds_the_leftmost_accession_even_when_its_kind_sorts_last`
proves position, not `ACCESSION_KINDS` order, decides the winner; the
`plan_summary_calls` mixed-validity test drops a non-uid while keeping a
valid one in the SAME call, so a filter that kept or dropped everything would
both fail it; and `test_disclosure_deduplicates_repeated_ids_across_linknames`
reproduces the exact shape `probes.md` Fact 3 measured live, where ELink
returned the identical id under three different linknames for one target.

Real values from `testing/Developer/reports/2026-09-22_bioproject_accession/
probes.md`, used throughout rather than invented ids: BioProject PRJNA31257,
uid 31257; BioSample SAMN12121739, uid 12121739; SRA record SRR9496657, uid
8317276; assembly GCF_000001405.40, uid 11968211.

What this file does NOT exercise: whether `search_input`'s plain term or
`link_inputs`' three calls are accepted by live ESearch/ELink (`probes.md`
in the same folder measures that live, not here), and the wiring into
`think_node` or `plan_node` in `core/graph.py` and the state field in
`core/state.py`, which do not exist when this file was written. `label()`'s
`kind not in ACCESSION_KINDS` and `search_input`/`link_inputs`' behaviour
for such a kind are exercised only as defensive-fallback checks, since
`parse_accession` itself can never produce one.

Depends on:
    - system_03_search_agent.core.accession (module under test)
"""

from __future__ import annotations

import pytest

from system_03_search_agent.core import accession as acc

# ---------------------------------------------------------------------------
# parse_accession: the must-parse examples from the fix-plan item's contract.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected_kind", "expected_value"),
    [
        ("For BioProject PRJNA31257, list the BioSamples", "bioproject", "PRJNA31257"),
        ("prjna31257", "bioproject", "PRJNA31257"),
        ("run SRR9496657", "sra", "SRR9496657"),
        ("assembly GCF_000001405.40 on GRCh38", "assembly", "GCF_000001405.40"),
        ("SAMN12121739", "biosample", "SAMN12121739"),
    ],
)
def test_parse_recognises_every_must_parse_example(
    text: str, expected_kind: str, expected_value: str
) -> None:
    result = acc.parse_accession(text)
    assert result is not None
    assert (result.kind, result.value) == (expected_kind, expected_value)


def test_parse_span_covers_exactly_the_matched_token_in_its_original_case() -> None:
    """`span` names the original text's own casing, never the upper-cased
    `value`, the same convention `coordinate_window`'s own span test pins."""
    text = "prjna31257"
    result = acc.parse_accession(text)
    assert result is not None
    assert text[result.span[0] : result.span[1]] == "prjna31257"


# ---------------------------------------------------------------------------
# parse_accession: the must-not-parse examples.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "PMID 11237011",
        "rs334",
        "NM_007294.4",
        "chr17:43,044,295-43,125,364",
        "PRJ12345",
        "GCF_12345",
    ],
)
def test_parse_rejects_text_with_no_accession(text: str) -> None:
    assert acc.parse_accession(text) is None


def test_parse_null_input_finds_nothing() -> None:
    assert acc.parse_accession("") is None
    assert acc.parse_accession(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# parse_accession: first-by-position, not by ACCESSION_KINDS priority.
# ---------------------------------------------------------------------------


def test_parse_finds_the_leftmost_accession_even_when_its_kind_sorts_last() -> None:
    """`assembly` is LAST in `ACCESSION_KINDS`, `bioproject` FIRST. This text
    puts the assembly first positionally, so a correct parser must return it;
    a parser that (wrongly) preferred `bioproject` by kind priority instead
    of position would return the BioProject accession, which is the
    populate check this test exists to catch."""
    text = "GCF_000001405.40 was assembled using reads from PRJNA31257"
    result = acc.parse_accession(text)
    assert result is not None
    assert (result.kind, result.value) == ("assembly", "GCF_000001405.40")


def test_parse_finds_the_leftmost_accession_the_other_direction_too() -> None:
    text = "BioProject PRJNA31257 produced BioSample SAMN12121739"
    result = acc.parse_accession(text)
    assert result is not None
    assert (result.kind, result.value) == ("bioproject", "PRJNA31257")


# ---------------------------------------------------------------------------
# Accession.label()
# ---------------------------------------------------------------------------


def test_label_for_bioproject() -> None:
    a = acc.Accession(kind="bioproject", value="PRJNA31257", span=(0, 0))
    assert a.label() == "BioProject PRJNA31257"


def test_label_for_biosample() -> None:
    a = acc.Accession(kind="biosample", value="SAMN12121739", span=(0, 0))
    assert a.label() == "BioSample SAMN12121739"


def test_label_for_assembly() -> None:
    a = acc.Accession(kind="assembly", value="GCF_000001405.40", span=(0, 0))
    assert a.label() == "assembly GCF_000001405.40"


@pytest.mark.parametrize(
    ("value", "expected_word"),
    [
        ("SRR9496657", "run"),
        ("SRX123456", "experiment"),
        ("SRS123456", "sample"),
        ("SRP123456", "study"),
    ],
)
def test_label_for_sra_reads_the_subtype_from_the_third_letter(
    value: str, expected_word: str
) -> None:
    """Populate check: R, X, S and P must each produce a DIFFERENT word in
    the same parametrize set, so a broken subtype lookup that fell back to
    one fixed word for all four would fail at least three of these cases."""
    a = acc.Accession(kind="sra", value=value, span=(0, 0))
    assert a.label() == f"SRA {expected_word} {value}"


def test_label_for_an_unrecognised_kind_falls_back_rather_than_raising() -> None:
    """`parse_accession` can never produce a kind outside `ACCESSION_KINDS`,
    but a hand-built `Accession` can; the fallback must not raise."""
    a = acc.Accession(kind="mystery", value="X1", span=(0, 0))
    assert a.label() == "mystery X1"


# ---------------------------------------------------------------------------
# search_input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("bioproject", "PRJNA31257"),
        ("biosample", "SAMN12121739"),
        ("sra", "SRR9496657"),
        ("assembly", "GCF_000001405.40"),
    ],
)
def test_search_input_sends_the_plain_term_with_no_field_tag(kind: str, value: str) -> None:
    a = acc.Accession(kind=kind, value=value, span=(0, 0))
    result = acc.search_input(a).root
    assert result.action == "search"
    assert result.db == kind
    assert result.term == value
    assert "[" not in result.term
    assert result.retmax == 1


# ---------------------------------------------------------------------------
# link_inputs
# ---------------------------------------------------------------------------


def test_link_inputs_for_bioproject_covers_all_three_targets_in_order() -> None:
    a = acc.Accession(kind="bioproject", value="PRJNA31257", span=(0, 0))
    calls = acc.link_inputs(a, "31257")
    assert [call.root.db for call in calls] == ["biosample", "sra", "assembly"]
    for call in calls:
        assert call.root.action == "link"
        assert call.root.dbfrom == "bioproject"
        assert call.root.ids == ["31257"]


def test_link_inputs_for_biosample_covers_sra_then_assembly() -> None:
    a = acc.Accession(kind="biosample", value="SAMN12121739", span=(0, 0))
    calls = acc.link_inputs(a, "12121739")
    assert [call.root.db for call in calls] == ["sra", "assembly"]
    assert all(call.root.dbfrom == "biosample" for call in calls)


def test_link_inputs_for_sra_has_exactly_one_target() -> None:
    a = acc.Accession(kind="sra", value="SRR9496657", span=(0, 0))
    calls = acc.link_inputs(a, "8317276")
    assert len(calls) == 1
    assert calls[0].root.dbfrom == "sra"
    assert calls[0].root.db == "biosample"
    assert calls[0].root.ids == ["8317276"]


def test_link_inputs_for_assembly_has_exactly_one_target() -> None:
    a = acc.Accession(kind="assembly", value="GCF_000001405.40", span=(0, 0))
    calls = acc.link_inputs(a, "11968211")
    assert len(calls) == 1
    assert calls[0].root.dbfrom == "assembly"
    assert calls[0].root.db == "biosample"


# ---------------------------------------------------------------------------
# plan_summary_calls
# ---------------------------------------------------------------------------

_BIOPROJECT = acc.Accession(kind="bioproject", value="PRJNA31257", span=(0, 0))


def test_plan_summary_calls_order_purposes_and_fields_for_bioproject() -> None:
    linked = {
        "biosample": ["12121739"],
        "sra": ["8317276"],
        "assembly": ["11968211"],
    }
    calls = acc.plan_summary_calls(_BIOPROJECT, "31257", linked)

    assert [call.purpose for call in calls] == [
        "bioproject_summary",
        "biosample_summary",
        "sra_summary",
        "assembly_summary",
    ]
    assert all(call.tool == "ncbi_efetch" for call in calls)
    assert all(call.layer == "layer_2_api" for call in calls)
    assert all(call.prefix == "ne" for call in calls)
    dbs_and_ids = [(call.tool_input.root.db, call.tool_input.root.ids) for call in calls]
    assert dbs_and_ids == [
        ("bioproject", ["31257"]),
        ("biosample", ["12121739"]),
        ("sra", ["8317276"]),
        ("assembly", ["11968211"]),
    ]
    assert all(call.tool_input.root.action == "summary" for call in calls)


def test_plan_summary_calls_caps_a_target_at_ten_highest_ids() -> None:
    fifteen_ids = [str(i) for i in range(1, 16)]
    linked = {"biosample": fifteen_ids}
    calls = acc.plan_summary_calls(_BIOPROJECT, "31257", linked)

    biosample_call = next(call for call in calls if call.purpose == "biosample_summary")
    assert biosample_call.tool_input.root.ids == [str(i) for i in range(15, 5, -1)]
    assert len(biosample_call.tool_input.root.ids) == acc.MAX_LINKED_PER_DB


def test_plan_summary_calls_skips_a_target_with_no_usable_ids() -> None:
    linked = {
        "biosample": [],  # empty
        "sra": ["abc", "0"],  # all invalid
        # "assembly" key absent entirely
    }
    calls = acc.plan_summary_calls(_BIOPROJECT, "31257", linked)
    assert [call.purpose for call in calls] == ["bioproject_summary"]


def test_plan_summary_calls_keeps_a_valid_id_and_drops_an_invalid_one_in_the_same_call() -> None:
    """The populate check named in the task contract: a non-uid dropped
    beside a valid one kept in the SAME call proves the filter discriminates
    per element rather than accepting or rejecting the whole list."""
    linked = {"biosample": ["12121739", "not-a-uid", "0"]}
    calls = acc.plan_summary_calls(_BIOPROJECT, "31257", linked)
    biosample_call = next(call for call in calls if call.purpose == "biosample_summary")
    assert biosample_call.tool_input.root.ids == ["12121739"]


@pytest.mark.parametrize(
    "linked",
    [None, "not a mapping", 42, ["biosample", "12121739"]],
)
def test_plan_summary_calls_never_raises_on_a_malformed_linked_value(linked: object) -> None:
    calls = acc.plan_summary_calls(_BIOPROJECT, "31257", linked)  # type: ignore[arg-type]
    assert [call.purpose for call in calls] == ["bioproject_summary"]


def test_plan_summary_calls_treats_a_bare_string_target_value_as_no_ids() -> None:
    """A string is iterable character by character; if it were read as a
    sequence of ids instead of rejected outright, this call would wrongly
    plan a biosample summary. It must not."""
    linked = {"biosample": "12121739"}
    calls = acc.plan_summary_calls(_BIOPROJECT, "31257", linked)
    assert [call.purpose for call in calls] == ["bioproject_summary"]


def test_plan_summary_calls_for_sra_covers_its_one_target() -> None:
    sra = acc.Accession(kind="sra", value="SRR9496657", span=(0, 0))
    calls = acc.plan_summary_calls(sra, "8317276", {"biosample": ["12121739"]})
    assert [call.purpose for call in calls] == ["sra_summary", "biosample_summary"]


def test_plan_summary_calls_for_assembly_covers_its_one_target() -> None:
    assembly = acc.Accession(kind="assembly", value="GCF_000001405.40", span=(0, 0))
    calls = acc.plan_summary_calls(assembly, "11968211", {"biosample": ["12121739"]})
    assert [call.purpose for call in calls] == ["assembly_summary", "biosample_summary"]


# ---------------------------------------------------------------------------
# disclosure
# ---------------------------------------------------------------------------


def test_disclosure_with_no_uid_says_not_found() -> None:
    assert acc.disclosure(_BIOPROJECT, None, {}) == "BioProject PRJNA31257 was not found in NCBI"


@pytest.mark.parametrize("blank_uid", ["", "   ", 12345])
def test_disclosure_treats_a_blank_or_non_string_uid_as_missing_too(blank_uid: object) -> None:
    assert acc.disclosure(_BIOPROJECT, blank_uid, {}) == (  # type: ignore[arg-type]
        "BioProject PRJNA31257 was not found in NCBI"
    )


def test_disclosure_with_no_links_at_all_reads_no_for_every_target() -> None:
    assert acc.disclosure(_BIOPROJECT, "31257", {}) == (
        "BioProject PRJNA31257 links to no BioSamples, no SRA runs and no assemblies"
    )


def test_disclosure_with_one_of_each_matches_the_locked_example_sentence() -> None:
    linked = {"biosample": ["12121739"], "sra": ["8317276"], "assembly": ["11968211"]}
    assert acc.disclosure(_BIOPROJECT, "31257", linked) == (
        "BioProject PRJNA31257 links to 1 BioSample, 1 SRA run and 1 assembly"
    )


def test_disclosure_with_several_pluralises_every_noun() -> None:
    linked = {
        "biosample": ["1", "2"],
        "sra": ["1", "2", "3"],
        "assembly": ["1", "2"],
    }
    assert acc.disclosure(_BIOPROJECT, "31257", linked) == (
        "BioProject PRJNA31257 links to 2 BioSamples, 3 SRA runs and 2 assemblies"
    )


def test_disclosure_deduplicates_repeated_ids_across_linknames() -> None:
    """`probes.md` Fact 3 measured ELink returning the SAME id under three
    different linknames for one target; a caller that folds every linkname's
    ids into one list before calling this module must not have that
    duplication double-count. This is the populate check: without dedup the
    count below would read 3 BioSamples instead of 1."""
    linked = {"biosample": ["12121739", "12121739", "12121739"]}
    assert acc.disclosure(_BIOPROJECT, "31257", linked) == (
        "BioProject PRJNA31257 links to 1 BioSample, no SRA runs and no assemblies"
    )


def test_disclosure_counts_valid_ids_before_the_summary_cap_applies() -> None:
    """15 valid ids: `plan_summary_calls` would only fetch 10 of them, but
    the disclosure sentence must still say 15, since it reports what was
    actually found rather than what will be fetched."""
    linked = {"biosample": [str(i) for i in range(1, 16)]}
    assert acc.disclosure(_BIOPROJECT, "31257", linked) == (
        "BioProject PRJNA31257 links to 15 BioSamples, no SRA runs and no assemblies"
    )


def test_disclosure_never_raises_on_a_malformed_linked_value() -> None:
    assert acc.disclosure(_BIOPROJECT, "31257", None) == (  # type: ignore[arg-type]
        "BioProject PRJNA31257 links to no BioSamples, no SRA runs and no assemblies"
    )


def test_disclosure_for_a_single_target_kind_joins_with_no_and_needed() -> None:
    sra = acc.Accession(kind="sra", value="SRR9496657", span=(0, 0))
    assert acc.disclosure(sra, "8317276", {"biosample": ["12121739"]}) == (
        "SRA run SRR9496657 links to 1 BioSample"
    )


def test_disclosure_for_a_two_target_kind_joins_with_and() -> None:
    biosample = acc.Accession(kind="biosample", value="SAMN12121739", span=(0, 0))
    linked = {"sra": ["8317276"], "assembly": ["11968211"]}
    assert acc.disclosure(biosample, "12121739", linked) == (
        "BioSample SAMN12121739 links to 1 SRA run and 1 assembly"
    )


def test_disclosure_stays_under_the_character_cap_when_the_vocabulary_is_forced_long(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ordinary input can never reach the 300-character cut, since the real
    vocabulary is a handful of short fixed words plus an id count. This test
    manufactures an oversized vocabulary by monkeypatching `_TARGET_NOUNS`,
    the only way to exercise the defensive cut at all, and is the populate
    check for it: without the cut, the assertion on length below fails."""
    long_nouns = {
        "biosample": ("X" * 150, "X" * 150 + "S"),
        "sra": ("Y" * 150, "Y" * 150 + "S"),
        "assembly": ("Z" * 150, "Z" * 150 + "S"),
    }
    monkeypatch.setattr(acc, "_TARGET_NOUNS", long_nouns)
    linked = {"biosample": ["1"], "sra": ["1"], "assembly": ["1"]}
    sentence = acc.disclosure(_BIOPROJECT, "31257", linked)
    assert len(sentence) <= acc._MAX_DISCLOSURE_CHARS
    # Written as the \u2026 escape, never a literal character, matching this
    # module's own ASCII-only-file discipline.
    assert sentence.endswith("\u2026")


# ---------------------------------------------------------------------------
# Locked constants.
# ---------------------------------------------------------------------------


def test_accession_kinds_is_the_locked_tuple() -> None:
    assert acc.ACCESSION_KINDS == ("bioproject", "biosample", "sra", "assembly")


def test_link_targets_is_the_locked_mapping() -> None:
    assert acc.LINK_TARGETS == {
        "bioproject": ("biosample", "sra", "assembly"),
        "biosample": ("sra", "assembly"),
        "sra": ("biosample",),
        "assembly": ("biosample",),
    }


def test_max_linked_per_db_is_ten() -> None:
    assert acc.MAX_LINKED_PER_DB == 10


# ---------------------------------------------------------------------------
# End-to-end, real probe values, PRJNA31257 (probes.md's full scenario).
# ---------------------------------------------------------------------------


def test_end_to_end_bioproject_prjna31257_matches_the_live_probe() -> None:
    question = "For BioProject PRJNA31257, list the BioSamples, SRA runs and any assemblies"
    parsed = acc.parse_accession(question)
    assert parsed is not None
    assert (parsed.kind, parsed.value) == ("bioproject", "PRJNA31257")

    search = acc.search_input(parsed).root
    assert (search.db, search.term, search.retmax) == ("bioproject", "PRJNA31257", 1)

    # ESearch resolves uid 31257 (probes.md Fact 1); simulate that result.
    uid = "31257"
    links = acc.link_inputs(parsed, uid)
    assert [call.root.db for call in links] == ["biosample", "sra", "assembly"]

    # ELink resolves one id per target, deduplicated across linknames
    # (probes.md Fact 3); simulate that result.
    linked = {"biosample": ["12121739"], "sra": ["8317276"], "assembly": ["11968211"]}
    summaries = acc.plan_summary_calls(parsed, uid, linked)
    assert [call.purpose for call in summaries] == [
        "bioproject_summary",
        "biosample_summary",
        "sra_summary",
        "assembly_summary",
    ]

    assert acc.disclosure(parsed, uid, linked) == (
        "BioProject PRJNA31257 links to 1 BioSample, 1 SRA run and 1 assembly"
    )
