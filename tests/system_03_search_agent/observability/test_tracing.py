"""Tests for T-5.0-03, `observability/tracing.py`.

Every test below is built to be able to FAIL: each one exercises an input
that would flip a passing assertion to a failing one under a plausible
wrong implementation (a redaction pass that only checks top-level keys, an
allowlist read from a hardcoded string tuple instead of `model_fields`, a
context manager that constructs a client even with no key configured), not
merely an input that happens to pass today. See `.claude/rules/goal-
contracts.md` and this repository's eleven-instance history of assertions
that could not fail.

Depends on:
    - system_03_search_agent.observability.tracing (the module under test)
    - system_03_search_agent.observability.config (monkeypatched via
      environment variables, never imported for its own logic here)

Reads:
    - Nothing beyond monkeypatched environment variables for the duration
      of each test.

Writes:
    - Nothing. No test in this file constructs a real `langsmith.Client`
      against the network; every client-construction path is mocked out.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from system_03_search_agent.observability import tracing


def _clear_langsmith_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every env var `observability.config` reads for LangSmith, in
    both namespaces, so a test starts from a known "nothing configured"
    baseline regardless of what the developer's own `.env` holds.
    """
    for name in (
        "LANGSMITH_API_KEY",
        "LANGCHAIN_API_KEY",
        "LANGSMITH_PROJECT",
        "LANGCHAIN_PROJECT",
        "LANGSMITH_ENDPOINT",
        "LANGCHAIN_ENDPOINT",
        "LANGSMITH_TRACING_V2",
        "LANGCHAIN_TRACING_V2",
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING",
    ):
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# traced_graph_run: OFF path, no key configured
# ---------------------------------------------------------------------------


def test_traced_graph_run_off_with_flag_but_no_key_builds_no_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact shape of this repository's live critical finding: the flag
    is on (as it is in every `.env` here) but no key is configured.
    `tracing_enabled()` must read False, and the client factory must never
    even be reached, which is the strongest available proof that no
    outbound call is attempted: there is no transport object in existence
    for one to happen through.

    Fails under a wrong implementation that checks only the flag (which is
    True here) rather than `config.tracing_enabled()` (which requires both
    flag and key), since that wrong version would call
    `build_traced_client` and this assertion would catch it red-handed.
    """
    _clear_langsmith_env(monkeypatch)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")

    def _fail_if_called() -> Any:
        raise AssertionError(
            "build_traced_client was called with no API key configured; "
            "this is exactly the outbound-call-with-no-credential failure "
            "F-5.0-03 exists to prevent"
        )

    monkeypatch.setattr(tracing, "build_traced_client", _fail_if_called)

    entered = False
    with tracing.traced_graph_run(run_name="test-run"):
        entered = True
    assert entered


def test_traced_graph_run_off_with_no_flag_and_no_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The simpler negative case: neither the flag nor the key is set.
    Included alongside the flag-only case above because they exercise
    different branches of `tracing_enabled()`'s AND, and a implementation
    could pass one while failing the other.
    """
    _clear_langsmith_env(monkeypatch)

    def _fail_if_called() -> Any:
        raise AssertionError("build_traced_client was called with tracing fully off")

    monkeypatch.setattr(tracing, "build_traced_client", _fail_if_called)

    with tracing.traced_graph_run(run_name="test-run"):
        pass


# ---------------------------------------------------------------------------
# traced_graph_run: ON path, key configured
# ---------------------------------------------------------------------------


def test_traced_graph_run_on_with_flag_and_key_builds_client_and_enables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With both the flag and a key present, tracing must be requested ON,
    with a real (here, mocked) client wired through and the configured
    project name passed along.

    Fails under a wrong implementation that always calls
    `_langsmith_tracing_context(enabled=False)` regardless of
    configuration (i.e. one that never actually turns tracing on at all),
    since `calls[0]["enabled"]` would then be False rather than True.
    """
    _clear_langsmith_env(monkeypatch)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key-123")
    monkeypatch.setenv("LANGSMITH_PROJECT", "test-project")

    sentinel_client = object()
    monkeypatch.setattr(tracing, "build_traced_client", lambda: sentinel_client)

    calls: list[dict[str, Any]] = []

    from contextlib import contextmanager

    @contextmanager
    def _fake_tracing_context(**kwargs: Any):
        calls.append(kwargs)
        yield

    monkeypatch.setattr(tracing, "_langsmith_tracing_context", _fake_tracing_context)

    with tracing.traced_graph_run(run_name="test-run", tags=["t1"]):
        pass

    assert len(calls) == 1
    assert calls[0]["enabled"] is True
    assert calls[0]["client"] is sentinel_client
    assert calls[0]["project_name"] == "test-project"
    assert calls[0]["tags"] == ["t1"]


# ---------------------------------------------------------------------------
# redact_payload: named-field removal
# ---------------------------------------------------------------------------


def test_redact_payload_removes_owner_id_and_user_id_values_from_nested_payload() -> None:
    """A realistic nested payload shaped like what LangGraph would actually
    send: `GraphState` with `query` and `context` sub-dicts. The secret
    values must not merely be absent under their original key; they must
    not appear ANYWHERE in the serialized result, which also catches a
    wrong implementation that moves the value to a different key instead
    of removing it.
    """
    owner_secret = "owner-secret-9f8e7d6c"
    user_secret = "user-secret-1a2b3c4d"

    payload = {
        "query": {
            "text": "which diseases are associated with BRCA1?",
            "session_id": "sess-abc",
            "trace_id": "trace-xyz",
            "user_id": user_secret,
            "owner_id": owner_secret,
            "audience_depth": "researcher",
        },
        "context": {
            "surface": "web_ui",
            "operator_mode": False,
            "session_memory": {
                "session_id": "sess-abc",
                "resolved_entities": [],
                "compressed_findings": [],
                "open_threads": [],
                "token_budget": 1500,
                "last_updated": "2026-08-29T00:00:00Z",
            },
        },
    }

    result = tracing.redact_payload(payload)
    serialized = json.dumps(result, default=str)

    assert owner_secret not in serialized
    assert user_secret not in serialized
    assert result["query"]["owner_id"] != owner_secret
    assert result["query"]["user_id"] != user_secret
    # The question text itself is exactly what Section 20.1 clears for a
    # trace and must survive; this is what stops a too-aggressive fix (one
    # that returns `{}` for any recognized Query) from also passing.
    assert result["query"]["text"] == "which diseases are associated with BRCA1?"
    assert result["query"]["trace_id"] == "trace-xyz"
    # session_memory is dropped wholesale, not selectively redacted inside.
    assert result["context"]["session_memory"] == tracing._REDACTED
    assert result["context"]["surface"] == "web_ui"


def test_redact_payload_catches_a_pii_shaped_field_not_hardcoded() -> None:
    """Proves the CATEGORY rule rather than an enumerated field-name list.

    `access_token` is not one of the three fields the ticket names as the
    minimum bar (owner_id, user_id, session memory), and it is not a
    field on `Query` or `RequestContext` at all, so the structural
    allowlist pass cannot be what catches it. Only a category match on the
    key's normalized name explains a pass here. A hardcoded tuple of exact
    field names (`{"owner_id", "user_id", "session_memory"}`) would fail
    this test, which is the point: that is the implementation this rule
    was written to reject.
    """
    secret = "abcd-live-token-value"
    payload = {
        "some_unrelated_wrapper": {
            "nested": {
                "access_token": secret,
                "gene_symbol": "BRCA1",
            }
        }
    }

    result = tracing.redact_payload(payload)

    assert result["some_unrelated_wrapper"]["nested"]["access_token"] == tracing._REDACTED
    assert secret not in json.dumps(result)
    # A neighboring, non-PII-shaped field in the same dict must survive;
    # this is what stops a wrong fix that redacts the whole parent dict
    # instead of just the matched key.
    assert result["some_unrelated_wrapper"]["nested"]["gene_symbol"] == "BRCA1"


def test_redact_payload_default_denies_an_unlisted_query_field() -> None:
    """A `Query`-shaped dict carrying a field this module's SAFE allowlist
    does not name (here, `session_id`, a real `Query` field that is
    deliberately NOT on `_QUERY_SAFE_FIELDS`) must be redacted, proving the
    allowlist is default-deny rather than default-allow. This is the
    guarantee the ticket asks for under "a NEW PII field added to Query
    later is caught by default": a field's mere presence on the model,
    with no special-casing by name, is enough to redact it here.
    """
    payload = {
        "text": "what is the function of TP53?",
        "session_id": "sess-should-not-survive",
        "trace_id": "trace-1",
        "user_id": None,
        "owner_id": None,
        "audience_depth": "researcher",
    }

    result = tracing.redact_payload(payload)

    assert result["session_id"] == tracing._REDACTED
    assert result["text"] == "what is the function of TP53?"
    assert result["trace_id"] == "trace-1"


def test_redact_payload_passes_through_a_non_query_dict_unchanged_when_no_pii() -> None:
    """A dict that is neither Query- nor RequestContext-shaped and carries
    no PII-shaped key must be returned with every value intact, not
    over-redacted. Without this test, an implementation that redacts
    everything unconditionally would still pass every test above.
    """
    payload = {"gene_symbol": "BRCA1", "curie": "NCBIGene:672", "score": 0.87}

    result = tracing.redact_payload(payload)

    assert result == payload


# ---------------------------------------------------------------------------
# redact_payload: F-5.0-09, the fail-open extra-key regression
# ---------------------------------------------------------------------------


def test_redact_payload_query_shaped_dict_with_one_extra_key_still_redacts_session_id() -> None:
    """The exact reproduction in F-5.0-09: a Query-shaped dict carrying
    every real `Query` field, PLUS one key the model does not declare
    (`billing_address`). Under the old `issubset` recognition test, that
    one extra key made the whole dict unrecognized, which switched off
    the SAFE allowlist entirely and let `session_id` ship in cleartext.

    Asserts BOTH directions so this arm fails whether the fix does not
    engage at all (session_id survives) or regresses the field it already
    protected (fixing recognition but somehow losing the redaction it
    already had).
    """
    secret_session_id = "sess-should-not-survive-9f8e7d6c"
    payload = {
        "text": "what is the function of TP53?",
        "session_id": secret_session_id,
        "trace_id": "trace-1",
        "user_id": None,
        "owner_id": None,
        "audience_depth": "researcher",
        "billing_address": "123 Main St, unexpected key not on Query",
    }

    result = tracing.redact_payload(payload)

    assert result["session_id"] == tracing._REDACTED
    assert secret_session_id not in json.dumps(result, default=str)
    assert result["billing_address"] == tracing._REDACTED
    # The extra key must not be treated as a signal that this is NOT a
    # Query, which is the specific failure mode: recognition disengaging
    # rather than tightening.
    assert result["text"] == "what is the function of TP53?"
    assert result["trace_id"] == "trace-1"


def test_redact_payload_request_context_shaped_dict_with_extra_key_still_redacts_session_memory() -> (
    None
):
    """The same reproduction shape for `RequestContext`: every real field
    plus one the model does not declare. `session_memory` is the field
    that actually matters here, since it carries the whole memory summary
    and is dropped wholesale (never selectively redacted inside) whenever
    the dict is recognized.
    """
    memory_secret = "resolved-entity-should-not-survive"
    payload = {
        "surface": "web_ui",
        "operator_mode": False,
        "session_memory": {
            "session_id": "sess-abc",
            "resolved_entities": [memory_secret],
            "compressed_findings": [],
            "open_threads": [],
            "token_budget": 1500,
            "last_updated": "2026-08-29T00:00:00Z",
        },
        "unexpected_field_not_on_request_context": "some-value",
    }

    result = tracing.redact_payload(payload)

    assert result["session_memory"] == tracing._REDACTED
    assert memory_secret not in json.dumps(result, default=str)
    assert result["unexpected_field_not_on_request_context"] == tracing._REDACTED
    assert result["surface"] == "web_ui"
    assert result["operator_mode"] is False


def test_redact_payload_denies_every_query_field_not_on_the_safe_allowlist() -> None:
    """Generalizes the "new field is caught by default" guarantee: this
    walks the LIVE `Query.model_fields` at run time rather than naming
    `session_id` specifically, so a field added to `Query` in a later
    build phase starts being asserted on by this same, unedited test the
    moment it exists, exactly the property the module docstring claims
    for `_QUERY_FIELDS`. Every field gets a distinct value so a bug that
    swaps two field values rather than redacting one would also be caught.
    """
    payload = {name: f"value-for-{name}" for name in tracing._QUERY_FIELDS}

    result = tracing.redact_payload(payload)

    for name in tracing._QUERY_FIELDS:
        if name in tracing._QUERY_SAFE_FIELDS:
            assert result[name] == f"value-for-{name}", name
        else:
            assert result[name] == tracing._REDACTED, name


def test_redact_payload_leaves_a_non_identity_tool_result_dict_untouched() -> None:
    """The over-recognition arm: a dict shaped like a tool result (rows and
    citations, the shape `cypher_query` and friends actually return), none
    of whose keys are `Query` or `RequestContext` fields at all, must not
    be mangled by the new co-occurrence recognition path. This is the
    specific risk a looser recognition rule introduces: without this test,
    a fix that recognizes on any single shared field name, or that
    lowers the co-occurrence floor too far, would pass every test above
    while silently stripping legitimate tool-result fields it has no
    business touching.
    """
    payload = {
        "rows": [{"gene_symbol": "BRCA1", "disease": "breast cancer"}],
        "citations": [
            {"source": "ncbi_gene", "source_url": "https://www.ncbi.nlm.nih.gov/gene/672"}
        ],
        "total_count": 42,
    }

    result = tracing.redact_payload(payload)

    assert result == payload


# ---------------------------------------------------------------------------
# build_runnable_config
# ---------------------------------------------------------------------------


def test_build_runnable_config_carries_trace_id_and_no_account_pii() -> None:
    trace_id = "trace-not-a-uuid-abc123"
    result = tracing.build_runnable_config(trace_id=trace_id, run_name="guardrail-to-write")

    assert result["metadata"]["trace_id"] == trace_id
    assert result["run_name"] == "guardrail-to-write"
    assert "owner_id" not in result["metadata"]
    assert "user_id" not in result["metadata"]
    assert "owner_id" not in json.dumps(result, default=str)
    assert "user_id" not in json.dumps(result, default=str)


def test_build_runnable_config_non_uuid_trace_id_does_not_raise_and_omits_run_id() -> None:
    trace_id = "definitely-not-a-uuid"

    result = tracing.build_runnable_config(trace_id=trace_id, run_name="test-run")

    assert "run_id" not in result
    assert result["metadata"]["trace_id"] == trace_id


def test_build_runnable_config_uuid_shaped_trace_id_sets_run_id() -> None:
    """The positive counterpart to the test above: when `trace_id` DOES
    happen to parse as a UUID, `run_id` is set to the parsed value, proving
    the try/except is a genuine attempt rather than a no-op that always
    swallows.
    """
    valid_uuid = str(uuid.uuid4())

    result = tracing.build_runnable_config(trace_id=valid_uuid, run_name="test-run")

    assert result["run_id"] == uuid.UUID(valid_uuid)
