"""Tests for coordinator_worker_execute (T-2.0-05, extended by T-2.1-08).

Covers the asyncio.gather concurrency guarantee (two artificially delayed
free-text results run their reader passes in parallel, not sequentially),
the free-text/structured branching (a free-text result routes through a
mocked `Harness.call_tier`, a structured result never calls it at all),
the no-raw-text-leak guarantee (a free-text result's returned `Finding`
never contains the original payload substring, including on a reader
response that fails to parse as JSON), the F-2.0-08 closure (the reader
pass now respects the per-query cost cap and a per-step timeout), and the
F-2.0-14 closure (the structured pass-through path caps an oversized
payload before a `Finding` is built).

No real model call is made anywhere in this file: `Harness.call_tier` is
mocked in every test, matching test_harness.py's own convention of never
issuing a real LiteLLM/network call.
"""

from __future__ import annotations

import asyncio
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
    assert all(len(value) <= 500 for value in nested.values() if isinstance(value, str))
    harness.call_tier.assert_not_awaited()  # structured pass-through never calls the reader


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
