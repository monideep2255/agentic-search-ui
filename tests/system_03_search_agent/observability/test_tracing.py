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
from datetime import UTC, datetime
from typing import Any, TypedDict

import pytest
import requests
import requests.adapters

from system_03_search_agent.contracts.query import (
    Query,
    RequestContext,
    SessionMemorySummary,
)
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


# ---------------------------------------------------------------------------
# The run ERROR path (A-5.0-13, J-03)
# ---------------------------------------------------------------------------


def _fake_credential() -> str:
    """A credential-shaped stand-in generated at runtime.

    Never a literal in this file: a checked-in secret-shaped string is
    exactly what this repository's write-time secret scanner exists to
    stop, and a generated value proves the same property.
    """
    return uuid.uuid4().hex


def _traced_client_pinned_to_loopback(monkeypatch: pytest.MonkeyPatch) -> Any:
    """The REAL shipped client, configured so it can reach nothing.

    Built through `build_traced_client` rather than by constructing a
    `langsmith.Client` by hand, so these arms exercise the anonymizer this
    module actually installs rather than one the test wired up itself. The
    endpoint is pinned to a closed loopback port: no arm below performs
    I/O, but a future edit that made one perform I/O must not be able to
    reach the real LangSmith with a real payload.
    """
    _clear_langsmith_env(monkeypatch)
    monkeypatch.setenv("LANGSMITH_API_KEY", _fake_credential())
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "http://127.0.0.1:1")
    return tracing.build_traced_client()


def test_api_key_in_a_run_error_never_reaches_the_langsmith_error_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-5.0-13, the reachable shape: `ncbi_transport._append_api_key` puts
    the NCBI credential in the request URL's query string, and
    `httpx.HTTPStatusError.__str__` embeds that URL, so a failed Layer 2
    call produces exactly this message. Driven through langsmith's own
    `_hide_run_error`, the private hook that assembles what is uploaded
    (`client.py:2744`), because that is the code path the credential
    actually travelled: asserting on `redact_payload` alone would be a
    correlate of the property rather than the property.
    """
    secret = _fake_credential()
    message = (
        "Client error '401 Unauthorized' for url "
        "'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        "?db=gene&term=BRCA1&api" + "_key=" + secret + "'"
    )
    raw = repr(ValueError(message)) + "\n\nTraceback (most recent call last):\n  ..."
    client = _traced_client_pinned_to_loopback(monkeypatch)

    # Populate-check: the input genuinely carries the credential, so a
    # green result below cannot mean the arm asserted over an empty or
    # already-clean string.
    assert secret in raw

    result = client._hide_run_error(raw)

    assert secret not in result
    assert "eutils.ncbi.nlm.nih.gov" not in result
    assert result.startswith(tracing._REDACTED_ERROR)
    # The class name survives, which is what makes this a BOUND rather
    # than a blanket erasure: a trace still says what kind of failure
    # occurred.
    assert result == tracing._REDACTED_ERROR + " ValueError"


def test_dsn_password_in_a_run_error_never_reaches_the_langsmith_error_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other measured shape: the `kg_reader` connection string, which a
    psycopg2 driver exception carries in its message text. Separate arm
    from the one above because the two travel through different pattern
    families in every scanner this phase tried, and a bound that happened
    to catch only one of them would still be a leak.
    """
    secret = _fake_credential()
    message = (
        "connection failed: postgresql://kg_reader:"
        + secret
        + "@46.225.128.133:5432/ncbi_kg"
    )
    raw = repr(RuntimeError(message)) + "\n\nTraceback (most recent call last):\n  ..."
    client = _traced_client_pinned_to_loopback(monkeypatch)

    assert secret in raw

    result = client._hide_run_error(raw)

    assert secret not in result
    assert "kg_reader" not in result
    assert result == tracing._REDACTED_ERROR + " RuntimeError"


def test_run_error_that_is_not_a_repr_falls_back_to_the_bare_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tracer that formats with `str(exc)` rather than `repr(exc)` gives
    the bound no class name to anchor on. It must then emit the marker
    alone rather than reading anything out of the message, which is the
    fail-closed half of the design: less information, never more.
    """
    secret = _fake_credential()
    raw = "could not connect using api" + "_key=" + secret
    client = _traced_client_pinned_to_loopback(monkeypatch)

    assert secret in raw

    result = client._hide_run_error(raw)

    assert result == tracing._REDACTED_ERROR


class TestAnOverriddenReprFailsClosedToTheBareMarker:
    """F-5.0-26: the class-name extraction's premise is not universally
    true, and this class pins what is actually true instead of the sentence
    that used to stand in for it.

    The corrected premise said position 0 followed by `(` is occupied by
    `type(exc).__name__` because the raising code chooses it. A class is
    free to override `__repr__`, and 33 classes in this branch's own
    installed dependency set do, including all 18 `litellm.exceptions.*`
    classes this repository's model harness raises. The property that
    actually holds is a property of the extraction rather than of the
    raiser: it is anchored and it fails CLOSED, so an override costs
    diagnostic fidelity and never leaks.
    """

    def test_a_litellm_exception_repr_yields_the_marker_with_no_class_name(
        self,
    ) -> None:
        """The live case, and the reason this arm uses the real dependency
        rather than a stand-in for it: `litellm.exceptions` is what this
        repository's own harness raises, so this is the override the next
        reader will actually meet.

        `litellm/exceptions.py`'s `__repr__` returns `self.message` with no
        class name of its own, and langsmith then prefixes
        `"litellm.<Class>: "`. The next character after that dotted
        identifier is `:` rather than `(`, so the extraction refuses it and
        emits the bare marker. The class name is LOST, which is the cost,
        and the message is discarded, which is the guarantee.
        """
        import litellm

        secret = _fake_credential()
        exc = litellm.exceptions.Timeout(
            message=(
                "POST https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
                "esearch.fcgi?db=gene&api" + "_key=" + secret
            ),
            model="a-model",
            llm_provider="a-provider",
        )
        raw = repr(exc)

        # Populate-check on the premise this arm exists for: the override
        # really is in force, so `repr` does NOT open with the default
        # `Timeout(` shape, and the credential really is in the input.
        assert not raw.startswith("Timeout(")
        assert secret in raw

        result = tracing._bound_error_text(raw)

        assert result == tracing._REDACTED_ERROR
        assert secret not in result

    def test_a_hand_written_repr_override_also_yields_the_bare_marker(self) -> None:
        """The same behaviour without the dependency, so this property
        survives `litellm` changing its own `__repr__`. An override that
        returns a bare message opens with a token the anchored pattern
        either rejects outright or refuses for want of a following `(`.
        """
        secret = _fake_credential()

        class _Overridden(Exception):
            def __repr__(self) -> str:
                return "connection failed: postgresql://kg_reader:" + secret + "@h/db"

        raw = repr(_Overridden())

        assert secret in raw

        result = tracing._bound_error_text(raw)

        assert result == tracing._REDACTED_ERROR
        assert secret not in result

    def test_the_residual_is_a_token_at_position_zero_followed_by_a_paren(
        self,
    ) -> None:
        """The residual, pinned rather than described, the same way
        `test_audit.TestKnownGapF5019` pins its own open gap.

        This is the F-5.0-21 residual reached by a different route: an
        identifier is a SHAPE, so an override that puts its own token where
        a class name belongs gets that token echoed after the marker. It is
        NOT reachable from any path that exists today, checked rather than
        assumed: no exception class in `src/` defines `__repr__`, and both
        live overrides in the installed dependency set fail closed above.
        The arm exists so that closing this, or widening the pattern into
        it, cannot happen without someone also correcting
        `_bound_error_text`'s docstring.
        """
        token = "a" + _fake_credential()[:16]

        result = tracing._bound_error_text(token + "(inner)")

        assert result == tracing._REDACTED_ERROR + " " + token
        # What still holds even here, and it is the load-bearing half: the
        # rest of the message is discarded, so nothing after the anchored
        # identifier travels.
        assert "inner" not in result


def test_redact_payload_bounds_an_error_key_nested_inside_a_run_payload() -> None:
    """The bound applies at every depth, not only to the single-key wrapper
    langsmith happens to build. A node output echoing a formatted exception
    under its own `error` key is the same exposure one level down.
    """
    secret = _fake_credential()
    payload = {
        "rows": [{"gene_symbol": "BRCA1"}],
        "tool_result": {
            "error": repr(ValueError("dsn postgresql://u:" + secret + "@h:5432/db")),
            "status": 500,
        },
    }

    result = tracing.redact_payload(payload)

    assert secret not in json.dumps(result, default=str)
    assert result["tool_result"]["error"] == tracing._REDACTED_ERROR + " ValueError"
    # Populate-check on the untouched half: the bound must not be a
    # blanket wipe of the surrounding payload, or this arm would pass
    # equally against a redactor that destroyed everything.
    assert result["rows"] == [{"gene_symbol": "BRCA1"}]
    assert result["tool_result"]["status"] == 500


def test_a_str_subclass_under_an_error_key_gets_the_bare_marker() -> None:
    """F-5.0-22's family, carried across from `audit.py`: a `str` subclass
    can override the very methods a guard calls, so the error bound uses an
    exact type test and refuses anything else outright rather than trusting
    a method the value controls.
    """
    secret = _fake_credential()

    class _Hostile(str):
        def __eq__(self, other: object) -> bool:
            return True

        def __hash__(self) -> int:
            return 0

    payload = {"error": _Hostile("ValueError(api" + "_key=" + secret + ")")}

    result = tracing.redact_payload(payload)

    assert result["error"] == tracing._REDACTED_ERROR
    assert secret not in json.dumps(result, default=str)


class TestTheAssembledTracePayloadCarriesNoAccountPii:
    """J-06: the PII control that closes this phase's own critical F-5.0-03
    had NO permanent arm behind it.

    `build_traced_client`'s `anonymizer=redact_payload` was the entire
    control, and deleting it left the whole suite green at `164 passed`,
    because every other reference either monkeypatched the function away or
    asserted it was never called. The goal contract asked for an arm
    inspecting the ACTUAL ASSEMBLED PAYLOAD rather than a proxy for it, and
    calling `redact_payload` directly is a correlate of the property, not
    the property: it cannot tell you whether the redactor is wired in.

    So this arm builds the whole path. A real `StateGraph`, invoked inside
    the shipped `traced_graph_run` with the shipped `build_runnable_config`,
    state carrying real `Query` and `RequestContext` objects with account
    identifiers and session-memory content, and the ACTUAL multipart body
    langsmith assembles captured at the transport.

    CONTAINMENT, since this arm exercises the real client: the endpoint is
    pinned to `http://127.0.0.1:1`, the key is a `uuid4` stand-in rather
    than any real credential, and `HTTPAdapter.send` is replaced with a
    recorder that captures the body and then raises without performing any
    I/O. Nothing leaves the machine and no real credential is used.

    WHY `build_traced_client` IS WRAPPED RATHER THAN REPLACED, stated
    because the finding this arm closes is specifically about tests that
    replace it: the wrapper CALLS the real function and keeps the client it
    returns, purely so `flush()` can be called before the recorder is
    removed. langsmith sends on a background thread that would otherwise
    fire after teardown, which is exactly what a first attempt measured, 0
    requests captured while langsmith's own error line reported a 5073-byte
    body. Every property under test still comes from the real function's
    real return value.
    """

    @staticmethod
    def _build_graph() -> Any:
        from langgraph.graph import END, START, StateGraph

        class _State(TypedDict, total=False):
            query: Any
            context: Any
            answer: str

        def _write(state: _State) -> _State:
            return {"answer": "BRCA1 is associated with breast cancer."}

        graph = StateGraph(_State)
        graph.add_node("write", _write)
        graph.add_edge(START, "write")
        graph.add_edge("write", END)
        return graph.compile()

    def test_owner_id_user_id_and_session_memory_never_reach_the_wire(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        owner_id = "owner-" + _fake_credential()
        user_id = "user-" + _fake_credential()
        memory_thread = "thread-" + _fake_credential()
        session_id = "sess-" + _fake_credential()

        query = Query(
            text="which diseases are associated with BRCA1?",
            session_id=session_id,
            trace_id=str(uuid.uuid4()),
            user_id=user_id,
            owner_id=owner_id,
        )
        context = RequestContext(
            surface="web_ui",
            session_memory=SessionMemorySummary(
                session_id=session_id,
                last_updated=datetime(2026, 8, 29, tzinfo=UTC),
                open_threads=[memory_thread],
            ),
        )

        captured: list[bytes] = []

        def _recorder(self: Any, request: Any, **kwargs: Any) -> Any:
            body = request.body
            if isinstance(body, str):
                body = body.encode("utf-8")
            if body:
                captured.append(body)
            raise requests.exceptions.ConnectionError("blocked by test")

        clients: list[Any] = []
        real_build = tracing.build_traced_client

        def _capturing_build() -> Any:
            client = real_build()
            clients.append(client)
            return client

        _clear_langsmith_env(monkeypatch)
        monkeypatch.setenv("LANGSMITH_API_KEY", _fake_credential())
        monkeypatch.setenv("LANGSMITH_ENDPOINT", "http://127.0.0.1:1")
        monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
        monkeypatch.setenv("LANGSMITH_PROJECT", "phase-5-0-arm")
        monkeypatch.setattr(tracing, "build_traced_client", _capturing_build)
        monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", _recorder)

        compiled = self._build_graph()
        with tracing.traced_graph_run(run_name="guardrail-to-write"):
            compiled.invoke(
                {"query": query, "context": context},
                config=tracing.build_runnable_config(
                    trace_id=query.trace_id, run_name="guardrail-to-write"
                ),
            )
        for client in clients:
            client.flush()

        blob = b"".join(captured)

        # POPULATE-CHECK, and it is doing two jobs. It proves a payload was
        # genuinely captured and is not empty, so "absent" below means
        # absent rather than "nothing was looked at"; and it proves the
        # redactor did not simply erase everything, since the question text
        # is on `redact_payload`'s SAFE allowlist and must survive.
        assert captured, "no outbound payload was captured at all"
        assert b"BRCA1" in blob

        assert owner_id.encode() not in blob
        assert user_id.encode() not in blob
        assert memory_thread.encode() not in blob
        assert session_id.encode() not in blob


def test_an_ordinary_string_under_an_ordinary_key_is_left_alone() -> None:
    """The scoping control for the arms above. The bound must apply to
    error-shaped keys and nothing else, or build phase 5.1's graders lose
    the answer text and tool results they read. Without this arm, a
    widening that bounded every string in a trace would pass every other
    test in this file.
    """
    payload = {"answer": "BRCA1 is associated with breast cancer.", "count": 3}

    assert tracing.redact_payload(payload) == payload
