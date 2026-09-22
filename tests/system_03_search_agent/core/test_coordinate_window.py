"""Tests for `core.coordinate_window`, the genomic coordinate window helpers.

No network and no model anywhere in this file: every function under test is a
pure function of its arguments, the same discipline `test_breadth_plan.py`
pins for its own module.

Coverage statement, per `goal-contracts`: each public function gets a valid,
an invalid and a null arm, and at least one populate check, an assertion
that fails if the behaviour it names were removed, not merely one that
happens to pass. The clearest instance is the `genes_in_window` test that
drops a non-overlapping record while keeping an overlapping one in the SAME
call: BRCA1 and a non-overlapping gene are filtered together, so a filter
that kept everything or dropped everything would both fail it. The other is
the `window_disclosure` ellipsis test, whose fixture is built to exceed 300
characters if nothing were cut, so a broken truncation would leave the
assertion on length failing.

What this file does NOT exercise: whether `GENE_WINDOW_TERM` or the position
search it builds are accepted by live ESearch (a parallel worker in the same
fix-plan item probes that live and records it in this folder's
`probes.md`/`findings.md`, not here), and the wiring into `think_node` or
`plan_node` in `core/graph.py` and the state field in `core/state.py`, which
did not exist when this file was written.

Depends on:
    - system_03_search_agent.core.coordinate_window (module under test)
"""

from __future__ import annotations

import pytest

from system_03_search_agent.core import coordinate_window as cw

# ---------------------------------------------------------------------------
# parse_coordinate_window: the four must-parse examples from the fix-plan
# item's contract, one per separator/prefix shape.
# ---------------------------------------------------------------------------


def test_parse_recognises_chr_prefix_commas_and_a_trailing_assembly() -> None:
    window = cw.parse_coordinate_window("chr17:43,044,295-43,125,364 on GRCh38")
    assert window is not None
    assert (window.chromosome, window.start, window.end) == ("17", 43044295, 43125364)
    assert window.assembly == "GRCh38"


def test_parse_recognises_plain_digits_and_a_parenthetical_assembly() -> None:
    window = cw.parse_coordinate_window("chr17:43044295-43125364 (hg38)")
    assert window is not None
    assert (window.chromosome, window.start, window.end) == ("17", 43044295, 43125364)
    assert window.assembly == "GRCh38"


def test_parse_recognises_chromosome_word_prefix_commas_and_the_word_to() -> None:
    window = cw.parse_coordinate_window("chromosome 17: 43,044,295 to 43,125,364, GRCh37")
    assert window is not None
    assert (window.chromosome, window.start, window.end) == ("17", 43044295, 43125364)
    assert window.assembly == "GRCh37"


def test_parse_recognises_an_en_dash_separator_with_no_spaces() -> None:
    # The en dash is written as the \u2013 escape in a normal (non-raw)
    # string literal, so Python converts it to the actual character at
    # parse time. No raw en-dash byte sits anywhere in this file's source.
    window = cw.parse_coordinate_window("chrX:100000\u2013200000 hg19")
    assert window is not None
    assert (window.chromosome, window.start, window.end) == ("X", 100000, 200000)
    assert window.assembly == "GRCh37"


@pytest.mark.parametrize(
    ("text", "expected_span_text"),
    [
        ("chr17:43,044,295-43,125,364 on GRCh38", "chr17:43,044,295-43,125,364"),
        ("chr17:43044295-43125364 (hg38)", "chr17:43044295-43125364"),
        (
            "chromosome 17: 43,044,295 to 43,125,364, GRCh37",
            "chromosome 17: 43,044,295 to 43,125,364",
        ),
        ("chrX:100000\u2013200000 hg19", "chrX:100000\u2013200000"),
    ],
)
def test_parse_span_covers_exactly_the_matched_window_text(
    text: str, expected_span_text: str
) -> None:
    """`span` names the window text only, never a trailing assembly word,
    since the assembly is found separately, anywhere in the text."""
    window = cw.parse_coordinate_window(text)
    assert window is not None
    assert text[window.span[0] : window.span[1]] == expected_span_text


# ---------------------------------------------------------------------------
# parse_coordinate_window: the must-not-parse examples.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "rs334",
        "17q21.31",
        "BRCA1",
        "1:2 ratio",
        "PMID 11237011",
        "2026-09-22",
        "43,044,295-43,125,364",
    ],
)
def test_parse_rejects_text_with_no_coordinate_window(text: str) -> None:
    assert cw.parse_coordinate_window(text) is None


def test_parse_null_input_plans_nothing() -> None:
    assert cw.parse_coordinate_window("") is None
    assert cw.parse_coordinate_window(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# parse_coordinate_window: chromosome token bounds and M/MT normalisation.
# ---------------------------------------------------------------------------


def test_parse_normalises_m_to_mt() -> None:
    window = cw.parse_coordinate_window("chrM:1-100")
    assert window is not None
    assert window.chromosome == "MT"


def test_parse_accepts_mt_directly() -> None:
    window = cw.parse_coordinate_window("chrMT:1-100")
    assert window is not None
    assert window.chromosome == "MT"


def test_parse_accepts_chromosome_22_and_y() -> None:
    assert cw.parse_coordinate_window("chr22:1-100").chromosome == "22"
    assert cw.parse_coordinate_window("chrY:1-100").chromosome == "Y"


def test_parse_rejects_chromosome_23_and_0() -> None:
    """There is no human chromosome 23 or 0. A digit run that is not one of
    1 to 22 never completes a chromosome-token match, and `\\b` blocks the
    regex from instead matching a trailing digit (`chr23` as chromosome
    `3`), the populate check for this arm: without the boundary this would
    wrongly parse as chromosome `3`."""
    assert cw.parse_coordinate_window("chr23:1-100") is None
    assert cw.parse_coordinate_window("chr0:1-100") is None


# ---------------------------------------------------------------------------
# parse_coordinate_window: the assembly families and the ambiguous case.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("word", ["GRCh38", "grch38", "hg38", "b38"])
def test_parse_recognises_every_grch38_alias(word: str) -> None:
    window = cw.parse_coordinate_window(f"chr1:1-100 {word}")
    assert window is not None
    assert window.assembly == "GRCh38"


@pytest.mark.parametrize("word", ["GRCh37", "grch37", "hg19", "b37"])
def test_parse_recognises_every_grch37_alias(word: str) -> None:
    window = cw.parse_coordinate_window(f"chr1:1-100 {word}")
    assert window is not None
    assert window.assembly == "GRCh37"


def test_parse_with_no_assembly_word_leaves_assembly_none() -> None:
    window = cw.parse_coordinate_window("chr1:1-100")
    assert window is not None
    assert window.assembly is None


def test_parse_with_both_assembly_families_is_ambiguous() -> None:
    """Naming both GRCh38 and GRCh37 in the same question is not a coin
    flip: neither can be assumed, so this reads exactly like naming
    neither, and the caller ends up asking `ASSEMBLY_QUESTION` either way."""
    window = cw.parse_coordinate_window("chr17:1-1000 on GRCh38 or GRCh37")
    assert window is not None
    assert window.assembly is None


def test_parse_finds_the_assembly_before_the_window_too() -> None:
    window = cw.parse_coordinate_window("On GRCh38, what genes sit in chr17:1-1000?")
    assert window is not None
    assert window.assembly == "GRCh38"


# ---------------------------------------------------------------------------
# parse_coordinate_window: inverted bounds and the 50 Mb bound.
# ---------------------------------------------------------------------------


def test_parse_swaps_a_window_given_backwards() -> None:
    window = cw.parse_coordinate_window("chr17:43,125,364-43,044,295 on GRCh38")
    assert window is not None
    assert (window.start, window.end) == (43044295, 43125364)


def test_parse_rejects_a_window_wider_than_the_bound() -> None:
    assert cw.parse_coordinate_window("chr1:1-60,000,000 on GRCh38") is None


def test_parse_accepts_a_window_exactly_at_the_bound() -> None:
    """`end - start + 1` is the inclusive base count; a window of exactly
    `MAX_WINDOW_SPAN_BASES` bases is a valid locus question, only a WIDER
    one is rejected."""
    text = f"chr1:1-{cw.MAX_WINDOW_SPAN_BASES:,} on GRCh38"
    window = cw.parse_coordinate_window(text)
    assert window is not None
    assert window.end - window.start + 1 == cw.MAX_WINDOW_SPAN_BASES


def test_parse_only_returns_the_first_window_in_the_text() -> None:
    text = "chr17:1-100 on GRCh38, also see chr2:5-6"
    window = cw.parse_coordinate_window(text)
    assert window is not None
    assert (window.chromosome, window.start, window.end) == ("17", 1, 100)


# ---------------------------------------------------------------------------
# CoordinateWindow.label
# ---------------------------------------------------------------------------


def test_label_renders_thousands_separators_and_the_assembly() -> None:
    window = cw.CoordinateWindow(
        chromosome="17", start=43044295, end=43125364, assembly="GRCh38", span=(0, 0)
    )
    assert window.label() == "chr17:43,044,295-43,125,364 (GRCh38)"


def test_label_with_no_assembly_says_so_instead_of_guessing() -> None:
    window = cw.CoordinateWindow(chromosome="17", start=1, end=2, assembly=None, span=(0, 0))
    assert window.label() == "chr17:1-2 (assembly not named)"


# ---------------------------------------------------------------------------
# gene_search_term / GENE_WINDOW_TERM
# ---------------------------------------------------------------------------


def test_gene_window_term_constant_is_the_locked_template() -> None:
    assert cw.GENE_WINDOW_TERM == "{chromosome}[CHR] AND {start}:{end}[CPOS] AND human[ORGN]"


def test_gene_search_term_for_grch38_fills_the_template() -> None:
    window = cw.CoordinateWindow(
        chromosome="17", start=43044295, end=43125364, assembly="GRCh38", span=(0, 0)
    )
    assert cw.gene_search_term(window) == "17[CHR] AND 43044295:43125364[CPOS] AND human[ORGN]"


def test_gene_search_term_for_grch37_is_none() -> None:
    window = cw.CoordinateWindow(
        chromosome="17", start=43044295, end=43125364, assembly="GRCh37", span=(0, 0)
    )
    assert cw.gene_search_term(window) is None


def test_gene_search_term_with_no_assembly_is_none() -> None:
    window = cw.CoordinateWindow(chromosome="17", start=1, end=2, assembly=None, span=(0, 0))
    assert cw.gene_search_term(window) is None


# ---------------------------------------------------------------------------
# genes_in_window
# ---------------------------------------------------------------------------

# Real values from the BRCA1 locus (GRCh38): uid 672, chraccver NC_000017.11,
# chrstart 43044294, chrstop 43125482.
_WINDOW38 = cw.CoordinateWindow(
    chromosome="17", start=43044295, end=43125364, assembly="GRCh38", span=(0, 0)
)

_BRCA1_WRAPPED = {
    "id": "672",
    "fields": {
        "name": "BRCA1",
        "genomicinfo": [
            {"chraccver": "NC_000017.11", "chrstart": 43044294, "chrstop": 43125482}
        ],
    },
}

_BRCA1_BARE = {
    "uid": "672",
    "name": "BRCA1",
    "genomicinfo": [
        {"chraccver": "NC_000017.11", "chrstart": 43044294, "chrstop": 43125482}
    ],
}

_BRCA1_EXPECTED = cw.WindowGene(
    symbol="BRCA1", curie="NCBIGene:672", start=43044294, end=43125482
)


def test_genes_window_reads_a_wrapped_record_with_a_fields_key() -> None:
    result = cw.genes_in_window([_BRCA1_WRAPPED], _WINDOW38)
    assert result == cw.WindowGenes(genes=(_BRCA1_EXPECTED,), total_overlapping=1, truncated=False)


def test_genes_window_reads_a_bare_fields_mapping_too() -> None:
    """The uid lookup order, `uid` on the given mapping first, `id` on the
    outer record second, is what makes both shapes resolve to the SAME
    gene: this is the populate check for `_resolve_uid`, since a broken
    lookup would produce two different results, or silently drop one."""
    result = cw.genes_in_window([_BRCA1_BARE], _WINDOW38)
    assert result == cw.WindowGenes(genes=(_BRCA1_EXPECTED,), total_overlapping=1, truncated=False)


def test_genes_window_handles_a_minus_strand_placement() -> None:
    """Gene reports a minus-strand gene with chrstart greater than chrstop.
    The smaller value is always treated as the start regardless of which
    field it came from."""
    minus_strand = {
        "id": "672",
        "fields": {
            "name": "BRCA1",
            "genomicinfo": [
                {"chraccver": "NC_000017.11", "chrstart": 43125482, "chrstop": 43044294}
            ],
        },
    }
    result = cw.genes_in_window([minus_strand], _WINDOW38)
    assert result.genes == (_BRCA1_EXPECTED,)


def test_genes_window_drops_non_overlap_keeps_overlap_in_same_call() -> None:
    far_away = {
        "id": "999",
        "fields": {
            "name": "FAR1",
            "genomicinfo": [
                {"chraccver": "NC_000017.11", "chrstart": 90000000, "chrstop": 90001000}
            ],
        },
    }
    result = cw.genes_in_window([_BRCA1_WRAPPED, far_away], _WINDOW38)
    assert [gene.symbol for gene in result.genes] == ["BRCA1"]
    assert result.total_overlapping == 1


@pytest.mark.parametrize(
    "malformed",
    [
        {"id": "1", "fields": {"genomicinfo": []}},  # no name
        {"id": "2", "fields": {"name": "NOPLACEMENT"}},  # no genomicinfo at all
        {
            "id": "3",
            "fields": {"name": "ONEBOUND", "genomicinfo": [{"chraccver": "x", "chrstart": 5}]},
        },  # placement missing chrstop
        {"fields": {"name": "NOID", "genomicinfo": [{"chrstart": 1, "chrstop": 2}]}},  # no id/uid
        {"id": "4", "fields": {"name": "", "genomicinfo": []}},  # blank name
        "not a mapping at all",
        None,
        5,
    ],
)
def test_genes_window_never_raises_on_a_malformed_record_and_skips_it(malformed: object) -> None:
    result = cw.genes_in_window([malformed], _WINDOW38)  # type: ignore[list-item]
    assert result == cw.WindowGenes(genes=(), total_overlapping=0, truncated=False)


def test_genes_window_ignores_one_bad_placement_but_uses_another_valid_one() -> None:
    """`chrstart`/`chrstop` accept ints or digit strings; a placement
    missing either bound is ignored, but a record is not dropped just
    because ONE of its placements is malformed, only when NONE overlap."""
    two_placements = {
        "id": "672",
        "fields": {
            "name": "BRCA1",
            "genomicinfo": [
                {"chraccver": "x", "chrstart": 5},  # missing chrstop, ignored
                {"chraccver": "NC_000017.11", "chrstart": "43044294", "chrstop": "43125482"},
            ],
        },
    }
    result = cw.genes_in_window([two_placements], _WINDOW38)
    assert result.genes == (_BRCA1_EXPECTED,)


def test_genes_window_null_input_is_empty() -> None:
    assert cw.genes_in_window([], _WINDOW38) == cw.WindowGenes(
        genes=(), total_overlapping=0, truncated=False
    )


def test_genes_window_sorts_by_start_ascending_then_symbol() -> None:
    reverse_order = [
        {
            "id": "3",
            "fields": {
                "name": "CCC",
                "genomicinfo": [{"chrstart": 43044400, "chrstop": 43044500}],
            },
        },
        {
            "id": "1",
            "fields": {
                "name": "BBB",
                "genomicinfo": [{"chrstart": 43044300, "chrstop": 43044350}],
            },
        },
        # Same start as BBB: the symbol breaks the tie.
        {
            "id": "2",
            "fields": {
                "name": "AAA",
                "genomicinfo": [{"chrstart": 43044300, "chrstop": 43044350}],
            },
        },
    ]
    result = cw.genes_in_window(reverse_order, _WINDOW38)
    assert [gene.symbol for gene in result.genes] == ["AAA", "BBB", "CCC"]


def test_genes_window_caps_at_ten_and_reports_truncation() -> None:
    # ids start at 1, never 0: a uid of zero is not a real Entrez id (the
    # same F-06 precedent `core.breadth_plan.select_ids` enforces), and
    # `_resolve_uid` correctly drops a record whose id is "0".
    fifteen = [
        {
            "id": str(i + 1),
            "fields": {
                "name": f"GENE{i:02d}",
                "genomicinfo": [
                    {
                        "chrstart": _WINDOW38.start + i * 1000,
                        "chrstop": _WINDOW38.start + i * 1000 + 500,
                    }
                ],
            },
        }
        for i in range(15)
    ]
    # Shuffle the input order so a pass here cannot be explained by the
    # cap simply taking however the caller happened to list them.
    shuffled = list(reversed(fifteen))
    result = cw.genes_in_window(shuffled, _WINDOW38)

    assert result.total_overlapping == 15
    assert result.truncated is True
    assert len(result.genes) == cw.MAX_WINDOW_GENES
    assert [gene.symbol for gene in result.genes] == [f"GENE{i:02d}" for i in range(10)]


# ---------------------------------------------------------------------------
# plan_overlap_calls
# ---------------------------------------------------------------------------


def test_plan_overlap_calls_for_grch38_is_clinvar_then_dbvar() -> None:
    calls = cw.plan_overlap_calls(_WINDOW38)

    assert [call.purpose for call in calls] == ["clinvar_overlap", "dbvar_overlap"]
    assert all(call.tool == "ncbi_efetch" and call.layer == "layer_2_api" for call in calls)
    assert all(call.prefix == "ne" for call in calls)
    clinvar, dbvar = (call.tool_input.root for call in calls)
    assert (clinvar.action, clinvar.db) == ("coordinate_overlap", "clinvar")
    assert (dbvar.action, dbvar.db) == ("coordinate_overlap", "dbvar")
    for planned in (clinvar, dbvar):
        assert planned.chromosome == "17"
        assert planned.start == 43044295
        assert planned.end == 43125364
        assert planned.assembly == "GRCh38"


def test_plan_overlap_calls_for_grch37_also_plans_both_calls() -> None:
    window37 = cw.CoordinateWindow(
        chromosome="17", start=43044295, end=43125364, assembly="GRCh37", span=(0, 0)
    )
    calls = cw.plan_overlap_calls(window37)
    assert [call.purpose for call in calls] == ["clinvar_overlap", "dbvar_overlap"]
    assert all(call.tool_input.root.assembly == "GRCh37" for call in calls)


def test_plan_overlap_calls_with_no_assembly_plans_nothing() -> None:
    window_none = cw.CoordinateWindow(chromosome="17", start=1, end=2, assembly=None, span=(0, 0))
    assert cw.plan_overlap_calls(window_none) == ()


# ---------------------------------------------------------------------------
# ASSEMBLY_QUESTION / window_disclosure
# ---------------------------------------------------------------------------


def test_assembly_question_is_the_exact_locked_text() -> None:
    assert cw.ASSEMBLY_QUESTION == (
        "These coordinates could be on GRCh38 or GRCh37, and the two put "
        "different genes under the same numbers. Add the assembly to the "
        'question, for example "on GRCh38", and I will search.'
    )


def test_window_disclosure_with_no_genes() -> None:
    empty = cw.WindowGenes(genes=(), total_overlapping=0, truncated=False)
    assert cw.window_disclosure(_WINDOW38, empty) == (
        "the window chr17:43,044,295-43,125,364 (GRCh38) overlaps no gene in NCBI Gene"
    )


def test_window_disclosure_with_one_gene_uses_singular() -> None:
    one = cw.WindowGenes(genes=(_BRCA1_EXPECTED,), total_overlapping=1, truncated=False)
    assert cw.window_disclosure(_WINDOW38, one) == (
        "the window chr17:43,044,295-43,125,364 (GRCh38) overlaps 1 gene: BRCA1"
    )


def test_window_disclosure_with_several_genes_uses_plural_and_lists_all() -> None:
    three = cw.WindowGenes(
        genes=(
            cw.WindowGene(symbol="AAA", curie="NCBIGene:1", start=1, end=2),
            cw.WindowGene(symbol="BBB", curie="NCBIGene:2", start=3, end=4),
            cw.WindowGene(symbol="CCC", curie="NCBIGene:3", start=5, end=6),
        ),
        total_overlapping=3,
        truncated=False,
    )
    assert cw.window_disclosure(_WINDOW38, three) == (
        "the window chr17:43,044,295-43,125,364 (GRCh38) overlaps 3 genes: AAA, BBB, CCC"
    )


def test_window_disclosure_when_truncated_names_the_cap() -> None:
    truncated = cw.WindowGenes(
        genes=tuple(
            cw.WindowGene(symbol=f"G{i}", curie=f"NCBIGene:{i}", start=i, end=i + 1)
            for i in range(10)
        ),
        total_overlapping=37,
        truncated=True,
    )
    disclosure = cw.window_disclosure(_WINDOW38, truncated)
    assert disclosure.startswith(
        "the window chr17:43,044,295-43,125,364 (GRCh38) overlaps 37 genes; "
        "the 10 nearest its start are searched: "
    )
    assert "G0" in disclosure


def test_window_disclosure_cuts_a_long_symbol_list_with_an_ellipsis() -> None:
    """Ten 24-character symbols joined with commas run well past 300
    characters once the prefix is added; if the cut logic were removed
    this assertion on length would fail, which is the populate check."""
    long_symbols = tuple(
        cw.WindowGene(symbol=f"GENE{i:02d}" + "X" * 20, curie=f"NCBIGene:{i}", start=i, end=i + 1)
        for i in range(10)
    )
    truncated = cw.WindowGenes(genes=long_symbols, total_overlapping=37, truncated=True)
    disclosure = cw.window_disclosure(_WINDOW38, truncated)

    uncut_list = ", ".join(gene.symbol for gene in long_symbols)
    assert len(disclosure) <= 300
    assert disclosure.endswith("\u2026")
    assert uncut_list not in disclosure



def test_named_genes_sort_before_unnamed_loci_whatever_their_position() -> None:
    """Measured live on the CFTR window (chr7:117,480,025-117,668,665, GRCh38):
    LOC111674463 starts before CFTR, and by position alone it came first, so
    the answer's literature, OMIM and gene summary followed the locus. The
    first resolved gene is the one the turn follows, so named genes lead."""
    window = cw.parse_coordinate_window("chr7:117,480,025-117,668,665 on GRCh38")
    assert window is not None
    records = [
        {"id": "111674463", "fields": {"name": "LOC111674463", "genomicinfo": [
            {"chraccver": "NC_000007.14", "chrstart": 117479000, "chrstop": 117481000}]}},
        {"id": "1080", "fields": {"name": "CFTR", "genomicinfo": [
            {"chraccver": "NC_000007.14", "chrstart": 117480024, "chrstop": 117668664}]}},
        {"id": "113664106", "fields": {"name": "LOC113664106", "genomicinfo": [
            {"chraccver": "NC_000007.14", "chrstart": 117500000, "chrstop": 117500500}]}},
    ]
    found = cw.genes_in_window(records, window)
    assert [gene.symbol for gene in found.genes] == ["CFTR", "LOC111674463", "LOC113664106"]
    # Populate check: two named genes still order by position between themselves.
    records.append({"id": "1081", "fields": {"name": "AAAA", "genomicinfo": [
        {"chraccver": "NC_000007.14", "chrstart": 117600000, "chrstop": 117600500}]}})
    assert [gene.symbol for gene in cw.genes_in_window(records, window).genes][:2] == ["CFTR", "AAAA"]
