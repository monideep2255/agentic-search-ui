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

Six mutations are covered, one per function, each named for the specific
regression it reproduces. This sentence does not say "every arm in this
phase's premise gates is covered": build phase 4.15 shipped that exact
completeness claim wrong three times, once inside the fix for the finding
that said so the first time. Count the functions below if you want to know
what is actually covered.

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

Depends on:
    - system_03_search_agent.observability.config
    - system_03_search_agent.observability.tracing
    - system_03_search_agent.observability.audit
    - system_03_search_agent.observability.analytics
    - system_03_search_agent.tools.ncbi_transport
    - tests.system_03_search_agent.observability.test_tracing
    - tests.system_03_search_agent.observability.test_audit
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
from typing import Any

import pytest
import requests

from system_03_search_agent.observability import analytics, audit, config, tracing
from system_03_search_agent.tools import ncbi_transport
from tests.system_03_search_agent.observability import (
    test_analytics,
    test_audit,
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

    control_arm = test_audit.TestValueLevelRedaction()
    control_arm.test_reproduction_api_key_in_url_under_endpoint_key(
        tmp_path / "control", pytest.MonkeyPatch()
    )

    monkeypatch.setattr(audit, "_redact_value_string", lambda value: value)

    mutated_arm = test_audit.TestValueLevelRedaction()
    with pytest.raises(_ARM_WENT_RED):
        mutated_arm.test_reproduction_api_key_in_url_under_endpoint_key(
            tmp_path / "mutated", pytest.MonkeyPatch()
        )

    monkeypatch.undo()
    assert audit._redact_value_string is original


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
    """
    original = ncbi_transport._endpoint_for_audit

    control_arm = test_wiring.TestCredentialNeverLeaksThroughTheTransport()
    _run_async(
        control_arm.test_api_key_reaches_the_request_but_never_the_audit_line(
            tmp_path / "control", pytest.MonkeyPatch()
        )
    )

    monkeypatch.setattr(ncbi_transport, "_endpoint_for_audit", lambda url: url)

    mutated_arm = test_wiring.TestCredentialNeverLeaksThroughTheTransport()
    with pytest.raises(_ARM_WENT_RED):
        _run_async(
            mutated_arm.test_api_key_reaches_the_request_but_never_the_audit_line(
                tmp_path / "mutated", pytest.MonkeyPatch()
            )
        )

    monkeypatch.undo()
    assert ncbi_transport._endpoint_for_audit is original


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


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
