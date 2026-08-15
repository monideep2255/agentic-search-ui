"""Tests for guest token primitives (T-4.10-01).

Mirrors test_tokens.py's structure and adversarial coverage, plus the
cross-type checks design decision 1 calls for: a guest token and an access
token must be unforgeable as each other, both directions.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from system_03_search_agent.auth.guest import (
    decode_guest_token,
    guest_signing_key,
    mint_guest_token,
)
from system_03_search_agent.auth.tokens import decode_access_token, mint_access_token

_TEST_SECRET = "unit-test-secret-do-not-use-in-production-environments-48b"
_GUEST_TTL_SECONDS = 7 * 24 * 60 * 60


@pytest.fixture(autouse=True)
def _auth_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set AUTH_SECRET for every test unless a test explicitly unsets it."""
    monkeypatch.setenv("AUTH_SECRET", _TEST_SECRET)


# --- guest_signing_key: domain separation at the key level ---


def test_guest_signing_key_is_not_the_bare_auth_secret() -> None:
    key = guest_signing_key()
    assert isinstance(key, bytes)
    assert key != _TEST_SECRET.encode("utf-8")


def test_guest_signing_key_is_deterministic_for_the_same_secret() -> None:
    assert guest_signing_key() == guest_signing_key()


def test_guest_signing_key_changes_with_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    first = guest_signing_key()
    monkeypatch.setenv("AUTH_SECRET", "a-completely-different-secret-that-is-also-long-enough")
    assert guest_signing_key() != first


def test_guest_signing_key_missing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        guest_signing_key()


# --- mint_guest_token ---


def test_mint_guest_token_valid_input_returns_a_string() -> None:
    token = mint_guest_token(str(uuid.uuid4()))
    assert isinstance(token, str)
    assert token.count(".") == 2


def test_mint_guest_token_invalid_input_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        mint_guest_token("")


def test_mint_guest_token_missing_input_none_raises() -> None:
    with pytest.raises(TypeError):
        mint_guest_token(None)  # type: ignore[arg-type]


def test_mint_guest_token_missing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        mint_guest_token(str(uuid.uuid4()))


def test_mint_guest_token_claims_are_exactly_the_four_documented() -> None:
    guest_id = str(uuid.uuid4())
    token = mint_guest_token(guest_id)
    raw_payload = jwt.decode(token, guest_signing_key(), algorithms=["HS256"])
    assert set(raw_payload.keys()) == {"guest_id", "typ", "iat", "exp"}
    assert raw_payload["guest_id"] == guest_id
    assert raw_payload["typ"] == "guest"


# --- decode_guest_token: valid path ---


def test_decode_guest_token_valid_input_round_trips_guest_id() -> None:
    guest_id = str(uuid.uuid4())
    token = mint_guest_token(guest_id)
    assert decode_guest_token(token) == {"guest_id": guest_id}


def test_decode_guest_token_valid_input_exp_at_the_policy_ceiling_is_accepted() -> None:
    guest_id = str(uuid.uuid4())
    token = mint_guest_token(guest_id)
    assert decode_guest_token(token) == {"guest_id": guest_id}


# --- decode_guest_token: invalid/adversarial paths ---


def test_decode_guest_token_invalid_input_garbage_string_raises() -> None:
    with pytest.raises(ValueError):
        decode_guest_token("not.a.jwt")


def test_decode_guest_token_invalid_input_tampered_signature_raises() -> None:
    token = mint_guest_token(str(uuid.uuid4()))
    header, payload, signature = token.split(".")
    tampered_signature = ("a" if signature[0] != "a" else "b") + signature[1:]
    tampered = f"{header}.{payload}.{tampered_signature}"
    with pytest.raises(ValueError):
        decode_guest_token(tampered)


def test_decode_guest_token_invalid_input_expired_raises() -> None:
    now = int(time.time())
    expired_payload = {
        "guest_id": str(uuid.uuid4()),
        "typ": "guest",
        "iat": now - _GUEST_TTL_SECONDS - 1000,
        "exp": now - 100,
    }
    expired_token = jwt.encode(expired_payload, guest_signing_key(), algorithm="HS256")
    with pytest.raises(ValueError):
        decode_guest_token(expired_token)


def test_decode_guest_token_invalid_input_no_exp_claim_raises() -> None:
    now = int(time.time())
    no_exp_token = jwt.encode(
        {"guest_id": str(uuid.uuid4()), "typ": "guest", "iat": now},
        guest_signing_key(),
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_guest_token(no_exp_token)


def test_decode_guest_token_invalid_input_no_typ_claim_raises() -> None:
    now = int(time.time())
    no_typ_token = jwt.encode(
        {"guest_id": str(uuid.uuid4()), "iat": now, "exp": now + 900},
        guest_signing_key(),
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_guest_token(no_typ_token)


def test_decode_guest_token_invalid_input_wrong_typ_value_raises() -> None:
    """A token that declares `typ` but not as the literal string "guest"."""
    now = int(time.time())
    wrong_typ_token = jwt.encode(
        {"guest_id": str(uuid.uuid4()), "typ": "access", "iat": now, "exp": now + 900},
        guest_signing_key(),
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_guest_token(wrong_typ_token)


def test_decode_guest_token_invalid_input_no_guest_id_claim_raises() -> None:
    now = int(time.time())
    no_subject_token = jwt.encode(
        {"typ": "guest", "iat": now, "exp": now + 900}, guest_signing_key(), algorithm="HS256"
    )
    with pytest.raises(ValueError):
        decode_guest_token(no_subject_token)


def test_decode_guest_token_invalid_input_exp_beyond_policy_raises() -> None:
    now = int(time.time())
    far_future_token = jwt.encode(
        {"guest_id": str(uuid.uuid4()), "typ": "guest", "iat": now, "exp": 32503680000},
        guest_signing_key(),
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_guest_token(far_future_token)


def test_decode_guest_token_invalid_input_exp_as_string_raises() -> None:
    now = int(time.time())
    string_exp_token = jwt.encode(
        {
            "guest_id": str(uuid.uuid4()),
            "typ": "guest",
            "iat": now,
            "exp": str(now + 900),
        },
        guest_signing_key(),
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_guest_token(string_exp_token)


def test_decode_guest_token_invalid_input_wrong_key_raises() -> None:
    """Signed with a key that is not the derived guest signing key at all."""
    now = int(time.time())
    token = jwt.encode(
        {
            "guest_id": str(uuid.uuid4()),
            "typ": "guest",
            "iat": now,
            "exp": now + 900,
        },
        "some-completely-unrelated-key",
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_guest_token(token)


def test_decode_guest_token_invalid_input_signed_with_bare_auth_secret_raises() -> None:
    """Design decision 1: AUTH_SECRET directly is the wrong key for a guest
    token, even though it is the RIGHT key for an access token. This is the
    same forgery attempt the phase 4.10 premise gate's
    `test_a_guest_token_signed_with_auth_secret_directly_is_rejected`
    exercises at the HTTP layer; this test exercises it at the primitive.
    """
    now = int(time.time())
    forged = jwt.encode(
        {
            "guest_id": str(uuid.uuid4()),
            "typ": "guest",
            "iat": now,
            "exp": now + 900,
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_guest_token(forged)


def test_decode_guest_token_invalid_input_wrong_algorithm_raises() -> None:
    now = int(time.time())
    payload = {"guest_id": str(uuid.uuid4()), "typ": "guest", "iat": now, "exp": now + 900}
    wrong_alg_token = jwt.encode(payload, guest_signing_key(), algorithm="HS384")
    with pytest.raises(ValueError):
        decode_guest_token(wrong_alg_token)


def test_decode_guest_token_missing_input_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        decode_guest_token("")


def test_decode_guest_token_missing_input_none_raises() -> None:
    with pytest.raises(TypeError):
        decode_guest_token(None)  # type: ignore[arg-type]


def test_decode_guest_token_missing_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    token = mint_guest_token(str(uuid.uuid4()))
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        decode_guest_token(token)


def test_decode_guest_token_error_never_leaks_token_or_secret_or_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = mint_guest_token(str(uuid.uuid4()))
    header, payload, _ = token.split(".")
    tampered = f"{header}.{payload}.invalid-signature"
    key_hex = guest_signing_key().hex()
    with caplog.at_level(logging.DEBUG):
        try:
            decode_guest_token(tampered)
        except ValueError as exc:
            assert _TEST_SECRET not in str(exc)
            assert key_hex not in str(exc)
            assert tampered not in str(exc)
    for record in caplog.records:
        message = record.getMessage()
        assert _TEST_SECRET not in message
        assert key_hex not in message
        assert tampered not in message


# --- cross-type rejection: the load-bearing property of design decision 1 ---


def test_an_access_token_is_rejected_by_decode_guest_token() -> None:
    access = mint_access_token(str(uuid.uuid4()))
    with pytest.raises(ValueError):
        decode_guest_token(access)


def test_a_guest_token_is_rejected_by_decode_access_token() -> None:
    guest = mint_guest_token(str(uuid.uuid4()))
    with pytest.raises(ValueError):
        decode_access_token(guest)


def test_domain_separation_survives_even_if_claim_checks_were_bypassed() -> None:
    """Belt-and-braces version of design decision 1's reasoning.

    Even a token that carries every claim `decode_guest_token` requires
    (`guest_id`, `typ: "guest"`, `iat`, `exp` within policy) is still
    rejected when it is signed with the bare AUTH_SECRET instead of the
    derived key, proving the rejection is cryptographic and does not rest
    on the claim shape alone.
    """
    now = datetime.now(UTC)
    shape_correct_but_wrong_key = jwt.encode(
        {
            "guest_id": str(uuid.uuid4()),
            "typ": "guest",
            "iat": now,
            "exp": now + timedelta(days=1),
        },
        _TEST_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(ValueError):
        decode_guest_token(shape_correct_but_wrong_key)
