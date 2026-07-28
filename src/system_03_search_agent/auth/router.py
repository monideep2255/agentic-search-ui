"""The `/auth` FastAPI router: signup, login, refresh, logout, me.

Spec: Technical_specification.md Section 15 (lines 2372-2390), the auth
service and its five-endpoint list. PII handling per Section 11.3 (lines
1935-1941): account PII (email) lives only in the `users` table and is
never forwarded to an LLM from this module.

Security properties this module is responsible for (T-1.1-03 acceptance
criteria):

- Login does not disclose which emails are registered: an unknown email
  and a known email with a wrong password return the same status and the
  same response body, and both branches run a real argon2 verify so the
  two paths take comparable time.
- Refresh rotates: the presented refresh token is revoked in the same
  database transaction that issues the replacement, so replaying it
  returns 401.
- Only the SHA-256 hash of a refresh token is ever persisted
  (`auth_sessions.refresh_token_hash`); the raw token exists only in the
  response body handed back to the caller.
- `auth_sessions.ip_hash` stores a keyed (HMAC-SHA256) hash of the client
  IP, never the raw address, in any column or log line. The key is
  `AUTH_SECRET`, the same secret already provisioned for token signing;
  see the module-level `_hash_ip` docstring for why reusing it is safe
  here and why no new environment variable was added.
- No response body ever includes `password_hash` or `refresh_token_hash`;
  every response model in `schemas.py` omits both fields entirely.

Depends on:
    - system_03_search_agent.auth.passwords (hash_password, verify_password)
    - system_03_search_agent.auth.tokens (mint/decode/generate/hash/verify)
    - system_03_search_agent.auth.dependencies (get_current_user)
    - system_03_search_agent.auth.schemas (every request/response model)
    - system_03_search_agent.data.models (User, AuthSession)
    - system_03_search_agent.data.session (get_session)

Writes:
    - `users` rows (signup, `last_login_at` on login).
    - `auth_sessions` rows (login creates one, refresh revokes the old
      and creates a new one, logout revokes one).

Never logs and never raises with a password, a token, or a connection
string embedded in a log record or exception string.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from system_03_search_agent.auth.dependencies import get_current_user
from system_03_search_agent.auth.passwords import hash_password, verify_password
from system_03_search_agent.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    MeResponse,
    RefreshRequest,
    SignupRequest,
    SignupResponse,
    TokenResponse,
)
from system_03_search_agent.auth.tokens import (
    generate_refresh_token,
    hash_refresh_token,
    mint_access_token,
)
from system_03_search_agent.data.models import AuthSession, User
from system_03_search_agent.data.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])

_INVALID_CREDENTIALS_DETAIL = "invalid email or password"
_INVALID_REFRESH_DETAIL = "invalid or expired refresh token"
_EMAIL_TAKEN_DETAIL = "email already registered"

# A refresh token's lifetime. Not a number the technical specification
# pins explicitly (Section 15 declares the `expires_at` column but not a
# TTL value); 30 days matches the common self-hosted-auth default and is
# a build-time value to confirm later, the same status the PII retention
# window carries in Section 11.3.
_REFRESH_TOKEN_TTL = timedelta(days=30)

# A fixed, validly-hashed placeholder used as the comparison target for
# `verify_password` when no user row exists. This makes the "unknown
# email" branch of login perform the same argon2id verification work as
# the "known email, wrong password" branch, so the two branches take
# comparable time and neither timing nor the response body discloses
# which emails are registered. Never a real user's hash.
_DUMMY_PASSWORD_HASH = hash_password("no-such-account-timing-parity-placeholder")


def _hash_ip(raw_ip: str | None) -> str | None:
    """Return a keyed HMAC-SHA256 hash of a client IP, or None if unknown.

    Keyed with AUTH_SECRET rather than a dedicated new secret: AUTH_SECRET
    is already the one long-lived secret this service provisions, and
    HMAC's security does not depend on using a distinct key per purpose,
    only on a distinct message per purpose. The message here
    (`b"ip_hash:" + raw_ip`) is disjoint from the JWT payload HS256 signs,
    so the two uses do not collide. No new environment variable was added
    since none of the files this ticket may touch include env.example.
    """
    if not raw_ip:
        return None
    secret = os.environ.get("AUTH_SECRET")
    if not secret:
        return None
    return hmac.new(secret.encode("utf-8"), b"ip_hash:" + raw_ip.encode("utf-8"), hashlib.sha256).hexdigest()


def _issue_session(
    session: Session, user: User, request: Request
) -> tuple[str, str]:
    """Mint an access token and a fresh `auth_sessions` row, return both tokens."""
    raw_refresh_token = generate_refresh_token()
    now = datetime.now(UTC)
    client_host = request.client.host if request.client else None
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(raw_refresh_token),
        expires_at=now + _REFRESH_TOKEN_TTL,
        user_agent=request.headers.get("user-agent"),
        ip_hash=_hash_ip(client_host),
    )
    session.add(auth_session)
    access_token = mint_access_token(str(user.id))
    return access_token, raw_refresh_token


def _revoke_active_auth_session(session: Session, raw_refresh_token: str) -> AuthSession | None:
    """Atomically revoke a non-revoked, non-expired `auth_sessions` row.

    A single `UPDATE ... WHERE revoked_at IS NULL AND expires_at > now`
    statement, not a SELECT followed by a separate UPDATE. Under READ
    COMMITTED (Postgres's default), two concurrent replays of the same
    refresh token could both pass a SELECT-based check before either
    commits; only one UPDATE can match and flip `revoked_at`, so at most
    one replay ever succeeds. Returns None if no row matched (unknown,
    already-revoked, or expired token), otherwise the now-revoked row.
    """
    token_hash = hash_refresh_token(raw_refresh_token)
    now = datetime.now(UTC)
    result = session.execute(
        update(AuthSession)
        .where(
            AuthSession.refresh_token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .values(revoked_at=now)
    )
    if result.rowcount != 1:
        return None
    return session.execute(
        select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
    ).scalar_one()


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI DI
) -> SignupResponse:
    existing = session.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_TAKEN_DETAIL)

    user = User(email=body.email, password_hash=hash_password(body.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # A concurrent signup for the same email committed between the
        # existence check above and this commit. The unique constraint on
        # users.email is the real guard; the pre-check above is only a
        # fast path for the common case.
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_EMAIL_TAKEN_DETAIL) from None
    session.refresh(user)
    return SignupResponse(id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI DI
) -> TokenResponse:
    user = session.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    candidate_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, candidate_hash)

    if user is None or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_DETAIL)

    access_token, raw_refresh_token = _issue_session(session, user, request)
    user.last_login_at = datetime.now(UTC)
    session.commit()
    return TokenResponse(access_token=access_token, refresh_token=raw_refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    request: Request,
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI DI
) -> TokenResponse:
    # Rotate: the atomic UPDATE above revokes the presented token, and its
    # replacement is minted in the same transaction, so a concurrent or
    # later replay of the old token can never also succeed.
    auth_session = _revoke_active_auth_session(session, body.refresh_token)
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_REFRESH_DETAIL)

    user = session.execute(select(User).where(User.id == auth_session.user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_REFRESH_DETAIL)

    access_token, raw_refresh_token = _issue_session(session, user, request)
    session.commit()
    return TokenResponse(access_token=access_token, refresh_token=raw_refresh_token)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    body: LogoutRequest,
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI DI
) -> LogoutResponse:
    auth_session = _revoke_active_auth_session(session, body.refresh_token)
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_REFRESH_DETAIL)

    session.commit()
    return LogoutResponse(status="ok")


@router.get("/me", response_model=MeResponse)
def me(
    current_user: User = Depends(get_current_user),  # noqa: B008 - idiomatic FastAPI DI
) -> MeResponse:
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )
