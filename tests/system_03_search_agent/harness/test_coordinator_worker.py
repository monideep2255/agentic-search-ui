"""Tests for coordinator_worker_execute (T-2.0-05, extended by T-2.1-08).

Covers the asyncio.gather concurrency guarantee (two artificially delayed
free-text results run their reader passes in parallel, not sequentially),
the free-text/structured branching (a free-text result routes through a
mocked `Harness.call_tier`, a structured result never calls it at all),
the no-raw-text-leak guarantee (a free-text result's returned `Finding`
never contains the original payload substring, including on a reader
response that fails to parse as JSON), the F-2.0-08 closure (the reader
pass now respects the per-query cost cap and a per-step timeout), the
F-2.0-14 closure (the structured pass-through path caps an oversized
payload before a `Finding` is built), and the F-03 closure (the F-2.0-14
cap is now genuinely recursive over arbitrarily nested dicts and lists,
dict keys are length-capped, recursion depth is bounded, and a total
size ceiling on the whole `Finding` composes with the per-field caps).

The F-03 regression tests below construct the real production shape
(`{"rows": [{"fields": {...}}, ...]}`, what `core/graph.py`'s
`_cypher_output_to_structured_fields` actually produces), not only the
flat one-level dict the pre-F-03 test suite used, since that flat shape
is exactly what let the F-2.0-14 cap's non-recursion go undetected.

No real model call is made anywhere in this file: `Harness.call_tier` is
mocked in every test, matching test_harness.py's own convention of never
issuing a real LiteLLM/network call.
"""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from system_03_search_agent.contracts.events import ToolCall
from system_03_search_agent.harness import coordinator_worker as coordinator_worker_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness.coordinator_worker import (
    Finding,
    ToolExecutionResult,
    coordinator_worker_execute,
)
from system_03_search_agent.harness.harness import Harness, HarnessCallError


@pytest.fixture(autouse=True)
def _cost_cap_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """F-2.0-08: `_reader_pass` now calls `cost_control.check_per_query_cap`,
    which reads `PER_QUERY_COST_CAP_USD` from the environment and raises
    `RuntimeError` if it is unset. Every test in this file needs it set,
    not only the ones added for F-2.0-08, since the free-text reader path
    is exercised throughout this file.
    """
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")


def _make_call(call_id: str, tool: str = "ncbi_efetch", layer: str = "layer_2_api") -> ToolCall:
    return ToolCall(tool=tool, call_id=call_id, layer=layer)


def _make_harness() -> Harness:
    # A real Harness instance, but call_tier is replaced per-test with an
    # AsyncMock; the tier-resolution and cost-accounting machinery it
    # otherwise owns is irrelevant to this module.
    return Harness(trace_id="test-trace-id")


def _reader_response(content: str) -> SimpleNamespace:
    """A minimal stand-in for the LLMResponse shape this module reads:
    only `.content` is ever touched."""
    return SimpleNamespace(content=content)


# --- Concurrency: asyncio.gather fan-out, not sequential ---


@pytest.mark.asyncio
async def test_free_text_reader_calls_run_concurrently() -> None:
    delay_seconds = 0.2
    harness = _make_harness()

    async def _slow_call_tier(tier: str, messages: list[dict[str, str]], **_: object) -> object:
        await asyncio.sleep(delay_seconds)
        return _reader_response('{"entities": [], "normalized_ids": [], "evidence_summary": ""}')

    harness.call_tier = AsyncMock(side_effect=_slow_call_tier)  # type: ignore[method-assign]

    tool_calls = [_make_call("call-1"), _make_call("call-2")]
    results = [
        ToolExecutionResult(contains_untrusted_free_text=True, free_text="abstract one"),
        ToolExecutionResult(contains_untrusted_free_text=True, free_text="abstract two"),
    ]

    start = time.monotonic()
    findings = await coordinator_worker_execute(harness, tool_calls, results)
    elapsed = time.monotonic() - start

    assert len(findings) == 2
    # Sequential would take ~2 * delay_seconds; concurrent stays close to
    # one delay_seconds. Generous upper bound to absorb scheduling jitter
    # without being close enough to the sequential total to pass by luck.
    assert elapsed < delay_seconds * 1.7, (
        f"expected concurrent execution near {delay_seconds}s, took {elapsed:.3f}s, "
        "close to the sequential sum: asyncio.gather fan-out is not happening"
    )
    assert harness.call_tier.await_count == 2


# --- Free-text routing through the isolated reader ---


@pytest.mark.asyncio
async def test_free_text_result_routes_through_reader_call() -> None:
    harness = _make_harness()
    harness.call_tier = AsyncMock(  # type: ignore[method-assign]
        return_value=_reader_response(
            '{"entities": ["BRCA1"], "normalized_ids": ["HGNC:1100"], '
            '"evidence_summary": "BRCA1 is discussed in the abstract."}'
        )
    )

    call = _make_call("call-1")
    result = ToolExecutionResult(
        contains_untrusted_free_text=True,
        free_text="BRCA1 mutations are associated with breast cancer risk.",
    )

    findings = await coordinator_worker_execute(harness, [call], [result])

    assert len(findings) == 1
    finding = findings[0]
    assert isinstance(finding, Finding)
    assert finding.source == "reader"
    assert finding.call_id == "call-1"
    assert finding.structured_fields is None
    assert finding.extracted_entities == ["BRCA1"]
    assert finding.normalized_ids == ["HGNC:1100"]
    assert finding.evidence_summary == "BRCA1 is discussed in the abstract."

    harness.call_tier.assert_awaited_once()
    tier_arg, messages_arg = harness.call_tier.await_args.args
    assert tier_arg == "guard"
    # The reader's scoping is enforced in the prompt content, not just a
    # code comment: assert the system message actually states the
    # read-only, no-tool, no-write scope.
    system_message = next(m["content"] for m in messages_arg if m["role"] == "system")
    assert "no ability to call any tool" in system_message
    assert "write or modify" in system_message
    # And the user message carries exactly the one payload, nothing else.
    user_message = next(m["content"] for m in messages_arg if m["role"] == "user")
    assert user_message == result.free_text


# --- Structured pass-through: no reader call at all ---


@pytest.mark.asyncio
async def test_structured_result_passes_through_with_no_reader_call() -> None:
    harness = _make_harness()
    harness.call_tier = AsyncMock()  # type: ignore[method-assign]

    call = _make_call("call-2", tool="cypher_query", layer="layer_1_graph")
    structured_fields = {"gene_symbol": "TP53", "ncbi_gene_id": "7157"}
    result = ToolExecutionResult(
        contains_untrusted_free_text=False,
        structured_fields=structured_fields,
    )

    findings = await coordinator_worker_execute(harness, [call], [result])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source == "structured_pass_through"
    assert finding.call_id == "call-2"
    assert finding.tool == "cypher_query"
    assert finding.layer == "layer_1_graph"
    assert finding.structured_fields == structured_fields
    assert finding.extracted_entities is None
    assert finding.normalized_ids is None
    assert finding.evidence_summary is None

    harness.call_tier.assert_not_awaited()


@pytest.mark.asyncio
async def test_mixed_batch_only_calls_reader_for_free_text_entry() -> None:
    harness = _make_harness()
    harness.call_tier = AsyncMock(  # type: ignore[method-assign]
        return_value=_reader_response(
            '{"entities": [], "normalized_ids": [], "evidence_summary": "ok"}'
        )
    )

    tool_calls = [_make_call("call-structured"), _make_call("call-free-text")]
    results = [
        ToolExecutionResult(contains_untrusted_free_text=False, structured_fields={"a": 1}),
        ToolExecutionResult(contains_untrusted_free_text=True, free_text="some record body"),
    ]

    findings = await coordinator_worker_execute(harness, tool_calls, results)

    assert findings[0].source == "structured_pass_through"
    assert findings[1].source == "reader"
    # Exactly one reader call for the one free-text entry, not two.
    assert harness.call_tier.await_count == 1


# --- No-raw-text-leak guarantee ---


@pytest.mark.asyncio
async def test_free_text_finding_never_contains_original_payload_on_valid_json() -> None:
    harness = _make_harness()
    marker = "UNIQUE_SECRET_MARKER_the_raw_abstract_text_12345"
    harness.call_tier = AsyncMock(  # type: ignore[method-assign]
        return_value=_reader_response(
            '{"entities": ["some gene"], "normalized_ids": [], '
            '"evidence_summary": "a short derived summary"}'
        )
    )

    call = _make_call("call-1")
    result = ToolExecutionResult(
        contains_untrusted_free_text=True,
        free_text=f"This abstract contains the marker {marker} inline.",
    )

    findings = await coordinator_worker_execute(harness, [call], [result])
    finding = findings[0]

    assert marker not in (finding.evidence_summary or "")
    assert not any(marker in entity for entity in finding.extracted_entities or [])
    assert not any(marker in nid for nid in finding.normalized_ids or [])
    assert marker not in repr(finding)


@pytest.mark.asyncio
async def test_free_text_finding_never_contains_original_payload_on_unparseable_reader_response() -> (
    None
):
    harness = _make_harness()
    marker = "UNIQUE_SECRET_MARKER_the_raw_abstract_text_67890"
    payload = f"This abstract contains the marker {marker} inline."
    # Simulate a misbehaving reader that echoes the raw payload back
    # instead of returning valid JSON findings.
    harness.call_tier = AsyncMock(  # type: ignore[method-assign]
        return_value=_reader_response(payload)
    )

    call = _make_call("call-1")
    result = ToolExecutionResult(contains_untrusted_free_text=True, free_text=payload)

    findings = await coordinator_worker_execute(harness, [call], [result])
    finding = findings[0]

    # The parser degrades to an empty-findings Finding on invalid JSON,
    # never falling back to the reader's raw (and here payload-echoing)
    # response content.
    assert finding.extracted_entities == []
    assert finding.normalized_ids == []
    assert marker not in (finding.evidence_summary or "")
    assert marker not in repr(finding)


# --- Input validation ---


@pytest.mark.asyncio
async def test_mismatched_list_lengths_raises_value_error() -> None:
    harness = _make_harness()
    harness.call_tier = AsyncMock()  # type: ignore[method-assign]

    tool_calls = [_make_call("call-1"), _make_call("call-2")]
    results = [ToolExecutionResult(contains_untrusted_free_text=False, structured_fields={})]

    with pytest.raises(ValueError, match="paired 1:1"):
        await coordinator_worker_execute(harness, tool_calls, results)

    harness.call_tier.assert_not_awaited()


# ---------------------------------------------------------------------------
# F-2.0-08: the reader pass now respects the per-query cost cap and a
# per-step timeout, instead of bypassing both entirely.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reader_call_skipped_when_it_would_breach_the_per_query_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _make_harness()
    harness.call_tier = AsyncMock()  # type: ignore[method-assign]

    def _always_over_cap(harness_arg, trace_id, tier, **kwargs):
        raise cost_control.QueryCapExceededError(
            "forced for test",
            query_cost_usd=1.0,
            query_cap_usd=1.0,
            estimated_call_cost_usd=0.01,
        )

    monkeypatch.setattr(cost_control, "check_per_query_cap", _always_over_cap)

    call = _make_call("call-1")
    result = ToolExecutionResult(contains_untrusted_free_text=True, free_text="some abstract")

    findings = await coordinator_worker_execute(harness, [call], [result])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source == "reader"
    assert finding.extracted_entities == []
    assert finding.normalized_ids == []
    assert "cost cap" in (finding.evidence_summary or "")
    harness.call_tier.assert_not_awaited()  # the call was never issued at all


@pytest.mark.asyncio
async def test_reader_call_timeout_degrades_to_a_finding_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _make_harness()

    async def _hang(*args: object, **kwargs: object) -> object:
        await asyncio.sleep(10)  # far longer than the reader's timeout budget
        raise AssertionError("should have been cancelled by enforce_timeout")

    harness.call_tier = AsyncMock(side_effect=_hang)  # type: ignore[method-assign]
    monkeypatch.setattr(coordinator_worker_module, "_READER_CALL_TIMEOUT_S", 0.05)

    call = _make_call("call-1")
    result = ToolExecutionResult(contains_untrusted_free_text=True, free_text="some abstract")

    findings = await coordinator_worker_execute(harness, [call], [result])

    assert len(findings) == 1
    finding = findings[0]
    assert finding.source == "reader"
    assert finding.extracted_entities == []
    assert "timeout" in (finding.evidence_summary or "")


@pytest.mark.asyncio
async def test_reader_call_classified_failure_degrades_to_a_finding_instead_of_raising() -> None:
    harness = _make_harness()
    harness.call_tier = AsyncMock(  # type: ignore[method-assign]
        side_effect=HarnessCallError("simulated call_tier failure", error_class="unexpected")
    )

    call = _make_call("call-1")
    result = ToolExecutionResult(contains_untrusted_free_text=True, free_text="some abstract")

    findings = await coordinator_worker_execute(harness, [call], [result])

    assert len(findings) == 1
    assert findings[0].source == "reader"
    assert findings[0].extracted_entities == []


@pytest.mark.asyncio
async def test_a_cap_breach_on_one_reader_call_does_not_crash_the_whole_gather(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A partial result, not a crash: one degraded Finding for the call
    that breached the cap, a normal Finding for the other."""
    harness = _make_harness()
    harness.call_tier = AsyncMock(  # type: ignore[method-assign]
        return_value=_reader_response(
            '{"entities": ["ok"], "normalized_ids": [], "evidence_summary": "fine"}'
        )
    )

    real_check = cost_control.check_per_query_cap
    call_count = {"n": 0}

    def _raise_on_first_check(harness_arg, trace_id, tier, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise cost_control.QueryCapExceededError(
                "forced for test", query_cost_usd=1.0, query_cap_usd=1.0,
                estimated_call_cost_usd=0.01,
            )
        return real_check(harness_arg, trace_id, tier, **kwargs)

    monkeypatch.setattr(cost_control, "check_per_query_cap", _raise_on_first_check)

    tool_calls = [_make_call("call-1"), _make_call("call-2")]
    results = [
        ToolExecutionResult(contains_untrusted_free_text=True, free_text="abstract one"),
        ToolExecutionResult(contains_untrusted_free_text=True, free_text="abstract two"),
    ]

    findings = await coordinator_worker_execute(harness, tool_calls, results)

    assert len(findings) == 2
    assert "cost cap" in (findings[0].evidence_summary or "")
    assert findings[1].extracted_entities == ["ok"]


# ---------------------------------------------------------------------------
# F-2.0-14: the structured pass-through path caps an oversized payload
# before a Finding is built.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_oversized_structured_payload_is_capped_before_reaching_a_finding() -> None:
    harness = _make_harness()
    harness.call_tier = AsyncMock()  # type: ignore[method-assign]

    hostile_fields: dict[str, object] = {
        "long_string": "y" * 10_000,  # far longer than the string cap
        "long_list": list(range(2000)),  # far more items than the list cap
        "nested": {f"nested_key_{i}": "z" * 5_000 for i in range(100)},
    }
    # Padding keys appended after the fields under test, so the top-level
    # key cap (which keeps the first N keys in insertion order) trims the
    # padding, not the fields the assertions below check.
    hostile_fields.update({f"key_{i}": "x" for i in range(100)})

    call = _make_call("call-1", tool="cypher_query", layer="layer_1_graph")
    result = ToolExecutionResult(contains_untrusted_free_text=False, structured_fields=hostile_fields)

    findings = await coordinator_worker_execute(harness, [call], [result])

    assert len(findings) == 1
    capped = findings[0].structured_fields
    assert capped is not None
    assert len(capped) <= 30  # top-level key count capped
    assert len(capped["long_string"]) <= 2000
    assert len(capped["long_list"]) <= 500
    nested = capped["nested"]
    assert len(nested) <= 30
    # Item 11.33, 2026-09-22: the cap rose to the finding's own bound (2000,
    # `synthesis/findings.py` MAX_FIELD_VALUE_CHARS) and one cap now applies
    # at every depth, so a nested value is bounded by 2000, not 500.
    assert all(len(value) <= 2000 for value in nested.values() if isinstance(value, str))
    harness.call_tier.assert_not_awaited()  # structured pass-through never calls the reader
    # F-03: truncation is signalled on the Finding, not left invisible.
    assert findings[0].truncated is True


@pytest.mark.asyncio
async def test_well_formed_structured_payload_passes_through_unchanged() -> None:
    """A payload already within every cap is not altered by the capping
    pass, only truly oversized payloads are trimmed."""
    harness = _make_harness()
    harness.call_tier = AsyncMock()  # type: ignore[method-assign]

    fields = {"gene_symbol": "TP53", "ncbi_gene_id": "7157", "row_count": 1}
    call = _make_call("call-1", tool="cypher_query", layer="layer_1_graph")
    result = ToolExecutionResult(contains_untrusted_free_text=False, structured_fields=fields)

    findings = await coordinator_worker_execute(harness, [call], [result])

    assert findings[0].structured_fields == fields
    # F-03: nothing was cut, so truncated must be False, not left as an
    # unconditional True whenever the capping pass merely ran.
    assert findings[0].truncated is False


# ---------------------------------------------------------------------------
# F-03: the F-2.0-14 cap was not actually recursive. A dict or a list
# reached `_cap_leaf_value` and passed through untouched; a nested list
# handed to the old list branch also passed through untouched; dict keys
# were never length-capped at all. The four cases below are the judge's
# own measured probes, each asserting the actual byte size before and
# after, not merely that the function returned something.
# ---------------------------------------------------------------------------


def _json_bytes(value: object) -> int:
    """The same size proxy the judge used: serialized JSON, encoded to
    bytes. Used here only to state the measured before/after sizes on the
    record; the module itself uses the same proxy internally.
    """
    return len(json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"))


async def _pass_through_one(structured_fields: dict[str, object]) -> object:
    """Run one structured payload through the real
    coordinator_worker_execute path and return the resulting Finding."""
    harness = _make_harness()
    harness.call_tier = AsyncMock()  # type: ignore[method-assign]
    call = _make_call("call-1", tool="cypher_query", layer="layer_1_graph")
    result = ToolExecutionResult(contains_untrusted_free_text=False, structured_fields=structured_fields)
    findings = await coordinator_worker_execute(harness, [call], [result])
    harness.call_tier.assert_not_awaited()
    return findings[0]


@pytest.mark.asyncio
async def test_real_production_shape_rows_and_fields_is_bounded_and_signalled() -> None:
    """The shape `core/graph.py`'s `_cypher_output_to_structured_fields`
    actually produces: `{"rows": [{"fields": {...}}, ...]}`. This is the
    shape the pre-F-03 test suite never constructed (it only exercised a
    flat one-level dict), which is exactly how the non-recursive F-2.0-14
    cap's gap went undetected: a hostile 5,000,000-char value inside a
    graph node's `fields` reaches this path unchanged under the old code.
    """
    hostile_row = {
        "node_id": "gene:7157",
        "fields": {"description": "d" * 5_000_000, "symbol": "TP53"},
    }
    structured_fields = {
        "status": "ok",
        "row_count": 3,
        "total_available": 3,
        "truncated": False,
        "rows": [hostile_row, hostile_row, hostile_row],
        "error": None,
    }
    before = _json_bytes(structured_fields)

    finding = await _pass_through_one(structured_fields)

    after = _json_bytes(finding.structured_fields)
    assert before > 15_000_000  # sanity: the hostile input really is huge
    assert after <= 50_000  # _MAX_FINDING_TOTAL_BYTES
    assert finding.truncated is True
    # the nested hostile description string is gone from the output at
    # anything like its original size, wherever it survived at all
    for row in finding.structured_fields.get("rows", []):
        description = row.get("fields", {}).get("description", "")
        # Item 11.33, 2026-09-22: the cap rose to the finding's own bound (2000).
        assert len(description) <= 2000


@pytest.mark.asyncio
async def test_measured_case_five_level_nest_with_ten_million_char_leaf() -> None:
    """Judge's measured case 1: 5-level nest with a 10,000,000-char leaf.
    Before F-03: 10,000,062 -> 10,000,062 bytes, UNBOUNDED (the leaf never
    reached a string cap because the nesting was more than one dict level
    deep, past what the old one-level `_cap_dict_one_level` covered).
    """
    nested = {"level1": {"level2": {"level3": {"level4": {"level5": "x" * 10_000_000}}}}}
    before = _json_bytes(nested)
    assert before > 10_000_000

    finding = await _pass_through_one(nested)

    after = _json_bytes(finding.structured_fields)
    assert after < 10_000  # collapsed from ~10,000,062 bytes
    assert finding.truncated is True
    leaf = finding.structured_fields["level1"]["level2"]["level3"]["level4"]["level5"]
    # Item 11.33, 2026-09-22: one string cap at every depth, at the finding's
    # own bound (2000), replacing the unreachable 2000/reachable 500 pair.
    assert len(leaf) <= 2000


@pytest.mark.asyncio
async def test_measured_case_list_of_lists() -> None:
    """Judge's measured case 2: a list of lists. Before F-03: 10,000,023
    -> 10,000,023 bytes, UNBOUNDED. The old list branch capped a dict item
    but handed a nested LIST item straight to `_cap_leaf_value`, which
    only special-cased `str` and returned every other type, including a
    list, unchanged.
    """
    list_of_lists = {"data": [["y" * 5_000_000, "y" * 5_000_000]]}
    before = _json_bytes(list_of_lists)
    assert before > 10_000_000

    finding = await _pass_through_one(list_of_lists)

    after = _json_bytes(finding.structured_fields)
    assert after < 10_000  # collapsed from ~10,000,023 bytes
    assert finding.truncated is True
    inner_list = finding.structured_fields["data"][0]
    # Item 11.33, 2026-09-22: the cap rose to the finding's own bound (2000).
    assert all(len(item) <= 2000 for item in inner_list)


@pytest.mark.asyncio
async def test_measured_case_dict_of_dicts_of_dicts() -> None:
    """Judge's measured case 3: dict -> dict -> dict. Before F-03:
    10,000,023 -> 10,000,023 bytes, UNBOUNDED, for the same reason as the
    5-level nest above: only one dict level was ever capped.
    """
    triple_nested = {"outer": {"middle": {"inner": "z" * 10_000_000}}}
    before = _json_bytes(triple_nested)
    assert before > 10_000_000

    finding = await _pass_through_one(triple_nested)

    after = _json_bytes(finding.structured_fields)
    assert after < 10_000  # collapsed from ~10,000,023 bytes
    assert finding.truncated is True
    # Item 11.33, 2026-09-22: the cap rose to the finding's own bound (2000).
    assert len(finding.structured_fields["outer"]["middle"]["inner"]) <= 2000


@pytest.mark.asyncio
async def test_measured_case_single_massive_dict_key() -> None:
    """Judge's measured case 4: a single 1,000,000-char dict key. Before
    F-03: 1,000,009 -> 1,000,009 bytes, UNBOUNDED. Dict KEYS were never
    length-capped at all, only dict values were.
    """
    massive_key = "k" * 1_000_000
    payload = {massive_key: "small value"}
    before = _json_bytes(payload)
    assert before > 1_000_000

    finding = await _pass_through_one(payload)

    after = _json_bytes(finding.structured_fields)
    assert after < 1_000  # collapsed from ~1,000,009 bytes
    assert finding.truncated is True
    (capped_key,) = finding.structured_fields.keys()
    assert len(capped_key) <= 200  # _MAX_STRUCTURED_KEY_CHARS


@pytest.mark.asyncio
async def test_recursion_depth_is_bounded_not_just_the_output() -> None:
    """A structure nested far past any real tool's output shape must not
    grow the recursion past a fixed ceiling: no RecursionError, no stack
    overflow, and the over-depth subtree is replaced rather than ever
    descended into. 200 levels comfortably exceeds
    `_MAX_STRUCTURED_DEPTH` (8) many times over.
    """
    deeply_nested: dict[str, object] = {"leaf": "bottom"}
    for _ in range(200):
        deeply_nested = {"child": deeply_nested}

    # Must complete without raising RecursionError.
    finding = await _pass_through_one(deeply_nested)

    assert finding.truncated is True
    after = _json_bytes(finding.structured_fields)
    assert after < 1_000  # the over-depth subtree was replaced, not descended into


@pytest.mark.asyncio
async def test_total_size_ceiling_shrinks_composed_rows_past_per_field_caps() -> None:
    """Even a payload that is already within every per-field cap (a
    well-formed 30-property row, repeated across many rows) can compose
    past a reasonable total size. Mirrors the report's own 7.7 MB example:
    30 properties x 500 chars x 500 rows, none of it individually over any
    per-field cap, still needs the total ceiling to bound it.

    RE-MEASURED 2026-09-22 (item 11.33), because the per-string cap rose
    from 500 to 2000 and a fixture built from 500-character values needed
    checking rather than assuming: before 7,735,603 bytes, after 46,516
    bytes, 3 of 500 rows kept. Those figures are UNCHANGED by the cap
    change, and that is the point of recording them: this fixture's values
    are 500 characters, which sits under the old cap and the new one
    alike, so no per-field capping runs here at all and the byte ceiling
    alone does the work. The fixture still exercises what it was written
    for.
    """
    row = {"node_id": "n1", "fields": {f"prop_{i}": "v" * 500 for i in range(30)}}
    structured_fields = {
        "status": "ok",
        "row_count": 500,
        "total_available": 500,
        "truncated": False,
        "rows": [dict(row) for _ in range(500)],
        "error": None,
    }
    before = _json_bytes(structured_fields)
    assert before > 7_000_000  # matches the report's measured 7.7 MB figure

    finding = await _pass_through_one(structured_fields)

    after = _json_bytes(finding.structured_fields)
    assert after <= 50_000  # _MAX_FINDING_TOTAL_BYTES
    assert finding.truncated is True
    # some rows survive; the ceiling shrinks the list, it does not empty it
    assert len(finding.structured_fields["rows"]) >= 1


@pytest.mark.asyncio
async def test_row_count_is_reconciled_against_the_rows_the_byte_ceiling_actually_kept() -> None:
    """F-2.1-C12 (adversary, third pass): confirmed failing against the
    pre-fix code. The byte ceiling shrinks `rows` from 500 down to a
    fraction of that, but `row_count`, a plain integer with nothing of its
    own to cap, kept reporting the pre-cut value of 500. Any caller
    reading `row_count`, the natural field to read, was off by a factor of
    several times. `row_count` must always agree with `len(rows)` once
    capping has run.

    RE-MEASURED 2026-09-22 (item 11.33), and the figure in this docstring
    was corrected rather than left: it said 118 survivors, and the shipped
    code keeps 3. The 118 is not reproducible against this fixture today.
    The assertion below has always been a range rather than that number,
    so the arm was measuring the right property while the prose beside it
    named a stale one, which is why only the prose changed. The 3 is
    unchanged by the cap rising from 500 to 2000, since this fixture's
    500-character values sit under both caps.
    """
    row = {"node_id": "n1", "fields": {f"prop_{i}": "v" * 500 for i in range(30)}}
    structured_fields = {
        "status": "ok",
        "row_count": 500,
        "total_available": 500,
        "truncated": False,
        "rows": [dict(row) for _ in range(500)],
        "error": None,
    }

    finding = await _pass_through_one(structured_fields)

    kept = len(finding.structured_fields["rows"])
    assert 0 < kept < 500, "the byte ceiling must actually have shrunk the rows list for this fixture"
    assert finding.structured_fields["row_count"] == kept, (
        "row_count must be recomputed from the rows the byte ceiling actually kept, "
        "not left at its pre-cut value"
    )


# ---------------------------------------------------------------------------
# Item 11.33 (2026-09-22): one string cap at every depth, at the finding's own
# bound, cutting on a word boundary.
#
# Every arm below FAILS against the pre-fix code, which capped a nested string
# at 500 characters with a hard mid-word slice and no ellipsis. Each names what
# the pre-fix code returned, so a reader can tell the arm apart from a
# tautology.
#
# What these arms do NOT cover, stated so the gap is arguable rather than
# invisible (`goal-contracts.md`): they exercise string leaves only. The list,
# dict-key, depth and byte-ceiling caps are covered by the F-03 arms above and
# are unchanged by this fix.
# ---------------------------------------------------------------------------


def test_the_harness_string_cap_equals_the_finding_schemas_own_bound() -> None:
    """Item 11.33. The harness cap is written as a literal because
    `synthesis.findings` imports `Finding` from `harness.coordinator_worker`,
    so importing the constant back would be circular. A literal can drift
    from the thing it copies, and this arm is what makes that drift a build
    failure rather than a silent re-run of the original defect: a cap here
    TIGHTER than the finding's own bound undercuts it invisibly, which is
    exactly what 500 did.

    THIS ARM PASSES AGAINST THE PRE-FIX CODE, and that is recorded rather
    than dressed up. `_MAX_STRUCTURED_STRING_CHARS` was already 2000
    before the fix; it was simply unreachable, so the equality held
    vacuously while the shipped behaviour was 500. An arm asserting a
    constant's VALUE cannot see that, which is precisely the defect
    shape item 11.33 turned out to be. The arm that does see it is
    `test_one_string_cap_applies_at_every_depth` below, which exercises
    the function rather than reading the constant. This one guards a
    different and narrower thing: future drift of the literal.
    """
    from system_03_search_agent.synthesis.findings import MAX_FIELD_VALUE_CHARS

    assert coordinator_worker_module._MAX_STRUCTURED_STRING_CHARS == MAX_FIELD_VALUE_CHARS, (
        "the harness's per-string cap and SynthFinding.field_value's bound must "
        "move together; if you changed one, change the other"
    )


def test_one_string_cap_applies_at_every_depth() -> None:
    """Item 11.33. The deleted two-tier design is not allowed back by the
    side door. `_cap_scalar_string` must return the same bound whatever
    depth it is told, since `_cap_structured_fields` passes the dict at
    depth 0 and no string leaf can ever be at depth 0.

    FAILS against the pre-fix code: depth 0 gave 2000 and depth 1 gave 500.
    """
    value = "word " * 600  # 3000 chars
    lengths = {
        depth: len(coordinator_worker_module._cap_scalar_string(value, depth)[0])
        for depth in (0, 1, 2, 5)
    }
    assert len(set(lengths.values())) == 1, f"the cap must not vary with depth: {lengths}"


def _real_gene_summary_length_value() -> str:
    """A 1253-character multi-sentence value, the length of the real BRCA1
    gene summary that item 11.33 was reported against."""
    sentence = "This gene encodes a nuclear phosphoprotein that acts as a tumor suppressor. "
    value = (sentence * 20)[:1253]
    assert len(value) == 1253
    return value


@pytest.mark.asyncio
async def test_a_value_the_length_of_a_real_gene_summary_passes_through_intact() -> None:
    """Item 11.33 (a). The defect, in one arm: the BRCA1 gene summary is
    1253 characters and reached the reader at 500, cut mid-word. It is
    under the finding's own 2000-character bound, so nothing here should
    touch it at all.

    FAILS against the pre-fix code: the nested cap was 500, so the value
    came back at length 500 with `truncated` True.
    """
    value = _real_gene_summary_length_value()
    structured_fields = {
        "status": "ok",
        "row_count": 1,
        "rows": [{"curie": "", "node_or_edge_type": "gene", "fields": {"summary": value}}],
        "error": None,
    }

    finding = await _pass_through_one(structured_fields)

    assert finding.structured_fields["rows"][0]["fields"]["summary"] == value
    assert finding.truncated is False, "a value inside the cap must not be reported as cut"


@pytest.mark.asyncio
async def test_an_over_cap_nested_value_is_cut_on_a_word_boundary_with_an_ellipsis() -> None:
    """Item 11.33 (b). A value past the cap is still cut, but visibly and
    never mid-word.

    FAILS against the pre-fix code three separate ways: the length came
    back 500 rather than at or under 2000, there was no ellipsis, and the
    final character was mid-word.
    """
    value = ("alpha beta gamma delta epsilon " * 100)[:3000]
    assert len(value) == 3000
    structured_fields = {
        "rows": [{"fields": {"abstract": value}}],
    }

    finding = await _pass_through_one(structured_fields)

    out = finding.structured_fields["rows"][0]["fields"]["abstract"]
    assert len(out) <= 2000, "the cut value must never exceed the cap"
    assert out.endswith("…"), "a cut must be visible to the reader"
    assert not out.endswith("……"), "one ellipsis, never two"
    assert finding.truncated is True
    # The word-boundary property, stated directly rather than by proxy: the
    # text before the ellipsis is a prefix of the source ending at a space.
    body = out[:-1]
    assert value.startswith(body), "the kept text must be the source's own prefix"
    assert value[len(body)] == " ", "the cut must land on a word boundary"


@pytest.mark.asyncio
async def test_a_string_directly_under_the_top_level_dict_gets_the_same_cap() -> None:
    """Item 11.33 (c). The two-tier design's depth-0 tier was unreachable,
    so this position was capped at 500 while a 2000 constant sat unused.
    One cap now applies here and everywhere else alike.

    FAILS against the pre-fix code: a 3000-character top-level string came
    back at 500, not at 2000.
    """
    value = "word " * 600  # 3000 chars, whitespace throughout
    structured_fields = {"error": value}

    finding = await _pass_through_one(structured_fields)

    out = finding.structured_fields["error"]
    assert 500 < len(out) <= 2000, (
        "a string directly under the top-level dict must get the same cap as a "
        "nested one; 500 here means the dead depth-0 tier is back"
    )
    assert out.endswith("…")
    assert finding.truncated is True


@pytest.mark.asyncio
async def test_a_value_with_no_whitespace_before_the_cap_is_cut_at_the_cap() -> None:
    """Item 11.33 (d). A long identifier or HGVS name has no word boundary
    to honour. It is cut hard at the cap with NO ellipsis, because
    appending one would push the result past the cap this function exists
    to enforce, and because breaking such a value at an arbitrary point is
    worse than a clean cut. Same rule as `answer_layout.clip_to_word`.

    FAILS against the pre-fix code: the value came back at 500, not 2000.
    """
    value = "N" * 2500 + " tail"
    structured_fields = {"rows": [{"fields": {"hgvs": value}}]}

    finding = await _pass_through_one(structured_fields)

    out = finding.structured_fields["rows"][0]["fields"]["hgvs"]
    assert len(out) == 2000, "no word boundary means a hard cut at the cap, never past it"
    assert not out.endswith("…"), "no ellipsis when there was no word boundary to cut at"
    assert finding.truncated is True


@pytest.mark.asyncio
async def test_a_harness_cut_value_never_renders_a_double_ellipsis() -> None:
    """Item 11.33, the label path. `answer_layout.clip_to_word` clips a
    finding's value again for a list row's label, and now receives values
    that may already end in an ellipsis. Two ellipses would read as a
    defect.

    It cannot happen, and this arm is the proof rather than the argument.
    When `clip_to_word` cuts, it cuts strictly before the existing
    ellipsis, which is therefore discarded; when it does not cut, it
    returns the value unchanged with the one ellipsis it already had.
    Checked at a limit below the value, at the value's own length, and
    above it.

    This is the one arm here that reaches across into `synthesis`. The
    PRODUCTION dependency still runs one way only, synthesis -> harness: a
    test importing both is not an import from harness into synthesis.
    """
    from system_03_search_agent.synthesis.answer_layout import clip_to_word

    value = ("alpha beta gamma delta epsilon " * 200)[:6000]
    finding = await _pass_through_one({"rows": [{"fields": {"summary": value}}]})
    capped = finding.structured_fields["rows"][0]["fields"]["summary"]
    assert capped.endswith("…"), "premise of this arm: the harness cut and marked the value"

    for limit in (200, 500, len(capped), len(capped) + 10):
        label = clip_to_word(capped, limit)
        assert not label.endswith("……"), f"double ellipsis at limit {limit}"
        assert len(label) <= max(limit, len(capped))
