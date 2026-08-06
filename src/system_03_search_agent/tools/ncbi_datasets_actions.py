"""The `dataset_report` action of `ncbi_efetch`: NCBI Datasets API v2 (T-3.1-08).

Technical_specification.md Section 6.2, the `dataset_report` branch. Covers
all three documented endpoints under `https://api.ncbi.nlm.nih.gov/datasets/v2/`:

    GET gene/id/{gene_id}
    GET gene/symbol/{symbol}/taxon/{taxon}
    GET genome/accession/{accession}/dataset_report

Which endpoint gets called is selected by which optional field the validated
`NcbiEfetchDatasetReportInput` carries, never guessed from a partial input.
An incoherent combination (for example `report_type: "gene"` with only an
`accession`) returns an actionable `status: "error"` with no network call.

## The defining constraint: status-coded, not body-coded

Datasets v2 returns proper HTTP status codes, the opposite convention from
E-utilities. This module classifies exclusively with
`ncbi_transport.classify_status_coded_response`, never
`classify_eutils_response`; the two classifiers have deliberately
incompatible signatures (`ncbi_transport`'s module docstring) so a mix-up
raises `TypeError` at the call site rather than silently reading the wrong
signal. See `docs/ncbi/Tool_implementation_mechanics.md:117-122`.

## What "ok" from the classifier does NOT mean here

`classify_status_coded_response` decides `ok` vs `error` from HTTP status
alone and explicitly does not distinguish `ok` from `empty`: a 2xx body
that logically contains zero records is still `"ok"` from the classifier's
point of view. Collapsing that into this tool's `"empty"` output status is
this module's job, and it is the load-bearing case here (see the bad-symbol
finding below).

## Live-verified ground truth, 2026-08-04/08-05

    GET gene/symbol/TP53/taxon/human         -> 200, gene_id "7157",
                                                 taxname "Homo sapiens"
    GET gene/id/7157                         -> 200, {"reports":[{"gene":
                                                 {...}}]}
    GET genome/accession/GCF_000001405.40
        /dataset_report                      -> 200, {"reports":[{...}]}
        (fields directly on the report, no "genome" wrapper, unlike the gene
        endpoint's {"gene": {...}} wrapper)

    A malformed gene_id (numeric garbage OR a non-numeric string) -> 400,
    {"error": "Bad Request", "code": 400, "message": "Invalid argument
    type ('parameter: gene_ids') provided. ..."}. This is the ONE path that
    actually returns the {"error","code","message"} shape the ticket's
    ground truth names.

FINDING (probed live 2026-08-05, both a bad gene SYMBOL and a bad genome
ACCESSION): Datasets v2 does NOT return a 4xx for an unmatched symbol or
accession. It returns HTTP 200 with an EMPTY body, literally `{}`, no
"reports" key at all:

    GET gene/symbol/notarealgenesymbolxyzzy/taxon/human -> 200, {}
    GET genome/accession/GCF_00000000X/dataset_report    -> 200, {}

So Datasets v2 has TWO different not-found conventions depending on which
argument was wrong: a malformed identifier TYPE (bad gene_id shape) is a
proper 400 error, but an identifier that is well-formed but does not MATCH
anything (bad symbol, bad accession) is a 200-with-empty-body, which this
module must collapse to this tool's `"empty"` status, not `"ok"`, and
never to `"error"` (nothing broke; nothing matched). This is exactly the
`classify_status_coded_response` docstring's warned-about gap: "a 2xx body
that logically contains zero records is still ok here", and it is this
module's job to close it. The premise gate's case 10 accepts `status in
{"error", "empty"}` for this reason, and this implementation produces
`"empty"`, observed 2026-08-05 against the live endpoint, not `"error"`.

## The extracted field set is a bounded allowlist, not the raw payload

The real Datasets v2 gene and genome payloads carry far more than Section
6.2's documented field list (nomenclature authorities, bioproject lineage,
free-text assembly diff narratives, reference-standard genomic ranges).
Only the fields Section 6.2 line 959 names are copied into the output
record's `fields`, everything else is dropped. This is the multi-agent
pipeline gate's "bounded context items" requirement applied at the source:
an unbounded upstream payload must not flow downstream unchecked, and
`NcbiEfetchRecord.fields`'s own `maxProperties: 40` cap
(`ncbi_efetch_schemas.py`) is the second, schema-level backstop, not the
only one.

## source_url: gene and genome both resolve, both stay inside the fetch host

Unlike `pubchem_property` (see `ncbi_pubchem_actions.py`'s module
docstring), both Datasets v2 record pages this module cites live under
`ncbi.nlm.nih.gov`, so `NCBI_EFETCH_RECORD_URL_PATTERN` accepts both
without conflict:

    gene   -> https://www.ncbi.nlm.nih.gov/gene/{gene_id}/
    genome -> https://www.ncbi.nlm.nih.gov/datasets/genome/{accession}/

Both verified live 2026-08-05 (HTTP 200, a real page, not a 404 shell).

Depends on:
    - system_03_search_agent.tools.ncbi_transport (execute_get,
      classify_status_coded_response)
    - system_03_search_agent.tools.ncbi_efetch_schemas
      (NcbiEfetchDatasetReportInput, NcbiEfetchOutput, NcbiEfetchRecord,
      NCBI_EFETCH_RECORD_URL_PATTERN)
    - httpx (pinned in pyproject.toml, >=0.27), for the optional test-only
      `client` injection point

Reads:
    - Nothing at import time. NCBI_API_KEY is not used: Datasets v2 needs
      no key (Section 6.2, "Rate limits").

Writes:
    - Nothing. Outbound HTTPS requests only.

Depended by:
    - system_03_search_agent.tools.ncbi_efetch (the dispatcher, not yet
      written; T-3.1-06/07 or later)
"""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from typing import Any, Final

import httpx

from system_03_search_agent.tools import ncbi_transport
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchDatasetReportInput,
    NcbiEfetchOutput,
    NcbiEfetchRecord,
)

_DATASETS_BASE: Final[str] = "https://api.ncbi.nlm.nih.gov/datasets/v2/"

# Section 6.2 line 959, gene report. Only these keys leave the raw upstream
# payload; see the module docstring's "bounded allowlist" section.
_GENE_REPORT_FIELDS: Final[tuple[str, ...]] = (
    "gene_id",
    "symbol",
    "description",
    "taxname",
    "tax_id",
    "omim_ids",
    "ensembl_gene_ids",
    "swiss_prot_accessions",
    "chromosomes",
    "map_locations",
    "gene_ontology",
    "synonyms",
)

# Section 6.2 line 959, genome report. `assembly_info.assembly_level` and
# `assembly_info.assembly_name` are flattened to those exact dotted keys,
# matching the spec's own naming, rather than nesting `assembly_info` whole.
_GENOME_REPORT_TOP_LEVEL_FIELDS: Final[tuple[str, ...]] = (
    "accession",
    "current_accession",
    "paired_accession",
    "assembly_stats",
)


def _quote_path_segment(value: str) -> str:
    """URL-encode one path segment. Never a raw f-string interpolation.

    Per production-standards.md's query-safety gate: `symbol`, `taxon`, and
    `accession` are caller-supplied and land in the URL PATH here, not a
    query string, so `urllib.parse.quote(value, safe="")` (no safe
    characters at all) is stricter than `ncbi_transport._build_query_string`'s
    `safe=":/=?&|+"`, which is calibrated for query-string values. A path
    segment must not carry an unencoded `/`, since that would silently
    insert an extra path component.
    """
    return urllib.parse.quote(value, safe="")


def _select_endpoint(action_input: NcbiEfetchDatasetReportInput) -> tuple[str | None, str | None]:
    """Choose the one Datasets v2 endpoint this request maps to, or an error.

    Returns `(url, None)` on a coherent request, or `(None, message)` on an
    incoherent one. Never guesses: `report_type` plus exactly the fields
    that endpoint needs must be present, per the ticket's instruction not to
    infer an endpoint from a partial input.
    """
    if action_input.report_type == "gene":
        if action_input.gene_id:
            return (
                _DATASETS_BASE + "gene/id/" + _quote_path_segment(action_input.gene_id),
                None,
            )
        if action_input.symbol and action_input.taxon:
            return (
                _DATASETS_BASE
                + "gene/symbol/"
                + _quote_path_segment(action_input.symbol)
                + "/taxon/"
                + _quote_path_segment(action_input.taxon),
                None,
            )
        return None, (
            "dataset_report with report_type='gene' needs either gene_id, "
            "or both symbol and taxon together; retry with one of those "
            "combinations"
        )

    # report_type == "genome" (the schema's only other Literal value).
    if action_input.accession:
        return (
            _DATASETS_BASE
            + "genome/accession/"
            + _quote_path_segment(action_input.accession)
            + "/dataset_report",
            None,
        )
    return None, (
        "dataset_report with report_type='genome' needs accession; retry "
        "with an accession"
    )


def _extract_gene_fields(gene_obj: Mapping[str, Any]) -> dict[str, Any]:
    return {key: gene_obj[key] for key in _GENE_REPORT_FIELDS if key in gene_obj}


def _extract_genome_fields(report: Mapping[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        key: report[key] for key in _GENOME_REPORT_TOP_LEVEL_FIELDS if key in report
    }
    assembly_info = report.get("assembly_info")
    if isinstance(assembly_info, dict):
        if "assembly_level" in assembly_info:
            fields["assembly_info.assembly_level"] = assembly_info["assembly_level"]
        if "assembly_name" in assembly_info:
            fields["assembly_info.assembly_name"] = assembly_info["assembly_name"]
    return fields


def _gene_source_url(gene_id: Any) -> str | None:
    if not gene_id:
        return None
    return "https://www.ncbi.nlm.nih.gov/gene/" + _quote_path_segment(str(gene_id)) + "/"


def _genome_source_url(accession: Any) -> str | None:
    if not accession:
        return None
    return (
        "https://www.ncbi.nlm.nih.gov/datasets/genome/"
        + _quote_path_segment(str(accession))
        + "/"
    )


def _error_output(message: str) -> NcbiEfetchOutput:
    return NcbiEfetchOutput(
        status="error",
        action="dataset_report",
        records=[],
        record_count=0,
        truncated=False,
        error=message,
    )


def _empty_output() -> NcbiEfetchOutput:
    return NcbiEfetchOutput(
        status="empty",
        action="dataset_report",
        records=[],
        record_count=0,
        truncated=False,
    )


async def dataset_report(
    action_input: NcbiEfetchDatasetReportInput,
    *,
    client: httpx.AsyncClient | None = None,
) -> NcbiEfetchOutput:
    """Execute the `dataset_report` action: NCBI Datasets API v2.

    Selects one of the three documented endpoints from `action_input`'s
    populated fields, classifies the response by HTTP status
    (`classify_status_coded_response`, never the body), then collapses a
    2xx-but-empty body to this tool's `"empty"` status. See the module
    docstring's live-verified finding: a bad symbol or accession is a 200
    with `{}`, not a 4xx, and only a malformed identifier TYPE is a genuine
    400.
    """
    url, incoherent_message = _select_endpoint(action_input)
    if url is None:
        assert incoherent_message is not None
        return _error_output(incoherent_message)

    response = await ncbi_transport.execute_get(
        url, {}, family="datasets", client=client
    )
    result = ncbi_transport.classify_status_coded_response(
        http_status=response.status_code, text=response.text
    )

    if result.status == "error":
        return _error_output(
            result.error_message or "Datasets v2 request failed with no structured error body"
        )

    body = result.body
    if not isinstance(body, dict):
        # Fail closed on an unparseable or non-object 2xx body, the same
        # allowlist discipline ncbi_transport's E-utilities classifier
        # already applies: an unrecognized shape is never a silent "ok".
        return _error_output(
            "Datasets v2 returned a 2xx response with an unparseable or "
            "non-object body, refusing to guess its meaning"
        )

    reports = body.get("reports")
    if reports is None:
        # Finding 9 (MAJOR, re-review): before this fix, ANY 2xx dict
        # lacking a `reports` key collapsed to `_empty_output()`, so a
        # renamed key, a proxy or error page that happens to be valid
        # JSON, or an undocumented API contract change was
        # indistinguishable from "nothing matched" and reported to the
        # user as a clean no-result answer. The only live-verified
        # not-found shape (module docstring's FINDING section) is a
        # LITERAL EMPTY BODY, `{}`, no keys at all. Allowlist exactly
        # that; anything else 2xx-but-keyless-of-reports is unrecognized
        # and fails closed as `error` rather than silently as `empty`.
        if not body:
            return _empty_output()
        return _error_output(
            "Datasets v2 returned a 2xx response with no 'reports' key and a "
            f"non-empty body ({sorted(body.keys())!r}). The only live-verified "
            "not-found shape is a literal empty body; this does not match it "
            "and may mean the API contract changed. Refusing to report this "
            "as \"no results\"; retry, and if this recurs, this module's "
            "not-found detection needs updating."
        )
    if not isinstance(reports, list):
        return _error_output(
            f"Datasets v2 returned a 2xx response whose 'reports' field is a "
            f"{type(reports).__name__}, not a list. This does not match any "
            "live-verified shape; refusing to guess its meaning."
        )
    if not reports:
        # The documented empty-list shape (`{"reports": []}`): a
        # confirmed, well-formed zero-match answer, distinct from the
        # unrecognized-shape case above.
        return _empty_output()

    records: list[NcbiEfetchRecord] = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        if action_input.report_type == "gene":
            gene_obj = report.get("gene")
            if not isinstance(gene_obj, dict):
                continue
            fields = _extract_gene_fields(gene_obj)
            records.append(
                NcbiEfetchRecord(
                    id=str(fields["gene_id"]) if fields.get("gene_id") else None,
                    db="gene",
                    fields=fields,
                    source_url=_gene_source_url(fields.get("gene_id")),
                )
            )
        else:
            fields = _extract_genome_fields(report)
            records.append(
                NcbiEfetchRecord(
                    id=str(fields["accession"]) if fields.get("accession") else None,
                    db="genome",
                    fields=fields,
                    source_url=_genome_source_url(fields.get("accession")),
                )
            )

    if not records:
        return _empty_output()

    truncated = len(records) > 100
    bounded_records = records[:100]
    return NcbiEfetchOutput(
        status="ok",
        action="dataset_report",
        records=bounded_records,
        record_count=len(bounded_records),
        total_available=len(records) if truncated else None,
        truncated=truncated,
    )
