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
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN_DETAIL)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN_DETAIL)
    try:
        claims = decode_access_token(token)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN_DETAIL) from None

    try:
        user_id = uuid.UUID(claims["user_id"])
    except (KeyError, ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN_DETAIL) from None

    user = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_TOKEN_DETAIL)
    return user
