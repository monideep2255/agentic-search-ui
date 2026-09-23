"""Tests for `ProxySchemeMiddleware` (item 11.30 fix B).

Owner: worker A, overnight run of 2026-09-22 into 2026-09-23
(`testing/Developer/reports/2026-09-23_overnight/contract.md`). This is a
checking role, not the maker's: the middleware under test was written by the
planner. This file's job is to prove it does what its own docstring claims,
and to catch it if a future edit quietly widens what it trusts.

Two groups of arms:

  Unit arms, against `ProxySchemeMiddleware` directly, wrapping a tiny
  recording ASGI app rather than the full FastAPI app. This is what proves
  `scope["client"]` never moves: the full app has no route that reports back
  the scope it received, so the only honest way to see it is to record it at
  the point the middleware hands off, per this ticket's own instruction to
  add a probe rather than read the source.

  Integration arms, against the real `app` and its real `/mcp` mount, over
  `TestClient`, reproducing the exact `location` values this ticket's brief
  states as already measured. These prove the unit-level scheme parsing
  actually reaches Starlette's redirect builder in the running app, not only
  in isolation.

`railway.json` is UNCHANGED by this fix and by this test file. Confirmed by
inspection during this work: its `startCommand` carries no
`--forwarded-allow-ips` flag before or after `proxy_scheme.py` landed. The
fix is deliberately in the app rather than in that deployment setting, per
`proxy_scheme.py`'s own docstring ("WHY IN THE APP RATHER THAN IN THE START
COMMAND"), so it travels with the code and is covered by the same gates as
the code, and the develop and production apps cannot silently disagree.

UPDATED 2026-09-23. This worker filed a finding that the pre-fix version of
`proxy_scheme.py` read `x-forwarded-proto` and could set the scope to
`"http"` on explicit request, an in-application downgrade path the
maker had not intended to leave open once the header was read at all. The
maker (not this worker, who checks but does not fix) answered it
structurally: `_forwarded_scheme` is now UPGRADE ONLY, returning `"https"`
or `None`, never `"http"`. This worker then re-checked the new code for any
input shape that still reaches a downgrade (found none, by structural
reading and by the arms below) and rewrote or added arms accordingly.

MUTATION PROOF, run once by hand rather than embedded here, and reported in
this worker's handback rather than re-run on every `pytest` invocation.
Four mutations, each applied by monkeypatching in a throwaway script and
reverted immediately after, never by writing to `proxy_scheme.py` on disk:

  Mutation A, middleware disabled: `_forwarded_scheme` always returns
  `None`, as if the header were never read. Killed 7 arms: both scheme
  arms that require the header to actually change something
  (`test_https_header_sets_the_scheme`,
  `test_mixed_case_header_value_is_folded_before_matching`,
  `test_comma_separated_list_uses_the_first_entry`,
  `test_scope_is_not_mutated_in_place`,
  `test_websocket_scope_is_also_translated`,
  `test_integration_https_header_redirects_to_https`,
  `test_integration_comma_list_redirects_to_https`).

  Mutation B, validation removed: `_forwarded_scheme` returns the raw first
  header value unchecked, whatever it is. Killed 11 arms: the 4 that exist
  to prove the allowlist from an http start
  (`test_unknown_value_is_ignored`, `test_empty_header_value_is_ignored`,
  `test_duplicate_header_honours_only_the_first_occurrence`,
  `test_integration_unknown_value_stays_plaintext`), plus 6 of the 7
  downgrade-safety arms added this session
  (`test_forged_http_header_does_not_downgrade_an_https_scope`,
  `test_comma_list_leading_http_does_not_downgrade_even_with_https_later`,
  `test_mixed_case_http_does_not_downgrade`,
  `test_whitespace_padded_http_does_not_downgrade`,
  `test_empty_value_does_not_downgrade_an_https_scope`,
  `test_duplicate_header_leading_http_does_not_downgrade`), plus
  `test_malformed_header_bytes_do_not_crash_or_downgrade`, whose payload
  (`http\x00`) an unvalidated passthrough assigns to `scope["scheme"]`
  verbatim, which is not `"https"` and fails the assertion.

  Mutation C, the address trusted too: `ProxySchemeMiddleware.__call__`
  patched to also rewrite `scope["client"]` from a forged
  `X-Forwarded-For`, simulating the exact regression the design refuses.
  Killed `test_client_address_is_identical_with_and_without_forwarded_for`,
  the load-bearing arm, and only that arm, which is the correct blast
  radius for a mutation that touches nothing but client trust.

  Mutation D, the downgrade regression itself: `_forwarded_scheme` restored
  to the pre-2026-09-23 two-member allowlist (`http` and `https` both
  accepted). This is the mutation that exists specifically to prove the
  security property the maker's rewrite claims. Killed 5 arms:
  `test_forged_http_header_does_not_downgrade_an_https_scope`,
  `test_comma_list_leading_http_does_not_downgrade_even_with_https_later`,
  `test_mixed_case_http_does_not_downgrade`,
  `test_whitespace_padded_http_does_not_downgrade`,
  `test_duplicate_header_leading_http_does_not_downgrade`. At least one arm
  dying under this mutation is the bar the coordinator set for this
  worker's re-check; five did, so the suite covers the property.
  `test_empty_value_does_not_downgrade_an_https_scope` and
  `test_malformed_header_bytes_do_not_crash_or_downgrade` do NOT die under
  D, because neither input literally equals `"http"`, the one value D
  re-admits; both die under B instead, which removes the allowlist rather
  than only widening it by one member.

  4 arms are NOT killed by any of the four mutations, each stating so in
  its own docstring with the reason: `test_header_absent_leaves_scheme_untouched`,
  `test_http_header_is_ignored_not_honoured`,
  `test_reversed_comma_list_ignores_the_first_entry_and_does_not_scan_further`,
  and `test_integration_no_header_redirects_to_plaintext`. Each is a
  control, or an explicit-`"http"`-from-an-http-start case where every
  mutation available here coincides with the expected value; each is
  load-bearing only in combination with its named paired arm, which the
  mutation does kill.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.adapters.web_sse.proxy_scheme import ProxySchemeMiddleware

# An address that is neither the real test-harness client nor anything an
# attacker would plausibly be handed for free. Standing in for "whatever the
# server itself observed the connecting peer to be", which is the one thing
# a caller-controlled header must never override.
_REAL_CLIENT_ADDRESS = ("198.51.100.9", 4000)

# An address a caller could put in `X-Forwarded-For` for free. Distinct from
# `_REAL_CLIENT_ADDRESS` on purpose: if the middleware ever let this value
# reach `scope["client"]`, the two arms below that compare against it would
# stop being able to tell "untouched" from "overwritten by the header".
_FORGED_FORWARDED_FOR = "203.0.113.77"


class _ScopeRecorder:
    """A minimal ASGI app that records the scope it receives and answers 200.

    This is the probe this ticket's brief asks for in place of reading
    `proxy_scheme.py`'s source: every unit arm below asserts on
    `self.last_scope`, what the middleware actually handed to whatever runs
    next, never on how the middleware is implemented.
    """

    def __init__(self) -> None:
        self.last_scope: dict[str, Any] | None = None

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        self.last_scope = scope
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})


def _encoded_headers(pairs: list[tuple[str, str]]) -> list[tuple[bytes, bytes]]:
    return [(name.encode("latin-1"), value.encode("latin-1")) for name, value in pairs]


async def _run_through_middleware(
    header_pairs: list[tuple[str, str]],
    client_address: tuple[str, int] = _REAL_CLIENT_ADDRESS,
    starting_scheme: str = "http",
    raw_headers: list[tuple[bytes, bytes]] | None = None,
) -> _ScopeRecorder:
    """Send one HTTP request through a fresh `ProxySchemeMiddleware` instance.

    `starting_scheme` defaults to `"http"`, the raw value uvicorn would set for
    a plaintext connection from Railway's edge (the exact situation
    `proxy_scheme.py`'s docstring describes), which is what makes an assertion
    of `"https"` afterward a real check of the middleware for the UPGRADE
    arms. The DOWNGRADE arms below pass `starting_scheme="https"` instead: a
    genuine HTTPS connection whose scope already carries `"https"`, which is
    the only starting point a downgrade attempt could actually matter against.
    Asserting "stays http" from an http start proves nothing about downgrade
    safety, since there was nothing to downgrade.

    `raw_headers`, when given, replaces `_encoded_headers(header_pairs)`
    entirely, for the one arm that needs to send bytes `_encoded_headers`
    cannot produce (an embedded null byte alongside ordinary text).
    """
    recorder = _ScopeRecorder()
    middleware = ProxySchemeMiddleware(recorder)
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": raw_headers if raw_headers is not None else _encoded_headers(header_pairs),
        "client": client_address,
        "server": ("testserver", 80),
        "scheme": starting_scheme,
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await middleware(scope, receive, send)
    assert recorder.last_scope is not None, (
        "the recorder never ran, so this helper measured nothing; the "
        "middleware must have swallowed the request instead of calling "
        "through to `self.app`"
    )
    return recorder


# ---------------------------------------------------------------------------
# Unit arms: scope["scheme"], one per header shape.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_header_absent_leaves_scheme_untouched() -> None:
    """No `x-forwarded-proto` at all: the scope keeps whatever scheme the
    server itself observed.

    Populate check: the starting scope is `"http"` (see
    `_run_through_middleware`), so an implementation that always forced
    `"https"` regardless of input would fail this arm, and one that always
    left the scope alone would pass it vacuously only if paired with the
    next arm also passing, which is why the two are read together.

    Mutation result: NOT independently killed by either mutation run for
    this worker's mutation proof (disabling `_forwarded_scheme` entirely, or
    letting it return an unvalidated raw value). Both leave an absent header
    resolving to nothing, so the scope stays `"http"` either way and this
    arm passes under both mutations. It only catches a regression in
    combination with `test_https_header_sets_the_scheme`, which mutation A
    does kill: a middleware that always forced `"https"` would fail this arm
    while passing that one, and a middleware that never set anything would
    fail that one while passing this one.
    """
    recorder = await _run_through_middleware(header_pairs=[])
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "http"


@pytest.mark.asyncio
async def test_https_header_sets_the_scheme() -> None:
    """The plain case this fix exists for: `x-forwarded-proto: https` flips
    the scope from `"http"` to `"https"`.

    Populate check: the starting scope is `"http"`, established in
    `_run_through_middleware`, so this arm would fail against a middleware
    that does nothing, which is exactly the pre-fix behaviour it exists to
    catch a regression back to.
    """
    recorder = await _run_through_middleware(header_pairs=[("x-forwarded-proto", "https")])
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


@pytest.mark.asyncio
async def test_http_header_is_ignored_not_honoured() -> None:
    """CORRECTED 2026-09-23. `_forwarded_scheme` used to accept an explicit
    `x-forwarded-proto: http` and set the scope to `"http"`. The maker
    rewrote it to be UPGRADE ONLY after this worker's finding that the
    previous version's rejected-alternative reasoning was substantive: `http`
    is now treated exactly like an unrecognized value, resolving to `None`,
    never assigned explicitly. This arm proves the new "ignored" behaviour
    from an http-starting scope; the real security property, that this
    cannot downgrade an ALREADY-https scope, is a separate arm below
    (`test_forged_http_header_does_not_downgrade_an_https_scope`), because
    starting from http here cannot distinguish "ignored" from "accepted and
    happened to match".

    Populate check: paired with `test_https_header_sets_the_scheme` above.
    `_forwarded_scheme` returning `None` for `"http"` and the scope starting
    at `"http"` are two different facts that both produce the same observed
    `"http"` result; this arm alone cannot tell them apart, which is exactly
    why the downgrade-from-https arm below exists as the arm that can.

    Mutation result: NOT killed by mutations A, B, C, or D (see the module
    docstring). Every one of those mutations either disables the middleware
    entirely (leaves `"http"` unchanged, matching this arm) or only affects
    inputs other than a bare `"http"` from an http-starting scope. Killed
    only in combination with `test_forged_http_header_does_not_downgrade_an_https_scope`,
    which mutation D does kill.
    """
    recorder = await _run_through_middleware(header_pairs=[("x-forwarded-proto", "http")])
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "http"


@pytest.mark.asyncio
async def test_mixed_case_header_value_is_folded_before_matching() -> None:
    """`X-Forwarded-Proto: HTTPS`, the header NAME already case-insensitive at
    the ASGI layer and the VALUE folded by `_forwarded_scheme` itself, still
    resolves to `"https"`.

    Populate check: the starting scope is `"http"`. A middleware that
    case-sensitively compared against `"https"` only would fail this arm
    while passing `test_https_header_sets_the_scheme`, which is the specific
    regression this arm exists to catch that the lowercase arm cannot.
    """
    recorder = await _run_through_middleware(header_pairs=[("x-forwarded-proto", "HTTPS")])
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


@pytest.mark.asyncio
async def test_comma_separated_list_uses_the_first_entry() -> None:
    """`x-forwarded-proto: https, http`, the shape a request crossing more
    than one proxy hop produces, resolves from the FIRST entry, the scheme
    the original client actually spoke.

    Populate check: the second entry in the list is `"http"`, the opposite of
    the expected result, so an implementation that read the LAST entry
    instead of the first would fail this arm loudly rather than passing by
    coincidence.
    """
    recorder = await _run_through_middleware(header_pairs=[("x-forwarded-proto", "https, http")])
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


@pytest.mark.asyncio
async def test_reversed_comma_list_ignores_the_first_entry_and_does_not_scan_further() -> None:
    """CORRECTED 2026-09-23. `x-forwarded-proto: http, https`: the FIRST entry
    is `"http"`, which under the new upgrade-only semantics resolves to
    `None`, so the scope stays whatever it started as. This is the mirror of
    `test_comma_separated_list_uses_the_first_entry`, and it now proves two
    things at once rather than one: first-entry authority (the same as
    before), AND that a valid `"https"` sitting later in the same list is
    never picked up as a fallback. An implementation that scanned the whole
    list for any occurrence of `"https"` would flip this scope to `"https"`
    and fail here while still passing the arm above.

    Populate check: the starting scope is `"http"`, so this arm alone still
    cannot tell "first entry read and ignored" apart from "list not read at
    all". The no-scan-past-first-entry property, from an https start, is
    covered by `test_comma_list_leading_http_does_not_downgrade_even_with_https_later`
    below, which can fail in a way this arm cannot.

    Mutation result: NOT killed by mutations A, B, C, or D. Same reason as
    `test_http_header_is_ignored_not_honoured` above: the first entry is
    `"http"` from an http-starting scope, a value none of the four mutations
    misreads into a change here. Killed only in combination with
    `test_comma_separated_list_uses_the_first_entry`, which mutation A does
    kill.
    """
    recorder = await _run_through_middleware(header_pairs=[("x-forwarded-proto", "http, https")])
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "http"


@pytest.mark.asyncio
async def test_unknown_value_is_ignored() -> None:
    """`x-forwarded-proto: ftp`, a value outside the two-member allowlist,
    leaves the scope untouched rather than being coerced to either scheme.

    Populate check: the starting scope is `"http"`. If the middleware ever
    changed from an allowlist to a denylist (`"not http means https"`, the
    exact shape its own docstring says it deliberately is not), this arm
    would flip to `"https"` and fail, which is the regression it exists to
    catch.
    """
    recorder = await _run_through_middleware(header_pairs=[("x-forwarded-proto", "ftp")])
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "http"


@pytest.mark.asyncio
async def test_empty_header_value_is_ignored() -> None:
    """`x-forwarded-proto: ` (present, empty) is treated the same as absent:
    the scope is left at `"http"`.

    Populate check: an implementation that skipped the allowlist check for an
    empty string, for example by treating a falsy value as "trust the raw
    scope" through a DIFFERENT code path than the intended one, could still
    coincidentally pass a naive "scheme is http" assertion; this arm's value
    is real (a genuine empty string sent on the wire), not the header being
    absent, so it exercises the parsing branch the absent-header arm does not.
    """
    recorder = await _run_through_middleware(header_pairs=[("x-forwarded-proto", "")])
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "http"


@pytest.mark.asyncio
async def test_duplicate_header_honours_only_the_first_occurrence() -> None:
    """Two separate `x-forwarded-proto` header lines, an ASGI header list can
    legally carry duplicates, and only the FIRST one encountered in scan
    order is read; the second is never consulted even to break a tie.

    Populate check: the first occurrence here is `"ftp"`, an unknown value
    that resolves to nothing, and the second is `"https"`, a valid one. If
    the middleware fell through to a later duplicate when the first one did
    not resolve, this arm would see `"https"` and fail; it asserts `"http"`,
    proving the fallthrough does not happen.
    """
    recorder = await _run_through_middleware(
        header_pairs=[("x-forwarded-proto", "ftp"), ("x-forwarded-proto", "https")]
    )
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "http"


# ---------------------------------------------------------------------------
# Downgrade-safety arms, added 2026-09-23. THE SECURITY PROPERTY: no value a
# caller can put in `x-forwarded-proto` may move a scope AWAY from `https`.
# Every arm here starts the scope at `"https"`, the one starting point a
# downgrade attempt could actually matter against, and built directly rather
# than through `TestClient`, since `TestClient` always connects as plain
# `http` and so can never represent "a genuine HTTPS request" at the scope
# level.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forged_http_header_does_not_downgrade_an_https_scope() -> None:
    """THE SECURITY PROPERTY, stated as the claim rather than as an
    implementation detail: a genuinely-HTTPS request (scope already
    `"https"`) that also carries a caller-forged `x-forwarded-proto: http`
    must still answer `"https"`. This is the one thing the header could ever
    usefully be forged for, since the header cannot lie the other direction
    (a caller cannot claim `https` for a request that was not, in a way that
    matters here: an actually-https claim only ever moves the scope TOWARD
    https).

    Populate check: the starting scope is `"https"`, not `"http"`. An
    implementation that still accepted `"http"` from the header, which is
    exactly what the pre-2026-09-23 version of `_forwarded_scheme` did,
    would flip this to `"http"` and fail. `test_http_header_is_ignored_not_honoured`
    above cannot catch that regression, because it starts from `"http"`,
    where "ignored" and "accepted" are indistinguishable; this arm is the one
    that can tell them apart.
    """
    recorder = await _run_through_middleware(
        header_pairs=[("x-forwarded-proto", "http")], starting_scheme="https"
    )
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https", (
        "a forged x-forwarded-proto: http downgraded a genuinely https scope; "
        "this is the exact defect item 11.30 fix B exists to close, now "
        "reachable from inside the application's own header handling rather "
        "than only from the deployment layer"
    )


@pytest.mark.asyncio
async def test_comma_list_leading_http_does_not_downgrade_even_with_https_later() -> None:
    """`x-forwarded-proto: http, https` against an https-starting scope: the
    first entry is `"http"`, so this must stay `"https"` (unaffected), never
    fall back to `"http"` and never opportunistically pick up the later
    `"https"` either. Only the equality with the starting value proves
    anything here; the scope already carries `"https"`, so "stays https"
    could otherwise mean "correctly ignored" or "incorrectly re-derived from
    the second entry", and this arm cannot tell those apart on its own,
    which is why `test_reversed_comma_list_ignores_the_first_entry_and_does_not_scan_further`
    above pins the from-http-start version, where the two are distinguishable.

    Populate check: paired with the arm above. If a future change made
    `_forwarded_scheme` scan the whole list for any `"https"` instead of
    reading only the first entry, `test_reversed_comma_list_ignores_the_first_entry_and_does_not_scan_further`
    (which starts at `"http"`) would flip to `"https"` and fail; this arm
    alone would stay green either way, since https-in equals https-out is
    consistent with both a correct and a scanning implementation.
    """
    recorder = await _run_through_middleware(
        header_pairs=[("x-forwarded-proto", "http, https")], starting_scheme="https"
    )
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


@pytest.mark.asyncio
async def test_mixed_case_http_does_not_downgrade() -> None:
    """`x-forwarded-proto: HTTP` (or any other casing of the literal `http`)
    against an https-starting scope must stay `"https"`. Case folding runs
    before the allowlist comparison in `_forwarded_scheme`, so a case
    variant of `http` must be rejected exactly as the lowercase form is.

    Populate check: the starting scope is `"https"`. An implementation that
    folded case only for the `https` comparison and matched `http` variants
    case-sensitively (in this specific mutated case, comparing raw
    `"HTTP"` against a lowercase-only rejection list and accidentally
    falling through to acceptance) would downgrade this scope and fail here.
    """
    recorder = await _run_through_middleware(
        header_pairs=[("x-forwarded-proto", "HTTP")], starting_scheme="https"
    )
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


@pytest.mark.asyncio
async def test_whitespace_padded_http_does_not_downgrade() -> None:
    """`x-forwarded-proto: " http "` (leading and trailing spaces) against an
    https-starting scope must stay `"https"`. `_forwarded_scheme` strips
    whitespace before comparing, so a padded `http` is exactly as invalid as
    a bare one, not a way to smuggle a downgrade past a naive equality check.

    Populate check: the starting scope is `"https"`. An implementation that
    forgot to strip before comparing to `"http"` would not accidentally leak
    a downgrade here, since the raw padded string would fail even that
    comparison; the useful failure mode this catches instead is a future
    rewrite that starts stripping AFTER the allowlist check for `http`
    specifically rather than before, an asymmetry that would show up as this
    arm passing while a corresponding padded-`https` upgrade arm regresses.
    """
    recorder = await _run_through_middleware(
        header_pairs=[("x-forwarded-proto", "  http  ")], starting_scheme="https"
    )
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


@pytest.mark.asyncio
async def test_empty_value_does_not_downgrade_an_https_scope() -> None:
    """An empty `x-forwarded-proto:` value against an https-starting scope
    must stay `"https"`, the downgrade-direction twin of
    `test_empty_header_value_is_ignored` above, which only proves the
    from-http-start case.

    Populate check: the starting scope is `"https"`, so this arm can fail in
    a way the from-http arm cannot: an implementation that treated an empty
    string as falsy and therefore "no opinion, defer to caller intent" down
    some other code path than the intended allowlist rejection could still
    coincidentally leave an http-starting scope at `"http"` while genuinely
    mishandling an https-starting one.
    """
    recorder = await _run_through_middleware(
        header_pairs=[("x-forwarded-proto", "")], starting_scheme="https"
    )
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


@pytest.mark.asyncio
async def test_duplicate_header_leading_http_does_not_downgrade() -> None:
    """Two `x-forwarded-proto` header lines, first `"http"` then `"https"`,
    against an https-starting scope: only the first is read, it resolves to
    nothing, and the scope must stay `"https"`. The downgrade-direction twin
    of `test_duplicate_header_honours_only_the_first_occurrence` above.

    Populate check: the second header value here is `"https"`, the scope's
    OWN starting value. An implementation that fell through past a
    non-matching first entry to consult a second one would still produce
    `"https"` here, coincidentally matching the correct answer, so this arm
    is deliberately paired with (never a substitute for)
    `test_duplicate_header_honours_only_the_first_occurrence`, whose
    first-vs-second values are chosen so a fallthrough is visible from an
    http start. Kept here anyway because it is the shape a real attacker
    would actually send (lead with the forged downgrade, hope a fallback
    reads the second, genuine entry) and is worth a direct arm even though
    it cannot alone distinguish the two implementations.
    """
    recorder = await _run_through_middleware(
        header_pairs=[("x-forwarded-proto", "http"), ("x-forwarded-proto", "https")],
        starting_scheme="https",
    )
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


@pytest.mark.asyncio
async def test_malformed_header_bytes_do_not_crash_or_downgrade() -> None:
    """A header value that is not clean ASCII text: an embedded null byte
    sitting between otherwise-valid-looking characters. `latin-1` maps every
    byte 0-255 to a code point, so `bytes.decode("latin-1")` cannot raise
    here; the risk this arm actually checks is that the extra byte causes a
    false match (for example if some future rewrite used a substring or
    startswith comparison instead of exact equality) rather than a crash.

    Populate check: the starting scope is `"https"`. The payload
    `b"http\\x00"` differs from `b"https"` by more than the null byte alone
    (it is also the wrong length and the wrong trailing content), so an
    exact-equality comparison rejects it cleanly; an implementation using
    `startswith("http")` instead of `== "https"` would still reject this
    specific payload (it starts with `"http"` but is not `"https"` either),
    so this arm is a defence-in-depth check on well-formed-but-dirty input
    rather than a proof that every possible malformed shape is safe.
    """
    raw_headers = [(b"x-forwarded-proto", b"http\x00")]
    recorder = await _run_through_middleware(
        header_pairs=[], starting_scheme="https", raw_headers=raw_headers
    )
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


# ---------------------------------------------------------------------------
# The load-bearing arm: scope["client"] never moves.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_address_is_identical_with_and_without_forwarded_for() -> None:
    """THE POINT OF THE DESIGN. `proxy_scheme.py` reads `x-forwarded-proto`
    and touches nothing else; `scope["client"]` is never written. This is
    what keeps `auth/router.py`'s sign-in rate limit and
    `data/guest_sessions.py`'s guest-session binding, both keyed on the
    connection's own address, un-movable by a caller-supplied header.

    Two requests, identical except one carries a caller-forged
    `X-Forwarded-For` naming an address that is NOT the real connecting peer.
    `scope["client"]` must be the same tuple in both, and it must be the REAL
    address, never the forged one.

    Populate check: `_FORGED_FORWARDED_FOR` is a distinct, real-looking
    address (203.0.113.77) that differs from `_REAL_CLIENT_ADDRESS`
    (198.51.100.9). An arm that only asserted "client is not None" would pass
    even if the middleware silently adopted the forged value; asserting
    equality to `_REAL_CLIENT_ADDRESS`, and explicitly asserting the host
    differs from the forged value, is what makes this arm able to fail
    against a middleware that started trusting the address.
    """
    without_header = await _run_through_middleware(header_pairs=[])
    with_header = await _run_through_middleware(
        header_pairs=[
            ("x-forwarded-proto", "https"),
            ("x-forwarded-for", _FORGED_FORWARDED_FOR),
        ]
    )

    assert without_header.last_scope is not None
    assert with_header.last_scope is not None
    assert without_header.last_scope["client"] == _REAL_CLIENT_ADDRESS
    assert with_header.last_scope["client"] == _REAL_CLIENT_ADDRESS
    assert with_header.last_scope["client"] == without_header.last_scope["client"]
    assert with_header.last_scope["client"][0] != _FORGED_FORWARDED_FOR, (
        "scope['client'] took on the caller-forged X-Forwarded-For value; "
        "this is the exact rate-limit and guest-session identity bypass "
        "`proxy_scheme.py`'s docstring says the design refuses to open"
    )


@pytest.mark.asyncio
async def test_scope_is_not_mutated_in_place() -> None:
    """`proxy_scheme.py`'s own docstring states it builds a NEW dict rather
    than mutating the caller's scope in place, because an ASGI server may
    reuse a scope object across a request's lifetime. Confirmed here by
    identity, not by re-reading the source: the object the recorder receives
    is not the same object passed in.

    Populate check: an implementation that mutated `scope["scheme"] = ...`
    directly and returned would make `recorder.last_scope is original_scope`
    true, which this arm asserts is false.
    """
    original_scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": _encoded_headers([("x-forwarded-proto", "https")]),
        "client": _REAL_CLIENT_ADDRESS,
        "server": ("testserver", 80),
        "scheme": "http",
    }
    recorder = _ScopeRecorder()
    middleware = ProxySchemeMiddleware(recorder)

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        pass

    await middleware(original_scope, receive, send)
    assert recorder.last_scope is not None
    assert recorder.last_scope is not original_scope
    assert original_scope["scheme"] == "http", (
        "the original scope was mutated in place; a reused scope on a "
        "subsequent request would carry a stale scheme forward"
    )
    assert recorder.last_scope["scheme"] == "https"


@pytest.mark.asyncio
async def test_websocket_scope_is_also_translated() -> None:
    """The middleware checks `scope["type"] in ("http", "websocket")`, not
    `== "http"` alone. A websocket connect scope gets the same treatment.

    Populate check: the starting scope is `"http"` (technically the
    websocket scheme analog is `"ws"`, but the middleware's own condition
    keys on `scope["type"]`, not `scope["scheme"]`, so this reuses the same
    starting value deliberately to isolate the `type` branch). An
    implementation that narrowed the check to `scope["type"] == "http"` only
    would leave this scope untouched and fail here while every http arm
    above still passed.
    """
    recorder = _ScopeRecorder()
    middleware = ProxySchemeMiddleware(recorder)
    scope: dict[str, Any] = {
        "type": "websocket",
        "path": "/mcp",
        "headers": _encoded_headers([("x-forwarded-proto", "https")]),
        "client": _REAL_CLIENT_ADDRESS,
        "server": ("testserver", 80),
        "scheme": "http",
    }

    async def receive() -> dict[str, Any]:
        return {"type": "websocket.connect"}

    async def send(message: dict[str, Any]) -> None:
        pass

    await middleware(scope, receive, send)
    assert recorder.last_scope is not None
    assert recorder.last_scope["scheme"] == "https"


# ---------------------------------------------------------------------------
# Integration arms: the real app, the real /mcp mount, the real redirect.
# ---------------------------------------------------------------------------


def test_integration_no_header_redirects_to_plaintext() -> None:
    """Reproduces the pre-fix, still-current-without-the-header shape this
    ticket's brief states as already measured: no `X-Forwarded-Proto` at all
    means the redirect this app builds stays plaintext, because nothing told
    it otherwise.

    Populate check: this is intentionally the "nothing happened" case. Its
    job is to prove the other integration arms below are testing a REAL
    change, not a client default; if this one also came back `https://`,
    the arms that assert `https://` would be meaningless.

    Mutation result: NOT independently killed by either mutation run for
    this worker's mutation proof, the same control shape as
    `test_header_absent_leaves_scheme_untouched` above and for the same
    reason: it is the "absent header" case, so it stays `http://` under
    both mutations. It is killed only in combination with
    `test_integration_https_header_redirects_to_https`, which mutation A
    does kill.
    """
    client = TestClient(app)
    response = client.post("/mcp", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers.get("location") == "http://testserver/mcp/"


def test_integration_https_header_redirects_to_https() -> None:
    """The defect this fix closes, proven end to end: `x-forwarded-proto:
    https` on a request to the real app produces an `https://` `Location`.

    Populate check: paired directly with the no-header arm above, which
    proves the same app, same route, same client, answers `http://` when the
    header is absent. Only the header differs between the two arms.
    """
    client = TestClient(app)
    response = client.post("/mcp", headers={"x-forwarded-proto": "https"}, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers.get("location") == "https://testserver/mcp/"


def test_integration_comma_list_redirects_to_https() -> None:
    """`x-forwarded-proto: https, http` end to end: the real app's redirect
    follows the FIRST entry, matching the unit-level arm above.

    Populate check: the second entry is `"http"`, the opposite scheme, so a
    regression to "read the last entry" would produce `http://` here and
    fail, the same shape the unit arm's populate check states.
    """
    client = TestClient(app)
    response = client.post(
        "/mcp", headers={"x-forwarded-proto": "https, http"}, follow_redirects=False
    )
    assert response.status_code == 307
    assert response.headers.get("location") == "https://testserver/mcp/"


def test_integration_unknown_value_stays_plaintext() -> None:
    """`x-forwarded-proto: ftp` end to end: an unrecognized value is ignored,
    exactly as the unit-level arm predicts, and the real app's redirect
    stays plaintext rather than being coerced to either scheme.

    Populate check: `"ftp"` is neither `"http"` nor `"https"`; the arm would
    fail if either allowlist branch accepted it, or if the middleware fell
    back to treating "not http" as "assume https".
    """
    client = TestClient(app)
    response = client.post("/mcp", headers={"x-forwarded-proto": "ftp"}, follow_redirects=False)
    assert response.status_code == 307
    assert response.headers.get("location") == "http://testserver/mcp/"
