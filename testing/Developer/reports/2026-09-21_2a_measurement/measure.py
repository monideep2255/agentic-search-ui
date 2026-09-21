"""Measure which admitted findings earn a citation through the findings tail.

Item 2a asks that every retrieved finding be cited. `tail_is_listing` is
unconditionally True in `core/graph.py`, so the tail already grounds every
admitted finding and merges those claims, which means the mechanism exists.
This script measures what it still misses.

Run from the repository root:

    PYTHONPATH=src python3 testing/Developer/reports/2026-09-21_2a_measurement/measure.py

Read-only. No server, no model, no network.
"""
from __future__ import annotations

from system_03_search_agent.synthesis.findings import (
    SynthFinding,
    build_structured_fallback_narrative,
)
from system_03_search_agent.synthesis.grounding import run_grounding_pass

QUESTION = "Which diseases are associated with BRCA1?"


def finding(index: int, field: str, value: str, entity_type: str, curie: str) -> SynthFinding:
    return SynthFinding(
        ref_index=index,
        citation_id=f"c{index}",
        layer="layer_2_api",
        tool="ncbi_efetch",
        field=field,
        field_value=value,
        source_url=f"https://www.ncbi.nlm.nih.gov/x/{index}",
        entity_type=entity_type,
        curie=curie,
    )


# Three single-sentence values and two multi-sentence ones. The two shapes
# are the whole experiment: an abstract (citeable since 9cf8572) and a gene
# summary (retrieved since 2026-09-21) are the two real finding types whose
# values routinely span several sentences.
FINDINGS = [
    finding(1, "name", "Familial cancer of breast", "Disease", "MedGen:C1"),
    finding(2, "abstract",
            "BRCA1 functions as a tumour suppressor. It participates in DNA repair.",
            "Publication", "PMID:2"),
    finding(3, "symbol", "BRCA1", "Gene", "NCBIGene:672"),
    finding(4, "summary",
            "This gene encodes a nuclear phosphoprotein. It acts as a tumor suppressor.",
            "Gene", "NCBIGene:672"),
    finding(5, "title", "A trial of olaparib", "Clinical trial", "NCT:5"),
]


def main() -> int:
    result = run_grounding_pass(
        build_structured_fallback_narrative(FINDINGS),
        FINDINGS,
        core_ask_required=True,
        question=QUESTION,
    )
    cited = {claim.finding.citation_id for claim in result.claims}
    print(
        f"admitted findings: {len(FINDINGS)}   "
        f"cited by the tail: {len(cited)}   stripped: {result.stripped_count}\n"
    )
    uncited_multi = 0
    for item in FINDINGS:
        is_cited = item.citation_id in cited
        multi = ". " in item.field_value.rstrip(".")
        if not is_cited and multi:
            uncited_multi += 1
        note = "  <- multi-sentence value" if multi else ""
        print(
            f"  [{item.ref_index}] {'CITED  ' if is_cited else 'NO CITE'} "
            f"{item.field}={item.field_value[:44]!r}{note}"
        )
    print()
    if len(cited) == len(FINDINGS):
        print("Every admitted finding is cited. Item 2a's gap is closed.")
        return 0
    print(
        f"{len(FINDINGS) - len(cited)} finding(s) uncited, of which "
        f"{uncited_multi} carry a multi-sentence value (item 11.34)."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
