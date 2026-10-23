"""Card 130 (2026-10-22): the writer is given the column the table shows.

For a list answer the writer was handed one finding per record, its name,
so a sentence could only repeat a name (dropped as a restatement) or say
more than any record backed (stripped). The table showed more than the
writer saw: an ortholog's organism, a dbSNP record's gene, an isolate's
resistance genes. Each now reaches the writer as a second finding, cited to
the same record, built from the row's own field and never from the
question's words.

What a reader must never see change, and the arms that hold it:

- the records listed: a column finding takes no display slot, is never a
  listing entry and never collapses two records that share a page;
- the completeness accounting: a column finding is never reported missing
  on its own, so it cannot start a second writing call;
- the code-built listing's text, byte for byte.

Coverage statement (goal-contracts): each of the three row types from the
real row builders (`cypher_query` with a faked executor for the ortholog,
`core.graph._layer_tool_output_to_structured_fields` for the dbSNP and the
isolate rows), the display cap with and without the lead quota, the
listing, the restatement grouping, the completeness list, the prompt
adjacency, and the rows that must get no column finding (other types, a
blank or sentinel value, a value already picked). NOT exercised here: the
live writer, the grounding pass on the writer's sentences, and the
variant-to-condition column, which needs MedGen titles that `core.graph`
resolves after this module runs (reported, not built).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness.coordinator_worker import Finding
from system_03_search_agent.synthesis.findings import (
    ROW_COLUMN_FIELDS,
    build_structured_fallback_narrative,
    build_synth_findings,
    column_value_for_row,
    one_finding_per_record,
    render_findings_block,
    unreported_findings,
)
from system_03_search_agent.tools import cypher_query as cypher_query_module
from system_03_search_agent.tools.cypher_query import cypher_query
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.ncbi_dbsnp_schemas import NcbiDbsnpGene, NcbiDbsnpOutput
from system_03_search_agent.tools.pathogen_detection_schemas import (
    PathogenDetectionOutput,
    PathogenIsolate,
)

PICK = graph_module._pick_representative_field
TP53 = "NCBIGene:7157"
ISOLATE_URL = "https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:{acc}"


# ------------------------------------------------------------ real row shapes


class _RefusingHarness:
    trace_id = "card130-trace"

    def get_query_cost_usd(self, trace_id: str) -> float:
        return 0.0

    async def call_tier(self, tier: str, messages: list[dict[str, str]], **_: Any) -> Any:
        raise AssertionError("plan tier called on the template path")


def _gene_vertex(curie: str) -> str:
    payload = {
        "id": 1,
        "label": "Gene",
        "properties": {
            "id": curie,
            "name": "tumor protein p53",
            "source_url": f"https://www.ncbi.nlm.nih.gov/gene/{curie.split(':')[1]}",
        },
    }
    return json.dumps(payload) + "::vertex"


async def _ortholog_rows(monkeypatch: pytest.MonkeyPatch, species: list[list[str]]) -> list[dict]:
    """Ortholog rows as `cypher_query` and `core.graph` really shape them."""
    rows = [
        {"c0": _gene_vertex(f"NCBIGene:{100000 + n}"), "c1": json.dumps(names)}
        for n, names in enumerate(species)
    ]

    def _fake_execute(cypher, params=None, row_limit=100, timeout_s=30.0, as_clause=None):
        if "total_count" in cypher:
            return [{"c0": str(len(rows))}], 1
        return rows, len(rows)

    monkeypatch.setattr(cypher_query_module, "execute_cypher", _fake_execute)
    output = await cypher_query(
        _RefusingHarness(),
        CypherQueryInput(
            query_intent="What are the known orthologs of TP53 in other species?",
            query_class="single_hop",
            target_entities=[TP53],
        ),
    )
    assert output.status == "ok" and output.template == "gene_orthologs_one"
    shaped = graph_module._cypher_output_to_structured_fields(output)
    assert shaped["rows"], "populate-check: no ortholog rows"
    return shaped["rows"]


def _dbsnp_row(rsid: str, *, significance: list[str], consequence: list[str], gene: str) -> dict:
    output = NcbiDbsnpOutput(
        status="ok",
        rsid=rsid,
        spdi_canonical="NC_000011.10:5227001:T:A",
        chrpos="11:5227002",
        clinical_significance=significance,
        functional_consequence=consequence,
        genes=[NcbiDbsnpGene(name=gene)],
        source_url=f"https://www.ncbi.nlm.nih.gov/snp/{rsid}",
    )
    shaped = graph_module._layer_tool_output_to_structured_fields("ncbi_dbsnp", output)
    assert shaped["rows"], "populate-check: the real dbSNP builder returned no row"
    return shaped["rows"][0]


def _isolate_rows(isolates: list[tuple[str, str | None, list[str]]]) -> list[dict]:
    output = PathogenDetectionOutput(
        status="ok",
        mode="isolate_search",
        pdg_snapshot="PDG000000004.6314",
        isolates=[
            PathogenIsolate(
                biosample_acc=acc,
                strain=strain,
                geo_loc_name="USA:AZ",
                collection_date="2013-03-05",
                amr_genotypes=genes,
                source_url=ISOLATE_URL.format(acc=acc),
            )
            for acc, strain, genes in isolates
        ],
        isolate_count=len(isolates),
        total_available=len(isolates),
        truncated=False,
        rows_scanned=584_433,
        scan_complete=True,
    )
    shaped = graph_module._layer_tool_output_to_structured_fields("pathogen_detection", output)
    assert shaped["rows"], "populate-check: the real isolate builder returned no row"
    return shaped["rows"]


def _finding(rows: list[dict], *, tool: str, layer: str, call_id: str | None = None) -> Finding:
    return Finding(
        call_id=call_id or f"call-{tool}",
        tool=tool,
        layer=layer,  # type: ignore[arg-type]
        source="structured_pass_through",
        structured_fields={
            "status": "ok",
            "row_count": len(rows),
            "total_available": len(rows),
            "truncated": False,
            "rows": rows,
            "error": None,
        },
        extracted_entities=None,
        normalized_ids=None,
        evidence_summary=None,
    )


def _shape(findings) -> list[tuple[str, str, bool]]:
    return [(f.field, f.field_value, f.row_detail) for f in findings]


# ---------------------------------------------------------- the three columns


@pytest.mark.asyncio
async def test_an_ortholog_reaches_the_writer_with_its_organism(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = await _ortholog_rows(monkeypatch, [["Oryctolagus cuniculus"], ["Oryzias latipes"]])
    synth, capped = build_synth_findings(
        [_finding(rows, tool="cypher_query", layer="layer_1_graph")], PICK
    )
    assert not capped
    assert _shape(synth) == [
        ("name", "tumor protein p53", False),
        ("organism", "Oryctolagus cuniculus", True),
        ("name", "tumor protein p53", False),
        ("organism", "Oryzias latipes", True),
    ]
    # Cited to the same record as its row, and numbered right behind it.
    assert synth[1].source_url == synth[0].source_url and synth[1].curie == synth[0].curie
    assert [f.ref_index for f in synth] == [1, 2, 3, 4]
    assert synth[1].entity_type == "Gene"


def test_a_dbsnp_record_reaches_the_writer_with_its_gene() -> None:
    rs334 = _dbsnp_row(
        "rs334",
        significance=["not-provided", "pathogenic"],
        consequence=["missense variant"],
        gene="HBB",
    )
    rs6025 = _dbsnp_row(
        "rs6025",
        significance=[],
        consequence=["coding_sequence_variant", "missense_variant"],
        gene="F5",
    )
    synth, _ = build_synth_findings(
        [_finding([rs334, rs6025], tool="ncbi_dbsnp", layer="layer_2_api")], PICK
    )
    assert _shape(synth) == [
        ("clinical_significance", "not-provided, pathogenic", False),
        ("genes", "HBB", True),
        ("functional_consequence", "coding_sequence_variant, missense_variant", False),
        ("genes", "F5", True),
    ]
    assert synth[1].source_url == "https://www.ncbi.nlm.nih.gov/snp/rs334"
    assert synth[3].source_url == "https://www.ncbi.nlm.nih.gov/snp/rs6025"


def test_an_isolate_reaches_the_writer_with_its_resistance_genes() -> None:
    rows = _isolate_rows(
        [
            ("SAMN01", "EC-17", ["mcr-1.1", "blaCTX-M-55"]),
            ("SAMN02", None, ["mcr-1.1"]),
        ]
    )
    synth, _ = build_synth_findings(
        [_finding(rows, tool="pathogen_detection", layer="layer_2_api")], PICK
    )
    assert _shape(synth) == [
        ("name", "EC-17", False),
        ("amr_genotypes", "mcr-1.1, blaCTX-M-55", True),
        ("name", "SAMN02", False),
        ("amr_genotypes", "mcr-1.1", True),
    ]
    assert synth[3].source_url == ISOLATE_URL.format(acc="SAMN02")


# ------------------------------------------------------- what must not change


def test_a_column_finding_takes_no_display_slot() -> None:
    """Mutation arm: counting the column finding against the cap halves the
    records a reader is shown. Three isolates under a cap of three must all
    be admitted, each with its genes, and the answer is not called partial."""
    rows = _isolate_rows([(f"SAMN0{n}", f"EC-{n}", ["mcr-1.1"]) for n in range(3)])
    synth, capped = build_synth_findings(
        [_finding(rows, tool="pathogen_detection", layer="layer_2_api")], PICK, max_findings=3
    )
    assert [f.field_value for f in synth if not f.row_detail] == ["EC-0", "EC-1", "EC-2"]
    assert sum(f.row_detail for f in synth) == 3
    assert capped is False

    # Populate-check: a fourth record over the same cap is still cut, and
    # its column finding goes with it, and the answer says it is partial.
    rows4 = _isolate_rows([(f"SAMN0{n}", f"EC-{n}", ["mcr-1.1"]) for n in range(4)])
    synth4, capped4 = build_synth_findings(
        [_finding(rows4, tool="pathogen_detection", layer="layer_2_api")], PICK, max_findings=3
    )
    assert [f.field_value for f in synth4 if not f.row_detail] == ["EC-0", "EC-1", "EC-2"]
    assert len(synth4) == 6 and capped4 is True


def test_the_lead_quota_admits_the_same_records_as_before() -> None:
    lead = _finding(
        _isolate_rows([(f"SAMN0{n}", f"EC-{n}", ["mcr-1.1"]) for n in range(5)]),
        tool="pathogen_detection",
        layer="layer_2_api",
        call_id="lead",
    )
    context = _finding(
        [
            {
                "curie": "",
                "node_or_edge_type": "Taxonomy",
                "fields": {"name": "Escherichia coli"},
                "source_url": "https://www.ncbi.nlm.nih.gov/taxonomy/562",
            }
        ],
        tool="ncbi_efetch",
        layer="layer_2_api",
        call_id="ctx",
    )
    synth, capped = build_synth_findings(
        [context, lead], PICK, max_findings=4, lead_call_ids=frozenset({"lead"}), lead_quota=2
    )
    records = [f.field_value for f in synth if not f.row_detail]
    assert records == ["EC-0", "EC-1", "EC-2", "Escherichia coli"]
    # Every admitted isolate is followed by its own genes, and nothing else.
    for index, finding in enumerate(synth):
        if finding.row_detail:
            assert synth[index - 1].source_url == finding.source_url
            assert not synth[index - 1].row_detail
    assert capped is True
    assert [f.ref_index for f in synth] == list(range(1, len(synth) + 1))


@pytest.mark.asyncio
async def test_the_listing_and_its_text_do_not_change(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = await _ortholog_rows(monkeypatch, [["Oryctolagus cuniculus"], ["Oryzias latipes"]])
    synth, _ = build_synth_findings(
        [_finding(rows, tool="cypher_query", layer="layer_1_graph")], PICK
    )
    primaries = [f for f in synth if not f.row_detail]
    listed = one_finding_per_record(synth)
    assert listed == primaries and all(not f.row_detail for f in listed)
    assert "organism" not in build_structured_fallback_narrative(synth)
    assert build_structured_fallback_narrative(synth) == build_structured_fallback_narrative(
        primaries
    )


def test_records_sharing_a_page_are_not_collapsed_by_their_columns() -> None:
    """Mutation arm: grouping the column findings with their rows turns a
    page two genes share into one record's several views, and one gene
    disappears from the listing."""
    page = "https://www.ncbi.nlm.nih.gov/gene/672"
    rows = [
        {
            "curie": f"NCBIGene:{n}",
            "node_or_edge_type": "Gene",
            "fields": {"name": f"gene {n}", "organism": f"Species {n}"},
            "source_url": page,
        }
        for n in (672, 673)
    ]
    synth, _ = build_synth_findings(
        [_finding(rows, tool="cypher_query", layer="layer_1_graph")], PICK
    )
    assert sum(f.row_detail for f in synth) == 2, "populate-check: no column findings"
    assert [f.field_value for f in one_finding_per_record(synth)] == ["gene 672", "gene 673"]


def test_a_column_finding_is_never_reported_missing_on_its_own() -> None:
    """Mutation arm: a column finding the prose did not cite would ask for
    a second writing call on almost every list answer, though the table
    already shows its value beside its record."""
    rows = _isolate_rows([("SAMN01", "EC-1", ["mcr-1.1"]), ("SAMN02", "EC-2", ["mcr-3.1"])])
    synth, _ = build_synth_findings(
        [_finding(rows, tool="pathogen_detection", layer="layer_2_api")], PICK
    )
    missing = unreported_findings(set(), synth)
    assert [f.field_value for f in missing] == ["EC-1", "EC-2"]
    cited_first = unreported_findings({synth[0].citation_id}, synth)
    assert [f.field_value for f in cited_first] == ["EC-2"]


def test_the_writer_reads_each_column_right_behind_its_record() -> None:
    rows = _isolate_rows([("SAMN01", "EC-1", ["mcr-1.1", "blaTEM-1"])])
    synth, _ = build_synth_findings(
        [_finding(rows, tool="pathogen_detection", layer="layer_2_api")], PICK
    )
    block = render_findings_block(synth)
    first = block.index("EC-1")
    second = block.index("amr_genotypes: mcr-1.1, blaTEM-1")
    assert first < second


# --------------------------------------------------- rows that get no column


def test_only_the_closed_table_of_row_types_gets_a_column() -> None:
    assert ROW_COLUMN_FIELDS == {
        "Gene": "organism",
        "Variant record": "genes",
        "Pathogen Detection isolate": "amr_genotypes",
    }
    # A Layer 2 gene record is a different row type from the graph's Gene.
    assert column_value_for_row({"node_or_edge_type": "gene", "fields": {"organism": "x y"}}, "name") is None
    assert (
        column_value_for_row(
            {"node_or_edge_type": "SequenceVariant", "fields": {"organism": "Homo sapiens"}}, "name"
        )
        is None
    )
    # Populate-check: the same row as a graph Gene does get one.
    assert column_value_for_row(
        {"node_or_edge_type": "Gene", "fields": {"organism": "Homo sapiens"}}, "name"
    ) == ("organism", "Homo sapiens")


@pytest.mark.parametrize("value", [None, "", "   ", "None", "null", "-", "n/a", ["x"], 3, True])
def test_a_blank_or_degenerate_column_value_gives_no_finding(value: Any) -> None:
    assert column_value_for_row({"node_or_edge_type": "Gene", "fields": {"organism": value}}, "name") is None


def test_a_column_already_picked_as_the_row_finding_is_not_repeated() -> None:
    row = {"node_or_edge_type": "Variant record", "fields": {"genes": "HBB"}}
    assert column_value_for_row(row, "genes") is None
    synth, _ = build_synth_findings(
        [
            _finding(
                [{**row, "curie": "", "source_url": "https://www.ncbi.nlm.nih.gov/snp/rs1"}],
                tool="ncbi_dbsnp",
                layer="layer_2_api",
            )
        ],
        PICK,
    )
    assert _shape(synth) == [("genes", "HBB", False)]
