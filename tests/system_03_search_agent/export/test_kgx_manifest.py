"""Unit tests for manifest.py (T-4.4-04).

Covers the manifest's shape and content directly, without needing the
live graph: the graph_snapshot_version fallback, the required keys the
premise gate reads, the truncation and empty_reason wiring, and the
summary text a caller can print alongside the manifest file.
"""

from __future__ import annotations

import json
from pathlib import Path

from system_03_search_agent.export import manifest as manifest_module


class TestGraphSnapshotVersion:
    def test_falls_back_to_the_default_when_env_var_unset(self, monkeypatch) -> None:
        monkeypatch.delenv("GRAPH_SNAPSHOT_VERSION", raising=False)
        assert manifest_module.graph_snapshot_version() == "ncbi_kg_v1_2026-04-22"

    def test_reads_the_env_var_when_set(self, monkeypatch) -> None:
        monkeypatch.setenv("GRAPH_SNAPSHOT_VERSION", "ncbi_kg_v2_2026-09-01")
        assert manifest_module.graph_snapshot_version() == "ncbi_kg_v2_2026-09-01"

    def test_truncates_to_forty_characters(self, monkeypatch) -> None:
        long_value = "x" * 100
        monkeypatch.setenv("GRAPH_SNAPSHOT_VERSION", long_value)
        assert len(manifest_module.graph_snapshot_version()) == 40

    def test_falls_back_when_env_var_is_set_but_empty(self, monkeypatch) -> None:
        monkeypatch.setenv("GRAPH_SNAPSHOT_VERSION", "")
        assert manifest_module.graph_snapshot_version() == "ncbi_kg_v1_2026-04-22"


def _build_sample_manifest(**overrides):
    base = {
        "seeds": ["NCBIGene:7157"],
        "hops": 1,
        "edge_labels_used": ("gene_associated_with_condition",),
        "max_nodes": 500,
        "max_edges": 1000,
        "time_budget_s": 60.0,
        "node_count": 13,
        "edge_count": 12,
        "truncated": False,
        "truncation": [],
        "empty_reason": None,
        "rows_with_empty_source_url": 0,
        "seeds_resolved": ["NCBIGene:7157"],
        "elapsed_s": 2.3,
    }
    base.update(overrides)
    return manifest_module.build_manifest(**base)


class TestBuildManifest:
    def test_carries_every_key_the_premise_gate_reads(self) -> None:
        manifest = _build_sample_manifest()
        for key in (
            "truncated",
            "truncation",
            "empty_reason",
            "layers",
            "layer_note",
            "seeds",
            "hops",
            "counts",
            "graph_snapshot_version",
            "exported_at",
        ):
            assert key in manifest
        assert manifest["counts"]["nodes"] == 13
        assert manifest["counts"]["edges"] == 12

    def test_layers_is_exactly_layer_1(self) -> None:
        manifest = _build_sample_manifest()
        assert manifest["layers"] == ["layer_1"]

    def test_layer_note_names_layer_2_and_layer_3(self) -> None:
        manifest = _build_sample_manifest()
        note = manifest["layer_note"].lower()
        assert "layer 2" in note
        assert "layer 3" in note

    def test_seeds_echoed_exactly_as_given_including_order(self) -> None:
        manifest = _build_sample_manifest(seeds=["b:2", "a:1"])
        assert manifest["seeds"] == ["b:2", "a:1"]

    def test_truncation_entries_pass_through_unchanged(self) -> None:
        truncation = [{"cap": "max_nodes", "value": 5}]
        manifest = _build_sample_manifest(truncated=True, truncation=truncation)
        assert manifest["truncated"] is True
        assert manifest["truncation"] == truncation

    def test_empty_reason_none_when_not_empty(self) -> None:
        manifest = _build_sample_manifest()
        assert manifest["empty_reason"] is None

    def test_rows_with_empty_source_url_present(self) -> None:
        manifest = _build_sample_manifest(rows_with_empty_source_url=3)
        assert manifest["rows_with_empty_source_url"] == 3

    def test_exported_at_is_a_non_empty_iso_looking_string(self) -> None:
        manifest = _build_sample_manifest()
        assert manifest["exported_at"]
        assert "T" in manifest["exported_at"]

    def test_result_is_json_serializable(self) -> None:
        manifest = _build_sample_manifest(truncated=True, truncation=[{"cap": "max_edges", "value": 1000}])
        # json.dumps must not raise: every value in the manifest is a
        # plain JSON-representable type.
        encoded = json.dumps(manifest)
        assert "max_edges" in encoded


class TestWriteManifest:
    def test_writes_inside_the_given_output_directory_only(self, tmp_path: Path) -> None:
        manifest = _build_sample_manifest()
        path = manifest_module.write_manifest(manifest, tmp_path)
        assert path == tmp_path / "manifest.json"
        assert path.exists()
        assert path.parent == tmp_path

    def test_written_file_round_trips_through_json_loads(self, tmp_path: Path) -> None:
        manifest = _build_sample_manifest(truncated=True, truncation=[{"cap": "max_nodes", "value": 5}])
        path = manifest_module.write_manifest(manifest, tmp_path)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["truncated"] is True
        assert loaded["truncation"] == [{"cap": "max_nodes", "value": 5}]
        assert loaded["seeds"] == manifest["seeds"]

    def test_never_writes_a_credential_value_into_the_file(self, tmp_path: Path, monkeypatch) -> None:
        # Belt-and-suspenders: nothing in build_manifest's inputs is a
        # credential, but this asserts the invariant directly rather than
        # trusting it by construction, matching how graph_connection.py's
        # own _redact helper is tested elsewhere in this codebase.
        monkeypatch.setenv("GRAPH_PG_PASSWORD", "super-secret-value")
        manifest = _build_sample_manifest()
        path = manifest_module.write_manifest(manifest, tmp_path)
        contents = path.read_text(encoding="utf-8")
        assert "super-secret-value" not in contents


class TestSummaryLines:
    def test_includes_the_layer_note(self) -> None:
        manifest = _build_sample_manifest()
        lines = manifest_module.summary_lines(manifest)
        assert manifest["layer_note"] in lines

    def test_states_no_cap_hit_when_not_truncated(self) -> None:
        manifest = _build_sample_manifest(truncated=False, truncation=[])
        lines = manifest_module.summary_lines(manifest)
        assert any("hit no cap" in line for line in lines)

    def test_states_which_caps_were_hit_when_truncated(self) -> None:
        manifest = _build_sample_manifest(
            truncated=True, truncation=[{"cap": "max_nodes", "value": 5}]
        )
        lines = manifest_module.summary_lines(manifest)
        assert any("INCOMPLETE" in line and "max_nodes=5" in line for line in lines)

    def test_includes_empty_reason_when_present(self) -> None:
        manifest = _build_sample_manifest(empty_reason="no seed resolved: NCBIGene:99999999")
        lines = manifest_module.summary_lines(manifest)
        assert any("no seed resolved" in line for line in lines)

    def test_includes_empty_source_url_count_when_nonzero(self) -> None:
        manifest = _build_sample_manifest(rows_with_empty_source_url=4)
        lines = manifest_module.summary_lines(manifest)
        assert any("4 row(s)" in line for line in lines)

    def test_omits_empty_source_url_line_when_zero(self) -> None:
        manifest = _build_sample_manifest(rows_with_empty_source_url=0)
        lines = manifest_module.summary_lines(manifest)
        assert not any("row(s) were written" in line for line in lines)
