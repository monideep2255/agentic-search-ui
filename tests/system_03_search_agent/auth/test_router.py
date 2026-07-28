"""Integration tests for the `/auth` router (T-1.1-03).

Hits the real local PostgreSQL `search_agent_users` database through the
actual FastAPI app and its session dependency, not a mock: the unique
constraint on `users.email`, the refresh-token rotation transaction, and
the `auth_sessions` revocation state cannot be verified against a mock
session. The whole module skips cleanly (does not fail) when
USER_DB_URL is unreachable, matching the pattern in
`tests/system_03_search_agent/data/test_migration.py`.

Every test uses a freshly generated email (uuid4-based) so reruns never
collide with rows a prior run left behind, the same convention
`test_models.py` already uses for this database.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

USER_DB_URL = os.environ.get("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")
os.environ.setdefault("USER_DB_URL", USER_DB_URL)


def _can_connect() -> bool:
    try:
        probe_engine = sa.create_engine(USER_DB_URL)
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


if not _can_connect():
    pytest.skip(
        "search_agent_users PostgreSQL database is not reachable; "
        "set USER_DB_URL and ensure the server is running to run this suite",
        allow_module_level=True,
    )

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.data.models import User

_TEST_AUTH_SECRET = "test-only-auth-secret-for-router-tests-do-not-reuse"


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


def _signup(client: TestClient, email: str | None = None, password: str = "Str0ngPassw0rd!"):
    email = email or _unique_email()
    response = client.post("/auth/signup", json={"email": email, "password": password})
    return email, password, response


def _login(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def _signup_and_login(client: TestClient) -> tuple[str, str, dict]:
    email, password, signup_response = _signup(client)
    assert signup_response.status_code == 201
    login_response = _login(client, email, password)
    assert login_response.status_code == 200
    return email, password, login_response.json()


def _count_users_with_email(email: str) -> int:
    engine = sa.create_engine(USER_DB_URL, future=True)
    try:
        with Session(bind=engine, future=True) as session:
            return len(session.execute(select(User).where(User.email == email)).all())
    finally:
        engine.dispose()


def _expired_access_token(user_id: str) -> str:
    now = datetime.now(UTC)
    payload = {"user_id": user_id, "iat": now - timedelta(minutes=30), "exp": now - timedelta(minutes=1)}
    return jwt.encode(payload, _TEST_AUTH_SECRET, algorithm="HS256")


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------


def test_signup_unused_email_returns_201_and_creates_one_row(client):
    email, _password, response = _signup(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert "password_hash" not in body
    assert _count_users_with_email(email) == 1


def test_signup_duplicate_email_returns_409_and_creates_no_second_row(client):
    email, password, first = _signup(client)
    assert first.status_code == 201

    second = _signup(client, email=email, password=password)[2]
    assert second.status_code == 409
    assert "password_hash" not in second.text
    assert _count_users_with_email(email) == 1


def test_signup_missing_password_returns_422(client):
    response = client.post("/auth/signup", json={"email": _unique_email()})
    assert response.status_code == 422


def test_signup_null_password_returns_422(client):
    response = client.post("/auth/signup", json={"email": _unique_email(), "password": None})
    assert response.status_code == 422


def test_signup_unknown_field_returns_422(client):
    response = client.post(
        "/auth/signup",
        json={"email": _unique_email(), "password": "Str0ngPassw0rd!", "is_admin": True},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


def test_login_correct_credentials_returns_tokens_and_updates_last_login(client):
    email, password, _signup_response = _signup(client)
    response = _login(client, email, password)
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert "password_hash" not in body
    assert "refresh_token_hash" not in body

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["last_login_at"] is not None


def test_login_wrong_password_returns_401_with_no_token(client):
    email, _password, _signup_response = _signup(client)
    response = _login(client, email, "the-wrong-password")
    assert response.status_code == 401
    assert "access_token" not in response.json()


def test_login_unknown_email_and_wrong_password_are_indistinguishable(client):
    email, _password, _signup_response = _signup(client)

    unknown_response = _login(client, _unique_email(), "whatever-password")
    wrong_password_response = _login(client, email, "the-wrong-password")

    assert unknown_response.status_code == wrong_password_response.status_code == 401
    assert unknown_response.json() == wrong_password_response.json()
    assert unknown_response.text == wrong_password_response.text


def test_login_missing_password_returns_422(client):
    response = client.post("/auth/login", json={"email": _unique_email()})
    assert response.status_code == 422


def test_login_null_email_returns_422(client):
    response = client.post("/auth/login", json={"email": None, "password": "x"})
    assert response.status_code == 422


def test_login_unknown_field_returns_422(client):
    response = client.post(
        "/auth/login",
        json={"email": _unique_email(), "password": "x", "remember_me": True},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


def test_refresh_rotates_and_old_token_401s_after_use(client):
    _email, _password, tokens = _signup_and_login(client)
    old_refresh = tokens["refresh_token"]

    first = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert first.status_code == 200
    new_body = first.json()
    assert new_body["refresh_token"] != old_refresh
    # A fresh access token minted in the same second as the original can be
    # byte-identical (same user_id, same iat/exp to the second); rotation
    # is proven by the refresh token, which is why that assertion is above.
    # The new access token must still be independently valid, which is
    # asserted via /auth/me below.

    replay = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {new_body['access_token']}"})
    assert me.status_code == 200

    # The rotated token still works.
    second = client.post("/auth/refresh", json={"refresh_token": new_body["refresh_token"]})
    assert second.status_code == 200


def test_refresh_invalid_token_returns_401(client):
    response = client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401


def test_refresh_missing_field_returns_422(client):
    response = client.post("/auth/refresh", json={})
    assert response.status_code == 422


def test_refresh_unknown_field_returns_422(client):
    response = client.post(
        "/auth/refresh", json={"refresh_token": "whatever", "device_id": "abc"}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


def test_logout_then_refresh_returns_401(client):
    _email, _password, tokens = _signup_and_login(client)
    refresh_token = tokens["refresh_token"]

    logout_response = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_response.status_code == 200

    replay = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401


def test_logout_invalid_token_returns_401(client):
    response = client.post("/auth/logout", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401


def test_logout_missing_field_returns_422(client):
    response = client.post("/auth/logout", json={})
    assert response.status_code == 422


def test_logout_unknown_field_returns_422(client):
    response = client.post("/auth/logout", json={"refresh_token": "whatever", "all_devices": True})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


def test_me_valid_token_returns_profile(client):
    email, _password, tokens = _signup_and_login(client)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email
    assert "password_hash" not in body


def test_me_missing_token_returns_401(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_malformed_token_returns_401(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"})
    assert response.status_code == 401


def test_me_missing_bearer_scheme_returns_401(client):
    _email, _password, tokens = _signup_and_login(client)
    response = client.get("/auth/me", headers={"Authorization": tokens["access_token"]})
    assert response.status_code == 401


def test_me_expired_token_returns_401(client):
    _email, _password, signup_response = _signup(client)
    user_id = signup_response.json()["id"]
    expired = _expired_access_token(user_id)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Phase 1.0 regression: /health and /query unchanged by mounting the router.
# ---------------------------------------------------------------------------


def test_health_unaffected_by_auth_router(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_router_does_not_shadow_query_route(client):
    # A malformed /query body should still 422 from the phase 1.0 contract,
    # not 404, proving the auth router mount left routing intact.
    response = client.post("/query", json={})
    assert response.status_code == 422
