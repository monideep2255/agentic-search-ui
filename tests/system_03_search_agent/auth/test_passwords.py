"""Tests for argon2id password hashing (T-1.1-02)."""

import logging

import pytest

from system_03_search_agent.auth.passwords import hash_password, verify_password


def test_hash_password_valid_input_returns_hash_not_equal_to_plaintext() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert isinstance(password_hash, str)
    assert password_hash != "correct horse battery staple"


def test_hash_password_invalid_input_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        hash_password("")


def test_hash_password_missing_input_none_raises() -> None:
    with pytest.raises(TypeError):
        hash_password(None)  # type: ignore[arg-type]


def test_verify_password_valid_input_matches_its_own_hash() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", password_hash) is True


def test_verify_password_invalid_input_wrong_password_fails() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert verify_password("wrong password", password_hash) is False


def test_verify_password_invalid_input_malformed_hash_returns_false() -> None:
    assert verify_password("correct horse battery staple", "not-a-real-hash") is False


def test_verify_password_missing_input_none_password_returns_false() -> None:
    password_hash = hash_password("correct horse battery staple")
    assert verify_password(None, password_hash) is False  # type: ignore[arg-type]


def test_verify_password_missing_input_none_hash_returns_false() -> None:
    assert verify_password("correct horse battery staple", None) is False  # type: ignore[arg-type]


def test_verify_password_null_input_empty_strings_return_false() -> None:
    assert verify_password("", "") is False


def test_hash_password_never_logs_plaintext_or_hash(
    caplog: pytest.LogCaptureFixture,
) -> None:
    plaintext = "correct horse battery staple"
    with caplog.at_level(logging.DEBUG):
        password_hash = hash_password(plaintext)
        verify_password(plaintext, password_hash)
    for record in caplog.records:
        assert plaintext not in record.getMessage()
        assert password_hash not in record.getMessage()


def test_verify_password_malformed_hash_never_raises_with_hash_in_message() -> None:
    malformed_hash = "$argon2id$garbage$"
    try:
        result = verify_password("some password", malformed_hash)
    except Exception as exc:
        assert malformed_hash not in str(exc)
        assert "some password" not in str(exc)
        raise
    assert result is False
