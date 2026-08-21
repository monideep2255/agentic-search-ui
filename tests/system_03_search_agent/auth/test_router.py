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
from system_03_search_agent.auth.tokens import hash_refresh_token
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


def test_signup_case_variant_email_returns_409_and_creates_no_second_row(client):
    """F-1.1-08 regression: the adversary's four-variant reproduction."""
    email, password, first = _signup(client)
    assert first.status_code == 201

    for variant in (
        email.upper(),
        f"{email.split('@')[0]}@{email.split('@')[1].upper()}",
        f" {email}",
        f"{email} ",
    ):
        response = _signup(client, email=variant, password=password)[2]
        assert response.status_code == 409, f"{variant!r} opened a second account"

    assert _count_users_with_email(email) == 1
    # And no row exists under any of the variant spellings either.
    assert _count_users_with_email(email.upper()) == 0


def test_login_resolves_a_case_variant_to_the_same_account(client):
    """F-1.1-08 regression: a user who types a different case still logs in."""
    email, password, signup_response = _signup(client)
    assert signup_response.status_code == 201
    user_id = signup_response.json()["id"]

    response = _login(client, email.upper(), password)
    assert response.status_code == 200

    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["id"] == user_id
    assert me.json()["email"] == email


def test_signup_stores_the_normalized_email_not_the_submitted_spelling(client):
    """F-1.1-08 regression: normalization happens before the insert, not after."""
    email = _unique_email()
    response = _signup(client, email=f"  {email.upper()}  ")[2]
    assert response.status_code == 201
    assert response.json()["email"] == email
    assert _count_users_with_email(email) == 1


@pytest.mark.parametrize(
    "malformed_email",
    [
        "not-an-email",
        "@",
        "<script>alert(1)</script>@x.com",
        "' OR 1=1 --@x.com",
        "x@x.com\n\rInjected: yes",
        "user@localhost",
        "user@@example.com",
        ".user@example.com",
        "user.@example.com",
    ],
)
def test_signup_malformed_email_returns_422(client, malformed_email):
    """F-1.1-13 regression: every payload the adversary got a 201 from."""
    # Counted before and after rather than asserted to be zero: the
    # adversary's own run left rows behind under several of these exact
    # addresses, so the property to prove is that this request creates no
    # new row, not that no row has ever existed.
    before = _count_users_with_email(malformed_email)
    response = client.post(
        "/auth/signup", json={"email": malformed_email, "password": "Str0ngPassw0rd!"}
    )
    assert response.status_code == 422
    assert _count_users_with_email(malformed_email) == before


@pytest.mark.parametrize(
    "malformed_email",
    ["not-an-email", "@", "x@x.com\n\rInjected: yes"],
)
def test_login_malformed_email_returns_422(client, malformed_email):
    """F-1.1-13 regression: the same boundary check on the login path."""
    response = client.post(
        "/auth/login", json={"email": malformed_email, "password": "Str0ngPassw0rd!"}
    )
    assert response.status_code == 422


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

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {new_body['access_token']}"})
    assert me.status_code == 200

    # The rotated token still works. Asserted before the replay below, not
    # after it: since F-1.1-07 the replay is a reuse event that revokes the
    # whole family by design, so a chain that survives a replay would now
    # be the defect rather than the property. Every assertion this test
    # originally made is still made, in an order that does not require the
    # reuse cascade to be absent.
    second = client.post("/auth/refresh", json={"refresh_token": new_body["refresh_token"]})
    assert second.status_code == 200

    replay = client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


def test_refresh_reuse_of_a_rotated_token_revokes_the_whole_family(client):
    """F-1.1-07 regression, the adversary's own reproduction.

    Attacker steals R1 and rotates first, victim replays R1, and the reuse
    must end the attacker's chain and the victim's other device too, not
    just 401 the replay.
    """
    email, password, first_device = _signup_and_login(client)
    second_device = _login(client, email, password)
    assert second_device.status_code == 200
    stolen = first_device["refresh_token"]
    other_device = second_device.json()["refresh_token"]

    # The attacker rotates first and gets a working chain.
    rotated = client.post("/auth/refresh", json={"refresh_token": stolen})
    assert rotated.status_code == 200
    attacker_chain = rotated.json()["refresh_token"]

    # The victim replays the token it still believes is current.
    replay = client.post("/auth/refresh", json={"refresh_token": stolen})
    assert replay.status_code == 401
    # The 401 body is the ordinary one: nothing discloses that a reuse was
    # detected.
    assert replay.json()["detail"] == "invalid or expired refresh token"

    # Before the fix the attacker kept rotating indefinitely from here.
    assert client.post("/auth/refresh", json={"refresh_token": attacker_chain}).status_code == 401
    # And the victim's other device kept working. Both holders are now
    # forced back to /auth/login, which is the property Section 15 claims.
    assert client.post("/auth/refresh", json={"refresh_token": other_device}).status_code == 401

    # The password is the control point again: a fresh login still works.
    assert _login(client, email, password).status_code == 200


def test_refresh_reuse_does_not_revoke_another_users_sessions(client):
    """The F-1.1-07 cascade is scoped to the family's own user."""
    _email, _password, victim = _signup_and_login(client)
    _bystander_email, _bystander_password, bystander = _signup_and_login(client)

    stolen = victim["refresh_token"]
    assert client.post("/auth/refresh", json={"refresh_token": stolen}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": stolen}).status_code == 401

    assert (
        client.post("/auth/refresh", json={"refresh_token": bystander["refresh_token"]}).status_code
        == 200
    )


def test_refresh_carries_the_absolute_ceiling_forward_instead_of_renewing_it(client):
    """F-1.1-07 regression: `expires_at` renews on rotation, the ceiling does not."""
    _email, _password, tokens = _signup_and_login(client)
    rotated = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert rotated.status_code == 200

    engine = sa.create_engine(USER_DB_URL, future=True)
    try:
        with Session(bind=engine, future=True) as session:
            rows = session.execute(
                sa.text(
                    "SELECT absolute_expires_at, expires_at FROM auth_sessions "
                    "WHERE refresh_token_hash IN (:original, :rotated) "
                    "ORDER BY created_at"
                ),
                {
                    "original": hash_refresh_token(tokens["refresh_token"]),
                    "rotated": hash_refresh_token(rotated.json()["refresh_token"]),
                },
            ).fetchall()
    finally:
        engine.dispose()

    assert len(rows) == 2
    original, replacement = rows
    assert original.absolute_expires_at is not None
    # The ceiling is identical across the rotation, so a chain cannot
    # outlive it however many times it rotates.
    assert replacement.absolute_expires_at == original.absolute_expires_at
    # The idle window, by contrast, did move forward.
    assert replacement.expires_at > original.expires_at


def test_refresh_past_the_absolute_ceiling_returns_401_even_when_not_expired(client):
    """F-1.1-07 regression: a chain past its ceiling cannot rotate again.

    Backdates only `absolute_expires_at` on this test's own row, leaving
    `expires_at` well in the future, so the 401 can only come from the
    ceiling.
    """
    _email, _password, tokens = _signup_and_login(client)
    token_hash = hash_refresh_token(tokens["refresh_token"])

    engine = sa.create_engine(USER_DB_URL, future=True)
    try:
        with Session(bind=engine, future=True) as session:
            session.execute(
                sa.text(
                    "UPDATE auth_sessions SET absolute_expires_at = now() - interval '1 day' "
                    "WHERE refresh_token_hash = :token_hash"
                ),
                {"token_hash": token_hash},
            )
            session.commit()
    finally:
        engine.dispose()

    assert (
        client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code
        == 401
    )


def test_login_and_refresh_responses_set_cache_control_no_store(client):
    """F-1.1-14 regression: no token-bearing response may be cached."""
    email, password, _signup_response = _signup(client)
    login_response = _login(client, email, password)
    assert login_response.status_code == 200
    assert login_response.headers["cache-control"] == "no-store"
    assert login_response.headers["pragma"] == "no-cache"

    refresh_response = client.post(
        "/auth/refresh", json={"refresh_token": login_response.json()["refresh_token"]}
    )
    assert refresh_response.status_code == 200
    assert refresh_response.headers["cache-control"] == "no-store"
    assert refresh_response.headers["pragma"] == "no-cache"


def test_login_truncates_an_oversized_user_agent_before_persisting_it(client):
    """F-1.1-16 regression: the adversary's 60,000-character User-Agent."""
    email, password, _signup_response = _signup(client)
    hostile_user_agent = "A" * 60_000
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
        headers={"User-Agent": hostile_user_agent},
    )
    assert response.status_code == 200

    engine = sa.create_engine(USER_DB_URL, future=True)
    try:
        with Session(bind=engine, future=True) as session:
            stored_length = session.execute(
                sa.text(
                    "SELECT length(user_agent) FROM auth_sessions "
                    "WHERE refresh_token_hash = :token_hash"
                ),
                {"token_hash": hash_refresh_token(response.json()["refresh_token"])},
            ).scalar_one()
    finally:
        engine.dispose()

    assert stored_length == 512


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
# Phase 1.0 regression: /health and /v1/query unchanged by mounting the
# router. Build phase 4.0 retired the phase 1.0/2.0 buffered POST /query
# endpoint (tracker/phase_4.0.md); this check now targets its finalized
# successor.
# ---------------------------------------------------------------------------


def test_health_unaffected_by_auth_router(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_router_does_not_shadow_v1_query_route(client):
    # A malformed, authenticated /v1/query body should still 422 from the
    # typed request schema, not 404, proving the auth router mount left
    # routing intact. Build phase 2.0 (T-2.0-08) added an auth dependency
    # to this surface, so an unauthenticated request now 401s before body
    # validation runs; authenticate first to isolate the routing check.
    _, _, tokens = _signup_and_login(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = client.post("/v1/query", json={}, headers=headers)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/guest (T-4.10-04)
# ---------------------------------------------------------------------------


def _mint_guest(client: TestClient) -> tuple[str, str]:
    """Mint a real guest through the real endpoint. Returns (guest_id, guest_token)."""
    response = client.post("/auth/guest")
    assert response.status_code == 201, response.text
    body = response.json()
    return body["guest_id"], body["guest_token"]


def _guest_session_row(guest_id: str):
    from system_03_search_agent.data.models import GuestSession

    engine = sa.create_engine(USER_DB_URL, future=True)
    try:
        with Session(bind=engine, future=True) as session:
            return session.execute(
                select(GuestSession).where(GuestSession.id == uuid.UUID(guest_id))
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def test_guest_valid_input_no_body_returns_201_with_a_fresh_allowance(client):
    response = client.post("/auth/guest")
    assert response.status_code == 201
    body = response.json()
    assert body["used"] == 0
    assert body["total"] == 5
    assert isinstance(body["guest_token"], str) and body["guest_token"]
    uuid.UUID(body["guest_id"])  # raises ValueError if not a well-formed UUID


def test_guest_invalid_input_a_body_is_tolerated_since_none_is_required(client):
    # "It never requires a body" (T-4.10-04 acceptance criterion). A caller
    # sending one anyway must not be treated as a hard error: no request
    # model is declared for this endpoint, so FastAPI ignores it.
    response = client.post("/auth/guest", json={"unexpected": "field"})
    assert response.status_code == 201


def test_guest_creates_a_distinct_row_and_token_on_each_call(client):
    first_id, first_token = _mint_guest(client)
    second_id, second_token = _mint_guest(client)
    assert first_id != second_id
    assert first_token != second_token


def test_guest_row_exists_in_guest_sessions_with_zero_runs_used(client):
    guest_id, _token = _mint_guest(client)
    row = _guest_session_row(guest_id)
    assert row is not None
    assert row.runs_used == 0
    assert row.revoked_at is None
    assert row.migrated_to_user_id is None


# ---------------------------------------------------------------------------
# Migration on signup/login (T-4.10-06)
# ---------------------------------------------------------------------------


def test_signup_with_a_valid_guest_token_migrates_and_revokes_the_guest_session(client):
    guest_id, guest_token = _mint_guest(client)
    response = client.post(
        "/auth/signup",
        json={"email": _unique_email(), "password": "Str0ngPassw0rd!", "guest_token": guest_token},
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    row = _guest_session_row(guest_id)
    assert row is not None
    assert row.revoked_at is not None
    assert str(row.migrated_to_user_id) == user_id


def test_login_with_a_valid_guest_token_migrates_and_revokes_the_guest_session(client):
    email, password, _ = _signup_and_login(client)
    guest_id, guest_token = _mint_guest(client)

    response = client.post(
        "/auth/login", json={"email": email, "password": password, "guest_token": guest_token}
    )
    assert response.status_code == 200

    user_row = None
    engine = sa.create_engine(USER_DB_URL, future=True)
    try:
        with Session(bind=engine, future=True) as session:
            user_row = session.execute(select(User).where(User.email == email)).scalar_one()
    finally:
        engine.dispose()

    row = _guest_session_row(guest_id)
    assert row is not None
    assert row.revoked_at is not None
    assert row.migrated_to_user_id == user_row.id


def test_signup_with_a_malformed_guest_token_string_still_returns_201(client):
    """T-4.10-06: authentication is the primary operation; a garbage
    guest_token must not fail signup, only skip migration silently."""
    response = client.post(
        "/auth/signup",
        json={
            "email": _unique_email(),
            "password": "Str0ngPassw0rd!",
            "guest_token": "not-a-real-jwt-at-all",
        },
    )
    assert response.status_code == 201


def test_login_with_an_expired_guest_token_still_succeeds(client):
    """The guest token is invalid/expired, not the account credentials;
    login must still succeed, only migration is skipped."""
    from system_03_search_agent.auth.guest import guest_signing_key

    email, password, _ = _signup_and_login(client)
    now = datetime.now(UTC)
    expired_guest_token = jwt.encode(
        {
            "guest_id": str(uuid.uuid4()),
            "typ": "guest",
            "iat": now - timedelta(days=10),
            "exp": now - timedelta(days=1),
        },
        guest_signing_key(),
        algorithm="HS256",
    )
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password, "guest_token": expired_guest_token},
    )
    assert response.status_code == 200


def test_signup_with_null_guest_token_is_unaffected(client):
    """guest_token omitted entirely: identical to every pre-existing signup
    test in this file, restated here explicitly as this ticket's own
    null-input case."""
    _email, _password, response = _signup(client)
    assert response.status_code == 201
    assert "guest_token" not in response.json()


def test_replaying_the_same_signup_guest_token_is_idempotent(client):
    """T-4.10-06: replaying the same signup with the same guest token gives
    the same end state. Modeled here as two separate account holders
    presenting the identical already-migrated guest token: the second
    presentation must be a harmless no-op (the row stays pointed at the
    FIRST migration), not an error and not a silent re-migration."""
    guest_id, guest_token = _mint_guest(client)

    first_response = client.post(
        "/auth/signup",
        json={"email": _unique_email(), "password": "Str0ngPassw0rd!", "guest_token": guest_token},
    )
    assert first_response.status_code == 201
    first_user_id = first_response.json()["id"]

    second_response = client.post(
        "/auth/signup",
        json={"email": _unique_email(), "password": "Str0ngPassw0rd!", "guest_token": guest_token},
    )
    assert second_response.status_code == 201, (
        "a replayed/already-migrated guest token must never fail signup"
    )

    row = _guest_session_row(guest_id)
    assert row is not None
    assert str(row.migrated_to_user_id) == first_user_id, (
        "a replay must not re-point an already-migrated guest session to a "
        "second account"
    )


def test_a_guest_tokens_migration_never_touches_another_guests_session(client):
    """T-4.10-06: a guest token belonging to a different guest cannot
    migrate a third party's runs/session. old_owner_id (and here,
    migrated_to_user_id) is derived only from the presented token's own
    guest_id claim, so guest A's session must be completely untouched by
    a signup carrying guest B's token."""
    guest_a_id, _guest_a_token = _mint_guest(client)
    _guest_b_id, guest_b_token = _mint_guest(client)

    response = client.post(
        "/auth/signup",
        json={
            "email": _unique_email(),
            "password": "Str0ngPassw0rd!",
            "guest_token": guest_b_token,
        },
    )
    assert response.status_code == 201

    row_a = _guest_session_row(guest_a_id)
    assert row_a is not None
    assert row_a.revoked_at is None
    assert row_a.migrated_to_user_id is None


def test_signup_still_returns_201_when_the_run_reassignment_raises(client, monkeypatch):
    """F-4.10-J-03 (judge round 1): `_migrate_guest_session`'s docstring
    said "NEVER raises" while `reassign_owner` was called OUTSIDE its
    `try`, so a failure there became a 500 on the signup, AFTER the guest
    session was already revoked and committed. The caller lost their
    allowance, got no account, and a retry hit 409 on an email that was by
    then taken.

    Nothing asserted the property the docstring claimed, which is why the
    gap survived. This asserts it: authentication is the primary
    operation, migration is best-effort, so a raising reassignment must
    leave signup at 201 and must still leave the guest session revoked.
    """
    from system_03_search_agent.core import run_registry as run_registry_module

    def _boom(**_kwargs):
        raise RuntimeError("dictionary changed size during iteration")

    monkeypatch.setattr(
        run_registry_module.default_registry, "reassign_owner", _boom
    )

    guest_id, guest_token = _mint_guest(client)
    email = _unique_email()
    response = client.post(
        "/auth/signup",
        json={"email": email, "password": "Str0ngPassw0rd!", "guest_token": guest_token},
    )

    assert response.status_code == 201, (
        "a failure inside the best-effort migration must never fail the signup "
        "it was attached to"
    )
    row = _guest_session_row(guest_id)
    assert row is not None
    assert row.revoked_at is not None, (
        "the revocation committed before the reassignment ran; swallowing the "
        "reassignment failure must not also roll that back"
    )


def test_login_still_succeeds_when_the_run_reassignment_raises(client, monkeypatch):
    """F-4.10-J-03, the other caller. `login` reaches the same
    best-effort helper and had the same exposure."""
    from system_03_search_agent.core import run_registry as run_registry_module

    def _boom(**_kwargs):
        raise RuntimeError("dictionary changed size during iteration")

    email, password, _ = _signup_and_login(client)
    _guest_id, guest_token = _mint_guest(client)
    monkeypatch.setattr(
        run_registry_module.default_registry, "reassign_owner", _boom
    )

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password, "guest_token": guest_token},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# F-4.6-J-01: signup also migrates the rows the guest already captured.
# ---------------------------------------------------------------------------


def _plant_interaction(owner_id: str) -> str:
    """One captured `interactions` row owned by `owner_id`.

    Written through the real `write_interaction`, not by hand, so this arm
    is migrating the same shape of row capture actually produces.
    """
    import asyncio

    from system_03_search_agent.feedback.contracts import InteractionRow
    from system_03_search_agent.feedback.writer import write_interaction

    trace_id = f"auth-migrate-{uuid.uuid4().hex[:12]}"
    asyncio.run(
        write_interaction(
            InteractionRow(
                trace_id=trace_id,
                user_id=None,
                session_id=None,
                owner_id=owner_id,
                query_text="What is BRCA1?",
                query_class="lookup",
                route={},
                trust_signal="answer",
                rubric_outcome="pass",
                cost_usd=0.01,
                latency_ms=250,
            )
        )
    )
    return trace_id


def _interaction_owner(trace_id: str):
    engine = sa.create_engine(USER_DB_URL, future=True)
    try:
        with engine.connect() as conn:
            return conn.execute(
                sa.text(
                    "SELECT owner_id, user_id, user_feedback FROM interactions "
                    "WHERE trace_id = :tid"
                ),
                {"tid": trace_id},
            ).one()
    finally:
        engine.dispose()


def test_signup_migrates_the_guests_already_captured_interactions(client):
    """F-4.6-J-01, end to end through the endpoint the user actually hits.

    Ownership of a run is recorded in two places, `RunEntry.owner_id` in the
    registry and `interactions.owner_id` in the database, and the feedback
    endpoint checks both. Signup used to migrate only the first, so a guest
    who signed up and then rated the answer they had just watched stream got
    HTTP 403 "you do not own this run" and their rating was silently
    discarded. Build phase 4.10 shipped the anonymous run path precisely so
    someone can use the product before creating an account, which makes
    signing up after a good answer the conversion path this breaks.

    Mutation: delete the `reassign_interaction_owner(...)` call from
    `auth/router.py::_migrate_guest_session`. Ran it. This test goes red on
    the `owner_id` assertion, and `record_feedback` below then raises
    `FeedbackOwnershipError`, which is the 403 the user saw."""
    import asyncio

    from system_03_search_agent.feedback import record_feedback

    guest_id, guest_token = _mint_guest(client)
    trace_id = _plant_interaction(f"guest:{guest_id}")
    assert _interaction_owner(trace_id).owner_id == f"guest:{guest_id}"

    response = client.post(
        "/auth/signup",
        json={
            "email": _unique_email(),
            "password": "Str0ngPassw0rd!",
            "guest_token": guest_token,
        },
    )
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]

    migrated = _interaction_owner(trace_id)
    assert migrated.owner_id == f"user:{user_id}", (
        "the captured row still names the revoked guest, so the new account "
        "is refused feedback on the answer it just watched (F-4.6-J-01)"
    )
    assert str(migrated.user_id) == user_id, (
        "interactions.user_id stayed NULL, so the new account's daily query "
        "cap will never count the queries it just inherited"
    )

    asyncio.run(
        record_feedback(trace_id=trace_id, owner_id=f"user:{user_id}", rating="up")
    )
    assert _interaction_owner(trace_id).user_feedback["rating"] == "up"


def test_signup_does_not_migrate_another_guests_interactions(client):
    """The F-4.5-A-02 guard at the endpoint: the migration is scoped to the
    guest identity decoded out of the presented token and to no other.

    Mutation: pass `old_owner_id="guest:%"` to
    `reassign_interaction_owner` from `auth/router.py`. Ran it. Both arms in
    this section go red, and NOT where predicted: the `WHERE` clause is
    exact equality rather than a pattern match, so `"guest:%"` matches
    nothing at all and the failure is the migrating guest's OWN row staying
    put, not a bystander's row moving. Recorded rather than smoothed over,
    because it says something about the fix worth keeping: over-matching is
    not reachable from this call site, and the only place it could be
    introduced is the `WHERE` clause itself, which
    `feedback/test_writer.py::test_a_migration_never_touches_another_
    principals_row` grades directly."""
    mine_id, mine_token = _mint_guest(client)
    theirs_id, _theirs_token = _mint_guest(client)
    mine_trace = _plant_interaction(f"guest:{mine_id}")
    theirs_trace = _plant_interaction(f"guest:{theirs_id}")

    response = client.post(
        "/auth/signup",
        json={
            "email": _unique_email(),
            "password": "Str0ngPassw0rd!",
            "guest_token": mine_token,
        },
    )
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]

    assert _interaction_owner(mine_trace).owner_id == f"user:{user_id}"
    assert _interaction_owner(theirs_trace).owner_id == f"guest:{theirs_id}", (
        "a bystanding guest's captured row was handed to the migrating account"
    )
