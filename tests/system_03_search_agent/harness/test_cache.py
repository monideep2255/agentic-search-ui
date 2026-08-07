"""Tests for the prompt-cache stable-prefix scaffold (T-2.0-06), plus the
fixed tool registry T-3.1-12 adds to it.

Depends on:
    - system_03_search_agent.harness.cache (build_stable_prefix,
      prefix_sha256, REGISTERED_TOOL_SCHEMAS, and the module's internal
      section markers, imported only to assert marker ordering/positioning
      or registry content, never to duplicate the assembly logic under
      test)
"""

from __future__ import annotations

import json

import pytest

from system_03_search_agent.harness.cache import (
    _BIOLINK_CONCEPT_SCHEMA,
    _GRAPH_SCHEMA_END,
    _GRAPH_SCHEMA_START,
    _TOOL_REGISTRY_FINGERPRINTS,
    _TOOL_SCHEMAS_END,
    _TOOL_SCHEMAS_START,
    REGISTERED_TOOL_SCHEMAS,
    SYSTEM_INSTRUCTIONS,
    TOOL_REGISTRY_VERSION,
    build_stable_prefix,
    prefix_sha256,
    tool_registry_fingerprint,
    verify_tool_registry_version,
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


# ---------------------------------------------------------------------------
# T-3.1-12: the fixed, code-level tool registry (REGISTERED_TOOL_SCHEMAS).
#
# These tests exercise the registry's actual content, not synthetic
# `{"name": ...}` stand-ins, closing the gap `prompt-cache-discipline.md`'s
# "How to verify" section names: a byte-equality assertion proven only
# against placeholder content would not catch a real schema (e.g. a
# `model_json_schema()` call that quietly started embedding something
# volatile) from breaking the stable-prefix guarantee.
# ---------------------------------------------------------------------------


def test_registered_tool_schemas_is_fixed_in_code_as_a_tuple() -> None:
    """A tuple, not a list: this registry must not be the kind of thing a
    caller can `.append()` to at runtime, which is the concrete form
    obligation 1's "the tool list never changes mid-session" takes here.
    """
    assert isinstance(REGISTERED_TOOL_SCHEMAS, tuple)
    for schema in REGISTERED_TOOL_SCHEMAS:
        assert isinstance(schema, dict)
        assert "name" in schema


def test_registered_tool_schemas_contains_exactly_the_two_built_tools() -> None:
    """Only `cypher_query` and `ncbi_efetch` exist as of this ticket. The
    other five names Technical_specification.md Section 4.2 reserves
    (`clinicaltrials_search`, `litvar2_lookup`, `ncbi_dbsnp`,
    `pathogen_detection`, `pubtator_annotate`) are not yet built and must
    not appear here as placeholders.
    """
    names = [schema["name"] for schema in REGISTERED_TOOL_SCHEMAS]
    assert names == ["cypher_query", "ncbi_efetch"], (
        f"expected exactly [cypher_query, ncbi_efetch] in that order, got {names!r}"
    )


def test_registered_tool_schemas_written_in_alphabetical_order() -> None:
    """obligation 2: sorted alphabetically and fixed in code. This checks
    the registry's OWN written order (not `_build_tool_schema_section`'s
    defensive re-sort, which the earlier tests in this file already cover
    against synthetic input), since a registry that relies entirely on the
    re-sort to be correct is not itself "fixed in code" in the sense the
    rule means.
    """
    names = [schema["name"] for schema in REGISTERED_TOOL_SCHEMAS]
    assert names == sorted(names)


def test_registered_tool_schemas_ncbi_efetch_input_schema_matches_the_model() -> None:
    """The registered `ncbi_efetch` entry's `input_schema` is generated
    from `NcbiEfetchInput.model_json_schema()`, the same validated
    contract the tool itself enforces, never a hand-written paraphrase
    that can silently drift out of sync with it.
    """
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

    entry = next(s for s in REGISTERED_TOOL_SCHEMAS if s["name"] == "ncbi_efetch")
    assert entry["input_schema"] == NcbiEfetchInput.model_json_schema()


def test_registered_prefix_byte_identical_across_differing_dynamic_suffixes() -> None:
    """The rule's own required proof (`prompt-cache-discipline.md`'s "How
    to verify"), run against the REAL registered content rather than a
    synthetic stand-in: a SHA-256 over the assembled prefix must be
    identical across two requests whose dynamic suffix differs.
    """
    tool_schemas = list(REGISTERED_TOOL_SCHEMAS)

    prefix_call_one = build_stable_prefix(tool_schemas)
    prefix_call_two = build_stable_prefix(tool_schemas)

    messages_one = _fake_messages(prefix_call_one, "current query: BRCA1 variants")
    messages_two = _fake_messages(prefix_call_two, "current query: gene TP53 orthologs")

    assert messages_one != messages_two
    assert prefix_sha256(messages_one[0]["content"]) == prefix_sha256(
        messages_two[0]["content"]
    )
    assert messages_one[0]["content"] == messages_two[0]["content"]


def test_prefix_from_registered_tool_schemas_is_byte_identical_across_repeated_calls() -> None:
    """Adding `ncbi_efetch` to the registry must be the ONLY prefix change
    this ticket makes. Two independent `build_stable_prefix` calls given
    the same registry content must produce byte-identical output, proven
    by SHA-256 rather than `==` alone so the check matches the rule's own
    stated verification method.
    """
    tool_schemas = list(REGISTERED_TOOL_SCHEMAS)

    first = build_stable_prefix(tool_schemas)
    second = build_stable_prefix(tool_schemas)

    assert prefix_sha256(first) == prefix_sha256(second)
    assert first == second


def test_cypher_query_sorts_before_ncbi_efetch_in_the_assembled_prefix() -> None:
    """Binding point from the ticket brief: ncbi_efetch sorts after
    cypher_query and before ncbi_dbsnp (not yet built, so only the first
    half of that ordering is checkable today).
    """
    prefix = build_stable_prefix(list(REGISTERED_TOOL_SCHEMAS))

    idx_cypher_query = prefix.index('"cypher_query"')
    idx_ncbi_efetch = prefix.index('"ncbi_efetch"')
    assert idx_cypher_query < idx_ncbi_efetch


def test_registered_tool_schemas_content_appears_serialized_in_the_prefix() -> None:
    """Both registered tools' names and a piece of each one's real
    `input_schema` content (not just the bare name) must appear in the
    assembled prefix, proving the registry's actual schema content is
    what gets serialized, not merely a name-only stand-in.
    """
    prefix = build_stable_prefix(list(REGISTERED_TOOL_SCHEMAS))

    for schema in REGISTERED_TOOL_SCHEMAS:
        serialized = json.dumps(schema, sort_keys=True)
        assert serialized in prefix, (
            f"expected {schema['name']!r}'s full serialized schema inside "
            f"the tool-schema slot"
        )


# ---------------------------------------------------------------------------
# F-3.1-11 (reopened): the tool-registry contract-version gate.
#
# `system-design-patterns` pattern 10: "a tool-registry change, adding or
# removing a tool, is coordinated with a contract-version bump. Never
# silent." Before these tests, `TOOL_REGISTRY_VERSION` was a string nothing
# imported, nothing tested, and nothing enforced, so build phase 3.2 could
# have registered `ncbi_dbsnp` with the version still reading "v2" and no
# check anywhere would have failed.
#
# The two expectations below are hardcoded on purpose. Registering the next
# tool must break this file, forcing the version, the fingerprint ledger in
# `cache.py`, and these literals to be edited together in one conscious
# change. Updating only the literals to make a failure go away is the
# reward-hacking move `goal-contracts` forbids: it re-weakens the check
# instead of doing the coordination the check exists to force.
#
# Coverage this gate deliberately omits (goal-contracts, "a verify surface
# must state its own coverage"): membership only, never a tool's
# `input_schema` content. A new field on `NcbiEfetchInput` moves the prefix
# bytes but adds no tool, so it is not a registry-contract event and this
# gate stays green for it by design. The byte-equality tests above own that
# case.
# ---------------------------------------------------------------------------

EXPECTED_TOOL_REGISTRY_VERSION = "v2"
EXPECTED_TOOL_REGISTRY_FINGERPRINT = "99358f2c0c86"  # cypher_query, ncbi_efetch

_FAKE_TOOL_SCHEMA = {
    "name": "ncbi_dbsnp",
    "description": "A tool that is not registered yet.",
    "input_schema": {"type": "object", "properties": {}},
}


def test_tool_registry_version_and_fingerprint_are_both_pinned() -> None:
    """The gate itself: the live registry's membership fingerprint and the
    declared contract version must both match what this file pins. Adding
    or removing a tool changes the fingerprint and fails here until
    `TOOL_REGISTRY_VERSION` is bumped and these literals are updated with
    it.
    """
    assert TOOL_REGISTRY_VERSION == EXPECTED_TOOL_REGISTRY_VERSION, (
        f"TOOL_REGISTRY_VERSION is {TOOL_REGISTRY_VERSION!r}, expected "
        f"{EXPECTED_TOOL_REGISTRY_VERSION!r}. If the registered tool set "
        f"genuinely changed, update both literals in this file in the same "
        f"change as the bump."
    )
    assert tool_registry_fingerprint() == EXPECTED_TOOL_REGISTRY_FINGERPRINT, (
        f"the registered tool set changed: it now fingerprints as "
        f"{tool_registry_fingerprint()!r} over "
        f"{[s['name'] for s in REGISTERED_TOOL_SCHEMAS]!r}. Bump "
        f"TOOL_REGISTRY_VERSION, add the new row to "
        f"_TOOL_REGISTRY_FINGERPRINTS, and update both literals here."
    )
    assert (
        _TOOL_REGISTRY_FINGERPRINTS[EXPECTED_TOOL_REGISTRY_VERSION]
        == EXPECTED_TOOL_REGISTRY_FINGERPRINT
    )


def test_live_registry_passes_the_version_gate() -> None:
    """The shipped registry and its declared version agree, which is also
    what the import-time call in `cache.py` asserts: if this ever stopped
    holding, importing the module would raise before any test ran.
    """
    verify_tool_registry_version()


def test_adding_a_tool_without_bumping_the_version_raises() -> None:
    """The proof the gate is real rather than decorative. A registry with a
    third tool, still claiming version "v2", must fail loudly.
    """
    with pytest.raises(RuntimeError) as excinfo:
        verify_tool_registry_version(
            tool_schemas=(*REGISTERED_TOOL_SCHEMAS, _FAKE_TOOL_SCHEMA),
            version=TOOL_REGISTRY_VERSION,
        )

    message = str(excinfo.value)
    assert "without a contract-version bump" in message
    assert "ncbi_dbsnp" in message
    assert "Bump TOOL_REGISTRY_VERSION" in message


def test_removing_a_tool_without_bumping_the_version_raises() -> None:
    """Pattern 10 names removal as well as addition, so the gate must fire
    in both directions, not only when the registry grows.
    """
    with pytest.raises(RuntimeError, match="without a contract-version bump"):
        verify_tool_registry_version(
            tool_schemas=REGISTERED_TOOL_SCHEMAS[:1],
            version=TOOL_REGISTRY_VERSION,
        )


def test_bumping_the_version_without_changing_the_registry_raises() -> None:
    """Coordination runs both ways: an unchanged registry claiming a
    different declared version is just as silent a contract lie as a
    changed registry claiming the old one.
    """
    with pytest.raises(RuntimeError, match="without a contract-version bump"):
        verify_tool_registry_version(
            tool_schemas=REGISTERED_TOOL_SCHEMAS,
            version="v1",
        )


def test_an_undeclared_version_raises_with_the_ledger_row_to_add() -> None:
    """Bumping the version without adding its ledger row leaves the new
    version unpinned, so the gate refuses it and prints the exact row.
    """
    with pytest.raises(RuntimeError) as excinfo:
        verify_tool_registry_version(
            tool_schemas=REGISTERED_TOOL_SCHEMAS,
            version="v99",
        )

    message = str(excinfo.value)
    assert "no row in _TOOL_REGISTRY_FINGERPRINTS" in message
    assert EXPECTED_TOOL_REGISTRY_FINGERPRINT in message


def test_every_ledger_row_pins_a_distinct_fingerprint() -> None:
    """Two versions mapping to the same fingerprint would mean one of them
    was declared without a real membership change, which makes the ledger
    unable to distinguish them.
    """
    fingerprints = list(_TOOL_REGISTRY_FINGERPRINTS.values())
    assert len(fingerprints) == len(set(fingerprints))
    assert TOOL_REGISTRY_VERSION in _TOOL_REGISTRY_FINGERPRINTS


def test_fingerprint_depends_on_membership_not_written_order() -> None:
    """The fingerprint sorts names before hashing, so re-writing the tuple
    in a different order is not a contract event. Only membership is.
    """
    forward = tool_registry_fingerprint(REGISTERED_TOOL_SCHEMAS)
    reversed_order = tool_registry_fingerprint(tuple(reversed(REGISTERED_TOOL_SCHEMAS)))
    assert forward == reversed_order == EXPECTED_TOOL_REGISTRY_FINGERPRINT


def test_fingerprint_ignores_input_schema_and_description_content() -> None:
    """The declared coverage boundary, asserted rather than only written in
    a comment: editing a tool's description or input schema does not move
    the registry fingerprint, because that is not adding or removing a
    tool. The prefix byte-equality tests above own that case instead.
    """
    edited = tuple(
        {**schema, "description": "edited", "input_schema": {"type": "object"}}
        for schema in REGISTERED_TOOL_SCHEMAS
    )
    assert tool_registry_fingerprint(edited) == EXPECTED_TOOL_REGISTRY_FINGERPRINT
