"""Pydantic request and response schemas for the `/auth` router.

Spec: Technical_specification.md Section 15 (lines 2372-2390), the auth
service and its five-endpoint list.

Every request model sets `extra="forbid"`, so an unknown field in a
request body is a 422, not a silently ignored field (T-1.1-03 acceptance
criterion). Every response model excludes `password_hash`,
`refresh_token_hash`, and any field belonging to a user other than the
caller.

Email handling (F-1.1-08 and F-1.1-13, 2026-07-28). Every request field
that carries an email is the `EmailAddress` annotated type below, which
normalizes (NFKC, strip, lowercase) and then format-checks the value
before it reaches the router. Normalization happens here, at the single
boundary both signup and login pass through, so the two endpoints can
never disagree about which account an address names. The database
enforces the same rule independently with a unique index on
`lower(email)` (alembic revision 0002), so a second code path cannot
reintroduce the gap.

Depends on:
    - Nothing outside pydantic and the standard library. This module
      never imports the ORM models or the database session directly.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

# A deliberately conservative address grammar rather than the full RFC
# 5322 one: one `@`, a dot-separated local part with no empty labels, and
# a domain of at least two labels made only of letters, digits, and
# internal hyphens. Anything carrying whitespace, a control character
# (including the CR/LF of a header-injection payload), a quote, or markup
# fails to match. No dependency was added for this; `EmailStr` would pull
# in `email-validator`, and `supply-chain-security` requires a review gate
# before a new package lands, which a regex at the boundary does not need.
_EMAIL_LOCAL_CHARS = r"A-Za-z0-9!#$%&'*+/=?^_`{|}~-"
_EMAIL_PATTERN = re.compile(
    rf"^[{_EMAIL_LOCAL_CHARS}]+(?:\.[{_EMAIL_LOCAL_CHARS}]+)*"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$"
)
_MAX_EMAIL_LENGTH = 320


def _normalize_and_validate_email(value: str) -> str:
    """Normalize an email to its canonical form, then reject a malformed one.

    Normalization is NFKC (folding fullwidth and other compatibility
    variants onto their plain forms), then a strip of surrounding
    whitespace, then `str.lower()`. Lowercase rather than `str.casefold()`
    on purpose: the database's uniqueness guarantee is a unique index on
    Postgres `lower(email)`, and the application-side normalization has to
    agree with it byte for byte or the two disagree on which addresses
    collide.

    Raises:
        ValueError: If the normalized value is empty, too long, or does
            not match the address grammar. Pydantic turns this into a 422.
    """
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    if not normalized or len(normalized) > _MAX_EMAIL_LENGTH:
        raise ValueError("value is not a valid email address")
    if not _EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("value is not a valid email address")
    return normalized


EmailAddress = Annotated[
    str,
    Field(min_length=1, max_length=_MAX_EMAIL_LENGTH),
    AfterValidator(_normalize_and_validate_email),
]


# T-4.10-06 (design decision 4 and 6, tracker/phase_4.10.md): bounded to a
# realistic HS256 guest-JWT length (guest.py's guest token carries exactly
# four short claims), not left unbounded. Optional and additive within v1
# (production-standards.md / system-design-patterns.md pattern 10): a
# request body that omits it validates exactly as it did before this
# ticket.
_MAX_GUEST_TOKEN_LENGTH = 1024


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailAddress
    password: str = Field(min_length=1, max_length=1024)
    guest_token: str | None = Field(default=None, max_length=_MAX_GUEST_TOKEN_LENGTH)


class SignupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailAddress
    password: str = Field(min_length=1, max_length=1024)
    guest_token: str | None = Field(default=None, max_length=_MAX_GUEST_TOKEN_LENGTH)


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    email: str
    created_at: datetime
    last_login_at: datetime | None
    # T-4.5-10, Section 14.2. Additive within v1, which
    # system-design-patterns pattern 10 permits: a new optional-to-ignore
    # field, never a redefinition. It is here so a signed-in client can show
    # the persona BEFORE its first query, which Section 14.2 requires (the
    # persona is assigned at first login, not at first answer). Without it the
    # chip would be empty on the landing screen until a run returned.
    persona_name: str


class GuestTokenResponse(BaseModel):
    """`POST /auth/guest`'s response (T-4.10-04, design decision 6's wire
    shape): `{guest_token, guest_id, used, total}`."""

    model_config = ConfigDict(extra="forbid")

    guest_token: str
    guest_id: uuid.UUID
    used: int
    total: int
    # T-4.5-10, Section 14.2: "an anonymous prototype session gets a persona
    # drawn and held for that session only, then redrawn on the next
    # anonymous session". The mint IS that session's start, so this is where
    # the draw becomes visible to the client. Keyed on the guest id, so it
    # holds for the life of the guest session and changes with the next one,
    # exactly as the section describes.
    persona_name: str
