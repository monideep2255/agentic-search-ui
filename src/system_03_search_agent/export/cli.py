"""The batch entry point for the KGX export, `s3-kgx-export` (T-4.4-05).

A separate console script, not a subcommand of `s3`. Build phase 4.2 scoped
the `s3` CLI as a thin HTTP client over the REST surface and explicitly not
a second path to data (`src/system_03_search_agent/adapters/cli/main.py`'s
own module docstring: "No agent logic, no grounding logic, no cost logic
lives here; that all stays server-side"). This export reads the graph
directly, so folding it into `s3` would create exactly the second path that
scoping decision ruled out. Technical_specification.md Section 25's 4.4 row
calls this "a batch job, not a live adapter", which is why this module never
touches the REST API, the agent loop, or `adapters.cli`.

This module owns argument parsing, input validation ahead of the graph call,
error rendering, and printing the manifest's Layer 1 limitation and
truncation disclosure to the user's own output, per T-4.4-04's acceptance
criterion that those statements "appear on the command's own output, not
only inside the manifest file". It performs the export itself by calling
`system_03_search_agent.export.kgx.export_subgraph`, imported lazily inside
`_export_subgraph` below rather than at module scope, so this module imports
cleanly regardless of whether that sibling module has landed yet (it is
being built concurrently, T-4.4-02 through T-4.4-04). `_export_subgraph` is
also the one seam this module's own tests patch, so those tests exercise
every other line in this file without needing the graph or the sibling
modules to exist yet (see the module docstring in
`tests/system_03_search_agent/export/test_kgx_cli.py`).

Depends on:
    - system_03_search_agent.export.kgx (T-4.4-02/03/04, imported lazily
      inside `_export_subgraph`, never at module level)
    - system_03_search_agent.tools.graph_connection (`GraphError` and its
      three subclasses, `GraphConnectionError`, `GraphTimeoutError`,
      `GraphAuthError`; this module is already built and stable, so it is
      imported directly rather than lazily. Every message these classes
      raise is already redacted of credential values by that module's own
      `_redact` function, which is what makes it safe for this module to
      print `str(exc)` for one of them without a second sanitization pass)

Reads:
    - Nothing beyond argv. This module opens no environment variable
      itself; `graph_connection.py`, reached indirectly through
      `export_subgraph`, is the only place GRAPH_PG_* is read.

Writes:
    - stdout, stderr: the export summary, the manifest's Layer 1 limitation
      and truncation disclosure, and every error message.
    - The caller-supplied output directory only, created if it does not
      already exist. This module never writes a file itself; every file in
      that directory is written by `export_subgraph`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TextIO

from system_03_search_agent.tools.graph_connection import GraphError

# A seed CURIE's syntactic shape, prefix:local_id, both halves non-empty and
# neither containing whitespace. Deliberately not restricted to the graph's
# own CURIE_PREFIXES set (graph_schema_constants.py): this is a parseability
# check ahead of the graph call, not a semantic check of whether the prefix
# is one the graph actually uses. A seed with a syntactically valid but
# unknown prefix, or one that matches no vertex, is the empty-export path
# T-4.4-02/T-4.4-04 already own (an empty subgraph with an explicit manifest
# reason), not a CLI-level rejection.
_CURIE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*:[^\s:]+$")

_CURIE_SHAPE_EXAMPLE = "NCBIGene:7157"

# The exit code for a usage-level failure: an unparseable argument or an
# unparseable seed CURIE. Matches argparse's own convention and
# `adapters/cli/main.py`'s `_ArgparseExit(2)` for the same class of failure.
EXIT_USAGE_ERROR = 2

# The exit code for a runtime failure once arguments were valid: the graph
# was unreachable, the output directory could not be created, or the export
# failed for any other reason.
EXIT_RUNTIME_ERROR = 1


class _ArgparseExit(Exception):
    """Raised by `_KgxArgumentParser` in place of `sys.exit`, so a parse
    failure or `--help` is testable through the injected stream seam every
    other path in this module uses, rather than killing the whole test
    process. The same pattern `adapters/cli/main.py`'s `_ArgparseExit` uses,
    reimplemented here rather than imported: that class is private to its
    own module and this module does not reach into `adapters.cli` at all,
    per this phase's own scoping decision.
    """

    def __init__(self, code: int) -> None:
        super().__init__(f"argument parsing exited with code {code}")
        self.code = code


class _KgxArgumentParser(argparse.ArgumentParser):
    """An `ArgumentParser` that raises `_ArgparseExit` instead of calling
    `sys.exit`, and writes usage, help, and error text to the injected
    streams instead of the real `sys.stdout`/`sys.stderr`.
    """

    def __init__(self, *args: object, out: TextIO, err: TextIO, **kwargs: object) -> None:
        self._out = out
        self._err = err
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]

    def print_usage(self, file: TextIO | None = None) -> None:
        super().print_usage(self._err)

    def print_help(self, file: TextIO | None = None) -> None:
        super().print_help(self._out)

    def error(self, message: str) -> None:
        self.print_usage()
        self._err.write(f"{self.prog}: error: {message}\n")
        raise _ArgparseExit(EXIT_USAGE_ERROR)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            self._err.write(message)
        raise _ArgparseExit(status)


def _parse_args(argv: list[str], *, out: TextIO, err: TextIO) -> argparse.Namespace:
    """Parses argv for the export. Every cap flag defaults to None and is
    omitted from the call to `export_subgraph` when not given, rather than
    this module guessing or duplicating whatever default `export_subgraph`
    itself uses (a design decision the ticket left open; see this phase's
    build report). `--hops` is the one exception: the interface this module
    codes against already states `hops: int = 1` as its own default, so
    mirroring that default here rather than treating it as unset is not a
    guess.
    """
    parser = _KgxArgumentParser(
        prog="s3-kgx-export",
        out=out,
        err=err,
        description=(
            "Export a query-scoped subgraph from the Layer 1 knowledge graph as "
            "KGX (nodes.tsv, edges.tsv, manifest.json). A batch job over the "
            "graph, not a live adapter: it never calls the REST API or the "
            "agent loop."
        ),
    )
    parser.add_argument(
        "seed",
        nargs="+",
        metavar="SEED",
        help=f"one or more seed CURIEs to export the neighbourhood of, e.g. {_CURIE_SHAPE_EXAMPLE}",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        metavar="DIR",
        help="the directory to write nodes.tsv, edges.tsv, and manifest.json into",
    )
    parser.add_argument(
        "--hops",
        type=int,
        default=1,
        metavar="N",
        help="how many hops to traverse from the seed set (default: 1)",
    )
    parser.add_argument(
        "--edge-label",
        action="append",
        default=None,
        dest="edge_label",
        metavar="LABEL",
        help=(
            "restrict traversal to this edge label; may be repeated. Every label "
            "the exporter itself uses is traversed when this is omitted"
        ),
    )
    parser.add_argument(
        "--max-nodes",
        type=int,
        default=None,
        dest="max_nodes",
        metavar="N",
        help="override the exporter's own node cap",
    )
    parser.add_argument(
        "--max-edges",
        type=int,
        default=None,
        dest="max_edges",
        metavar="N",
        help="override the exporter's own edge cap",
    )
    parser.add_argument(
        "--time-budget",
        type=float,
        default=None,
        dest="time_budget",
        metavar="SECONDS",
        help="override the exporter's own wall-clock traversal budget",
    )
    return parser.parse_args(list(argv))


def _invalid_seeds(seeds: list[str]) -> list[str]:
    """Returns every seed in `seeds` that does not match the CURIE shape
    `prefix:local_id`, preserving input order, so the rejection message
    below can name every offender at once rather than stopping at the
    first.
    """
    return [seed for seed in seeds if not _CURIE_PATTERN.match(seed)]


def _export_subgraph(**kwargs: object):
    """Lazily imports and calls `export_subgraph`. The one seam this
    module's own tests patch (`system_03_search_agent.export.cli.
    _export_subgraph`), which is what lets those tests run without the
    graph and without importing `system_03_search_agent.export.kgx`
    directly, per this ticket's own instruction. The lazy import means this
    module's real, non-test call path also works the instant the sibling
    module lands, with no further change here.
    """
    from system_03_search_agent.export.kgx import export_subgraph

    return export_subgraph(**kwargs)


def _print_disclosures(manifest: dict, *, stdout: TextIO) -> None:
    """Prints the manifest's Layer 1 limitation statement and any
    truncation or empty-export disclosure to the user's own output.
    T-4.4-04's acceptance criterion is that these statements "appear on the
    command's own output, not only inside the manifest file"; this function
    is where that happens. Every value printed here is read back out of the
    manifest this same run just wrote, never freshly derived, so the
    command's own output and the manifest file can never disagree about
    what happened in this run.
    """
    layer_note = manifest.get("layer_note")
    if layer_note:
        stdout.write(f"{layer_note}\n")

    if manifest.get("truncated"):
        for entry in manifest.get("truncation") or []:
            cap = entry.get("cap", "an unnamed cap")
            value = entry.get("value")
            stdout.write(
                f"truncated: hit the {cap} cap at {value}; the export is incomplete\n"
            )

    empty_reason = manifest.get("empty_reason")
    if empty_reason:
        stdout.write(f"empty export: {empty_reason}\n")


def run(argv: list[str], *, stdout: TextIO, stderr: TextIO) -> int:
    """The real command body, driven by both `main()` below and this
    module's own tests. Never raises for an ordinary failure; every
    expected failure shape returns a nonzero exit code after writing an
    actionable message to `stderr`.
    """
    try:
        args = _parse_args(argv, out=stdout, err=stderr)
    except _ArgparseExit as exc:
        return exc.code

    bad_seeds = _invalid_seeds(args.seed)
    if bad_seeds:
        joined = ", ".join(bad_seeds)
        stderr.write(
            f"s3-kgx-export: not a CURIE (expected prefix:local_id, e.g. "
            f"{_CURIE_SHAPE_EXAMPLE}): {joined}\n"
        )
        return EXIT_USAGE_ERROR

    output_dir = Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        stderr.write(
            f"s3-kgx-export: could not create the output directory "
            f"{output_dir} ({type(exc).__name__}); check the path and its "
            "permissions and retry\n"
        )
        return EXIT_RUNTIME_ERROR

    call_kwargs: dict[str, object] = {
        "seeds": list(args.seed),
        "output_dir": output_dir,
        "hops": args.hops,
    }
    if args.edge_label:
        call_kwargs["edge_labels"] = tuple(args.edge_label)
    if args.max_nodes is not None:
        call_kwargs["max_nodes"] = args.max_nodes
    if args.max_edges is not None:
        call_kwargs["max_edges"] = args.max_edges
    if args.time_budget is not None:
        call_kwargs["time_budget_s"] = args.time_budget

    try:
        result = _export_subgraph(**call_kwargs)
    except GraphError as exc:
        # Every GraphError message is already redacted of credential
        # values by graph_connection.py's own `_redact` (see this module's
        # docstring), and each of the three subclasses already names the
        # transport in its own curated message (host, port, the SSH
        # tunnel, or the kg_reader role), so `str(exc)` is safe and
        # actionable to print here without a second sanitization pass.
        stderr.write(f"s3-kgx-export: {exc}\n")
        return EXIT_RUNTIME_ERROR
    except Exception as exc:  # noqa: BLE001 - the export's own failure shape is not
        # fully known to this module: `traversal.py` and `kgx.py` are
        # concurrent, in-progress work (T-4.4-02/03), and this module must
        # not import them to find out. `type(exc).__name__` only, never
        # `str(exc)`: an exception from a code path this module cannot
        # inspect ahead of time is exactly the shape that could carry a
        # connection string or another credential-bearing value, the same
        # reasoning `adapters/cli/main.py`'s own last-resort catch-all
        # applies. The message still names the transport explicitly, since
        # a graph-unreachable failure that for any reason is not raised as
        # a GraphError must still meet this ticket's "names the transport"
        # requirement.
        stderr.write(
            f"s3-kgx-export: the export failed ({type(exc).__name__}); check "
            "that the output directory is writable and that the graph "
            "transport (the SSH tunnel to the Hetzner graph host) is "
            "reachable, then retry\n"
        )
        return EXIT_RUNTIME_ERROR

    try:
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        stderr.write(
            f"s3-kgx-export: the export ran but its manifest could not be read "
            f"({type(exc).__name__}); the export may be incomplete\n"
        )
        return EXIT_RUNTIME_ERROR

    counts = manifest.get("counts") or {}
    stdout.write(
        f"wrote {counts.get('nodes', 0)} nodes and {counts.get('edges', 0)} edges "
        f"to {output_dir}\n"
    )
    _print_disclosures(manifest, stdout=stdout)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Production entry point: real `sys.argv[1:]` (or an explicit
    override) and real stdio. Registered as the `s3-kgx-export` console
    script in `pyproject.toml`, and also reachable as
    `python -m system_03_search_agent.export.cli` via the `__main__` guard
    below, per this ticket's own requirement that both invocations work and
    neither routes through the REST API or the agent loop.
    """
    real_argv = list(sys.argv[1:] if argv is None else argv)
    return run(real_argv, stdout=sys.stdout, stderr=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
