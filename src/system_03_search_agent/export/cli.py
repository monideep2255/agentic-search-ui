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
`tests/system_03_search_agent/export/test_kgx_cli.py`). The disclosure text
itself is not derived here: `_print_disclosures` calls
`system_03_search_agent.export.manifest.summary_lines`, also imported
lazily, rather than re-deriving the same wording a second time (findings
F-4.4-05 and F-4.4-57, fixed in build phase 4.4's round 2).

Depends on:
    - system_03_search_agent.export.kgx (T-4.4-02/03/04, imported lazily
      inside `_export_subgraph`, never at module level)
    - system_03_search_agent.export.manifest (`summary_lines`, T-4.4-04,
      imported lazily inside `_print_disclosures`, never at module level,
      for the same reason as `export.kgx` above)
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
    - The caller-supplied output directory, created if it does not already
      exist. This module never writes a file itself; every file in that
      directory is written by `export_subgraph`, which also creates and
      removes one temporary directory beside it while the export runs (see
      that module's own Writes section). The summary line reports the
      directory the export says it landed in, not the string that was
      typed, so a symlinked or `..`-bearing argument does not hide where
      the files went (finding F-4.4-59).
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
        "--force",
        action="store_true",
        dest="force",
        help=(
            "replace a non-empty output directory. Without this an export "
            "into a directory that already holds anything is refused before "
            "any graph work, because an export replaces its destination "
            "wholesale rather than merging into it; with it, every file "
            "already in that directory is gone once the new export lands"
        ),
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
    """Prints the manifest's Layer 1 limitation statement and every
    truncation, hop-limit, dropped-row, and empty-export disclosure to the
    user's own output. T-4.4-04's acceptance criterion is that these
    statements "appear on the command's own output, not only inside the
    manifest file"; this function is where that happens.

    Delegates the actual wording to `manifest.summary_lines`, imported
    lazily for the same reason `_export_subgraph` imports `kgx` lazily:
    this module must import cleanly even while `manifest.py` is mid-edit.
    This function used to re-derive the same statements itself, which is
    exactly the drift `summary_lines`'s own docstring says it exists to
    prevent (findings F-4.4-05 and F-4.4-57): two independently written
    renderings of "what happened in this export" is two places for the
    wording, and eventually the facts, to disagree. Calling the shared
    function instead means the command's own output and the manifest file
    are reading the same sentence, not two sentences about the same
    numbers.
    """
    from system_03_search_agent.export.manifest import summary_lines

    for line in summary_lines(manifest):
        if line:
            stdout.write(f"{line}\n")


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
        # Always passed, unlike the cap flags below, which are omitted when
        # unset because this module does not know `export_subgraph`'s own
        # defaults for them. This one it does know: the flag's default IS
        # the decision, that a non-empty destination is refused unless the
        # user asked for it to be replaced (finding F-4.4-58).
        "overwrite": bool(args.force),
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
    except ValueError as exc:
        # `ValueError` is this module's explicit signal for "a problem with
        # what was typed, not with reaching the graph". Every validator
        # that runs ahead of graph contact in this export path
        # (`traversal.py`'s edge-label check, its hops check, `kgx.py`'s
        # empty-seed check) raises exactly this type, and each one already
        # builds its own specific, actionable message naming what was
        # wrong and what the valid options are. `str(exc)` is that
        # message; print it as is rather than discarding it in favour of a
        # generic one.
        #
        # This is classification by the actual nature of the failure, not
        # by which line of code happened to catch it, which is the same
        # shape of defect that shipped two criticals in build phase 4.3
        # when an exception's safety was inferred from a proxy (the
        # package or class family it came from) instead of an explicit
        # signal. `ValueError` is the explicit signal here, not a proxy:
        # it is the one exception type this export path's input
        # validation deliberately and consistently raises, matching the
        # same convention `adapters/cli/main.py` already uses for its own
        # argument-conversion failures. `graph_connection.py`, the only
        # module in this export path that ever handles a credential,
        # never raises `ValueError` for any failure of its own; every
        # credential-adjacent failure it raises is a `GraphError`
        # subclass, caught above. A validation check added to
        # `traversal.py` or `kgx.py` next year is classified correctly
        # here with no change to this module, as long as it keeps to that
        # same, already-established convention of raising `ValueError`
        # for a bad argument value.
        #
        # A usage-level exit code, matching `_ArgparseExit`'s own
        # `EXIT_USAGE_ERROR` for an unparseable argument or seed: this is
        # the same class of failure, caught one call later.
        stderr.write(f"s3-kgx-export: {exc}\n")
        return EXIT_USAGE_ERROR
    except Exception as exc:  # noqa: BLE001 - the export's own failure shape is not
        # fully known to this module beyond the two typed signals above:
        # `traversal.py` and `kgx.py` are concurrent, in-progress work
        # (T-4.4-02/03), and this module must not import them to find out.
        # `type(exc).__name__` only, never `str(exc)`: an exception from a
        # code path this module cannot inspect ahead of time, and that is
        # neither a `GraphError` nor a `ValueError`, is exactly the shape
        # that could carry a connection string or another
        # credential-bearing value, the same reasoning `adapters/cli/main.
        # py`'s own last-resort catch-all applies. The message still names
        # the transport explicitly, since a graph-unreachable failure that
        # for any reason is not raised as a GraphError must still meet
        # this ticket's "names the transport" requirement.
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
    # `result.output_dir`, never the `--output-dir` string as typed. The
    # export resolves its destination, so a symlink or a `..` segment means
    # the files landed somewhere other than what was typed, and a caller
    # told the typed path cannot go and check them (finding F-4.4-59).
    stdout.write(
        f"wrote {counts.get('nodes', 0)} nodes and {counts.get('edges', 0)} edges "
        f"to {result.output_dir}\n"
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
