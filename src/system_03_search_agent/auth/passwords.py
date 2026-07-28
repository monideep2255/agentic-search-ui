"""Password hashing primitives for the auth service.

Argon2id hashing and verification only (Technical_specification.md Section
15, lines 2384-2388). No HTTP, no database access.

Never logs and never raises with the plaintext password or the resulting
hash embedded in a log record or exception string: only literal field
names appear in any message this module produces.

Depends on:
    - argon2-cffi (PyPI package providing the `argon2` module)
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using argon2id.

    Args:
        password: The plaintext password to hash. Never logged.

    Returns:
        An argon2id hash string suitable for storage. Never equal to the
        input plaintext.

    Raises:
        TypeError: If password is not a string.
        ValueError: If password is an empty string.
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    if not password:
        raise ValueError("password must not be empty")
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored argon2id hash.

    Args:
        password: The plaintext password to check. Never logged.
        password_hash: The stored argon2id hash. Never logged.

    Returns:
        True if password matches password_hash. False for a wrong
        password, a missing or null password or hash, or a malformed
        hash. This function never raises; every failure path returns
        False rather than surfacing an exception that could echo the
        input values.
    """
    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    if not password or not password_hash:
        return False
    try:
        return _password_hasher.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        return False
