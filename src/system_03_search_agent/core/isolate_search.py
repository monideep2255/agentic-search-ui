"""Deterministic recognition and call planning for a Pathogen Detection isolate
question (golden question G-035, fix-plan "Next, in order" item 1, 2026-09-22).

A question like "What Escherichia coli isolates in Pathogen Detection carry
extended-spectrum beta-lactamase genes?" names an organism and a resistance
gene family, not a gene symbol, a variant, a disease or an accession, so
until this module existed Think resolved nothing for it and the plan
dispatched a graph search with nothing to bind. Everything here is a pure
function of its arguments: no network call, no model call, the same
discipline `core.accession` and `core.coordinate_window` document for the
same reason, so `think_node` in `core/graph.py` can call it and hand the
result to its own resolution and planning logic.

What the person gets, decided from the user's chair and approved by the
product owner on 2026-09-22: the exact number of isolates in the current
snapshot carrying a gene in the family asked about, the first twenty of them
with their full AMR genotype list and a link to each isolate's page, which
gene prefixes were searched and which deliberately were not, and the
organism cited to its NCBI Taxonomy record.

Three jobs, read top to bottom:

- `parse_isolate_question`: recognise the shape by a fixed rule, never the
  model: an isolate word, an organism from `ORGANISMS`, and either a gene
  family word from `GENE_FAMILIES` or an explicit gene token. Returns the
  organism, the gene prefixes to search, and the two clarifications the
  shape can need (no organism, no gene).
- `plan_calls`: the two calls the shape plans and no graph call: one
  `pathogen_detection` `isolate_search` over the organism's FTP taxon
  folder, then one `ncbi_efetch` summary of the organism's Taxonomy record,
  so the organism is cited to NCBI as the golden row requires.
- `disclosure` and `count_sentence`: the sentences Think and Write need,
  which prefixes were searched and why some were not, and how many isolates
  were found against how many are shown.

Why "ESBL" searches the blaCTX-M family only, measured 2026-09-22
(`testing/Developer/reports/2026-09-22_isolate_search/probes.md`): 279,100 of
584,433 E. coli isolates carry a blaTEM allele, nearly all the narrow-spectrum
blaTEM-1, and whether a blaTEM or blaSHV allele is an ESBL cannot be told from
its name. Every blaCTX-M allele is an ESBL. A confident wrong record is worse
than a missing one, so the family is searched on the prefix that is right by
construction and the omission is said out loud.

Every taxonomy id in `ORGANISMS` was verified live against NCBI Taxonomy on
2026-09-22 (ESearch on `[Scientific Name]`), and every taxon folder is one the
FTP root listed the same day (probes.md, item A). Extend the table only from
both sources.

Depends on:
    - system_03_search_agent.core.breadth_plan (PlannedCall)
    - system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchInput)
    - system_03_search_agent.tools.pathogen_detection_schemas
      (PathogenDetectionInput)

Reads:
    - Nothing. Pure functions over their arguments.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.core.graph (think_node, plan_node) and
      core.state, the wiring for golden question G-035.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from system_03_search_agent.core.breadth_plan import PlannedCall
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput
from system_03_search_agent.tools.pathogen_detection_schemas import PathogenDetectionInput

#: How many isolates the answer shows. The tool counts every match to the end
#: of the file; this is the sample, chosen so the record table stays readable.
ISOLATES_SHOWN: Final[int] = 20


@dataclass(frozen=True)
class Organism:
    """One organism Pathogen Detection covers, as a person names it.

    `label` is the name the answer uses, `taxon_folder` the FTP folder the
    tool reads, `taxid` the NCBI Taxonomy id (verified live), and `patterns`
    the word-bounded, case-insensitive spellings a question may use. A
    genus entry (`Klebsiella`) sits AFTER its species entry (`Klebsiella
    pneumoniae`) so the longer, more specific name wins when both match.
    """

    label: str
    taxon_folder: str
    taxid: int
    patterns: tuple[str, ...]

    @property
    def curie(self) -> str:
        return f"NCBITaxon:{self.taxid}"


ORGANISMS: Final[tuple[Organism, ...]] = (
    Organism("Escherichia coli", "Escherichia_coli_Shigella", 562, (r"escherichia\s+coli", r"e\.?\s*coli")),
    Organism("Shigella", "Escherichia_coli_Shigella", 620, (r"shigella",)),
    Organism("Salmonella", "Salmonella", 590, (r"salmonella",)),
    Organism("Listeria monocytogenes", "Listeria", 1639, (r"listeria\s+monocytogenes", r"l\.\s*monocytogenes")),
    Organism("Listeria", "Listeria", 1637, (r"listeria",)),
    Organism("Klebsiella pneumoniae", "Klebsiella", 573, (r"klebsiella\s+pneumoniae", r"k\.\s*pneumoniae")),
    Organism("Klebsiella", "Klebsiella", 570, (r"klebsiella",)),
    Organism("Campylobacter jejuni", "Campylobacter", 197, (r"campylobacter\s+jejuni", r"c\.\s*jejuni")),
    Organism("Campylobacter", "Campylobacter", 194, (r"campylobacter",)),
    Organism("Staphylococcus aureus", "Staphylococcus_aureus", 1280, (r"staphylococcus\s+aureus", r"s\.\s*aureus", r"\bmrsa\b")),
    Organism("Pseudomonas aeruginosa", "Pseudomonas_aeruginosa", 287, (r"pseudomonas\s+aeruginosa", r"p\.\s*aeruginosa")),
    Organism("Acinetobacter", "Acinetobacter", 469, (r"acinetobacter",)),
    Organism("Enterococcus faecium", "Enterococcus_faecium", 1352, (r"enterococcus\s+faecium", r"e\.\s*faecium")),
    Organism("Enterococcus faecalis", "Enterococcus_faecalis", 1351, (r"enterococcus\s+faecalis", r"e\.\s*faecalis")),
    Organism("Enterobacter cloacae", "Enterobacter_cloacae", 550, (r"enterobacter\s+cloacae",)),
    Organism("Vibrio cholerae", "Vibrio_cholerae", 666, (r"vibrio\s+cholerae", r"v\.\s*cholerae")),
    Organism("Clostridioides difficile", "Clostridioides_difficile", 1496, (r"clostridi(?:oides|um)\s+difficile", r"c\.\s*diff(?:icile)?\b")),
    Organism("Neisseria gonorrhoeae", "Neisseria_gonorrhoeae", 485, (r"neisseria\s+gonorrhoeae", r"n\.\s*gonorrhoeae")),
    Organism("Mycobacterium tuberculosis", "Mycobacterium_tuberculosis", 1773, (r"mycobacterium\s+tuberculosis", r"m\.\s*tuberculosis")),
    Organism("Streptococcus pneumoniae", "Streptococcus_pneumoniae", 1313, (r"streptococcus\s+pneumoniae", r"s\.\s*pneumoniae")),
)

#: The organisms the clarification names as examples, in the order a person
#: is most likely to mean.
_EXAMPLE_ORGANISMS: Final[str] = (
    "Escherichia coli, Salmonella, Listeria monocytogenes, Klebsiella pneumoniae or Campylobacter"
)


@dataclass(frozen=True)
class GeneFamily:
    """A resistance gene family a person names in words, and what it searches.

    `prefixes` are the AMR genotype prefixes the tool matches (boundary
    aware, so `blaOXA-48` never matches `blaOXA-484`). `omitted` is the
    sentence stating what the family deliberately does not search and why,
    or empty when the prefixes cover the family by construction.
    """

    key: str
    label: str
    patterns: tuple[str, ...]
    prefixes: tuple[str, ...]
    omitted: str = ""


GENE_FAMILIES: Final[tuple[GeneFamily, ...]] = (
    GeneFamily(
        "esbl",
        "extended-spectrum beta-lactamase (ESBL) genes",
        (r"\besbls?\b", r"extended[\s-]+spectrum\s+(?:beta|β)[\s-]*lactamases?"),
        ("blaCTX-M",),
        (
            "blaTEM and blaSHV alleles were not searched: most are not ESBLs and the "
            "name alone cannot tell an ESBL allele from a narrow-spectrum one, so "
            "listing them would show isolates that do not carry an ESBL"
        ),
    ),
    GeneFamily(
        "carbapenemase",
        "carbapenemase genes",
        (r"carbapenemases?", r"carbapenem[\s-]+resist\w*", r"\bcre\b", r"\bcpe\b"),
        ("blaKPC", "blaNDM", "blaOXA-48", "blaVIM", "blaIMP"),
        (
            "other blaOXA alleles were not searched, since only the blaOXA-48 family "
            "is a carbapenemase by name"
        ),
    ),
    GeneFamily(
        "colistin",
        "mobile colistin resistance (mcr) genes",
        (r"colistin", r"\bmcr\b"),
        ("mcr-",),
    ),
    GeneFamily(
        "methicillin",
        "methicillin resistance (mec) genes",
        (r"methicillin", r"\bmrsa\b"),
        ("mecA", "mecC"),
    ),
    GeneFamily(
        "vancomycin",
        "vancomycin resistance (van) genes",
        (r"vancomycin", r"\bvre\b"),
        ("vanA", "vanB"),
    ),
)

#: An explicit AMR gene as AMRFinderPlus spells it: a `bla` gene with its
#: family and optional allele number, an `mcr` gene, or one of the other
#: named genes a person types. Word-bounded on the left, and the token ends
#: where the gene spelling does, so a sentence comma never joins it.
_GENE_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z0-9])("
    r"bla[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*"
    r"|mcr-\d+(?:\.\d+)?"
    r"|mec[A-Ca-c]\b|van[A-Za-z]\b|qnr[A-Za-z]\d*\b|sul[1-4]\b|erm\([A-Z]\)|erm[A-Z]\b"
    r"|tet\([A-Z0-9]+\)|aac\(6'\)-Ib-cr|fosA\d*\b|arm[A-Z]\b|rmt[A-Z]\b|optrA\b|cfr\b"
    r")",
)

#: The shape's trigger words. Without one of these a question naming an
#: organism and a gene is not an isolate question, and stays on its own path.
_ISOLATE_WORDS: Final[re.Pattern[str]] = re.compile(
    r"\bisolates?\b|pathogen\s+detection", re.IGNORECASE
)

#: A Pathogen Detection isolate (`PDT...`) or SNP cluster (`PDS...`) identifier.
#: A question naming one is about THAT record, the tool's older two modes
#: and competency question Q5, never a search by gene, so the shape stands
#: aside for it whatever else the sentence says.
_PATHOGEN_RECORD_ID: Final[re.Pattern[str]] = re.compile(r"\bPD[TS]\d{6,}", re.IGNORECASE)

#: The shape's own two clarifications, in the person's words.
ORGANISM_QUESTION: Final[str] = (
    "Pathogen Detection is searched one organism at a time. Which organism do "
    f"you mean? For example {_EXAMPLE_ORGANISMS}."
)
GENE_QUESTION: Final[str] = (
    "Which resistance gene or gene family should the isolates carry? For example "
    "ESBL (the blaCTX-M family), carbapenemase (blaKPC, blaNDM, blaOXA-48, blaVIM, "
    "blaIMP), colistin resistance (mcr), or a gene name such as blaCTX-M-15."
)

_MAX_PREFIXES: Final[int] = 10
_MAX_PREFIX_CHARS: Final[int] = 40


@dataclass(frozen=True)
class IsolateQuestion:
    """What a fixed rule read from an isolate question.

    `organism` is None when no organism from `ORGANISMS` was named, and
    `prefixes` is empty when neither a family word nor a gene token was
    found; `clarification` then carries the question to ask instead of
    searching. `families` are the families named in words, `genes` the
    explicit gene tokens as the person typed them.
    """

    organism: Organism | None
    families: tuple[GeneFamily, ...]
    genes: tuple[str, ...]

    @property
    def prefixes(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for family in self.families:
            for prefix in family.prefixes:
                seen.setdefault(prefix, None)
        for gene in self.genes:
            seen.setdefault(gene, None)
        return tuple(seen)[:_MAX_PREFIXES]

    @property
    def clarification(self) -> str | None:
        if self.organism is None:
            return ORGANISM_QUESTION
        if not self.prefixes:
            return GENE_QUESTION
        return None


def _find_organism(text: str) -> Organism | None:
    """The first table entry whose spelling appears in `text`, species before genus."""
    lowered = text.lower()
    for organism in ORGANISMS:
        for pattern in organism.patterns:
            if re.search(r"(?<![a-z])" + pattern + r"(?![a-z])", lowered):
                return organism
    return None


def _find_families(text: str) -> tuple[GeneFamily, ...]:
    lowered = text.lower()
    return tuple(
        family
        for family in GENE_FAMILIES
        if any(re.search(pattern, lowered) for pattern in family.patterns)
    )


def _find_genes(text: str) -> tuple[str, ...]:
    """Explicit gene tokens in question order, de-duplicated, spelling kept.

    A token that a family word also covers (`blaCTX-M-15` beside "ESBL") is
    still kept: the person named it, so the disclosure names it too.
    """
    found: dict[str, None] = {}
    for match in _GENE_TOKEN.finditer(text):
        token = match.group(1)
        if 2 <= len(token) <= _MAX_PREFIX_CHARS:
            found.setdefault(token, None)
    return tuple(found)


def parse_isolate_question(text: str) -> IsolateQuestion | None:
    """Recognise an isolate question, or None when the text is not one.

    The rule: an isolate word ("isolate", "isolates", "Pathogen Detection")
    is present, and at least one of an organism, a gene family word or a
    gene token is found beside it. A question with the isolate word and
    nothing else ("what is an isolate?") is not this shape and returns None,
    so it keeps whatever path it had. So does a question naming a Pathogen
    Detection isolate or cluster identifier (`PDT000123456`), which asks
    about one record rather than for a search, competency question Q5 among
    them: the model's spans on such a question must still be confirmed, and
    the mutation harness's P1 arm pins that.
    """
    if not text or _ISOLATE_WORDS.search(text) is None:
        return None
    if _PATHOGEN_RECORD_ID.search(text) is not None:
        return None
    organism = _find_organism(text)
    families = _find_families(text)
    genes = _find_genes(text)
    if organism is None and not families and not genes:
        return None
    return IsolateQuestion(organism=organism, families=families, genes=genes)


def plan_calls(question: IsolateQuestion) -> list[PlannedCall]:
    """The two calls an isolate question plans, in order, and no graph call.

    Index 0 is the isolate search itself, so that under the Section 21.3
    ceiling it is never the call admission skips. Index 1 is the organism's
    Taxonomy summary, which is what the answer cites the organism to.
    Raises `ValueError` when the question still needs a clarification,
    since planning a search for an unnamed organism would be a guess.
    """
    if question.organism is None or not question.prefixes:
        raise ValueError("an isolate question with a clarification pending plans no call")
    organism = question.organism
    return [
        PlannedCall(
            tool="pathogen_detection",
            layer="layer_2_api",
            prefix="pd",
            purpose="isolate_search",
            tool_input=PathogenDetectionInput.model_validate(
                {
                    "mode": "isolate_search",
                    "taxon": organism.taxon_folder,
                    "amr_gene_prefixes": list(question.prefixes),
                    "max_isolates": ISOLATES_SHOWN,
                }
            ),
        ),
        PlannedCall(
            tool="ncbi_efetch",
            layer="layer_2_api",
            prefix="ef",
            purpose="taxonomy_summary",
            tool_input=NcbiEfetchInput.model_validate(
                {"action": "summary", "db": "taxonomy", "ids": [str(organism.taxid)]}
            ),
        ),
    ]


def disclosure(question: IsolateQuestion) -> str:
    """The Think narrative's clause: what will be searched, and what will not.

    "searching Escherichia coli isolates in Pathogen Detection for AMR
    genotypes starting blaCTX-M; blaTEM and blaSHV alleles were not
    searched: ..."
    """
    assert question.organism is not None
    parts = [
        (
            f"searching {question.organism.label} isolates in Pathogen Detection for AMR "
            f"genotypes starting {', '.join(question.prefixes)}"
        )
    ]
    for family in question.families:
        if family.omitted:
            parts.append(family.omitted)
    return "; ".join(parts)


def count_sentence(organism_label: str, shown: int, total: int, complete: bool) -> str:
    """The sentence under the answer stating the count and the cut.

    Exact when the tool read the whole file, "at least" when its time ran
    out first, so the person is never told a total nobody counted.
    """
    total_words = f"{total:,}" if complete else f"at least {total:,}"
    noun = "isolate" if total == 1 else "isolates"
    if shown >= total and complete:
        return f"Pathogen Detection lists {total_words} {organism_label} {noun} with these genes, all shown."
    return (
        f"Pathogen Detection lists {total_words} {organism_label} {noun} with these genes; "
        f"the first {shown:,} in the snapshot are shown."
    )
