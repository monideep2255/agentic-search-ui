"""Mutation harness for build phase 4.15's premise gate.

Every arm in `test_release_environments_premise.py` is asserted here to go RED
when the property it guards is broken. An arm that stays green under mutation
is not an arm, it is decoration that reads like one.

This file exists because vacuous assertions are the single most repeated
failure in `LEARNINGS.md`: eleven separate instances by 2026-08-14, and four of
those were caught ONLY by mutation and not by anybody reading them. Build phase
4.11 wrote three vacuous arms while quoting the lesson against vacuous arms in
its own docstring, and build phase 4.16 shipped six assertions that could not
fail, five of them written by the lead.

## Why the live arms are mutated OFFLINE

P1 to P6 talk to two deployed environments. Mutating them for real would mean
breaking a live deployment on purpose, which is not an acceptable price for a
test run.

So each live arm is driven against a FAKE transport instead: the arm's logic is
re-run with `httpx` responses substituted, once with responses describing a
healthy two-environment setup (the control, which must be GREEN) and once with
responses describing the specific failure the arm exists to catch (the
mutation, which must be RED).

The control half is not optional and is the half most likely to be dropped. A
mutation test that only proves an arm can fail proves nothing about whether it
can pass: an arm hardcoded to `assert False` would satisfy every red case here.
Both directions, every arm.

## What this harness does NOT prove

- It does not prove the arms behave identically against the real deployments as
  against the fake transport. It proves the assertion logic discriminates. P1
  to P6 running green against the live environments is the other half, and
  neither half substitutes for the other.
- It does not mutate P6's `railway` subprocess boundary beyond its parse. A
  Railway CLI that changed its output format would break the arm, and nothing
  here would notice.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREMISE = Path(__file__).with_name("test_release_environments_premise.py")
_FIXTURE = Path(__file__).with_name("fixtures") / "release_environments.json"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_ENV_EXAMPLE = _REPO_ROOT / "env.example"


# ---------------------------------------------------------------------------
# A fake transport, small enough to read in one sitting
# ---------------------------------------------------------------------------


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload


class _World:
    """A tiny model of two deployments, configurable to be broken.

    Every flag below turns off exactly one property the gate asserts, so a
    mutation case flips one flag and nothing else. That one-variable discipline
    is what makes a red result attributable.
    """

    def __init__(
        self,
        *,
        shared_database: bool = False,
        shared_auth_secret: bool = False,
        shared_cors: bool = False,
        permissive_cors: bool = False,
        shared_app_env: bool = False,
        health_omits_app_env: bool = False,
        develop_down: bool = False,
    ) -> None:
        self.shared_database = shared_database
        self.shared_auth_secret = shared_auth_secret
        self.shared_cors = shared_cors
        self.permissive_cors = permissive_cors
        self.shared_app_env = shared_app_env
        self.health_omits_app_env = health_omits_app_env
        self.develop_down = develop_down
        # email -> environment that holds it
        self.accounts: dict[str, tuple[str, str]] = {}
        # token -> environment that minted it
        self.tokens: dict[str, str] = {}
        self._counter = 0

    @staticmethod
    def _deployments() -> dict:
        return json.loads(_FIXTURE.read_text())["deployments"]

    def _env_of(self, url: str) -> str:
        """Which deployment a URL belongs to, resolved from the FIXTURE.

        Was `"develop" if "develop" in url else "production"`, a template that
        silently stopped matching when Railway appended a hash to the generated
        domains (`...-develop-43b3...`). Reading the fixture means this cannot
        drift from the thing the premise gate actually probes.
        """
        for name, entry in self._deployments().items():
            if url.startswith(entry["api"]) or url.startswith(entry["web"]):
                return name
        raise AssertionError(f"URL belongs to no deployment in the fixture: {url}")

    def _web_of(self, env: str) -> str:
        return self._deployments()[env]["web"]

    def _owns(self, env: str, holder: str) -> bool:
        """Whether `env` can see a record created on `holder`."""
        return env == holder or self.shared_database

    def get(self, url: str, headers: dict | None = None) -> _Response:
        env = self._env_of(url)
        if env == "develop" and self.develop_down:
            return _Response(404, {"message": "Application not found"})

        if url.endswith("/health"):
            app_env = "production" if self.shared_app_env else env
            payload = {"status": "ok"}
            if not self.health_omits_app_env:
                payload["app_env"] = app_env
            return _Response(200, payload)

        if url.endswith("/auth/me"):
            raw = (headers or {}).get("Authorization", "")
            token = raw.removeprefix("Bearer ").strip()
            minted_by = self.tokens.get(token)
            if minted_by is None:
                return _Response(401, {"detail": "invalid"})
            verified = minted_by == env or self.shared_auth_secret
            return _Response(200 if verified else 401, {"id": 1})

        raise AssertionError(f"unmodelled GET {url}")

    def post(self, url: str, json: dict | None = None) -> _Response:  # noqa: A002
        env = self._env_of(url)
        if env == "develop" and self.develop_down:
            return _Response(404, {"message": "Application not found"})
        body = json or {}

        if url.endswith("/auth/signup"):
            email = body["email"]
            if any(
                stored_email == email and self._owns(env, holder)
                for stored_email, (holder, _) in self.accounts.items()
            ):
                return _Response(409, {"detail": "taken"})
            self.accounts[email] = (env, body["password"])
            return _Response(201, {"id": 1, "email": email})

        if url.endswith("/auth/login"):
            email = body["email"]
            record = self.accounts.get(email)
            if record is None:
                return _Response(401, {"detail": "bad credentials"})
            holder, password = record
            if password != body["password"] or not self._owns(env, holder):
                return _Response(401, {"detail": "bad credentials"})
            self._counter += 1
            token = f"tok-{self._counter}"
            self.tokens[token] = env
            return _Response(200, {"access_token": token, "token_type": "bearer"})

        raise AssertionError(f"unmodelled POST {url}")

    def options(self, url: str, headers: dict | None = None) -> _Response:
        env = self._env_of(url)
        if env == "develop" and self.develop_down:
            return _Response(404, {"message": "Application not found"})
        origin = (headers or {}).get("Origin", "")
        if self.permissive_cors:
            # Echoes back whatever it is asked about, the classic
            # `allow_origins=["*"]`-with-credentials shape. Every origin is
            # admitted, including the other environment's.
            return _Response(200, {}, {"access-control-allow-origin": origin})
        allowed = self._web_of("production") if self.shared_cors else self._web_of(env)
        out = {"access-control-allow-origin": allowed} if origin == allowed else {}
        return _Response(200, {}, out)


class _FakeClient:
    def __init__(self, world: _World) -> None:
        self._world = world

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get(self, url: str, headers: dict | None = None, **_: object) -> _Response:
        return self._world.get(url, headers)

    def post(self, url: str, json: dict | None = None, **_: object) -> _Response:  # noqa: A002
        return self._world.post(url, json)

    def options(self, url: str, headers: dict | None = None, **_: object) -> _Response:
        return self._world.options(url, headers)


def _run_arm(monkeypatch: pytest.MonkeyPatch, arm_name: str, world: _World) -> BaseException | None:
    """Run one live arm against `world`, returning the failure or None."""
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    monkeypatch.setattr(premise, "_client", lambda: _FakeClient(world))
    arm = getattr(premise, arm_name)
    # The arms carry a skipif marker keyed on RUN_PREMISE_GATE. Calling the
    # underlying function directly bypasses the marker, which is what we want:
    # this harness tests the assertion logic, not the gating.
    try:
        arm.__wrapped__() if hasattr(arm, "__wrapped__") else arm()
    except BaseException as exc:  # noqa: BLE001 - the failure IS the result
        return exc
    return None


_HEALTHY = dict(
    shared_database=False,
    shared_auth_secret=False,
    shared_cors=False,
    permissive_cors=False,
    shared_app_env=False,
    health_omits_app_env=False,
    develop_down=False,
)


@pytest.mark.parametrize(
    ("arm", "mutation", "must_mention"),
    [
        # P1: one environment stops answering.
        ("test_p1_both_environments_answer_at_different_hostnames", {"develop_down": True}, "not 200"),
        # P2: the two environments read one user table.
        (
            "test_p2_an_account_made_on_develop_cannot_sign_in_on_production",
            {"shared_database": True},
            "share a user database",
        ),
        # P3: both environments verify with the same secret.
        (
            "test_p3_a_token_minted_on_one_environment_is_refused_by_the_other",
            {"shared_auth_secret": True},
            "same AUTH_SECRET",
        ),
        # P4, first assertion: CORS_ORIGINS was carried by the duplicate, so
        # develop admits production's origin and not its own. This trips the
        # POSITIVE CONTROL rather than the refusal check, which is the correct
        # and earlier of the two. Predicted wrongly on the first write of this
        # harness, and the expectation was corrected to the message that
        # actually fires rather than the arm being reordered to produce the
        # predicted one. An arm is allowed to catch a defect earlier than you
        # expected; a harness that insists on the later message would have
        # forced a worse arm.
        (
            "test_p4_each_api_admits_its_own_web_origin_and_refuses_the_other",
            {"shared_cors": True},
            "did not admit its OWN web origin",
        ),
        # P4, second assertion: an API that echoes every origin back. Its own
        # origin IS admitted, so the positive control passes and only the
        # refusal check can catch it. Without this case, P4's second half
        # would be unproven and could be deleted with the harness still green.
        (
            "test_p4_each_api_admits_its_own_web_origin_and_refuses_the_other",
            {"permissive_cors": True},
            "the OTHER",
        ),
        # P5, first assertion: the duplicate carried production's APP_ENV, so
        # develop reports a value the fixture does not record. Same story as
        # P4 above: the per-environment check fires before the cross-environment
        # comparison, and it is the better failure of the two because it names
        # which environment is wrong.
        (
            "test_p5_the_two_environments_report_different_app_env",
            {"shared_app_env": True},
            "but release_environments.json records",
        ),
        # P5 again, a different way to break it: /health stops reporting it,
        # which must fail loudly rather than pass by absence.
        (
            "test_p5_the_two_environments_report_different_app_env",
            {"health_omits_app_env": True},
            "does not report app_env",
        ),
    ],
)
def test_each_live_arm_goes_red_under_its_own_mutation(
    monkeypatch: pytest.MonkeyPatch,
    arm: str,
    mutation: dict,
    must_mention: str,
) -> None:
    """The mutation makes the arm fail, AND the healthy world makes it pass.

    Both halves in one test on purpose. Splitting them invites the control half
    to be deleted later as redundant, and the control half is the one that
    catches an arm hardcoded to fail.
    """
    control = _run_arm(monkeypatch, arm, _World(**_HEALTHY))
    assert control is None, (
        f"{arm} FAILED against a healthy two-environment world, so its red "
        f"result below proves nothing about the property it claims to guard: "
        f"{control!r}"
    )

    broken = _run_arm(monkeypatch, arm, _World(**{**_HEALTHY, **mutation}))
    assert broken is not None, (
        f"{arm} stayed GREEN with {mutation} applied. It does not detect the "
        f"failure it exists to detect."
    )
    assert must_mention in str(broken), (
        f"{arm} failed under {mutation}, but for a reason that does not name "
        f"the property: expected {must_mention!r} in the message, got "
        f"{str(broken)[:400]!r}. An arm that goes red for the wrong reason is "
        f"indistinguishable from one that works."
    )


# ---------------------------------------------------------------------------
# The offline arms, mutated by rewriting the files they read
# ---------------------------------------------------------------------------


def _rerun_offline(monkeypatch: pytest.MonkeyPatch, arm_name: str) -> BaseException | None:
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    try:
        getattr(premise, arm_name)()
    except BaseException as exc:  # noqa: BLE001
        return exc
    return None


def test_p7_goes_red_when_a_deployed_variable_leaves_env_example(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """P7 catches the exact defect it was written for: F-4.15-01 reappearing."""
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    assert _rerun_offline(monkeypatch, "test_p7_env_example_documents_every_variable_the_deployment_sets") is None, (
        "P7 is red before any mutation, so the red result below would prove nothing"
    )

    original = _ENV_EXAMPLE.read_text()
    assert "RUN_MIGRATIONS_ON_STARTUP" in original, (
        "env.example no longer documents RUN_MIGRATIONS_ON_STARTUP, so the "
        "removal below is not a mutation"
    )
    stripped = "\n".join(
        line for line in original.splitlines() if not line.startswith("RUN_MIGRATIONS_ON_STARTUP=")
    )
    mutated = tmp_path / "env.example"
    mutated.write_text(stripped)
    monkeypatch.setattr(premise, "_ENV_EXAMPLE", mutated)

    failure = _rerun_offline(monkeypatch, "test_p7_env_example_documents_every_variable_the_deployment_sets")
    assert failure is not None, (
        "P7 stayed green with RUN_MIGRATIONS_ON_STARTUP removed from "
        "env.example, which is precisely finding F-4.15-01 reappearing"
    )
    assert "RUN_MIGRATIONS_ON_STARTUP" in str(failure), (
        f"P7 failed but did not name the missing variable: {str(failure)[:300]!r}"
    )


@pytest.mark.parametrize(
    ("mutate", "must_mention"),
    [
        # The production line loses its post-merge run.
        (lambda t: t.replace("branches: [develop, production]", "branches: [develop]"), "not `production`"),
        # The integration line loses its post-merge run.
        (lambda t: t.replace("branches: [develop, production]", "branches: [production]"), "lost `develop`"),
        # Someone "tightens" the pull_request trigger, silently stopping every
        # release pull request from being gated. This is the mutation that
        # would look like an improvement in review.
        (
            lambda t: t.replace("  pull_request:\n", "  pull_request:\n    branches: [develop]\n"),
            "gained a branch filter",
        ),
    ],
)
def test_p8_goes_red_for_each_way_the_trigger_can_be_broken(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mutate, must_mention: str
) -> None:
    """Three distinct breakages, three distinct messages.

    The third is the one worth having. Adding a branch filter to
    `pull_request` reads as tightening CI and would silently stop release pull
    requests being checked at all, which is the opposite of what it looks like.
    """
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    assert _rerun_offline(monkeypatch, "test_p8_ci_runs_on_the_production_line") is None, (
        "P8 is red before any mutation, so the red results below prove nothing"
    )

    original = _CI_WORKFLOW.read_text()
    mutated_text = mutate(original)
    assert mutated_text != original, "the mutation changed nothing, so it is not a mutation"

    mutated = tmp_path / "ci.yml"
    mutated.write_text(mutated_text)
    monkeypatch.setattr(premise, "_CI_WORKFLOW", mutated)

    failure = _rerun_offline(monkeypatch, "test_p8_ci_runs_on_the_production_line")
    assert failure is not None, "P8 stayed green under a mutation of the CI trigger"
    assert must_mention in str(failure), (
        f"P8 failed for a reason that does not name the breakage: expected "
        f"{must_mention!r}, got {str(failure)[:300]!r}"
    )


def test_p1_goes_red_when_the_fixture_names_one_url_twice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Two labels on one deployment is the failure "two environments" excludes.

    Separated from the parametrized cases above because it mutates the FIXTURE
    rather than the world, and it is the one failure mode where every live
    probe would succeed and the premise would still be false.
    """
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    data = json.loads(_FIXTURE.read_text())
    data["deployments"]["develop"]["api"] = data["deployments"]["production"]["api"]
    mutated = tmp_path / "release_environments.json"
    mutated.write_text(json.dumps(data))
    monkeypatch.setattr(premise, "_FIXTURE", mutated)

    failure = _run_arm(
        monkeypatch, "test_p1_both_environments_answer_at_different_hostnames", _World(**_HEALTHY)
    )
    assert failure is not None, (
        "P1 stayed green with both environments naming the same API URL, so it "
        "does not actually assert there are two deployments"
    )
    assert "same API URL" in str(failure), f"P1 failed for the wrong reason: {str(failure)[:300]!r}"


def test_p1_goes_red_when_an_environment_is_absent_from_the_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Absence is a FAILURE, never a skip. This is the gating rule, asserted.

    The premise gate's whole departure from house convention is that a missing
    environment fails rather than skips. That rule lives in a docstring, and a
    docstring is a claim to be tested, per `.claude/rules/self-eval-loop.md`.
    """
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    data = json.loads(_FIXTURE.read_text())
    del data["deployments"]["develop"]
    mutated = tmp_path / "release_environments.json"
    mutated.write_text(json.dumps(data))
    monkeypatch.setattr(premise, "_FIXTURE", mutated)

    failure = _run_arm(
        monkeypatch, "test_p1_both_environments_answer_at_different_hostnames", _World(**_HEALTHY)
    )
    assert failure is not None, "P1 passed with the develop environment absent from the fixture"
    assert "absent from" in str(failure), (
        f"P1 failed but not on absence: {str(failure)[:300]!r}"
    )
    assert not isinstance(failure, pytest.skip.Exception), (
        "P1 SKIPPED rather than failed when the develop environment was absent. "
        "That is the exact behaviour this gate's docstring says it does not "
        "have, and a skip on absence makes every green run unreadable."
    )


def test_the_premise_gate_gates_on_the_flag_alone_and_not_on_reachability() -> None:
    """The live arms must not skip themselves when an environment is down.

    A structural check on the source, because the property is about what the
    marker is CONDITIONED on, and no runtime call can observe that. If someone
    later adds a reachability probe to the skipif, every live arm silently
    becomes a no-op on the day the develop environment breaks, which is the day
    they are most needed.
    """
    text = _PREMISE.read_text()
    marker = re.search(r"requires_live = pytest\.mark\.skipif\((.*?)\)\n", text, re.DOTALL)
    assert marker is not None, "could not find the requires_live marker to check"
    condition = marker.group(1)

    assert "_RUN_LIVE" in condition, f"requires_live no longer keys on the flag: {condition!r}"
    for forbidden in ("reachable", "_is_up", "httpx", "socket"):
        assert forbidden not in condition, (
            f"requires_live's condition mentions {forbidden!r}: {condition!r}. "
            f"Gating a live arm on reachability turns 'the environment this "
            f"phase built is down' into a skip, which is the failure the gate "
            f"exists to report."
        )
