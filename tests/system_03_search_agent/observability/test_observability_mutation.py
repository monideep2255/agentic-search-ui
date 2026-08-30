"""Permanent mutation harness for build phase 5.0's observability arms.

Vacuous assertions are the single most repeated failure in `LEARNINGS.md`.
Build phase 4.11 wrote three vacuous premise-gate arms while quoting the
lesson against vacuous arms in its own docstring; build phase 4.7 wrote
three more in a file whose own docstring quotes 4.11's lesson back. This
file exists so that, for the six properties named below, vacuity is a
`pytest` failure rather than something a reviewer has to notice by reading.

## Why monkeypatch, not file-text editing

The two existing PERMANENT mutation harnesses this file follows,
`test_cq_routing_mutation.py` and `test_release_environments_mutation.py`,
both mutate BEHAVIOUR at runtime (a fake `_World`, a monkeypatched
function) rather than editing a `.py` file on disk and reloading the
module. This file does the same, for reasons specific to this phase's
own import graph rather than by default: `audit.py` imports `audit_
enabled` and `audit_log_path` by NAME from `config.py`
(`from ...config import audit_enabled, audit_log_path`), so
`importlib.reload(config)` alone would leave `audit.py`'s own already-bound
names stale, and reloading `audit.py` too would reset its module-level
`threading.Lock` and this whole test session's already-imported references
to it. `monkeypatch.setattr` sidesteps all of that: it replaces the exact
attribute a caller looks up, its own `undo()` is the same restoration
mechanism this repository already trusts for every other test in this
directory, and it never touches a file on disk, which is also why this
file needs no byte-diff step to prove restoration: nothing is written to
restore.

Each function below still proves restoration explicitly, by identity
comparison against the ORIGINAL function object captured before mutating,
rather than only trusting the fixture's own teardown. That is the closest
analogue this technique has to the "byte-identical restoration" this
repository's file-editing precedents (T-5.0-01's mutation evidence,
F-5.0-08's and F-5.0-09's fix reports, all in tracker/phase_5.0.md) assert
with `diff`: there, the proof is that the file's bytes match; here, the
proof is that the attribute is once again the exact object it was before.

## The control half is not optional

A mutation case that only proves an arm can go RED proves nothing about
whether it can also PASS: an arm hardcoded to `assert False` would satisfy
every red case here. Every function below runs its target arm BOTH ways,
unmutated first (must be green) and mutated second (must be red), matching
`test_release_environments_mutation.py`'s own stated discipline.

## What this file does NOT claim

One mutation per function, each named for the specific regression it
reproduces. No count is stated here on purpose: build phase 4.15 shipped
that exact completeness claim wrong three times, once inside the fix for
the finding that said so the first time, and a number in a docstring rots
the moment a case is added. Count the functions below if you want to know
what is actually covered, and add the mutation case in the same edit as
the arm it proves.

## Targets, and why each was chosen over an alternative in the same file

Where more than one existing arm proves the same property, this file picks
the one requiring the fewest hand-constructed fixtures, or the one this
phase's own tracker had flagged as unproven:

1. `tracing_enabled()` made flag-only, config.py's own naive
   implementation this whole phase opened to correct: breaks
   `test_tracing.test_traced_graph_run_off_with_flag_but_no_key_builds_
   no_client`.
2. The tracing redactor's structural recognition reverted to a bare
   `issubset` (F-5.0-09's fail-open defect): breaks
   `test_tracing.test_redact_payload_query_shaped_dict_with_one_extra_
   key_still_redacts_session_id`.
3. The audit redactor's value-level string scanning removed (F-5.0-08):
   breaks
   `test_audit.TestValueLevelRedaction.
   test_reproduction_api_key_in_url_under_endpoint_key`.
4. `ncbi_transport._endpoint_for_audit` reverted to the raw URL (F-5.0-08's
   other half): breaks `test_wiring.
   TestCredentialNeverLeaksThroughTheTransport.
   test_api_key_reaches_the_request_but_never_the_audit_line`, which
   `test_wiring.py`'s OWN coverage statement names as NOT separately
   hand-mutated. This function closes exactly that stated gap, in a
   separate file rather than by editing test_wiring.py, which this
   ticket may not touch.
5. The analytics property allowlist made permissive: breaks
   `test_analytics.
   test_build_properties_rejects_unregistered_key_proving_allowlist_not_
   blocklist`.
6. The `requests`-layer blocker removed from the hermetic guard (F-5.0-07):
   breaks `test_hermetic_guard.test_a_requests_call_is_blocked`. This one
   is proven WITHOUT ever writing to `tests/conftest.py`, which this
   ticket may not modify even temporarily: the conftest fixture is
   session-scoped and already active by the time this test runs, so the
   mutation is applied one layer down, at `requests.adapters.HTTPAdapter.
   send` itself (the exact attribute F-5.0-07's own patch replaces),
   using a passthrough fake that performs no real network I/O. Restoring
   that attribute puts the conftest-installed blocker back in place for
   the rest of the session, proven by identity comparison exactly like
   the other five.
7. The audit redactor's EMBEDDED-URL scanning (F-5.0-13, gap two)
   collapsed back to F-5.0-08's whole-string-only check: breaks
   `test_audit.TestEmbeddedUrlRedaction.
   test_dsn_embedded_after_a_prose_prefix_is_redacted`, the shape gap two
   exists for, a credential inside a URL that is itself embedded in a
   larger string rather than filling the whole value.
8. The error field carrying a raw exception message again: breaks
   `test_audit.TestErrorFieldIsStructurallyBounded.
   test_credential_in_a_raised_exception_message_never_reaches_the_line`.
   This case previously targeted an arm proving a free-text `error` was
   REDACTED; that arm was replaced, not deleted, when the field stopped
   accepting free text at all, and this case follows it. Two layers must
   be reverted together to put the message back on the line, and the case
   probes each layer alone and states what it measured rather than what
   it expected. See its own comment block: the first draft's
   defense-in-depth claim was half wrong and is recorded there.
9. The audit redactor reverted to F-5.0-14's URL-token scan: breaks
   `test_audit.TestSecretAssignmentRedaction.
   test_a_bracket_in_an_earlier_query_parameter_no_longer_truncates_the_
   scan` while LEAVING `test_control_no_boundary_character_before_the_
   credential_is_redacted` green under the same mutation, which is what
   distinguishes a truncation defect from a dead scanner.
10. The secret-assignment rule removed: breaks `test_audit.
    TestSecretAssignmentRedaction.
    test_secret_assignment_in_prose_with_no_url_at_all_is_redacted`, an
    input with no `scheme://` anywhere, so only this rule can catch it.
11. The netloc-credential rule removed: breaks `test_audit.
    TestEmbeddedUrlRedaction.test_dsn_embedded_after_a_prose_prefix_is_
    redacted`. A userinfo password has no key name to match, only a
    position, so mutation 10 cannot reach it.
12. The same regression as 8 at the OTHER converted chokepoint,
    `ncbi_transport.execute_get`: breaks `test_audit.
    TestErrorFieldIsStructurallyBounded.test_credential_in_a_transport_
    exception_message_never_reaches_the_line`. Separate from 8 because
    the two call sites were converted separately, and 8 going red says
    nothing about whether this one ever could.
13. `classify_error_code`'s fail-closed branch softened into a permissive
    passthrough: breaks `test_audit.TestLegacyErrorKeywordFailsClosed.
    test_a_message_passed_to_the_legacy_keyword_records_unexpected`. One
    layer is enough here, unlike 8, because the deprecated keyword's one
    remaining caller passes `str(exc)` already.
14. `graph_connection`'s exception mapping emptied to the catch-all:
    breaks `test_audit.TestExceptionTypesAreEnumeratedNotHandTyped.
    test_every_graph_error_subclass_maps_to_a_specific_code`. An arm that
    walks a set can pass vacuously if the walk finds nothing, so this is
    what proves that one discriminates.
15. The NEVER-LOSE-THE-RECORD fallback removed (A-5.0-05): breaks
    `test_audit.TestAnUnserializableValueDegradesRatherThanDeletingTheLine.
    test_an_unserializable_scalar_field_still_writes_a_line`. Targets
    `_bounded_line` rather than `_degraded_line`, because neutering the
    fallback alone would still write something and the defect was TOTAL
    loss of the record. It drives the SCALAR arm rather than the
    `record_ids` one because `record_ids` is caught a layer above by
    `_bounded`, measured rather than assumed.
16. The PII CONTROL ITSELF deleted from `build_traced_client` (J-06),
    this phase's own critical F-5.0-03: breaks `test_tracing.
    TestTheAssembledTracePayloadCarriesNoAccountPii.
    test_owner_id_user_id_and_session_memory_never_reach_the_wire`, an arm
    that inspects the ACTUAL multipart body langsmith assembles rather
    than calling `redact_payload` directly. Deleting the line used to
    leave the suite green at `164 passed`.
17. The PostHog credential-kind bound made permissive (J-07), in two
    cases: any prefix accepted, which breaks `test_config.
    TestPostHogKeyKindIsBounded.test_a_personal_key_is_refused_by_name`;
    and a two-entry BLOCKLIST substituted for the bound, which passes that
    first case and breaks `..._an_unrecognised_prefix_fails_closed`. The
    second is the one the design rests on, since an empty blocklist is
    exactly what the pre-fix code was.
18. The SINK's own field bounds removed (A-5.0-03, A-5.0-04, A-5.0-19),
    one case per bound: `_bounded_text`, `_bounded_record_ids` and
    `_bounded_line`. The third targets the arm that drives
    `record_tool_call` with every field sitting just under its own
    per-field cap, which is how the whole-line branch is actually
    reached. It used to target a direct arm instead, on a claim that the
    branch was unreachable through `record_tool_call`; that claim was
    refuted (F-5.0-27).
19. The audit redactor's SUBCLASS FLATTENING removed (A-5.0-01), mutated
    once per delegating rule: breaks `test_audit.
    TestSubclassKeysAndValuesCannotDefeatRedaction.
    test_a_key_subclass_lying_about_lower_still_redacts_its_value` and
    `..._value_subclass_lying_about_contains_is_still_scanned`. Two cases
    because the key rule and the value rule reach the same function by
    different paths and either could be fixed without the other.
20. The audit redactor's DEFERRED-STRINGIFICATION branch removed
    (A-5.0-02, an ordering gap rather than a scanner gap): breaks
    `test_audit.TestDeferredStringificationIsRedacted.
    test_a_deferred_dsn_under_an_innocuous_key_is_redacted`. Mutated
    together with a pre-fix `_redact_value_string`, because the real one
    raises on a non-`str` and a raised exception would suppress the line
    rather than leak it, turning the arm red for the wrong reason.
21. The tracing redactor's ERROR BOUND removed, in two separately mutated
    layers (A-5.0-13, J-03): the key test that recognizes an error-shaped
    field, and the bound that discards the message under it. Both break
    arms in `test_tracing` that drive langsmith's own `_hide_run_error`
    rather than `redact_payload` directly, so the property proved is the
    one on the wire.

Depends on:
    - system_03_search_agent.observability.config
    - system_03_search_agent.observability.tracing
    - system_03_search_agent.observability.audit
    - system_03_search_agent.observability.analytics
    - system_03_search_agent.tools.ncbi_transport
    - tests.system_03_search_agent.observability.test_tracing
    - tests.system_03_search_agent.observability.test_audit
    - tests.system_03_search_agent.observability.test_config
    - tests.system_03_search_agent.observability.test_analytics
    - tests.system_03_search_agent.observability.test_hermetic_guard
    - tests.system_03_search_agent.observability.test_wiring

Writes:
    - Nothing outside tmp_path. Runs entirely offline: no model call, no
      graph, no real network. Mutation 6's fake transport never performs
      real socket I/O, so this file needs no RUN_PREMISE_GATE opt-in and
      makes no third-party call, LangSmith or PostHog, under any
      condition.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import urllib.parse
from typing import Any

import pytest
import requests

from system_03_search_agent.observability import analytics, audit, config, tracing
from system_03_search_agent.tools import graph_connection, ncbi_transport
from tests.system_03_search_agent.observability import (
    test_analytics,
    test_audit,
    test_config,
    test_hermetic_guard,
    test_tracing,
    test_wiring,
)

# `pytest.raises(...)` itself raises this when the expected exception did
# NOT occur inside its block, which is exactly what happens when a mutated
# arm's own internal `with pytest.raises(...)` fails to see what it was
# looking for (mutations 5 and 6 below). A plain `assert` inside an arm
# raises `AssertionError` directly (the rest). Both count as "the arm went
# red" for the purpose of this file.
_ARM_WENT_RED = (AssertionError, pytest.fail.Exception)


def _run_async(coro: Any) -> None:
    asyncio.run(coro)


# ---------------------------------------------------------------------------
# Mutation 1: tracing_enabled() made flag-only.
# ---------------------------------------------------------------------------


def test_tracing_enabled_made_flag_only_turns_the_no_key_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The naive implementation of this entire phase (config.py's own
    module docstring names it as the load-bearing decision): dropping the
    key requirement and answering only from the tracing flag, which is
    `true` in every `.env` in this project regardless of whether a
    credential exists.
    """
    original = config.tracing_enabled

    # Control: the target arm passes against the real, unmutated function.
    control_mp = pytest.MonkeyPatch()
    try:
        test_tracing.test_traced_graph_run_off_with_flag_but_no_key_builds_no_client(control_mp)
    finally:
        control_mp.undo()

    monkeypatch.setattr(config, "tracing_enabled", lambda: config.tracing_flag_set())

    mutated_mp = pytest.MonkeyPatch()
    try:
        with pytest.raises(_ARM_WENT_RED):
            test_tracing.test_traced_graph_run_off_with_flag_but_no_key_builds_no_client(
                mutated_mp
            )
    finally:
        mutated_mp.undo()

    monkeypatch.undo()
    assert config.tracing_enabled is original, "restoration must return the exact original object"


# ---------------------------------------------------------------------------
# Mutation 2: the tracing redactor's structural recognition reverted to a
# bare issubset (F-5.0-09's fail-open defect).
# ---------------------------------------------------------------------------


def test_looks_like_model_reverted_to_bare_issubset_turns_the_extra_key_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-5.0-09: `key_set <= model_fields` alone is the exact defect this
    phase fixed. One key the model does not declare, alongside every real
    field, used to switch the whole SAFE allowlist off and let `session_id`
    ship in cleartext. `_looks_like_model`'s co-occurrence branch is what
    keeps recognition engaged when that happens; reverting to the bare
    subset test removes exactly that branch.
    """
    original = tracing._looks_like_model

    test_tracing.test_redact_payload_query_shaped_dict_with_one_extra_key_still_redacts_session_id()

    monkeypatch.setattr(
        tracing,
        "_looks_like_model",
        lambda key_set, model_fields: key_set <= model_fields,
    )

    with pytest.raises(_ARM_WENT_RED):
        test_tracing.test_redact_payload_query_shaped_dict_with_one_extra_key_still_redacts_session_id()

    monkeypatch.undo()
    assert tracing._looks_like_model is original


# ---------------------------------------------------------------------------
# Mutation 3: the audit redactor's value-level string scanning removed
# (F-5.0-08).
# ---------------------------------------------------------------------------


def test_redact_value_string_removed_turns_the_url_leak_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-5.0-08: before this phase, a key-name rule alone could not see a
    credential embedded in a URL's query string under an innocuous key
    like `endpoint`, because `_append_api_key` appends the NCBI API key to
    the query string, never to a key named for it. `_redact_value_string`
    is the value-scanning rule that closed that gap; making it an identity
    function removes it and reopens the exact leak F-5.0-08 reproduced.
    """
    original = audit._redact_value_string
    original_enabled = audit.audit_enabled
    original_log_path = audit.audit_log_path

    control_arm = test_audit.TestValueLevelRedaction()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_reproduction_api_key_in_url_under_endpoint_key(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(audit, "_redact_value_string", lambda value: value)

    mutated_arm = test_audit.TestValueLevelRedaction()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_reproduction_api_key_in_url_under_endpoint_key(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    # F-5.0-16: every attribute this case caused to be patched is checked,
    # not only the one the outer fixture owned. The target arm patches the
    # two audit-config lookups itself, so a leaked patch here would follow
    # the rest of the session.
    assert audit._redact_value_string is original
    assert audit.audit_enabled is original_enabled
    assert audit.audit_log_path is original_log_path


# ---------------------------------------------------------------------------
# Mutation 4: ncbi_transport._endpoint_for_audit reverted to the raw URL
# (F-5.0-08's other half, the one this phase's own transport hook owns).
# ---------------------------------------------------------------------------


def test_endpoint_for_audit_reverted_to_raw_url_turns_the_wiring_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_endpoint_for_audit` is what strips the query string (and
    therefore any `api_key=` `_append_api_key` appended to it) down to
    host plus path before the endpoint ever reaches `record_tool_call`.
    Reverting it to return the full URL puts the credential back on the
    audit line through the endpoint field specifically, a different path
    from `redact_params`'s own value-scanning rule (mutation 3, above),
    and one `test_wiring.py`'s own coverage statement names as NOT
    separately hand-mutated: `TestCredentialNeverLeaksThroughTheTransport`
    "share[s] the identical file-existence populate-check shape as the two
    proven classes, and [is] recorded as unproven-by-mutation rather than
    assumed equivalent." This function closes exactly that gap.

    TWO LAYERS MUST NOW BE REVERTED TOGETHER, and this is a real change in
    what the case proves rather than a convenience (F-5.0-24, filed in
    `tracker/phase_5.0.md` the moment it was measured). A-5.0-03's fix gave
    the SINK its own bound on the endpoint field, so reverting
    `_endpoint_for_audit` alone leaves the credential still redacted and
    this case reported `DID NOT RAISE`. What each layer alone was measured
    doing, stated rather than assumed:

    - `_endpoint_for_audit` reverted alone: arm stays GREEN, because the
      sink redacts the query-string assignment itself.
    - `_bounded_text` neutered alone: arm stays GREEN, because the caller
      never hands the sink a raw URL to begin with.

    That is defense in depth working, and it is the same shape mutation 8
    already documents for the error field. The case reverts both because
    the property it exists to prove, that a credential cannot reach the
    line through the endpoint field, now has two independent guards and
    neither one alone is the reason it holds.
    """
    original = ncbi_transport._endpoint_for_audit
    original_bounded_text = audit._bounded_text
    original_enabled = audit.audit_enabled
    original_log_path = audit.audit_log_path
    original_api_key = os.environ.get("NCBI_API_KEY")

    control_arm = test_wiring.TestCredentialNeverLeaksThroughTheTransport()
    with pytest.MonkeyPatch.context() as arm_mp:
        _run_async(
            control_arm.test_api_key_reaches_the_request_but_never_the_audit_line(
                tmp_path / "control", arm_mp
            )
        )

    monkeypatch.setattr(ncbi_transport, "_endpoint_for_audit", lambda url: url)
    monkeypatch.setattr(audit, "_bounded_text", lambda value, *, field_name: value)

    mutated_arm = test_wiring.TestCredentialNeverLeaksThroughTheTransport()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        _run_async(
            mutated_arm.test_api_key_reaches_the_request_but_never_the_audit_line(
                tmp_path / "mutated", arm_mp
            )
        )

    monkeypatch.undo()
    assert audit._bounded_text is original_bounded_text
    # F-5.0-16: this target arm patches the two audit-config lookups AND
    # sets NCBI_API_KEY to a generated credential, so an un-undone patch
    # here would leave that credential in os.environ for the rest of the
    # session. All four are checked, not just the one the outer fixture
    # owned.
    assert ncbi_transport._endpoint_for_audit is original
    assert audit.audit_enabled is original_enabled
    assert audit.audit_log_path is original_log_path
    assert os.environ.get("NCBI_API_KEY") == original_api_key


# ---------------------------------------------------------------------------
# Mutation 5: the analytics property allowlist made permissive.
# ---------------------------------------------------------------------------


def test_build_properties_made_permissive_turns_the_allowlist_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`build_properties` is an ALLOWLIST by design (its own docstring):
    a property name must be registered in `_PROPERTY_SCHEMA` with an
    explicit shape before any value under that name leaves this process.
    Replacing it with a passthrough that forwards whatever it is given is
    the blocklist failure mode that design exists to rule out: nothing
    would stop free text from reaching PostHog under an unregistered key.
    """
    original = analytics.build_properties

    test_analytics.test_build_properties_rejects_unregistered_key_proving_allowlist_not_blocklist()

    monkeypatch.setattr(analytics, "build_properties", lambda **properties: dict(properties))

    with pytest.raises(_ARM_WENT_RED):
        test_analytics.test_build_properties_rejects_unregistered_key_proving_allowlist_not_blocklist()

    monkeypatch.undo()
    assert analytics.build_properties is original


# ---------------------------------------------------------------------------
# Mutation 6: the requests-layer blocker removed from the hermetic guard
# (F-5.0-07). Never touches tests/conftest.py; see this file's own
# docstring for why the mutation is applied one layer down instead.
# ---------------------------------------------------------------------------


def _passthrough_send(self: requests.adapters.HTTPAdapter, request: Any, **kwargs: Any):
    """What `HTTPAdapter.send` would do if F-5.0-07's blocker were never
    installed: hand back a response with no real socket I/O attempted,
    which is itself the point (build phase 5.0's own hermetic-suite rule).
    """
    response = requests.Response()
    response.status_code = 200
    response.request = request
    response._content = b"{}"
    return response


def test_requests_blocker_removed_turns_the_hermetic_guard_arm_red() -> None:
    """`tests/conftest.py`'s session-scoped fixture is already active by
    the time this test runs, having patched `requests.adapters.
    HTTPAdapter.send` at session start. The mutation therefore targets
    that same attribute one layer down rather than the fixture itself: a
    fresh `pytest.MonkeyPatch()`, scoped to this function only, swaps it
    for a passthrough that performs no real network I/O, proving the
    property F-5.0-07 exists to guard without ever writing to conftest.py
    and without reaching a real host.
    """
    original = requests.adapters.HTTPAdapter.send

    test_hermetic_guard.test_a_requests_call_is_blocked()

    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(requests.adapters.HTTPAdapter, "send", _passthrough_send)
        with pytest.raises(_ARM_WENT_RED):
            test_hermetic_guard.test_a_requests_call_is_blocked()
    finally:
        mp.undo()

    assert requests.adapters.HTTPAdapter.send is original


# ---------------------------------------------------------------------------
# Mutation 7: the audit redactor's embedded-URL scanning (F-5.0-13, gap two)
# reverted to F-5.0-08's whole-string-only check.
# ---------------------------------------------------------------------------


def _whole_string_only_redact_value_string(value: str) -> str:
    """What `_redact_value_string` did before F-5.0-13's gap two: the exact
    pre-fix implementation, reproduced here rather than imported, since the
    fixed version is what `audit.py` now exports under this name. Redacts
    a value only when the ENTIRE string parses as a URL, which is the
    defect gap two closed: a credential embedded in a URL sitting inside a
    larger string, an exception message's prose, was invisible to this
    check.
    """
    if "://" not in value:
        return value
    parsed = urllib.parse.urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    # The two redaction rules themselves are the CURRENT ones. What this
    # stand-in reproduces is the pre-fix GATE in front of them, refusing to
    # act unless the entire string parses as a URL, which is the defect gap
    # two closed. Reproducing the old rules too would conflate two
    # regressions in one mutation, and F-5.0-14 removed the helpers they
    # were built from.
    return audit._redact_secret_assignments(audit._redact_netloc_credentials(value))


def test_embedded_url_scan_reverted_to_whole_string_only_turns_the_gap_two_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-5.0-13, gap two: `_redact_value_string` scanning for a
    URL-shaped TOKEN anywhere in a string, rather than requiring the whole
    string to parse as one, is what catches a credential embedded in an
    exception message's prose. Reverting to the whole-string-only version
    reopens exactly that gap while leaving the whole-string case (mutation
    3, F-5.0-08's original reproduction) untouched, which is why this is a
    separate mutation rather than a duplicate of mutation 3.
    """
    original = audit._redact_value_string

    control_arm = test_audit.TestEmbeddedUrlRedaction()
    control_arm.test_dsn_embedded_after_a_prose_prefix_is_redacted()

    monkeypatch.setattr(audit, "_redact_value_string", _whole_string_only_redact_value_string)

    mutated_arm = test_audit.TestEmbeddedUrlRedaction()
    with pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_dsn_embedded_after_a_prose_prefix_is_redacted()

    monkeypatch.undo()
    assert audit._redact_value_string is original


# ---------------------------------------------------------------------------
# Mutation 8: the error field carries a raw exception message again, the
# state this whole design change removed (F-5.0-13, F-5.0-14, F-5.0-19).
# ---------------------------------------------------------------------------

#: Reverting BOTH layers at once is deliberate, and the two single-layer
#: probes below say exactly what each layer buys. Two independent things
#: stop a credential in an exception message reaching the sink: the call
#: site classifies instead of stringifying, and `classify_error_code`
#: fails closed on anything outside the vocabulary.
#:
#: A first draft of this case claimed each layer alone leaves the target
#: arm green. RUNNING IT SHOWED THAT IS FALSE, and the false half is
#: recorded here rather than quietly corrected, because it is the same
#: "confident sentence describing a check that was not there" shape build
#: phase 4.15 shipped four times. What is actually true, measured:
#:
#: - Sink layer alone reverted: arm GREEN. The call site still passes a
#:   vocabulary member, so a permissive sink has nothing hostile to admit.
#: - Call-site layer alone reverted: arm RED, but on its `error_code ==
#:   "connection"` assertion rather than on the leak, and the credential
#:   still does NOT reach the file. That is the defense-in-depth result
#:   worth having, and the probe below asserts the absence directly
#:   instead of inferring it from the arm's colour.
#: - Both reverted: arm RED and the message genuinely lands on the line,
#:   which is the pre-change state this case reproduces.


def _passthrough_classify(value):
    """`classify_error_code` with its fail-closed branch softened into a
    permissive passthrough, the single change that would reopen the hole.
    """
    return value


def test_error_field_written_raw_again_turns_the_graph_credential_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replaces the earlier version of this case, whose target arm proved
    a free-text `error` was REDACTED. That arm no longer exists because
    the field no longer accepts free text; this proves the successor arm,
    that a credential in a raised exception's MESSAGE cannot reach the
    line, driven through the real `execute_cypher` chokepoint.
    """
    original_classify = audit.classify_error_code
    original_graph_classifier = graph_connection.audit_error_code

    control_arm = test_audit.TestErrorFieldIsStructurallyBounded()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_credential_in_a_raised_exception_message_never_reaches_the_line(
            tmp_path / "control", arm_mp
        )

    # Single-layer probe one: a permissive sink alone changes nothing,
    # because the call site still hands it a vocabulary member.
    with pytest.MonkeyPatch.context() as single_mp:
        single_mp.setattr(audit, "classify_error_code", _passthrough_classify)
        with pytest.MonkeyPatch.context() as arm_mp:
            control_arm.test_credential_in_a_raised_exception_message_never_reaches_the_line(
                tmp_path / "sink-only", arm_mp
            )

    # Single-layer probe two: a stringifying call site alone DOES turn the
    # arm red, on its code assertion, and the sink's fail-closed branch
    # still keeps the message off the line. Asserted against the file
    # rather than inferred from the arm's colour, since "it went red" says
    # nothing about which assertion fired.
    call_site_only_dir = tmp_path / "call-site-only"
    with pytest.MonkeyPatch.context() as single_mp:
        single_mp.setattr(graph_connection, "audit_error_code", lambda exc: str(exc))
        with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
            control_arm.test_credential_in_a_raised_exception_message_never_reaches_the_line(
                call_site_only_dir, arm_mp
            )
    written = (call_site_only_dir / "audit.jsonl").read_text(encoding="utf-8")
    assert "postgresql" not in written
    assert "connection failed" not in written

    monkeypatch.setattr(audit, "classify_error_code", _passthrough_classify)
    monkeypatch.setattr(graph_connection, "audit_error_code", lambda exc: str(exc))

    mutated_arm = test_audit.TestErrorFieldIsStructurallyBounded()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_credential_in_a_raised_exception_message_never_reaches_the_line(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit.classify_error_code is original_classify
    assert graph_connection.audit_error_code is original_graph_classifier


# ---------------------------------------------------------------------------
# Mutation 9: the audit redactor reverted to F-5.0-14's URL-token scan, the
# implementation this round replaced.
# ---------------------------------------------------------------------------

#: The exact pattern `audit.py` carried when F-5.0-14 was raised against it.
#: It stops the token at the FIRST boundary character anywhere in it, which
#: is the defect: a bracket, parenthesis or quote in the path or in an
#: earlier query parameter truncates the match, and the credential
#: `_append_api_key` appends LAST is then never scanned at all.
_F_5_0_14_URL_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^\s\"'<>()\[\]{}]+")


def _url_token_only_redact_value_string(value: str) -> str:
    """What `_redact_value_string` did when F-5.0-14 was raised: delimit a
    URL-shaped token inside the string, then redact only within it.

    The redaction rules applied inside the token are the CURRENT ones, so
    the only thing this mutation changes is WHERE they are allowed to look.
    That is what isolates the finding: the defect was never that the rules
    were wrong, it was that a boundary character upstream of the credential
    ended the region they were allowed to see.
    """
    if "://" not in value:
        return value

    def _redact_token(match: re.Match[str]) -> str:
        token = match.group(0)
        return audit._redact_secret_assignments(audit._redact_netloc_credentials(token))

    redacted = _F_5_0_14_URL_TOKEN.sub(_redact_token, value)
    return redacted if redacted != value else value


def test_url_token_scan_restored_turns_the_bracket_truncation_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F-5.0-14: an Entrez bracketed field parameter sitting BEFORE the
    appended credential. Restoring the URL-token scan reopens the leak.

    This case runs the CONTROL arm under the mutation too, not only the
    unmutated control every case here runs. That is the evidentiary point
    of F-5.0-14: the same URL with no boundary character is still redacted
    by the broken implementation, so a suite that only checked "something
    gets redacted" could not tell truncation from a dead scanner. Green
    control plus red bracket arm, under one mutation, is what makes this a
    truncation finding rather than a coverage guess.
    """
    original = audit._redact_value_string

    control_arm = test_audit.TestSecretAssignmentRedaction()
    control_arm.test_a_bracket_in_an_earlier_query_parameter_no_longer_truncates_the_scan()

    monkeypatch.setattr(audit, "_redact_value_string", _url_token_only_redact_value_string)

    mutated_arm = test_audit.TestSecretAssignmentRedaction()
    with pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_a_bracket_in_an_earlier_query_parameter_no_longer_truncates_the_scan()
    # Still green under the same mutation: no boundary character upstream
    # of the credential, so there is nothing to truncate.
    mutated_arm.test_control_no_boundary_character_before_the_credential_is_redacted()

    monkeypatch.undo()
    assert audit._redact_value_string is original


# ---------------------------------------------------------------------------
# Mutation 10: the secret-assignment rule removed (F-5.0-14's first half).
# ---------------------------------------------------------------------------


def test_secret_assignment_rule_removed_turns_the_bare_prose_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_redact_secret_assignments` is the rule that redacts a secret-ish
    `name=value` wherever it occurs, with no URL wrapper required. The
    target arm has no `scheme://` in it at all, so it isolates this rule
    from the netloc rule mutation 11 covers: only this one can catch it.
    """
    original = audit._redact_secret_assignments

    control_arm = test_audit.TestSecretAssignmentRedaction()
    control_arm.test_secret_assignment_in_prose_with_no_url_at_all_is_redacted()

    monkeypatch.setattr(audit, "_redact_secret_assignments", lambda value: value)

    mutated_arm = test_audit.TestSecretAssignmentRedaction()
    with pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_secret_assignment_in_prose_with_no_url_at_all_is_redacted()

    monkeypatch.undo()
    assert audit._redact_secret_assignments is original


# ---------------------------------------------------------------------------
# Mutation 11: the netloc-credential rule removed (F-5.0-14's second half).
# ---------------------------------------------------------------------------


def test_netloc_credential_rule_removed_turns_the_dsn_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_redact_netloc_credentials` is the rule that blanks a password in a
    `scheme://user:pw@host` userinfo segment. A DSN password carries no key
    name to test against `_SECRET_KEY_MARKERS`, only a position, so the
    assignment rule structurally cannot catch it and this mutation is not a
    duplicate of mutation 10.
    """
    original = audit._redact_netloc_credentials

    control_arm = test_audit.TestEmbeddedUrlRedaction()
    control_arm.test_dsn_embedded_after_a_prose_prefix_is_redacted()

    monkeypatch.setattr(audit, "_redact_netloc_credentials", lambda value: value)

    mutated_arm = test_audit.TestEmbeddedUrlRedaction()
    with pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_dsn_embedded_after_a_prose_prefix_is_redacted()

    monkeypatch.undo()
    assert audit._redact_netloc_credentials is original


# ---------------------------------------------------------------------------
# Mutation 12: the same regression at the OTHER converted chokepoint.
# ---------------------------------------------------------------------------


def test_error_field_written_raw_again_turns_the_transport_credential_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`ncbi_transport.execute_get` is a separate call site from
    `graph_connection.execute_cypher` and was converted separately, so its
    arm needs its own mutation. Mutation 8 proving the graph arm red says
    nothing about whether this one could ever fail, which is the exact
    assumption `test_wiring.py`'s own coverage statement warned against
    when it recorded two of its classes as unproven-by-mutation.
    """
    original_classify = audit.classify_error_code
    original_transport_classifier = ncbi_transport.audit_error_code

    control_arm = test_audit.TestErrorFieldIsStructurallyBounded()
    with pytest.MonkeyPatch.context() as arm_mp:
        _run_async(
            control_arm.test_credential_in_a_transport_exception_message_never_reaches_the_line(
                tmp_path / "control", arm_mp
            )
        )

    monkeypatch.setattr(audit, "classify_error_code", _passthrough_classify)
    monkeypatch.setattr(ncbi_transport, "audit_error_code", lambda exc: str(exc))

    mutated_arm = test_audit.TestErrorFieldIsStructurallyBounded()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        _run_async(
            mutated_arm.test_credential_in_a_transport_exception_message_never_reaches_the_line(
                tmp_path / "mutated", arm_mp
            )
        )

    monkeypatch.undo()
    assert audit.classify_error_code is original_classify
    assert ncbi_transport.audit_error_code is original_transport_classifier


# ---------------------------------------------------------------------------
# Mutation 13: the fail-closed branch alone, softened into a passthrough.
# ---------------------------------------------------------------------------


def test_permissive_vocabulary_fallback_turns_the_legacy_keyword_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fail-closed branch is what makes the deprecated `error` keyword
    safe for `pathogen_ftp_transport.py`, the one caller this design
    change could not edit (F-5.0-20). Softening it to a passthrough is the
    plausible future regression, since "just let a string through" reads
    as a small convenience rather than as reopening a credential path.

    Unlike mutation 8 this needs only ONE layer reverted, because that
    caller passes `str(exc)` already: the vocabulary check is the only
    thing standing between its message and the sink.
    """
    original_classify = audit.classify_error_code

    control_arm = test_audit.TestLegacyErrorKeywordFailsClosed()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_a_message_passed_to_the_legacy_keyword_records_unexpected(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(audit, "classify_error_code", _passthrough_classify)

    mutated_arm = test_audit.TestLegacyErrorKeywordFailsClosed()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_a_message_passed_to_the_legacy_keyword_records_unexpected(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit.classify_error_code is original_classify


# ---------------------------------------------------------------------------
# Mutation 14: an exception type left unmapped.
# ---------------------------------------------------------------------------


def test_an_unmapped_exception_type_turns_the_enumerating_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The enumerating arm reads both error families from their own
    `__subclasses__()` so a NEW type with no mapping row cannot be
    silently classified `unexpected`. An arm that walks a set can pass
    vacuously if the walk finds nothing useful, so this proves it
    actually discriminates: emptying the mapping down to the catch-all
    makes every subclass fall through, which is precisely the "silently
    unmapped" state the arm exists to forbid.
    """
    original = graph_connection._AUDIT_ERROR_CODE_BY_CLASS_NAME

    control_arm = test_audit.TestExceptionTypesAreEnumeratedNotHandTyped()
    control_arm.test_every_graph_error_subclass_maps_to_a_specific_code()

    monkeypatch.setattr(
        graph_connection,
        "_AUDIT_ERROR_CODE_BY_CLASS_NAME",
        {"GraphError": audit.UNEXPECTED_ERROR_CODE},
    )

    mutated_arm = test_audit.TestExceptionTypesAreEnumeratedNotHandTyped()
    with pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_every_graph_error_subclass_maps_to_a_specific_code()

    monkeypatch.undo()
    assert graph_connection._AUDIT_ERROR_CODE_BY_CLASS_NAME is original


# ---------------------------------------------------------------------------
# Mutation 15: the vocabulary check reverted to `isinstance` plus a
# passthrough of the caller's own object.
# ---------------------------------------------------------------------------


def _isinstance_vocabulary_check(value: Any) -> Any:
    """`classify_error_code` exactly as it stood before F-5.0-22.

    Kept as a real reimplementation rather than a stub, so the mutation
    reproduces the actual regression: a `str` subclass overriding `__eq__`
    satisfies tuple containment and is then returned verbatim.
    """
    if value is None:
        return None
    if isinstance(value, str) and value in audit.AUDIT_ERROR_CODES:
        return value
    return audit.UNEXPECTED_ERROR_CODE


def test_isinstance_vocabulary_check_turns_the_hostile_eq_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`isinstance` reads as the ordinary, idiomatic spelling, which is why
    the exact-type test is the plausible thing for a future reader to
    "simplify" back. This makes that edit a failure rather than a review
    finding.
    """
    original_classify = audit.classify_error_code

    control_arm = test_audit.TestGuardsRefuseAHostileStrSubclass()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_a_subclass_overriding_eq_cannot_write_itself_into_error_code(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(audit, "classify_error_code", _isinstance_vocabulary_check)

    mutated_arm = test_audit.TestGuardsRefuseAHostileStrSubclass()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_a_subclass_overriding_eq_cannot_write_itself_into_error_code(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit.classify_error_code is original_classify


# ---------------------------------------------------------------------------
# Mutation 16: the class-name check reverted to `isinstance`, leaving both
# of its bounds on methods a subclass owns.
# ---------------------------------------------------------------------------


def _isinstance_error_class_check(value: Any) -> Any:
    """`_safe_error_class` exactly as it stood before F-5.0-22."""
    if value is None:
        return None
    if (
        isinstance(value, str)
        and len(value) <= audit._MAX_ERROR_CLASS_CHARS
        and value.isidentifier()
    ):
        return value
    return audit._REFUSED_ERROR_CLASS


def test_isinstance_error_class_check_turns_the_hostile_identifier_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same reversion at the other guard. Reverting one does not turn
    the other's arm red, which is why both mutations exist: the two guards
    share the hole but neither covers the other.
    """
    original_safe_error_class = audit._safe_error_class

    control_arm = test_audit.TestGuardsRefuseAHostileStrSubclass()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_a_subclass_lying_about_both_bounds_cannot_reach_error_class(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(audit, "_safe_error_class", _isinstance_error_class_check)

    mutated_arm = test_audit.TestGuardsRefuseAHostileStrSubclass()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_a_subclass_lying_about_both_bounds_cannot_reach_error_class(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit._safe_error_class is original_safe_error_class


# ---------------------------------------------------------------------------
# Mutation 17: a call site going back to a data-derived `error_class`.
# ---------------------------------------------------------------------------


def _source_with_a_stringified_error_class(module: Any) -> str:
    """The module's real source with the class-name literal replaced by
    `str(exc)`, which is precisely the expression this phase removed from
    both call sites and the one a future edit is most likely to restore.

    Returns real source rather than a hand-written snippet so the arm is
    fed something that parses the same way the genuine file does.
    """
    return inspect.getsource(module).replace(
        "error_class=type(exc).__name__",
        "error_class=str(exc)",
    )


def test_a_stringified_call_site_turns_the_call_site_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The call-site arm is what carries F-5.0-21's real guarantee, since
    the guard in front of it is a shape check rather than a secrecy check.
    An arm that walks parsed source can pass vacuously by matching
    nothing, so this proves it discriminates: feed it a source where the
    class-name literal became `str(exc)` and it must go red.
    """
    original_module_source = test_audit._module_source

    control_arm = test_audit.TestErrorClassCallSitesPassAClassNameLiteral()
    control_arm.test_every_record_tool_call_passes_a_class_name_or_none()

    monkeypatch.setattr(
        test_audit, "_module_source", _source_with_a_stringified_error_class
    )

    mutated_arm = test_audit.TestErrorClassCallSitesPassAClassNameLiteral()
    with pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_every_record_tool_call_passes_a_class_name_or_none()

    monkeypatch.undo()
    assert test_audit._module_source is original_module_source


# ---------------------------------------------------------------------------
# Mutation 18: the never-lose-the-record fallback removed (A-5.0-05).
# ---------------------------------------------------------------------------


def test_degraded_line_fallback_removed_turns_the_unserializable_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-5.0-05. A bare `json.dumps` with no fallback is the pre-fix code:
    the exception escapes into `record_tool_call`'s blanket handler and the
    line is never written at all, which for an append-only audit sink is
    permanent and silent.

    The mutation targets `_bounded_line` rather than `_degraded_line`,
    because neutering the fallback alone would still leave SOMETHING
    written; the defect was total loss of the record, and only removing the
    call to the fallback reproduces that.

    IT DRIVES THE SCALAR-FIELD ARM, NOT THE `record_ids` ONE, and that is a
    measurement rather than a choice. `record_ids` now reaches the line
    through `_bounded`, whose own try/except substitutes a disclosure
    marker, so the adversary's original reproduction is caught a layer
    ABOVE this fallback and stayed green under this mutation. `latency_ms`
    is a field no redactor walks, so the fallback is the only thing
    standing behind it. Both arms are kept: one pins the shape the finding
    was filed against, the other pins the layer this fix added.
    """
    original = audit._bounded_line

    control_arm = test_audit.TestAnUnserializableValueDegradesRatherThanDeletingTheLine()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_an_unserializable_scalar_field_still_writes_a_line(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(
        audit, "_bounded_line", lambda entry: json.dumps(entry, default=str)
    )

    mutated_arm = test_audit.TestAnUnserializableValueDegradesRatherThanDeletingTheLine()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_an_unserializable_scalar_field_still_writes_a_line(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit._bounded_line is original


# ---------------------------------------------------------------------------
# Mutation 19: the PII control itself deleted from build_traced_client
# (J-06). This is the phase's own critical, F-5.0-03.
# ---------------------------------------------------------------------------


def _client_with_no_anonymizer() -> Any:
    """`build_traced_client` with the PII control removed, and nothing else.

    Byte-for-byte the shipped function minus `anonymizer=redact_payload`,
    which is the single line standing between `GraphState` and LangSmith.
    `hide_metadata` is deliberately LEFT WIRED so this mutation isolates
    the anonymizer rather than removing both controls at once and proving
    less than it appears to.
    """
    from langsmith import Client

    return Client(
        api_key=config.langsmith_api_key(),
        api_url=config.langsmith_endpoint(),
        hide_metadata=tracing.redact_payload,
    )


def test_deleting_the_anonymizer_turns_the_assembled_payload_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-06. Deleting this line left the whole suite green at `164 passed`,
    because every reference to `build_traced_client` either monkeypatched
    it away or asserted it was never called. That is the twelfth recorded
    instance in this repository of an assertion that could not fail, and it
    sat on the most sensitive control the phase ships.

    This case exists so the deletion is a `pytest` failure. The arm it
    drives inspects the ACTUAL multipart body langsmith assembles, which is
    the property, rather than calling `redact_payload` directly, which is a
    correlate of it and is exactly what could not catch this.
    """
    original = tracing.build_traced_client

    control_arm = test_tracing.TestTheAssembledTracePayloadCarriesNoAccountPii()
    control_mp = pytest.MonkeyPatch()
    try:
        control_arm.test_owner_id_user_id_and_session_memory_never_reach_the_wire(
            control_mp
        )
    finally:
        control_mp.undo()

    monkeypatch.setattr(tracing, "build_traced_client", _client_with_no_anonymizer)

    mutated_arm = test_tracing.TestTheAssembledTracePayloadCarriesNoAccountPii()
    mutated_mp = pytest.MonkeyPatch()
    try:
        with pytest.raises(_ARM_WENT_RED):
            mutated_arm.test_owner_id_user_id_and_session_memory_never_reach_the_wire(
                mutated_mp
            )
    finally:
        mutated_mp.undo()

    monkeypatch.undo()
    assert tracing.build_traced_client is original


# ---------------------------------------------------------------------------
# Mutation 19: the PostHog credential-kind bound made permissive (J-07).
# ---------------------------------------------------------------------------


def test_any_posthog_prefix_accepted_turns_the_personal_key_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """J-07 and F-5.0-12. Accepting any configured value is the pre-fix
    code exactly, and it is what made an account-wide read-write PERSONAL
    api key live in any shell that had not exported the right one.

    The mutation reads the raw environment the same way the real function
    does, so the only thing removed is the prefix bound itself.
    """
    original = config.posthog_api_key

    control_arm = test_config.TestPostHogKeyKindIsBounded()
    control_mp = pytest.MonkeyPatch()
    try:
        for name in test_config._ALL_OBSERVABILITY_VARS:
            control_mp.delenv(name, raising=False)
        control_arm.test_a_personal_key_is_refused_by_name(control_mp)
    finally:
        control_mp.undo()

    monkeypatch.setattr(
        config, "posthog_api_key", lambda: os.environ.get("POSTHOG_API_KEY") or None
    )

    mutated_arm = test_config.TestPostHogKeyKindIsBounded()
    mutated_mp = pytest.MonkeyPatch()
    try:
        for name in test_config._ALL_OBSERVABILITY_VARS:
            mutated_mp.delenv(name, raising=False)
        with pytest.raises(_ARM_WENT_RED):
            mutated_arm.test_a_personal_key_is_refused_by_name(mutated_mp)
    finally:
        mutated_mp.undo()

    monkeypatch.undo()
    assert config.posthog_api_key is original


def test_unknown_prefix_failing_open_turns_the_fail_closed_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second half, and the one the design actually rests on. A
    blocklist of the two known-bad prefixes would pass the case above and
    still admit every credential kind nobody has reasoned about, which is
    what the pre-fix code was with an empty blocklist.
    """
    original = config.posthog_api_key
    refused = tuple(config._POSTHOG_REFUSED_PREFIXES)

    def _blocklist_only() -> str | None:
        raw = os.environ.get("POSTHOG_API_KEY") or None
        if raw is None or raw.startswith(refused):
            return None
        return raw

    control_arm = test_config.TestPostHogKeyKindIsBounded()
    control_mp = pytest.MonkeyPatch()
    try:
        for name in test_config._ALL_OBSERVABILITY_VARS:
            control_mp.delenv(name, raising=False)
        control_arm.test_an_unrecognised_prefix_fails_closed(control_mp)
    finally:
        control_mp.undo()

    monkeypatch.setattr(config, "posthog_api_key", _blocklist_only)

    mutated_arm = test_config.TestPostHogKeyKindIsBounded()
    mutated_mp = pytest.MonkeyPatch()
    try:
        for name in test_config._ALL_OBSERVABILITY_VARS:
            mutated_mp.delenv(name, raising=False)
        with pytest.raises(_ARM_WENT_RED):
            mutated_arm.test_an_unrecognised_prefix_fails_closed(mutated_mp)
    finally:
        mutated_mp.undo()

    monkeypatch.undo()
    assert config.posthog_api_key is original


# ---------------------------------------------------------------------------
# Mutation 19: the sink's own field bounds removed (A-5.0-03, A-5.0-04,
# A-5.0-19), one case per bound.
# ---------------------------------------------------------------------------


def test_bounded_text_removed_turns_the_sink_endpoint_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-5.0-03. Placing the caller's value verbatim is exactly what the
    sink did before this fix, and it is why F-5.0-08's caller-side fix left
    the sink itself as defenceless as the day that critical was filed.
    """
    original = audit._bounded_text

    control_arm = test_audit.TestSinkFieldsAreBoundedAndRedacted()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_a_credential_in_the_endpoint_field_is_redacted_at_the_sink(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(audit, "_bounded_text", lambda value, *, field_name: value)

    mutated_arm = test_audit.TestSinkFieldsAreBoundedAndRedacted()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_a_credential_in_the_endpoint_field_is_redacted_at_the_sink(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit._bounded_text is original


def test_record_ids_bound_removed_turns_the_untrusted_content_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-5.0-04. `list(record_ids)` and nothing else is the pre-fix code
    verbatim. Separate from the case above because `record_ids` reaches the
    line through a different function and neither bound covers the other.
    """
    original = audit._bounded_record_ids

    control_arm = test_audit.TestSinkFieldsAreBoundedAndRedacted()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_record_ids_elements_are_redacted_and_stringified(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(
        audit,
        "_bounded_record_ids",
        lambda record_ids: list(record_ids) if record_ids is not None else [],
    )

    mutated_arm = test_audit.TestSinkFieldsAreBoundedAndRedacted()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_record_ids_elements_are_redacted_and_stringified(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit._bounded_record_ids is original


def test_line_bound_removed_turns_the_atomic_append_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-5.0-19. A plain `json.dumps` with no whole-line check is the
    pre-fix code, and it is what let a 20 KB line be written, which four
    concurrent PROCESSES then interleaved into 251 unparseable lines in an
    append-only file. This case is what stops that guarantee decaying back
    into arithmetic stated in a comment.

    It targets the arm that drives `record_tool_call` for real, which is
    the stronger case: it proves the belt fires on the public entry point
    rather than only on a hand-built entry. This case previously targeted
    the direct arm instead, on the strength of a claim that the reduction
    branch was unreachable through `record_tool_call`. That claim was
    false (F-5.0-27): it is reached by sitting JUST UNDER every per-field
    cap at once, and the earlier probe missed it because it drove every
    field far OVER its cap, where each field is replaced by a short
    disclosure marker and the line comes out small.
    """
    original = audit._bounded_line

    control_arm = test_audit.TestSinkFieldsAreBoundedAndRedacted()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_the_reduction_branch_is_reachable_through_record_tool_call(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(
        audit, "_bounded_line", lambda entry: json.dumps(entry, default=str)
    )

    mutated_arm = test_audit.TestSinkFieldsAreBoundedAndRedacted()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_the_reduction_branch_is_reachable_through_record_tool_call(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit._bounded_line is original


# ---------------------------------------------------------------------------
# Mutation 19: the subclass flattening removed from the audit redactor
# (A-5.0-01), mutated once per delegating rule.
# ---------------------------------------------------------------------------


def test_plain_str_removed_turns_the_lying_key_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-5.0-01, the KEY rule. An identity `_plain_str` is precisely the
    pre-fix code: `_is_secret_key` then calls the subclass's own `lower()`,
    which answers `"harmless"`, so a key literally named `api_key` is not
    recognized as secret-ish and its value lands on the line.
    """
    original = audit._plain_str

    control_arm = test_audit.TestSubclassKeysAndValuesCannotDefeatRedaction()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_a_key_subclass_lying_about_lower_still_redacts_its_value(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(audit, "_plain_str", lambda value: value)

    mutated_arm = test_audit.TestSubclassKeysAndValuesCannotDefeatRedaction()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_a_key_subclass_lying_about_lower_still_redacts_its_value(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit._plain_str is original


def test_plain_str_removed_turns_the_lying_value_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same mutation at the VALUE rule, which delegates to the same
    function through a different path. Separate case because the key arm
    going red says nothing about whether the value arm ever could: the two
    rules fail for different reasons and one could be fixed without the
    other.
    """
    original = audit._plain_str

    control_arm = test_audit.TestSubclassKeysAndValuesCannotDefeatRedaction()
    control_arm.test_a_value_subclass_lying_about_contains_is_still_scanned()

    monkeypatch.setattr(audit, "_plain_str", lambda value: value)

    mutated_arm = test_audit.TestSubclassKeysAndValuesCannotDefeatRedaction()
    with pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_a_value_subclass_lying_about_contains_is_still_scanned()

    monkeypatch.undo()
    assert audit._plain_str is original


# ---------------------------------------------------------------------------
# Mutation 19: the audit redactor's deferred-stringification branch removed
# (A-5.0-02, the ordering gap).
# ---------------------------------------------------------------------------


def test_stringify_leaf_removed_turns_the_deferred_dsn_arm_red(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-5.0-02: making `_stringify_leaf` return the object unchanged puts
    the ordering defect back exactly as it was. `_redact_value_string` then
    receives a non-`str`, its `"=" not in value` guard raises no error but
    matches nothing useful, and `json.dumps(default=str)` converts the
    object to a credential-bearing string after redaction has finished.

    The mutation returns the OBJECT rather than a neutered string on
    purpose: an identity function on the string form would still be
    redacted by the value rule, which would prove nothing about the
    ordering.
    """
    original = audit._stringify_leaf

    control_arm = test_audit.TestDeferredStringificationIsRedacted()
    with pytest.MonkeyPatch.context() as arm_mp:
        control_arm.test_a_deferred_dsn_under_an_innocuous_key_is_redacted(
            tmp_path / "control", arm_mp
        )

    monkeypatch.setattr(audit, "_redact_value_string", _passthrough_unless_str)
    monkeypatch.setattr(audit, "_stringify_leaf", lambda value: value)

    mutated_arm = test_audit.TestDeferredStringificationIsRedacted()
    with pytest.MonkeyPatch.context() as arm_mp, pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_a_deferred_dsn_under_an_innocuous_key_is_redacted(
            tmp_path / "mutated", arm_mp
        )

    monkeypatch.undo()
    assert audit._stringify_leaf is original
    assert audit._redact_value_string is _ORIGINAL_REDACT_VALUE_STRING


#: Captured at import so the restoration check below compares against the
#: genuine original rather than against whatever the last mutation left.
_ORIGINAL_REDACT_VALUE_STRING = audit._redact_value_string


def _passthrough_unless_str(value: Any) -> Any:
    """The pre-fix `_redact_value_string`, which only ever saw strings.

    Needed alongside the `_stringify_leaf` mutation because the real
    function calls `str` methods unconditionally and would raise on the
    object the mutation now lets through, and a raised `TypeError` inside
    `record_tool_call`'s best-effort handler would suppress the line
    entirely. That would turn the arm red for the wrong reason: no line at
    all rather than a leaked credential. Restoring the pre-fix contract,
    strings scanned and everything else untouched, reproduces the actual
    historical behaviour.
    """
    if isinstance(value, str):
        return _ORIGINAL_REDACT_VALUE_STRING(value)
    return value


# ---------------------------------------------------------------------------
# Mutation 19: the tracing redactor's error bound removed (A-5.0-13, J-03).
# ---------------------------------------------------------------------------


def test_error_bound_removed_turns_the_run_error_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A-5.0-13: before the bound existed, `redact_payload` walked dicts
    and lists and returned every other type unchanged, so the string
    langsmith wraps as `{"error": ...}` came back byte-identical carrying a
    live credential. Making `_is_error_text_key` answer False restores
    exactly that state: the dict walk still runs and the two redaction
    passes still fire, so only the third pass disappears.

    Targeting the key test rather than `_bound_error_text` is deliberate.
    Neutering the bound function alone would still leave every value under
    an error key replaced by something, which is not the defect; the defect
    was the free text reaching the wire, and only a key test that says "this
    is not an error field" reproduces it.
    """
    original = tracing._is_error_text_key

    control_mp = pytest.MonkeyPatch()
    try:
        test_tracing.test_api_key_in_a_run_error_never_reaches_the_langsmith_error_field(
            control_mp
        )
    finally:
        control_mp.undo()

    monkeypatch.setattr(tracing, "_is_error_text_key", lambda key: False)

    mutated_mp = pytest.MonkeyPatch()
    try:
        with pytest.raises(_ARM_WENT_RED):
            test_tracing.test_api_key_in_a_run_error_never_reaches_the_langsmith_error_field(
                mutated_mp
            )
    finally:
        mutated_mp.undo()

    monkeypatch.undo()
    assert tracing._is_error_text_key is original


def test_bound_error_text_made_a_passthrough_turns_the_dsn_arm_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second layer, mutated alone. Mutation 18 proves the key test
    discriminates; this proves the bound itself is what removes the
    credential rather than some incidental rewrite elsewhere in the walk.
    Both must exist, because either one going red says nothing about
    whether the other could.
    """
    original = tracing._bound_error_text

    control_mp = pytest.MonkeyPatch()
    try:
        test_tracing.test_dsn_password_in_a_run_error_never_reaches_the_langsmith_error_field(
            control_mp
        )
    finally:
        control_mp.undo()

    monkeypatch.setattr(tracing, "_bound_error_text", lambda value: value)

    mutated_mp = pytest.MonkeyPatch()
    try:
        with pytest.raises(_ARM_WENT_RED):
            test_tracing.test_dsn_password_in_a_run_error_never_reaches_the_langsmith_error_field(
                mutated_mp
            )
    finally:
        mutated_mp.undo()

    monkeypatch.undo()
    assert tracing._bound_error_text is original


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
