"""Mutation harness for build phase 4.15's premise gate.

Each case here drives ONE arm of `test_release_environments_premise.py`,
breaks the property that arm guards, and asserts the arm goes RED. An arm that
stays green under mutation is not an arm, it is decoration that reads like one.

Note what that sentence does NOT say. It does not claim every arm has a case.
That claim was made twice in this file and was false both times, most recently
inside the fix for the finding that said so, and the account is under "AND THEN
THIS FILE DID IT TWICE" below.

This file exists because vacuous assertions are the single most repeated
failure in `LEARNINGS.md`: eleven separate instances by 2026-08-14, and four of
those were caught ONLY by mutation and not by anybody reading them. Build phase
4.11 wrote three vacuous arms while quoting the lesson against vacuous arms in
its own docstring, and build phase 4.16 shipped six assertions that could not
fail, five of them written by the lead.

AND THEN THIS FILE DID IT TWICE. The first version claimed every arm was
covered while P6 and P9 had none; a judge and an adversary filed that
independently as F-4.15-J-03 and F-4.15-A-15. The fix added those cases and
wrote a NEW completeness claim, which was also false, and which named P3b as
covered while P3b had no case. That was F-4.15-RV-01, found by a fresh
re-verifier inside the fix for the finding that said exactly this.

SO THERE IS NO COVERAGE CLAIM IN THIS DOCSTRING ANY MORE, and its absence is
deliberate rather than an oversight to be helpfully corrected. A sentence
asserting that every arm is covered is unverifiable by reading, goes stale the
moment an arm is added, and reads as permission to stop checking. Twice it did
exactly that. If you want to know which arms have cases, count them: the arms
are the `test_p*` functions in the premise gate, and the cases here name the
arm they drive in their own parameters.

The rule that replaces the claim: ADD THE CASE IN THE SAME EDIT AS THE ARM. An
arm added to close a finding, that cannot itself fail, has closed nothing.

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
import time
from pathlib import Path
from typing import Self

import jwt
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
        accepts_forged_signature: bool = False,
        shared_cors: bool = False,
        permissive_cors: bool = False,
        shared_app_env: bool = False,
        health_omits_app_env: bool = False,
        develop_down: bool = False,
    ) -> None:
        self.shared_database = shared_database
        self.shared_auth_secret = shared_auth_secret
        self.accepts_forged_signature = accepts_forged_signature
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
            if url.startswith((entry["api"], entry["web"])):
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
                # An unknown token is a forged or tampered one. A
                # deployment that skips signature verification takes it
                # anyway, which is what P3a exists to catch.
                if self.accepts_forged_signature:
                    return _Response(200, {"id": 1})
                return _Response(401, {"detail": "invalid"})
            verified = minted_by == env or self.shared_auth_secret
            return _Response(200 if verified else 401, {"id": 1})

        raise AssertionError(f"unmodelled GET {url}")

    def post(self, url: str, json: dict | None = None) -> _Response:
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
            # JWT SHAPED, three dot-separated base64url segments with a
            # signature long enough to tamper with in the middle. The fake
            # used to mint an opaque `tok-N`, which made P3a's own
            # structural assertion fail in the healthy control and so made
            # the mutation case unrunnable. A fake transport that cannot
            # satisfy the arm's preconditions cannot test the arm.
            token = f"aGVhZGVy.cGF5bG9hZA{self._counter}.c2lnbmF0dXJlYnl0ZXM{self._counter}"
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

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get(self, url: str, headers: dict | None = None, **_: object) -> _Response:
        return self._world.get(url, headers)

    def post(self, url: str, json: dict | None = None, **_: object) -> _Response:
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


_HEALTHY = {
    "shared_database": False,
    "shared_auth_secret": False,
    "accepts_forged_signature": False,
    "shared_cors": False,
    "permissive_cors": False,
    "shared_app_env": False,
    "health_omits_app_env": False,
    "develop_down": False,
}


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
        # P3a: a deployment that does not actually verify signatures. The
        # old P3 case went with the old arm: it asserted that a shared
        # signing key made the arm red, which was never true of the real
        # system (F-4.15-J-04). Its replacement tests what P3a really
        # holds, that a corrupted signature is rejected.
        (
            "test_p3a_each_deployment_actually_verifies_a_token_signature",
            {"accepts_forged_signature": True},
            "ACCEPTED a token whose signature was corrupted",
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


# ---------------------------------------------------------------------------
# P6, P7b and P9: the arms that had no mutation case at all
# ---------------------------------------------------------------------------
#
# Added 2026-08-27 after findings F-4.15-J-03 and F-4.15-A-15, filed
# independently by a judge and an adversary. This file's own docstring said
# "Every arm in test_release_environments_premise.py is asserted here to go RED
# when the property it guards is broken" while two of the nine arms had no case
# at all, so the harness made exactly the claim it exists to disprove. That is
# the same shape as a code comment asserting an untested property, and it is
# recorded rather than quietly filled in.
#
# P6, P7b and P9 all read something OUTSIDE the fake transport: two shell out to
# the Railway CLI, one reads the workflow file. They are mutated by substituting
# the boundary rather than by flipping a flag in `_World`.


def _run_named(monkeypatch: pytest.MonkeyPatch, arm_name: str) -> BaseException | None:
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    try:
        arm = getattr(premise, arm_name)
        arm.__wrapped__() if hasattr(arm, "__wrapped__") else arm()
    except BaseException as exc:  # noqa: BLE001 - the failure IS the result
        return exc
    return None


def _fake_variable_reader(table: dict[tuple[str, str], set[str]]):
    """Stand in for the Railway CLI, keyed by (project, service)."""

    def reader(service: str, entry: dict) -> set[str]:
        return table[(entry["project"], service)]

    return reader


_PROD_PROJECT = "system3-search-agent"
_DEV_PROJECT = "system3-search-agent-develop"
_BOTH_SERVICES = ("search-agent-api", "search-agent-web")


def _healthy_variable_table(names: set[str]) -> dict[tuple[str, str], set[str]]:
    return {(project, service): set(names) for project in (_PROD_PROJECT, _DEV_PROJECT) for service in _BOTH_SERVICES}


def test_p6_goes_red_when_develop_is_missing_a_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """P6 detects a dropped variable, and passes when nothing is dropped.

    This is the arm that caught a real gap during the phase: the develop
    project's web service was genuinely missing two build variables, and P6
    found it. That is evidence the arm works in practice; this is the evidence
    that it can fail on demand.
    """
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    base = {"APP_ENV", "AUTH_SECRET", "CORS_ORIGINS", "USER_DB_URL"}
    monkeypatch.setattr(premise.shutil, "which", lambda _: "/usr/bin/railway")

    healthy = _healthy_variable_table(base)
    monkeypatch.setattr(premise, "_service_variable_names", _fake_variable_reader(healthy))
    assert _run_named(monkeypatch, "test_p6_develop_is_not_missing_a_variable_production_has") is None, (
        "P6 fails against a healthy pair of projects, so its red result below "
        "would prove nothing"
    )

    broken = _healthy_variable_table(base)
    broken[(_DEV_PROJECT, "search-agent-api")] = base - {"AUTH_SECRET"}
    monkeypatch.setattr(premise, "_service_variable_names", _fake_variable_reader(broken))
    failure = _run_named(monkeypatch, "test_p6_develop_is_not_missing_a_variable_production_has")
    assert failure is not None, "P6 stayed green with a variable dropped from develop"
    assert "AUTH_SECRET" in str(failure), (
        f"P6 failed without naming the dropped variable: {str(failure)[:300]!r}"
    )


def test_p7b_goes_red_when_a_deployment_sets_an_undocumented_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P7b catches F-4.15-01 recurring, which P7 structurally cannot.

    P7 compares env.example against a hand-taken snapshot, so a NEW variable
    appearing on a service is invisible to it: the snapshot does not know about
    it either. P7b reads the deployment. This case is the proof of that
    difference, and it is the reason P7b exists.
    """
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    documented = premise._documented_variable_names()
    assert documented, "env.example parsed to nothing, so this case is vacuous"
    monkeypatch.setattr(premise.shutil, "which", lambda _: "/usr/bin/railway")

    healthy = _healthy_variable_table(set(list(documented)[:5]))
    monkeypatch.setattr(premise, "_service_variable_names", _fake_variable_reader(healthy))
    assert _run_named(monkeypatch, "test_p7b_env_example_documents_what_the_deployments_actually_set") is None, (
        "P7b fails when every live variable is documented, so its red result "
        "below would prove nothing"
    )

    broken = _healthy_variable_table(set(list(documented)[:5]))
    broken[(_DEV_PROJECT, "search-agent-api")] |= {"A_BRAND_NEW_UNDOCUMENTED_VARIABLE"}
    monkeypatch.setattr(premise, "_service_variable_names", _fake_variable_reader(broken))
    failure = _run_named(monkeypatch, "test_p7b_env_example_documents_what_the_deployments_actually_set")
    assert failure is not None, (
        "P7b stayed green while a deployment carried a variable env.example "
        "does not document, which is finding F-4.15-01 recurring undetected"
    )
    assert "A_BRAND_NEW_UNDOCUMENTED_VARIABLE" in str(failure)


@pytest.mark.parametrize(
    ("mutate", "must_mention"),
    [
        # Shell smuggled back into a step body, the failure build phase 4.14
        # was defeated by twice.
        (
            lambda t: t.replace(
                "run: .github/release/derive_version.sh",
                'run: ".github/release/derive_version.sh;#"',
            ),
            "not exactly one script path",
        ),
        # An injection sink reintroduced into a real expression.
        (
            lambda t: t.replace(
                "RELEASE_VERSION: ${{ steps.version.outputs.version }}",
                "RELEASE_VERSION: ${{ github.event.head_commit.message }}",
                1,
            ),
            "attacker-influenced text",
        ),
        # A step naming a script that does not exist. This is the case that
        # actually fired during the phase, when three scripts were written
        # without the executable bit.
        (
            lambda t: t.replace(
                "run: .github/release/tag_and_release.sh",
                "run: .github/release/does_not_exist.sh",
            ),
            "does not exist",
        ),
    ],
)
def test_p9_goes_red_for_each_way_the_release_workflow_can_be_broken(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mutate, must_mention: str
) -> None:
    """P9 detects shell smuggled back in, an injection sink, and a missing script."""
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    assert _run_named(monkeypatch, "test_p9_the_release_workflow_holds_the_no_shell_and_no_injection_rules") is None, (
        "P9 is red before any mutation, so the red results below prove nothing"
    )

    original = _REPO_ROOT / ".github" / "workflows" / "release.yml"
    mutated_text = mutate(original.read_text())
    assert mutated_text != original.read_text(), "the mutation changed nothing"

    mutated = tmp_path / "release.yml"
    mutated.write_text(mutated_text)
    monkeypatch.setattr(premise, "_RELEASE_WORKFLOW", mutated)

    failure = _run_named(monkeypatch, "test_p9_the_release_workflow_holds_the_no_shell_and_no_injection_rules")
    assert failure is not None, "P9 stayed green under a mutation of the release workflow"
    assert must_mention in str(failure), (
        f"P9 failed for a reason that does not name the breakage: expected "
        f"{must_mention!r}, got {str(failure)[:300]!r}"
    )


# ---------------------------------------------------------------------------
# P10: the bundle arm, mutated against a fake web server
# ---------------------------------------------------------------------------


class _WebWorld:
    """A web app serving one index and one bundle, configurable to be broken.

    Deliberately separate from `_World`, which models the API. P10 reads HTML
    and JavaScript rather than JSON, and folding it into the API model would
    have meant teaching that model two content types to save one small class.
    """

    def __init__(self, *, stale_bundle: bool = False, no_bundle_reference: bool = False) -> None:
        self.stale_bundle = stale_bundle
        self.no_bundle_reference = no_bundle_reference

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def _deployment_for(self, url: str) -> dict:
        for entry in json.loads(_FIXTURE.read_text())["deployments"].values():
            if url.startswith(entry["web"].rstrip("/")):
                return entry
        raise AssertionError(f"no deployment owns {url}")

    def get(self, url: str, **_: object) -> _Response:
        entry = self._deployment_for(url)
        if url.rstrip("/").endswith(entry["web"].rstrip("/")):
            body = "<html><body>no bundle here</body></html>"
            if not self.no_bundle_reference:
                body = '<html><script src="/assets/index-abc123.js"></script></html>'
            response = _Response(200, {})
            response.text = body
            return response

        # The bundle itself.
        if self.stale_bundle:
            # Built before VITE_API_BASE_URL was set: the local development
            # fallback ships instead of the deployment's own API host. This is
            # exactly what F-4.15-A-14 found live.
            js = 'const API="http://127.0.0.1:8000";'
        else:
            js = f'const API="{entry["api"].rstrip("/")}";'
        response = _Response(200, {})
        response.text = js
        return response


def _run_p10(monkeypatch: pytest.MonkeyPatch, world: _WebWorld) -> BaseException | None:
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    monkeypatch.setattr(premise, "_client", lambda: world)
    arm = premise.test_p10_each_web_app_is_built_against_its_own_api
    try:
        arm.__wrapped__() if hasattr(arm, "__wrapped__") else arm()
    except BaseException as exc:  # noqa: BLE001 - the failure IS the result
        return exc
    return None


def test_p10_goes_red_when_a_bundle_ships_the_local_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact live defect F-4.15-A-14 found, reproduced against a fake.

    The control half matters more than usual here. P10 passed the moment it was
    written, because the live bundle had already been rebuilt by then, and an
    arm that has only ever been green is indistinguishable from one that cannot
    go red.
    """
    assert _run_p10(monkeypatch, _WebWorld()) is None, (
        "P10 fails against a correctly built pair of bundles, so its red "
        "result below would prove nothing"
    )

    failure = _run_p10(monkeypatch, _WebWorld(stale_bundle=True))
    assert failure is not None, (
        "P10 stayed green against a bundle carrying http://127.0.0.1:8000, "
        "which is the live critical it was written for"
    )
    assert "loopback" in str(failure) or "does not contain its own API host" in str(failure), (
        f"P10 failed for a reason that does not name the defect: {str(failure)[:300]!r}"
    )


def test_p10_goes_red_when_the_index_references_no_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """An index with no script tag must fail rather than pass by absence.

    Without this, a web app serving a blank page would satisfy P10, because
    there would be no bundle in which to find a loopback address. That is the
    populate-check build phase 4.11 paid for, applied to a surface rather than
    to a variable.
    """
    failure = _run_p10(monkeypatch, _WebWorld(no_bundle_reference=True))
    assert failure is not None, (
        "P10 passed against an index referencing no bundle at all, so a blank "
        "deployment would satisfy it"
    )
    assert "references no" in str(failure), (
        f"P10 failed but not on the missing bundle: {str(failure)[:300]!r}"
    )


# ---------------------------------------------------------------------------
# P3b and P9b: the two arms that had no case, added in round 3
# ---------------------------------------------------------------------------
#
# F-4.15-RV-01, a critical, and the second time this phase produced the same
# shape. Round 1 found this harness claiming coverage it did not have. The
# round 2 fix added cases, then wrote a NEW claim that was also false, and
# named P3b in it as covered while P3b had no case. A claim about completeness
# has now failed twice here, which is why the claim is gone from the module
# docstring rather than corrected a third time.


class _FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = ""


def _variable_dump(pairs: dict[str, str]) -> str:
    return "\n".join(f"{k}={v}" for k, v in pairs.items())


def _p3b_with_secrets(monkeypatch: pytest.MonkeyPatch, per_project: dict[str, str]) -> BaseException | None:
    """Run P3b with the Railway CLI replaced by a fixed answer per project."""
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    key = "AUTH" + "_SECRET"
    monkeypatch.setattr(premise.shutil, "which", lambda _: "/usr/bin/railway")

    def fake_run(argv, **_):
        project = argv[argv.index("--project") + 1]
        return _FakeCompleted(_variable_dump({key: per_project[project], "APP_ENV": "x"}))

    monkeypatch.setattr(premise.subprocess, "run", fake_run)
    return _run_named(monkeypatch, "test_p3b_the_two_deployments_hold_different_signing_keys")


def test_p3b_goes_red_when_both_deployments_hold_the_same_signing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P3b detects a shared signing key, and passes when the keys differ.

    P3b is half of the pair that replaced the arm F-4.15-J-04 found unsound, so
    an unfalsifiable P3b would mean that critical was closed by nothing at all.
    """

    deployments = json.loads(_FIXTURE.read_text())["deployments"]
    prod = deployments["production"]["project_id"]
    dev = deployments["develop"]["project_id"]

    control = _p3b_with_secrets(monkeypatch, {prod: "key-one", dev: "key-two"})
    assert control is None, (
        f"P3b fails when the two keys genuinely differ, so its red result "
        f"below would prove nothing: {control!r}"
    )

    failure = _p3b_with_secrets(monkeypatch, {prod: "same-key", dev: "same-key"})
    assert failure is not None, (
        "P3b stayed green with both deployments holding an identical signing "
        "key, which is the whole property it exists to assert"
    )
    assert "SAME" in str(failure), (
        f"P3b failed for a reason that does not name the shared key: "
        f"{str(failure)[:300]!r}"
    )


def test_p3b_goes_red_when_a_deployment_has_no_signing_key_at_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absence must fail rather than pass by comparing nothing to nothing.

    Two empty strings are equal, so a naive comparison would report them as
    shared and go red for the right reason by luck. This pins that the arm
    stops on the missing value with its own message instead.
    """

    deployments = json.loads(_FIXTURE.read_text())["deployments"]
    prod = deployments["production"]["project_id"]
    dev = deployments["develop"]["project_id"]

    failure = _p3b_with_secrets(monkeypatch, {prod: "key-one", dev: ""})
    assert failure is not None, "P3b passed with a deployment holding no signing key"
    # The message moved when P3b was refactored onto the shared
    # `_signing_key_for` reader, which raises on an empty value before P3b
    # sees it. The expectation follows the code rather than the code being
    # bent back to an old string: the arm still stops on the missing value,
    # which is the property, and it now says which deployment.
    assert "empty" in str(failure), (
        f"P3b failed but not on the missing value: {str(failure)[:300]!r}"
    )


@pytest.mark.parametrize(
    ("body", "must_mention"),
    [
        # A release script that continues past a failed command while holding
        # write access to the production line.
        ("#!/usr/bin/env bash\necho hello\n", "set -euo pipefail"),
        # Workflow interpolation syntax copied into a script, where GitHub does
        # not expand it.
        ('#!/usr/bin/env bash\nset -euo pipefail\nx="${{ github.event.head_commit.message }}"\n', "in executable code"),
        # A script that does not parse. Three shipped non-executable earlier in
        # this phase; a syntax error is the same class of failure at release
        # time, on the production line, after the merge.
        ("#!/usr/bin/env bash\nset -euo pipefail\nif [ -z ; then\n", "does not parse"),
    ],
)
def test_p9b_goes_red_for_each_way_a_release_script_can_be_unsafe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: str, must_mention: str
) -> None:
    """P9b checks the scripts the workflow delegates to. This proves it can fail.

    P9b was itself added to close F-4.15-A-13, which was "P9 certifies the
    workflow has no shell and never looks at the shell". Adding an arm to close
    a finding and leaving it unfalsifiable closes nothing, which is the point
    F-4.15-RV-01 makes about this whole file.
    """
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    assert _run_named(monkeypatch, "test_p9b_the_release_scripts_themselves_hold_their_safety_rules") is None, (
        "P9b is red against the real scripts before any mutation, so the red "
        "results below prove nothing"
    )

    release_dir = tmp_path / ".github" / "release"
    release_dir.mkdir(parents=True)
    for name in ("commit_lib", "derive_version", "write_changelog", "tag_and_release"):
        good = release_dir / f"{name}.sh"
        good.write_text("#!/usr/bin/env bash\nset -euo pipefail\necho ok\n")
    (release_dir / "open_backmerge_pr.sh").write_text(body)

    monkeypatch.setattr(premise, "_REPO_ROOT", tmp_path)
    failure = _run_named(monkeypatch, "test_p9b_the_release_scripts_themselves_hold_their_safety_rules")
    assert failure is not None, (
        f"P9b stayed green against a release script that is unsafe: {body!r}"
    )
    assert must_mention in str(failure), (
        f"P9b failed for a reason that does not name the breakage: expected "
        f"{must_mention!r}, got {str(failure)[:300]!r}"
    )


# ---------------------------------------------------------------------------
# P3c: the arm that finally removed the proxy
# ---------------------------------------------------------------------------


class _SigningWorld:
    """A production API that verifies tokens against ONE key it actually holds.

    Faithful where the earlier fake was not. `_World`'s `/auth/me` looked a
    token up in a dictionary, which models "was this token issued here" and NOT
    "does this signature verify", and that unfaithfulness is part of what let
    F-4.15-J-04 survive two rounds. This one decodes with a real key, so the
    distinction P3c exists to make is present in the model.
    """

    def __init__(self, server_key: str, *, accepts_any_signature: bool = False) -> None:
        self.server_key = server_key
        self.accepts_any_signature = accepts_any_signature

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def post(self, url: str, json: dict | None = None, **_: object) -> _Response:
        if url.endswith("/auth/signup"):
            return _Response(201, {"id": "u-1", "email": (json or {}).get("email", "")})
        if url.endswith("/auth/login"):
            now = int(time.time())
            token = jwt.encode(
                {"user_id": "u-1", "iat": now, "exp": now + 900},
                self.server_key,
                algorithm="HS256",
            )
            return _Response(200, {"access_token": token, "token_type": "bearer"})
        raise AssertionError(f"unmodelled POST {url}")

    def get(self, url: str, headers: dict | None = None, **_: object) -> _Response:
        if url.endswith("/auth/me"):
            raw = (headers or {}).get("Authorization", "")
            token = raw.removeprefix("Bearer ").strip()
            if self.accepts_any_signature:
                # A deployment that decodes without verifying. This is the
                # state where the two CONFIGURED keys differ and production
                # still takes a token signed with develop's, which is the
                # concrete miss F-4.15-GC-01 described.
                return _Response(200, {"id": "u-1"})
            try:
                jwt.decode(token, self.server_key, algorithms=["HS256"])
            except Exception:  # noqa: BLE001 - any verification failure is a 401
                return _Response(401, {"detail": "invalid or expired access token"})
            return _Response(200, {"id": "u-1"})
        raise AssertionError(f"unmodelled GET {url}")


def _run_p3c(
    monkeypatch: pytest.MonkeyPatch,
    *,
    configured_prod: str,
    configured_dev: str,
    accepts_any_signature: bool = False,
) -> BaseException | None:
    import tests.system_03_search_agent.tools.test_release_environments_premise as premise

    keys = {"production": configured_prod, "develop": configured_dev}
    monkeypatch.setattr(premise, "_signing_key_for", lambda name: keys[name])
    # The server runs on production's CONFIGURED value, which is the honest
    # arrangement: the mutation below changes what is configured on develop,
    # not what production runs.
    monkeypatch.setattr(
        premise,
        "_client",
        lambda: _SigningWorld(configured_prod, accepts_any_signature=accepts_any_signature),
    )
    return _run_named(
        monkeypatch,
        "test_p3c_a_token_signed_with_the_other_key_is_refused_for_a_user_that_exists",
    )


def test_p3c_goes_red_when_both_deployments_sign_with_the_same_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P3c detects a shared signing key through the path that depends on it.

    The control proves the arm passes when the keys genuinely differ. The
    mutation makes develop's configured key equal production's, so re-signing
    production's own claims with "the other" key produces a token production
    accepts, and the arm must go red.

    This is the case none of P3, P3a or P3b could express. P3 read a 401 that
    was really about a missing user row; P3a never read a configured key; P3b
    never sent a request. Here the row exists, the request is real, and the key
    is the only variable.
    """
    control = _run_p3c(
        monkeypatch, configured_prod="alpha-one-two", configured_dev="beta-three-four"
    )
    assert control is None, (
        f"P3c fails when the two keys genuinely differ, so its red result "
        f"below would prove nothing: {control!r}"
    )

    # THE MUTATION THAT EXERCISES P3C'S OWN ASSERTION. The two configured
    # keys still differ, so P3c's early guard does not fire, and production
    # accepts a token signed with develop's key anyway. That is the state
    # F-4.15-GC-01 named: nothing tied the key the running process uses to
    # the value that was compared.
    #
    # The first version of this case made the two CONFIGURED keys equal,
    # which trips P3c's guard and routes to P3b's finding. It went red for
    # the right reason under the wrong arm, which is the same "red, but not
    # for its own property" trap this harness checks for everywhere else,
    # met here by the person writing the harness.
    failure = _run_p3c(
        monkeypatch,
        configured_prod="alpha-one-two",
        configured_dev="beta-three-four",
        accepts_any_signature=True,
    )
    assert failure is not None, (
        "P3c stayed green while production accepted a token signed with "
        "develop's key, which is the entire property it was written to "
        "establish"
    )
    assert "ACCEPTED" in str(failure), (
        f"P3c failed for a reason that does not name the acceptance: "
        f"{str(failure)[:300]!r}"
    )

    # And the guard itself: equal configured keys route to P3b rather than
    # producing a confusing P3c failure.
    guarded = _run_p3c(
        monkeypatch, configured_prod="alpha-one-two", configured_dev="alpha-one-two"
    )
    assert guarded is not None and "P3b's finding" in str(guarded), (
        f"P3c did not route equal configured keys to P3b: {str(guarded)[:200]!r}"
    )
