"""FastAPI dependencies for the `/auth` router.

Depends on:
    - system_03_search_agent.auth.tokens (decode_access_token)
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

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from system_03_search_agent.auth.tokens import decode_access_token
from system_03_search_agent.data.models import User
from system_03_search_agent.data.session import get_session

_INVALID_TOKEN_DETAIL = "invalid or expired access token"


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
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidBearerTokenError(_INVALID_TOKEN_DETAIL)
    token = authorization.removeprefix("Bearer ").strip()
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
