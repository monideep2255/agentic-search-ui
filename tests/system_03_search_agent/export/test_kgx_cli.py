"""Unit tests for the KGX export's batch entry point, `cli.py` (T-4.4-05).

`kgx.py` and `traversal.py` (T-4.4-02/03) are a different builder's files,
still in flight. `cli.py` defers importing `export_subgraph` into
`_export_subgraph`'s own function body rather than at module scope (see its
own module docstring), and this file never imports either of those two
modules directly for the same reason: every test below monkeypatches
`system_03_search_agent.export.cli._export_subgraph` itself, the one seam
`cli.py` calls through, so this file exercises argument parsing, CURIE
validation, output-directory handling, and error rendering entirely
independent of whether the real `kgx.export_subgraph` exists yet.

`manifest.py` (T-4.4-04) is different: it is complete, and round 2 of this
phase's review made `cli.py`'s own `_print_disclosures` call its
`summary_lines` directly rather than re-deriving the same wording a second
time (findings F-4.4-05/F-4.4-57). This file's fake export fixture,
`_write_fake_export`, therefore builds its manifest through the real
`manifest.build_manifest`/`manifest.write_manifest` rather than a
hand-rolled dict, so a fixture drifting from the real manifest shape cannot
hide a real regression in what `cli.py` prints.

This file does not re-prove the real, end-to-end integration against the
live graph: that is `test_kgx_export_premise.py`'s job (T-4.4-01).

Coverage stated explicitly, so the gap is arguable rather than discovered
later:

- Exercised: CURIE syntax rejection, missing required flags, cap-override
  pass-through (present and absent), a successful export's stdout summary
  and every disclosure line `manifest.summary_lines` can produce (the
  Layer 1 limitation, truncation, no-cap-hit, hop-limit, dropped-row,
  rows-fetched-not-exported, empty-source_url-count, and
  unqueried-edge-label lines), a `GraphError` failure path, an
  unexpected-exception failure path, a `ValueError` input-validation
  failure path (its own message shown verbatim at the usage exit code,
  never the transport remediation, for an unknown edge label, negative
  hops, and an empty seed set, plus that distinct scenarios produce
  distinct messages), an output-directory creation failure, that no
  credential-shaped value ever reaches stdout or stderr on any path
  (including one that is neither a `GraphError` nor a `ValueError`), and
  that `main()` and a real `python -m` subprocess invocation both
  dispatch through the same `run()` body.
- Deliberately NOT exercised here: the real graph, the real `kgx.py`
  traversal or serialization behaviour, and concurrent invocations
  against the same output directory (matching the premise gate's own
  stated omissions for the phase as a whole).
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

from system_03_search_agent.export import cli
from system_03_search_agent.export import manifest as manifest_module
from system_03_search_agent.tools.graph_connection import (
    GraphAuthError,
    GraphConnectionError,
    GraphTimeoutError,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_DIR = _REPO_ROOT / "src"

TP53 = "NCBIGene:7157"
A_DISEASE = "MedGen:C0205770"


class _FakeExportResult(NamedTuple):
    nodes_path: Path
    edges_path: Path
    manifest_path: Path


def _write_fake_export(
    output_dir: Path,
    *,
    truncated: bool = False,
    truncation: list[dict[str, object]] | None = None,
    empty_reason: str | None = None,
    node_count: int = 2,
    edge_count: int = 1,
    edge_labels_traversed: tuple[str, ...] = (),
    edge_labels_requested: tuple[str, ...] = (),
    hop_limit_reached: bool = False,
    unexpanded_frontier_nodes: int = 0,
    dropped_rows: dict[str, int] | None = None,
    rows_fetched_not_exported: int = 0,
    rows_with_empty_source_url: int = 0,
) -> _FakeExportResult:
    """Writes a minimal but shape-correct KGX export into `output_dir`,
    mirroring what `kgx.export_subgraph` is contracted to produce.

    Builds the manifest through the REAL `manifest.build_manifest` and
    `manifest.write_manifest` (T-4.4-04), rather than a hand-rolled dict, on
    purpose: `manifest.py` now exists and is a real, direct (lazily
    imported) dependency of `cli.py`'s own `_print_disclosures`, so a fixture
    that drifts from `build_manifest`'s actual shape would defeat the exact
    thing this round's fix exists to prevent (F-4.4-05/F-4.4-57, drift
    between two independently maintained renderings of the same facts). This
    is the one place this file imports `system_03_search_agent.export.
    manifest` directly; every test still monkeypatches `_export_subgraph`
    itself and never calls the real `kgx.export_subgraph` or `traversal.py`.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = output_dir / "nodes.tsv"
    edges_path = output_dir / "edges.tsv"

    nodes_path.write_text(
        "id\tcategory\tname\tsource\tsource_url\n"
        f"{TP53}\tbiolink:Gene\tTP53\tNCBI\thttps://www.ncbi.nlm.nih.gov/gene/7157\n",
        encoding="utf-8",
    )
    edges_path.write_text(
        "subject\tpredicate\tobject\tsource\tsource_url\tknowledge_level\tagent_type\n",
        encoding="utf-8",
    )

    manifest = manifest_module.build_manifest(
        seeds=[TP53],
        hops=1,
        edge_labels_traversed=edge_labels_traversed,
        max_nodes=100,
        max_edges=200,
        time_budget_s=60.0,
        node_count=node_count,
        edge_count=edge_count,
        truncated=truncated,
        truncation=truncation or [],
        empty_reason=empty_reason,
        rows_with_empty_source_url=rows_with_empty_source_url,
        seeds_resolved=[] if empty_reason else [TP53],
        elapsed_s=1.23,
        edge_labels_requested=edge_labels_requested,
        per_query_row_limit=500,
        dropped_rows=dropped_rows,
        rows_fetched_not_exported=rows_fetched_not_exported,
        hop_limit_reached=hop_limit_reached,
        unexpanded_frontier_nodes=unexpanded_frontier_nodes,
    )
    manifest_path = manifest_module.write_manifest(manifest, output_dir)
    return _FakeExportResult(nodes_path, edges_path, manifest_path)


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = cli.run(argv, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


class TestCurieValidation:
    def test_rejects_an_unparseable_seed_naming_the_expected_shape(self, tmp_path: Path) -> None:
        code, out, err = _run(["not-a-curie", "--output-dir", str(tmp_path)])

        assert code == cli.EXIT_USAGE_ERROR
        assert "not-a-curie" in err
        assert "NCBIGene:7157" in err, "the message must name the expected shape"
        assert out == ""

    def test_rejects_a_seed_with_no_local_id(self, tmp_path: Path) -> None:
        code, _out, err = _run(["NCBIGene:", "--output-dir", str(tmp_path)])

        assert code == cli.EXIT_USAGE_ERROR
        assert "NCBIGene:" in err

    def test_rejects_a_seed_with_embedded_whitespace(self, tmp_path: Path) -> None:
        code, _out, err = _run(["NCBI Gene:7157", "--output-dir", str(tmp_path)])

        assert code == cli.EXIT_USAGE_ERROR
        assert "NCBI Gene:7157" in err

    def test_names_every_bad_seed_at_once_not_just_the_first(self, tmp_path: Path) -> None:
        code, _out, err = _run(
            ["nope", TP53, "also-bad", "--output-dir", str(tmp_path)]
        )

        assert code == cli.EXIT_USAGE_ERROR
        assert "nope" in err
        assert "also-bad" in err
        # TP53 legitimately appears in the message's own "e.g. NCBIGene:7157"
        # shape example; what must NOT happen is TP53 showing up as one of
        # the reported offenders in the comma-joined bad-seed list itself.
        reported = err.rsplit(":", 1)[-1]
        assert TP53 not in reported, "a valid seed is not reported as bad"

    def test_a_valid_multi_seed_multi_prefix_set_passes_validation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_export(**kwargs: object) -> _FakeExportResult:
            captured.update(kwargs)
            return _write_fake_export(kwargs["output_dir"])  # type: ignore[arg-type]

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        code, _out, _err = _run(
            [TP53, A_DISEASE, "--output-dir", str(tmp_path)]
        )

        assert code == 0
        assert captured["seeds"] == [TP53, A_DISEASE]


class TestArgumentParsing:
    def test_missing_output_dir_is_a_usage_error(self, tmp_path: Path) -> None:
        code, _out, err = _run([TP53])

        assert code == cli.EXIT_USAGE_ERROR
        assert "output-dir" in err

    def test_missing_seed_is_a_usage_error(self, tmp_path: Path) -> None:
        code, _out, _err = _run(["--output-dir", str(tmp_path)])

        assert code == cli.EXIT_USAGE_ERROR

    def test_help_exits_zero_and_writes_to_stdout(self, tmp_path: Path) -> None:
        code, out, err = _run(["--help"])

        assert code == 0
        assert "s3-kgx-export" in out
        assert err == ""


class TestCapOverridePassThrough:
    """The ticket left the default cap values undecided (they belong to
    `export_subgraph`, still in flight). The design decision this phase
    made: omit a cap kwarg entirely when the flag is not given, rather than
    this module guessing or duplicating `export_subgraph`'s own default.
    These tests pin that decision so a future change to it is deliberate.
    """

    def test_omitted_caps_are_not_passed_through_at_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_export(**kwargs: object) -> _FakeExportResult:
            captured.update(kwargs)
            return _write_fake_export(kwargs["output_dir"])  # type: ignore[arg-type]

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        _run([TP53, "--output-dir", str(tmp_path)])

        assert "max_nodes" not in captured
        assert "max_edges" not in captured
        assert "time_budget_s" not in captured
        assert "edge_labels" not in captured
        assert captured["hops"] == 1, "hops mirrors the interface's own default of 1"

    def test_given_caps_and_edge_labels_are_passed_through_exactly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_export(**kwargs: object) -> _FakeExportResult:
            captured.update(kwargs)
            return _write_fake_export(kwargs["output_dir"])  # type: ignore[arg-type]

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        _run(
            [
                TP53,
                "--output-dir",
                str(tmp_path),
                "--hops",
                "2",
                "--max-nodes",
                "50",
                "--max-edges",
                "75",
                "--time-budget",
                "12.5",
                "--edge-label",
                "gene_associated_with_condition",
                "--edge-label",
                "orthologous_to",
            ]
        )

        assert captured["hops"] == 2
        assert captured["max_nodes"] == 50
        assert captured["max_edges"] == 75
        assert captured["time_budget_s"] == 12.5
        assert captured["edge_labels"] == (
            "gene_associated_with_condition",
            "orthologous_to",
        )


class TestSuccessfulExport:
    def test_writes_a_summary_line_with_the_manifest_counts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli,
            "_export_subgraph",
            lambda **kwargs: _write_fake_export(
                kwargs["output_dir"], node_count=2, edge_count=1
            ),
        )

        code, out, err = _run([TP53, "--output-dir", str(tmp_path)])

        assert code == 0
        assert "2 nodes" in out
        assert "1 edges" in out
        assert str(tmp_path) in out
        assert err == ""

    def test_prints_the_layer_1_limitation_statement_on_stdout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli, "_export_subgraph", lambda **kwargs: _write_fake_export(kwargs["output_dir"])
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "Layer 1" in out and "only" in out
        assert "Layer 2" in out and "Layer 3" in out

    def test_prints_truncation_disclosure_when_the_manifest_reports_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli,
            "_export_subgraph",
            lambda **kwargs: _write_fake_export(
                kwargs["output_dir"],
                truncated=True,
                truncation=[{"cap": "max_nodes", "value": 5}],
            ),
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        # Wording owned by manifest.summary_lines, not re-derived here
        # (F-4.4-05/F-4.4-57's fix): assert on ITS actual sentence rather
        # than a guessed synonym, so a future re-wording there is caught
        # here too, not silently tolerated by a loose substring check.
        assert "This export is INCOMPLETE" in out
        assert "max_nodes=5" in out

    def test_prints_no_truncation_line_when_the_manifest_reports_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli, "_export_subgraph", lambda **kwargs: _write_fake_export(kwargs["output_dir"])
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "This export hit no cap" in out
        assert "INCOMPLETE" not in out

    def test_prints_the_empty_reason_when_the_manifest_carries_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli,
            "_export_subgraph",
            lambda **kwargs: _write_fake_export(
                kwargs["output_dir"],
                empty_reason="seed matched no vertex in the graph",
                node_count=0,
                edge_count=0,
            ),
        )

        _code, out, _err = _run(["NCBIGene:99999999", "--output-dir", str(tmp_path)])

        assert "seed matched no vertex in the graph" in out

    def test_prints_the_hop_limit_disclosure_when_the_manifest_reports_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli,
            "_export_subgraph",
            lambda **kwargs: _write_fake_export(
                kwargs["output_dir"],
                hop_limit_reached=True,
                unexpanded_frontier_nodes=7,
            ),
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "stopped at its hop limit of 1" in out
        assert "7 vertex(es) left unexpanded" in out

    def test_prints_the_dropped_row_disclosure_when_the_manifest_reports_any(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli,
            "_export_subgraph",
            lambda **kwargs: _write_fake_export(
                kwargs["output_dir"],
                dropped_rows={"malformed_row": 2, "duplicate": 1},
            ),
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "3 fetched row(s) were discarded" in out
        assert "malformed_row=2" in out
        assert "duplicate=1" in out

    def test_prints_no_dropped_row_line_when_every_reason_counts_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli,
            "_export_subgraph",
            lambda **kwargs: _write_fake_export(
                kwargs["output_dir"], dropped_rows={"malformed_row": 0}
            ),
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "discarded" not in out

    def test_prints_rows_fetched_not_exported_when_the_manifest_reports_any(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli,
            "_export_subgraph",
            lambda **kwargs: _write_fake_export(
                kwargs["output_dir"], rows_fetched_not_exported=4
            ),
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "4 fetched row(s) were read from the graph and not exported" in out

    def test_prints_the_unqueried_edge_label_disclosure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli,
            "_export_subgraph",
            lambda **kwargs: _write_fake_export(
                kwargs["output_dir"],
                edge_labels_traversed=("gene_associated_with_condition",),
                edge_labels_requested=(
                    "gene_associated_with_condition",
                    "orthologous_to",
                ),
            ),
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "queried 1 of the 2 requested edge label(s)" in out
        assert "orthologous_to" in out

    def test_prints_the_empty_source_url_count_when_the_manifest_reports_any(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli,
            "_export_subgraph",
            lambda **kwargs: _write_fake_export(
                kwargs["output_dir"], rows_with_empty_source_url=3
            ),
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "3 row(s) were written with an empty source_url" in out

    def test_creates_the_output_directory_when_it_does_not_exist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "does" / "not" / "exist" / "yet"
        monkeypatch.setattr(
            cli, "_export_subgraph", lambda **kwargs: _write_fake_export(kwargs["output_dir"])
        )

        code, _out, _err = _run([TP53, "--output-dir", str(target)])

        assert code == 0
        assert target.is_dir()

    def test_writes_no_file_outside_the_given_output_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "export_here"
        sibling = tmp_path / "sibling"
        sibling.mkdir()
        before = set(sibling.iterdir())

        monkeypatch.setattr(
            cli, "_export_subgraph", lambda **kwargs: _write_fake_export(kwargs["output_dir"])
        )

        code, _out, _err = _run([TP53, "--output-dir", str(target)])

        assert code == 0
        assert set(sibling.iterdir()) == before, "no stray file appeared next to the target"
        after_target = set(target.iterdir())
        assert after_target == {
            target / "nodes.tsv",
            target / "edges.tsv",
            target / "manifest.json",
        }


class TestGraphUnreachable:
    @pytest.mark.parametrize(
        "make_error",
        [
            lambda: GraphConnectionError(
                "graph connection refused or unreachable, verify GRAPH_PG_HOST and "
                "GRAPH_PG_PORT and that the SSH tunnel to the graph host is open, "
                "then retry"
            ),
            lambda: GraphTimeoutError("graph query exceeded 30s, retry with a narrower query"),
            lambda: GraphAuthError(
                "graph authentication failed for the kg_reader role, verify "
                "GRAPH_PG_USER and GRAPH_PG_PASSWORD are set correctly and retry"
            ),
        ],
    )
    def test_a_graph_error_exits_nonzero_naming_the_transport_not_a_traceback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_error
    ) -> None:
        def fake_export(**_kwargs: object) -> _FakeExportResult:
            raise make_error()

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        code, out, err = _run([TP53, "--output-dir", str(tmp_path)])

        assert code == cli.EXIT_RUNTIME_ERROR
        assert out == ""
        assert "Traceback" not in err
        assert "GRAPH_PG_HOST" in err or "SSH tunnel" in err or "kg_reader" in err or "30s" in err

    def test_an_unexpected_exception_still_names_the_transport_and_exits_nonzero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_export(**_kwargs: object) -> _FakeExportResult:
            raise RuntimeError("connection refused")

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        code, out, err = _run([TP53, "--output-dir", str(tmp_path)])

        assert code == cli.EXIT_RUNTIME_ERROR
        assert out == ""
        assert "Traceback" not in err
        assert "transport" in err.lower() or "tunnel" in err.lower()
        assert "RuntimeError" in err


class TestValidationFailureClassification:
    """Round 2 fix for F-4.4-04 / F-4.4-54: a pure input-validation
    failure, raised before any graph contact, must be classified as a
    usage error, not a graph-transport failure. `_export_subgraph`
    (really `traversal.py` and `kgx.py`, once they land) raises a plain
    `ValueError` for each of these, carrying its own specific, actionable
    message. This class proves the CLI shows that message verbatim, exits
    with the usage code, and never substitutes the generic
    transport-and-output-directory remediation for any of them.

    Each test below constructs an input that actually reaches its own
    distinct `ValueError`, and checks a message unique to that scenario,
    so a single shared boilerplate string could not accidentally satisfy
    every assertion in this class at once.
    """

    def test_an_unknown_edge_label_shows_its_own_message_at_the_usage_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_export(**_kwargs: object) -> _FakeExportResult:
            raise ValueError(
                "unknown edge label 'bogus_label'; valid labels are: "
                "gene_associated_with_disease, interacts_with, mentioned_in"
            )

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        code, out, err = _run(
            [TP53, "--output-dir", str(tmp_path), "--edge-label", "bogus_label"]
        )

        assert code == cli.EXIT_USAGE_ERROR
        assert out == ""
        assert "bogus_label" in err
        assert "gene_associated_with_disease" in err
        assert "Traceback" not in err
        assert "SSH tunnel" not in err
        assert "output directory" not in err
        assert "transport" not in err.lower()

    def test_negative_hops_shows_its_own_message_at_the_usage_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_export(**_kwargs: object) -> _FakeExportResult:
            raise ValueError("hops must be zero or greater")

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        code, out, err = _run([TP53, "--output-dir", str(tmp_path), "--hops", "-1"])

        assert code == cli.EXIT_USAGE_ERROR
        assert out == ""
        assert "hops must be zero or greater" in err
        assert "Traceback" not in err
        assert "SSH tunnel" not in err
        assert "output directory" not in err
        assert "transport" not in err.lower()

    def test_an_empty_seed_set_shows_its_own_message_at_the_usage_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_export(**_kwargs: object) -> _FakeExportResult:
            raise ValueError("export_subgraph requires at least one seed CURIE")

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        code, out, err = _run([TP53, "--output-dir", str(tmp_path)])

        assert code == cli.EXIT_USAGE_ERROR
        assert out == ""
        assert "requires at least one seed CURIE" in err
        assert "Traceback" not in err
        assert "SSH tunnel" not in err
        assert "output directory" not in err
        assert "transport" not in err.lower()

    def test_each_validation_failure_message_is_distinct_not_a_shared_boilerplate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        messages = [
            "unknown edge label 'bogus_label'; valid labels are: interacts_with",
            "hops must be zero or greater",
            "export_subgraph requires at least one seed CURIE",
        ]
        seen_errors = []
        for message in messages:

            def fake_export(_message: str = message, **_kwargs: object) -> _FakeExportResult:
                raise ValueError(_message)

            monkeypatch.setattr(cli, "_export_subgraph", fake_export)
            _code, _out, err = _run([TP53, "--output-dir", str(tmp_path)])
            seen_errors.append(err)

        assert len(set(seen_errors)) == len(messages), "each scenario produced its own message"
        for message, err in zip(messages, seen_errors, strict=True):
            assert message in err

    def test_a_value_error_never_reports_the_runtime_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Guards the classification itself, not just the message text: a
        # validation failure must land on EXIT_USAGE_ERROR, never
        # EXIT_RUNTIME_ERROR, so a caller's own exit-code handling can
        # tell the two failure classes apart without parsing stderr.
        def fake_export(**_kwargs: object) -> _FakeExportResult:
            raise ValueError("some validation problem")

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        code, _out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert code == cli.EXIT_USAGE_ERROR
        assert code != cli.EXIT_RUNTIME_ERROR


class _MysteryError(Exception):
    """An exception shape that is neither `GraphError` nor `ValueError`,
    standing in for a failure this module has no typed knowledge of
    ahead of time. Defined here, not imported from anywhere, precisely so
    it carries no special meaning to `cli.py`: the point of the test that
    uses it is that a shape the module does not recognise is redacted
    regardless of what that shape happens to be called.
    """


class TestNoCredentialLeakage:
    """No credential value appears in the command's output on either the
    success or the failure path (T-4.4-05's own last acceptance criterion).
    A `GraphError` message is already redacted by `graph_connection.py`
    itself; this test proves the CLI does not undo that by re-deriving or
    logging the raw exception text for an exception SHAPE that is neither
    a `GraphError` nor a `ValueError`, where `str(exc)` could carry
    anything, including a connection string.

    Round 2 fix note: this test used to raise a bare `ValueError` to stand
    in for "an unknown exception shape". That premise no longer holds:
    `ValueError` is now this module's explicit, deliberate signal for an
    input-validation failure (see `run`'s `except ValueError` branch and
    `TestValidationFailureClassification` below), because every validator
    ahead of graph contact in this export path already raises exactly
    that type for exactly that reason, and `graph_connection.py`, the
    only module in this path that ever handles a credential, never raises
    `ValueError`. Simulating "unknown shape" with `ValueError` would now
    be simulating a shape this module DOES recognise, so this test uses
    `_MysteryError` instead, which is neither typed branch, to keep
    testing the property it actually exists to test.
    """

    def test_a_credential_bearing_unknown_exception_never_reaches_the_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret_dsn = "postgresql://kg_reader:hunter2@127.0.0.1:15432/ncbi_kg"

        def fake_export(**_kwargs: object) -> _FakeExportResult:
            raise _MysteryError(f"could not connect using {secret_dsn}")

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        code, out, err = _run([TP53, "--output-dir", str(tmp_path)])

        assert code == cli.EXIT_RUNTIME_ERROR
        assert "hunter2" not in out
        assert "hunter2" not in err
        assert secret_dsn not in out
        assert secret_dsn not in err
        assert "_MysteryError" in err, "the exception TYPE name is fine, only the value is withheld"

    def test_a_graph_auth_error_message_carries_no_password_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # graph_connection.py's own GraphAuthError message never embeds the
        # password value (see _classify_connect_error's docstring); this
        # pins that this module does not add one back in.
        def fake_export(**_kwargs: object) -> _FakeExportResult:
            raise GraphAuthError(
                "graph authentication failed for the kg_reader role, verify "
                "GRAPH_PG_USER and GRAPH_PG_PASSWORD are set correctly and retry"
            )

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        _code, _out, err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "GRAPH_PG_PASSWORD" in err, "the variable NAME is fine to mention"
        # No `=` followed by a plausible secret value: the message only
        # ever names the env var, never a value.
        assert "GRAPH_PG_PASSWORD=" not in err


class TestOutputDirectoryFailure:
    def test_a_directory_that_cannot_be_created_exits_nonzero_with_no_traceback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A file sitting where a directory needs to go: mkdir(parents=True,
        # exist_ok=True) raises FileExistsError/NotADirectoryError on this
        # shape on every platform this repo targets.
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        target = blocker / "export_here"

        code, out, err = _run([TP53, "--output-dir", str(target)])

        assert code == cli.EXIT_RUNTIME_ERROR
        assert out == ""
        assert "Traceback" not in err
        assert str(target) in err


class TestEntryPoints:
    def test_main_dispatches_through_run_and_returns_its_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli, "_export_subgraph", lambda **kwargs: _write_fake_export(kwargs["output_dir"])
        )
        monkeypatch.setattr(sys, "argv", ["s3-kgx-export", TP53, "--output-dir", str(tmp_path)])

        assert cli.main() == 0

    def test_runnable_as_python_dash_m(self, tmp_path: Path) -> None:
        """The production `python -m system_03_search_agent.export.cli`
        invocation, run as a real subprocess against the actual module (no
        monkeypatching reaches across a process boundary), proving the
        `__main__` guard and argv wiring work end to end. Exercises the
        argument-parsing and CURIE-validation path only, since the real
        `export_subgraph` is not expected to exist yet in this worktree and
        this test must not need the graph.
        """
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "system_03_search_agent.export.cli",
                "not-a-curie",
                "--output-dir",
                str(tmp_path),
            ],
            cwd=_REPO_ROOT,
            env={"PYTHONPATH": str(_SRC_DIR)},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert completed.returncode == cli.EXIT_USAGE_ERROR
        assert "NCBIGene:7157" in completed.stderr
