"""Build phase 4.10 premise gate: `tracker/phase_4.10.md`.

The done-when this file pins, in one sentence:

    A caller the server has never seen can complete five real, cited runs
    without an account, the server alone decides when the fifth is spent,
    and no guest can read, stop, or spend another caller's runs.

## Why this gate has two arms

This is a guardrail-shaped phase, the same shape as build phase 3.0's, and
a guardrail has no safe direction of failure. `return 401` scores one
hundred percent on every attack test that will ever be written against
this file and destroys the product, because the whole point of the phase
is that a visitor with no account can use the thing. Admitting every
caller passes every admission test and gives the system away.

Only one of those two failures is caught by an attack test. So the ADMIT
arm below is written first and is not decoration: `TestAdmitArm` failing
is exactly as much a gate failure as `TestRefuseArm` failing, and a fix
that makes the refuse arm greener by making the admit arm redder has not
fixed anything.

## What this gate covers

Admit:

- A caller with no account, no cookie and no prior state mints a guest
  identity and completes a real run end to end.
- Runs two through five also succeed, so the allowance is five and not one.
- The server's own reported count rises by exactly one per run, which is
  what makes the five dots in the UI truthful rather than decorative.
- Signing up while holding a guest token moves that guest's runs to the
  new account.

Refuse:

- The sixth run is refused, and refused with a reason a client can branch
  on rather than a bare failure.
- A tampered guest token, a guest token signed with `AUTH_SECRET`
  directly rather than the derived key, and an expired one are each
  rejected.
- Token confusion in both directions: a guest token is not an access
  token, and an access token is not a guest token.
- Cross-guest isolation on all three run-scoped endpoints (events, stop,
  citations).
- The allowance survives concurrency. Six simultaneous requests at the
  boundary yield at most five successes, which is the property a
  read-then-write implementation silently fails.
- A guest whose session was migrated at signup cannot keep spending on
  the old token.
- A guest is never an operator, so no guest is ever streamed a `cost`
  event.

Documented, accepted behaviour, asserted here so it is on the record
rather than discovered later by someone who assumes it is a bug:

- Clearing the guest token and minting a fresh one yields a fresh
  allowance. Product-owner decision, 2026-08-14, taken with a prototype
  mindset and with the consequence understood.

## What this gate deliberately does NOT cover

Per `goal-contracts.md`'s coverage-declaration discipline, and because
build phase 2.1's gate had a blind spot identical to the code it graded:

- Durable, cross-reload run history. Nothing persists a run today: the
  `RunRegistry` is in-memory and evicts, and the browser's history list is
  React state. This gate asserts that a guest's LIVE runs move at signup,
  which is what actually exists. Build phase 4.6 owns the rest, and
  F-4.10-01 records that the wall's copy overstated it.
- Multi-process or multi-worker counting. The run registry is per-process,
  so a two-worker deployment is outside anything this file can observe.
  The `guest_sessions` counter is the one piece that would survive it, and
  the concurrency arm exercises it only within one process.
- Device-level or IP-level abuse resistance. The clearable-token decision
  declines it on purpose, so there is nothing here to test.
- The registered 100/day cap actually firing. It cannot: nothing writes
  `interactions` rows (F-2.0-04, build phase 4.6), so the counter reads a
  structural zero. This gate asserts the allowance endpoint reports that
  honestly rather than presenting an uncounted zero as a count.
- Real Layer 1 answers. The graph tunnel cannot be opened from a sandboxed
  session (T-3.0-07), so the agent loop runs against the same stubbed
  harness every other endpoint test in this directory uses. What is under
  test here is who may start a run and how many, not what the run answers.

## How it runs

The same two fixture styles as `test_phase_4_0_premise.py`: the real
FastAPI app over `httpx.AsyncClient` + `ASGITransport`, against a real
`search_agent_users` PostgreSQL, skipping cleanly rather than failing when
that database is unreachable. Every import of a module this phase has not
built yet is deliberately made INSIDE the test that needs it, so each arm
fails on its own and the failure list is a work list, rather than one
collection error hiding eleven of twelve arms.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

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
    reason=f"user database unreachable at {USER_DB_URL}; the guest allowance is a server-side count",
)

from system_03_search_agent.adapters.web_sse.app import app
from system_03_search_agent.core import run_registry as run_registry_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module

_TEST_AUTH_SECRET = "test-only-auth-secret-for-phase-4-10-premise-tests-do-not-reuse"

# The allowance the approved design calls for, and the number the five dots
# in `components/guest/GuestAllowance.tsx` render. Stated here as the gate's
# own expectation rather than imported from the implementation: a gate that
# reads its expected value out of the code it grades cannot catch that value
# being wrong.
_EXPECTED_FREE_SEARCHES = 5


# ---------------------------------------------------------------------------
# Fixtures. Identical in intent to test_phase_4_0_premise.py's: the agent
# loop is stubbed because what is under test is admission, not answers.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _harness_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")


@pytest.fixture(autouse=True)
def _mock_litellm(monkeypatch: pytest.MonkeyPatch):
    from tests.system_03_search_agent.model_stub import install_dispatching_acompletion

    return install_dispatching_acompletion(monkeypatch, harness_module)


@pytest.fixture(autouse=True)
def _stub_symbol_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from system_03_search_agent.core import graph as graph_module

    known = {"BRCA1": "NCBIGene:672", "TP53": "NCBIGene:7157"}

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
def _auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_SECRET", _TEST_AUTH_SECRET)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _unique_email() -> str:
    return f"{uuid.uuid4()}@example.com"


def _create_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {"text": "What gene is BRCA1?", "session_id": "session-1"}
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
# Helpers that describe the interface this phase must build. The gate is
# written before the code, so these ARE the contract, not a reading of it.
# ---------------------------------------------------------------------------


async def _mint_guest(client: AsyncClient) -> tuple[str, dict[str, str]]:
    """`POST /auth/guest`: no body, no credentials, a guest identity back.

    Returns the guest id and the Authorization headers a guest calls with.
    """
    response = await client.post("/auth/guest")
    assert response.status_code == 201, (
        f"a first-time visitor must be able to mint a guest identity; got "
        f"{response.status_code} {response.text[:200]}"
    )
    body = response.json()
    assert body["total"] == _EXPECTED_FREE_SEARCHES
    assert body["used"] == 0
    return body["guest_id"], {"Authorization": f"Bearer {body['guest_token']}"}


async def _auth_headers(
    client: AsyncClient, *, guest_token: str | None = None
) -> tuple[str, dict[str, str]]:
    """Sign up and log in, optionally carrying a guest session to migrate."""
    email, password = _unique_email(), "Str0ngPassw0rd!"
    payload: dict[str, object] = {"email": email, "password": password}
    if guest_token is not None:
        payload["guest_token"] = guest_token
    signup = await client.post("/auth/signup", json=payload)
    assert signup.status_code == 201, signup.text[:200]
    user_id = signup.json()["id"]
    login = await client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text[:200]
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _run(client: AsyncClient, headers: dict[str, str]):
    return await client.post("/v1/query", json=_create_body(), headers=headers)


async def _drain_run_task(run_id: str) -> None:
    entry = run_registry_module.default_registry.get_run(run_id)
    await asyncio.wait_for(entry.task, timeout=10.0)


def _token_of(headers: dict[str, str]) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


# ---------------------------------------------------------------------------
# ARM ONE: ADMIT. The product exists because of these.
# ---------------------------------------------------------------------------


class TestAdmitArm:
    """A visitor with no account can actually use the product.

    Every assertion here fails today, because all four `/v1/query`
    endpoints return 401 without a bearer token and no guest path exists
    anywhere in `src/`. That is the point of writing it first.
    """

    @pytest.mark.asyncio
    async def test_a_visitor_with_no_account_completes_a_real_run(self) -> None:
        async with _client() as client:
            _guest_id, headers = await _mint_guest(client)

            created = await _run(client, headers)
            assert created.status_code == 202, (
                "an anonymous visitor must be able to start a run; this is the "
                "whole reason build phase 4.10 was pulled ahead of 4.2"
            )
            run_id = created.json()["run_id"]
            await _drain_run_task(run_id)

            events = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            assert events.status_code == 200, "a guest must be able to read its own run's stream"

            citations = await client.get(f"/v1/query/{run_id}/citations", headers=headers)
            assert citations.status_code == 200, "a guest must be able to export its own citations"

    @pytest.mark.asyncio
    async def test_the_allowance_is_five_runs_not_one(self) -> None:
        async with _client() as client:
            _guest_id, headers = await _mint_guest(client)
            for attempt in range(_EXPECTED_FREE_SEARCHES):
                created = await _run(client, headers)
                assert created.status_code == 202, (
                    f"run {attempt + 1} of {_EXPECTED_FREE_SEARCHES} was refused; the "
                    f"allowance must be {_EXPECTED_FREE_SEARCHES}, not fewer"
                )
                await _drain_run_task(created.json()["run_id"])

    @pytest.mark.asyncio
    async def test_the_server_reported_count_rises_by_exactly_one_per_run(self) -> None:
        """What makes the five dots truthful rather than decorative.

        A client-side counter can render the same dots and be wrong the
        moment the page reloads. The count has to come from the server, and
        it has to be exact: off-by-one here is a visitor being told they
        have a search left when they do not, or the reverse.
        """
        async with _client() as client:
            _guest_id, headers = await _mint_guest(client)

            first = await client.get("/v1/allowance", headers=headers)
            assert first.status_code == 200
            assert first.json() == {
                "kind": "guest",
                "used": 0,
                "total": _EXPECTED_FREE_SEARCHES,
                "counted": True,
            }

            for expected_used in range(1, _EXPECTED_FREE_SEARCHES + 1):
                created = await _run(client, headers)
                assert created.status_code == 202
                await _drain_run_task(created.json()["run_id"])
                current = await client.get("/v1/allowance", headers=headers)
                assert current.status_code == 200
                assert current.json()["used"] == expected_used, (
                    "the server's own count must move in lockstep with the runs it "
                    "accepted, or the allowance shown to the user is a guess"
                )

    @pytest.mark.asyncio
    async def test_a_registered_caller_is_told_the_truth_about_its_own_limit(self) -> None:
        """F-4.9-A-16: the account menu says "unlimited searches" today.

        It is false against a shipped, enforced 100/day cap. It is also not
        the case that the honest answer is a number: nothing writes
        `interactions` rows (F-2.0-04), so the count is a structural zero,
        not a measured one. The endpoint must distinguish those, because
        rendering an uncounted zero as a count is the same dishonesty class
        as the client-side counter this phase removes.
        """
        async with _client() as client:
            _user_id, headers = await _auth_headers(client)
            allowance = await client.get("/v1/allowance", headers=headers)
            assert allowance.status_code == 200
            body = allowance.json()
            assert body["kind"] == "user"
            assert body["total"] == 100, "must be the real PER_USER_DAILY_QUERY_CAP, not 'unlimited'"
            assert body["counted"] is False, (
                "nothing writes interactions rows yet (F-2.0-04), so the count is "
                "structurally zero; the wire must say so rather than report a zero "
                "that reads as a measurement"
            )

    @pytest.mark.asyncio
    async def test_signing_up_moves_the_guest_runs_to_the_new_account(self) -> None:
        """Migration of what actually exists, per design decision 4.

        Not durable history. The guest's LIVE runs become the new user's
        runs, which is the honest subset of "your searches move with you".
        """
        async with _client() as client:
            _guest_id, guest_headers = await _mint_guest(client)
            created = await _run(client, guest_headers)
            assert created.status_code == 202
            run_id = created.json()["run_id"]
            await _drain_run_task(run_id)

            _user_id, user_headers = await _auth_headers(
                client, guest_token=_token_of(guest_headers)
            )

            moved = await client.get(f"/v1/query/{run_id}/citations", headers=user_headers)
            assert moved.status_code == 200, (
                "the run started as a guest must belong to the new account after "
                "signup; a 403 here means the migration did not happen"
            )


# ---------------------------------------------------------------------------
# ARM TWO: REFUSE. The system exists after these.
# ---------------------------------------------------------------------------


class TestRefuseArm:
    """Everything that must not be possible once the door is open."""

    @pytest.mark.asyncio
    async def test_the_sixth_run_is_refused_with_a_reason_a_client_can_branch_on(self) -> None:
        """403 rather than 429, deliberately.

        The allowance is spent, not rate limited: retrying later does not
        help, so a 429 with a `Retry-After` would be a lie the UI would
        then repeat to the user. The concurrent-run cap (F-4.0-A-10) is the
        genuinely transient condition and is the one that gets a 429.
        """
        async with _client() as client:
            _guest_id, headers = await _mint_guest(client)
            for _ in range(_EXPECTED_FREE_SEARCHES):
                created = await _run(client, headers)
                assert created.status_code == 202
                await _drain_run_task(created.json()["run_id"])

            refused = await _run(client, headers)
            assert refused.status_code == 403, (
                "the sixth run must be refused by the SERVER; a client-side "
                "counter is the dishonesty class build phase 4.8's judge filed"
            )
            body = refused.json()
            assert "guest_allowance_exhausted" in str(body), (
                "the refusal must carry a machine-readable reason so the UI shows "
                "the sign-in wall for this specific case rather than for any 403"
            )

    @pytest.mark.asyncio
    async def test_a_tampered_guest_token_is_rejected(self) -> None:
        async with _client() as client:
            _guest_id, headers = await _mint_guest(client)
            token = _token_of(headers)
            tampered = token[:-2] + ("ab" if not token.endswith("ab") else "cd")
            response = await _run(client, {"Authorization": f"Bearer {tampered}"})
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_a_guest_token_signed_with_auth_secret_directly_is_rejected(self) -> None:
        """Domain separation, design decision 1.

        The guest key is `HMAC-SHA256(AUTH_SECRET, b"guest-token-v1")`, not
        `AUTH_SECRET`. Anyone who can reach the access-token signing path
        must not thereby be able to mint guest identities, and the reverse.
        This test fails loudly if a later refactor "simplifies" the key
        derivation away.

        HONESTY NOTE, recorded at the moment the gate was watched failing:
        this is the ONE clause of seventeen that passed on the first run,
        and it passed VACUOUSLY. Every request is 401 today because no
        guest path exists at all, so the assertion cannot yet distinguish
        "domain separation works" from "nothing works". It becomes a real
        check the moment `POST /auth/guest` exists, and the judge should
        re-run it against a working guest path with the derivation
        deliberately replaced by bare `AUTH_SECRET`, and watch it go red,
        before crediting it. A clause that has never been seen failing for
        its own reason is not yet evidence of anything.
        """
        import jwt

        forged = jwt.encode(
            {
                "guest_id": str(uuid.uuid4()),
                "typ": "guest",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(days=1),
            },
            _TEST_AUTH_SECRET,
            algorithm="HS256",
        )
        async with _client() as client:
            response = await _run(client, {"Authorization": f"Bearer {forged}"})
            assert response.status_code == 401, (
                "a guest token must not be forgeable from AUTH_SECRET alone"
            )

    @pytest.mark.asyncio
    async def test_an_expired_guest_token_is_rejected(self) -> None:
        import jwt

        from system_03_search_agent.auth import guest as guest_module

        forged = jwt.encode(
            {
                "guest_id": str(uuid.uuid4()),
                "typ": "guest",
                "iat": datetime.now(UTC) - timedelta(days=30),
                "exp": datetime.now(UTC) - timedelta(days=1),
            },
            guest_module.guest_signing_key(),
            algorithm="HS256",
        )
        async with _client() as client:
            response = await _run(client, {"Authorization": f"Bearer {forged}"})
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_a_guest_token_is_not_an_access_token(self) -> None:
        """Token confusion, direction one.

        A guest presenting its token to a registered-only route must get
        the same 401 as any stranger, never a `users` row.
        """
        async with _client() as client:
            _guest_id, headers = await _mint_guest(client)
            response = await client.get("/auth/me", headers=headers)
            assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_an_access_token_is_not_a_guest_token(self) -> None:
        """Token confusion, direction two, checked at the primitive.

        Checked below the HTTP layer on purpose: `POST /v1/query` will
        accept both principal classes, so the endpoint cannot show that the
        two token types stay distinct. The decoder can.
        """
        from system_03_search_agent.auth.guest import decode_guest_token

        from system_03_search_agent.auth.tokens import mint_access_token

        access = mint_access_token(str(uuid.uuid4()))
        with pytest.raises(ValueError):
            decode_guest_token(access)

    @pytest.mark.asyncio
    async def test_a_guest_cannot_touch_another_guests_run(self) -> None:
        """All three run-scoped endpoints, not just the one that was easiest.

        `_get_owned_run` is shared, so a single check would look sufficient;
        it is asserted three times because a future change that special-cases
        one endpoint would otherwise pass.
        """
        async with _client() as client:
            _a_id, a_headers = await _mint_guest(client)
            _b_id, b_headers = await _mint_guest(client)

            created = await _run(client, a_headers)
            assert created.status_code == 202
            run_id = created.json()["run_id"]
            await _drain_run_task(run_id)

            for method, path in (
                ("get", f"/v1/query/{run_id}/events"),
                ("get", f"/v1/query/{run_id}/citations"),
                ("post", f"/v1/query/{run_id}/stop"),
            ):
                response = await getattr(client, method)(path, headers=b_headers)
                assert response.status_code == 403, (
                    f"guest B reached guest A's run via {method.upper()} {path}"
                )

    @pytest.mark.asyncio
    async def test_a_guest_cannot_touch_a_registered_users_run(self) -> None:
        async with _client() as client:
            _user_id, user_headers = await _auth_headers(client)
            _guest_id, guest_headers = await _mint_guest(client)

            created = await _run(client, user_headers)
            assert created.status_code == 202
            run_id = created.json()["run_id"]
            await _drain_run_task(run_id)

            response = await client.get(f"/v1/query/{run_id}/citations", headers=guest_headers)
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_the_allowance_holds_under_concurrency(self) -> None:
        """The property a read-then-write implementation silently fails.

        Two tabs, two simultaneous requests, both observing four used and
        both taking the fifth, is a six-search allowance available to anyone
        who can double-click. The spend must be one conditional UPDATE.
        """
        async with _client() as client:
            _guest_id, headers = await _mint_guest(client)
            responses = await asyncio.gather(
                *(_run(client, headers) for _ in range(_EXPECTED_FREE_SEARCHES + 1)),
                return_exceptions=True,
            )
            accepted = [r for r in responses if getattr(r, "status_code", None) == 202]
            assert len(accepted) <= _EXPECTED_FREE_SEARCHES, (
                f"{len(accepted)} of {_EXPECTED_FREE_SEARCHES + 1} concurrent requests were "
                f"accepted; the allowance is not being spent atomically"
            )
            for response in accepted:
                await _drain_run_task(response.json()["run_id"])

    @pytest.mark.asyncio
    async def test_a_migrated_guest_token_cannot_keep_spending(self) -> None:
        """Otherwise signup mints a second allowance rather than moving one."""
        async with _client() as client:
            _guest_id, guest_headers = await _mint_guest(client)
            created = await _run(client, guest_headers)
            assert created.status_code == 202
            await _drain_run_task(created.json()["run_id"])

            await _auth_headers(client, guest_token=_token_of(guest_headers))

            after = await _run(client, guest_headers)
            assert after.status_code in (401, 403), (
                "the guest session was migrated and revoked; its token must not "
                "start further runs"
            )

    @pytest.mark.asyncio
    async def test_a_guest_is_never_an_operator(self) -> None:
        """Section 19.4/19.5: cost data is internal-only.

        A guest has no `users` row, so `is_operator_user` is being asked
        about a principal that cannot be on any allowlist. The failure mode
        worth guarding is a namespaced owner id, or a `None`, being passed
        somewhere that treats an unrecognised value permissively.
        """
        async with _client() as client:
            _guest_id, headers = await _mint_guest(client)
            created = await _run(client, headers)
            assert created.status_code == 202
            run_id = created.json()["run_id"]
            await _drain_run_task(run_id)

            events = await client.get(f"/v1/query/{run_id}/events", headers=headers)
            assert events.status_code == 200
            assert "event: cost" not in events.text, (
                "a guest was streamed a cost event; cost and token usage are "
                "internal-only data"
            )


# ---------------------------------------------------------------------------
# Accepted behaviour, asserted so it is recorded rather than rediscovered.
# ---------------------------------------------------------------------------


class TestAcceptedBehaviour:
    @pytest.mark.asyncio
    async def test_clearing_the_guest_token_yields_a_fresh_allowance(self) -> None:
        """Product-owner decision, 2026-08-14, taken knowingly.

        A signed token in the browser is clearable, and anyone who clears it
        gets five more searches. This is asserted rather than left implicit
        so that a later reviewer reading it as a defect finds the decision
        attached to it, and so that anyone who decides to close it has to
        change a test that states the tradeoff out loud.

        Closing it would mean device or IP fingerprinting, which this
        product declined for a prototype.
        """
        async with _client() as client:
            _first_id, first_headers = await _mint_guest(client)
            for _ in range(_EXPECTED_FREE_SEARCHES):
                created = await _run(client, first_headers)
                assert created.status_code == 202
                await _drain_run_task(created.json()["run_id"])
            assert (await _run(client, first_headers)).status_code == 403

            _second_id, second_headers = await _mint_guest(client)
            fresh = await client.get("/v1/allowance", headers=second_headers)
            assert fresh.status_code == 200
            assert fresh.json()["used"] == 0
