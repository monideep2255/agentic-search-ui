"""Unit tests for the KGX serialization and write path in kgx.py (T-4.4-03).

Two halves, neither of which needs the live graph.

The serialization half covers the shapes the premise gate deliberately
does not exercise (`tests/system_03_search_agent/export/
test_kgx_export_premise.py`'s own module docstring): a property value
carrying a tab, a newline, or a double quote, a list-valued property, a
zero-row export, extra columns sorted after the required ones, and a row
missing a column. These exercise `kgx.py`'s pure TSV-writing functions
directly against hand-built row dicts.

The write-path half, added in review round 3, covers the output-directory
discipline findings F-4.4-53, F-4.4-58 and F-4.4-59 filed against this
phase, which are one defect: the export had no discipline about the
directory it writes into. Concurrency is the fourth item on the premise
gate's own stated omission list, so it is covered here instead, with the
race made deterministic rather than scheduled (see
`TestAtomicPublish`'s own docstring for exactly how). These tests drive
the real `kgx.export_subgraph` with `traverse_subgraph` replaced by a
fake, so they exercise every line of the write path and none of the
graph.

Stated so the gap is arguable rather than discovered later, this file
does NOT cover: multi-process concurrency (every case here is threads in
one process, so it proves the ordering of the rename, not the kernel's),
crash or power-loss durability (nothing in the write path is fsynced, and
nothing here asserts it is), a staging directory and a destination that
land on different filesystems, and the real traversal or the real graph.
"""

from __future__ import annotations

import csv
import errno
import json
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from system_03_search_agent.export import kgx


def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        return fieldnames, list(reader)


class TestSerializeValue:
    def test_list_is_pipe_joined(self) -> None:
        assert kgx.serialize_value(["HGNC:1100", "OMIM:113705"]) == "HGNC:1100|OMIM:113705"

    def test_tuple_is_pipe_joined(self) -> None:
        assert kgx.serialize_value(("a", "b", "c")) == "a|b|c"

    def test_none_becomes_empty_string(self) -> None:
        assert kgx.serialize_value(None) == ""

    def test_plain_scalar_is_stringified(self) -> None:
        assert kgx.serialize_value(672) == "672"
        assert kgx.serialize_value("NCBIGene:672") == "NCBIGene:672"

    def test_empty_list_becomes_empty_string(self) -> None:
        assert kgx.serialize_value([]) == ""


class TestFieldnameOrdering:
    def test_extra_columns_sorted_alphabetically_after_required(self) -> None:
        records = [
            {"id": "a", "xrefs": "x", "knowledge_level": "y", "agent_type": "z"},
            {"id": "b", "zzz_custom": "w"},
        ]
        fieldnames = kgx._build_fieldnames(records, kgx.NODE_REQUIRED_COLUMNS)
        assert fieldnames[: len(kgx.NODE_REQUIRED_COLUMNS)] == kgx.NODE_REQUIRED_COLUMNS
        extra = fieldnames[len(kgx.NODE_REQUIRED_COLUMNS) :]
        assert extra == sorted(extra)
        assert set(extra) == {"agent_type", "knowledge_level", "xrefs", "zzz_custom"}

    def test_no_extra_columns_when_records_carry_only_required_keys(self) -> None:
        records = [{"id": "a", "category": "biolink:Gene", "name": "", "source": "", "source_url": ""}]
        fieldnames = kgx._build_fieldnames(records, kgx.NODE_REQUIRED_COLUMNS)
        assert fieldnames == kgx.NODE_REQUIRED_COLUMNS


class TestWriteTsv:
    def test_zero_row_export_still_writes_header(self, tmp_path: Path) -> None:
        path = kgx._write_tsv([], tmp_path / "nodes.tsv", kgx.NODE_REQUIRED_COLUMNS)
        fieldnames, rows = _read_tsv(path)
        assert fieldnames == kgx.NODE_REQUIRED_COLUMNS
        assert rows == []

    def test_zero_row_edges_export_still_writes_header(self, tmp_path: Path) -> None:
        path = kgx._write_tsv([], tmp_path / "edges.tsv", kgx.EDGE_REQUIRED_COLUMNS)
        fieldnames, rows = _read_tsv(path)
        assert fieldnames == kgx.EDGE_REQUIRED_COLUMNS
        assert rows == []

    def test_a_row_missing_a_column_is_written_empty_not_shifted(self, tmp_path: Path) -> None:
        # The second record has no "name" key at all, unlike the first,
        # which is exactly the "a row missing a column" case: the missing
        # field must land as an empty string in the "name" column, never
        # shift every later column left by one.
        records = [
            {"id": "NCBIGene:1", "category": "biolink:Gene", "name": "GENE1",
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/1"},
            {"id": "NCBIGene:2", "category": "biolink:Gene",
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/2"},
        ]
        path = kgx._write_tsv(records, tmp_path / "nodes.tsv", kgx.NODE_REQUIRED_COLUMNS)
        fieldnames, rows = _read_tsv(path)
        assert fieldnames == kgx.NODE_REQUIRED_COLUMNS
        second = next(r for r in rows if r["id"] == "NCBIGene:2")
        assert second["name"] == ""
        assert second["source"] == "NCBI Gene"
        assert second["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/2"

    def test_tab_newline_and_quote_round_trip_without_shifting_a_row(self, tmp_path: Path) -> None:
        hostile_name = 'a name with a "quote", a\ttab, and a\nnewline'
        records = [
            {"id": "NCBIGene:9", "category": "biolink:Gene", "name": hostile_name,
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/9"},
            {"id": "NCBIGene:10", "category": "biolink:Gene", "name": "ordinary",
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/10"},
        ]
        path = kgx._write_tsv(records, tmp_path / "nodes.tsv", kgx.NODE_REQUIRED_COLUMNS)
        fieldnames, rows = _read_tsv(path)

        assert fieldnames == kgx.NODE_REQUIRED_COLUMNS
        assert len(rows) == 2
        hostile_row = next(r for r in rows if r["id"] == "NCBIGene:9")
        ordinary_row = next(r for r in rows if r["id"] == "NCBIGene:10")

        # The row was not split or shifted: every column still holds
        # exactly what it should, including the hostile one round-tripping
        # byte for byte.
        assert hostile_row["name"] == hostile_name
        assert hostile_row["source"] == "NCBI Gene"
        assert hostile_row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/9"
        assert ordinary_row["name"] == "ordinary"
        assert ordinary_row["id"] == "NCBIGene:10"

    def test_list_valued_property_is_pipe_joined_on_disk(self, tmp_path: Path) -> None:
        records = [
            {"id": "NCBIGene:1", "category": "biolink:Gene", "name": "G1",
             "source": "NCBI Gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/1",
             "xrefs": ["HGNC:1", "OMIM:2"]},
        ]
        path = kgx._write_tsv(records, tmp_path / "nodes.tsv", kgx.NODE_REQUIRED_COLUMNS)
        _, rows = _read_tsv(path)
        assert rows[0]["xrefs"] == "HGNC:1|OMIM:2"


class TestResolveSourceUrl:
    def test_keeps_a_valid_host_pinned_stored_url(self) -> None:
        stored = "https://www.ncbi.nlm.nih.gov/gene/672"
        assert kgx._resolve_source_url("NCBIGene:672", stored) == stored

    def test_discards_a_stored_url_on_a_foreign_host_and_derives_instead(self) -> None:
        stored = "https://evil.example/gene/672"
        resolved = kgx._resolve_source_url("NCBIGene:672", stored)
        assert resolved == "https://www.ncbi.nlm.nih.gov/gene/672"

    def test_returns_none_for_an_unmapped_prefix_with_no_stored_url(self) -> None:
        assert kgx._resolve_source_url("GO:0008150", None) is None

    def test_returns_none_when_curie_is_empty(self) -> None:
        assert kgx._resolve_source_url("", None) is None
        assert kgx._resolve_source_url(None, None) is None

    def test_a_stored_url_with_a_second_url_appended_is_not_passed_through(self) -> None:
        # Finding F-4.4-03(b). The host pattern is anchored only at the
        # start, so a bare `re.match` accepted this whole string and wrote
        # it into the column. Verifying the value (reverse-deriving it to
        # a real CURIE) rather than its prefix rejects the tail.
        stored = "https://www.ncbi.nlm.nih.gov/gene/672 https://elsewhere.example/x"
        resolved = kgx._resolve_source_url("NCBIGene:672", stored)
        assert resolved == "https://www.ncbi.nlm.nih.gov/gene/672"
        assert "elsewhere.example" not in (resolved or "")

    def test_a_stored_url_is_re_derived_canonically_not_passed_through_verbatim(
        self,
    ) -> None:
        # F-2.1-C04's determinism guarantee: two differently-formatted
        # stored URLs for the same record must produce one citation.
        with_slash = kgx._resolve_source_url(
            "NCBIGene:672", "https://www.ncbi.nlm.nih.gov/gene/672/"
        )
        without_slash = kgx._resolve_source_url(
            "NCBIGene:672", "https://www.ncbi.nlm.nih.gov/gene/672"
        )
        assert with_slash == without_slash


class TestEdgeCitationPolicy:
    """Finding F-4.4-03, reversing F-2.1-B06, F-2.1-C04 and F-2.1-C05.

    An AGE edge carries no CURIE of its own, so its citation is always
    some other record's. The policy here is `cypher_provenance`'s, not a
    second one: the edge's own stored URL is reverse-derived first because
    that is edge-intrinsic, the endpoints are tried in order rather than
    subject-only, the canonical URL is always rebuilt from the verified
    CURIE, and the row is marked as citing an endpoint's record.
    """

    def test_the_edges_own_stored_url_wins_over_either_endpoint(self) -> None:
        url, curie = kgx._edge_citation(
            "https://pubmed.ncbi.nlm.nih.gov/1088347/",
            "NCBIGene:7157",
            "PMID:1088347",
        )
        assert curie == "PMID:1088347"
        assert url == "https://pubmed.ncbi.nlm.nih.gov/1088347/"

    def test_the_object_endpoint_is_tried_when_the_subject_cannot_be_built(self) -> None:
        # Subject-only attribution is the asymmetry F-2.1-B06 filed. `GO:`
        # has no record-page builder, so a subject-only implementation
        # returns no citation at all here and this assertion fails.
        url, curie = kgx._edge_citation("", "GO:0008150", "NCBIGene:7157")
        assert curie == "NCBIGene:7157"
        assert url == "https://www.ncbi.nlm.nih.gov/gene/7157"

    def test_the_subject_endpoint_is_preferred_over_the_object(self) -> None:
        url, curie = kgx._edge_citation("", "NCBIGene:7157", "MedGen:C0205770")
        assert curie == "NCBIGene:7157"
        assert url == "https://www.ncbi.nlm.nih.gov/gene/7157"

    def test_a_foreign_host_stored_url_falls_back_to_an_endpoint(self) -> None:
        url, curie = kgx._edge_citation(
            "https://evil.example/pubmed/1", "NCBIGene:7157", "PMID:1"
        )
        assert curie == "NCBIGene:7157"
        assert url == "https://www.ncbi.nlm.nih.gov/gene/7157"

    def test_nothing_verifiable_yields_no_citation_rather_than_a_guess(self) -> None:
        assert kgx._edge_citation("", "GO:0008150", "GO:0008151") == (None, None)

    def test_the_row_marks_the_record_its_citation_actually_points_at(self) -> None:
        edge_entity = {
            "id": 42,
            "label": "mentioned_in",
            "start_id": 1,
            "end_id": 2,
            "subject_curie": "NCBIGene:7157",
            "object_curie": "PMID:1088347",
            "properties": {
                "source": "NCBI Gene",
                "source_url": "https://www.ncbi.nlm.nih.gov/gene/7157",
            },
        }
        row, is_empty = kgx._edge_row(edge_entity)
        assert is_empty is False
        assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/7157"
        # The load-bearing part: the row says whose record that is, so the
        # citation is never read as the edge's own identity.
        assert row[kgx.EDGE_CITED_VIA_COLUMN] == "NCBIGene:7157"

    def test_an_uncitable_edge_carries_an_empty_marker_not_a_stale_one(self) -> None:
        edge_entity = {
            "id": 43,
            "label": "close_match",
            "start_id": 1,
            "end_id": 2,
            "subject_curie": "GO:0008150",
            "object_curie": "GO:0008151",
            "properties": {"source": "GO", "source_url": ""},
        }
        row, is_empty = kgx._edge_row(edge_entity)
        assert is_empty is True
        assert row["source_url"] == ""
        assert row[kgx.EDGE_CITED_VIA_COLUMN] == ""


class TestNodeAndEdgeRowShaping:
    def test_node_row_maps_label_to_biolink_category_and_carries_extras(self) -> None:
        entity = {
            "id": 12345,
            "label": "Gene",
            "properties": {
                "id": "NCBIGene:7157",
                "name": "TP53",
                "source": "NCBI Gene",
                "source_url": "https://www.ncbi.nlm.nih.gov/gene/7157",
                "xrefs": "HGNC:11998",
                "agent_type": "",
                "knowledge_level": "",
            },
        }
        row, is_empty = kgx._node_row("NCBIGene:7157", entity)
        assert row["id"] == "NCBIGene:7157"
        assert row["category"] == "biolink:Gene"
        assert row["name"] == "TP53"
        assert row["source"] == "NCBI Gene"
        assert row["source_url"] == "https://www.ncbi.nlm.nih.gov/gene/7157"
        assert row["xrefs"] == "HGNC:11998"
        assert is_empty is False

    def test_node_row_reports_empty_source_url_for_an_unmapped_prefix(self) -> None:
        entity = {
            "id": 1,
            "label": "OntologyClass",
            "properties": {"id": "GO:0008150", "name": "biological_process", "source": "GO"},
        }
        row, is_empty = kgx._node_row("GO:0008150", entity)
        assert row["source_url"] == ""
        assert is_empty is True

    def test_edge_row_maps_label_to_biolink_predicate_and_uses_attached_curies(self) -> None:
        edge_entity = {
            "id": 999,
            "label": "gene_associated_with_condition",
            "start_id": 1,
            "end_id": 2,
            "subject_curie": "NCBIGene:7157",
            "object_curie": "MedGen:C0205770",
            "properties": {
                "source": "NCBI MIM2Gene",
                "source_url": "https://www.ncbi.nlm.nih.gov/gene/7157",
                "agent_type": "manual_agent",
                "knowledge_level": "knowledge_assertion",
            },
        }
        row, is_empty = kgx._edge_row(edge_entity)
        assert row["subject"] == "NCBIGene:7157"
        assert row["predicate"] == "biolink:gene_associated_with_condition"
        assert row["object"] == "MedGen:C0205770"
        assert row["knowledge_level"] == "knowledge_assertion"
        assert row["agent_type"] == "manual_agent"
        assert is_empty is False

    def test_edge_row_with_no_stored_or_derivable_url_is_counted_empty(self) -> None:
        edge_entity = {
            "id": 1000,
            "label": "close_match",
            "start_id": 1,
            "end_id": 2,
            "subject_curie": "GO:0008150",
            "object_curie": "GO:0008151",
            "properties": {"source": "GO", "source_url": ""},
        }
        row, is_empty = kgx._edge_row(edge_entity)
        assert row["source_url"] == ""
        assert is_empty is True


class TestRowsFromTraversal:
    def test_empty_traversal_result_produces_empty_row_lists(self) -> None:
        from system_03_search_agent.export.traversal import TraversalResult

        result = TraversalResult(
            nodes={},
            edges=[],
            seeds_requested=["NCBIGene:99999999"],
            seeds_resolved=[],
            hops=1,
            max_nodes=500,
            max_edges=1000,
            time_budget_s=60.0,
            elapsed_s=0.01,
            truncated=False,
            truncation=[],
            empty_reason="0 of 1 requested seed CURIE(s) resolved",
        )
        node_rows, edge_rows, empty_count = kgx.rows_from_traversal(result)
        assert node_rows == []
        assert edge_rows == []
        assert empty_count == 0


# The three files one export bundle is made of. Restated here rather than
# imported from `kgx.BUNDLE_FILENAMES` on purpose: a test that reads the
# names from the module it is checking cannot notice that module dropping
# one of them from what it writes.
BUNDLE_FILENAMES = ("nodes.tsv", "edges.tsv", "manifest.json")

SEED_A = "NCBIGene:1"
SEED_B = "NCBIGene:2"
NEIGHBOURS_A = ("MedGen:C0000001", "MedGen:C0000002")
NEIGHBOURS_B = ("MedGen:C0000003",)


def _vertex(curie: str, label: str) -> dict[str, Any]:
    return {
        "id": len(curie),
        "label": label,
        "properties": {
            "id": curie,
            "name": curie.replace(":", "_"),
            "source": "NCBI Gene",
            "source_url": "",
        },
    }


def _edge_entity(subject_curie: str, object_curie: str) -> dict[str, Any]:
    return {
        "id": len(subject_curie) + len(object_curie),
        "label": "gene_associated_with_condition",
        "start_id": 1,
        "end_id": 2,
        "subject_curie": subject_curie,
        "object_curie": object_curie,
        "properties": {
            "source": "NCBI MIM2Gene",
            "source_url": "",
            "knowledge_level": "knowledge_assertion",
            "agent_type": "manual_agent",
        },
    }


def _traversal_result(seed: str, neighbours: tuple[str, ...]):
    """A TraversalResult a fake `traverse_subgraph` can return.

    Each run this file builds is identifiable from any one of its three
    files on its own: the seed appears in `nodes.tsv` and in the manifest's
    `seeds`, every edge's subject is that seed, and the two runs differ in
    row counts. That is what makes a mixed bundle detectable rather than
    merely suspicious.
    """
    from system_03_search_agent.export.traversal import TraversalResult

    nodes = {seed: _vertex(seed, "Gene")}
    for neighbour in neighbours:
        nodes[neighbour] = _vertex(neighbour, "Disease")

    return TraversalResult(
        nodes=nodes,
        edges=[_edge_entity(seed, neighbour) for neighbour in neighbours],
        seeds_requested=[seed],
        seeds_resolved=[seed],
        hops=1,
        max_nodes=500,
        max_edges=1000,
        time_budget_s=60.0,
        elapsed_s=0.01,
        truncated=False,
        edge_labels_requested=("gene_associated_with_condition",),
        edge_labels_traversed=("gene_associated_with_condition",),
    )


class _TraversalSpy:
    """A stand-in for `traverse_subgraph` that records every call.

    The recording is the point for the destination tests: a check that is
    supposed to run before any graph work is only proven by a traversal
    that never ran, not by an exception that happened to be raised.
    """

    def __init__(self, per_seed: dict[str, tuple[str, ...]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self._per_seed = per_seed or {
            SEED_A: NEIGHBOURS_A,
            SEED_B: NEIGHBOURS_B,
        }

    def __call__(self, **kwargs: Any):
        seeds = list(kwargs["seeds"])
        self.calls.append(seeds)
        seed = seeds[0]
        return _traversal_result(seed, self._per_seed.get(seed, ()))


def _install_traversal(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> _TraversalSpy:
    spy = _TraversalSpy(**kwargs)
    monkeypatch.setattr(kgx, "traverse_subgraph", spy)
    return spy


def _bundle_state(destination: Path) -> str:
    """What a reader looking at `destination` right now would see.

    Returns "absent", "empty", "complete", or a "partial: ..." string
    naming what it found, so a failing assertion says which files were
    visible rather than only that something was wrong.
    """
    if not destination.exists():
        return "absent"
    present = sorted(entry.name for entry in destination.iterdir())
    if not present:
        return "empty"
    if set(present) == set(BUNDLE_FILENAMES):
        return "complete"
    return "partial: " + ", ".join(present)


def _bundle_run(destination: Path) -> str:
    """The one run a complete bundle belongs to, or an assertion failure.

    Checks the three files against each other the way a downstream KGX
    consumer would: the manifest's seed must appear in `nodes.tsv`, every
    edge subject must be a node the same file holds, and the manifest's
    counts must match the rows actually on disk. A bundle assembled from
    two runs fails at least one of those, which is exactly what the
    adversary observed: four edges whose subject was absent from
    `nodes.tsv`, beside a manifest certifying the pair.
    """
    assert _bundle_state(destination) == "complete", _bundle_state(destination)

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    _, node_rows = _read_tsv(destination / "nodes.tsv")
    _, edge_rows = _read_tsv(destination / "edges.tsv")

    seeds = manifest["seeds"]
    assert len(seeds) == 1, seeds
    seed = seeds[0]
    node_ids = {row["id"] for row in node_rows}

    assert seed in node_ids, (
        "torn bundle: the manifest names seed "
        + seed
        + " and nodes.tsv holds "
        + str(sorted(node_ids))
    )
    dangling = {row["subject"] for row in edge_rows} - node_ids
    assert not dangling, (
        "torn bundle: edges.tsv references subjects absent from nodes.tsv: "
        + str(sorted(dangling))
    )
    assert manifest["counts"]["nodes"] == len(node_rows), (
        "torn bundle: the manifest certifies "
        + str(manifest["counts"]["nodes"])
        + " nodes and nodes.tsv holds "
        + str(len(node_rows))
    )
    assert manifest["counts"]["edges"] == len(edge_rows), (
        "torn bundle: the manifest certifies "
        + str(manifest["counts"]["edges"])
        + " edges and edges.tsv holds "
        + str(len(edge_rows))
    )
    return seed


def _observe(destination: Path) -> tuple[str, str | None]:
    """One reader's observation of `destination` at this instant.

    Returns the directory's state and, when it holds a complete bundle,
    which run that bundle belongs to. Taken at the moment of the call and
    kept, rather than re-derived after the run: a check written after every
    export has finished is a check of the final state three times over, not
    of what a reader could see while they were running.
    """
    state = _bundle_state(destination)
    return state, _bundle_run(destination) if state == "complete" else None


def _leftovers(parent: Path, destination: Path) -> list[str]:
    """Everything beside the destination the export should not have left."""
    return sorted(
        entry.name for entry in parent.iterdir() if entry.name != destination.name
    )


class TestDestinationDiscipline:
    """Findings F-4.4-58 and F-4.4-59.

    The destination is resolved and checked before the traversal is paid
    for, a destination that already holds something is refused rather than
    merged into, and replacing one wholesale leaves none of its previous
    contents behind.
    """

    def test_an_empty_destination_is_exported_into_without_a_force_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The premise gate passes pytest's own empty `tmp_path` straight
        # through as `output_dir`, so this is the case that must keep
        # working unchanged.
        _install_traversal(monkeypatch)
        destination = tmp_path / "bundle"
        destination.mkdir()

        result = kgx.export_subgraph(seeds=[SEED_A], output_dir=destination)

        assert _bundle_run(destination) == SEED_A
        assert result.nodes_path == destination / "nodes.tsv"
        assert result.edges_path == destination / "edges.tsv"
        assert result.manifest_path == destination / "manifest.json"

    def test_a_destination_that_does_not_exist_yet_is_created(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_traversal(monkeypatch)
        destination = tmp_path / "deep" / "not" / "there" / "yet"

        kgx.export_subgraph(seeds=[SEED_A], output_dir=destination)

        assert _bundle_run(destination) == SEED_A

    def test_a_non_empty_destination_is_refused_before_any_graph_work(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spy = _install_traversal(monkeypatch)
        destination = tmp_path / "bundle"
        destination.mkdir()
        stale = destination / "extra_from_last_run.tsv"
        stale.write_text("stale", encoding="utf-8")

        with pytest.raises(ValueError) as excinfo:
            kgx.export_subgraph(seeds=[SEED_A], output_dir=destination)

        message = str(excinfo.value)
        assert str(destination) in message
        assert "extra_from_last_run.tsv" in message
        assert "overwrite=True" in message and "--force" in message
        assert spy.calls == [], "the destination was rejected only after traversing"
        assert stale.read_text(encoding="utf-8") == "stale", "a refusal changes nothing"
        assert sorted(entry.name for entry in destination.iterdir()) == [
            "extra_from_last_run.tsv"
        ]

    def test_force_replaces_a_non_empty_destination_leaving_no_stale_sibling(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Finding F-4.4-58 exactly: a file the new run does not write must
        # not survive beside the new bundle, where a consumer reading the
        # directory as one export would count it as part of it.
        _install_traversal(monkeypatch)
        destination = tmp_path / "bundle"
        destination.mkdir()
        (destination / "extra_from_last_run.tsv").write_text("stale", encoding="utf-8")
        (destination / "nodes.tsv").write_text("stale header\n", encoding="utf-8")
        (destination / "nested").mkdir()
        (destination / "nested" / "deep.txt").write_text("stale", encoding="utf-8")

        kgx.export_subgraph(seeds=[SEED_A], output_dir=destination, overwrite=True)

        assert sorted(entry.name for entry in destination.iterdir()) == sorted(
            BUNDLE_FILENAMES
        )
        assert _bundle_run(destination) == SEED_A
        assert _leftovers(tmp_path, destination) == []

    def test_a_destination_that_is_a_file_is_refused_before_any_graph_work(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spy = _install_traversal(monkeypatch)
        destination = tmp_path / "not_a_directory"
        destination.write_text("occupied", encoding="utf-8")

        with pytest.raises(ValueError) as excinfo:
            kgx.export_subgraph(seeds=[SEED_A], output_dir=destination)

        message = str(excinfo.value)
        assert "not a directory" in message
        assert str(destination) in message, "the message must name the path it refused"
        assert spy.calls == []
        assert destination.read_text(encoding="utf-8") == "occupied"

    def test_the_filesystem_root_is_refused_before_any_graph_work(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spy = _install_traversal(monkeypatch)

        with pytest.raises(ValueError) as excinfo:
            kgx.export_subgraph(seeds=[SEED_A], output_dir=Path("/"))

        assert "filesystem root" in str(excinfo.value)
        assert spy.calls == []

    @pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="a root user is not stopped by a read-only directory",
    )
    def test_an_unwritable_parent_fails_before_any_graph_work(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Finding F-4.4-59's second half. This used to run the whole
        # traversal and discover the problem at the first write, so the
        # assertion that matters here is not the exception, it is that the
        # spy was never called.
        spy = _install_traversal(monkeypatch)
        parent = tmp_path / "read_only_parent"
        parent.mkdir()
        destination = parent / "bundle"
        os.chmod(parent, 0o500)
        try:
            with pytest.raises(OSError) as excinfo:
                kgx.export_subgraph(seeds=[SEED_A], output_dir=destination)
        finally:
            os.chmod(parent, 0o700)

        assert isinstance(excinfo.value, PermissionError)
        assert spy.calls == [], "the traversal was paid for before the write failed"
        assert not destination.exists()

    def test_the_result_reports_the_resolved_destination_not_the_path_as_typed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Finding F-4.4-59's first half: a symlinked destination wrote
        # somewhere other than the path the user typed, with nothing
        # resolved and nothing reported.
        _install_traversal(monkeypatch)
        real = tmp_path / "real_location"
        real.mkdir()
        typed = tmp_path / "looks_local"
        typed.symlink_to(real, target_is_directory=True)

        result = kgx.export_subgraph(seeds=[SEED_A], output_dir=typed)

        assert result.output_dir == real.resolve()
        assert result.output_dir != typed
        assert _bundle_run(real) == SEED_A

    def test_a_dot_dot_segment_is_collapsed_in_the_reported_destination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_traversal(monkeypatch)
        (tmp_path / "somewhere").mkdir()
        typed = tmp_path / "somewhere" / ".." / "elsewhere"

        result = kgx.export_subgraph(seeds=[SEED_A], output_dir=typed)

        assert result.output_dir == (tmp_path / "elsewhere").resolve()
        assert ".." not in str(result.output_dir)
        assert _bundle_run(tmp_path / "elsewhere") == SEED_A

    def test_a_successful_export_leaves_nothing_beside_the_destination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The bundle is assembled in a sibling directory, so this is the
        # check that the sibling never outlives the export.
        _install_traversal(monkeypatch)
        destination = tmp_path / "bundle"

        kgx.export_subgraph(seeds=[SEED_A], output_dir=destination)

        assert _leftovers(tmp_path, destination) == []

    def test_a_failed_export_leaves_nothing_beside_the_destination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def exploding_traversal(**_kwargs: Any):
            raise RuntimeError("the graph went away mid-traversal")

        monkeypatch.setattr(kgx, "traverse_subgraph", exploding_traversal)
        destination = tmp_path / "bundle"

        with pytest.raises(RuntimeError):
            kgx.export_subgraph(seeds=[SEED_A], output_dir=destination)

        assert not destination.exists(), "a failed export publishes nothing"
        assert sorted(entry.name for entry in tmp_path.iterdir()) == []

    def test_a_failed_publish_puts_the_previous_bundle_back(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The one path where the destination is briefly moved aside. If the
        # move that follows fails, what was there has to come back, or a
        # failed export would have destroyed the export it was replacing.
        _install_traversal(monkeypatch)
        destination = tmp_path / "bundle"
        destination.mkdir()
        (destination / "previous.tsv").write_text("previous bundle", encoding="utf-8")

        real_rename = os.rename
        staging_moves = {"count": 0}

        def flaky_rename(src: Any, dst: Any) -> None:
            if Path(src).name.startswith(kgx._STAGING_PREFIX):
                staging_moves["count"] += 1
                if staging_moves["count"] == 2:
                    raise OSError(errno.EACCES, "injected publish failure")
            real_rename(src, dst)

        monkeypatch.setattr(os, "rename", flaky_rename)

        with pytest.raises(OSError) as excinfo:
            kgx.export_subgraph(seeds=[SEED_A], output_dir=destination, overwrite=True)

        assert excinfo.value.errno == errno.EACCES
        assert (destination / "previous.tsv").read_text(encoding="utf-8") == (
            "previous bundle"
        )
        assert _leftovers(tmp_path, destination) == []


class TestAtomicPublish:
    """Finding F-4.4-53, the blocking one.

    Two exports into one directory used to interleave three unsynchronized
    overwrites and both return success, leaving `nodes.tsv` from one run
    beside `edges.tsv` and `manifest.json` from another, with the manifest
    certifying the pair.

    How the race is made deterministic, stated plainly rather than implied:
    nothing here schedules a real race and hopes. `kgx._write_tsv` is
    replaced with a wrapper that blocks one export on a `threading.Event`
    immediately after it has written its `nodes.tsv`, which is the exact
    point the adversary widened with an injected sleep. The window it opens
    is genuine in the shipped code, since the write path has no lock and no
    ordering of its own; the event only removes the timing luck from the
    reproduction. Everything here runs in one process, so these tests prove
    the ordering of the publish step, not the kernel's rename semantics.
    """

    def _run_interleaved(
        self, monkeypatch: pytest.MonkeyPatch, destination: Path
    ) -> list[tuple[str, str | None]]:
        """Drive the interleaving and return what a reader observed at each
        of the three checkpoints, so a caller asserts on observations
        rather than on timing.

        Every observation is taken while the schedule is still in progress
        and returned by value. A caller that re-read the directory after
        both exports had finished would be asserting on the final state
        three times, which no interleaving can fail.
        """
        _install_traversal(monkeypatch)
        real_write_tsv = kgx._write_tsv
        wrote_nodes = threading.Event()
        may_continue = threading.Event()

        def stalling_write_tsv(records: Any, path: Path, required_columns: Any) -> Path:
            written = real_write_tsv(records, path, required_columns)
            if threading.current_thread().name == "export-A" and path.name == "nodes.tsv":
                wrote_nodes.set()
                assert may_continue.wait(timeout=30), "the second export never finished"
            return written

        monkeypatch.setattr(kgx, "_write_tsv", stalling_write_tsv)

        failures: list[BaseException] = []

        def run_a() -> None:
            try:
                kgx.export_subgraph(seeds=[SEED_A], output_dir=destination)
            except BaseException as exc:  # noqa: BLE001 - re-raised in the caller
                failures.append(exc)

        thread_a = threading.Thread(target=run_a, name="export-A")
        thread_a.start()
        try:
            assert wrote_nodes.wait(timeout=30), "the first export never started writing"
            observations = [_observe(destination)]

            kgx.export_subgraph(seeds=[SEED_B], output_dir=destination)
            observations.append(_observe(destination))
        finally:
            may_continue.set()
            thread_a.join(timeout=30)

        assert not thread_a.is_alive(), "the first export never finished"
        if failures:
            raise failures[0]
        observations.append(_observe(destination))
        return observations

    def test_a_reader_never_sees_half_a_bundle_or_two_runs_mixed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        destination = tmp_path / "shared_output_dir"

        mid_write, after_second, after_first = self._run_interleaved(
            monkeypatch, destination
        )

        # Checkpoint 1: the first export has written its nodes.tsv and is
        # stalled. Before the fix this read "partial: nodes.tsv", which is
        # half a bundle, reachable.
        assert mid_write[0] in {"absent", "empty"}, (
            "a reader could see a partly written export: " + mid_write[0]
        )
        # Checkpoint 2: the second export finished while the first is still
        # stalled. What a reader saw at that moment was one complete
        # bundle, and it was the second export's, entire.
        assert after_second == ("complete", SEED_B), after_second
        # Checkpoint 3: the first export published on top. Last writer
        # wins, entire: never one run's nodes beside another run's edges.
        assert after_first == ("complete", SEED_A), after_first

    def test_neither_interleaved_export_leaves_anything_beside_the_destination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        destination = tmp_path / "shared_output_dir"

        self._run_interleaved(monkeypatch, destination)

        assert _leftovers(tmp_path, destination) == []


class TestRetiredCopyCleanup:
    """The one step that may fail without failing the export.

    Replacing an occupied destination moves its contents aside first and
    removes them once the new bundle is in place. If that removal fails,
    the export has already succeeded, so the removal warns rather than
    raising: a caller that reads a landed export as a failed one is worse
    than a caller told exactly what was left behind and where.
    """

    @pytest.mark.skipif(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        reason="a root user is not stopped by a read-only directory",
    )
    def test_an_unremovable_previous_bundle_warns_and_still_publishes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _install_traversal(monkeypatch)
        destination = tmp_path / "bundle"
        destination.mkdir()
        locked = destination / "locked"
        locked.mkdir()
        (locked / "previous.tsv").write_text("previous", encoding="utf-8")
        os.chmod(locked, 0o500)

        try:
            with pytest.warns(UserWarning, match="could not be removed"):
                kgx.export_subgraph(
                    seeds=[SEED_A], output_dir=destination, overwrite=True
                )

            assert _bundle_run(destination) == SEED_A
            leftovers = _leftovers(tmp_path, destination)
            assert len(leftovers) == 1
            assert leftovers[0].startswith(".kgx-export-replaced-")
        finally:
            for path in tmp_path.rglob("locked"):
                os.chmod(path, 0o700)
