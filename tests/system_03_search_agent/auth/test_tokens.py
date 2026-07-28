"""Tests for HS256 access tokens and opaque refresh tokens (T-1.1-02)."""

import base64
import json
import logging
import time

import jwt
import pytest

from system_03_search_agent.auth.tokens import (
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    mint_access_token,
    verify_refresh_token,
)

_TEST_SECRET = "unit-test-secret-do-not-use-in-production-environments-48b"


@pytest.fixture(autouse=True)
def _auth_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set AUTH_SECRET for every test unless a test explicitly unsets it."""
    monkeypatch.setenv("AUTH_SECRET", _TEST_SECRET)


def _make_none_alg_token(payload: dict[str, object]) -> str:
    """Build a raw `alg: none` JWT with no signature, bypassing PyJWT encode."""

    def _b64(data: dict[str, object]) -> str:
        raw = json.dumps(data).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = {"alg": "none", "typ": "JWT"}
    return f"{_b64(header)}.{_b64(payload)}."


# --- access token: mint ---


def test_mint_access_token_valid_input_returns_a_string() -> None:
    token = mint_access_token("user-123")
    assert isinstance(token, str)
    assert token.count(".") == 2


def test_mint_access_token_invalid_input_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        mint_access_token("")


def test_mint_access_token_missing_input_none_raises() -> None:
    with pytest.raises(TypeError):
        mint_access_token(None)  # type: ignore[arg-type]


def test_mint_access_token_missing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        mint_access_token("user-123")


# --- access token: decode, valid path ---


def test_decode_access_token_valid_input_round_trips_user_id() -> None:
    token = mint_access_token("user-123")
    claims = decode_access_token(token)
    assert claims == {"user_id": "user-123"}


def test_decode_access_token_claims_contain_only_user_id_and_registered_claims() -> None:
    token = mint_access_token("user-123")
    raw_payload = jwt.decode(token, _TEST_SECRET, algorithms=["HS256"])
    assert set(raw_payload.keys()) == {"user_id", "iat", "exp"}


# --- access token: decode, invalid/adversarial paths ---


def test_decode_access_token_invalid_input_garbage_string_raises() -> None:
    with pytest.raises(ValueError):
        decode_access_token("not.a.jwt")


def test_decode_access_token_invalid_input_tampered_signature_raises() -> None:
    token = mint_access_token("user-123")
    header, payload, signature = token.split(".")
    tampered_signature = ("a" if signature[0] != "a" else "b") + signature[1:]
    tampered = f"{header}.{payload}.{tampered_signature}"
    with pytest.raises(ValueError):
        decode_access_token(tampered)


def test_decode_access_token_invalid_input_expired_raises() -> None:
    now = int(time.time())
    expired_payload = {"user_id": "user-123", "iat": now - 1000, "exp": now - 100}
    expired_token = jwt.encode(expired_payload, _TEST_SECRET, algorithm="HS256")
    with pytest.raises(ValueError):
        decode_access_token(expired_token)


def test_decode_access_token_invalid_input_wrong_secret_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = mint_access_token("user-123")
    monkeypatch.setenv("AUTH_SECRET", "a-completely-different-secret-that-is-also-long-enough")
    with pytest.raises(ValueError):
        decode_access_token(token)


def test_decode_access_token_invalid_input_wrong_algorithm_raises() -> None:
    now = int(time.time())
    payload = {
        "user_id": "user-123",
        "iat": now,
        "exp": now + 900,
    }
    wrong_alg_token = jwt.encode(payload, _TEST_SECRET, algorithm="HS384")
    with pytest.raises(ValueError):
        decode_access_token(wrong_alg_token)


def test_decode_access_token_invalid_input_alg_none_raises() -> None:
    now = int(time.time())
    payload = {"user_id": "user-123", "iat": now, "exp": now + 900}
    none_alg_token = _make_none_alg_token(payload)
    with pytest.raises(ValueError):
        decode_access_token(none_alg_token)


def test_decode_access_token_missing_input_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        decode_access_token("")


def test_decode_access_token_missing_input_none_raises() -> None:
    with pytest.raises(TypeError):
        decode_access_token(None)  # type: ignore[arg-type]


def test_decode_access_token_missing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    token = mint_access_token("user-123")
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        decode_access_token(token)


def test_decode_access_token_error_never_leaks_token_or_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = mint_access_token("user-123")
    header, payload, _ = token.split(".")
    tampered = f"{header}.{payload}.invalid-signature"
    with caplog.at_level(logging.DEBUG):
        try:
            decode_access_token(tampered)
        except ValueError as exc:
            assert _TEST_SECRET not in str(exc)
    for record in caplog.records:
        assert _TEST_SECRET not in record.getMessage()


# --- refresh token: generation ---


def test_generate_refresh_token_valid_returns_non_jwt_opaque_string() -> None:
    token = generate_refresh_token()
    assert isinstance(token, str)
    # A JWT has exactly two dots. Reject the token as opaque if it happens
    # to parse as one; assert it is not a JWT either structurally or by
    # decode failure.
    with pytest.raises(Exception):  # noqa: B017 - any decode failure proves non-JWT
        jwt.decode(token, options={"verify_signature": False})


def test_generate_refresh_token_has_at_least_32_bytes_of_entropy() -> None:
    token = generate_refresh_token()
    # token_urlsafe(32) base64-encodes 32 raw bytes with no padding.
    # Reconstruct the padded form and decode to confirm the byte length.
    padded = token + "=" * (-len(token) % 4)
    decoded = base64.urlsafe_b64decode(padded)
    assert len(decoded) >= 32


def test_generate_refresh_token_differs_across_successive_calls() -> None:
    first = generate_refresh_token()
    second = generate_refresh_token()
    assert first != second


# --- refresh token: hashing ---


def test_hash_refresh_token_valid_input_never_equals_the_raw_token() -> None:
    token = generate_refresh_token()
    token_hash = hash_refresh_token(token)
    assert isinstance(token_hash, str)
    assert token_hash != token


def test_hash_refresh_token_invalid_input_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        hash_refresh_token("")


def test_hash_refresh_token_missing_input_none_raises() -> None:
    with pytest.raises(TypeError):
        hash_refresh_token(None)  # type: ignore[arg-type]


# --- refresh token: verification ---


def test_verify_refresh_token_valid_input_matches_its_own_hash() -> None:
    token = generate_refresh_token()
    token_hash = hash_refresh_token(token)
    assert verify_refresh_token(token, token_hash) is True


def test_verify_refresh_token_invalid_input_wrong_token_fails() -> None:
    token = generate_refresh_token()
    token_hash = hash_refresh_token(token)
    other_token = generate_refresh_token()
    assert verify_refresh_token(other_token, token_hash) is False


def test_verify_refresh_token_missing_input_none_token_returns_false() -> None:
    token_hash = hash_refresh_token(generate_refresh_token())
    assert verify_refresh_token(None, token_hash) is False  # type: ignore[arg-type]


def test_verify_refresh_token_missing_input_none_hash_returns_false() -> None:
    token = generate_refresh_token()
    assert verify_refresh_token(token, None) is False  # type: ignore[arg-type]


def test_verify_refresh_token_null_input_empty_strings_return_false() -> None:
    assert verify_refresh_token("", "") is False
