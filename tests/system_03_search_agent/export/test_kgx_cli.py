"""Unit tests for the KGX export's batch entry point, `cli.py` (T-4.4-05).

The other two builders' modules this phase depends on (`kgx.py`,
`traversal.py`, `manifest.py`; T-4.4-02/03/04) are being built concurrently
and may not exist in this worktree yet. `cli.py` defers importing
`export_subgraph` into `_export_subgraph`'s own function body rather than at
module scope (see its own module docstring), and this file never imports
`system_03_search_agent.export.kgx` directly for the same reason: every test
below monkeypatches `system_03_search_agent.export.cli._export_subgraph`
itself, the one seam `cli.py` calls through, so this file exercises argument
parsing, CURIE validation, output-directory handling, error rendering, and
the manifest disclosure printing entirely independent of whether the real
`kgx.export_subgraph` exists yet.

This file does not re-prove the real, end-to-end integration against the
live graph: that is `test_kgx_export_premise.py`'s job (T-4.4-01).

Coverage stated explicitly, so the gap is arguable rather than discovered
later:

- Exercised: CURIE syntax rejection, missing required flags, cap-override
  pass-through (present and absent), a successful export's stdout summary
  and manifest disclosure printing (limitation note, truncation, and empty
  reason), a `GraphError` failure path, an unexpected-exception failure
  path, an output-directory creation failure, that no credential-shaped
  value ever reaches stdout or stderr on any path, and that `main()` and a
  real `python -m` subprocess invocation both dispatch through the same
  `run()` body.
- Deliberately NOT exercised here: the real graph, the real `kgx.py`
  traversal or serialization behaviour, and concurrent invocations against
  the same output directory (matching the premise gate's own stated
  omissions for the phase as a whole).
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

from system_03_search_agent.export import cli
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
) -> _FakeExportResult:
    """Writes a minimal but shape-correct KGX export into `output_dir`,
    mirroring what `kgx.export_subgraph` is contracted to produce (T-4.4-03/
    04's manifest keys: `truncated`, `truncation`, `empty_reason`, `layers`,
    `layer_note`, `counts`). Used as the return value of a fake
    `_export_subgraph`, never called directly by `cli.py`.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes_path = output_dir / "nodes.tsv"
    edges_path = output_dir / "edges.tsv"
    manifest_path = output_dir / "manifest.json"

    nodes_path.write_text(
        "id\tcategory\tname\tsource\tsource_url\n"
        f"{TP53}\tbiolink:Gene\tTP53\tNCBI\thttps://www.ncbi.nlm.nih.gov/gene/7157\n",
        encoding="utf-8",
    )
    edges_path.write_text(
        "subject\tpredicate\tobject\tsource\tsource_url\tknowledge_level\tagent_type\n",
        encoding="utf-8",
    )
    manifest = {
        "seeds": [TP53],
        "hops": 1,
        "truncated": truncated,
        "truncation": truncation or [],
        "empty_reason": empty_reason,
        "layers": ["layer_1"],
        "layer_note": (
            "This export covers Layer 1 only. Layer 2 and Layer 3 data are "
            "fetched live at query time and are not present here."
        ),
        "counts": {"nodes": node_count, "edges": edge_count},
        "graph_snapshot_version": "2026-07-29",
        "exported_at": "2026-08-19T00:00:00Z",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
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

        assert "Layer 1 only" in out
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

        assert "truncated" in out.lower()
        assert "max_nodes" in out
        assert "5" in out

    def test_prints_no_truncation_line_when_the_manifest_reports_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            cli, "_export_subgraph", lambda **kwargs: _write_fake_export(kwargs["output_dir"])
        )

        _code, out, _err = _run([TP53, "--output-dir", str(tmp_path)])

        assert "truncated" not in out.lower()

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


class TestNoCredentialLeakage:
    """No credential value appears in the command's output on either the
    success or the failure path (T-4.4-05's own last acceptance criterion).
    A `GraphError` message is already redacted by `graph_connection.py`
    itself; this test proves the CLI does not undo that by re-deriving or
    logging the raw exception text for an exception SHAPE that is not a
    `GraphError`, where `str(exc)` could carry anything, including a
    connection string.
    """

    def test_a_credential_bearing_generic_exception_never_reaches_the_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret_dsn = "postgresql://kg_reader:hunter2@127.0.0.1:15432/ncbi_kg"

        def fake_export(**_kwargs: object) -> _FakeExportResult:
            raise ValueError(f"could not connect using {secret_dsn}")

        monkeypatch.setattr(cli, "_export_subgraph", fake_export)

        code, out, err = _run([TP53, "--output-dir", str(tmp_path)])

        assert code == cli.EXIT_RUNTIME_ERROR
        assert "hunter2" not in out
        assert "hunter2" not in err
        assert secret_dsn not in out
        assert secret_dsn not in err
        assert "ValueError" in err, "the exception TYPE name is fine, only the value is withheld"

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
