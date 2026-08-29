"""Tests for `observability.analytics` (T-5.0-04, tech spec Section 20.2).

Every arm here is built to FAIL when the property it names is false, per
this repository's own eleven-instance history of assertions that could not
fail (`.claude/rules/goal-contracts.md`). Concretely:

    - The "no key configured" arm asserts against a call-recording
      transport spy, not merely that `capture_event` did not raise, so a
      future change that fires a request anyway with a garbage key would
      be caught.
    - The "raw free text is refused" arms use the SAME spy and assert zero
      calls were recorded, which is a stronger claim than "the string is
      absent from the body": if `build_properties` ever regressed to
      forwarding an unregistered or mistyped property, the spy would
      record a call and the assertion would fail before any string search
      was needed.
    - The allowlist-not-blocklist arm sends a value with none of the
      shapes a blocklist would flag (no script tags, no SQL syntax, no
      profanity), specifically because a blocklist would let it through;
      only an allowlist that requires the KEY to be pre-registered rejects
      it, which is the property this arm exists to prove.

Coverage statement (`.claude/rules/goal-contracts.md`'s "a verify surface
must state its own coverage"): every arm here mocks the HTTP transport with
`httpx.MockTransport`, per `test_pathogen_ftp_transport.py`'s established
pattern in this repository, and NEVER sends a request to the real PostHog
service (T-5.0-04's ticket is explicit that no test may assert a 200 from
the real service as evidence of anything, since F-5.0-05 measured that a
200 there proves only reachability). This file does not exercise
`config.analytics_enabled`'s own truthiness and empty-string-is-absent
rules beyond what one gating arm below needs; the full matrix for those
rules is `test_config.py`'s job, not this file's, so it is not repeated
here.

Depends on:
    - system_03_search_agent.observability.analytics (module under test)
"""

from __future__ import annotations

import json

import httpx
import pytest

from system_03_search_agent.observability import analytics

POSTHOG_HOST = "https://us.i.posthog.com"
POSTHOG_KEY = "phc_test_key_not_real"


@pytest.fixture(autouse=True)
def _clean_posthog_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the two PostHog env vars before every arm.

    Autouse so an arm that means to test the disabled path cannot pass for
    the wrong reason because the developer's own shell happens to export
    `POSTHOG_API_KEY`, the same failure `test_config.py`'s own autouse
    fixture exists to prevent.
    """
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
    monkeypatch.delenv("POSTHOG_HOST", raising=False)


def _enable_posthog(monkeypatch: pytest.MonkeyPatch, *, host: str = POSTHOG_HOST) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", POSTHOG_KEY)
    monkeypatch.setenv("POSTHOG_HOST", host)


class _RecordingTransport:
    """A call-recording spy, not just a canned responder.

    `test_body_carries_required_fields` and every "must not send" arm below
    assert against `.requests`, the actual list of calls made, rather than
    only checking `capture_event` did not raise. A spy that only returns a
    response cannot prove ABSENCE of a call; this one can.
    """

    def __init__(self, response: httpx.Response | None = None,
                 raises: Exception | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self._response = response or httpx.Response(200, json={"status": "Ok"})
        self._raises = raises

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._raises is not None:
            raise self._raises
        return self._response

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(self))


# ---------------------------------------------------------------------------
# Gating: no credential means provably zero outbound calls.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_key_configured_makes_zero_outbound_calls() -> None:
    """`_clean_posthog_env` already left POSTHOG_API_KEY unset."""
    spy = _RecordingTransport()
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.QUERY_COMPLETED,
            distinct_id="guest:11111111-1111-1111-1111-111111111111",
            properties={"query_class": "lookup"},
            client=client,
        )
    assert spy.requests == [], (
        f"expected zero outbound calls with no key configured, got {len(spy.requests)}"
    )


# ---------------------------------------------------------------------------
# The wire body: the documented path, and the four required fields.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_body_carries_required_fields_at_documented_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_posthog(monkeypatch)
    spy = _RecordingTransport()
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.FEEDBACK_SUBMITTED,
            distinct_id="user:22222222-2222-2222-2222-222222222222",
            properties={"rating": "up"},
            client=client,
        )

    assert len(spy.requests) == 1, "expected exactly one outbound call"
    request = spy.requests[0]
    assert str(request.url) == POSTHOG_HOST + "/i/v0/e"

    body = json.loads(request.content)
    assert body["api_key"] == POSTHOG_KEY
    assert body["event"] == "feedback_submitted"
    assert body["distinct_id"] == "user:22222222-2222-2222-2222-222222222222"
    assert body.get("timestamp"), "timestamp must be present and non-empty"
    assert body["properties"] == {"rating": "up"}


# ---------------------------------------------------------------------------
# The properties builder: safe by construction.
# ---------------------------------------------------------------------------


RAW_QUESTION = "What is the association between BRCA1 and hereditary breast cancer risk?"


@pytest.mark.asyncio
async def test_capture_event_drops_event_carrying_raw_free_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caller mistakenly attaches the real question text under a
    registered enum-shaped key, the realistic way a leak would actually
    happen (not a made-up key nobody would type). The whole event must be
    refused, not sent with a sanitized value, so the spy must record ZERO
    calls, and the raw text can therefore appear in no serialized body at
    all, since no body was ever built to send.
    """
    _enable_posthog(monkeypatch)
    spy = _RecordingTransport()
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.QUERY_COMPLETED,
            distinct_id="guest:33333333-3333-3333-3333-333333333333",
            properties={"query_class": RAW_QUESTION},
            client=client,
        )
    assert spy.requests == [], "a raw free-text value must never reach the transport"


def test_build_properties_rejects_raw_free_text_directly() -> None:
    with pytest.raises(analytics.UnsafePropertyError):
        analytics.build_properties(query_class=RAW_QUESTION)


@pytest.mark.asyncio
async def test_capture_event_drops_event_with_unregistered_property_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same "must not send" proof, for a property key that was simply
    never registered, an innocuous value with none of the shapes a
    blocklist would flag.
    """
    _enable_posthog(monkeypatch)
    spy = _RecordingTransport()
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.QUERY_COMPLETED,
            distinct_id="guest:44444444-4444-4444-4444-444444444444",
            properties={"totally_unhardcoded_property": "harmless"},
            client=client,
        )
    assert spy.requests == []


def test_build_properties_rejects_unregistered_key_proving_allowlist_not_blocklist() -> None:
    """`"harmless"` triggers no blocklist pattern (no script tag, no SQL
    syntax, no length past any sane cap). It is refused solely because the
    KEY `totally_unhardcoded_property` was never added to `_PROPERTY_SCHEMA`,
    which is only possible under an allowlist design; a blocklist scanning
    this value for danger signals would find none and let it through.
    """
    with pytest.raises(analytics.UnsafePropertyError):
        analytics.build_properties(totally_unhardcoded_property="harmless")


def test_build_properties_accepts_every_registered_shape() -> None:
    """The positive path, so a future edit that breaks a valid combination
    (not just an invalid one) has an arm to fail against.
    """
    safe = analytics.build_properties(
        query_class="multi_hop",
        trust_signal="answer",
        rubric_outcome="pass",
        rating="down",
        has_citations=True,
        was_flagged=False,
        citation_flag_count=3,
        latency_ms=1450.5,
    )
    assert safe == {
        "query_class": "multi_hop",
        "trust_signal": "answer",
        "rubric_outcome": "pass",
        "rating": "down",
        "has_citations": True,
        "was_flagged": False,
        "citation_flag_count": 3,
        "latency_ms": 1450.5,
    }


def test_build_properties_rejects_bool_under_a_count_typed_key() -> None:
    """`bool` is a subclass of `int` in Python; a naive `isinstance(value,
    (int, float))` check would silently accept `True` as `1` under a
    count-typed property. This asserts the explicit exclusion holds.
    """
    with pytest.raises(analytics.UnsafePropertyError):
        analytics.build_properties(citation_flag_count=True)


def test_build_properties_rejects_out_of_set_enum_value() -> None:
    with pytest.raises(analytics.UnsafePropertyError):
        analytics.build_properties(rubric_outcome="maybe")


def test_build_properties_rejects_non_string_under_an_enum_typed_key() -> None:
    with pytest.raises(analytics.UnsafePropertyError):
        analytics.build_properties(trust_signal=1)


# ---------------------------------------------------------------------------
# distinct_id: truncation and the no-owner fallback.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_distinct_id_longer_than_200_chars_is_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_posthog(monkeypatch)
    long_id = "guest:" + ("a" * 250)
    assert len(long_id) > 200

    spy = _RecordingTransport()
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.QUERY_COMPLETED,
            distinct_id=long_id,
            client=client,
        )

    body = json.loads(spy.requests[0].content)
    assert len(body["distinct_id"]) == 200
    assert body["distinct_id"] == long_id[:200]


@pytest.mark.asyncio
async def test_no_owner_falls_back_to_the_anonymous_bucket_rather_than_dropping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_posthog(monkeypatch)
    spy = _RecordingTransport()
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.QUERY_COMPLETED,
            distinct_id=None,
            client=client,
        )
    assert len(spy.requests) == 1, "an identity-less caller must still be counted"
    body = json.loads(spy.requests[0].content)
    assert body["distinct_id"] == "anonymous"


# ---------------------------------------------------------------------------
# Transport failure discipline: never raise to the caller.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transport_timeout_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_posthog(monkeypatch)
    spy = _RecordingTransport(raises=httpx.ConnectTimeout("simulated timeout"))
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.QUERY_COMPLETED,
            distinct_id="guest:55555555-5555-5555-5555-555555555555",
            client=client,
        )
    # Reaching this line at all is the assertion: a regression that lets
    # the ConnectTimeout propagate fails the test by raising through it.
    assert len(spy.requests) == 1


@pytest.mark.asyncio
async def test_transport_connection_error_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_posthog(monkeypatch)
    spy = _RecordingTransport(raises=httpx.ConnectError("simulated connection failure"))
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.QUERY_COMPLETED,
            distinct_id="guest:66666666-6666-6666-6666-666666666666",
            client=client,
        )
    assert len(spy.requests) == 1


@pytest.mark.asyncio
async def test_http_500_response_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_posthog(monkeypatch)
    spy = _RecordingTransport(response=httpx.Response(500, text="internal error"))
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.QUERY_COMPLETED,
            distinct_id="guest:77777777-7777-7777-7777-777777777777",
            client=client,
        )
    assert len(spy.requests) == 1


# ---------------------------------------------------------------------------
# The declared timeout is real, not defaulted.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_declared_timeout_is_passed_explicitly_to_httpx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`httpx.Client.build_request` only writes `extensions["timeout"]`
    from the CALL's own `timeout=` argument when one was actually passed;
    a call that relies on the client's default never sets it to this
    module's own constant. Asserting the exact value, rather than mere
    presence, is what proves this is a declared per-call timeout and not
    whatever httpx.AsyncClient() happens to default to (5.0s, a different
    number from this module's 4.0s on purpose, see `analytics.py`'s own
    comment on `CAPTURE_TIMEOUT_SECONDS`).
    """
    _enable_posthog(monkeypatch)
    spy = _RecordingTransport()
    async with spy.client() as client:
        await analytics.capture_event(
            analytics.AnalyticsEvent.QUERY_COMPLETED,
            distinct_id="guest:88888888-8888-8888-8888-888888888888",
            client=client,
        )

    request = spy.requests[0]
    declared = request.extensions["timeout"]
    expected = httpx.Timeout(analytics.CAPTURE_TIMEOUT_SECONDS).as_dict()
    assert declared == expected, f"expected {expected}, got {declared}"


# ---------------------------------------------------------------------------
# The event catalogue itself: closed, and matching the wire spelling.
# ---------------------------------------------------------------------------


def test_event_catalogue_is_exactly_the_three_honestly_built_signals() -> None:
    """Locks the closed set. A future addition of `saved_query_created`,
    a follow-up funnel event, or a session-length event must edit this
    test deliberately, per the ticket's explicit instruction not to
    approximate the three signals that are not built yet.
    """
    assert {member.value for member in analytics.AnalyticsEvent} == {
        "query_completed",
        "feedback_submitted",
        "trust_outcome_recorded",
    }
