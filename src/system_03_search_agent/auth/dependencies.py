"""FastAPI dependencies for the `/auth` router and the guest-aware `Principal`
resolver (T-4.10-03, `tracker/phase_4.10.md`).

Depends on:
    - system_03_search_agent.auth.tokens (decode_access_token)
    - system_03_search_agent.auth.guest (decode_guest_token)
    - system_03_search_agent.data.models (User)
    - system_03_search_agent.data.session (get_session)

Reads:
    - The `Authorization` request header on every protected route.

Writes:
    - Nothing.

Never logs the raw `Authorization` header, the decoded token, or any
token value in an exception string: only literal field names appear in
any message this module produces.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from system_03_search_agent.auth.guest import decode_guest_token
from system_03_search_agent.auth.tokens import decode_access_token
from system_03_search_agent.data.models import User
from system_03_search_agent.data.session import get_session

_INVALID_TOKEN_DETAIL = "invalid or expired access token"

# F-4.1-A-12 (adversary round 1, build phase 4.1): RFC 7235 section 2.1
# makes the auth-scheme token case-insensitive, so `bearer`/`BEARER`/
# `Bearer` must all be accepted equally. The single literal space
# separating scheme from token is unchanged from before this fix; RFC
# 7230's optional-whitespace allowance around the separator (a tab, or
# leading whitespace before the scheme) is a separate, narrower gap the
# same finding named and did not ask to close, carried open rather than
# silently widened here.
_BEARER_SCHEME_LOWER = "bearer "


def has_bearer_scheme(authorization: str | None) -> bool:
    """True if `authorization` starts with the `Bearer` scheme, matched
    case-insensitively (F-4.1-A-12). Exposed as its own function, not
    inlined into `resolve_user_from_bearer_token`, so a caller that only
    needs the cheap, no-database shape check (`adapters/mcp/server.py`'s
    `_authenticate_mcp_caller`, F-4.1-A-14) can run it before opening a
    session, without a second, drifting implementation of the same check.
    """
    return authorization is not None and authorization.lower().startswith(_BEARER_SCHEME_LOWER)


class InvalidBearerTokenError(Exception):
    """Raised by `resolve_user_from_bearer_token` for a missing, malformed,
    or invalid bearer token.

    T-4.1-03 (`tracker/phase_4.1.md`): the MCP adapter needs the exact same
    decode-then-lookup logic `get_current_user` already uses, but cannot
    raise a FastAPI `HTTPException` (it is not running inside a FastAPI
    request/response cycle) and instead needs to raise `mcp.shared.
    exceptions.MCPError`. This exception is the seam: the decode-then-
    lookup logic lives in one place (`resolve_user_from_bearer_token`
    below) and raises this transport-neutral error, and each surface
    translates it into its own failure shape. `get_current_user`'s own
    behavior is unchanged by this split: same checks, same order, same
    `_INVALID_TOKEN_DETAIL` string, same 401.
    """


def resolve_user_from_bearer_token(authorization: str | None, session: Session) -> User:
    """Resolve a `User` row from a raw `Authorization` header value.

    The decode-then-lookup logic `get_current_user` used to inline
    directly, extracted so a non-FastAPI caller (the MCP adapter's tool
    handler) can reuse it without duplicating it. Behavior is byte-for-byte
    what `get_current_user` had before this extraction: same rejection
    order (missing header, malformed scheme, empty token, undecodable
    token, malformed or absent `user_id` claim, unknown user), same single
    detail string on every failure so no failure mode leaks which check
    tripped.

    Raises:
        InvalidBearerTokenError: for any of the failure modes above.
    """
    if not has_bearer_scheme(authorization):
        raise InvalidBearerTokenError(_INVALID_TOKEN_DETAIL)
    assert authorization is not None  # narrowed by has_bearer_scheme above
    token = authorization[len(_BEARER_SCHEME_LOWER) :].strip()
    if not token:
        raise InvalidBearerTokenError(_INVALID_TOKEN_DETAIL)
    try:
        claims = decode_access_token(token)
    except (TypeError, ValueError):
        raise InvalidBearerTokenError(_INVALID_TOKEN_DETAIL) from None

    try:
        user_id = uuid.UUID(claims["user_id"])
    except (KeyError, ValueError, TypeError, AttributeError):
        raise InvalidBearerTokenError(_INVALID_TOKEN_DETAIL) from None

    user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise InvalidBearerTokenError(_INVALID_TOKEN_DETAIL)
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> User:
    """Resolve the caller's `User` row from a `Bearer` access token.

    Returns 401 for a missing header, a malformed header (no `Bearer`
    scheme), an expired token, a tampered or wrongly signed token, or a
    token whose subject no longer maps to a `users` row. A misconfigured
    server (AUTH_SECRET unset) is not an auth failure and is left to
    propagate as a 500 via tokens.py's RuntimeError.
    """
    try:
        return resolve_user_from_bearer_token(authorization, session)
    except InvalidBearerTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN_DETAIL) from None


# ---------------------------------------------------------------------------
# T-4.10-03: the guest-aware Principal resolver. get_current_user above is
# UNCHANGED (design decision, "the four things most likely to go wrong" #1
# in this ticket's brief): a guest token presented to a get_current_user
# route gets the exact same 401 it always did, since decode_access_token
# rejects a guest token on signature verification alone (the two token
# families are signed with cryptographically distinct keys, guest.py's own
# module docstring). get_caller below is additive, used only by routes that
# must admit both principal classes.
# ---------------------------------------------------------------------------

_INVALID_CALLER_DETAIL = "invalid or expired credentials"


@dataclass(frozen=True)
class Principal:
    """The authenticated caller behind a request: a registered user or a guest.

    T-4.10-03, design decision 2 (`tracker/phase_4.10.md`): `owner_id` is
    the ONLY field an ownership comparison may read (`adapters/web_sse/
    app.py`'s `_get_owned_run`), namespaced `user:<uuid>` or `guest:<uuid>`
    so the two principal classes can never collide on a bare UUID.
    `user_id` is the bare registered-user UUID string, or `None` for a
    guest: it is what `harness.cost_control.is_operator_user()` reads and
    what `contracts.query.Query.user_id` and a future `interactions.
    user_id` write need. `user_id` must NEVER receive a namespaced string;
    that is the exact defect this two-field split exists to prevent, and
    `is_operator_user(None)` is already required to return False (a guest
    can never be an operator).
    """

    owner_id: str
    user_id: str | None
    kind: Literal["user", "guest"]


class InvalidCallerError(Exception):
    """Raised by `resolve_caller_from_bearer_token` for any failure mode.

    One exception, one message, matching `InvalidBearerTokenError`'s own
    discipline above: a missing header, a malformed scheme, an empty
    token, an undecodable access token, and an undecodable guest token all
    raise this same exception with the same detail, so the 401 a caller
    receives never discloses which check tripped or which token family
    was even attempted.
    """


def resolve_caller_from_bearer_token(authorization: str | None, session: Session) -> Principal:
    """Resolve a `Principal` (a registered user OR a guest) from a raw
    `Authorization` header value.

    Tries the access-token path first (reusing `resolve_user_from_bearer_
    token` verbatim, so a registered caller's rejection behavior is
    byte-for-byte unchanged), then falls back to the guest-token path.
    This is not a guess between two shapes: the two token families are
    signed with cryptographically domain-separated keys (`auth/guest.py`'s
    module docstring), so `decode_access_token` fails on signature
    verification alone for a genuine guest token, before it ever reaches a
    database lookup, and the reverse holds for `decode_guest_token`
    against a genuine access token. Trying one and falling back to the
    other is therefore a deterministic dispatch on which of two disjoint
    keys actually verifies, not an ambiguous heuristic.

    Raises:
        InvalidCallerError: if neither a valid access token nor a valid
            guest token was presented.
    """
    if not has_bearer_scheme(authorization):
        raise InvalidCallerError(_INVALID_CALLER_DETAIL)
    assert authorization is not None  # narrowed by has_bearer_scheme above
    token = authorization[len(_BEARER_SCHEME_LOWER) :].strip()
    if not token:
        raise InvalidCallerError(_INVALID_CALLER_DETAIL)

    try:
        user = resolve_user_from_bearer_token(authorization, session)
    except InvalidBearerTokenError:
        user = None
    if user is not None:
        return Principal(owner_id=f"user:{user.id}", user_id=str(user.id), kind="user")

    try:
        claims = decode_guest_token(token)
    except (TypeError, ValueError):
        raise InvalidCallerError(_INVALID_CALLER_DETAIL) from None
    return Principal(owner_id=f"guest:{claims['guest_id']}", user_id=None, kind="guest")


def get_caller(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI dependency injection
) -> Principal:
    """FastAPI dependency: resolve the calling `Principal`, user or guest.

    Returns 401 for every failure mode `get_current_user` already returns
    401 for, PLUS an invalid, expired, tampered, or wrong-key guest token.
    A caller presenting neither a valid access token nor a valid guest
    token gets the exact same status and detail string regardless of which
    token family it attempted, matching `get_current_user`'s own
    single-detail-string discipline.
    """
    try:
        return resolve_caller_from_bearer_token(authorization, session)
    except InvalidCallerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CALLER_DETAIL
        ) from None
