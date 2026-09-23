"""Tests for `core.isolate_search`, the Pathogen Detection isolate question helpers.

No network and no model anywhere in this file: every function under test is a
pure function of its arguments, the same discipline `test_accession.py` and
`test_coordinate_window.py` pin for their own modules.

Coverage statement, per `goal-contracts`: the recogniser gets a valid, an
invalid and a null arm; each of its three parts (the isolate word, the
organism, the gene family or token) has an arm proving its absence changes
the result, so no arm passes on an empty match. The organism table is checked
against the FTP root listing and the live taxonomy ids recorded in
`testing/Developer/reports/2026-09-22_isolate_search/probes.md` and the
module docstring, so a folder or an id typed wrong fails here. The ESBL family
arm pins the decision that only `blaCTX-M` is searched. `plan_calls` is
checked for order, tool, mode and the absence of any graph call, and
`count_sentence` for the exact and the "at least" forms.

What this file does NOT exercise: the wiring in `core/graph.py`
(`test_isolate_search_wiring.py`), and whether the tool finds anything for
these prefixes live (`test_pathogen_detection_premise.py`).

Depends on:
    - system_03_search_agent.core.isolate_search (module under test)
"""

from __future__ import annotations

import pytest

from system_03_search_agent.core import isolate_search as module

GOLDEN = "What Escherichia coli isolates in Pathogen Detection carry extended-spectrum beta-lactamase genes?"

# The 107 taxon folders the FTP root listed on 2026-09-22 (probes.md, item A),
# only the ones the organism table names.
FTP_FOLDERS_LISTED = {
    "Escherichia_coli_Shigella", "Salmonella", "Listeria", "Klebsiella", "Campylobacter",
    "Staphylococcus_aureus", "Pseudomonas_aeruginosa", "Acinetobacter", "Enterococcus_faecium",
    "Enterococcus_faecalis", "Enterobacter_cloacae", "Vibrio_cholerae", "Clostridioides_difficile",
    "Neisseria_gonorrhoeae", "Mycobacterium_tuberculosis", "Streptococcus_pneumoniae",
}

# Verified live against NCBI Taxonomy on 2026-09-22, ESearch `[Scientific Name]`.
LIVE_TAXIDS = {
    "Escherichia coli": 562, "Shigella": 620, "Salmonella": 590, "Listeria monocytogenes": 1639,
    "Listeria": 1637, "Klebsiella pneumoniae": 573, "Klebsiella": 570, "Campylobacter jejuni": 197,
    "Campylobacter": 194, "Staphylococcus aureus": 1280, "Pseudomonas aeruginosa": 287,
    "Acinetobacter": 469, "Enterococcus faecium": 1352, "Enterococcus faecalis": 1351,
    "Enterobacter cloacae": 550, "Vibrio cholerae": 666, "Clostridioides difficile": 1496,
    "Neisseria gonorrhoeae": 485, "Mycobacterium tuberculosis": 1773, "Streptococcus pneumoniae": 1313,
}


# ---------------------------------------------------------------------------
# The table itself
# ---------------------------------------------------------------------------


def test_every_organism_folder_was_listed_by_the_ftp_root() -> None:
    assert {o.taxon_folder for o in module.ORGANISMS} <= FTP_FOLDERS_LISTED


def test_every_organism_taxid_matches_the_live_lookup() -> None:
    assert {o.label: o.taxid for o in module.ORGANISMS} == LIVE_TAXIDS


def test_a_species_entry_sits_before_its_genus_entry() -> None:
    labels = [o.label for o in module.ORGANISMS]
    for species, genus in (
        ("Listeria monocytogenes", "Listeria"),
        ("Klebsiella pneumoniae", "Klebsiella"),
        ("Campylobacter jejuni", "Campylobacter"),
    ):
        assert labels.index(species) < labels.index(genus)


def test_esbl_searches_the_ctx_m_family_only_and_says_why() -> None:
    esbl = next(f for f in module.GENE_FAMILIES if f.key == "esbl")
    assert esbl.prefixes == ("blaCTX-M",)
    assert "blaTEM" in esbl.omitted and "blaSHV" in esbl.omitted


# ---------------------------------------------------------------------------
# parse_isolate_question
# ---------------------------------------------------------------------------


def test_the_golden_question_is_recognised_in_full() -> None:
    question = module.parse_isolate_question(GOLDEN)
    assert question is not None
    assert question.organism is not None and question.organism.curie == "NCBITaxon:562"
    assert question.organism.taxon_folder == "Escherichia_coli_Shigella"
    assert [f.key for f in question.families] == ["esbl"]
    assert question.prefixes == ("blaCTX-M",)
    assert question.clarification is None


@pytest.mark.parametrize(
    "text",
    [
        "ESBL E. coli isolates?",
        "Which E.coli isolates in Pathogen Detection carry ESBLs?",
        "extended spectrum beta lactamase genes in escherichia coli isolates",
    ],
)
def test_the_shortest_and_the_loosest_spellings_still_read_as_the_golden_shape(text: str) -> None:
    question = module.parse_isolate_question(text)
    assert question is not None and question.clarification is None
    assert question.organism is not None and question.organism.taxid == 562
    assert question.prefixes == ("blaCTX-M",)


def test_a_question_about_one_isolate_record_is_not_this_shape() -> None:
    """Competency question Q5 names an isolate by its PDT identifier and asks
    about its cluster and AMR: a lookup of one record, never a search by
    gene. Found by the mutation harness's P1 arm going vacuous on Q5."""
    q5 = (
        "For Salmonella isolate PDT000123456, what SNP cluster is it in, what "
        "AMR genes does it carry, and which other isolates are within 5 SNPs?"
    )
    assert module.parse_isolate_question(q5) is None
    assert module.parse_isolate_question("Which isolates are in cluster PDS000065758.2005?") is None
    # Populate check: the same words without the identifier ARE the shape.
    without = module.parse_isolate_question("For Salmonella isolates, what AMR genes carry blaCTX-M?")
    assert without is not None and without.prefixes == ("blaCTX-M",)


def test_without_an_isolate_word_the_same_organism_and_family_are_not_this_shape() -> None:
    assert module.parse_isolate_question("Which E. coli strains carry ESBL genes?") is None


@pytest.mark.parametrize("text", ["", "What is an isolate?", "Which diseases are associated with BRCA1?"])
def test_text_with_nothing_of_the_shape_is_not_recognised(text: str) -> None:
    assert module.parse_isolate_question(text) is None


def test_a_gene_with_no_organism_asks_which_organism() -> None:
    question = module.parse_isolate_question("Which isolates in Pathogen Detection carry blaKPC?")
    assert question is not None and question.organism is None
    assert question.prefixes == ("blaKPC",)
    assert question.clarification == module.ORGANISM_QUESTION
    assert "Escherichia coli" in module.ORGANISM_QUESTION


def test_an_unknown_organism_with_a_resistance_word_asks_which_organism() -> None:
    """Measured live 2026-09-22: the tomato question got the generic gene
    refusal because "resistance genes" named no family."""
    question = module.parse_isolate_question(
        "Which tomato isolates in Pathogen Detection carry resistance genes?"
    )
    assert question is not None and question.organism is None
    assert question.clarification == module.ORGANISM_QUESTION
    amr = module.parse_isolate_question("Which E. coli isolates have AMR genes?")
    assert amr is not None and amr.clarification == module.GENE_QUESTION
    # Populate check: the same sentence with no resistance word is not the shape.
    assert module.parse_isolate_question("Which tomato isolates in Pathogen Detection carry genes?") is None


def test_an_organism_with_no_gene_asks_which_gene() -> None:
    question = module.parse_isolate_question("Which E. coli isolates are in Pathogen Detection?")
    assert question is not None and question.organism is not None
    assert question.prefixes == ()
    assert question.clarification == module.GENE_QUESTION


def test_an_explicit_allele_is_kept_as_typed_beside_the_family() -> None:
    question = module.parse_isolate_question("Which Salmonella isolates carry blaCTX-M-15 or other ESBLs?")
    assert question is not None
    assert question.genes == ("blaCTX-M-15",)
    assert question.prefixes == ("blaCTX-M", "blaCTX-M-15")


@pytest.mark.parametrize(
    ("text", "label", "folder"),
    [
        ("Klebsiella pneumoniae isolates with carbapenemase genes", "Klebsiella pneumoniae", "Klebsiella"),
        ("Klebsiella isolates with carbapenemase genes", "Klebsiella", "Klebsiella"),
        ("MRSA isolates in Pathogen Detection", "Staphylococcus aureus", "Staphylococcus_aureus"),
        ("Listeria monocytogenes isolates carrying vanA", "Listeria monocytogenes", "Listeria"),
    ],
)
def test_the_most_specific_organism_name_wins(text: str, label: str, folder: str) -> None:
    question = module.parse_isolate_question(text)
    assert question is not None and question.organism is not None
    assert question.organism.label == label and question.organism.taxon_folder == folder


def test_carbapenemase_and_colistin_families_carry_their_prefixes() -> None:
    carb = module.parse_isolate_question("Klebsiella isolates carrying carbapenemase genes")
    assert carb is not None and carb.prefixes == ("blaKPC", "blaNDM", "blaOXA-48", "blaVIM", "blaIMP")
    mcr = module.parse_isolate_question("E. coli isolates with colistin resistance")
    assert mcr is not None and mcr.prefixes == ("mcr-",)


def test_a_sentence_comma_never_joins_a_gene_token() -> None:
    question = module.parse_isolate_question("Salmonella isolates carrying blaCTX-M-15, blaNDM-1, or mcr-1.1")
    assert question is not None
    assert question.genes == ("blaCTX-M-15", "blaNDM-1", "mcr-1.1")


def test_prefixes_are_capped_at_ten() -> None:
    genes = " ".join(f"blaGENE{i}" for i in range(15))
    question = module.parse_isolate_question(f"E. coli isolates carrying {genes}")
    assert question is not None and len(question.prefixes) == 10


# ---------------------------------------------------------------------------
# plan_calls, disclosure, count_sentence
# ---------------------------------------------------------------------------


def test_plan_calls_is_the_isolate_search_then_the_taxonomy_record_and_no_graph_call() -> None:
    question = module.parse_isolate_question(GOLDEN)
    assert question is not None
    calls = module.plan_calls(question)
    assert [c.tool for c in calls] == ["pathogen_detection", "ncbi_efetch"]
    assert [c.purpose for c in calls] == ["isolate_search", "taxonomy_summary"]
    assert all(c.layer == "layer_2_api" for c in calls)
    search = calls[0].tool_input.root
    assert search.mode == "isolate_search"
    assert search.taxon == "Escherichia_coli_Shigella"
    assert search.amr_gene_prefixes == ["blaCTX-M"]
    assert search.max_isolates == module.ISOLATES_SHOWN
    taxonomy = calls[1].tool_input.root
    assert taxonomy.action == "summary" and taxonomy.db == "taxonomy" and taxonomy.ids == ["562"]


def test_plan_calls_refuses_a_question_that_still_needs_a_clarification() -> None:
    question = module.parse_isolate_question("Which isolates carry blaKPC?")
    assert question is not None
    with pytest.raises(ValueError):
        module.plan_calls(question)


def test_disclosure_names_the_prefixes_and_the_omission() -> None:
    question = module.parse_isolate_question(GOLDEN)
    assert question is not None
    text = module.disclosure(question)
    assert "Escherichia coli" in text and "blaCTX-M" in text
    assert "blaTEM and blaSHV alleles were not searched" in text
    plain = module.parse_isolate_question("Klebsiella isolates carrying blaKPC-2")
    assert plain is not None
    assert "not searched" not in module.disclosure(plain)


@pytest.mark.parametrize(
    ("shown", "total", "complete", "expected"),
    [
        (20, 21_004, True, "Pathogen Detection lists 21,004 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown."),
        (20, 20, True, "Pathogen Detection lists 20 Escherichia coli isolates with these genes, all shown."),
        (3, 3, True, "Pathogen Detection lists 3 Escherichia coli isolates with these genes, all shown."),
        (1, 1, True, "Pathogen Detection lists 1 Escherichia coli isolate with these genes, all shown."),
        (0, 0, True, "Pathogen Detection lists 0 Escherichia coli isolates with these genes, all shown."),
        (20, 500, False, "Pathogen Detection lists at least 500 Escherichia coli isolates with these genes; the first 20 in the snapshot are shown."),
    ],
)
def test_count_sentence_is_exact_when_the_scan_finished_and_at_least_when_it_did_not(
    shown: int, total: int, complete: bool, expected: str
) -> None:
    assert module.count_sentence("Escherichia coli", shown, total, complete) == expected
