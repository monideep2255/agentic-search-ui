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
- Refresh reuse is acted on, not merely observed (F-1.1-07): presenting
  an already-revoked refresh token revokes every `auth_sessions` row for
  that user, so a stolen token buys one rotation and then forces both
  holders back to `/auth/login`. This is what makes Section 15's "bounds
  the damage of a stolen refresh token to one use" true rather than
  merely intended.
- A rotation chain has an absolute ceiling (F-1.1-07): `expires_at`
  renews on every rotation, `absolute_expires_at` does not, so a
  continuously rotating holder still expires.
- Every response carrying a token sets `Cache-Control: no-store` and
  `Pragma: no-cache` (F-1.1-14), so no intermediary, browser disk cache,
  or debugging proxy persists an access or refresh token.
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
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from system_03_search_agent.auth.dependencies import get_current_user
from system_03_search_agent.auth.guest import decode_guest_token, mint_guest_token
from system_03_search_agent.auth.passwords import hash_password, verify_password
from system_03_search_agent.auth.schemas import (
    GuestTokenResponse,
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
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.data.guest_sessions import FREE_RUN_ALLOWANCE, create_guest_session
from system_03_search_agent.data.models import AuthSession, GuestSession, User
from system_03_search_agent.data.session import get_session

logger = logging.getLogger(__name__)

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

# The ceiling a rotation chain may never outlive, measured from the login
# that started it and carried forward unchanged through every rotation
# (F-1.1-07). `_REFRESH_TOKEN_TTL` above bounds an idle token only: every
# rotation writes a fresh 30-day `expires_at`, so without this a holder
# who keeps rotating never expires at all.
#
# 90 days, chosen as three idle windows. The reasoning, since Section 15
# pins no value: the cap has to be a comfortable multiple of the idle TTL
# or it becomes the effective session length and forces a re-login on an
# active user, and it has to be short enough that a compromise which
# somehow escapes reuse detection still ends on its own. Three idle
# windows satisfies both, and it sits inside the PII retention window
# Section 11.3 already discusses. A build-time value to confirm with the
# product owner, the same status `_REFRESH_TOKEN_TTL` carries.
_REFRESH_TOKEN_ABSOLUTE_TTL = timedelta(days=90)

# The longest `User-Agent` string persisted on an `auth_sessions` row
# (F-1.1-16). The header is attacker-chosen and unbounded on the wire;
# 100,000 characters were written from a single login before this cap.
# 512 comfortably holds every real browser and client UA string.
_MAX_USER_AGENT_LENGTH = 512

# Applied to every response that carries an access or refresh token
# (F-1.1-14), so a token never lands in a browser disk cache, an
# intermediary, or a debugging proxy.
_NO_STORE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}

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


def _truncate_user_agent(raw_user_agent: str | None) -> str | None:
    """Bound the attacker-chosen `User-Agent` header before persisting it (F-1.1-16)."""
    if raw_user_agent is None:
        return None
    return raw_user_agent[:_MAX_USER_AGENT_LENGTH]


def _issue_session(
    session: Session,
    user: User,
    request: Request,
    absolute_expires_at: datetime | None = None,
) -> tuple[str, str]:
    """Mint an access token and a fresh `auth_sessions` row, return both tokens.

    Args:
        session: The open database session; this function adds a row to it
            and never commits.
        user: The account the new session belongs to.
        request: The inbound request, read only for its client IP and
            `User-Agent` header.
        absolute_expires_at: The rotation chain's ceiling, carried forward
            from the row being rotated. None on a fresh login, which
            starts a new chain and so sets a new ceiling.
    """
    raw_refresh_token = generate_refresh_token()
    now = datetime.now(UTC)
    client_host = request.client.host if request.client else None
    auth_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(raw_refresh_token),
        expires_at=now + _REFRESH_TOKEN_TTL,
        absolute_expires_at=absolute_expires_at or (now + _REFRESH_TOKEN_ABSOLUTE_TTL),
        user_agent=_truncate_user_agent(request.headers.get("user-agent")),
        ip_hash=_hash_ip(client_host),
    )
    session.add(auth_session)
    access_token = mint_access_token(str(user.id))
    return access_token, raw_refresh_token


def _revoke_active_auth_session(session: Session, raw_refresh_token: str) -> AuthSession | None:
    """Atomically revoke a non-revoked, unexpired, uncapped `auth_sessions` row.

    A single `UPDATE ... WHERE revoked_at IS NULL AND expires_at > now`
    statement, not a SELECT followed by a separate UPDATE. Under READ
    COMMITTED (Postgres's default), two concurrent replays of the same
    refresh token could both pass a SELECT-based check before either
    commits; only one UPDATE can match and flip `revoked_at`, so at most
    one replay ever succeeds. Returns None if no row matched (unknown,
    already-revoked, expired, or past its chain's absolute ceiling),
    otherwise the now-revoked row.

    The `absolute_expires_at` predicate is the F-1.1-07 ceiling: a row
    written before revision 0002 carries NULL there and is treated as
    capped at `created_at + _REFRESH_TOKEN_ABSOLUTE_TTL` instead, so the
    ceiling applies to pre-existing rows too rather than exempting them.
    """
    token_hash = hash_refresh_token(raw_refresh_token)
    now = datetime.now(UTC)
    result = session.execute(
        update(AuthSession)
        .where(
            AuthSession.refresh_token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
            or_(
                and_(
                    AuthSession.absolute_expires_at.is_(None),
                    AuthSession.created_at + _REFRESH_TOKEN_ABSOLUTE_TTL > now,
                ),
                AuthSession.absolute_expires_at > now,
            ),
        )
        .values(revoked_at=now)
    )
    if result.rowcount != 1:
        return None
    # scalar_one_or_none, not scalar_one (F-1.1-12): the unique index added
    # in revision 0002 is what makes a second row with this hash
    # impossible, and this call must not raise if that invariant is ever
    # violated by a restore or a future writer. A miss here is treated as
    # an invalid token, never as a 500.
    return session.execute(
        select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
    ).scalar_one_or_none()


def _revoke_family_on_reuse(session: Session, raw_refresh_token: str) -> bool:
    """Detect a replayed (already-revoked) refresh token and revoke its family.

    Called only after `_revoke_active_auth_session` found no active row.
    A revoked row matching the presented hash is the canonical stolen-token
    signal, since only one of two holders can have rotated it, so RFC 6819
    Section 5.2.2.3's response applies: revoke every live `auth_sessions`
    row for that user and force both holders back to `/auth/login`.

    The caller still returns the same 401 it would have returned anyway.
    Nothing in the response says a reuse was detected, so an attacker
    learns nothing from the status or the body.

    Returns:
        True if a reuse was detected and the user's sessions were revoked.
    """
    token_hash = hash_refresh_token(raw_refresh_token)
    # No `revoked_at IS NULL` predicate here, which is the whole point: the
    # already-revoked row is the evidence.
    replayed = session.execute(
        select(AuthSession).where(
            AuthSession.refresh_token_hash == token_hash,
            AuthSession.revoked_at.is_not(None),
        )
    ).first()
    if replayed is None:
        return False

    session.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == replayed[0].user_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    session.commit()
    return True


def _migrate_guest_session(session: Session, guest_token: str | None, user: User) -> None:
    """Best-effort: re-point a guest's LIVE runs to `user` and revoke the
    guest session (T-4.10-06, design decision 4, `tracker/phase_4.10.md`).

    NEVER raises. An absent, invalid, expired, malformed, or
    already-migrated guest token is not an authentication failure
    (signup/login's acceptance criterion: "authentication is the primary
    operation; migration is best-effort and its failure is logged, never
    fatal"), so every expected and unexpected failure mode here is caught
    and logged, field names only, never the token value or its decoded
    payload.

    Idempotent (replaying the same signup/login with the same guest token
    gives the same end state): the `revoked_at IS NULL` predicate below
    means a second call with an already-migrated token matches zero rows
    and returns as a clean no-op, never a duplicate reassignment.

    Cross-guest isolation: `old_owner_id` is built ONLY from the
    `guest_id` claim this exact token decodes to, so a guest token can
    never migrate any runs but its own, regardless of which user account
    presents it.
    """
    if not guest_token:
        return
    try:
        claims = decode_guest_token(guest_token)
        guest_uuid = uuid.UUID(claims["guest_id"])
    except (TypeError, ValueError):
        logger.info("guest token migration skipped: token is invalid, expired, or malformed")
        return

    try:
        # One UPDATE sets revoked_at and migrated_to_user_id together, the
        # same "no read-then-write" discipline data.guest_sessions.
        # spend_one_run already uses: the guest session is never
        # observably revoked-but-unmigrated or migrated-but-still-
        # spendable. `revoked_at IS NULL` in the WHERE clause is what
        # makes a replay idempotent, per this function's own docstring.
        result = session.execute(
            update(GuestSession)
            .where(GuestSession.id == guest_uuid, GuestSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), migrated_to_user_id=user.id)
        )
        session.commit()
    except Exception:  # noqa: BLE001 - migration must never fail signup/login, any error included
        # No exc_info here, deliberately: a DB exception's own string
        # representation can embed the failed statement's bound
        # parameters, and this codebase's discipline (production-
        # standards.md's secrets gate) is to log field names and static
        # messages only, never a value that could carry anything
        # token-derived, even indirectly through an exception repr.
        session.rollback()
        logger.warning("guest token migration failed while updating guest_sessions")
        return

    if result.rowcount != 1:
        # Already migrated/revoked (a replay), or the id never existed:
        # not fatal, matching this function's best-effort contract.
        return

    reassigned = run_registry_module.default_registry.reassign_owner(
        old_owner_id=f"guest:{claims['guest_id']}",
        new_owner_id=f"user:{user.id}",
        new_user_id=str(user.id),
    )
    logger.info("guest session migrated to a new user; %d live run(s) reassigned", reassigned)


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
    # T-4.10-06: best-effort, never fatal (see _migrate_guest_session's own
    # docstring). Runs after the user row is already committed, so a
    # migration-side failure can never roll back a successful signup.
    _migrate_guest_session(session, body.guest_token, user)
    return SignupResponse(id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI DI
) -> TokenResponse:
    # body.email arrives already normalized (NFKC, stripped, lowercased) by
    # the EmailAddress type in schemas.py, and every stored email is
    # normalized the same way, so this equality is the case-insensitive
    # match F-1.1-08 asked for rather than a byte-exact one.
    user = session.execute(select(User).where(User.email == body.email)).scalar_one_or_none()
    candidate_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_ok = verify_password(body.password, candidate_hash)

    if user is None or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDENTIALS_DETAIL)

    access_token, raw_refresh_token = _issue_session(session, user, request)
    user.last_login_at = datetime.now(UTC)
    session.commit()
    # T-4.10-06: best-effort, never fatal, after the login itself has
    # already succeeded and committed.
    _migrate_guest_session(session, body.guest_token, user)
    response.headers.update(_NO_STORE_HEADERS)
    return TokenResponse(access_token=access_token, refresh_token=raw_refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI DI
) -> TokenResponse:
    # Rotate: the atomic UPDATE above revokes the presented token, and its
    # replacement is minted in the same transaction, so a concurrent or
    # later replay of the old token can never also succeed.
    auth_session = _revoke_active_auth_session(session, body.refresh_token)
    if auth_session is None:
        # No active row matched. If the reason is that this exact token was
        # already rotated, that is a reuse event, not an ordinary expiry:
        # revoke the whole family before answering (F-1.1-07). The 401 the
        # caller sees is identical either way.
        _revoke_family_on_reuse(session, body.refresh_token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_REFRESH_DETAIL)

    user = session.execute(select(User).where(User.id == auth_session.user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_REFRESH_DETAIL)

    # The chain's ceiling is carried forward unchanged, never renewed, so a
    # continuously rotating holder still expires (F-1.1-07). A row written
    # before revision 0002 carries NULL, in which case the ceiling is
    # anchored to that row's own creation time.
    absolute_expires_at = auth_session.absolute_expires_at or (
        auth_session.created_at + _REFRESH_TOKEN_ABSOLUTE_TTL
    )
    access_token, raw_refresh_token = _issue_session(
        session, user, request, absolute_expires_at=absolute_expires_at
    )
    session.commit()
    response.headers.update(_NO_STORE_HEADERS)
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


# T-4.10-04 (design decision 1 and 6, tracker/phase_4.10.md): mints a
# fresh guest identity. Never requires a body and never requires
# credentials, by design: this is the FIRST call an anonymous visitor's
# browser makes.
#
# Rate-limit consideration (acceptance criterion): minting a guest token
# is an unauthenticated write, so it is named here rather than silently
# left unconsidered. It carries no per-IP or per-caller throttle of its
# own in this phase: the full token-bucket-plus-bounded-queue mechanism
# `.claude/rules/tool-call-budgets.md` describes is build phase 6.0's job
# (this phase's own "what is deliberately not in this phase" section),
# and there is no deployed public URL yet to make an abuse path reachable
# by anyone but the product owner. What bounds the cost of an unthrottled
# mint today: the operation is a single small INSERT (data.guest_sessions.
# create_guest_session), no model call and no external API, and the
# clearable-token accepted tradeoff (TestAcceptedBehaviour in the premise
# gate) already means a determined caller can always get a fresh
# allowance anyway, so a missing throttle here does not open a materially
# worse abuse path than the one already accepted by design. Documented as
# a known, deliberate gap rather than an oversight; build phase 6.0 owns
# closing it for real.
@router.post("/guest", response_model=GuestTokenResponse, status_code=status.HTTP_201_CREATED)
def create_guest(
    session: Session = Depends(get_session),  # noqa: B008 - idiomatic FastAPI DI
) -> GuestTokenResponse:
    guest = create_guest_session(session)
    token = mint_guest_token(str(guest.id))
    return GuestTokenResponse(
        guest_token=token, guest_id=guest.id, used=guest.runs_used, total=FREE_RUN_ALLOWANCE
    )
