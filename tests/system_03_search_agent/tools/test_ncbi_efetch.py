"""Unit tests for `ncbi_efetch`, the dispatcher half of T-3.1-12.

No live network anywhere in this file. Every one of the six sibling
action functions (`search`, `summary`, `fetch`, `link`,
`coordinate_overlap`, `dataset_report`, `pubchem_property`) is monkeypatched
on the module object `ncbi_efetch.py` imported it into, the same pattern
`test_cypher_query.py` already established for `execute_cypher`. Live
coverage of what these functions actually do against the real NCBI
endpoints is `test_ncbi_efetch_premise.py`'s job, not this file's: this
file only proves the dispatcher routes correctly and never lets an
exception escape.

What this file proves, per the ticket's explicit requirements:

    - Each of the 7 actions routes to the correct sub-module function and
      returns its output unchanged (identity-checked, not merely
      equality-checked, so a dispatcher that silently rebuilt the output
      would still be caught).
    - Each sub-module function is called with the resolved, action-specific
      model (`tool_input.root`), never the outer `NcbiEfetchInput` wrapper.
    - An unexpected exception raised by a sub-module (something other than
      the `TransportError` those modules already catch internally) becomes
      `status: "error"`, never propagates, and the error message names the
      action, the exception type, and an actionable next step, not a bare
      "failed".
    - The defensive last-resort branch (an action value with no matching
      dispatch arm) also returns `status: "error"` rather than raising,
      exercised through a duck-typed stub input since `NcbiEfetchInput`'s
      real discriminated union cannot construct an invalid action value.

Depends on:
    - system_03_search_agent.tools.ncbi_efetch (module under test)
    - system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchInput,
      NcbiEfetchOutput, and the seven action input models, to build
      realistic validated inputs)

Writes:
    - Nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

from system_03_search_agent.tools import ncbi_efetch as ncbi_efetch_module
from system_03_search_agent.tools.ncbi_efetch import build_layer2_citation, ncbi_efetch
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchInput,
    NcbiEfetchOutput,
    NcbiEfetchRecord,
)

# ---------------------------------------------------------------------------
# One valid, schema-legal payload per action, shaped exactly like the
# premise gate's own `_call_input` payloads, so a routing bug that only
# shows up on a realistic input is not masked by an artificially minimal one.
# ---------------------------------------------------------------------------

_PAYLOAD_BY_ACTION: dict[str, dict[str, Any]] = {
    "search": {"action": "search", "db": "gene", "term": "TP53[sym] AND human[orgn]"},
    "summary": {"action": "summary", "db": "gene", "ids": ["7157"]},
    "fetch": {
        "action": "fetch",
        "db": "pubmed",
        "ids": ["21376230"],
        "rettype": "abstract",
        "retmode": "xml",
    },
    "link": {"action": "link", "dbfrom": "gene", "db": "pubmed", "ids": ["7157"]},
    "coordinate_overlap": {
        "action": "coordinate_overlap",
        "db": "dbvar",
        "chromosome": "1",
        "start": 1_000_000,
        "end": 1_100_000,
        "assembly": "GRCh38",
    },
    "dataset_report": {
        "action": "dataset_report",
        "report_type": "gene",
        "symbol": "TP53",
        "taxon": "human",
    },
    "pubchem_property": {
        "action": "pubchem_property",
        "lookup_type": "cid",
        "value": "2244",
        "properties": ["MolecularFormula"],
    },
}

# The module-level function name `ncbi_efetch.py` imported for each action,
# so the test can monkeypatch the right symbol on the dispatcher module.
_FUNCTION_NAME_BY_ACTION: dict[str, str] = {
    "search": "search",
    "summary": "summary",
    "fetch": "fetch",
    "link": "link",
    "coordinate_overlap": "coordinate_overlap",
    "dataset_report": "dataset_report",
    "pubchem_property": "pubchem_property",
}


def _fake_output(action: str) -> NcbiEfetchOutput:
    """A distinctive, valid output for `action`, used to prove identity."""
    return NcbiEfetchOutput(
        status="ok",
        action=action,
        records=[],
        record_count=0,
        total_available=0,
        truncated=False,
        error=None,
    )


# ---------------------------------------------------------------------------
# Routing: each of the 7 actions reaches the right sub-module and the
# output comes back unchanged.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("action", sorted(_PAYLOAD_BY_ACTION))
async def test_each_action_routes_to_its_own_sub_module_and_returns_output_unchanged(
    action: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _PAYLOAD_BY_ACTION[action]
    tool_input = NcbiEfetchInput.model_validate(payload)
    expected_resolved = tool_input.root
    sentinel_output = _fake_output(action)

    calls: list[Any] = []

    async def _fake_action(resolved: Any, *args: Any, **kwargs: Any) -> NcbiEfetchOutput:
        calls.append(resolved)
        return sentinel_output

    monkeypatch.setattr(ncbi_efetch_module, _FUNCTION_NAME_BY_ACTION[action], _fake_action)

    result = await ncbi_efetch(tool_input)

    assert result is sentinel_output, (
        f"the {action!r} route must return the sub-module's output object "
        f"unchanged, not a rebuilt copy"
    )
    assert len(calls) == 1, f"expected exactly one call to the {action!r} sub-module"
    assert calls[0] is expected_resolved, (
        f"the {action!r} sub-module must be called with tool_input.root, "
        f"the resolved action-specific model, never the outer "
        f"NcbiEfetchInput wrapper"
    )


@pytest.mark.asyncio
async def test_other_actions_are_never_called_for_a_given_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `search` call must not also invoke any of the other six functions.

    A dispatcher that routed on something other than a clean if/elif chain,
    for example a bug that called every branch and discarded all but one
    result, would still pass the identity check above. This closes that gap
    by asserting the untouched five sub-modules were never even invoked.
    """
    payload = _PAYLOAD_BY_ACTION["search"]
    tool_input = NcbiEfetchInput.model_validate(payload)
    sentinel_output = _fake_output("search")

    other_calls: list[str] = []

    async def _fake_search(resolved: Any) -> NcbiEfetchOutput:
        return sentinel_output

    monkeypatch.setattr(ncbi_efetch_module, "search", _fake_search)
    for other_name in ("summary", "fetch", "link", "coordinate_overlap", "dataset_report",
                        "pubchem_property"):
        async def _inner(
            resolved: Any, *args: Any, _other_name: str = other_name, **kwargs: Any
        ) -> NcbiEfetchOutput:
            other_calls.append(_other_name)
            return _fake_output(_other_name)

        monkeypatch.setattr(ncbi_efetch_module, other_name, _inner)

    result = await ncbi_efetch(tool_input)

    assert result is sentinel_output
    assert other_calls == [], f"unexpected calls to non-search actions: {other_calls!r}"


# ---------------------------------------------------------------------------
# Never raises: an unexpected exception from a sub-module becomes
# status="error" with an actionable message, not a propagated exception.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("action", sorted(_PAYLOAD_BY_ACTION))
async def test_unexpected_exception_from_sub_module_becomes_error_not_raised(
    action: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = _PAYLOAD_BY_ACTION[action]
    tool_input = NcbiEfetchInput.model_validate(payload)

    async def _raising(resolved: Any, *args: Any, **kwargs: Any) -> NcbiEfetchOutput:
        raise KeyError("simulated defect: an unexpected key lookup failed")

    monkeypatch.setattr(ncbi_efetch_module, _FUNCTION_NAME_BY_ACTION[action], _raising)

    result = await ncbi_efetch(tool_input)

    assert result.status == "error"
    assert result.action == action[:20]
    assert result.records == []
    assert result.record_count == 0
    assert not result.truncated
    assert result.error is not None


@pytest.mark.asyncio
async def test_error_message_is_actionable_not_bare_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The retry-safety gate (production-standards.md): an error message
    must say what to do next, not just what failed. "failed" alone, or
    the bare exception string with nothing else, does not tell the Act
    step whether to retry, and does not name which action broke.
    """
    payload = _PAYLOAD_BY_ACTION["summary"]
    tool_input = NcbiEfetchInput.model_validate(payload)

    async def _raising(resolved: Any, *args: Any, **kwargs: Any) -> NcbiEfetchOutput:
        raise ValueError("boom")

    monkeypatch.setattr(ncbi_efetch_module, "summary", _raising)

    result = await ncbi_efetch(tool_input)

    assert result.status == "error"
    assert result.error is not None
    lowered = result.error.lower()
    assert "summary" in lowered, "the message must name which action broke"
    assert "valueerror" in lowered, "the message must name the exception type"
    assert "retry" in lowered, (
        "the message must tell the next step what to do, not just what failed"
    )
    assert result.error.strip().lower() not in {"failed", "error", "failed."}, (
        "a bare 'failed' tells the agent loop nothing actionable"
    )


@pytest.mark.asyncio
async def test_error_message_is_capped_to_the_schema_field_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pathologically long exception string must not itself violate
    `NcbiEfetchOutput.error`'s own `max_length=500` bound. Since the
    dispatcher builds the `NcbiEfetchOutput` itself (not pydantic
    re-validating untrusted input), an unbounded message would raise a
    `pydantic.ValidationError` from inside the dispatcher's own error
    path, which would defeat the entire "never raises" guarantee.
    """
    payload = _PAYLOAD_BY_ACTION["search"]
    tool_input = NcbiEfetchInput.model_validate(payload)

    async def _raising(resolved: Any, *args: Any, **kwargs: Any) -> NcbiEfetchOutput:
        raise ValueError("x" * 5000)

    monkeypatch.setattr(ncbi_efetch_module, "search", _raising)

    result = await ncbi_efetch(tool_input)

    assert result.status == "error"
    assert result.error is not None
    assert len(result.error) <= 500


# ---------------------------------------------------------------------------
# The defensive last-resort branch: an action value with no dispatch arm.
# Cannot be reached through the real NcbiEfetchInput (a closed
# discriminated union), so this uses a minimal duck-typed stub instead.
# ---------------------------------------------------------------------------


class _StubResolved:
    def __init__(self, action: str) -> None:
        self.action = action


class _StubInput:
    def __init__(self, action: str) -> None:
        self.root = _StubResolved(action)


@pytest.mark.asyncio
async def test_unknown_action_value_returns_error_not_raise() -> None:
    stub_input = _StubInput("some_future_action")

    result = await ncbi_efetch(stub_input)  # type: ignore[arg-type]

    assert result.status == "error"
    assert result.action == "some_future_action"[:20]
    assert result.error is not None
    assert "dispatch" in result.error.lower() or "registration" in result.error.lower()


@pytest.mark.asyncio
async def test_tool_input_root_access_failure_returns_error_not_raise() -> None:
    """Even a caller passing something with no usable `.root`/`.action`
    at all must not crash the dispatcher: the fallback action label
    ("unknown") is used and the failure is reported, not raised.
    """

    class _Broken:
        @property
        def root(self) -> Any:
            raise RuntimeError("simulated: root access itself failed")

    result = await ncbi_efetch(_Broken())  # type: ignore[arg-type]

    assert result.status == "error"
    assert result.error is not None


# ---------------------------------------------------------------------------
# T-3.4-04: build_layer2_citation. No live network: every case constructs a
# valid NcbiEfetchOutput directly, since build_layer2_citation is a pure
# function over an already-fetched result, not a network caller itself.
# ---------------------------------------------------------------------------


def _gene_result(fields: dict[str, Any], source_url: str | None) -> NcbiEfetchOutput:
    return NcbiEfetchOutput(
        status="ok",
        action="dataset_report",
        records=[
            NcbiEfetchRecord(id="672", db="gene", fields=fields, source_url=source_url)
        ],
        record_count=1,
        truncated=False,
    )


def test_build_layer2_citation_resolves_official_symbol_alias() -> None:
    """The gate calls this with field="official_symbol", a logical name that
    is never the raw key `_extract_gene_fields` actually produces ("symbol").
    The alias table must bridge the two without fabricating a value.
    """
    result = _gene_result(
        {"gene_id": "672", "symbol": "BRCA1"},
        "https://www.ncbi.nlm.nih.gov/gene/672/",
    )

    citation = build_layer2_citation(result, field="official_symbol")

    assert citation.field == "official_symbol"
    assert "BRCA1" in citation.claim_text
    assert citation.evidence_kind == "primary_assertion"
    assert citation.assertion_confidence == "asserted"
    assert citation.license == "public_domain_us_gov"
    assert citation.source_url == "https://www.ncbi.nlm.nih.gov/gene/672/"
    assert citation.layer == "layer_2_api"
    assert citation.population_ancestry_context is None
    assert citation.display_index == 1


def test_build_layer2_citation_uses_clinvar_confidence_for_clinvar_shaped_field() -> None:
    """coordinate_overlap's ClinVar branch names its field
    "germline_classification"; a "contested" ClinVar term must lower
    assertion_confidence, never default to "asserted" like a plain field.
    """
    result = _gene_result(
        {"germline_classification": "conflicting_interpretations_of_pathogenicity"},
        "https://www.ncbi.nlm.nih.gov/clinvar/variation/12345/",
    )

    citation = build_layer2_citation(result, field="clinical_significance")

    assert citation.assertion_confidence == "contested"


def test_build_layer2_citation_raises_when_no_record_has_a_source_url() -> None:
    result = _gene_result({"symbol": "BRCA1"}, source_url=None)

    with pytest.raises(ValueError, match="source_url"):
        build_layer2_citation(result, field="official_symbol")


def test_build_layer2_citation_raises_when_field_not_present() -> None:
    result = _gene_result(
        {"gene_id": "672"}, "https://www.ncbi.nlm.nih.gov/gene/672/"
    )

    with pytest.raises(ValueError, match="official_symbol"):
        build_layer2_citation(result, field="official_symbol")
