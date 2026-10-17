"""Card 37, slice A2: the writer is given a variant's gene.

A dbSNP record's `genes` field reaches the writer as one low-risk
companion finding (field `gene`) right after the record's own finding, so
"rs334 is in the HBB gene [1]." can pass the unchanged grounding gate and
be cited to rs334's dbSNP record. Only row type `Variant record` gains a
companion; every other row type's findings are unchanged.
"""

from __future__ import annotations

from typing import Any

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.findings import SynthFinding, build_synth_findings
from system_03_search_agent.synthesis.grounding import run_grounding_pass
from system_03_search_agent.synthesis.trust import aggregate, risk_tier_for, trust_for_claims
from system_03_search_agent.tools.ncbi_dbsnp_schemas import NcbiDbsnpOutput

_URL = "https://www.ncbi.nlm.nih.gov/snp/rs334"
_QUESTION = "What is rs334 and what condition is it associated with?"


def _dbsnp_output(genes: Any = None) -> NcbiDbsnpOutput:
    return NcbiDbsnpOutput(
        status="ok",
        rsid="rs334",
        spdi_canonical="NC_000011.10:5227001:T:A",
        clinical_significance=["pathogenic"],
        genes=genes if genes is not None else [{"name": "HBB", "gene_id": "3043"}],
        source_url=_URL,
    )


def _finding(out: NcbiDbsnpOutput, call_id: str = "db-1") -> Finding:
    return Finding(
        call_id=call_id,
        tool="ncbi_dbsnp",
        layer="layer_2_api",
        source="structured_pass_through",
        structured_fields=graph_module._layer_tool_output_to_structured_fields("ncbi_dbsnp", out),
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


def _build(findings: list[Finding], **kw: Any) -> tuple[list[SynthFinding], bool]:
    return build_synth_findings(findings, graph_module._pick_representative_field, **kw)


def _generic_finding(tool: str, layer: str, row: dict[str, Any], call_id: str) -> Finding:
    return Finding(
        call_id=call_id,
        tool=tool,
        layer=layer,
        source="structured_pass_through",
        structured_fields={"status": "ok", "row_count": 1, "rows": [row]},
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


def test_rs334_row_gives_its_own_finding_first_then_the_gene() -> None:
    synth, capped = _build([_finding(_dbsnp_output())])
    assert [(f.field, f.field_value) for f in synth] == [
        ("clinical_significance", "pathogenic"),
        ("gene", "HBB"),
    ]
    first, companion = synth
    assert companion.source_url == first.source_url == _URL
    assert companion.entity_type == "Variant record"
    assert companion.tool == "ncbi_dbsnp" and companion.call_id == "db-1"
    assert companion.citation_id == "db-1-2" and first.citation_id == "db-1-1"
    assert risk_tier_for(companion.field, companion.entity_type) == "low"
    assert capped is False


def test_gene_companion_citation_resolves_to_the_dbsnp_record() -> None:
    out = _dbsnp_output()
    synth, _ = _build([_finding(out)])
    companion = synth[1]
    citation = graph_module._layer3_base_citation(companion, out, 2)
    assert citation is not None
    assert citation.source == "dbsnp" and citation.source_id == "rs334"
    assert citation.source_url == _URL


def test_a_gene_sentence_passes_the_unchanged_gate_and_cites_the_record() -> None:
    synth, _ = _build([_finding(_dbsnp_output())])
    result = run_grounding_pass("rs334 is in the HBB gene [2].", synth, question=_QUESTION)
    assert result.grounded
    assert result.narrative == "rs334 is in the HBB gene [1]."
    assert [c.finding.field for c in result.claims] == ["gene"]


def test_only_the_gene_sentence_surviving_still_answers_and_the_most_restrictive_governs() -> None:
    synth, _ = _build([_finding(_dbsnp_output())])
    result = run_grounding_pass("rs334 is in the HBB gene [2].", synth, question=_QUESTION)
    trust = trust_for_claims(
        result.claims, synth, {f.citation_id: ("Variant record", False) for f in synth}
    )
    # The gene claim is low risk, so on its own the verdict is `answer`
    # instead of the fallback's refusal.
    assert [t.outcome for t in trust] == ["answer"]
    assert aggregate([t.outcome for t in trust]) == "answer"
    # With the significance claim also surviving, the most restrictive
    # claim still governs, exactly as before this change.
    both = run_grounding_pass(
        "rs334 is pathogenic [1]. rs334 is in the HBB gene [2].", synth, question=_QUESTION
    )
    outcomes = [
        t.outcome
        for t in trust_for_claims(
            both.claims, synth, {f.citation_id: ("Variant record", False) for f in synth}
        )
    ]
    assert len(outcomes) == 2
    assert aggregate(outcomes) == min(outcomes, key=["refuse", "ask", "flag", "answer"].index)


def test_a_dbsnp_row_without_genes_yields_no_companion() -> None:
    synth, _ = _build([_finding(_dbsnp_output(genes=[]))])
    assert [f.field for f in synth] == ["clinical_significance"]


def test_a_blank_or_non_string_genes_value_yields_no_companion() -> None:
    for value in ("   ", None, ["HBB"], 7):
        row = {
            "curie": "",
            "source_url": _URL,
            "node_or_edge_type": "Variant record",
            "fields": {"clinical_significance": "pathogenic", "genes": value},
        }
        synth, _ = _build([_generic_finding("ncbi_dbsnp", "layer_2_api", row, "db-1")])
        assert [f.field for f in synth] == ["clinical_significance"], value


def test_other_row_types_are_unchanged() -> None:
    cases = [
        ("ncbi_efetch", "layer_2_api", "Gene", {"name": "TP53", "gene": "TP53"}),
        (
            "litvar2_lookup",
            "layer_3_enrichment",
            "Literature variant",
            {"name": "rs334", "gene": "HBB"},
        ),
        ("cypher_query", "layer_1_graph", "SequenceVariant", {"name": "rs334", "genes": "HBB"}),
        (
            "ncbi_efetch",
            "layer_2_api",
            "ClinVar record",
            {"clinical_significance": "pathogenic", "genes": "HBB"},
        ),
    ]
    for tool, layer, row_type, fields in cases:
        row = {
            "curie": "",
            "source_url": "https://www.ncbi.nlm.nih.gov/x/1",
            "node_or_edge_type": row_type,
            "fields": fields,
        }
        synth, _ = _build([_generic_finding(tool, layer, row, "c-1")])
        assert len(synth) == 1, (row_type, [f.field for f in synth])
        assert all(f.field not in ("gene",) or row_type == "Literature variant" for f in synth)


def test_the_companion_never_pushes_a_record_out_at_the_cap() -> None:
    def other(n: int) -> Finding:
        row = {
            "curie": f"NCBIGene:{n}",
            "source_url": f"https://www.ncbi.nlm.nih.gov/gene/{n}",
            "node_or_edge_type": "Gene",
            "fields": {"name": f"G{n}"},
        }
        return _generic_finding("ncbi_efetch", "layer_2_api", row, f"g-{n}")

    findings = [_finding(_dbsnp_output())] + [other(n) for n in range(1, 4)]
    # Develop shows the dbSNP finding and two genes at a cap of 3.
    bare, bare_capped = _build(findings, max_findings=3)
    assert [f.field_value for f in bare] == ["pathogenic", "G1", "G2"]
    assert bare_capped is True
    # Room for one more: the companion takes the free slot.
    roomy, _ = _build(findings, max_findings=5)
    assert [f.field_value for f in roomy] == ["pathogenic", "HBB", "G1", "G2", "G3"]
    # A list exactly at the cap keeps every record develop shows.
    full, full_capped = _build(findings[:3], max_findings=3)
    assert [f.field_value for f in full] == ["pathogenic", "G1", "G2"]
    assert full_capped is False
