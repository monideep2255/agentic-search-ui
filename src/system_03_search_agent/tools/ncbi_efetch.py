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
