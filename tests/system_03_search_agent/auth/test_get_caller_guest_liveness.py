"""F-4.13-A-01's fix: `get_caller`'s guest branch now refuses a revoked or
unknown `guest_sessions` identity, for EVERY route that depends on it, not
only `GET /v1/allowance` and `POST /v1/query`.

## Why this file exists rather than extending an existing premise gate

Build phase 4.10's premise gate (`test_phase_4_10_premise.py`) already
proves a migrated guest token cannot keep spending, and proves it against
`POST /v1/query` and `GET /v1/allowance` specifically, the two routes that
had their OWN inline liveness check before this fix. Build phase 4.13's
premise gate (`test_phase_4_13_premise.py`) is the phase contract for
`GET /v1/history` and this fix's brief permits exactly one edit to it
(F-4.13-J-02's failure-message correction), not a new arm. Neither file is
the right place to prove the CLASS fix: that liveness is now enforced in
`get_caller` itself, reaching routes that never had a liveness check of
their own before this fix and were never covered by either premise gate.
This file proves exactly that, against real routes over a real database,
reproducing the adversary's and judge's own repro steps
(`tracker/phase_4.13.md`, F-4.13-A-01) as an executable regression rather
than leaving the fix's evidence only in a hand-run script.

## What this file covers

- `GET /v1/history`, the route the finding was raised against: a guest
  token that decodes but whose session was migrated at signup no longer
  gets 200 with that guest's rows (the adversary's reproduction:
  `GET /v1/history -> 200 {"items": [...ghost row...]}` against a REVOKED
  credential). It gets 401 with the same structured
  `guest_session_revoked` reason `GET /v1/allowance` already used.
- `GET /v1/query/{run_id}/events`, one of the five routes the finding
  named as having ZERO references to `GuestSession` before this fix
  (`get_v1_query_events`), reached with a run created before the guest's
  session was revoked, so the only thing standing between 401 and a
  200/404 is `get_caller`'s new check.
- A guest id with no `guest_sessions` row at all (never migrated, never
  existed) is refused the same way on `GET /v1/history`, matching
  `test_streaming_endpoints.py`'s existing coverage of the identical shape
  against `GET /v1/allowance`.
- An account `Principal` reaching `GET /v1/history` is unaffected: this
  fix's guest-only branch must never touch, or refuse on, an account
  caller.

## What this file deliberately does NOT cover

- `POST /v1/query` and `GET /v1/allowance` themselves: already covered by
  build phase 4.10's premise gate, unchanged by this fix (see
  `auth/dependencies.py`'s comments on why their own inline checks are
  kept as defense in depth rather than removed).
- `POST /v1/query/{run_id}/stop`, `GET /v1/query/{run_id}/citations` and
  `POST /v1/query/{run_id}/feedback`, the other three previously-uncovered
  routes: they resolve the caller through the identical `Depends(get_caller)`
  as `GET /v1/query/{run_id}/events`, so the mechanism proven against one
  run-scoped route is the same mechanism securing the rest. Not
  re-demonstrated per route to keep this file's runtime real-database
  cost proportionate to what it adds.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient

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


pytestmark = pytest.mark.skipif(
    not _can_connect(),
    reason=f"user database unreachable at {USER_DB_URL}; this fix is a real-database check",
)

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module

_TEST_AUTH_KEY = "test-only-value-for-f-4-13-a-01-guest-liveness-fix-do-not-reuse"


@pytest.fixture(autouse=True)
def _harness_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("ANON_DAILY_RUN_CAP", "10000")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch):
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


@pytest.fixture(autouse=True)
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672"}

    async def _fake_resolve_symbol_to_curie(symbol: str, **kwargs: object) -> str | None:
        return known.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _fake_resolve_symbol_to_curie)


@pytest.fixture(autouse=True)
def _stub_ncbi_efetch_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import graph as graph_module
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput

    async def _fake_ncbi_efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty",
            action="dataset_report",
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _fake_ncbi_efetch)


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cost_control, "check_user_daily_query_cap", lambda session, user_id, **kw: None
    )
    monkeypatch.setattr(cost_control, "check_system_daily_cost_cap", lambda session, **kw: None)


@pytest.fixture(autouse=True)
def _auth_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_KEY)


@pytest.fixture(autouse=True)
def _reset_mint_throttle() -> None:
    from system_03_search_agent.auth import router as auth_router

    auth_router._mint_throttle._hits.clear()


def _client(source_host: str | None = None) -> AsyncClient:
    transport = (
        ASGITransport(app=app)
        if source_host is None
        else ASGITransport(app=app, client=(source_host, 123))
    )
    return AsyncClient(transport=transport, base_url="http://test")


def _unique_source() -> str:
    return f"203.0.113.{uuid.uuid4().hex}"


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


async def _drain_run_task(run_id: str) -> None:
    entry = run_registry_module.default_registry.get_run(run_id)
    await asyncio.wait_for(entry.task, timeout=30.0)


def _assert_revoked_401(response, label: str) -> None:
    assert response.status_code == 401, f"{label}: got {response.status_code} {response.text[:300]}"
    detail = response.json()["detail"]
    assert isinstance(detail, dict), f"{label}: a bare-string 401, not the structured reason"
    assert detail["reason"] == "guest_session_revoked", f"{label}: {detail}"
    assert detail["message"], f"{label}: the human-readable half was dropped"


class TestARevokedGuestSessionIsRefusedOnEveryRouteThroughGetCaller:
    @pytest.mark.asyncio
    async def test_history_refuses_the_migrated_guests_token_rather_than_serving_its_ghost_row(
        self,
    ) -> None:
        """The exact reproduction filed as F-4.13-A-01.

        Before this fix: `GET /v1/allowance -> 401 guest_session_revoked`
        while `GET /v1/history -> 200 {"items": [...]}` for the SAME
        credential, because `get_v1_history` never checked
        `guest_sessions` at all. Both must now agree.
        """
        async with _client(_unique_source()) as client:
            guest = await client.post("/auth/guest")
            assert guest.status_code == 201
            guest_token = guest.json()["guest_token"]
            guest_headers = {"Authorization": f"Bearer {guest_token}"}

            question = f"What gene is BRCA1? marker-{uuid.uuid4().hex[:12]}"
            created = await client.post(
                "/v1/query",
                json={"text": question, "session_id": f"session-{uuid.uuid4().hex[:8]}"},
                headers=guest_headers,
            )
            assert created.status_code == 202, created.text[:300]
            await _drain_run_task(created.json()["run_id"])

            # Before revocation: the control holds, the guest sees its own row.
            before = await client.get("/v1/history", headers=guest_headers)
            assert before.status_code == 200, before.text[:300]
            assert question in [item["question"] for item in before.json()["items"]], (
                "the control did not hold: the guest cannot see its own row "
                "before migration, so revocation proves nothing below"
            )

            # Migrate: signing up while holding the guest token revokes it
            # (build phase 4.10's `_migrate_guest_session`).
            email, password = _unique_email(), "Str0ngPassw0rd!"
            signup = await client.post(
                "/auth/signup",
                json={"email": email, "password": password, "guest_token": guest_token},
            )
            assert signup.status_code == 201, signup.text[:300]

            allowance = await client.get("/v1/allowance", headers=guest_headers)
            history = await client.get("/v1/history", headers=guest_headers)

        _assert_revoked_401(allowance, "GET /v1/allowance")
        _assert_revoked_401(history, "GET /v1/history")

    @pytest.mark.asyncio
    async def test_a_run_scoped_route_the_finding_named_uncovered_also_refuses(self) -> None:
        """`get_v1_query_events` is one of the five routes F-4.13-A-01's
        scope correction measured as having ZERO references to
        `GuestSession` before this fix. Reached with a run created BEFORE
        revocation, so the run genuinely exists and the only thing that
        can produce a 401 here is `get_caller`'s new check, not a 404.
        """
        async with _client(_unique_source()) as client:
            guest = await client.post("/auth/guest")
            assert guest.status_code == 201
            guest_token = guest.json()["guest_token"]
            guest_headers = {"Authorization": f"Bearer {guest_token}"}

            created = await client.post(
                "/v1/query",
                json={
                    "text": f"What gene is BRCA1? marker-{uuid.uuid4().hex[:12]}",
                    "session_id": f"session-{uuid.uuid4().hex[:8]}",
                },
                headers=guest_headers,
            )
            assert created.status_code == 202, created.text[:300]
            run_id = created.json()["run_id"]
            await _drain_run_task(run_id)

            email, password = _unique_email(), "Str0ngPassw0rd!"
            signup = await client.post(
                "/auth/signup",
                json={"email": email, "password": password, "guest_token": guest_token},
            )
            assert signup.status_code == 201, signup.text[:300]

            events = await client.get(f"/v1/query/{run_id}/events", headers=guest_headers)

        _assert_revoked_401(events, "GET /v1/query/{run_id}/events")

    @pytest.mark.asyncio
    async def test_an_unknown_guest_id_is_refused_on_history_too(self) -> None:
        """The second shape F-4.10-A-03 measured against `GET /v1/allowance`:
        a validly SIGNED guest token whose `guest_id` has no `guest_sessions`
        row at all. `GET /v1/history` must refuse it identically.
        """
        from system_03_search_agent.auth.guest import guest_signing_key

        orphan = jwt.encode(
            {
                "guest_id": str(uuid.uuid4()),
                "typ": "guest",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=1),
            },
            guest_signing_key(),
            algorithm="HS256",
        )
        headers = {"Authorization": f"Bearer {orphan}"}

        async with _client(_unique_source()) as client:
            history = await client.get("/v1/history", headers=headers)

        _assert_revoked_401(history, "GET /v1/history, unknown guest id")

    @pytest.mark.asyncio
    async def test_an_account_principal_is_unaffected_and_never_guest_gated(self) -> None:
        """The fix's guest-only branch must never touch an account caller."""
        async with _client(_unique_source()) as client:
            email, password = _unique_email(), "Str0ngPassw0rd!"
            signup = await client.post(
                "/auth/signup", json={"email": email, "password": password}
            )
            assert signup.status_code == 201, signup.text[:300]
            login = await client.post("/auth/login", json={"email": email, "password": password})
            assert login.status_code == 200, login.text[:300]
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

            history = await client.get("/v1/history", headers=headers)

        assert history.status_code == 200, (
            f"an account principal must never be refused by the guest-liveness "
            f"check; got {history.status_code} {history.text[:300]}"
        )
