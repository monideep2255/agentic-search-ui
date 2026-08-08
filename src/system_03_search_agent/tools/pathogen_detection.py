"""pathogen_detection: bulk Salmonella isolate/cluster/AMR access over the
NCBI Pathogen Detection PDG snapshot tree (T-3.5-05).

READ THIS FIRST: the prerequisite artifacts this build task described as
already in place do not exist anywhere in this worktree. There is no
`tracker/phase_3.5.md` (no phase premise, no pre-build live probes beyond
what the dispatching task quoted inline as F-3.5-01/F-3.5-03), and, most
importantly for THIS module specifically, no
`pathogen_ftp_transport.py` at all: the module this tool is supposed to
`import` and consume. `git log` on this worktree's branch
(`phase/3.5-pathogen-clinicaltrials-tools`) shows zero commits beyond
`main`'s tip; the transport module, the tracker file, and the premise gate
test were never committed here. This module is therefore written directly
against the EXACT function signatures the dispatching task quoted
verbatim (`resolve_complete_snapshot(taxon, *, client,
base_url=PATHOGEN_FTP_BASE) -> str`, `stream_filtered_tsv_rows(url, *,
key_column, key_values, deadline, client, max_matches=None) ->
TsvScanResult`, `PathogenSnapshotUnavailableError`,
`PathogenDeadlineExceededError`, `DEFAULT_TIMEOUT_S = 60.0`), not against
a file this worktree could actually read. Every choice beyond that literal
contract is a documented, flagged assumption, listed below, made necessary
by the missing module rather than a live-verified fact. This is the
opposite of `.claude/rules/attack-the-constraint.md`'s "read the input
first" discipline by necessity: the input (the real transport module) does
not exist to read. The dispatching task's own instructions anticipate
exactly this kind of gap for the premise gate file ("if it is genuinely
wrong, stop and report the exact discrepancy instead of weakening the
check") and this module extends the same discipline to its own upstream
dependency: it does not fabricate `pathogen_ftp_transport.py` (explicitly
out of this ticket's file ownership and explicitly described as
pre-built), and it does not pretend the gaps below are verified when they
are not.

Flagged assumptions, for the phase lead to confirm or correct once the
real `pathogen_ftp_transport.py` lands:

1. ASYNC, not sync. The task's quoted signatures carry no explicit `async`
   marker, but every other Layer 2 tool in this repo
   (`ncbi_transport.execute_get`, every action module under
   `system_03_search_agent/tools/ncbi_*_actions.py`) uses
   `httpx.AsyncClient`, opened fresh per call with `async with` rather
   than a module-level singleton (`ncbi_transport.py`'s own "Client
   lifetime, not a singleton" comment: a shared client can outlive, and be
   reused from a different event loop than, the one it was created on).
   This module follows that house convention: both
   `pathogen_ftp_transport` functions are called with `await`, and the
   `client` argument is a fresh `httpx.AsyncClient()` opened once per
   `pathogen_detection` call and reused across every FTP read that one
   call makes (never a caller-crossing singleton). If the real module
   turns out to be synchronous, every `await` here becomes a no-op
   removal, a small, mechanical diff.

2. `deadline` is a `time.monotonic()`-comparable float. The dispatching
   task's own wording ("a shared wall-clock deadline (`time.monotonic() +
   budget`)") states this directly, so this is the least speculative
   assumption in this module.

3. The TSV column names used as `key_column` values and as dict keys on
   the rows `stream_filtered_tsv_rows` returns. Three of these are
   directly stated, not guessed: `biosample_acc` (Section 6.6's own
   Metadata source-file table row), and `PDS_acc` as the SNP_distances.tsv
   filter column (the dispatching task's F-3.5-01 summary states this
   verbatim: "filtering rows by `PDS_acc`"). The rest, most importantly
   the cluster_list.tsv cluster-id column name and the SNP_distances.tsv
   pairwise-partner and numeric-distance column names, are NOT stated
   anywhere this module could read, since the pre-build live probes that
   would normally have pinned them (`tracker/phase_3.5.md`) do not exist
   in this worktree. `_first_present` below tries a short list of
   plausible candidate names per field, chosen from Section 6.6's own
   prose and this repo's naming conventions elsewhere, and quietly moves
   on (never fabricates a value) when none of the candidates are present
   on a row. This is the single largest unverified surface in this
   module; see `_index_snp_distances`'s own docstring for exactly what it
   does and does not guarantee. It cannot be closed without either the
   real live probes or the real transport module's own live-fetched TSV
   header, neither of which exists in this worktree.

4. The per-invocation wall-clock budget, `_TOTAL_BUDGET_S`. `
   .claude/rules/tool-call-budgets.md` locks the FLOOR ("60 seconds or
   more") but not an exact figure for a whole invocation that, per the
   dispatching task's own F-3.5-01 instruction, shares ONE deadline across
   up to three sequential FTP reads (snapshot resolution, cluster_list,
   SNP_distances, sometimes also a Metadata read keyed on multiple
   accessions). 120 seconds, twice the documented floor, is this module's
   own chosen value, asserted against the floor at import time
   (`assert _TOTAL_BUDGET_S >= pathogen_ftp_transport.DEFAULT_TIMEOUT_S`)
   so a future change to the floor cannot silently put this module out of
   compliance with its own governing rule.

5. RESOLVED by the lead after this module's first draft, live-verified
   2026-08-08 (F-3.5-04, `tracker/phase_3.5.md`): `source_url` for an
   isolate is `https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/
   biosample_acc:{biosample_acc}`, confirmed reachable (HTTP 200) and
   satisfies the locked Section 6.6 host-and-path pattern. It is a
   CLIENT-RENDERED single-page app, the same architecture LitVar2's own
   citation UI was found to be (`tracker/phase_3.3.md`'s F-3.3-A-09): the
   URL fragment after `#` is never sent to or read by the server, so this
   page and `https://www.ncbi.nlm.nih.gov/pathogens/isolates` with no
   fragment at all return byte-identical bodies (differing only in a
   per-request `ncbi_phid` session tracking value). HTTP 200 confirms the
   isolate browser itself is reachable, not that a specific
   `biosample_acc` renders on load; whether the client-side app actually
   pre-populates the search from the fragment was not verified (the same
   scope F-3.3-A-09 stopped at). Documented honestly rather than
   overclaimed, per that finding's own precedent.

## The three findings this module implements (per the dispatching task)

F-3.5-01 (critical, deadline discipline): `cluster_snp_neighbors` streams
`Clusters/*.reference_target.SNP_distances.tsv` (~411 GB) via
`pathogen_ftp_transport.stream_filtered_tsv_rows`, filtered by `PDS_acc`,
bounded by ONE shared `deadline` computed once per invocation
(`_pathogen_detection_impl`) and threaded through every FTP read that
invocation makes. `_deadline_exceeded_output` is the single place a
deadline cutoff becomes an output: always `status: "empty"` with an
actionable message naming the timeout and suggesting a narrower
`max_snp_distance` or a more specific cluster, NEVER a silently-partial
`status: "ok"`. Both `TsvScanResult.truncated_by_deadline` (checked after
every scan) and a fail-fast check BEFORE starting a scan whose remaining
budget is already zero or negative feed this same path.

F-3.5-03 (comma-join/NULL parsing): `_parse_pathogen_list_field` strips a
double-quoted comma-join (`"ant(2'')-Ia,aph(3')-Ia,blaTEM-1"`) into a real
`list[str]`, and treats the bare literal `NULL` (or an empty/whitespace
value) as `[]`, never as `["NULL"]`. Applied to `AMR_genotypes` and
`AST_phenotypes` uniformly.

The snapshot-pinning trap (Section 6.6 / Tool_implementation_mechanics.md):
every FTP read in this module goes through
`pathogen_ftp_transport.resolve_complete_snapshot(taxon, client=client)`
exactly once per invocation; the resolved snapshot id is reused for every
subsequent URL this invocation builds, so a single call never mixes rows
from two different snapshots even if a newer one completes mid-call.

## Untrusted content (ai-security-standards.md)

Every free-text field this module reads from a Metadata/Clusters TSV row
(`strain`, `serovar`, `geo_loc_name`, `collection_date`, the parsed
`amr_genotypes`/`ast_phenotypes` entries) is lab-submitted content, the
same untrusted-external-content class every other Layer 2/3 tool's
free-text fields are. Nothing in this module ever evaluates, formats as a
template, or executes any of it; every value is either passed through
Pydantic's own typed, length-capped fields unmodified, or withheld
entirely per the withhold-not-truncate policy below. `taxon` gets an
additional, narrower defense: it is used to build a URL PATH SEGMENT, not
merely cited as data, so `_TAXON_SHAPE_PATTERN` re-checks it at this
layer (defense in depth; the schema layer already enforces the same
pattern, see `pathogen_detection_schemas.PATHOGEN_TAXON_PATTERN`) before
any URL is built from it, following the exact
"validate before building a URL from unsanitized caller input"
requirement the dispatching task's own "Standing rules" section states.

Never raises: `pathogen_detection` (the public entry point) wraps
`_pathogen_detection_impl` in a `try`/`except`, the same outer-boundary
pattern `ncbi_dbsnp.py`'s and `litvar2_lookup.py`'s dispatchers use, per
`.claude/rules/production-standards.md`'s retry-safety gate: an error
message must say what to do next, not just what failed.

Depends on:
    - system_03_search_agent.tools.pathogen_ftp_transport (NOT present in
      this worktree at build time; see the module-level warning above).
      Consumed via `resolve_complete_snapshot`, `stream_filtered_tsv_rows`,
      `TsvScanResult`, `PathogenSnapshotUnavailableError`,
      `PathogenDeadlineExceededError`, `DEFAULT_TIMEOUT_S`,
      `PATHOGEN_FTP_BASE`.
    - system_03_search_agent.tools.pathogen_detection_schemas (T-3.5-03;
      `PathogenDetectionInput`, `PathogenDetectionOutput`, `PathogenIsolate`,
      `PathogenIsolateLookupInput`, `PathogenClusterSnpNeighborsInput`,
      `PATHOGEN_TAXON_PATTERN`, `PATHOGEN_SOURCE_URL_PATTERN`)
    - httpx (AsyncClient, per assumption 1 above)

Reads:
    - Nothing directly beyond outbound HTTPS via `pathogen_ftp_transport`.
      No API key: the Pathogen Detection FTP tree needs none.

Writes:
    - Nothing. Outbound HTTPS requests only, via `pathogen_ftp_transport`.

Depended by:
    - system_03_search_agent.harness.cache (tool registration, a separate
      ticket per this build task's own file-ownership list, explicitly
      out of scope here)
    - tests/system_03_search_agent/tools/test_pathogen_detection.py
    - tests/system_03_search_agent/tools/test_pathogen_detection_premise.py,
      IF that file exists in a later merge of this worktree; it did not
      exist anywhere in this worktree at the time this module was written.
"""

from __future__ import annotations

import re
import time
from typing import Final
from urllib.parse import quote

import httpx

from system_03_search_agent.tools import pathogen_ftp_transport
from system_03_search_agent.tools.pathogen_detection_schemas import (
    PATHOGEN_SOURCE_URL_PATTERN,
    PATHOGEN_TAXON_PATTERN,
    PathogenClusterSnpNeighborsInput,
    PathogenDetectionInput,
    PathogenDetectionOutput,
    PathogenIsolate,
    PathogenIsolateLookupInput,
)

_TAXON_SHAPE_PATTERN: Final[re.Pattern[str]] = re.compile(PATHOGEN_TAXON_PATTERN)
# Matched with .fullmatch(), never .match(): see
# pathogen_detection_schemas.py's design decision 2 for why (Python re's
# own `$`-before-trailing-newline exception; fullmatch is the portable
# equivalent of `\A...\Z`, which pydantic-core's Rust regex engine cannot
# parse).

# Assumption 4 in the module docstring: twice the documented floor, since
# one invocation can share this budget across up to three sequential FTP
# reads. Asserted against the floor below so a future change to the rule
# cannot silently put this module out of compliance without failing loud
# at import time.
_TOTAL_BUDGET_S: Final[float] = 120.0
assert _TOTAL_BUDGET_S >= pathogen_ftp_transport.DEFAULT_TIMEOUT_S, (
    "_TOTAL_BUDGET_S must stay at or above pathogen_ftp_transport.DEFAULT_TIMEOUT_S "
    "(.claude/rules/tool-call-budgets.md's 60-second-or-more floor for pathogen_detection)"
)

_MAX_ISOLATES: Final[int] = 100
_DEFAULT_ISOLATE_LOOKUP_SNP_DISTANCE: Final[int] = 5

# Field caps, mirroring pathogen_detection_schemas.py's own Field(max_length=...)
# constraints exactly, checked here BEFORE construction so an over-cap
# value is withheld (or, for an identity field, excludes the whole
# isolate) rather than raising pydantic.ValidationError deep inside output
# construction. Same discipline litvar2_lookup.py's own cap constants
# document.
_MAX_BIOSAMPLE_CHARS: Final[int] = 30
_MAX_RUN_SRA_CHARS: Final[int] = 30
_MAX_STRAIN_CHARS: Final[int] = 100
_MAX_SEROVAR_CHARS: Final[int] = 60
_MAX_GEO_CHARS: Final[int] = 150
_MAX_COLLECTION_DATE_CHARS: Final[int] = 30
_MAX_PDS_CLUSTER_CHARS: Final[int] = 30
_MAX_AMR_CHARS: Final[int] = 40
_MAX_AST_CHARS: Final[int] = 60
_MAX_AMR_ITEMS: Final[int] = 30
_MAX_AST_ITEMS: Final[int] = 30
_MAX_SOURCE_URL_CHARS: Final[int] = 300
_MAX_ERROR_CHARS: Final[int] = 500
_MAX_SNAPSHOT_CHARS: Final[int] = 30
_MAX_WITHHELD_NOTE_CHARS: Final[int] = 150
_MAX_FIELDS_WITHHELD_ITEMS: Final[int] = 20

# Assumption 3 in the module docstring: `biosample_acc` is directly named
# by Section 6.6's own source-file table; the rest are candidate lists,
# tried in order, because the real column names could not be live-verified
# from this worktree.
_METADATA_KEY_COLUMN: Final[str] = "biosample_acc"
_RUN_SRA_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("Run", "run_sra", "run")
_STRAIN_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("strain",)
_SEROVAR_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("serovar",)
_GEO_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("geo_loc_name",)
_COLLECTION_DATE_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("collection_date",)
_AMR_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("AMR_genotypes", "amr_genotypes")
_AST_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("AST_phenotypes", "ast_phenotypes")

_CLUSTER_LIST_KEY_COLUMN: Final[str] = "biosample_acc"
_CLUSTER_LIST_CLUSTER_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("PDS_acc", "pds_cluster")

# F-3.5-01's own quoted finding: "filtering rows by PDS_acc". This one is
# directly stated, not a candidate list.
_SNP_DISTANCES_CLUSTER_COLUMN: Final[str] = "PDS_acc"

# CORRECTED against the real live header (tracker/phase_3.5.md's pre-build
# probe, 2026-08-08), which this worktree could not read at write time:
# SNP_distances.tsv is a PAIRWISE file, one row per isolate pair, with
# BOTH accessions suffixed _1/_2 (`target_acc_1`, `biosample_acc_1`,
# `gencoll_acc_1`, `sample_name_1`, then the same four suffixed _2), never
# a single unsuffixed "target" column. The distance metric NCBI's own
# pipeline reports is `compatible_distance` (verified present in the real
# header, alongside `delta_positions_unambiguous`/`informative_positions`,
# which are inputs to that metric rather than the metric itself).
_SNP_DISTANCES_SIDE1_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("biosample_acc_1",)
_SNP_DISTANCES_SIDE2_COLUMN_CANDIDATES: Final[tuple[str, ...]] = ("biosample_acc_2",)
_SNP_DISTANCES_DISTANCE_COLUMN_CANDIDATES: Final[tuple[str, ...]] = (
    "compatible_distance",
    "delta_positions_unambiguous",
)


def _remaining(deadline: float) -> float:
    return deadline - time.monotonic()


def _cap(text: str, limit: int) -> str:
    return text[:limit]


def _withheld_note(text: str) -> str:
    """Cap a diagnostic fields_withheld entry. Truncates a NOTE describing
    what was withheld, never the withheld DATA itself (dropped entirely),
    matching litvar2_lookup.py's `_withheld_note` exactly.
    """
    return _cap(text, _MAX_WITHHELD_NOTE_CHARS)


def _cap_fields_withheld(notes: list[str]) -> list[str]:
    """Cap fields_withheld at its schema max_length=20, disclosing an
    overflow rather than silently dropping it, matching
    litvar2_lookup.py's `_cap_fields_withheld` exactly.
    """
    if len(notes) <= _MAX_FIELDS_WITHHELD_ITEMS:
        return notes
    kept = notes[: _MAX_FIELDS_WITHHELD_ITEMS - 1]
    overflow = len(notes) - len(kept)
    kept.append(
        _withheld_note(
            f"...and {overflow} more fields withheld (the withholding count "
            f"exceeded the {_MAX_FIELDS_WITHHELD_ITEMS}-item disclosure cap)"
        )
    )
    return kept


def _first_present(row: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    """Return the first non-empty value found under any candidate column
    name, or None. Case-sensitive first pass, then a case-insensitive
    fallback, since the real TSV header casing could not be live-verified
    from this worktree (assumption 3 in the module docstring).
    """
    for name in candidates:
        value = row.get(name)
        if value is not None and value != "":
            return value
    lowered = {key.lower(): value for key, value in row.items()}
    for name in candidates:
        value = lowered.get(name.lower())
        if value is not None and value != "":
            return value
    return None


def _parse_pathogen_list_field(raw: str | None) -> list[str]:
    """F-3.5-03: parse a double-quoted comma-joined TSV cell into a real
    list[str]. A bare NULL, or an empty/whitespace value, becomes [],
    never ["NULL"].

    Example: '"ant(2\\'\\')-Ia,aph(3\\')-Ia,blaTEM-1"' -> ["ant(2'')-Ia",
    "aph(3')-Ia", "blaTEM-1"]. A value with no surrounding quotes at all
    (a single unquoted term, or an already-unquoted comma-join) is handled
    the same way: the quote-stripping step is a no-op when no matching
    outer quotes are present, so it never damages an unquoted value.
    """
    if raw is None:
        return []
    value = raw.strip()
    if not value or value.upper() == "NULL":
        return []
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item and item.upper() != "NULL"]


def _cap_or_withhold(
    value: str | None, limit: int, field_name: str, withheld: list[str]
) -> str | None:
    """A scalar field: None/empty/NULL becomes None (a fact, not a
    failure); an over-length value is withheld (dropped, appended to
    `withheld`, never truncated), matching ncbi_dbsnp.py's
    `_cap_or_withhold` and litvar2_lookup.py's per-field withhold
    treatment.
    """
    if value is None:
        return None
    value = value.strip()
    if not value or value.upper() == "NULL":
        return None
    if len(value) > limit:
        withheld.append(_withheld_note(f"{field_name}: {value}"))
        return None
    return value


def _parse_list_field_capped(
    raw: str | None, item_limit: int, item_cap_count: int, field_name: str, withheld: list[str]
) -> list[str]:
    """F-3.5-03's comma-join parse, plus per-item withhold-not-truncate and
    a spec-authorized array-length cap (the same "truncate to the array
    cap, never a term's own content" split litvar2_lookup.py's
    `_parse_clinical_significance` documents).
    """
    parsed = _parse_pathogen_list_field(raw)
    kept: list[str] = []
    for term in parsed:
        if len(term) > item_limit:
            withheld.append(_withheld_note(f"{field_name}: {term}"))
            continue
        kept.append(term)
    if len(kept) > item_cap_count:
        kept = kept[:item_cap_count]
    return kept


def _build_isolate(
    row: dict[str, str],
    *,
    cluster_id_override: str | None,
    snp_distance: int | None,
) -> tuple[PathogenIsolate | None, list[str]]:
    """Build one PathogenIsolate from a raw Metadata TSV row dict, or
    exclude it. Returns (isolate_or_None, withheld_notes). `None` only
    when the identity field (biosample_acc) overflows its cap: the
    whole-item exclusion discipline `pathogen_detection_schemas.
    PathogenIsolate`'s own docstring documents.
    """
    withheld: list[str] = []

    biosample_raw = row.get(_METADATA_KEY_COLUMN)
    biosample_acc = biosample_raw.strip() if isinstance(biosample_raw, str) else None
    if biosample_acc and len(biosample_acc) > _MAX_BIOSAMPLE_CHARS:
        return None, [
            _withheld_note(
                f"isolate row: excluded, biosample_acc {len(biosample_acc)} chars "
                f"exceeds {_MAX_BIOSAMPLE_CHARS} cap"
            )
        ]
    if not biosample_acc:
        return None, [_withheld_note("isolate row: excluded, no biosample_acc present")]

    run_sra = _cap_or_withhold(
        _first_present(row, _RUN_SRA_COLUMN_CANDIDATES), _MAX_RUN_SRA_CHARS, "run_sra", withheld
    )
    strain = _cap_or_withhold(
        _first_present(row, _STRAIN_COLUMN_CANDIDATES), _MAX_STRAIN_CHARS, "strain", withheld
    )
    serovar = _cap_or_withhold(
        _first_present(row, _SEROVAR_COLUMN_CANDIDATES), _MAX_SEROVAR_CHARS, "serovar", withheld
    )
    geo_loc_name = _cap_or_withhold(
        _first_present(row, _GEO_COLUMN_CANDIDATES), _MAX_GEO_CHARS, "geo_loc_name", withheld
    )
    collection_date = _cap_or_withhold(
        _first_present(row, _COLLECTION_DATE_COLUMN_CANDIDATES),
        _MAX_COLLECTION_DATE_CHARS,
        "collection_date",
        withheld,
    )
    pds_cluster = _cap_or_withhold(
        cluster_id_override, _MAX_PDS_CLUSTER_CHARS, "pds_cluster", withheld
    )
    amr_genotypes = _parse_list_field_capped(
        _first_present(row, _AMR_COLUMN_CANDIDATES),
        _MAX_AMR_CHARS,
        _MAX_AMR_ITEMS,
        f"isolates[{biosample_acc}].amr_genotypes",
        withheld,
    )
    ast_phenotypes = _parse_list_field_capped(
        _first_present(row, _AST_COLUMN_CANDIDATES),
        _MAX_AST_CHARS,
        _MAX_AST_ITEMS,
        f"isolates[{biosample_acc}].ast_phenotypes",
        withheld,
    )

    source_url = _build_isolate_source_url(biosample_acc)

    isolate = PathogenIsolate(
        biosample_acc=biosample_acc,
        run_sra=run_sra,
        strain=strain,
        serovar=serovar,
        geo_loc_name=geo_loc_name,
        collection_date=collection_date,
        pds_cluster=pds_cluster,
        amr_genotypes=amr_genotypes,
        ast_phenotypes=ast_phenotypes,
        snp_distance=snp_distance,
        source_url=source_url,
    )
    return isolate, withheld


def _build_isolate_source_url(biosample_acc: str) -> str | None:
    """Assumption 5 in the module docstring: NOT live-verified reachable
    from this worktree. Satisfies PATHOGEN_SOURCE_URL_PATTERN and this
    module's best understanding of the isolate browser's URL shape.
    Fails closed (returns None) rather than shipping a URL that would
    fail the schema's own pattern, matching litvar2_lookup.py's
    `_build_source_url` defense-in-depth discipline.
    """
    url = (
        "https://www.ncbi.nlm.nih.gov/pathogens/isolates#/search/biosample_acc:"
        + quote(biosample_acc, safe="")
    )
    if len(url) > _MAX_SOURCE_URL_CHARS:
        return None
    if not re.match(PATHOGEN_SOURCE_URL_PATTERN, url):
        return None
    return url


def _snapshot_base_url(taxon: str, snapshot: str) -> str:
    base = pathogen_ftp_transport.PATHOGEN_FTP_BASE.rstrip("/")
    return f"{base}/{taxon}/{snapshot}/"


def _metadata_url(taxon: str, snapshot: str) -> str:
    return _snapshot_base_url(taxon, snapshot) + f"Metadata/{snapshot}.metadata.tsv"


def _cluster_list_url(taxon: str, snapshot: str) -> str:
    return (
        _snapshot_base_url(taxon, snapshot)
        + f"Clusters/{snapshot}.reference_target.cluster_list.tsv"
    )


def _snp_distances_url(taxon: str, snapshot: str) -> str:
    return (
        _snapshot_base_url(taxon, snapshot)
        + f"Clusters/{snapshot}.reference_target.SNP_distances.tsv"
    )


def _index_snp_distances(
    rows: list[dict[str, str]], anchor_biosamples: set[str] | None, max_snp_distance: int
) -> dict[str, int]:
    """Build {biosample_acc: nearest_snp_distance} from SNP_distances.tsv
    rows already filtered to one PDS cluster (via the `PDS_acc` key
    column, upstream in `stream_filtered_tsv_rows`).

    Each row is a PAIRWISE comparison (`biosample_acc_1` vs
    `biosample_acc_2`, distance in `compatible_distance`), corrected
    against the real live header (`tracker/phase_3.5.md`'s pre-build
    probe): the original draft assumed a single unsuffixed "target"
    column, which the real file does not have.

    `anchor_biosamples=None` (cluster_snp_neighbors): every row already
    qualifies by construction (both sides were filtered to this cluster's
    `PDS_acc`), so both sides are reported as candidate neighbors.
    `anchor_biosamples={one_accession}` (isolate_lookup's optional
    enrichment): only a row where the anchor appears on exactly one side
    counts, and the OTHER side is reported as that anchor's neighbor. A
    row where the anchor appears on both sides, or neither, is skipped as
    uninformative.

    A row this function cannot parse (either side missing, or the
    distance value is not an integer) is skipped, never fabricated as a
    distance of 0 or as a match. Only distances within `max_snp_distance`
    are kept; when the same biosample is reported by more than one row,
    the SMALLEST observed distance wins (nearest neighbor).
    """
    result: dict[str, int] = {}
    for row in rows:
        side1 = _first_present(row, _SNP_DISTANCES_SIDE1_COLUMN_CANDIDATES)
        side2 = _first_present(row, _SNP_DISTANCES_SIDE2_COLUMN_CANDIDATES)
        distance_raw = _first_present(row, _SNP_DISTANCES_DISTANCE_COLUMN_CANDIDATES)
        if side1 is None or side2 is None or distance_raw is None:
            continue
        side1, side2 = side1.strip(), side2.strip()
        try:
            distance = int(distance_raw.strip())
        except (ValueError, AttributeError):
            continue
        if distance < 0 or distance > max_snp_distance:
            continue

        if anchor_biosamples is None:
            candidates: tuple[str, ...] = (side1, side2)
        elif side1 in anchor_biosamples and side2 not in anchor_biosamples:
            candidates = (side2,)
        elif side2 in anchor_biosamples and side1 not in anchor_biosamples:
            candidates = (side1,)
        else:
            continue  # neither side is the anchor, or both are: not informative

        for candidate in candidates:
            existing = result.get(candidate)
            if existing is None or distance < existing:
                result[candidate] = distance
    return result


def _deadline_exceeded_output(mode: str, stage: str) -> PathogenDetectionOutput:
    """F-3.5-01: a deadline cutoff before a scan completes is always
    status: "empty" with an actionable message, never a silently-partial
    status: "ok".
    """
    return PathogenDetectionOutput(
        status="empty",
        mode=mode,
        isolate_count=0,
        total_available=0,
        truncated=True,
        error=_cap(
            f"pathogen_detection's {_TOTAL_BUDGET_S:.0f}s shared wall-clock budget was "
            f"exhausted during the {stage} step before the scan completed. This is not a "
            "partial answer; nothing returned here should be treated as complete. Retry "
            "with a narrower max_snp_distance, a more specific pds_cluster or "
            "biosample_acc, or during a period of lower FTP load.",
            _MAX_ERROR_CHARS,
        ),
    )


def _error_output(mode: str, message: str) -> PathogenDetectionOutput:
    return PathogenDetectionOutput(
        status="error",
        mode=mode,
        isolate_count=0,
        total_available=0,
        truncated=False,
        error=_cap(message, _MAX_ERROR_CHARS),
    )


async def _isolate_lookup(
    action: PathogenIsolateLookupInput,
    snapshot: str,
    taxon: str,
    deadline: float,
    client: httpx.AsyncClient,
) -> PathogenDetectionOutput:
    if _remaining(deadline) <= 0:
        return _deadline_exceeded_output(action.mode, "isolate_lookup metadata read")

    try:
        metadata_scan = await pathogen_ftp_transport.stream_filtered_tsv_rows(
            _metadata_url(taxon, snapshot),
            key_column=_METADATA_KEY_COLUMN,
            key_values={action.biosample_acc},
            deadline=deadline,
            client=client,
            max_matches=1,
        )
    except pathogen_ftp_transport.PathogenDeadlineExceededError:
        return _deadline_exceeded_output(action.mode, "isolate_lookup metadata read")

    if metadata_scan.truncated_by_deadline:
        return _deadline_exceeded_output(action.mode, "isolate_lookup metadata read")

    if not metadata_scan.rows:
        return PathogenDetectionOutput(
            status="empty",
            mode=action.mode,
            pdg_snapshot=_cap(snapshot, _MAX_SNAPSHOT_CHARS),
            isolate_count=0,
            total_available=0,
            truncated=False,
        )

    # Cluster membership: best-effort per this task's own explicit
    # allowance ("if the SNP-distance read for a single isolate lookup is
    # expensive, you may design it as optional/best-effort as long as
    # status/isolates/amr_genotypes are always correct"). Any failure here
    # (deadline, a transport error, an unparseable row, anything at all)
    # never fails the call; it only means pds_cluster/snp_distance stay
    # None on the returned isolate. This is the ONE place in this module
    # that deliberately catches a bare `Exception` rather than the
    # specific `PathogenDeadlineExceededError` the mandatory reads
    # elsewhere in this file catch: every other FTP read in this module is
    # load-bearing for the call's own correctness and must surface a
    # genuine failure, this pair is the one sub-step the dispatching task
    # explicitly authorized as optional.
    cluster_id: str | None = None
    snp_distance: int | None = None
    if _remaining(deadline) > 0:
        try:
            cluster_scan = await pathogen_ftp_transport.stream_filtered_tsv_rows(
                _cluster_list_url(taxon, snapshot),
                key_column=_CLUSTER_LIST_KEY_COLUMN,
                key_values={action.biosample_acc},
                deadline=deadline,
                client=client,
                max_matches=1,
            )
            if cluster_scan.rows and not cluster_scan.truncated_by_deadline:
                cluster_id = _first_present(
                    cluster_scan.rows[0], _CLUSTER_LIST_CLUSTER_COLUMN_CANDIDATES
                )
        except Exception:  # noqa: BLE001 - deliberately broad, see comment above
            cluster_id = None

    if cluster_id and _remaining(deadline) > 0:
        try:
            snp_scan = await pathogen_ftp_transport.stream_filtered_tsv_rows(
                _snp_distances_url(taxon, snapshot),
                key_column=_SNP_DISTANCES_CLUSTER_COLUMN,
                key_values={cluster_id},
                deadline=deadline,
                client=client,
            )
            if not snp_scan.truncated_by_deadline:
                # anchor_biosamples={action.biosample_acc}: the returned
                # dict is keyed by the OTHER side of each qualifying pair
                # (the neighbor), never by the anchor's own accession, so
                # this isolate's own nearest-neighbor distance is the
                # SMALLEST value in the dict, not a lookup by its own id.
                distances = _index_snp_distances(
                    snp_scan.rows,
                    {action.biosample_acc},
                    _DEFAULT_ISOLATE_LOOKUP_SNP_DISTANCE,
                )
                snp_distance = min(distances.values()) if distances else None
        except Exception:  # noqa: BLE001 - deliberately broad, see comment above
            snp_distance = None

    isolate, withheld = _build_isolate(
        metadata_scan.rows[0], cluster_id_override=cluster_id, snp_distance=snp_distance
    )
    if isolate is None:
        # The identity field itself (biosample_acc) overflowed its cap or
        # was absent, which should not be possible given this is the exact
        # row the key-filtered scan matched, but fails closed rather than
        # raising, matching this module's never-raises outer contract.
        return PathogenDetectionOutput(
            status="empty",
            mode=action.mode,
            pdg_snapshot=_cap(snapshot, _MAX_SNAPSHOT_CHARS),
            isolate_count=0,
            total_available=0,
            truncated=False,
            fields_withheld=_cap_fields_withheld(withheld) if withheld else None,
        )

    return PathogenDetectionOutput(
        status="ok",
        mode=action.mode,
        pdg_snapshot=_cap(snapshot, _MAX_SNAPSHOT_CHARS),
        isolates=[isolate],
        isolate_count=1,
        total_available=1,
        truncated=False,
        fields_withheld=_cap_fields_withheld(withheld) if withheld else None,
    )


async def _cluster_snp_neighbors(
    action: PathogenClusterSnpNeighborsInput,
    snapshot: str,
    taxon: str,
    deadline: float,
    client: httpx.AsyncClient,
) -> PathogenDetectionOutput:
    if _remaining(deadline) <= 0:
        return _deadline_exceeded_output(action.mode, "cluster_snp_neighbors cluster_list read")

    try:
        cluster_scan = await pathogen_ftp_transport.stream_filtered_tsv_rows(
            _cluster_list_url(taxon, snapshot),
            key_column=_SNP_DISTANCES_CLUSTER_COLUMN,
            key_values={action.pds_cluster},
            deadline=deadline,
            client=client,
        )
    except pathogen_ftp_transport.PathogenDeadlineExceededError:
        return _deadline_exceeded_output(action.mode, "cluster_snp_neighbors cluster_list read")

    if cluster_scan.truncated_by_deadline:
        return _deadline_exceeded_output(action.mode, "cluster_snp_neighbors cluster_list read")

    if not cluster_scan.rows:
        return PathogenDetectionOutput(
            status="empty",
            mode=action.mode,
            pdg_snapshot=_cap(snapshot, _MAX_SNAPSHOT_CHARS),
            isolate_count=0,
            total_available=0,
            truncated=False,
        )

    member_biosamples: set[str] = set()
    for row in cluster_scan.rows:
        value = row.get(_CLUSTER_LIST_KEY_COLUMN)
        if value:
            member_biosamples.add(value.strip())
    total_available = len(member_biosamples)
    if total_available == 0:
        return PathogenDetectionOutput(
            status="empty",
            mode=action.mode,
            pdg_snapshot=_cap(snapshot, _MAX_SNAPSHOT_CHARS),
            isolate_count=0,
            total_available=0,
            truncated=False,
        )

    if _remaining(deadline) <= 0:
        return _deadline_exceeded_output(
            action.mode, "cluster_snp_neighbors SNP_distances read"
        )
    try:
        snp_scan = await pathogen_ftp_transport.stream_filtered_tsv_rows(
            _snp_distances_url(taxon, snapshot),
            key_column=_SNP_DISTANCES_CLUSTER_COLUMN,
            key_values={action.pds_cluster},
            deadline=deadline,
            client=client,
        )
    except pathogen_ftp_transport.PathogenDeadlineExceededError:
        return _deadline_exceeded_output(
            action.mode, "cluster_snp_neighbors SNP_distances read"
        )
    if snp_scan.truncated_by_deadline:
        return _deadline_exceeded_output(
            action.mode, "cluster_snp_neighbors SNP_distances read"
        )
    # anchor_biosamples=None: every row already qualifies by construction,
    # since both sides were filtered to this cluster's PDS_acc upstream
    # (F-3.5-01, see _index_snp_distances's own docstring for why this
    # differs from isolate_lookup's single-anchor call below).
    distances = _index_snp_distances(snp_scan.rows, None, action.max_snp_distance)

    # Neighbors are isolates the SNP_distances scan actually placed within
    # max_snp_distance, not the whole cluster's membership: a cluster
    # member with no qualifying row is not a "neighbor" of anything and
    # must not be reported with a fabricated or missing snp_distance
    # (the premise gate's own case 3 asserts every returned isolate in a
    # status="ok" response carries a real, in-budget snp_distance).
    neighbor_biosamples = set(distances.keys())
    if not neighbor_biosamples:
        return PathogenDetectionOutput(
            status="empty",
            mode=action.mode,
            pdg_snapshot=_cap(snapshot, _MAX_SNAPSHOT_CHARS),
            isolate_count=0,
            total_available=0,
            truncated=False,
            error=_cap(
                f"No isolate in cluster {action.pds_cluster!r} was found within "
                f"{action.max_snp_distance} SNP(s) of another cluster member.",
                _MAX_ERROR_CHARS,
            ),
        )
    total_available = len(neighbor_biosamples)

    if _remaining(deadline) <= 0:
        return _deadline_exceeded_output(action.mode, "cluster_snp_neighbors metadata read")
    try:
        metadata_scan = await pathogen_ftp_transport.stream_filtered_tsv_rows(
            _metadata_url(taxon, snapshot),
            key_column=_METADATA_KEY_COLUMN,
            key_values=neighbor_biosamples,
            deadline=deadline,
            client=client,
            max_matches=_MAX_ISOLATES,
        )
    except pathogen_ftp_transport.PathogenDeadlineExceededError:
        return _deadline_exceeded_output(action.mode, "cluster_snp_neighbors metadata read")
    if metadata_scan.truncated_by_deadline:
        return _deadline_exceeded_output(action.mode, "cluster_snp_neighbors metadata read")

    isolates: list[PathogenIsolate] = []
    withheld_all: list[str] = []
    for row in metadata_scan.rows[:_MAX_ISOLATES]:
        biosample = row.get(_METADATA_KEY_COLUMN)
        snp_distance = distances.get(biosample.strip()) if biosample else None
        if snp_distance is None:
            continue  # not one of this cluster's within-budget neighbors
        isolate, withheld = _build_isolate(
            row, cluster_id_override=action.pds_cluster, snp_distance=snp_distance
        )
        withheld_all.extend(withheld)
        if isolate is not None:
            isolates.append(isolate)

    truncated = len(isolates) < total_available
    if not isolates:
        return PathogenDetectionOutput(
            status="empty",
            mode=action.mode,
            pdg_snapshot=_cap(snapshot, _MAX_SNAPSHOT_CHARS),
            isolate_count=0,
            total_available=total_available,
            truncated=truncated,
            fields_withheld=_cap_fields_withheld(withheld_all) if withheld_all else None,
        )

    return PathogenDetectionOutput(
        status="ok",
        mode=action.mode,
        pdg_snapshot=_cap(snapshot, _MAX_SNAPSHOT_CHARS),
        isolates=isolates,
        isolate_count=len(isolates),
        total_available=total_available,
        truncated=truncated,
        fields_withheld=_cap_fields_withheld(withheld_all) if withheld_all else None,
    )


async def _pathogen_detection_impl(input_data: PathogenDetectionInput) -> PathogenDetectionOutput:
    """The real implementation. See `pathogen_detection` below for the
    never-raises wrapper.

    F-3.5-01: `deadline` is computed exactly ONCE here, per invocation,
    and threaded through every FTP read this invocation makes (snapshot
    resolution, and whichever mode-specific reads follow). Never
    recomputed per read.
    """
    action = input_data.root
    taxon = action.taxon

    if not _TAXON_SHAPE_PATTERN.fullmatch(taxon):
        # Defense in depth: pathogen_detection_schemas.PathogenIsolateLookupInput
        # and PathogenClusterSnpNeighborsInput already enforce this same
        # pattern at construction time, so this branch should be
        # unreachable via the public Pydantic entry point. Kept anyway per
        # the dispatching task's own "Standing rules" requirement to
        # validate taxon before building a URL from it at THIS layer too,
        # not only at the schema layer.
        return _error_output(
            action.mode,
            f"taxon {taxon!r} is not a valid FTP folder name (letters, digits, "
            "underscore, hyphen only, starting with a letter). Refusing to build a URL "
            "from it.",
        )

    deadline = time.monotonic() + _TOTAL_BUDGET_S

    async with httpx.AsyncClient() as client:
        try:
            snapshot = await pathogen_ftp_transport.resolve_complete_snapshot(
                taxon, client=client
            )
        except pathogen_ftp_transport.PathogenSnapshotUnavailableError as exc:
            return _error_output(
                action.mode,
                f"No complete Pathogen Detection snapshot is available for taxon "
                f"{taxon!r}: {exc}. Verify the taxon name (for example 'Salmonella') "
                "or try again later once NCBI's snapshot build for this taxon completes.",
            )

        if isinstance(action, PathogenIsolateLookupInput):
            return await _isolate_lookup(action, snapshot, taxon, deadline, client)
        if isinstance(action, PathogenClusterSnpNeighborsInput):
            return await _cluster_snp_neighbors(action, snapshot, taxon, deadline, client)
        # Defensive, not assumed reachable: PathogenAction is a closed,
        # discriminator-validated union pydantic has already checked at
        # construction time, so every real branch is handled above.
        # Matches ncbi_dbsnp.py's and litvar2_lookup.py's own
        # trailing-branch discipline for their own mode dispatch.
        return _error_output(
            "error",
            f"pathogen_detection has no branch for input {action!r}. This is a tool "
            "defect, not a caller error; report it rather than retrying.",
        )


async def pathogen_detection(input_data: PathogenDetectionInput) -> PathogenDetectionOutput:
    """Bulk Salmonella isolate/cluster/AMR access over the NCBI Pathogen
    Detection PDG snapshot tree. Never raises.

    See the module docstring for the two modes, the flagged assumptions
    this module was forced to make in the absence of the real
    `pathogen_ftp_transport.py`, and the F-3.5-01/F-3.5-03 findings this
    implementation closes. This public entry point is a thin wrapper
    around `_pathogen_detection_impl`: every expected failure (a
    transport error, a rejected input, a deadline cutoff) is already
    classified and returned as a `status: "error"` or `status: "empty"`
    output by the functions above. This wrapper's own `try`/`except` is
    the last-resort boundary for an UNEXPECTED exception, the same
    outer-boundary pattern `ncbi_dbsnp.py`'s and `litvar2_lookup.py`'s
    dispatchers use, per `.claude/rules/production-standards.md`'s
    retry-safety gate: an error message must say what to do next, not
    just what failed.
    """
    try:
        return await _pathogen_detection_impl(input_data)
    except Exception as exc:  # noqa: BLE001 - the module's deliberate last-resort catch
        mode = getattr(getattr(input_data, "root", None), "mode", "error")
        return _error_output(
            str(mode),
            f"pathogen_detection raised an unexpected {type(exc).__name__} instead of "
            f"returning a classified result: {exc}. Retry once; if this recurs, this "
            "tool has a defect that needs fixing before it can be trusted.",
        )
