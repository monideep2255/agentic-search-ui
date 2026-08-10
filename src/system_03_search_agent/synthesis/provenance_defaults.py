"""Section 9.2: the per-tool provenance default table.

Every `CitationPayload` carries four fields no tool computed before this
phase: `evidence_kind`, `assertion_confidence`, `population_ancestry_
context`, and `license`. Section 9.2 states population is "a static,
per-tool default table maintained in code, not a per-call model judgment",
and this module is that table. `core/graph.py`'s Layer 1 citation builders
(`_citation_for_row`, `_citations_from_grounded_claims`) hardcode their own
four Layer-1-only literals and are unchanged by this module; every Layer 2
and Layer 3 tool's own citation-building function reads its defaults from
here instead of hardcoding them a second time per tool.

`license` never defaults to `"unspecified"` for any of the seven tools.
Section 9.2 calls that value build-blocking for any source that reaches it,
so each entry below reflects a real, confirmed mapping against that source's
actual terms of use, not a placeholder pending confirmation:

    - `public_domain_us_gov`: every NCBI-native source (Layer 1's graph,
      `ncbi_efetch`, `ncbi_dbsnp`), plus `pathogen_detection` (NCBI Pathogen
      Detection, an NCBI-hosted FTP tree) and `clinicaltrials_search`
      (ClinicalTrials.gov, a US federal government source, NLM/NIH-operated,
      published under the same public-domain terms as other .gov clinical
      data). Neither `pathogen_detection` nor `clinicaltrials_search`
      publishes third-party copyrighted abstracts; both are federal-source
      structured records.
    - `publisher_copyright_abstract_only`: `pubtator_annotate` and
      `litvar2_lookup`. Both surface PubMed/PMC-sourced text (an entity
      annotation grounded in an abstract, a literature-evidence PMID list),
      and PubMed abstract text itself carries the original publisher's
      copyright even though the citation metadata and the annotation are
      NIH/NLM-produced. This is the same distinction Section 9.2 draws
      between a PubMed *citation* (public domain) and a PubMed *abstract*
      (publisher copyright), applied to two tools whose whole output is
      abstract-adjacent text-mining, never a bare citation record.

Depends on:
    - Nothing. Pure data and pure functions only.

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations

from typing import Literal, TypedDict

EvidenceKind = Literal[
    "primary_assertion", "derived_summary", "literature_mention",
    "external_annotation",
]
License = Literal[
    "public_domain_us_gov", "publisher_copyright_abstract_only", "unspecified",
]


class ToolDefaults(TypedDict):
    evidence_kind: EvidenceKind
    license: License


# Section 9.2's per-tool table. Every one of the seven tools (Layer 1's
# `cypher_query` included, for completeness and so a future caller cannot
# reach a KeyError for it) must appear here with a real, non-"unspecified"
# license. `test_no_tool_default_table_entry_is_left_unspecified`
# (build phase 3.4's premise gate) enforces this for every entry.
PER_TOOL_DEFAULTS: dict[str, ToolDefaults] = {
    "cypher_query": {
        "evidence_kind": "primary_assertion",
        "license": "public_domain_us_gov",
    },
    "ncbi_efetch": {
        "evidence_kind": "primary_assertion",
        "license": "public_domain_us_gov",
    },
    "ncbi_dbsnp": {
        "evidence_kind": "primary_assertion",
        "license": "public_domain_us_gov",
    },
    "pubtator_annotate": {
        "evidence_kind": "literature_mention",
        "license": "publisher_copyright_abstract_only",
    },
    "litvar2_lookup": {
        "evidence_kind": "literature_mention",
        "license": "publisher_copyright_abstract_only",
    },
    "pathogen_detection": {
        "evidence_kind": "primary_assertion",
        "license": "public_domain_us_gov",
    },
    "clinicaltrials_search": {
        "evidence_kind": "external_annotation",
        "license": "public_domain_us_gov",
    },
}


def defaults_for_tool(tool_name: str) -> ToolDefaults:
    """Look up a tool's default `evidence_kind`/`license` pair.

    Raises KeyError, deliberately, on an unregistered tool name rather than
    falling back to a guessed default: a tool with no entry here has not had
    its license confirmed against real terms of use, and Section 9.2 makes
    that a build-blocking gap, not a silently-absorbed one.
    """
    return PER_TOOL_DEFAULTS[tool_name]


# ClinVar `clinical_significance` term to `assertion_confidence`. Reused
# across `ncbi_dbsnp` (whose output carries `clinical_significance` as a
# list of these exact terms, per its own schema) and any future structured
# ClinVar-vocabulary field. Terms this table does not name fall through to
# `"hedged"`, the safer default for an unrecognized clinical term, never
# `"asserted"`.
_CLINVAR_TERM_CONFIDENCE: dict[str, str] = {
    "pathogenic": "asserted",
    "likely_pathogenic": "asserted",
    "benign": "asserted",
    "likely_benign": "asserted",
    "drug_response": "asserted",
    "risk_factor": "asserted",
    "protective": "asserted",
    "affects": "asserted",
    "association": "hedged",
    "uncertain_significance": "hedged",
    "not_provided": "hedged",
    "other": "hedged",
    "conflicting_interpretations_of_pathogenicity": "contested",
    "no_classifications_from_unflagged_records": "contested",
}

# A free-text hedge lexicon for a literature-mention finding
# (`pubtator_annotate`/`litvar2_lookup`), where there is no structured
# ClinVar term to look up. Deliberately conservative: presence of any one
# of these tokens marks the finding `"hedged"`, never `"contested"`, since a
# single lexical hedge is weaker evidence of genuine dispute than a ClinVar
# `conflicting_interpretations` classification is.
_HEDGE_LEXICON = (
    "may", "might", "possibly", "possible", "suggests", "suggest",
    "appears to", "appear to", "likely", "potential", "potentially",
    "uncertain", "unclear", "preliminary", "unconfirmed", "putative",
)


def clinvar_term_confidence(term: str) -> str:
    """`assertion_confidence` for one ClinVar `clinical_significance` term.

    Case- and separator-insensitive: the raw term is lowercased and its
    separators normalized to underscore before lookup, so `"Uncertain
    significance"`, `"uncertain_significance"`, and `"uncertain-
    significance"` all resolve to the same entry.
    """
    normalized = "_".join(term.strip().lower().replace("-", " ").split())
    return _CLINVAR_TERM_CONFIDENCE.get(normalized, "hedged")


def hedge_scan_confidence(text: str) -> str:
    """`assertion_confidence` for one free-text literature-mention finding.

    A whole-word scan, not a substring scan: `"likely"` matches the word
    "likely" but not "unlikelier". Returns `"hedged"` if any lexicon token
    appears, `"asserted"` otherwise. Never returns `"contested"`; see the
    module-level note on `_HEDGE_LEXICON` for why.
    """
    import re

    lowered = text.lower()
    for token in _HEDGE_LEXICON:
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            return "hedged"
    return "asserted"
