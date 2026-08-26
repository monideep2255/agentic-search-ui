"""Premise gate for build phase 4.4, the KGX export (T-4.4-01).

This gate exists because of what this phase can actually ship: a file that
is well-formed and wrong. Correct TSV, correct headers, correct row count,
and a subgraph that is not the one the seed names. Every shape-level check
passes on that file. Only a content check against ground truth read from
the live graph catches it.

Stage 5 of `docs/build/Build_workflow_cadence.md` requires a premise gate
to not mock the model. That clause does not apply here and is deliberately
dropped: a KGX export is deterministic, no model is in its path. Every
other stage 5 property is kept, and they are the ones doing the work.

What this gate exercises:

- A seed whose neighbourhood is small and label-scoped, so the exact set of
  neighbours is pinnable: TP53 and its 12 `gene_associated_with_condition`
  edges to Disease vertices, read live on 2026-08-19 and pinned below.
- The KGX column contract on both files, including column ORDER, since a
  shifted column is the failure a row count cannot see.
- A hub seed against a deliberately small cap, so truncation is forced and
  the manifest must disclose it.
- A seed that resolves to no vertex, so the empty path is a tested path
  rather than an afterthought.
- Provenance on every exported row, host-pinned, since a citation URL that
  only checks for `https://` can point anywhere.

- THE DEFAULT INVOCATION, with no edge-label list at all. Added
  2026-08-19 after review round 1, and it is the most important case in
  this file. Its absence let finding F-4.4-50 through: the default path
  spent its whole node budget on the highest-cardinality edge label and
  returned 500 Articles and none of the 12 disease edges this same file
  pins as ground truth, with a manifest listing all fourteen labels as
  traversed. Every other case here passes an explicit single-label list,
  so every other case walked straight past it.

What this gate deliberately OMITS, stated so the gap is arguable rather
than discovered later:

- Multi-hop traversal. Every case here is one hop. A defect that only
  appears at hop two or three is invisible to this gate, which is exactly
  the shape of finding F-2.1-A5-03 in build phase 2.1, where nine gate
  questions were all one hop from a single anchor type and a two-hop
  defect survived.
- Exhaustive per-label coverage. The default-invocation case below proves
  a high-cardinality label cannot starve the others, but it does not
  exercise all fourteen labels individually.
- Seeds that are not Gene vertices. Disease, Article, and SequenceVariant
  seeds are unexercised. `NamedThing` seeds are known broken, filed as
  F-4.4-52, and are not pinned here.
- Concurrency. A second export running against the same output directory
  is not tested.

A note on this file's own history, kept because it is the lesson. The
omission list above named "every edge label but
`gene_associated_with_condition`" from the day this gate was written, and
the phase's only critical lived exactly there. Writing a blind spot down
makes it arguable. It does not make it safe. A stated omission that
covers the DEFAULT path is not an omission, it is a hole.

Ground truth provenance: read live from the AGE graph on Hetzner on
2026-08-19 over the tunnel on 127.0.0.1:15432, via `execute_cypher` with
`MATCH (g:Gene {id: $seed})-[r:gene_associated_with_condition]->(d:Disease)`.
Twelve rows returned in 2.3 seconds. The same query unscoped by edge label
takes 23 seconds on BRCA1 and times out in the reverse direction, which is
why the export traverses per edge label rather than with a bare pattern.

A note on what is NOT asserted, and why. The Disease vertices in this
graph carry source names in their `name` field ("MedGen", "GARD",
"SNOMEDCT_US", "OMIM allelic variant") rather than disease names. That is
an upstream System 1 and System 2 ingest artifact, not something this
export can fix, so this gate asserts on `id` and `category` and never on
`name`. Asserting on `name` here would pin an upstream defect as correct.
"""

from __future__ import annotations

import csv
import json
import os
import pathlib
from pathlib import Path

import pytest

# Imported rather than restated, so this gate cannot drift from the
# label set the traversal actually walks.
from system_03_search_agent.tools.graph_schema_constants import EDGE_LABELS as ALL_EDGE_LABELS

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

TP53 = "NCBIGene:7157"
TP53_CATEGORY = "biolink:Gene"
GENE_DISEASE_PREDICATE = "biolink:gene_associated_with_condition"

# Read live 2026-08-19. Exactly twelve, no more and no fewer.
TP53_DISEASE_CURIES: frozenset[str] = frozenset(
    {
        "MedGen:C0205770",
        "MedGen:C0346153",
        "MedGen:C0346629",
        "MedGen:C0585442",
        "MedGen:C1835398",
        "MedGen:C1859972",
        "MedGen:C2239176",
        "MedGen:C2750850",
        "MedGen:C2931038",
        "MedGen:C2931822",
        "MedGen:C3553606",
        "MedGen:C4748488",
    }
)

# A hub. One unscoped hop off this seed does not complete inside the
# per-call budget, which is why it is the truncation case and not the
# happy path.
BRCA1 = "NCBIGene:672"

ABSENT_SEED = "NCBIGene:99999999"

NODE_REQUIRED_COLUMNS = ["id", "category", "name", "source", "source_url"]
EDGE_REQUIRED_COLUMNS = [
    "subject",
    "predicate",
    "object",
    "source",
    "source_url",
    "knowledge_level",
    "agent_type",
]

NCBI_HOST_SUFFIX = ".ncbi.nlm.nih.gov"


def _load_env_explicitly() -> None:
    """Populate the graph variables from .env.

    Same reason as `test_cypher_query_premise.py`'s copy (finding
    F-2.1-04): nothing in this repo calls `load_dotenv()`, so these reach
    `os.environ` only as a side effect of importing litellm, and this file
    must not depend on that.
    """
    env_path = _REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if "=" not in stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _graph_is_reachable() -> bool:
    """Whether Layer 1 answers right now, over whichever transport is live.

    Build phase 4.12. This used to open a TCP socket to `GRAPH_PG_HOST` and
    `GRAPH_PG_PORT`, the local port of the SSH tunnel build phase 4.11
    deleted. Measured 2026-08-24 on a machine where the graph was perfectly
    reachable over HTTPS: that probe returned False with
    ConnectionRefusedError, so every live arm behind this gate SKIPPED while
    printing a reason that was false. A green run then reads as "this class
    is covered" when the arms never ran.

    Delegates to `tests.system_03_search_agent.graph_gate`, the ONE
    implementation, which dispatches on `GRAPH_QUERY_URL` exactly as
    `graph_connection.execute_cypher` and `tracker/preflight.py` do. Eight
    corrected copies would have left eight places for the next transport
    change to be applied seven times.
    """
    from tests.system_03_search_agent.graph_gate import live_graph_arms_enabled

    return live_graph_arms_enabled()


requires_graph = pytest.mark.skipif(
    not _graph_is_reachable(),
    reason="Layer 1 graph unreachable: open the tunnel and re-run",
)


def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, list(reader)


def _export(tmp_path: Path, **kwargs):
    """Call the export under test.

    Imported inside the call rather than at module scope so that collection
    of this file reports a real assertion failure per test while the module
    does not yet exist, instead of erroring out the whole file at import.
    """
    from system_03_search_agent.export.kgx import export_subgraph

    return export_subgraph(output_dir=tmp_path, **kwargs)


@requires_graph
def test_export_contains_exactly_the_seed_neighbourhood_the_graph_holds(
    tmp_path: Path,
) -> None:
    """The content check. Shape-level checks all pass on a wrong subgraph."""
    result = _export(
        tmp_path,
        seeds=[TP53],
        hops=1,
        edge_labels=("gene_associated_with_condition",),
    )

    _, node_rows = _read_tsv(result.nodes_path)
    _, edge_rows = _read_tsv(result.edges_path)

    node_ids = {row["id"] for row in node_rows}
    assert TP53 in node_ids, "the seed itself must appear in the export"
    assert node_ids - {TP53} == TP53_DISEASE_CURIES, (
        "exported neighbours must be exactly the twelve MedGen conditions the "
        "graph holds for TP53, no extras and none missing"
    )

    seed_row = next(row for row in node_rows if row["id"] == TP53)
    assert seed_row["category"] == TP53_CATEGORY
    for row in node_rows:
        if row["id"] == TP53:
            continue
        assert row["category"] == "biolink:Disease"

    assert len(edge_rows) == len(TP53_DISEASE_CURIES)
    for row in edge_rows:
        assert row["subject"] == TP53
        assert row["predicate"] == GENE_DISEASE_PREDICATE
        assert row["object"] in TP53_DISEASE_CURIES
    assert {row["object"] for row in edge_rows} == TP53_DISEASE_CURIES


@requires_graph
def test_both_files_carry_the_kgx_required_columns_first_and_in_order(
    tmp_path: Path,
) -> None:
    """Column ORDER, not just presence. A shifted column reads as valid TSV."""
    result = _export(
        tmp_path,
        seeds=[TP53],
        hops=1,
        edge_labels=("gene_associated_with_condition",),
    )

    node_fields, _ = _read_tsv(result.nodes_path)
    edge_fields, _ = _read_tsv(result.edges_path)

    assert node_fields[: len(NODE_REQUIRED_COLUMNS)] == NODE_REQUIRED_COLUMNS
    assert edge_fields[: len(EDGE_REQUIRED_COLUMNS)] == EDGE_REQUIRED_COLUMNS

    node_extra = node_fields[len(NODE_REQUIRED_COLUMNS) :]
    edge_extra = edge_fields[len(EDGE_REQUIRED_COLUMNS) :]
    assert node_extra == sorted(node_extra)
    assert edge_extra == sorted(edge_extra)


@requires_graph
def test_every_exported_row_carries_host_pinned_provenance(tmp_path: Path) -> None:
    """A source_url that only checks for https:// can point anywhere."""
    result = _export(
        tmp_path,
        seeds=[TP53],
        hops=1,
        edge_labels=("gene_associated_with_condition",),
    )

    _, node_rows = _read_tsv(result.nodes_path)
    _, edge_rows = _read_tsv(result.edges_path)

    for row in node_rows + edge_rows:
        url = row["source_url"]
        assert url, "every row in this export has a resolvable source"
        assert url.startswith("https://")
        host = url.split("/")[2]
        assert host == "ncbi.nlm.nih.gov" or host.endswith(NCBI_HOST_SUFFIX)

    for row in edge_rows:
        assert row["knowledge_level"] == "knowledge_assertion"
        assert row["agent_type"] == "manual_agent"


@requires_graph
def test_hitting_a_cap_is_disclosed_in_the_manifest_not_silently_truncated(
    tmp_path: Path,
) -> None:
    """Silent truncation is this project's most-filed defect class."""
    result = _export(tmp_path, seeds=[BRCA1], hops=1, max_nodes=5)

    manifest = json.loads(result.manifest_path.read_text())

    assert manifest["truncated"] is True
    assert manifest["truncation"], "a truncated export names which cap it hit"
    hit = {entry["cap"] for entry in manifest["truncation"]}
    assert "max_nodes" in hit
    assert any(entry["value"] == 5 for entry in manifest["truncation"])

    _, node_rows = _read_tsv(result.nodes_path)
    assert len(node_rows) <= 5


@requires_graph
def test_a_seed_that_matches_no_vertex_exports_empty_with_a_reason(
    tmp_path: Path,
) -> None:
    """The empty path is a tested path, not an afterthought."""
    result = _export(tmp_path, seeds=[ABSENT_SEED], hops=1)

    node_fields, node_rows = _read_tsv(result.nodes_path)
    edge_fields, edge_rows = _read_tsv(result.edges_path)

    assert node_rows == []
    assert edge_rows == []
    assert node_fields[: len(NODE_REQUIRED_COLUMNS)] == NODE_REQUIRED_COLUMNS
    assert edge_fields[: len(EDGE_REQUIRED_COLUMNS)] == EDGE_REQUIRED_COLUMNS

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["empty_reason"], "an empty export says why it is empty"
    assert manifest["truncated"] is False


@requires_graph
def test_the_default_invocation_reaches_the_low_cardinality_labels_too(
    tmp_path: Path,
) -> None:
    """No edge-label list at all, which is what every real caller sends first.

    Pins finding F-4.4-50. A traversal that walks the labels in list order
    against one shared node budget spends all of it on `mentioned_in`,
    which is second in `EDGE_LABELS` and the highest-cardinality edge in
    the graph, and never reaches `gene_associated_with_condition`, which
    is thirteenth. The export that results is well-formed, correctly
    cited, correctly ordered, and holds none of the answer.

    This asserts the property, not the mechanism: whatever scheduling the
    traversal uses, a high-cardinality label must not be able to starve a
    low-cardinality one out of the export entirely.
    """
    result = _export(tmp_path, seeds=[TP53], hops=1)

    _, node_rows = _read_tsv(result.nodes_path)
    _, edge_rows = _read_tsv(result.edges_path)

    node_ids = {row["id"] for row in node_rows}
    missing = TP53_DISEASE_CURIES - node_ids
    assert not missing, (
        "the default invocation dropped "
        + str(len(missing))
        + " of the 12 disease neighbours the graph holds for TP53, so a "
        "high-cardinality edge label starved a low-cardinality one"
    )

    predicates = {row["predicate"] for row in edge_rows}
    assert GENE_DISEASE_PREDICATE in predicates
    assert len(predicates) > 1, (
        "every exported edge carried one predicate, which is the starvation "
        "shape F-4.4-50 named"
    )


@requires_graph
def test_the_manifest_never_claims_an_edge_label_it_did_not_traverse(
    tmp_path: Path,
) -> None:
    """Pins the disclosure half of F-4.4-50 and the judge's F-4.4-02.

    The manifest's `edge_labels` is documented as the labels actually
    traversed. Filling it with the labels REQUESTED is the same defect
    shape as build phase 4.3's two criticals: deciding a value from a
    proxy for that value rather than from the value itself. A consumer
    reading a label that was never queried concludes the graph holds no
    such edges, which is a false negative about Layer 1 contents.

    A first draft of this case passed an explicit single-label list, where
    the requested set and the traversed set cannot diverge by
    construction, so it could not fail. It was rewritten against the
    default path, which is where the divergence is real.
    """
    result = _export(tmp_path, seeds=[TP53], hops=1, max_nodes=60)

    manifest = json.loads(result.manifest_path.read_text())
    _, edge_rows = _read_tsv(result.edges_path)

    claimed = set(manifest["edge_labels"])
    observed = {row["predicate"].removeprefix("biolink:") for row in edge_rows}

    assert claimed >= observed, (
        "the manifest omitted a label that actually produced exported edges: "
        + str(sorted(observed - claimed))
    )
    assert manifest["truncated"] is True, (
        "a 60 node cap on this seed must truncate, or this case proves nothing"
    )
    assert claimed != set(ALL_EDGE_LABELS), (
        "a truncated export claims to have traversed all "
        + str(len(ALL_EDGE_LABELS))
        + " edge labels. The manifest documents this field as the labels "
        "actually traversed, so listing the labels merely REQUESTED asserts "
        "coverage the export does not have"
    )


@requires_graph
def test_the_manifest_states_the_layer_1_only_limitation(tmp_path: Path) -> None:
    """A consumer must not read this export as the full three-layer picture."""
    result = _export(
        tmp_path,
        seeds=[TP53],
        hops=1,
        edge_labels=("gene_associated_with_condition",),
    )

    manifest = json.loads(result.manifest_path.read_text())

    assert manifest["layers"] == ["layer_1"]
    note = manifest["layer_note"].lower()
    assert "layer 2" in note and "layer 3" in note
    assert manifest["seeds"] == [TP53]
    assert manifest["hops"] == 1
    assert manifest["counts"]["nodes"] == len(TP53_DISEASE_CURIES) + 1
    assert manifest["counts"]["edges"] == len(TP53_DISEASE_CURIES)
    assert manifest["graph_snapshot_version"]
    assert manifest["exported_at"]
