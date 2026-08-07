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

    F-3.1-28 (CRITICAL, re-review round 1). The taxon-aware cache key is
    used for the cache and nowhere else. It used to be passed into the
    uncached helper as the symbol, so every live lookup asked NCBI for a
    gene literally named "BRCA1:human" and every gene-symbol resolution
    in the system returned None.

    Finding 2 (CRITICAL, re-review) and F-3.1-26 (re-review round 1). A
    confirmed non-resolution (both Datasets and ESearch answered and
    neither found the symbol) is cached; a transient failure on EITHER
    leg (a `status == "error"`, modeling a timeout, connection failure,
    5xx, or rate limit) is never cached, so the identical symbol is
    retried live on the next call rather than replaying a stale outage
    forever.

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
# F-3.1-28 (CRITICAL, re-review round 1): the cache key is a cache key, and
# never the value put on the wire.
# ===========================================================================


@pytest.mark.asyncio
async def test_the_symbol_sent_to_ncbi_is_the_symbol_not_the_cache_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.1-28's exact repro, asserted on the request rather than on the
    answer.

    `resolve_symbol_to_curie` composes a taxon-aware cache key,
    "BRCA1:human", and used to pass THAT into the uncached helper as the
    symbol. Both live calls then asked NCBI for a gene literally named
    "BRCA1:human": the Datasets `symbol` parameter and the ESearch
    "BRCA1:human[sym]" term. No such gene exists, so every gene-symbol
    resolution in the system returned None.

    Asserting on the outbound request is deliberate. A test that only
    checked the returned CURIE would pass the moment a fake responds to
    any symbol at all, which is precisely how this defect survived a
    green suite.
    """
    dataset_calls: list[tuple[str | None, str | None]] = []
    search_terms: list[str] = []

    async def _recording_ncbi_efetch(tool_input: Any) -> NcbiEfetchOutput:
        root = tool_input.root
        if root.action == "dataset_report":
            dataset_calls.append((root.symbol, root.taxon))
            return _dataset_report_output(status="empty")
        search_terms.append(root.term)
        return _search_output(status="empty", idlist=[])

    monkeypatch.setattr(graph_module, "ncbi_efetch", _recording_ncbi_efetch)

    await graph_module.resolve_symbol_to_curie("  brca1  ", taxon="Human")

    assert dataset_calls == [("BRCA1", "human")], (
        f"the Datasets call must carry the normalized SYMBOL and the taxon as "
        f"two separate values, got {dataset_calls!r}"
    )
    assert search_terms == ["BRCA1[sym] AND human[orgn]"], (
        f"the ESearch term must be built from the symbol alone, got "
        f"{search_terms!r}"
    )


# ===========================================================================
# Finding 2 (CRITICAL, re-review) and F-3.1-26 (re-review round 1):
# confirmed-negative caching vs transient-failure caching, on BOTH legs.
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
    assert "TP53:human" not in graph_module._SYMBOL_CURIE_CACHE, (
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
async def test_a_datasets_error_is_never_cached_even_when_esearch_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.1-26 (reopened at re-review round 1). This test previously
    asserted the OPPOSITE, that a Datasets error still gets cached as
    long as ESearch succeeded, on the reasoning that only the last branch
    to decide matters. That reasoning contradicts the property both
    `_SYMBOL_CURIE_CACHE` and `_resolve_symbol_to_curie_uncached` claim in
    their own comments: that a cached value means BOTH Datasets and
    ESearch answered. A Datasets timeout is not an answer.

    The consequence of the old behavior is Finding 2's defect one leg
    over: during a partial NCBI outage where Datasets is down and ESearch
    returns nothing, the symbol is cached as a confirmed absence and stays
    unresolvable for the life of the process even after Datasets recovers.

    Both arms are asserted here, because the ESearch-found-something arm
    is the one the old test got wrong and the ESearch-found-nothing arm is
    the one that actually corrupts an answer.
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(status="error"),
        search=_search_output(status="ok", idlist=["672"]),
    )

    result = await graph_module.resolve_symbol_to_curie("BRCA1")
    assert result == "NCBIGene:672", "the ESearch answer is still returned to the caller"
    assert calls == ["dataset_report", "search"]
    assert "BRCA1:human" not in graph_module._SYMBOL_CURIE_CACHE, (
        "a leg that errored means the result is not a confirmed answer from "
        "both APIs, so it must not be written to a process-lifetime cache"
    )

    # The arm that actually corrupts an answer: Datasets errors, ESearch
    # genuinely finds nothing. That is NOT a confirmed absence.
    _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(status="error"),
        search=_search_output(status="empty", idlist=[]),
    )

    missing = await graph_module.resolve_symbol_to_curie("EGFR")
    assert missing is None
    assert "EGFR:human" not in graph_module._SYMBOL_CURIE_CACHE, (
        "a zero-hit ESearch behind an ERRORED Datasets call is a partial "
        "outage, not a confirmed non-resolution, and caching it makes the "
        "symbol permanently unresolvable"
    )

    # Datasets recovers: the same symbol must be retried live, not served
    # from a cached outage.
    calls_after_recovery = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(records=[_dataset_record(gene_id="1956")]),
    )
    assert await graph_module.resolve_symbol_to_curie("EGFR") == "NCBIGene:1956"
    assert calls_after_recovery == ["dataset_report"]


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
    """F-3.1-17 (adversary finding 5, CRITICAL): non-human taxon records
    are now accepted rather than discarded. A single Datasets record with
    gene_id and any taxname resolves directly; only a record missing
    gene_id falls through to ESearch.
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(
            records=[_dataset_record(gene_id=None, taxname="Mus musculus")]
        ),
        search=_search_output(status="ok", idlist=["672"]),
    )

    result = await graph_module.resolve_symbol_to_curie("MOUSEONLYSYMBOL")
    assert calls == ["dataset_report", "search"]
    assert result == "NCBIGene:672"


@pytest.mark.asyncio
async def test_non_human_taxon_resolves_directly_from_datasets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.1-17 (adversary finding 5, CRITICAL): a non-human taxon must
    resolve correctly from the Datasets branch without falling through to
    a human-hardcoded ESearch. Before this fix, TRP53/taxon=mouse returned
    NCBIGene:7157 (human) because the Datasets result was discarded
    (taxname != "Homo sapiens") and the ESearch fallback was hardcoded to
    human[orgn].
    """
    calls = _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(
            records=[_dataset_record(gene_id="22059", taxname="Mus musculus")]
        ),
        search=_search_output(status="ok", idlist=["7157"]),
    )

    result = await graph_module.resolve_symbol_to_curie("TRP53", taxon="mouse")
    assert calls == ["dataset_report"], (
        f"non-human taxon must resolve from Datasets without falling through "
        f"to ESearch, got calls {calls!r}"
    )
    assert result == "NCBIGene:22059", (
        f"TRP53/mouse must resolve to NCBIGene:22059 (mouse), "
        f"got {result!r}"
    )


@pytest.mark.asyncio
async def test_cache_key_includes_taxon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-3.1-17 continued: the cache key must include taxon, so BRCA1
    resolved for human does not return from cache for mouse with zero
    network calls.
    """
    _install_fake_ncbi_efetch(
        monkeypatch,
        dataset_report=_dataset_report_output(
            records=[_dataset_record(gene_id="672", taxname="Homo sapiens")]
        ),
    )
    await graph_module.resolve_symbol_to_curie("BRCA1", taxon="human")
    assert "BRCA1:human" in graph_module._SYMBOL_CURIE_CACHE, (
        "cache key must include taxon"
    )
    assert "BRCA1:mouse" not in graph_module._SYMBOL_CURIE_CACHE, (
        "BRCA1 resolved for human must not be cached for mouse"
    )
