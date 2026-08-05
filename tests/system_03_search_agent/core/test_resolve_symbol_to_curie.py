"""Unit tests for `core.graph.resolve_symbol_to_curie` and its private
helper `_resolve_symbol_to_curie_uncached` (T-3.1-11), closing two
re-review findings on build phase 3.1 no other test file in this repo
covers directly: every other test file that touches this function stubs
it out entirely (`test_graph.py`, `test_run.py`, `test_query_endpoint.py`,
`test_streaming_endpoints.py`), by design, since their own job is the
graph's routing logic, not this function's internal cache and ambiguity
handling.

No live network anywhere in this file: `graph_module.ncbi_efetch` is
monkeypatched per test, the same chokepoint
`_resolve_symbol_to_curie_uncached` itself calls, so nothing here reaches
`system_03_search_agent.tools.ncbi_transport.execute_get` at all.
`tests/conftest.py`'s session-wide network guard would catch it if it
somehow did.

What this file proves:

    Finding 2 (CRITICAL, re-review). A confirmed non-resolution (both
    Datasets and ESearch answered and neither found the symbol) is
    cached; a transient failure (a `status == "error"` from either call,
    modeling a timeout, connection failure, 5xx, or rate limit) is never
    cached, so the identical symbol is retried live on the next call
    rather than replaying a stale outage forever.

    Finding 5 (MAJOR, re-review). `dataset_report` returning more than
    one record is ambiguous and must never be resolved by taking
    `records[0]`; it must fall through to the ESearch path, exactly
    mirroring the guard ESearch's own `len(idlist) != 1` check already
    applied twenty lines below it.

Depends on:
    - system_03_search_agent.core.graph (resolve_symbol_to_curie,
      _resolve_symbol_to_curie_uncached, _SYMBOL_CURIE_CACHE, the module
      under test)
    - system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchOutput,
      NcbiEfetchRecord, for building fake ncbi_efetch responses)

Writes:
    - Nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput, NcbiEfetchRecord


@pytest.fixture(autouse=True)
def _reset_symbol_curie_cache() -> None:
    """`_SYMBOL_CURIE_CACHE` is process-global, in-process-for-life state
    (see its own declaration comment in `core/graph.py`), so a test in
    this file left unreset could see a cached value an earlier test in
    the same session wrote for the same symbol. Every test here uses a
    fresh, distinguishable symbol regardless, but resetting explicitly is
    the same discipline `test_ncbi_transport.py`'s and
    `test_ncbi_coordinate_overlap.py`'s own rate-limiter reset fixtures
    already apply to their own module-global state.
    """
    graph_module._SYMBOL_CURIE_CACHE.clear()
    yield
    graph_module._SYMBOL_CURIE_CACHE.clear()


def _dataset_report_output(
    *, status: str = "ok", records: list[NcbiEfetchRecord] | None = None
) -> NcbiEfetchOutput:
    records = records or []
    return NcbiEfetchOutput(
        status=status,
        action="dataset_report",
        records=records,
        record_count=len(records),
        total_available=len(records),
        truncated=False,
        error="simulated dataset_report failure" if status == "error" else None,
    )


def _search_output(*, status: str = "ok", idlist: list[str] | None = None) -> NcbiEfetchOutput:
    records: list[NcbiEfetchRecord] = []
    if idlist is not None:
        records = [NcbiEfetchRecord(id=None, db="gene", fields={"idlist": idlist})]
    return NcbiEfetchOutput(
        status=status,
        action="search",
        records=records,
        record_count=len(records),
        total_available=len(records) if idlist is None else len(idlist),
        truncated=False,
        error="simulated search failure" if status == "error" else None,
    )


def _dataset_record(*, gene_id: str, taxname: str = "Homo sapiens") -> NcbiEfetchRecord:
    return NcbiEfetchRecord(id=gene_id, db="gene", fields={"gene_id": gene_id, "taxname": taxname})


def _install_fake_ncbi_efetch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dataset_report: NcbiEfetchOutput,
    search: NcbiEfetchOutput | None = None,
) -> list[str]:
    """Patches `graph_module.ncbi_efetch` to answer `dataset_report` and
    `search` actions with the two canned outputs, and returns the list of
    actions actually called, in order, so a test can assert whether the
    ESearch fallback fired at all.
    """
    calls: list[str] = []

    async def _fake_ncbi_efetch(tool_input: Any) -> NcbiEfetchOutput:
        action = tool_input.root.action
        calls.append(action)
        if action == "dataset_report":
            return dataset_report
        if action == "search":
            assert search is not None, "test did not expect the ESearch fallback to fire"
            return search
        raise AssertionError(f"unexpected ncbi_efetch action {action!r} in this test")

    monkeypatch.setattr(graph_module, "ncbi_efetch", _fake_ncbi_efetch)
    return calls


# ===========================================================================
# Finding 2 (CRITICAL, re-review): confirmed-negative caching vs
# transient-failure caching.
# ===========================================================================


@pytest.mark.asyncio
async def test_confirmed_non_resolution_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both Datasets and ESearch genuinely answer and neither finds the
    symbol: a real, stable negative. The second call for the same symbol
    must be served from cache, not re-fetched.
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(status="empty"),
        search=_search_output(status="empty", idlist=[]),
    )

    first = await graph_module.resolve_symbol_to_curie("NOTAREALGENEXYZZY")
    assert first is None
    assert calls == ["dataset_report", "search"]

    second = await graph_module.resolve_symbol_to_curie("NOTAREALGENEXYZZY")
    assert second is None
    assert calls == ["dataset_report", "search"], (
        "a confirmed non-resolution must be served from cache on the second "
        "call, not re-fetched"
    )


@pytest.mark.asyncio
async def test_transient_outage_is_never_cached_and_retries_on_the_next_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finding 2's exact repro: during a transient outage a symbol
    resolves to `None` because neither call could even be answered
    (`status == "error"` on both). That `None` must NOT be cached, so
    after NCBI recovers the next query for the same symbol retries live
    and succeeds, rather than replaying the cached outage forever.
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(status="error"),
        search=_search_output(status="error"),
    )

    during_outage = await graph_module.resolve_symbol_to_curie("TP53")
    assert during_outage is None
    assert calls == ["dataset_report", "search"]
    assert "TP53" not in graph_module._SYMBOL_CURIE_CACHE, (
        "a transient error must never be written to the cache"
    )

    # NCBI recovers: swap in a fake that answers for real.
    calls_after_recovery = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(records=[_dataset_record(gene_id="7157")]),
    )

    after_recovery = await graph_module.resolve_symbol_to_curie("TP53")
    assert after_recovery == "NCBIGene:7157", (
        "the symbol must be retried live after the cached-outage bug is fixed, not "
        "permanently stuck at None"
    )
    assert calls_after_recovery == ["dataset_report"]


@pytest.mark.asyncio
async def test_datasets_error_falling_back_to_a_successful_esearch_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Datasets errors but the ESearch fallback genuinely succeeds
    with an unambiguous match, the overall result is a confirmed
    resolution and must be cached: only the LAST branch to decide
    matters for cacheability, not every branch along the way.
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(status="error"),
        search=_search_output(status="ok", idlist=["672"]),
    )

    result = await graph_module.resolve_symbol_to_curie("BRCA1")
    assert result == "NCBIGene:672"
    assert calls == ["dataset_report", "search"]
    assert graph_module._SYMBOL_CURIE_CACHE.get("BRCA1") == "NCBIGene:672"


@pytest.mark.asyncio
async def test_ambiguous_esearch_match_is_a_confirmed_negative_and_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ambiguous ESearch match (more than one id) is a real, answered
    outcome, never fabricated into a CURIE, and is just as cacheable as a
    genuine zero-hit search: both are confirmed answers from a
    successful call.
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(status="empty"),
        search=_search_output(status="ok", idlist=["1", "2"]),
    )

    result = await graph_module.resolve_symbol_to_curie("AMBIGUOUSGENE")
    assert result is None
    assert calls == ["dataset_report", "search"]

    second = await graph_module.resolve_symbol_to_curie("AMBIGUOUSGENE")
    assert second is None
    assert calls == ["dataset_report", "search"], "an ambiguous match is a confirmed negative, cached"


# ===========================================================================
# Finding 5 (MAJOR, re-review): the Datasets branch must require exactly
# one record, mirroring the ESearch guard, never take records[0] blind.
# ===========================================================================


@pytest.mark.asyncio
async def test_single_dataset_report_record_resolves_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordinary, unambiguous case: exactly one Datasets record, human,
    with a gene_id. Resolves without ever calling ESearch.
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(records=[_dataset_record(gene_id="7157")]),
    )

    result = await graph_module.resolve_symbol_to_curie("TP53")
    assert result == "NCBIGene:7157"
    assert calls == ["dataset_report"], "an unambiguous match must never trigger the ESearch fallback"


@pytest.mark.asyncio
async def test_multiple_dataset_report_records_falls_through_to_esearch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finding 5's exact repro: `dataset_report` returns MORE THAN ONE
    record (it can return up to 100). Before the fix, `records[0]` was
    taken with no ambiguity check, silently guessing among candidates.
    The fix must fall through to ESearch instead of trusting an
    arbitrary first record, mirroring the ESearch guard's own
    `len(idlist) != 1` refusal. The two records below carry DIFFERENT
    gene_ids (7157 and 99999) so a test that accidentally kept the old
    `records[0]` behavior would return 7157 instead of going through
    ESearch's own, different, unambiguous answer (672).
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(
            records=[
                _dataset_record(gene_id="7157"),
                _dataset_record(gene_id="99999"),
            ]
        ),
        search=_search_output(status="ok", idlist=["672"]),
    )

    result = await graph_module.resolve_symbol_to_curie("AMBIGUOUSSYMBOL")
    assert calls == ["dataset_report", "search"], (
        "an ambiguous Datasets response must fall through to the ESearch path, "
        "never resolve directly off an arbitrary records[0]"
    )
    assert result == "NCBIGene:672", (
        f"expected the ESearch fallback's unambiguous answer, got {result!r}, which is "
        f"exactly what taking dataset_report's records[0] blind would have produced"
    )


@pytest.mark.asyncio
async def test_ambiguous_dataset_report_with_no_esearch_match_resolves_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ambiguous Datasets response that ALSO fails to resolve via
    ESearch must end in None, never in a guessed CURIE from the
    ambiguous Datasets candidates.
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(
            records=[
                _dataset_record(gene_id="7157"),
                _dataset_record(gene_id="99999"),
            ]
        ),
        search=_search_output(status="empty", idlist=[]),
    )

    result = await graph_module.resolve_symbol_to_curie("AMBIGUOUSSYMBOLTWO")
    assert result is None
    assert calls == ["dataset_report", "search"]


@pytest.mark.asyncio
async def test_dataset_report_record_missing_gene_id_falls_through_to_esearch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single record that is missing `gene_id` or is not human must
    also fall through to ESearch, the existing (pre-Finding-5) behavior,
    preserved by this fix: the ambiguity guard only changes what happens
    when there is MORE than one record, not the single-record checks
    that already existed.
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(
            records=[_dataset_record(gene_id="7157", taxname="Mus musculus")]
        ),
        search=_search_output(status="ok", idlist=["672"]),
    )

    result = await graph_module.resolve_symbol_to_curie("MOUSEONLYSYMBOL")
    assert calls == ["dataset_report", "search"]
    assert result == "NCBIGene:672"
