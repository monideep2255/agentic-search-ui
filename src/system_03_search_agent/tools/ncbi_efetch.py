"""ncbi_efetch: the dispatcher for build phase 3.1's Layer 2 tool
(T-3.1-12, dispatcher half).

This module is deliberately thin. Every action's real work, EInfo field
validation, ESearch/ESummary/EFetch/ELink body-versus-status
classification, the dbVar/ClinVar coordinate-overlap procedure, and the
Datasets v2 and PubChem status-branching, already lives in six sibling
modules (`ncbi_eutils_actions`, `ncbi_coordinate_overlap`,
`ncbi_datasets_actions`, `ncbi_pubchem_actions`, plus the transport and
schema modules those import). This file's only job is to route a
validated `NcbiEfetchInput` to the right one of those six functions by
its `action` discriminator, and to guarantee that nothing it calls can
raise past this boundary.

Signature note (DECISIONS.md, 2026-08-05): `ncbi_efetch(tool_input)`
takes no `harness` parameter, unlike `cypher_query(harness, tool_input)`.
This tool makes no model call; it is a deterministic HTTP client across
three API families, carries its own per-call timeout internally
(Section 6.2). This tool carries its own per-call timeout internally via
`ncbi_transport.execute_get`, and the Act step does not currently dispatch
this tool (F-3.1-04, the answer-path premise gap). Adding an unused
`harness` parameter to match
`cypher_query`'s shape would be cargo-culting a dependency this tool does
not have.

Never raises. Every sub-module already catches its own
`ncbi_transport.TransportError` and returns a classified `status: "error"`
`NcbiEfetchOutput` (see each sibling module's own docstring). This
dispatcher adds one more layer under that: an unexpected exception from a
sub-module, one that is not a `TransportError` and therefore not a bug
class those modules already handle, for example a `KeyError` or
`AttributeError` surfacing a genuine defect, is caught here and turned
into the same `status: "error"` shape with an actionable message, per
`.claude/rules/production-standards.md`'s retry-safety gate: an error
message must say what to do next, not just what failed. This mirrors
`cypher_query.py`'s own outer boundary (`cypher_query`'s `try`/`except
TimeoutError` around `_run_pipeline`), just for an unexpected exception
class rather than a timeout, since this tool's own sub-modules already
own their per-call timeout and retry.

Depends on:
    - system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchInput,
      NcbiEfetchOutput)
    - system_03_search_agent.tools.ncbi_eutils_actions (search, summary,
      fetch, link)
    - system_03_search_agent.tools.ncbi_coordinate_overlap
      (coordinate_overlap)
    - system_03_search_agent.tools.ncbi_datasets_actions (dataset_report)
    - system_03_search_agent.tools.ncbi_pubchem_actions (pubchem_property)

Reads:
    - Nothing directly. Each sub-module reads its own environment
      variables (`NCBI_API_KEY`, the per-family rate-limit overrides) via
      `ncbi_transport.py`; this dispatcher has no environment surface of
      its own.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.core.graph (the Act step's tool dispatch,
      not yet wired to this tool; a separate builder's T-3.1-12 half)
    - tests/system_03_search_agent/tools/test_ncbi_efetch_premise.py, via
      its `_run` helper, which imports `ncbi_efetch` from this module by
      name
"""

from __future__ import annotations

import hashlib
from typing import Any

from system_03_search_agent.contracts.events import CitationPayload
from system_03_search_agent.synthesis.provenance_defaults import (
    clinvar_term_confidence,
    defaults_for_tool,
)
from system_03_search_agent.tools.ncbi_coordinate_overlap import coordinate_overlap
from system_03_search_agent.tools.ncbi_datasets_actions import dataset_report
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchInput,
    NcbiEfetchOutput,
)
from system_03_search_agent.tools.ncbi_eutils_actions import fetch, link, search, summary
from system_03_search_agent.tools.ncbi_pubchem_actions import pubchem_property

_MAX_ERROR_CHARS = 500
_MAX_ACTION_CHARS = 20

# T-3.4-04: a logical/semantic field name a caller cites (e.g. "official_
# symbol", the name `core/graph.py` already uses for this exact concept at
# line 1201) does not always match the raw dict key a given action's
# `NcbiEfetchRecord.fields` actually carries (`_extract_gene_fields` in
# `ncbi_datasets_actions.py` names it "symbol"). This alias table bridges
# the two without renaming either side: the raw key stays what the action
# module already produces, the logical name stays what a caller (this
# ticket's own premise gate, `core/graph.py`) already uses.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "official_symbol": ("symbol",),
    # coordinate_overlap's ClinVar branch (ncbi_coordinate_overlap.py) names
    # its ClinVar-vocabulary field "germline_classification", never
    # "clinical_significance"; both logical names resolve to it here.
    "clinical_significance": ("germline_classification", "clinical_significance"),
}

# Raw `fields` keys whose value is itself a ClinVar clinical_significance-
# shaped vocabulary term, per T-3.4-04's own instruction: "asserted" is the
# default for this tool's structured, non-clinical-vocabulary fields,
# UNLESS the cited field is itself one of these.
_CLINVAR_SHAPED_RAW_FIELDS = frozenset({"clinical_significance", "germline_classification"})


def _resolve_citable_field(
    fields: dict[str, Any], field: str
) -> tuple[str, Any] | None:
    """Find `field`'s real value in a record's `fields` dict, by alias if needed.

    Returns `(raw_key, value)` for the first candidate (the logical name
    itself, then its known aliases in `_FIELD_ALIASES`) that is present and
    non-empty, or `None` when no candidate resolves. Never fabricates a
    value: a `field` this record's `fields` dict genuinely has nothing for
    resolves to `None`, for the caller to refuse on, not to a guessed
    substitute.
    """
    candidates = (field, *_FIELD_ALIASES.get(field, ()))
    for candidate in candidates:
        value = fields.get(candidate)
        if value not in (None, "", []):
            return candidate, value
    return None


def _mint_citation_id(prefix: str, seed: str, display_index: int) -> str:
    """A short, deterministic-shaped citation id, mirroring `core/graph.py`'s
    `_citation_for_row` pattern (a stable id plus a display-index suffix),
    adapted for a tool with no `call_id` of its own: the id is minted from a
    short hash of the real source id instead. Only needs to be non-colliding
    within one tool's own output, not globally unique across a whole answer.
    """
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:10]
    return f"{prefix}-{digest}-{display_index}"[:64]


def build_layer2_citation(
    result: NcbiEfetchOutput, field: str, display_index: int = 1
) -> CitationPayload:
    """Build a Section 9.2 `CitationPayload` from a real `ncbi_efetch` result.

    `field` is the logical field name being cited (e.g. `"official_symbol"`,
    `"clinical_significance"`), resolved against the cited record's real
    `fields` dict via `_resolve_citable_field`, never fabricated. Raises
    `ValueError` with an actionable message, never returns a placeholder or
    a partially-fabricated citation, when the result carries no record with
    both a `source_url` and a resolvable value for `field`: per production-
    standards.md's cite-or-refuse gate, an uncitable result has nothing this
    function may honestly build a citation from.

    `evidence_kind` and `license` come from
    `provenance_defaults.defaults_for_tool("ncbi_efetch")`, never
    hardcoded here a second time. `assertion_confidence` defaults to
    `"asserted"` for this tool's structured, non-clinical-vocabulary fields
    (gene reports, PubChem properties, dbVar/ClinVar coordinate overlaps),
    EXCEPT when the resolved raw field is itself a ClinVar
    `clinical_significance`-shaped value (`_CLINVAR_SHAPED_RAW_FIELDS`,
    reachable via `coordinate_overlap`'s ClinVar branch), in which case
    `clinvar_term_confidence` decides it instead.
    `population_ancestry_context` is always `None`: this tool has no
    population or ancestry field to honestly report one from.
    """
    citable_record = next((record for record in result.records if record.source_url), None)
    if citable_record is None:
        raise ValueError(
            "ncbi_efetch result carries no record with a source_url; refusing to "
            "build a citation rather than fabricate one. Retry with an action/"
            "input that returns a citable record."
        )
    resolved = _resolve_citable_field(citable_record.fields, field)
    if resolved is None:
        raise ValueError(
            f"ncbi_efetch record {citable_record.id!r} has no real value for "
            f"logical field {field!r} (or its known aliases); available fields: "
            f"{sorted(citable_record.fields)}. Refusing to fabricate a citation "
            "for a field this record does not carry."
        )
    raw_key, value = resolved

    defaults = defaults_for_tool("ncbi_efetch")
    confidence = (
        clinvar_term_confidence(str(value))
        if raw_key in _CLINVAR_SHAPED_RAW_FIELDS
        else "asserted"
    )

    source = (citable_record.db or "ncbi_efetch")[:128]
    source_id = (citable_record.id or "unknown")[:128]
    claim_text = f"{source} {source_id}: {field}={value}"[:1000]

    return CitationPayload(
        citation_id=_mint_citation_id("ncbief", source_id, display_index),
        display_index=display_index,
        source=source,
        source_id=source_id,
        source_url=citable_record.source_url,
        layer="layer_2_api",
        field=field[:128],
        claim_text=claim_text,
        evidence_kind=defaults["evidence_kind"],
        assertion_confidence=confidence,
        population_ancestry_context=None,
        license=defaults["license"],
    )


def _error_output(action: str, message: str) -> NcbiEfetchOutput:
    """Build a `status: "error"` output with an actionable message.

    Same shape `cypher_query.py`'s own `_error_output` builds: `records`
    empty, `total_available` unknown, never truncated, the message capped
    to the schema's own `error` field length so a pathological exception
    string cannot itself violate `NcbiEfetchOutput`'s `max_length`.
    """
    return NcbiEfetchOutput(
        status="error",
        action=action[:_MAX_ACTION_CHARS],
        records=[],
        record_count=0,
        total_available=None,
        truncated=False,
        error=message[:_MAX_ERROR_CHARS],
    )


async def ncbi_efetch(tool_input: NcbiEfetchInput) -> NcbiEfetchOutput:
    """Route a validated `NcbiEfetchInput` to its action's implementation.

    `tool_input.root` is the action-specific, already-validated pydantic
    model (`NcbiEfetchSearchInput`, `NcbiEfetchFetchInput`, ...) per
    `ncbi_efetch_schemas`'s own documented `.root` access pattern. The
    `action` field on that model is the dispatch key; it is a closed
    `Literal` in a discriminated union pydantic has already validated, so
    every one of the seven branches below is reachable by construction
    and the trailing branch exists only as a defensive last resort, never
    as evidence that an eighth action is expected.

    Never raises. See the module docstring for the two-layer error
    handling this relies on: each sub-module already classifies its own
    transport failures, and this function's `try`/`except` catches
    whatever an unexpected exception from any of them would otherwise let
    escape.
    """
    action = "unknown"
    try:
        resolved = tool_input.root
        action = resolved.action

        if action == "search":
            return await search(resolved)
        if action == "summary":
            return await summary(resolved)
        if action == "fetch":
            return await fetch(resolved)
        if action == "link":
            return await link(resolved)
        if action == "coordinate_overlap":
            return await coordinate_overlap(resolved)
        if action == "dataset_report":
            return await dataset_report(resolved)
        if action == "pubchem_property":
            return await pubchem_property(resolved)
        # Defensive, not assumed impossible: NcbiEfetchInput's discriminated
        # union is closed to exactly these seven action values today, so
        # pydantic validation would already have rejected anything else
        # before this function ever runs. If a future schema change adds
        # an eighth action without a matching branch here, that is a tool
        # registration gap, and the caller needs to be told to report it
        # rather than retry, not handed a raised, unclassified exception.
        return _error_output(
            action,
            f"ncbi_efetch has no dispatch branch for action {action!r}. "
            "This is a tool registration gap, not a caller error; report "
            "it rather than retrying.",
        )
    except Exception as exc:  # noqa: BLE001 - the dispatcher's deliberate last-resort catch
        return _error_output(
            action,
            f"ncbi_efetch's {action!r} action raised an unexpected "
            f"{type(exc).__name__} instead of returning a classified "
            f"result: {exc}. Retry once; if this recurs, the {action!r} "
            "action module has a defect that needs fixing before this "
            "action can be trusted.",
        )
