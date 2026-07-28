"""Token primitives for the auth service.

Two token shapes, per Technical_specification.md Section 15 (lines
2384-2388):

- Access token: a short-lived JWT (15 minutes), signed HS256 with the
  `AUTH_SECRET` env var. Carries `user_id` and standard registered claims
  (`iat`, `exp`) and nothing else. Verification pins the algorithm to
  HS256 explicitly, so a token presented with `alg: none` or any other
  algorithm is rejected regardless of its signature.
- Refresh token: an opaque random string (never a JWT), at least 32 bytes
  of entropy. Only its SHA-256 hash is ever returned for storage; the
  raw token itself is never persisted.

No HTTP, no database access. Never logs and never raises with the raw
token, the decoded payload, or `AUTH_SECRET` embedded in a log record or
exception string.

Depends on:
    - PyJWT (PyPI package providing the `jwt` module)
    - Environment variable: AUTH_SECRET (read at call time, never cached
      at import time, so a test can change it between calls)
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

_ACCESS_TOKEN_ALGORITHM = "HS256"
_ACCESS_TOKEN_TTL_SECONDS = 15 * 60
_REFRESH_TOKEN_ENTROPY_BYTES = 32

# Tolerance for clock skew between the minting host and the verifying host
# when checking that a token's `exp` is not further out than the 15-minute
# policy allows (F-1.1-09). Small enough that it cannot be used to stretch
# a token's life meaningfully, large enough that ordinary NTP drift does
# not reject a legitimately minted token.
_MAX_EXP_SKEW_SECONDS = 60


def _get_auth_secret() -> str:
    """Read AUTH_SECRET from the environment at call time.

    Raises:
        RuntimeError: If AUTH_SECRET is unset or empty. Never falls back
            to a default, empty, or hardcoded secret.
    """
    secret = os.environ.get("AUTH_SECRET")
    if not secret:
        raise RuntimeError(
            "AUTH_SECRET environment variable is not set; refusing to "
            "mint or verify a token without an explicit secret"
        )
    return secret


def mint_access_token(user_id: str) -> str:
    """Mint a 15-minute HS256 access token for a user.

    Args:
        user_id: The subject user id to embed in the token.

    Returns:
        An encoded JWT carrying `user_id`, `iat`, and `exp` only.

    Raises:
        TypeError: If user_id is not a string.
        ValueError: If user_id is an empty string.
        RuntimeError: If AUTH_SECRET is unset.
    """
    if not isinstance(user_id, str):
        raise TypeError("user_id must be a string")
    if not user_id:
        raise ValueError("user_id must not be empty")
    secret = _get_auth_secret()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "user_id": user_id,
        "iat": now,
        "exp": now + timedelta(seconds=_ACCESS_TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, secret, algorithm=_ACCESS_TOKEN_ALGORITHM)


def decode_access_token(token: str) -> dict[str, str]:
    """Decode and verify an HS256 access token.

    The algorithm is pinned explicitly to HS256 on every call, so a token
    presented with `alg: none` or signed with any other algorithm is
    rejected rather than accepted, regardless of its claimed header.

    The verifier enforces the token contract independently of the minter
    (F-1.1-09): `exp` and `user_id` are required rather than merely
    validated when present, `exp` must be a real number rather than a
    string PyJWT would coerce, and an `exp` further out than the 15-minute
    policy allows is rejected. A verifier that trusts the minting path has
    no contract of its own, and any second minting path (a test helper, a
    migration script, an admin tool) would silently inherit an unbounded
    token.

    Args:
        token: The encoded JWT to verify.

    Returns:
        A dict with the single key `user_id`.

    Raises:
        TypeError: If token is not a string.
        ValueError: If token is empty, expired, tampered, signed with the
            wrong secret, signed with any algorithm other than HS256,
            missing `exp` or `user_id`, or carrying an `exp` that is not a
            number or that exceeds the 15-minute access-token policy.
        RuntimeError: If AUTH_SECRET is unset.
    """
    if not isinstance(token, str):
        raise TypeError("token must be a string")
    if not token:
        raise ValueError("token must not be empty")
    secret = _get_auth_secret()
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_ACCESS_TOKEN_ALGORITHM],
            options={"require": ["exp", "user_id"], "verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("access token has expired") from None
    except jwt.PyJWTError:
        raise ValueError("access token is invalid") from None

    expires_at = payload.get("exp")
    # bool is a subclass of int, and PyJWT coerces a numeric string, so
    # both are excluded explicitly rather than left to duck typing.
    if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
        # The TRY004 suppression below is deliberate. A wrongly typed claim
        # inside an attacker-supplied token is an invalid token, not a
        # caller type error: this function reserves TypeError for `token`
        # itself being the wrong type, per the contract documented above.
        raise ValueError("access token is invalid")  # noqa: TRY004
    ceiling = datetime.now(UTC).timestamp() + _ACCESS_TOKEN_TTL_SECONDS + _MAX_EXP_SKEW_SECONDS
    if expires_at > ceiling:
        raise ValueError("access token is invalid")

    if "user_id" not in payload:
        raise ValueError("access token is invalid")
    return {"user_id": payload["user_id"]}


def generate_refresh_token() -> str:
    """Generate an opaque refresh token.

    Never a JWT. Carries at least 32 bytes of entropy
    (`secrets.token_urlsafe`), and differs across successive calls.

    Returns:
        A URL-safe random string suitable for issuing to a client. Only
        its hash (see `hash_refresh_token`) is ever stored.
    """
    return secrets.token_urlsafe(_REFRESH_TOKEN_ENTROPY_BYTES)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage.

    Args:
        token: The raw opaque refresh token.

    Returns:
        The hex-encoded SHA-256 digest of the token. The raw token itself
        is never what this function returns for storage.

    Raises:
        TypeError: If token is not a string.
        ValueError: If token is an empty string.
    """
    if not isinstance(token, str):
        raise TypeError("token must be a string")
    if not token:
        raise ValueError("token must not be empty")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_refresh_token(token: str, token_hash: str) -> bool:
    """Verify a raw refresh token against its stored SHA-256 hash.

    Args:
        token: The raw opaque refresh token presented by the client.
        token_hash: The stored SHA-256 hash to check against.

    Returns:
        True if token hashes to token_hash. False for a wrong token, a
        missing or null token or hash. Never raises.
    """
    if not isinstance(token, str) or not isinstance(token_hash, str):
        return False
    if not token or not token_hash:
        return False
    computed = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return secrets.compare_digest(computed, token_hash)
