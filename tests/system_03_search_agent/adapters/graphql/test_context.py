"""Unit tests for `system_03_search_agent.adapters.graphql.context`.

Covers T-4.3-03's own acceptance surface directly, ahead of and independent
from `tests/.../test_phase_4_3_premise.py` (which drives the full schema
through the real router mounted on the real app, out of this ticket's reach
since `schema.py`, `router.py`, and `security.py` do not exist yet).

No live database. `resolve_user_from_bearer_token` and `decode_guest_token`
are monkeypatched at the names `context` imports them under, so these tests
exercise this module's own dispatch logic (which path gets tried, in which
order, and what each failure becomes) rather than re-proving the decode-
then-lookup logic those two functions already own and are already tested
elsewhere (`auth/dependencies.py`, `auth/guest.py`).

Every assertion below names, in a comment beside it, the mutation that
turns it red, matching this repository's mutation-proof discipline for a
gate-adjacent file (`tracker/phase_4.3.md`'s "Premise gate design" section,
and this repo's `test_types.py`/`test_fold.py` precedent for the same
package).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from system_03_search_agent.adapters.graphql import context as context_module
from system_03_search_agent.auth.dependencies import InvalidBearerTokenError


class _FakeUser:
    """A minimal stand-in for `data.models.User`. Python's duck typing means
    nothing in `context.py` ever does an `isinstance(..., User)` check, so a
    plain object with an `id` is sufficient and keeps these tests free of a
    live database, per this module's own docstring.
    """

    def __init__(self, user_id: str = "11111111-1111-1111-1111-111111111111") -> None:
        self.id = user_id


def _request(headers: list[tuple[bytes, bytes]]) -> Request:
    scope = {
        "type": "http",
        "headers": headers,
        "method": "POST",
        "path": "/graphql",
        "query_string": b"",
        "client": ("test", 123),
        "server": ("test", 80),
        "scheme": "http",
    }
    return Request(scope)


def _request_with_auth(value: str | None) -> Request:
    if value is None:
        return _request([])
    return _request([(b"authorization", value.encode())])


def _request_with_duplicate_auth(first: str, second: str) -> Request:
    return _request([(b"authorization", first.encode()), (b"authorization", second.encode())])


# ---------------------------------------------------------------------------
# _extract_bearer_header: the duplicated-header case (F-4.1-A-11's precedent
# on this surface).
# ---------------------------------------------------------------------------


class TestExtractBearerHeader:
    def test_a_single_header_is_returned_verbatim(self) -> None:
        # Mutation that turns this red: return None even when exactly one
        # header is present, or return a mangled value.
        request = _request_with_auth("Bearer abc123")
        assert context_module._extract_bearer_header(request) == "Bearer abc123"

    def test_a_missing_header_returns_none(self) -> None:
        # Mutation that turns this red: raise instead of returning None, or
        # return an empty string that would pass a truthiness check
        # downstream where None would not.
        request = _request_with_auth(None)
        assert context_module._extract_bearer_header(request) is None

    def test_a_duplicated_header_is_treated_as_absent(self) -> None:
        # Mutation that turns this red: drop the `getlist`/`len(...) > 1`
        # check and fall through to `headers.get(...)`, which resolves a
        # genuine duplicate first-wins rather than refusing it outright
        # (F-4.1-A-11's exact finding, on this surface's own transport).
        request = _request_with_duplicate_auth("Bearer one", "Bearer two")
        assert context_module._extract_bearer_header(request) is None


# ---------------------------------------------------------------------------
# _resolve_registered_principal: the dispatch order (registered path first,
# guest path only on that failure) and the two distinct refusal shapes.
# ---------------------------------------------------------------------------


class TestResolveRegisteredPrincipal:
    def test_a_malformed_scheme_is_rejected_before_any_lookup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: call resolve_user_from_bearer_token
        # (or decode_guest_token) even when has_bearer_scheme is False,
        # spending a database lookup on a request that cannot possibly
        # succeed, mirroring F-4.1-A-14's "cheap check before opening a
        # session" precedent.
        calls: list[str] = []
        monkeypatch.setattr(
            context_module,
            "resolve_user_from_bearer_token",
            lambda *a, **k: calls.append("resolve") or (_ for _ in ()).throw(AssertionError),
        )
        monkeypatch.setattr(
            context_module,
            "decode_guest_token",
            lambda *a, **k: calls.append("guest") or (_ for _ in ()).throw(AssertionError),
        )

        with pytest.raises(context_module.GraphQLAuthError) as exc_info:
            context_module._resolve_registered_principal("Token not-bearer", session=object())

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == context_module._INVALID_CREDENTIAL_DETAIL
        assert calls == []

    def test_a_missing_token_is_rejected_the_same_way(self) -> None:
        # Mutation that turns this red: treat None differently from a
        # malformed scheme, producing a distinguishable message a caller
        # could use to learn something about the check order.
        with pytest.raises(context_module.GraphQLAuthError) as exc_info:
            context_module._resolve_registered_principal(None, session=object())

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == context_module._INVALID_CREDENTIAL_DETAIL

    def test_a_valid_registered_token_resolves_the_user(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: return the raw token or None
        # instead of the resolved User, or fall through to the guest check
        # even on a successful registered-user resolution.
        fake_user = _FakeUser()
        guest_calls: list[str] = []
        monkeypatch.setattr(
            context_module, "resolve_user_from_bearer_token", lambda *a, **k: fake_user
        )
        monkeypatch.setattr(
            context_module,
            "decode_guest_token",
            lambda *a, **k: guest_calls.append("called"),
        )

        principal = context_module._resolve_registered_principal(
            "Bearer a-real-token", session=object()
        )

        assert principal is fake_user
        assert guest_calls == []

    def test_an_invalid_token_that_is_not_a_guest_token_gets_the_generic_refusal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: report the guest-specific detail
        # for a token that is not, in fact, a valid guest token, which
        # would let an attacker learn a guest-shaped check was attempted
        # for a credential that never verified as anything.
        def _raise_invalid(*_a: object, **_k: object) -> None:
            raise InvalidBearerTokenError("invalid or expired access token")

        def _raise_not_guest(*_a: object, **_k: object) -> None:
            raise ValueError("guest token is invalid")

        monkeypatch.setattr(context_module, "resolve_user_from_bearer_token", _raise_invalid)
        monkeypatch.setattr(context_module, "decode_guest_token", _raise_not_guest)

        with pytest.raises(context_module.GraphQLAuthError) as exc_info:
            context_module._resolve_registered_principal("Bearer nope", session=object())

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == context_module._INVALID_CREDENTIAL_DETAIL
        assert "guest" not in exc_info.value.detail.lower()

    def test_a_genuine_guest_token_gets_the_actionable_distinct_refusal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: swap this branch for the
        # registered-only `get_caller` path (which would resolve a guest
        # happily instead of refusing), or reuse the generic detail here.
        # tracker/phase_4.3.md scope reading 2 is what this pins.
        def _raise_invalid(*_a: object, **_k: object) -> None:
            raise InvalidBearerTokenError("invalid or expired access token")

        monkeypatch.setattr(context_module, "resolve_user_from_bearer_token", _raise_invalid)
        monkeypatch.setattr(
            context_module, "decode_guest_token", lambda *a, **k: {"guest_id": "g-1"}
        )

        with pytest.raises(context_module.GraphQLAuthError) as exc_info:
            context_module._resolve_registered_principal("Bearer a-guest-token", session=object())

        assert exc_info.value.status_code == 403
        detail = exc_info.value.detail.lower()
        assert "guest" in detail
        assert "account" in detail or "sign in" in detail or "log in" in detail

    def test_the_guest_refusal_is_distinguishable_from_the_generic_refusal(self) -> None:
        # Mutation that turns this red: collapse both module-level detail
        # constants to the same string, which would make a developer
        # holding a guest token debug a credential problem that does not
        # exist (the exact failure the premise gate's own arm names).
        assert context_module._GUEST_REFUSAL_DETAIL != context_module._INVALID_CREDENTIAL_DETAIL


# ---------------------------------------------------------------------------
# GraphQLContext: the carrier every resolver reads.
# ---------------------------------------------------------------------------


class TestGraphQLContext:
    def test_principal_is_set_and_request_starts_unset(self) -> None:
        # Mutation that turns this red: forget to call `super().__init__()`
        # (BaseContext.request/background_tasks/response would never be
        # set, so strawberry.fastapi.GraphQLRouter's own post-construction
        # `custom_context.request = request` assignment would still work,
        # but `background_tasks`/`response` would raise AttributeError the
        # first time a resolver reads them), or forget to assign
        # `self.principal`.
        fake_user = _FakeUser()
        context = context_module.GraphQLContext(principal=fake_user)

        assert context.principal is fake_user
        assert context.request is None
        assert context.background_tasks is None
        assert context.response is None


# ---------------------------------------------------------------------------
# get_context: the actual FastAPI dependency, and the property this whole
# ticket exists for, auth resolves before any GraphQL execution.
# ---------------------------------------------------------------------------


class TestGetContext:
    @pytest.mark.asyncio
    async def test_a_missing_token_raises_before_ever_returning_a_context(self) -> None:
        # Mutation that turns this red: return a GraphQLContext with a
        # placeholder/anonymous principal instead of raising, which is
        # exactly the shape that would let a resolver run (and a run be
        # created via RunRegistry.create_run) for an unauthenticated
        # caller once T-4.3-07 wires this as GraphQLRouter's
        # context_getter. Since context_getter runs as a FastAPI
        # dependency resolved strictly before the route body executes
        # (verified against the installed strawberry-graphql==0.324.0
        # router source, see this module's own docstring), raising here is
        # what makes "auth precedes execution" true for the whole surface.
        with pytest.raises(HTTPException) as exc_info:
            await context_module.get_context(_request_with_auth(None), session=object())

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_a_valid_registered_token_returns_a_context_carrying_the_principal(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: return a context whose principal is
        # not the resolved User (a raw token string, None, or a guest-
        # shaped placeholder).
        fake_user = _FakeUser()
        monkeypatch.setattr(
            context_module, "resolve_user_from_bearer_token", lambda *a, **k: fake_user
        )

        context = await context_module.get_context(
            _request_with_auth("Bearer a-real-token"), session=object()
        )

        assert isinstance(context, context_module.GraphQLContext)
        assert context.principal is fake_user

    @pytest.mark.asyncio
    async def test_a_guest_token_raises_403_with_an_actionable_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: raise a bare 401 with the generic
        # detail for a guest token, losing the distinguishable, actionable
        # refusal the premise gate's TestAuth arms require.
        def _raise_invalid(*_a: object, **_k: object) -> None:
            raise InvalidBearerTokenError("invalid or expired access token")

        monkeypatch.setattr(context_module, "resolve_user_from_bearer_token", _raise_invalid)
        monkeypatch.setattr(
            context_module, "decode_guest_token", lambda *a, **k: {"guest_id": "g-1"}
        )

        with pytest.raises(HTTPException) as exc_info:
            await context_module.get_context(
                _request_with_auth("Bearer a-guest-token"), session=object()
            )

        assert exc_info.value.status_code == 403
        detail = str(exc_info.value.detail).lower()
        assert "guest" in detail
        assert "account" in detail or "sign in" in detail or "log in" in detail

    @pytest.mark.asyncio
    async def test_a_duplicated_authorization_header_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Mutation that turns this red: read only the first header value
        # (or the last) instead of refusing outright, resolving a genuine
        # duplicate first-wins the way F-4.1-A-11 forbade on the MCP
        # surface. Two DIFFERENT real-shaped bearer values are used so a
        # first-wins or last-wins implementation would actually succeed
        # here rather than coincidentally failing for an unrelated reason.
        calls: list[str] = []

        def _spy_resolve(*_a: object, **_k: object) -> object:
            calls.append("resolve")
            return _FakeUser()

        monkeypatch.setattr(context_module, "resolve_user_from_bearer_token", _spy_resolve)

        with pytest.raises(HTTPException) as exc_info:
            await context_module.get_context(
                _request_with_duplicate_auth("Bearer token-one", "Bearer token-two"),
                session=object(),
            )

        assert exc_info.value.status_code == 401
        assert calls == []

    @pytest.mark.asyncio
    async def test_a_malformed_scheme_is_rejected(self) -> None:
        # Mutation that turns this red: accept a non-Bearer scheme (e.g.
        # `Basic`, or a bare token with no scheme at all).
        with pytest.raises(HTTPException) as exc_info:
            await context_module.get_context(
                _request_with_auth("Basic dXNlcjpwYXNz"), session=object()
            )

        assert exc_info.value.status_code == 401
