"""An in-process function catalogue of every existing action of the seven
tools, shaped like an MCP tool listing (build phase 8.2, card 9,
DECISIONS.md 2026-09-25).

Depends on:
    - system_03_search_agent.tools.cypher_schemas (CypherQueryInput)
    - system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchSearchInput,
      NcbiEfetchFetchInput, NcbiEfetchSummaryInput, NcbiEfetchLinkInput,
      NcbiEfetchCoordinateOverlapInput, NcbiEfetchDatasetReportInput,
      NcbiEfetchPubchemPropertyInput)
    - system_03_search_agent.tools.ncbi_dbsnp_schemas (NcbiDbsnpInput)
    - system_03_search_agent.tools.pubtator_annotate_schemas
      (PubtatorEntityLookupInput, PubtatorAnnotatePublicationsInput)
    - system_03_search_agent.tools.litvar2_lookup_schemas
      (Litvar2VariantSearchInput, Litvar2PublicationsLookupInput)
    - system_03_search_agent.tools.pathogen_detection_schemas
      (PathogenIsolateLookupInput, PathogenClusterSnpNeighborsInput,
      PathogenIsolateSearchInput)
    - system_03_search_agent.tools.clinicaltrials_search_schemas
      (ClinicalTrialsSearchInput)

Reads:
    - Nothing.

Writes:
    - Nothing.

This module changes no tool: it reads each tool's ALREADY-LOCKED Pydantic
input model and generates that model's JSON schema
(`Model.model_json_schema()`), it never redefines a field or a limit. The
seven tools do not share one input shape each: `cypher_query` and
`clinicaltrials_search` are flat, single-shape tools (Section 6.1 and
Section 6.7 name no action discriminator), while `ncbi_efetch`,
`litvar2_lookup`, `pathogen_detection`, and `pubtator_annotate` each carry
a `Literal["<action>"]`-discriminated set of input shapes (see each
schema module's own design decision 1). `ncbi_dbsnp` sits in between: one
flat input model whose `query_type` field selects among three Variation
Services endpoint families, so it is catalogued as one action whose
schema itself carries the `query_type` enum, not three separate actions.

Every action's `timeout_s` and `rate_limit_pool` are read from
`.claude/rules/tool-call-budgets.md`'s per-tool timeout table, copied
here as literal values (that rule's table is the source of truth; this
module restates it, it does not compute it).

Sorted by name and fixed in code, per `.claude/rules/
prompt-cache-discipline.md`: "never reorder the tool array at runtime for
any reason." This catalogue is not itself part of a prompt today, but if
a future decision point's `state` ever includes it, an unstable order
would be exactly the kind of silent prefix-byte change that rule exists
to prevent. Building the discipline in now costs nothing and avoids a
second migration later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from system_03_search_agent.tools.clinicaltrials_search_schemas import (
    ClinicalTrialsSearchInput,
)
from system_03_search_agent.tools.cypher_schemas import CypherQueryInput
from system_03_search_agent.tools.litvar2_lookup_schemas import (
    Litvar2PublicationsLookupInput,
    Litvar2VariantSearchInput,
)
from system_03_search_agent.tools.ncbi_dbsnp_schemas import NcbiDbsnpInput
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchCoordinateOverlapInput,
    NcbiEfetchDatasetReportInput,
    NcbiEfetchFetchInput,
    NcbiEfetchLinkInput,
    NcbiEfetchPubchemPropertyInput,
    NcbiEfetchSearchInput,
    NcbiEfetchSummaryInput,
)
from system_03_search_agent.tools.pathogen_detection_schemas import (
    PathogenClusterSnpNeighborsInput,
    PathogenIsolateLookupInput,
    PathogenIsolateSearchInput,
)
from system_03_search_agent.tools.pubtator_annotate_schemas import (
    PubtatorAnnotatePublicationsInput,
    PubtatorEntityLookupInput,
)


@dataclass(frozen=True)
class ToolAction:
    """One callable action of one tool, MCP-listing shaped.

    `input_schema` is the action's input model's own `model_json_schema()`
    output verbatim: nothing here narrows or widens a field, a length cap,
    or an enum beyond what the tool's own locked schema already declares.
    """

    name: str  # "<tool>.<action>"
    tool: str
    description: str
    input_schema: dict[str, Any]
    timeout_s: float
    rate_limit_pool: str | None


def _entry(name: str, tool: str, description: str, model: type[BaseModel], *, timeout_s: float, rate_limit_pool: str | None) -> ToolAction:
    return ToolAction(
        name=name,
        tool=tool,
        description=description,
        input_schema=model.model_json_schema(),
        timeout_s=timeout_s,
        rate_limit_pool=rate_limit_pool,
    )


# Per-tool timeout and rate-limit pool, copied literally from
# `.claude/rules/tool-call-budgets.md`'s table. One tuple entry per tool,
# reused across that tool's own action rows below so the number is stated
# once per tool rather than repeated per action.
_CYPHER_QUERY_BUDGET = (30.0, "Not rate-limited by NCBI; the graph is not an NCBI API")
_NCBI_EFETCH_BUDGET = (
    15.0,
    "E-utilities: 3 requests/second unauthenticated, 10 requests/second with an API key",
)
_NCBI_DBSNP_BUDGET = (
    15.0,
    (
        "Variation Services: roughly 1 request/second, a separate pool from "
        "E-utilities (up to 30s worst case for one call, since normalization "
        "and the clinical fetch run sequentially)"
    ),
)
_PUBTATOR_BUDGET = (15.0, "No documented rate limit; shared per-query call budget")
_LITVAR2_BUDGET = (15.0, "No documented rate limit; shared per-query call budget")
_PATHOGEN_DETECTION_BUDGET = (
    60.0,
    "Not a request-rate API; bound by bulk FTP transfer time and snapshot pinning",
)
_CLINICALTRIALS_BUDGET = (15.0, "No documented rate limit; provisional throttle of about 5 requests/second")


_ALL_ACTIONS: tuple[ToolAction, ...] = (
    _entry(
        "clinicaltrials_search.search",
        "clinicaltrials_search",
        "Search ClinicalTrials.gov studies by condition, term, or intervention.",
        ClinicalTrialsSearchInput,
        timeout_s=_CLINICALTRIALS_BUDGET[0],
        rate_limit_pool=_CLINICALTRIALS_BUDGET[1],
    ),
    _entry(
        "cypher_query.query",
        "cypher_query",
        "Run one structured, parameterized Cypher query against the read-only knowledge graph.",
        CypherQueryInput,
        timeout_s=_CYPHER_QUERY_BUDGET[0],
        rate_limit_pool=_CYPHER_QUERY_BUDGET[1],
    ),
    _entry(
        "litvar2_lookup.publications_lookup",
        "litvar2_lookup",
        "List publications LitVar2 has linked to a specific variant.",
        Litvar2PublicationsLookupInput,
        timeout_s=_LITVAR2_BUDGET[0],
        rate_limit_pool=_LITVAR2_BUDGET[1],
    ),
    _entry(
        "litvar2_lookup.variant_search",
        "litvar2_lookup",
        "Search LitVar2 for variants matching a gene, rsid, or free-text query.",
        Litvar2VariantSearchInput,
        timeout_s=_LITVAR2_BUDGET[0],
        rate_limit_pool=_LITVAR2_BUDGET[1],
    ),
    _entry(
        "ncbi_dbsnp.query",
        "ncbi_dbsnp",
        "Look up a variant in dbSNP by rsid, HGVS expression, or SPDI, optionally with clinical significance.",
        NcbiDbsnpInput,
        timeout_s=_NCBI_DBSNP_BUDGET[0],
        rate_limit_pool=_NCBI_DBSNP_BUDGET[1],
    ),
    _entry(
        "ncbi_efetch.coordinate_overlap",
        "ncbi_efetch",
        "Find dbVar or ClinVar records overlapping a genomic coordinate range.",
        NcbiEfetchCoordinateOverlapInput,
        timeout_s=_NCBI_EFETCH_BUDGET[0],
        rate_limit_pool=_NCBI_EFETCH_BUDGET[1],
    ),
    _entry(
        "ncbi_efetch.dataset_report",
        "ncbi_efetch",
        "Fetch an NCBI Datasets API v2 gene or genome report.",
        NcbiEfetchDatasetReportInput,
        timeout_s=_NCBI_EFETCH_BUDGET[0],
        rate_limit_pool=_NCBI_EFETCH_BUDGET[1],
    ),
    _entry(
        "ncbi_efetch.fetch",
        "ncbi_efetch",
        "Fetch one or more NCBI records by id via EFetch.",
        NcbiEfetchFetchInput,
        timeout_s=_NCBI_EFETCH_BUDGET[0],
        rate_limit_pool=_NCBI_EFETCH_BUDGET[1],
    ),
    _entry(
        "ncbi_efetch.link",
        "ncbi_efetch",
        "Find related records across NCBI databases via ELink.",
        NcbiEfetchLinkInput,
        timeout_s=_NCBI_EFETCH_BUDGET[0],
        rate_limit_pool=_NCBI_EFETCH_BUDGET[1],
    ),
    _entry(
        "ncbi_efetch.pubchem_property",
        "ncbi_efetch",
        "Fetch a PubChem compound property by CID or name.",
        NcbiEfetchPubchemPropertyInput,
        timeout_s=_NCBI_EFETCH_BUDGET[0],
        rate_limit_pool=_NCBI_EFETCH_BUDGET[1],
    ),
    _entry(
        "ncbi_efetch.search",
        "ncbi_efetch",
        "Search an NCBI database via ESearch and return matching ids.",
        NcbiEfetchSearchInput,
        timeout_s=_NCBI_EFETCH_BUDGET[0],
        rate_limit_pool=_NCBI_EFETCH_BUDGET[1],
    ),
    _entry(
        "ncbi_efetch.summary",
        "ncbi_efetch",
        "Fetch document summaries for NCBI record ids via ESummary.",
        NcbiEfetchSummaryInput,
        timeout_s=_NCBI_EFETCH_BUDGET[0],
        rate_limit_pool=_NCBI_EFETCH_BUDGET[1],
    ),
    _entry(
        "pathogen_detection.cluster_snp_neighbors",
        "pathogen_detection",
        "List the SNP-distance neighbors of a pathogen cluster.",
        PathogenClusterSnpNeighborsInput,
        timeout_s=_PATHOGEN_DETECTION_BUDGET[0],
        rate_limit_pool=_PATHOGEN_DETECTION_BUDGET[1],
    ),
    _entry(
        "pathogen_detection.isolate_lookup",
        "pathogen_detection",
        "Look up one pathogen isolate by its accession or biosample id.",
        PathogenIsolateLookupInput,
        timeout_s=_PATHOGEN_DETECTION_BUDGET[0],
        rate_limit_pool=_PATHOGEN_DETECTION_BUDGET[1],
    ),
    _entry(
        "pathogen_detection.isolate_search",
        "pathogen_detection",
        "Search pathogen isolates by organism, location, or other metadata.",
        PathogenIsolateSearchInput,
        timeout_s=_PATHOGEN_DETECTION_BUDGET[0],
        rate_limit_pool=_PATHOGEN_DETECTION_BUDGET[1],
    ),
    _entry(
        "pubtator_annotate.annotate_publications",
        "pubtator_annotate",
        "Annotate one or more publications' text with PubTator3's recognized entities.",
        PubtatorAnnotatePublicationsInput,
        timeout_s=_PUBTATOR_BUDGET[0],
        rate_limit_pool=_PUBTATOR_BUDGET[1],
    ),
    _entry(
        "pubtator_annotate.entity_lookup",
        "pubtator_annotate",
        "Look up a normalized biomedical entity id in PubTator3.",
        PubtatorEntityLookupInput,
        timeout_s=_PUBTATOR_BUDGET[0],
        rate_limit_pool=_PUBTATOR_BUDGET[1],
    ),
)

# Sorted by name, fixed at import time. Never reordered at runtime (see
# module docstring).
CATALOGUE: tuple[ToolAction, ...] = tuple(sorted(_ALL_ACTIONS, key=lambda action: action.name))

_TOOL_NAMES: tuple[str, ...] = tuple(sorted({action.tool for action in CATALOGUE}))


def get_catalogue() -> tuple[ToolAction, ...]:
    """Return the fixed, sorted tool-action catalogue."""
    return CATALOGUE


def resource_options() -> tuple[str, ...]:
    """The closed option list for the `"plan.resource"` decision point.

    Returns the seven tool names (never the finer-grained action names,
    which would exceed `DecisionRecord.options`'s `max_length=12` bound at
    seventeen entries), sorted and fixed, matching this module's own
    never-reorder-at-runtime discipline.
    """
    return _TOOL_NAMES
