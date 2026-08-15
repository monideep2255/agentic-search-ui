"""Guest token primitives for the anonymous run path (T-4.10-01).

Design decision 1, tracker/phase_4.10.md: a guest identity is a signed
token, minted on first visit, clearable by anyone who clears their
browser storage (product-owner decision, 2026-08-14, accepted with a
prototype mindset). Its signing key is NOT `AUTH_SECRET` directly. It is
`HMAC-SHA256(AUTH_SECRET, b"guest-token-v1")`, so a guest token and an
access token (`system_03_search_agent.auth.tokens`) are unforgeable as
each other even if the claim checks below were ever weakened. This is
cryptographic domain separation, not merely a naming convention: sharing
one key across two principal classes is a single edit away from a
token-confusion vulnerability, the highest-severity defect available in
this phase.

Two token shapes exist side by side, matching `tokens.py`'s own contract:

- Guest token: an HS256 JWT, signed with the derived key above, carrying
  `guest_id`, `typ: "guest"`, `iat`, and `exp`. TTL 7 days, not the access
  token's 15 minutes: a guest has no refresh path, and a 15-minute guest
  identity would silently hand a visitor a fresh allowance every 15
  minutes, defeating the count `data.guest_sessions.spend_one_run` tracks.

No HTTP, no database access. Never logs and never raises with the raw
token, the decoded payload, `AUTH_SECRET`, or the derived signing key
embedded in a log record or exception string. Field names appear as
string literals only, matching `tokens.py`'s discipline.

Depends on:
    - PyJWT (PyPI package providing the `jwt` module)
    - Environment variable: AUTH_SECRET (read at call time, never cached
      at import time, so a test can change it between calls, and so this
      module never introduces a second required env var)

Reads:
    - Environment variable: AUTH_SECRET.

Writes:
    - Nothing.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

_GUEST_TOKEN_ALGORITHM = "HS256"
_GUEST_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60

# The HMAC domain-separation tag. Changing this string mints a family of
# guest tokens that no previously issued guest token, and no access token
# minted by tokens.py, can ever be mistaken for.
_GUEST_KEY_DOMAIN = b"guest-token-v1"

# Tolerance for clock skew between the minting host and the verifying host
# when checking that a token's `exp` is not further out than the 7-day
# policy allows, matching tokens.py's own _MAX_EXP_SKEW_SECONDS in both
# name and value.
_MAX_EXP_SKEW_SECONDS = 60


def _get_auth_secret() -> str:
    """Read AUTH_SECRET from the environment at call time.

    Deliberately duplicated from tokens.py rather than imported: each
    token module owns its own read of AUTH_SECRET, matching tokens.py's
    own env discipline, rather than importing a private, underscore-
    prefixed symbol across a module boundary.

    Raises:
        RuntimeError: If AUTH_SECRET is unset or empty. Never falls back
            to a default, empty, or hardcoded secret.
    """
    secret = os.environ.get("AUTH_SECRET")
    if not secret:
        raise RuntimeError(
            "AUTH_SECRET environment variable is not set; refusing to "
            "mint or verify a guest token without an explicit secret"
        )
    return secret


def guest_signing_key() -> bytes:
    """Return the derived guest-token signing key.

    `HMAC-SHA256(AUTH_SECRET, b"guest-token-v1")`, derived fresh from the
    environment on every call, never cached at import or module load time,
    so a test can change AUTH_SECRET between calls exactly as it can for
    tokens.py's access-token secret.

    This is the load-bearing domain separation from design decision 1: an
    access token is signed with `AUTH_SECRET` directly, a guest token is
    signed with this derived key, so the two are unforgeable as each other
    at the cryptographic layer, independent of any claim check.

    Raises:
        RuntimeError: If AUTH_SECRET is unset.
    """
    secret = _get_auth_secret()
    return hmac.new(secret.encode("utf-8"), _GUEST_KEY_DOMAIN, hashlib.sha256).digest()


def mint_guest_token(guest_id: str) -> str:
    """Mint a 7-day HS256 guest token for `guest_id`.

    Args:
        guest_id: The guest session id to embed in the token. Expected to
            be a `guest_sessions.id` UUID rendered as a string, but this
            function does not itself validate UUID shape.

    Returns:
        An encoded JWT carrying `guest_id`, `typ: "guest"`, `iat`, and
        `exp` only, signed with `guest_signing_key()`.

    Raises:
        TypeError: If guest_id is not a string.
        ValueError: If guest_id is an empty string.
        RuntimeError: If AUTH_SECRET is unset.
    """
    if not isinstance(guest_id, str):
        raise TypeError("guest_id must be a string")
    if not guest_id:
        raise ValueError("guest_id must not be empty")
    key = guest_signing_key()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "guest_id": guest_id,
        "typ": "guest",
        "iat": now,
        "exp": now + timedelta(seconds=_GUEST_TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, key, algorithm=_GUEST_TOKEN_ALGORITHM)


def decode_guest_token(token: str) -> dict[str, str]:
    """Decode and verify an HS256 guest token.

    The algorithm is pinned explicitly to HS256 on every call, so a token
    presented with `alg: none` or signed with any other algorithm is
    rejected regardless of its claimed header, matching
    `decode_access_token`'s contract.

    The verifier enforces the token contract independently of the minter,
    the same discipline F-1.1-09 established for access tokens: `exp`,
    `typ`, and `guest_id` are required rather than merely validated when
    present, `typ` must equal the literal string `"guest"` (a token
    missing or misdeclaring `typ` is rejected), `exp` must be a real
    number rather than a string PyJWT would coerce, and an `exp` further
    out than the 7-day policy allows is rejected.

    Args:
        token: The encoded JWT to verify.

    Returns:
        A dict with the single key `guest_id`.

    Raises:
        TypeError: If token is not a string.
        ValueError: If token is empty, expired, tampered, signed with the
            wrong key (including a token signed with bare `AUTH_SECRET`
            rather than the derived guest key, e.g. a forged access token
            presented here), signed with any algorithm other than HS256,
            missing `exp`, `typ`, or `guest_id`, declaring a `typ` other
            than `"guest"` (an access token has no `typ` claim at all and
            is rejected by the `require` check below before this is even
            reached), or carrying an `exp` that is not a number or that
            exceeds the 7-day guest-token policy.
        RuntimeError: If AUTH_SECRET is unset.
    """
    if not isinstance(token, str):
        raise TypeError("token must be a string")
    if not token:
        raise ValueError("token must not be empty")
    key = guest_signing_key()
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=[_GUEST_TOKEN_ALGORITHM],
            options={"require": ["exp", "typ", "guest_id"], "verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("guest token has expired") from None
    except jwt.PyJWTError:
        raise ValueError("guest token is invalid") from None

    if payload.get("typ") != "guest":
        raise ValueError("guest token is invalid")

    expires_at = payload.get("exp")
    # bool is a subclass of int, and PyJWT coerces a numeric string, so
    # both are excluded explicitly rather than left to duck typing.
    if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
        # The TRY004 suppression below is deliberate. A wrongly typed claim
        # inside an attacker-supplied token is an invalid token, not a
        # caller type error: this function reserves TypeError for `token`
        # itself being the wrong type, per the contract documented above.
        raise ValueError("guest token is invalid")  # noqa: TRY004
    ceiling = datetime.now(UTC).timestamp() + _GUEST_TOKEN_TTL_SECONDS + _MAX_EXP_SKEW_SECONDS
    if expires_at > ceiling:
        raise ValueError("guest token is invalid")

    guest_id = payload.get("guest_id")
    if not isinstance(guest_id, str) or not guest_id:
        raise ValueError("guest token is invalid")

    return {"guest_id": guest_id}
