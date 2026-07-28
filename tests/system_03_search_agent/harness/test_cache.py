"""Tests for the prompt-cache stable-prefix scaffold (T-2.0-06).

Depends on:
    - system_03_search_agent.harness.cache (build_stable_prefix,
      prefix_sha256, and the module's internal section markers, imported
      only to assert marker ordering/positioning, never to duplicate the
      assembly logic under test)
"""

from __future__ import annotations

import pytest

from system_03_search_agent.harness.cache import (
    _BIOLINK_CONCEPT_SCHEMA,
    _GRAPH_SCHEMA_END,
    _GRAPH_SCHEMA_START,
    _TOOL_SCHEMAS_END,
    _TOOL_SCHEMAS_START,
    SYSTEM_INSTRUCTIONS,
    build_stable_prefix,
    prefix_sha256,
)

# ---------------------------------------------------------------------------
# Acceptance criterion 1: assembly order.
# ---------------------------------------------------------------------------


def test_sections_appear_in_fixed_order_with_no_tool_schemas() -> None:
    prefix = build_stable_prefix()

    system_idx = prefix.index(SYSTEM_INSTRUCTIONS)
    tool_start_idx = prefix.index(_TOOL_SCHEMAS_START)
    tool_end_idx = prefix.index(_TOOL_SCHEMAS_END)
    graph_start_idx = prefix.index(_GRAPH_SCHEMA_START)
    graph_end_idx = prefix.index(_GRAPH_SCHEMA_END)

    assert system_idx < tool_start_idx < tool_end_idx < graph_start_idx < graph_end_idx


def test_sections_appear_in_fixed_order_with_tool_schemas() -> None:
    tool_schemas = [
        {"name": "cypher_query", "description": "Query the graph"},
        {"name": "ncbi_efetch", "description": "Fetch an NCBI record"},
    ]
    prefix = build_stable_prefix(tool_schemas)

    system_idx = prefix.index(SYSTEM_INSTRUCTIONS)
    tool_start_idx = prefix.index(_TOOL_SCHEMAS_START)
    tool_end_idx = prefix.index(_TOOL_SCHEMAS_END)
    graph_start_idx = prefix.index(_GRAPH_SCHEMA_START)
    graph_end_idx = prefix.index(_GRAPH_SCHEMA_END)

    assert system_idx < tool_start_idx < tool_end_idx < graph_start_idx < graph_end_idx


# ---------------------------------------------------------------------------
# Acceptance criterion 2: byte-equality of the prefix across differing
# dynamic suffixes. build_stable_prefix() takes no suffix parameter by
# design, so the point is proven downstream: build two full `messages`
# lists (prefix + different fake dynamic content) and assert the PREFIX
# portion's SHA-256 is identical across both, while the full messages
# differ.
# ---------------------------------------------------------------------------


def _fake_messages(prefix: str, dynamic_suffix: str) -> list[dict[str, str]]:
    """Simulate what a caller sends to Harness.call_tier: the prefix as a
    leading system message, followed by dynamic, per-request content.
    Mirrors harness.py's `_with_cache_prefix` shape without importing it,
    since this test targets cache.py's guarantee, not harness.py's
    wiring.
    """
    return [
        {"role": "system", "content": prefix},
        {"role": "user", "content": dynamic_suffix},
    ]


def test_prefix_byte_identical_across_differing_dynamic_suffixes() -> None:
    tool_schemas = [{"name": "pubtator_annotate"}, {"name": "cypher_query"}]

    prefix_call_one = build_stable_prefix(tool_schemas)
    prefix_call_two = build_stable_prefix(tool_schemas)

    messages_one = _fake_messages(prefix_call_one, "current query: BRCA1 variants")
    messages_two = _fake_messages(prefix_call_two, "current query: gene TP53 orthologs")

    # The full messages differ (different dynamic suffix)...
    assert messages_one != messages_two

    # ...but the prefix portion (the leading system message) is byte-identical.
    assert prefix_sha256(messages_one[0]["content"]) == prefix_sha256(
        messages_two[0]["content"]
    )
    assert messages_one[0]["content"] == messages_two[0]["content"]


# ---------------------------------------------------------------------------
# Acceptance criterion 3: no volatile token leaks into the prefix. Call
# from two code paths that differ only in an unrelated trace_id/current-
# time variable in scope, and assert the returned string is unchanged.
# ---------------------------------------------------------------------------


def _build_prefix_in_scope_with_trace_id(trace_id: str) -> str:
    """A stand-in for a real call site: a trace_id is in local scope (as
    it would be inside a Harness instance, minted at the Guardrail step),
    but build_stable_prefix takes no such argument and must not pick it
    up from the caller's scope.
    """
    _ = trace_id  # in scope, deliberately unused by build_stable_prefix
    return build_stable_prefix()


def test_no_volatile_token_leaks_across_differing_trace_ids() -> None:
    prefix_a = _build_prefix_in_scope_with_trace_id("trace-aaaa-11111")
    prefix_b = _build_prefix_in_scope_with_trace_id("trace-bbbb-99999")

    assert prefix_a == prefix_b
    assert prefix_sha256(prefix_a) == prefix_sha256(prefix_b)


def test_no_volatile_token_leaks_across_differing_simulated_timestamps() -> None:
    import time

    _ = time.time()  # simulate "current time" in scope at call site A
    prefix_at_t1 = build_stable_prefix()

    _ = time.time() + 3600  # simulate a different "current time" at call site B
    prefix_at_t2 = build_stable_prefix()

    assert prefix_at_t1 == prefix_at_t2


def test_no_timestamp_or_id_like_tokens_in_assembled_prefix() -> None:
    prefix = build_stable_prefix([{"name": "clinicaltrials_search"}])

    # Defensive literal check: none of these ever appear as substrings
    # anywhere in the static constants this module assembles.
    for forbidden in ("trace_id", "session_id", "request_id", "timestamp"):
        assert forbidden not in prefix


# ---------------------------------------------------------------------------
# Acceptance criterion 4: tool-schema sort order is fixed in code
# (alphabetic by name), regardless of input order, and idempotent.
# ---------------------------------------------------------------------------


def test_tool_schemas_sorted_alphabetically_regardless_of_input_order() -> None:
    unsorted_input = [
        {"name": "pubtator_annotate"},
        {"name": "cypher_query"},
        {"name": "ncbi_efetch"},
    ]
    already_sorted_input = [
        {"name": "cypher_query"},
        {"name": "ncbi_efetch"},
        {"name": "pubtator_annotate"},
    ]

    prefix_from_unsorted = build_stable_prefix(unsorted_input)
    prefix_from_sorted = build_stable_prefix(already_sorted_input)

    # Same set of schemas, different input order -> identical output.
    assert prefix_from_unsorted == prefix_from_sorted

    # And the serialized order inside the prefix is actually alphabetic:
    # cypher_query's serialized position precedes ncbi_efetch's, which
    # precedes pubtator_annotate's.
    idx_cypher = prefix_from_unsorted.index("cypher_query")
    idx_efetch = prefix_from_unsorted.index("ncbi_efetch")
    idx_pubtator = prefix_from_unsorted.index("pubtator_annotate")
    assert idx_cypher < idx_efetch < idx_pubtator


def test_tool_schema_sort_is_idempotent_on_already_sorted_input() -> None:
    sorted_input = [
        {"name": "clinicaltrials_search"},
        {"name": "cypher_query"},
        {"name": "litvar2_lookup"},
    ]

    first_call = build_stable_prefix(sorted_input)
    second_call = build_stable_prefix(list(sorted_input))  # fresh list, same order

    assert first_call == second_call


def test_tool_schemas_serialized_deterministically_regardless_of_dict_key_order() -> None:
    schema_key_order_one = [{"name": "cypher_query", "description": "d", "timeout": 30}]
    schema_key_order_two = [{"timeout": 30, "description": "d", "name": "cypher_query"}]

    prefix_one = build_stable_prefix(schema_key_order_one)
    prefix_two = build_stable_prefix(schema_key_order_two)

    assert prefix_one == prefix_two


# ---------------------------------------------------------------------------
# Acceptance criterion 5: empty tool_schemas (None or []) works, and the
# slot's position is stable, verified via the boundary markers rather
# than a fragile length/offset check. A future phase that starts passing
# real schemas fills content strictly between the same two markers; it
# does not need the surrounding assembly to change shape.
# ---------------------------------------------------------------------------


def test_none_tool_schemas_produces_empty_slot_between_markers() -> None:
    prefix = build_stable_prefix(None)
    empty_slot = f"{_TOOL_SCHEMAS_START}\n{_TOOL_SCHEMAS_END}"
    assert empty_slot in prefix


def test_empty_list_tool_schemas_produces_empty_slot_between_markers() -> None:
    prefix = build_stable_prefix([])
    empty_slot = f"{_TOOL_SCHEMAS_START}\n{_TOOL_SCHEMAS_END}"
    assert empty_slot in prefix


def test_none_and_empty_list_produce_byte_identical_prefixes() -> None:
    assert build_stable_prefix(None) == build_stable_prefix([])


def test_tool_schema_slot_position_stable_when_schemas_are_added() -> None:
    """Verifies "position stability" the way the ticket asks: the two
    boundary markers sit at the same relative position in the section
    order (strictly after SYSTEM_INSTRUCTIONS, strictly before the graph
    schema section) whether the slot is empty or populated. Populating
    the slot changes the *content* between the markers and therefore the
    overall byte length, which is expected and correct: only the slot's
    *position in the section order* is a drop-in, not its byte offset.
    """
    empty_prefix = build_stable_prefix(None)
    populated_prefix = build_stable_prefix([{"name": "ncbi_dbsnp"}])

    for prefix in (empty_prefix, populated_prefix):
        system_idx = prefix.index(SYSTEM_INSTRUCTIONS)
        tool_start_idx = prefix.index(_TOOL_SCHEMAS_START)
        tool_end_idx = prefix.index(_TOOL_SCHEMAS_END)
        graph_start_idx = prefix.index(_GRAPH_SCHEMA_START)
        assert system_idx < tool_start_idx < tool_end_idx < graph_start_idx

    # The populated slot actually contains the schema; the empty one does not.
    assert "ncbi_dbsnp" in populated_prefix
    assert "ncbi_dbsnp" not in empty_prefix


# ---------------------------------------------------------------------------
# Supporting checks: the static graph/BioLink schema section itself, and
# prefix_sha256's basic contract.
# ---------------------------------------------------------------------------


def test_biolink_concept_schema_is_static_module_constant() -> None:
    # Sanity check that the concept-level schema is a fixed constant, not
    # rebuilt per call from any external or mutable source.
    prefix_one = build_stable_prefix()
    prefix_two = build_stable_prefix()
    assert _BIOLINK_CONCEPT_SCHEMA in prefix_one
    assert _BIOLINK_CONCEPT_SCHEMA in prefix_two


def test_prefix_sha256_is_deterministic_and_sensitive_to_content() -> None:
    prefix_a = build_stable_prefix()
    prefix_b = build_stable_prefix()
    prefix_c = build_stable_prefix([{"name": "cypher_query"}])

    assert prefix_sha256(prefix_a) == prefix_sha256(prefix_b)
    assert prefix_sha256(prefix_a) != prefix_sha256(prefix_c)
    assert len(prefix_sha256(prefix_a)) == 64  # hex-encoded SHA-256


def test_build_stable_prefix_has_no_dynamic_suffix_parameter() -> None:
    """Deliberate signature check: build_stable_prefix must not accept a
    suffix-shaped keyword. This is the anti-conflation guarantee the
    ticket calls out explicitly: the function's shape itself proves the
    dynamic suffix can never be merged into the stable prefix by a caller
    passing "just one more argument".
    """
    with pytest.raises(TypeError):
        build_stable_prefix(tool_schemas=None, dynamic_suffix="anything")  # type: ignore[call-arg]
