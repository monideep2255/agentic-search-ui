"""dbVar/ClinVar coordinate-overlap action for `ncbi_efetch` (T-3.1-10).

This is one action on `ncbi_efetch` (Technical_specification.md Section 6.2,
lines 961 to 970), but it gets its own module rather than living inside
`ncbi_efetch.py` alongside the other six actions: it is a five-step
procedure across two ESearch/ESummary calls with a real filtering predicate
in between, not a single parameterized request built from an input dict the
way `search`, `fetch`, `summary`, `link`, `dataset_report`, and
`pubchem_property` are.

## The trap this module exists to close

dbVar and ClinVar coordinate-range search on Entrez LOOKS like genomic
interval overlap and is not. `docs/ncbi/Tool_implementation_mechanics.md:
100-108` and the phase 4 capability sheet
(`requirements/phase_4/API_capability_sheet.md:150-160`) proved this live:
on dbVar, chromosome 1, GRCh38 window 1,000,000 to 1,100,000, three sampled
"hits" from a two-field ESearch trick were all 0bp point insertions that
matched only because a GRCh37 unplaced-scaffold start paired numerically
with a GRCh38 end. Trusting the raw ESearch range as the answer is a
confident, cited, WRONG answer, which is the exact failure class this whole
system exists to prevent.

This module re-verified the bug live on 2026-08-05, using the actual step-1
query this module issues (a single `[BASE]` range field pinned to `[ASSM]`,
not the capability sheet's deliberately looser two-field trick), and found
the same shape occurring through the real step-1 query: dbVar uid 57696443
(`nsv7855404`, a real ~80bp copy number variant, not a degenerate point
insertion) is a coarse-prefilter candidate for the window above because its
GRCh37.p13 placement (1,084,984 to 1,085,063) falls inside the window, while
its actual GRCh38 placement (1,149,604 to 1,149,683) does not overlap the
window at all. `test_ncbi_efetch_premise.py`'s case 17 pins this exact
record as live ground truth: the tool must surface at least one genuine
overlap in this window AND must never surface `nsv7855404`.

## The five steps (Section 6.2, lines 962 to 969), implemented exactly

1. ESearch coarse prefilter, one request:
   dbVar:   `<chr>[CH] AND <start>:<end>[BASE] AND <assembly>[ASSM]`
   ClinVar: `<chr>[CHR] AND <start>:<end>[C37 or CPOS]`
   `retmax` is capped at `max_candidates` so the tool never place-checks an
   unbounded candidate set; `esearchresult.count` (the TOTAL match count,
   independent of `retmax`) is carried into the output's `total_available`,
   and `truncated` is set honestly whenever `count` exceeds the number of
   ids actually returned.
2. ESummary every candidate id, in exactly ONE batched call (comma-joined
   ids), never one call per candidate. Batching is what keeps this
   procedure inside the "no unthrottled burst" instruction from the ticket
   and the shared eutils rate pool in `tool-call-budgets.md`: two network
   calls total per invocation, regardless of how many candidates step 1
   found, not one plus N.
3. Select the placement entry (or entries; see the note below) matching
   the REQUESTED assembly.
4. Apply the exact predicate in code, never in the ESearch query:
   `placement.chr_start <= end AND placement.chr_end >= start`.
5. Drop any candidate that fails step 4, OR that has no placement at all
   for the requested assembly. Only genuine overlaps, each tagged with its
   resolved placement and assembly, reach the output.

## A verified deviation from Section 6.2's stated ClinVar field shape

Section 6.2 states ClinVar exposes `C37`/`CPOS`/`VLEN` as flat ESummary
fields "directly, since those are already single-assembly". Live
verification on 2026-08-05 (ESummary on ClinVar uid 4865884, TP53
c.1035T>C) found no such top-level keys. `C37`/`CPOS`/`CHR` are ESearch
INDEX field tags (confirmed against EInfo's fieldlist for db=clinvar), not
ESummary JSON keys. The actual per-assembly placement data lives nested at
`variation_set[].variation_loc[]`, each entry carrying `assembly_name`
(`"GRCh38"` or `"GRCh37"`, unpatched, verified clean), `chr`, `start`, and
`stop` as strings. This is structurally the same shape as dbVar's
`dbvarplacementlist`, an array of per-assembly placements, not a pair of
flat scalars, and this module reads it that way. No `VLEN` key was present
either; the placement's own `start`/`stop` span already gives the length
directly, so a separate length field is redundant for the overlap
predicate this module applies. Filed as F-3.1-03 (`tracker/phase_3.1.md`)
for the Step 6.2 spec reconciliation; not a local weakening, since the
predicate this module actually applies is unchanged and is exactly Section
6.2's own formula.

## The assembly-match is a prefix match, not an exact match, for dbVar

Live verification found dbVar placements carry PATCHED assembly strings
inconsistently within the same record: uid 57704119 has one placement
tagged bare `"GRCh37"` and a second tagged `"GRCh38.p12"`; uid 57696443 has
`"GRCh38"` (bare) and `"GRCh37.p13"` (patched) side by side. An exact
string match against the caller's requested `"GRCh38"` would silently skip
a legitimate `"GRCh38.p12"` placement, which is a false NEGATIVE, the
opposite-direction failure from the one this module exists to prevent but
still a wrong answer. `_assembly_matches` therefore accepts an exact match
or a `"<requested>."`-prefixed patch version. ClinVar's `assembly_name` was
verified clean (bare `"GRCh38"`/`"GRCh37"`, no patch suffix) in every
record sampled, so this is a no-op for ClinVar and a real fix for dbVar.

## A dbVar record can carry more than one placement for the SAME assembly

Verified live: uid 57735186 (`nsv7894147`) carries two separate
`"GRCh37.p13"` placements. When more than one placement matches the
requested assembly, this module checks the overlap predicate against ALL
of them and keeps the candidate if ANY one overlaps, using that placement
as the resolved one tagged on the output record. Requiring every matching
placement to overlap would be a false NEGATIVE (a record legitimately
split across a translocation or multiple remapped segments, one of which
genuinely covers the window, would be dropped); accepting a candidate on
any single non-overlapping placement while ignoring the others would
silently reintroduce the exact bug this module exists to close. Requiring
at least one matching placement to satisfy the predicate is the reading
consistent with Section 6.2's own step 5 ("only genuine overlaps ... reach
the output").

Depends on:
    - system_03_search_agent.tools.ncbi_efetch_schemas
      (NcbiEfetchCoordinateOverlapInput, NcbiEfetchOutput, NcbiEfetchRecord)
    - system_03_search_agent.tools.ncbi_transport (execute_get,
      classify_eutils_response, and the Transport*Error hierarchy). Both
      network calls this module makes are E-utilities (dbVar and ClinVar
      are both Entrez databases), so only the eutils classifier and the
      "eutils" rate-limit family are ever used here, never the
      status-coded classifier or the datasets/pubchem families.

Reads:
    - Nothing at import time. NCBI_API_KEY is read indirectly, inside
      ncbi_transport, at call time.

Writes:
    - Nothing. Two outbound HTTPS GETs per call (ESearch, then one batched
      ESummary), no local file or database writes.

Depended by:
    - system_03_search_agent.tools.ncbi_efetch (not yet written; a later
      ticket dispatches the `coordinate_overlap` action to this module's
      `coordinate_overlap()` function)
    - tests/system_03_search_agent/tools/test_ncbi_coordinate_overlap.py
      (this module's own unit tests, fully mocked, no live network)
    - tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py,
      cases 17 and 18 (live-network ground truth for this module,
      currently unreachable end to end because `ncbi_efetch.py` does not
      exist yet, exactly like every other case in that file today)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final, Literal

import httpx
import pydantic

from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchCoordinateOverlapInput,
    NcbiEfetchOutput,
    NcbiEfetchRecord,
)
from system_03_search_agent.tools.ncbi_transport import (
    TransportConnectionError,
    TransportRateLimitedError,
    TransportTimeoutError,
    classify_eutils_response,
    execute_get,
)

logger = logging.getLogger(__name__)

_ESEARCH_URL: Final[str] = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY_URL: Final[str] = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# "Cap the number of candidates you will place-check" (ticket instruction).
# Chosen so a single ESummary call stays well under any practical URL-length
# or NCBI batch-size concern, while still comfortably covering the coarse
# prefilter's first page for the queries this tool is expected to serve
# (verified live: the proven-bug fixture in case 17 appears at position 2
# of 10 for its window, well inside this cap).
_DEFAULT_MAX_CANDIDATES: Final[int] = 20

# Record-page URL templates. Both hosts are `www.ncbi.nlm.nih.gov`, which
# NCBI_EFETCH_RECORD_URL_PATTERN in ncbi_efetch_schemas.py already accepts;
# neither fetch call in this module ever touches these hosts, only
# eutils.ncbi.nlm.nih.gov, so the fetch-host-vs-record-host split
# ncbi_efetch_schemas.py's design decision 3 documents applies here too.
# Both templates verified live 2026-08-05 (HTTP 200, `curl -L`):
#   https://www.ncbi.nlm.nih.gov/dbvar/variants/nsv7863080/
#   https://www.ncbi.nlm.nih.gov/clinvar/variation/4865884/
_DBVAR_SOURCE_URL: Final[str] = "https://www.ncbi.nlm.nih.gov/dbvar/variants/{accession}/"
_CLINVAR_SOURCE_URL: Final[str] = "https://www.ncbi.nlm.nih.gov/clinvar/variation/{uid}/"


@dataclass(frozen=True)
class _Placement:
    """One assembly-tagged genomic placement, dbVar and ClinVar alike.

    dbVar's `dbvarplacementlist` and ClinVar's `variation_set[].
    variation_loc[]` are read into this one shape (see the module
    docstring's field-shape section for why ClinVar is NOT the flat
    `C37`/`CPOS` scalars Section 6.2 describes), so step 3 and step 4 below
    run identically regardless of which database the candidate came from.
    """

    chr_start: int
    chr_end: int
    assembly: str
    chromosome: str


def _build_search_term(*, db: str, chromosome: str, start: int, end: int, assembly: str) -> str:
    """Step 1's query text. `execute_get` URL-encodes every parameter; this
    function only ever builds the Entrez TERM VALUE, never the request URL
    or query string, so it carries no injection surface of its own.
    """
    if db == "dbvar":
        # Verified live 2026-08-05 against EInfo's db=dbvar fieldlist: the
        # chromosome tag is CH ("Chr"), not CHR. ASSM ("Assembly") accepts
        # a bare assembly name and matches patched placements too (Entrez
        # text search, not an exact-string filter).
        return f"{chromosome}[CH] AND {start}:{end}[BASE] AND {assembly}[ASSM]"
    if db == "clinvar":
        # Verified live 2026-08-05 against EInfo's db=clinvar fieldlist:
        # the chromosome tag is CHR here (the opposite of dbVar's CH).
        # C37 is GRCh37's position index; CPOS is GRCh38's (the "current"
        # assembly), confirmed against EInfo's field descriptions.
        position_tag = "C37" if assembly == "GRCh37" else "CPOS"
        return f"{chromosome}[CHR] AND {start}:{end}[{position_tag}]"
    # Unreachable: NcbiEfetchCoordinateOverlapInput.db is
    # Literal["dbvar", "clinvar"]. Kept as a fail-closed guard rather than
    # a silent fallthrough, per production-standards.md's allowlist
    # discipline.
    raise ValueError(f"unsupported coordinate_overlap db {db!r}, expected 'dbvar' or 'clinvar'")


def _assembly_matches(placement_assembly: str, requested: str) -> bool:
    """Exact match, or a patch-version match (`GRCh38.p12` matches `GRCh38`).

    See the module docstring's assembly-match section: this is a verified
    fix, not a defensive guess. dbVar mixes bare and patched assembly
    strings within a single record.
    """
    return placement_assembly == requested or placement_assembly.startswith(requested + ".")


def _overlaps(placement: _Placement, start: int, end: int) -> bool:
    """Section 6.2's own predicate, applied here and nowhere else in this module."""
    return placement.chr_start <= end and placement.chr_end >= start


def _dbvar_placements(record: dict[str, Any]) -> list[_Placement]:
    placements: list[_Placement] = []
    for entry in record.get("dbvarplacementlist", None) or []:
        if not isinstance(entry, dict):
            continue
        try:
            placements.append(
                _Placement(
                    chr_start=int(entry["chr_start"]),
                    chr_end=int(entry["chr_end"]),
                    assembly=str(entry.get("assembly", "")),
                    chromosome=str(entry.get("chr", "")),
                )
            )
        except (KeyError, TypeError, ValueError):
            # A placement entry missing a required key, or carrying a
            # non-numeric position, is not a placement this module can
            # reason about. Skip it rather than guess; a candidate whose
            # ONLY placements are malformed this way is dropped by the
            # "no matching placement" path below, which is the correct,
            # honest outcome.
            continue
    return placements


def _clinvar_placements(record: dict[str, Any]) -> list[_Placement]:
    placements: list[_Placement] = []
    for variation in record.get("variation_set", None) or []:
        if not isinstance(variation, dict):
            continue
        for loc in variation.get("variation_loc", None) or []:
            if not isinstance(loc, dict):
                continue
            try:
                placements.append(
                    _Placement(
                        chr_start=int(loc["start"]),
                        chr_end=int(loc["stop"]),
                        assembly=str(loc.get("assembly_name", "")),
                        chromosome=str(loc.get("chr", "")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return placements


def _extract_placements(db: str, record: dict[str, Any]) -> list[_Placement]:
    return _dbvar_placements(record) if db == "dbvar" else _clinvar_placements(record)


def _build_record(
    *, db: str, uid: str, record: dict[str, Any], placement: _Placement, requested_assembly: str
) -> NcbiEfetchRecord | None:
    """Build one output record from a candidate that survived steps 4 and 5.

    Returns None (never raises) on a pydantic ValidationError, so one
    malformed record cannot take down an otherwise-good batch; the
    dropped-record count is only implicit today (fewer records than
    surviving candidates), which is an acceptable gap for a case that has
    never yet occurred against live data in verification.
    """
    if db == "dbvar":
        accession = str(record.get("sv") or record.get("st") or uid)
        gene_names = [
            g.get("name")
            for g in (record.get("dbvargenelist", None) or [])
            if isinstance(g, dict) and g.get("name")
        ]
        fields: dict[str, Any] = {
            "chr": placement.chromosome,
            "chr_start": placement.chr_start,
            "chr_end": placement.chr_end,
            "assembly": placement.assembly,
            "requested_assembly": requested_assembly,
            "variant_type": record.get("dbvarvarianttypelist"),
            "gene_name": gene_names or None,
        }
        source_url = _DBVAR_SOURCE_URL.format(accession=accession)
        record_id = accession
    else:
        accession = str(record.get("accession") or uid)
        classification = record.get("germline_classification")
        gene_symbols = [
            g.get("symbol")
            for g in (record.get("genes", None) or [])
            if isinstance(g, dict) and g.get("symbol")
        ]
        fields = {
            "chr": placement.chromosome,
            "chr_start": placement.chr_start,
            "chr_end": placement.chr_end,
            "assembly": placement.assembly,
            "requested_assembly": requested_assembly,
            "title": record.get("title"),
            "germline_classification": (
                classification.get("description") if isinstance(classification, dict) else None
            ),
            "gene_symbol": gene_symbols or None,
        }
        source_url = _CLINVAR_SOURCE_URL.format(uid=uid)
        record_id = accession

    fields = {key: value for key, value in fields.items() if value is not None}

    try:
        return NcbiEfetchRecord(id=record_id, db=db, fields=fields, source_url=source_url)
    except pydantic.ValidationError as exc:
        logger.warning(
            "coordinate_overlap: dropping candidate %s (db=%s) that failed output "
            "validation: %s",
            uid,
            db,
            exc,
        )
        return None


def _error_output(message: str, *, total_available: int | None = None) -> NcbiEfetchOutput:
    return NcbiEfetchOutput(
        status="error",
        action="coordinate_overlap",
        records=[],
        record_count=0,
        total_available=total_available,
        truncated=False,
        error=message[:500],
    )


def _empty_output(*, total_available: int = 0) -> NcbiEfetchOutput:
    return NcbiEfetchOutput(
        status="empty",
        action="coordinate_overlap",
        records=[],
        record_count=0,
        total_available=total_available,
        truncated=False,
    )


async def coordinate_overlap(
    input_model: NcbiEfetchCoordinateOverlapInput,
    *,
    client: httpx.AsyncClient | None = None,
    max_candidates: int = _DEFAULT_MAX_CANDIDATES,
    wait_ceiling_s: float | None = None,
) -> NcbiEfetchOutput:
    """Run the five-step dbVar/ClinVar coordinate-overlap procedure.

    `client` and `wait_ceiling_s` exist for the same reasons they exist on
    `ncbi_transport.execute_get`: `client` lets a unit test substitute a
    fake HTTP client with no live network, and `wait_ceiling_s` lets the
    Act step pass a per-query-class fail-fast budget instead of one
    constant serving every query class (`tool-call-budgets.md`).
    `max_candidates` is this action's own knob, not one Section 6.2 names,
    covering the ticket's "cap the number of candidates you will
    place-check, and if you truncate, SAY SO" instruction; both the
    ESearch page size and the single batched ESummary call size are capped
    by it.
    """
    db = input_model.db
    chromosome = input_model.chromosome
    start = input_model.start
    end = input_model.end
    assembly = input_model.assembly

    term = _build_search_term(db=db, chromosome=chromosome, start=start, end=end, assembly=assembly)

    try:
        search_response = await execute_get(
            _ESEARCH_URL,
            {"db": db, "term": term, "retmode": "json", "retmax": max_candidates},
            family="eutils",
            include_api_key=True,
            client=client,
            wait_ceiling_s=wait_ceiling_s,
        )
    except TransportRateLimitedError as exc:
        return _error_output(
            f"coordinate_overlap ESearch prefilter for {db} chr{chromosome}:{start}-{end} "
            f"was rate limited on the {exc.family} pool, retry after "
            f"{exc.retry_after:.1f}s or with a narrower window"
        )
    except (TransportTimeoutError, TransportConnectionError) as exc:
        return _error_output(
            f"coordinate_overlap ESearch prefilter for {db} chr{chromosome}:{start}-{end} "
            f"failed: {exc}. Retry with a narrower window or fewer candidates."
        )

    search_result = classify_eutils_response(
        content_type=search_response.headers.get("content-type", ""),
        text=search_response.text,
    )

    if search_result.status == "error":
        return _error_output(
            f"coordinate_overlap ESearch prefilter for {db} chr{chromosome}:{start}-{end} "
            f"returned an error: {search_result.error_message}. Verify the chromosome "
            f"name and coordinate window and retry."
        )
    if search_result.status == "empty":
        return _empty_output(total_available=0)

    body = search_result.body if isinstance(search_result.body, dict) else {}
    esearch_result = body.get("esearchresult", {}) if isinstance(body, dict) else {}
    candidate_ids = [str(cid) for cid in (esearch_result.get("idlist", None) or [])]

    try:
        total_available = int(esearch_result.get("count", len(candidate_ids)))
    except (TypeError, ValueError):
        total_available = len(candidate_ids)

    if not candidate_ids:
        return _empty_output(total_available=total_available)

    truncated = total_available > len(candidate_ids)

    try:
        summary_response = await execute_get(
            _ESUMMARY_URL,
            {"db": db, "id": ",".join(candidate_ids), "retmode": "json"},
            family="eutils",
            include_api_key=True,
            client=client,
            wait_ceiling_s=wait_ceiling_s,
        )
    except TransportRateLimitedError as exc:
        return _error_output(
            f"coordinate_overlap ESummary placement fetch for {db} was rate limited on "
            f"the {exc.family} pool, retry after {exc.retry_after:.1f}s or with fewer "
            f"candidates",
            total_available=total_available,
        )
    except (TransportTimeoutError, TransportConnectionError) as exc:
        return _error_output(
            f"coordinate_overlap ESummary placement fetch for {db} failed: {exc}. Retry "
            f"with fewer candidates or a narrower window.",
            total_available=total_available,
        )

    summary_result = classify_eutils_response(
        content_type=summary_response.headers.get("content-type", ""),
        text=summary_response.text,
    )

    if summary_result.status == "error":
        return _error_output(
            f"coordinate_overlap ESummary placement fetch for {db} returned an error: "
            f"{summary_result.error_message}. The ESearch prefilter's candidate ids "
            f"could not be resolved to placements.",
            total_available=total_available,
        )

    summary_body = summary_result.body if isinstance(summary_result.body, dict) else {}
    result_envelope = summary_body.get("result", {}) if isinstance(summary_body, dict) else {}
    uids = result_envelope.get("uids", None) or candidate_ids

    records: list[NcbiEfetchRecord] = []
    for uid in uids:
        record = result_envelope.get(uid)
        if not isinstance(record, dict):
            # ESummary silently omitted this candidate (a deleted or
            # merged uid, for example). Never fabricate a placement for
            # it; drop it the same as a genuine predicate failure.
            continue

        placements = _extract_placements(db, record)
        matching = [p for p in placements if _assembly_matches(p.assembly, assembly)]
        if not matching:
            # Step 5: no placement for the requested assembly. Drop,
            # never guess one.
            continue

        overlapping = [p for p in matching if _overlaps(p, start, end)]
        if not overlapping:
            # Steps 4 and 5: a real placement for the requested assembly
            # exists and does not overlap the window. This is the proven
            # bug's exact shape (see the module docstring): the candidate
            # only reached this point because the coarse ESearch prefilter
            # matched a DIFFERENT placement's coordinates. Drop it.
            continue

        built = _build_record(
            db=db, uid=uid, record=record, placement=overlapping[0], requested_assembly=assembly
        )
        if built is not None:
            records.append(built)

    if len(records) > 100:
        # NcbiEfetchOutput.records carries maxLength: 100 (Section 6.2).
        # Never silently drop past that cap; say so.
        records = records[:100]
        truncated = True

    status: Literal["ok", "empty"] = "ok" if records else "empty"
    return NcbiEfetchOutput(
        status=status,
        action="coordinate_overlap",
        records=records,
        record_count=len(records),
        total_available=total_available,
        truncated=truncated,
    )
