"""Premise gate for build phase 4.15, the two-environment release flow.

The premise is one sentence: `develop` and `production` are SEPARATE
deployments, with separate URLs, separate secrets and separate data, and each
one deploys from its own branch. Everything below tries to make that sentence
false.

## Why this gate is behavioural rather than a configuration comparison

The obvious gate reads both environments' variables and asserts the values
differ. It was rejected for two reasons, and the second is the load-bearing
one.

First, it would require rendering secrets. `AUTH_SECRET` is the variable whose
separation matters most, and a gate that proves it by printing it into a test
process, a CI log or an assertion message has traded the property for the
proof. `.claude/rules/ai-security-standards.md` forbids it in those words.

Second, and this is the part worth carrying: comparing two values proves they
are different STRINGS, not that anything depends on the difference. A
deployment could hold two distinct `AUTH_SECRET` values and still verify
tokens with a third, hardcoded one, and the comparison gate would be green.
That is the safety-by-proxy shape build phase 4.3 shipped as a critical twice
and build phase 4.7 hit again: the check verifies a CORRELATE of the property
rather than the property.

That objection took FOUR attempts to actually answer, and the sequence is
recorded in P3c's docstring because each intermediate step looked like a fix
and was not. The answer that holds: P3c takes a token production itself minted,
re-signs the identical claims with DEVELOP's key, and requires production to
refuse it, with the same claims re-signed with production's own key accepted as
the control. The user row exists, so a 401 can only mean the signature was
rejected.

## How an arm is gated, and why "skip" is not the default here

Every other live gate in this repository skips when its transport is
unreachable, because an unreachable NCBI endpoint is a fact about the network
rather than about the code. That rule is wrong for this gate and is
deliberately not followed.

Here, "the develop environment does not answer" is not a network condition. It
is the exact failure this phase exists to prevent. So:

- `RUN_PREMISE_GATE` unset: the live arms skip. Nothing was measured and the
  gate says so.
- `RUN_PREMISE_GATE=1`: the live arms FAIL when an environment is missing,
  unreachable or misconfigured. They never skip for that reason.

This is the populate-check discipline build phase 4.11 arrived at, stated as a
gating rule rather than as an assertion: an arm that cannot distinguish "the
control held" from "nothing happened" is not an arm. An arm that skips when
the thing it guards is absent is that same defect wearing a skip marker.

P7 and P8 are static file checks and run ALWAYS, with no flag, because nothing
about them needs a network. Putting them behind the flag would have hidden two
thirds of the gate from CI for no reason.

## What each arm catches

DELIBERATELY NOT LISTED HERE, and the omission is the lesson rather than an
oversight. This section used to hold a table of nine arms with a row each. By
2026-08-28 the gate held fourteen, the table still described a `P3` that no
longer exists, and it named none of P3a, P3b, P3c, P7b, P9b or P10. A summary
table of a growing set is stale from its second edit, and a reader who trusts
it stops reading the arms.

Twice in this phase a confident summary sentence WAS the defect: P1's docstring
claimed a comparison the body did not perform (F-4.15-J-01, F-4.15-A-10), and
the mutation harness claimed coverage it did not have, twice (F-4.15-J-03, then
F-4.15-RV-01 inside the fix for it). So the summary is gone.

Each arm's own docstring states what it catches and what it does not, next to
the code that has to stay true to it. Read `git grep "^def test_p" ` on this
file for the current set.

## What this gate does NOT cover

Stated here rather than left to be discovered, per `.claude/rules/goal-contracts.md`.

- It does not prove a release cut from `develop` and merged to `production` actually
  reaches production. It proves the triggers are configured. The first real
  release is that proof and it is outside this phase.
- It does not test rollback. Railway's rollback is a console redeploy of a
  previous build with no API surface exercised here.
- It does not prove the two Postgres instances differ at rest. P2 proves it
  through the auth path, the path that matters, and says nothing about the
  `interactions` or `runs` tables.
- P6 compares variable NAMES, never values. A variable present in both with
  production's value copied into develop PASSES P6. P3b, P3c and P4 cover the
  cases where that would be dangerous. Nothing covers the rest.
- Nothing here separates the graph credential per environment, deliberately.
  Layer 1 is read-only at the connection level, so there is no
  develop-versus-production hazard to separate.
- P4 tests the CORS preflight response, not whether a browser honours it. A
  server that returns the right headers and a browser that ignores them is
  outside anything this repository can assert.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import jwt
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURE = Path(__file__).with_name("fixtures") / "release_environments.json"
_CI_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
_ENV_EXAMPLE = _REPO_ROOT / "env.example"

_RUN_LIVE = os.environ.get("RUN_PREMISE_GATE") == "1"

# Gated on the FLAG ALONE, never on reachability. See "How an arm is gated"
# in the module docstring: an environment that does not answer is the defect
# this gate exists to find, so it must fail rather than skip.
requires_live = pytest.mark.skipif(
    not _RUN_LIVE,
    reason="needs RUN_PREMISE_GATE=1 (the live arms FAIL rather than skip when an environment is absent)",
)

_HTTP_TIMEOUT = 30.0

# Railway injects these into every service. They are not ours to document in
# env.example and not ours to provision, so both P6 and P7 exclude them.
_RAILWAY_PREFIX = "RAILWAY_"


def _environments() -> dict[str, dict[str, str]]:
    """The two DEPLOYMENTS, which are two Railway projects rather than two environments.

    Renamed from `environments` on 2026-08-27, finding F-4.15-03. The first
    build of this phase put both deployments in one Railway project as two
    environments, which is what Section 24's wording implies, and it does not
    work: a service's git branch is service-level, so both environments
    deployed the same branch. The key name changed with the topology so that a
    reader of this file cannot come away with the wrong mental model.
    """
    return json.loads(_FIXTURE.read_text())["deployments"]


def _require(name: str) -> dict[str, str]:
    """The fixture entry for one environment, or a failure that says what to do.

    A missing entry is a FAILURE and not a skip. Build phase 4.15 exists to
    create the develop environment, so "develop is not in the fixture" is the
    phase being incomplete, which is precisely what a gate should report.
    """
    envs = _environments()
    if name not in envs:
        pytest.fail(
            f"environment {name!r} is absent from {_FIXTURE.name}. Provision it "
            f"(T-4.15-03) and record its URLs here, or this gate is asserting "
            f"nothing about it."
        )
    entry = envs[name]
    for key in ("api", "web", "branch", "app_env", "project_id", "environment_id"):
        if not entry.get(key):
            pytest.fail(f"environment {name!r} has no {key!r} in {_FIXTURE.name}")
    return entry


def _client() -> Any:
    import httpx

    return httpx.Client(timeout=_HTTP_TIMEOUT, follow_redirects=True)


def _throwaway_credentials() -> tuple[str, str]:
    """A unique account per run, so a re-run never collides with its own rows.

    The address is deliberately marked so anyone reading the develop database
    can tell at a glance that these rows are gate exhaust rather than a person.
    """
    token = uuid.uuid4().hex
    return f"gate-4.15-{token}@example.invalid", f"pw-{token}"


# ---------------------------------------------------------------------------
# P1: two environments, both answering, at different hostnames
# ---------------------------------------------------------------------------


@requires_live
def test_p1_both_environments_answer_at_different_hostnames() -> None:
    """Both APIs are healthy AND they are not the same deployment.

    The second half is the half that matters. Asserting each `/health` returns
    ok would pass if the fixture named one URL twice, or if a DNS alias pointed
    develop at production, and either of those is exactly the failure "two
    deployments" is supposed to exclude. So the hostnames are compared, and so
    are the Railway project ids the fixture records, since two hostnames in one
    project cannot watch two branches (F-4.15-03) and would defeat the whole
    phase.

    WHAT THIS ARM DOES NOT DO, corrected 2026-08-27 after findings F-4.15-J-01
    and F-4.15-A-10, which a judge and an adversary filed independently against
    the same sentence. This docstring used to claim "the service ids reported
    by the two deployments are compared too, because two hostnames can still
    front one service". No such comparison existed anywhere in the body, and
    none is possible over HTTP, because nothing this API exposes reports a
    Railway service id. A comment asserting a check that is not there is worse
    than no comment: it tells the next reader the case was covered, which is
    the exact reason both reviewers went looking. The claim is replaced by the
    project-id comparison, which IS performed, and by this paragraph naming
    what remains uncovered: two hostnames fronting one service inside one
    project would still pass P1, and only P2, P3a and P3b would catch it.
    """
    prod = _require("production")
    dev = _require("develop")

    assert prod["api"] != dev["api"], (
        "production and develop name the same API URL, so there is one "
        "deployment wearing two labels"
    )
    assert prod["web"] != dev["web"], "production and develop name the same web URL"
    # The check the old docstring claimed and did not perform. Two deployments
    # in ONE Railway project cannot watch two branches (F-4.15-03), so a shared
    # project id defeats the phase even when the hostnames differ.
    assert prod["project_id"] != dev["project_id"], (
        f"both deployments name Railway project {prod['project_id']}. A "
        f"service's git branch is service-level, so one project cannot carry "
        f"two branches and the release flow would be promoting nothing."
    )

    with _client() as client:
        for label, entry in (("production", prod), ("develop", dev)):
            response = client.get(entry["api"].rstrip("/") + "/health")
            assert response.status_code == 200, (
                f"{label} API {entry['api']} returned {response.status_code}, "
                f"not 200. A premise gate arm for an environment that does not "
                f"answer is a failure, never a skip."
            )
            assert response.json().get("status") == "ok", (
                f"{label} API answered but did not report status ok: {response.text[:200]}"
            )


# ---------------------------------------------------------------------------
# P2 and P3: one signup, two separations
# ---------------------------------------------------------------------------


@requires_live
def test_p2_an_account_made_on_develop_cannot_sign_in_on_production() -> None:
    """Data isolation, proven through the path that would actually leak.

    This is the arm that would be UNWRITABLE had the two environments shared a
    Postgres. It creates a real account on develop and then tries the same
    credentials against production, which must not know them.

    A 401 is the pass. Anything in the 2xx range means the two environments
    read one user table, which is the configuration the product owner rejected
    on 2026-08-27.
    """
    dev = _require("develop")
    prod = _require("production")
    email, password = _throwaway_credentials()

    with _client() as client:
        created = client.post(
            dev["api"].rstrip("/") + "/auth/signup",
            json={"email": email, "password": password},
        )
        assert created.status_code == 201, (
            f"could not create an account on develop to test with: "
            f"{created.status_code} {created.text[:200]}"
        )

        # The positive control. Without it, a develop API that rejects EVERY
        # login would make the negative assertion below pass for the wrong
        # reason, which is the vacuous-arm shape this repository has now been
        # caught by eleven times.
        on_develop = client.post(
            dev["api"].rstrip("/") + "/auth/login",
            json={"email": email, "password": password},
        )
        assert on_develop.status_code == 200, (
            f"the account was created on develop but cannot log in there "
            f"({on_develop.status_code}), so the cross-environment assertion "
            f"below would prove nothing"
        )

        on_production = client.post(
            prod["api"].rstrip("/") + "/auth/login",
            json={"email": email, "password": password},
        )

    assert on_production.status_code == 401, (
        f"an account created on develop logged in on production with "
        f"{on_production.status_code}. The two environments share a user "
        f"database, which is the exact configuration build phase 4.15 was "
        f"opened to prevent."
    )


def _signing_key_for(name: str) -> str:
    """The signing key CONFIGURED on one deployment's api service.

    Shared by P3b, which hashes it, and P3c, which must SIGN with it. One
    reader on purpose: two readers of one secret is the exact shape that
    produced three separate findings in the release scripts (F-4.15-A-01,
    A-03, A-07), and it is not worth repeating here to save an indirection.

    The plaintext is returned rather than hashed, because P3c cannot mint a
    token with a digest. It is never rendered: no caller puts it in an
    assertion message. Reading a credential is permitted; printing one is what
    `.claude/rules/ai-security-standards.md` forbids.
    """
    if shutil.which("railway") is None:
        pytest.fail(
            "the Railway CLI is not on PATH, so the signing keys cannot be "
            "read. Install it or run this gate from a machine that has it; do "
            "not weaken the arm to a skip."
        )
    entry = _require(name)
    key_name = "AUTH" + "_SECRET"
    completed = subprocess.run(
        [
            "railway",
            "variables",
            "--project",
            entry["project_id"],
            "--environment",
            entry["environment_id"],
            "--service",
            "search-agent-api",
            "--kv",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=_REPO_ROOT,
        check=False,
    )
    assert completed.returncode == 0, (
        f"`railway variables` failed for {name}: exit {completed.returncode}"
    )
    for line in completed.stdout.splitlines():
        if line.startswith(key_name + "="):
            value = line.split("=", 1)[1]
            assert value, f"{name} has an empty {key_name}"
            return value
    pytest.fail(
        f"{name} has no {key_name} set on search-agent-api, so any arm "
        f"depending on it would compare or sign with nothing"
    )
    raise AssertionError("unreachable")


@requires_live
def test_p3a_each_deployment_actually_verifies_a_token_signature() -> None:
    """Signature verification is live on each deployment, tested by tampering.

    REWRITTEN 2026-08-27 after findings F-4.15-J-04, and the reason is the most
    important thing in this file.

    The previous P3 minted a token on one deployment, presented it to the
    other, asserted 401, and CALLED THAT PROOF that the signing key is not
    shared. It is not proof. `resolve_user_from_bearer_token` decodes the token
    and THEN looks the subject up in that deployment's own database
    (`src/system_03_search_agent/auth/dependencies.py:108-111`), raising the
    SAME `_INVALID_TOKEN_DETAIL` when the row is absent. The two deployments
    have separate databases, so the cross-deployment 401 arrives on the missing
    user row whether the signing key is shared or not. The arm measured
    database separation, which is already P2's property, and asserted key
    separation, which is merely correlated with it.

    That is the safety-by-proxy shape this module's own docstring said it was
    written to avoid: written by the same person, in the same file, under the
    warning. It is the fourth instance in this repository after build phases
    4.3, 4.7 and 4.11, and it is recorded here rather than quietly repaired
    because the transferable lesson is that WRITING THE WARNING DOWN DOES NOT
    IMMUNISE YOU AGAINST THE THING.

    The property is now split into two arms that are each directly testable:

    - P3a, here: each deployment really does verify a signature, proven by
      corrupting one and watching that deployment reject it. Without this, a
      deployment that skipped verification altogether would still pass P3b.
    - P3b, below: the two signing keys differ, compared as digests so that no
      secret is rendered.

    Neither half alone is the property. Together they are: the keys differ, and
    each deployment enforces its own.

    The tamper is applied to the SIGNATURE segment only, leaving the header and
    payload intact, so a rejection cannot be explained away by malformed base64
    or a broken claim set.
    """
    for name in ("develop", "production"):
        entry = _require(name)
        api = entry["api"].rstrip("/")
        email, password = _throwaway_credentials()

        with _client() as client:
            created = client.post(
                api + "/auth/signup", json={"email": email, "password": password}
            )
            assert created.status_code == 201, (
                f"could not create an account on {name}: {created.status_code} "
                f"{created.text[:200]}"
            )
            logged_in = client.post(
                api + "/auth/login", json={"email": email, "password": password}
            )
            assert logged_in.status_code == 200, (
                f"could not log in on {name}: {logged_in.status_code}"
            )
            token = logged_in.json()["access_token"]

            # Positive control. The untampered token must work, or the
            # rejection below proves nothing about signatures.
            good = client.get(
                api + "/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
            assert good.status_code == 200, (
                f"a freshly minted token does not work on {name} "
                f"({good.status_code}), so the tamper assertion below would be "
                f"vacuous"
            )

            parts = token.split(".")
            assert len(parts) == 3, (
                f"{name} issued a token that is not three dot-separated "
                f"segments, so the signature cannot be isolated: "
                f"{len(parts)} segment(s)"
            )
            # Flip one character in the MIDDLE of the signature, keeping the
            # length and the base64url alphabet, so the token stays well formed
            # and only the signature is wrong.
            #
            # The middle matters and this was measured, not reasoned. The first
            # version of this arm flipped the LAST character and both
            # deployments returned 200, which reads as "the API accepts forged
            # tokens" and is not what happened. A base64url string encodes 6
            # bits per character, and an HMAC-SHA256 signature is 32 bytes, so
            # the final character carries only the 2 remaining significant bits
            # and 4 that decode to nothing. Flipping it can produce a DIFFERENT
            # STRING that decodes to the IDENTICAL SIGNATURE BYTES, which the
            # server then correctly accepts.
            #
            # Worth keeping because of what it nearly became: a false critical
            # security finding produced by a faulty probe. The measurement that
            # settled it is that the tampered token still verified, which a
            # forged-token acceptance bug cannot explain but a no-op edit can.
            signature = parts[2]
            assert len(signature) >= 8, (
                f"signature segment is {len(signature)} characters, too short "
                f"to tamper with in the middle"
            )
            midpoint = len(signature) // 2
            swapped = "B" if signature[midpoint] != "B" else "C"
            tampered = ".".join(
                [parts[0], parts[1], signature[:midpoint] + swapped + signature[midpoint + 1 :]]
            )
            assert tampered != token, "the tamper produced the original token"

            bad = client.get(
                api + "/auth/me", headers={"Authorization": f"Bearer {tampered}"}
            )

        assert bad.status_code == 401, (
            f"{name} ACCEPTED a token whose signature was corrupted "
            f"({bad.status_code}). It is not verifying signatures at all, so "
            f"which key it holds does not matter."
        )


@requires_live
def test_p3b_the_two_deployments_hold_different_signing_keys() -> None:
    """The two signing keys differ, compared as digests rather than as values.

    This is the value comparison the module docstring originally rejected, and
    it is here now with its objection answered rather than ignored.

    The first objection was that comparing values means rendering secrets. It
    does not have to. The values are hashed inside this process and only the
    digests are ever compared, so no secret reaches an assertion message, a log
    or a CI transcript. `.claude/rules/ai-security-standards.md` forbids a
    credential in a log, not the fact of reading one.

    The second objection was the real one and it still stands: a difference
    between two strings does not prove anything DEPENDS on the difference.
    Which is exactly why this arm does not stand alone. P3a proves each
    deployment enforces a signature; this proves the keys they enforce with are
    not the same key. The composition is the property. The previous single
    arm's mistake was believing one behavioural-looking check could carry both
    halves at once.
    """
    digests = {
        name: hashlib.sha256(_signing_key_for(name).encode()).hexdigest()
        for name in ("production", "develop")
    }

    assert digests["production"] != digests["develop"], (
        "the two deployments hold the SAME signing key. A token minted on "
        "develop is therefore signed acceptably for production, and the only "
        "thing standing between them is that their user tables differ. "
        "Section 24 requires this value be generated per environment and "
        "never shared."
    )
# ---------------------------------------------------------------------------
# P4: CORS is per environment
# ---------------------------------------------------------------------------


@requires_live
def test_p4_each_api_admits_its_own_web_origin_and_refuses_the_other() -> None:
    """`CORS_ORIGINS` was set per environment rather than carried by the duplicate.

    Both halves are asserted for the same reason P3 tests both directions: an
    API that allowed NOTHING would pass a refusal-only check while being
    completely broken.
    """
    prod = _require("production")
    dev = _require("develop")

    with _client() as client:
        for label, entry, other in (
            ("production", prod, dev),
            ("develop", dev, prod),
        ):
            api = entry["api"].rstrip("/")

            allowed = client.options(
                api + "/auth/login",
                headers={
                    "Origin": entry["web"],
                    "Access-Control-Request-Method": "POST",
                },
            )
            allow_own = allowed.headers.get("access-control-allow-origin")
            assert allow_own == entry["web"], (
                f"{label}'s API did not admit its OWN web origin "
                f"{entry['web']}: allow-origin was {allow_own!r}. The refusal "
                f"assertion below would pass vacuously against an API that "
                f"allows nothing."
            )

            refused = client.options(
                api + "/auth/login",
                headers={
                    "Origin": other["web"],
                    "Access-Control-Request-Method": "POST",
                },
            )
            allow_other = refused.headers.get("access-control-allow-origin")
            assert allow_other != other["web"], (
                f"{label}'s API admitted {other['web']}, the OTHER "
                f"environment's web origin. CORS_ORIGINS was copied by the "
                f"environment duplicate rather than set per environment."
            )


# ---------------------------------------------------------------------------
# P5: the two report different APP_ENV
# ---------------------------------------------------------------------------


@requires_live
def test_p5_the_two_environments_report_different_app_env() -> None:
    """The duplicate did not carry production's app config unchanged.

    `/health` is the only unauthenticated surface that reports it, so this arm
    is bounded by what that endpoint exposes. If it stops reporting `app_env`
    this arm fails loudly rather than silently passing, which is the intent.
    """
    prod = _require("production")
    dev = _require("develop")

    seen: dict[str, str] = {}
    with _client() as client:
        for label, entry in (("production", prod), ("develop", dev)):
            payload = client.get(entry["api"].rstrip("/") + "/health").json()
            assert "app_env" in payload, (
                f"{label}'s /health does not report app_env, so this arm can "
                f"no longer distinguish the two environments: {payload}"
            )
            seen[label] = payload["app_env"]
            assert payload["app_env"] == entry["app_env"], (
                f"{label} reports app_env={payload['app_env']!r}, but "
                f"{_FIXTURE.name} records {entry['app_env']!r}"
            )

    assert seen["production"] != seen["develop"], (
        f"both environments report app_env={seen['production']!r}, so the "
        f"duplicate carried production's app config unchanged"
    )


# ---------------------------------------------------------------------------
# P6: no variable was dropped in provisioning
# ---------------------------------------------------------------------------


def _service_variable_names(service: str, entry: dict[str, str]) -> set[str]:
    """Variable NAMES for one service, never values.

    The `sed` that strips everything after the first `=` runs before anything
    reaches this process's memory, so no value is read, logged, or capable of
    reaching an assertion message. That is deliberate and is the whole reason
    this shells out instead of using the Railway MCP, whose response renders
    every value in full.
    """
    completed = subprocess.run(
        [
            "railway",
            "variables",
            "--project",
            entry["project_id"],
            "--environment",
            entry["environment_id"],
            "--service",
            service,
            "--kv",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=_REPO_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail(
            f"`railway variables` failed for {service} in project "
            f"{entry['project']}. This arm needs the Railway CLI linked and "
            f"logged in. Run `railway status` to check. Exit "
            f"{completed.returncode}."
        )
    names = set()
    for line in completed.stdout.splitlines():
        name = line.split("=", 1)[0].strip()
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", name) and not name.startswith(_RAILWAY_PREFIX):
            names.add(name)
    return names


@requires_live
def test_p6_develop_is_not_missing_a_variable_production_has() -> None:
    """Provisioning dropped nothing.

    Direction matters and is asserted one way only, on purpose. Production
    having something develop lacks is a provisioning gap and fails. Develop
    having something extra is normal (a debug flag, a feature under test) and
    is reported rather than failed, because failing it would make the gate
    hostile to the exact experimentation a develop environment is for.
    """
    if shutil.which("railway") is None:
        pytest.fail(
            "the Railway CLI is not on PATH, so this arm cannot verify the "
            "variable sets. Install it or run this gate from a machine that "
            "has it; do not weaken the arm to a skip."
        )

    prod_entry = _require("production")
    dev_entry = _require("develop")

    assert prod_entry["project_id"] != dev_entry["project_id"], (
        "both deployments name the same Railway project. Since a service's git "
        "branch is service-level (F-4.15-03), one project cannot carry two "
        "branches, so this arm's comparison would be between a thing and itself."
    )

    for service in ("search-agent-api", "search-agent-web"):
        production = _service_variable_names(service, prod_entry)
        develop = _service_variable_names(service, dev_entry)

        assert production, (
            f"read zero variable names for {service} in "
            f"{prod_entry['project']}, so the comparison below would pass "
            f"against anything"
        )
        assert develop, (
            f"read zero variable names for {service} in {dev_entry['project']}"
        )

        missing = sorted(production - develop)
        assert not missing, (
            f"{service} in {dev_entry['project']} is missing {len(missing)} "
            f"variable(s) that production has: {missing}. Provisioning dropped "
            f"them. This is the arm that would have caught F-4.15-04 had the "
            f"copy script dropped variables instead of over-copying them."
        )


# ---------------------------------------------------------------------------
# P7 and P8: static, always run, no flag
# ---------------------------------------------------------------------------


def _documented_variable_names() -> set[str]:
    names = set()
    for line in _ENV_EXAMPLE.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        name = stripped.split("=", 1)[0].strip()
        if re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            names.add(name)
    return names


def test_p7_env_example_documents_every_variable_the_deployment_sets() -> None:
    """F-4.15-01: a variable can be load-bearing in the deployment and undocumented.

    `RUN_MIGRATIONS_ON_STARTUP` gates `alembic upgrade head` in `railway.json`'s
    start command and was absent from `env.example`, so provisioning a second
    environment from the file this repository tells people to provision from
    would silently omit the variable that decides whether migrations run.

    This arm runs OFFLINE against a checked-in expectation rather than against
    the live service, for one reason: it has to keep working in CI, where there
    is no Railway credential.

    WHAT IT THEREFORE CANNOT DO, corrected after F-4.15-J-06 and F-4.15-A-11.
    The set below is a SNAPSHOT taken by hand on 2026-08-27, not a reading of
    any deployment. If someone sets a new variable on a service tomorrow and
    documents it nowhere, this arm stays green, because the snapshot does not
    know about it either. That is finding F-4.15-01 recurring undetected, which
    is the one thing this arm is named for. P7b below is the arm that actually
    reads the deployments; this one only checks that the snapshot and the
    documentation still agree.

    The direction asserted is deployment-set implies documented. The converse
    is false on purpose and must stay false: `env.example` legitimately carries
    alternate-provider keys and build phase 5.0/5.1 variables that no service
    sets yet.
    """
    deployment_sets = {
        "ANON_DAILY_RUN_CAP",
        "APP_ENV",
        "AUTH_SECRET",
        "CORS_ORIGINS",
        "GRAPH_QUERY_TOKEN",
        "GRAPH_QUERY_URL",
        "GUARD_MODEL",
        "LANGCHAIN_TRACING_V2",
        "LANGSMITH_PROJECT",
        "LOG_LEVEL",
        "NCBI_API_KEY",
        "NCBI_EMAIL",
        "NIXPACKS_NODE_VERSION",
        "NIXPACKS_NO_CACHE",
        "OPENROUTER_API_KEY",
        "PER_QUERY_COST_CAP_USD",
        "PER_STEP_TIMEOUT_SECONDS",
        "PER_USER_DAILY_QUERY_CAP",
        "PLAN_MODEL",
        "POSTHOG_HOST",
        "REDIS_URL",
        "RUN_MIGRATIONS_ON_STARTUP",
        "SYNTH_MODEL",
        "SYSTEM_DAILY_CAP_USD",
        "USER_DB_URL",
        "VITE_API_BASE_URL",
    }
    documented = _documented_variable_names()

    assert documented, "read zero names out of env.example, so this arm is vacuous"

    undocumented = sorted(deployment_sets - documented)
    assert not undocumented, (
        f"{len(undocumented)} variable(s) are set on the deployed services and "
        f"absent from env.example: {undocumented}. Anyone provisioning a new "
        f"environment from env.example would omit them. This is F-4.15-01."
    )


@requires_live
def test_p7b_env_example_documents_what_the_deployments_actually_set() -> None:
    """The live half of P7, and the only arm that can catch F-4.15-01 again.

    ADDED 2026-08-27 after findings F-4.15-J-06 and F-4.15-A-11, filed
    independently by a judge and an adversary against the same gap.

    P7 above is named "env.example documents every variable the deployment
    sets" and never reads a deployment. It compares `env.example` against a
    SNAPSHOT of variable names taken by hand on 2026-08-27. That snapshot is
    useful, because it runs in CI where there is no Railway credential, and it
    is not the property: the day someone sets a new variable on a service and
    does not document it, which is precisely finding F-4.15-01, the snapshot
    still matches `env.example` and P7 stays green.

    So the arm that carries the property is this one, and it reads the live
    services. The two together are honest: P7 is a cheap always-on check that
    the snapshot and the documentation agree, and P7b is the expensive check
    that the snapshot is still true of reality.

    Names only, never values. The comparison is over variable NAMES and the
    values are not read into this process at all.
    """
    if shutil.which("railway") is None:
        pytest.fail(
            "the Railway CLI is not on PATH, so the deployed variable set "
            "cannot be read. This arm is the only one that can catch a new "
            "undocumented variable; do not weaken it to a skip."
        )

    documented = _documented_variable_names()
    assert documented, "read zero names out of env.example, so this arm is vacuous"

    undocumented: dict[str, list[str]] = {}
    for name in ("production", "develop"):
        entry = _require(name)
        for service in ("search-agent-api", "search-agent-web"):
            live = _service_variable_names(service, entry)
            assert live, (
                f"read zero variable names for {service} in {entry['project']}, "
                f"so the comparison below would pass against anything"
            )
            missing = sorted(live - documented)
            if missing:
                undocumented[f"{entry['project']}/{service}"] = missing

    assert not undocumented, (
        f"variables are set on a deployed service and absent from env.example: "
        f"{undocumented}. Anyone provisioning a new deployment from the file "
        f"this repository tells them to provision from would omit them. This is "
        f"finding F-4.15-01 recurring, and it is the reason this arm exists."
    )


def test_p8_ci_runs_on_the_production_line() -> None:
    """A merge to `production` runs the gates.

    Measured before this was written: `on: pull_request:` already carries NO
    branch filter, so a pull request into `production` runs every gate today with no
    change at all. What was missing is the POST-merge run. This arm therefore
    pins the push trigger and, separately, pins that the pull_request trigger
    stays unfiltered, because "helpfully" adding a branch list there would
    silently stop release pull requests from being checked.
    """
    text = _CI_WORKFLOW.read_text()

    # The `on:` block, not the first paragraph. This file opens with a ~40 line
    # comment block explaining why it contains no shell, and the first version
    # of this arm parsed that instead and failed for the wrong reason. Left
    # recorded rather than quietly fixed: an arm that fails for a reason other
    # than its own property is indistinguishable from one that works, right up
    # until the property becomes true and the arm stays red.
    on_block = re.search(r"^on:\s*\n((?:[ \t]+.*\n|\n)*)", text, re.MULTILINE)
    assert on_block is not None, (
        f"no top-level `on:` block found in {_CI_WORKFLOW.name}; every parse "
        f"below would assert nothing"
    )
    # Comments are stripped BEFORE matching. The first version of this arm did
    # not, and the very comment added to `ci.yml` explaining why the
    # pull_request trigger is unfiltered sat between `push:` and `branches:`
    # and broke the arm's own regex. Recorded rather than quietly fixed,
    # because it is the same class as build phase 4.14's `:;#ruff check`: a
    # checker that treats `#` as ordinary text sees a structure that the tool
    # reading the file does not.
    trigger = "\n".join(
        line for line in on_block.group(1).splitlines() if not line.strip().startswith("#")
    )
    assert "pull_request" in trigger and "push" in trigger, (
        f"the `on:` block does not carry both triggers; the parse below would "
        f"assert nothing. Read: {trigger!r}"
    )

    push_block = re.search(r"push:\s*\n\s*branches:\s*\[([^\]]*)\]", trigger)
    assert push_block is not None, (
        "no `push: branches: [...]` block found in the CI workflow, so this "
        "arm cannot tell which branches trigger a post-merge run"
    )
    branches = {b.strip() for b in push_block.group(1).split(",") if b.strip()}
    assert "production" in branches, (
        f"CI's push trigger covers {sorted(branches)} and not `production`, so "
        f"merging a release to the production line would run no gates at all."
    )
    assert "develop" in branches, (
        f"CI's push trigger lost `develop`: {sorted(branches)}. Adding the "
        f"production line must not remove the integration line."
    )

    assert not re.search(r"pull_request:\s*\n\s*branches:", text), (
        "the pull_request trigger has gained a branch filter. It is unfiltered "
        "on purpose, which is what makes a release pull request into `production` "
        "run every gate. Narrowing it would silently stop that."
    )


# ---------------------------------------------------------------------------
# P9: the release workflow, structural and always run
# ---------------------------------------------------------------------------

_RELEASE_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "release.yml"


def test_p9_the_release_workflow_holds_the_no_shell_and_no_injection_rules() -> None:
    """The release workflow obeys the two rules build phase 4.14 paid for.

    Rule one, no shell in the workflow. Build phase 4.14 was defeated twice
    trying to verify inline shell by matching strings in a `run:` body, the
    second time by `run: ":;#ruff check"`, which executes nothing while reading
    as if it runs ruff. The fix was structural: a step body must EQUAL a script
    path, because a whole-string equality has no room for a comment or a second
    command. This arm holds `release.yml` to the same rule `ci.yml` follows,
    rather than trusting that whoever wrote it remembered.

    Rule two, no `github.event` interpolation. A commit subject is chosen by
    whoever opens a pull request, and `${{ }}` splices its text into the shell
    before bash parses it. This workflow reads commit text with `git log`
    instead, where it is data on a pipe. The arm forbids the sink outright
    rather than trying to judge whether a particular use is safe, which is the
    same "change what is being checked" move that ended build phase 4.14's
    losing streak.
    """
    text = _RELEASE_WORKFLOW.read_text()

    runs = re.findall(r"^\s*run:\s*(.+?)\s*$", text, re.MULTILINE)
    assert runs, (
        f"no `run:` steps found in {_RELEASE_WORKFLOW.name}; every assertion "
        f"below would pass against a file that does nothing"
    )
    for body in runs:
        assert re.fullmatch(r"\.github/release/[a-z0-9_]+\.sh", body), (
            f"a release step's `run:` is {body!r}, which is not exactly one "
            f"script path under .github/release/. Build phase 4.14 measured "
            f"that a `run:` body containing shell cannot be checked by matching "
            f"strings inside it, so the rule is a whole-string equality."
        )

    # Check the EXPRESSIONS, not the raw text. The first version of this arm
    # searched the whole file for the sink names and failed on the workflow's
    # own comment explaining why it does not use them. That is the build phase
    # 4.14 lesson arriving from the other direction: there, a checker treated a
    # comment as code and passed something dangerous; here it treated a comment
    # as code and failed something safe. Either way, a checker that cannot tell
    # comment from code is measuring the wrong thing.
    expressions = re.findall(r"\$\{\{(.*?)\}\}", text, re.DOTALL)
    for expression in expressions:
        for sink in (
            "github.event.head_commit",
            "github.event.commits",
            "github.event.pull_request",
            "github.head_ref",
            "github.event.issue",
            "github.event.comment",
        ):
            assert sink not in expression, (
                f"{_RELEASE_WORKFLOW.name} interpolates {sink} in "
                f"${{{{{expression.strip()}}}}}, which is attacker-influenced "
                f"text spliced into the shell before bash parses it. Read the "
                f"value with `git log` inside the script instead, where it is "
                f"data rather than code."
            )

    # The arm must be able to see expressions at all, or the loop above is a
    # no-op that passes on any file. This workflow genuinely has some.
    assert expressions, (
        f"found no ${{{{ }}}} expressions in {_RELEASE_WORKFLOW.name}, so the "
        f"injection check above scanned nothing"
    )

    # Every script the workflow names must exist and be executable. A workflow
    # naming a missing script fails at run time, on the production line, after
    # a release has already been merged, which is the worst place to find out.
    for body in runs:
        script = _REPO_ROOT / body
        assert script.is_file(), f"{body} is named by the workflow and does not exist"
        assert script.stat().st_mode & 0o111, f"{body} exists but is not executable"


def test_p9b_the_release_scripts_themselves_hold_their_safety_rules() -> None:
    """P9 checks the workflow. This checks the scripts the workflow runs.

    ADDED 2026-08-27 after finding F-4.15-A-13. P9 asserts that `release.yml`
    contains no shell and interpolates no `github.event` value, and then never
    looks at the shell it delegates to. The workflow having no shell is not a
    safety property on its own: it MOVED the shell into four scripts, and an
    unchecked script is exactly where the shell went.

    The gap mattered because the workflow's whole security argument is that
    commit text reaches the scripts as data through `git log` rather than as
    code through `${{ }}`. Nothing was checking the second half of that
    sentence, which is the half that lives in the scripts.

    Three properties, each chosen because it is a real failure this phase
    already had or nearly had:

    1. `set -euo pipefail`. Two of these scripts push to a branch and publish a
       permanent tag; a script that continues past a failed command does so
       holding write access to the production line.
    2. No `${{` anywhere. A script is not a workflow and GitHub does not expand
       expressions inside it, so a `${{ }}` in a script is either dead text or
       a sign someone copied workflow syntax into the wrong file.
    3. Every script parses under `bash -n`. Three of the four shipped
       non-executable earlier in this phase, which P9 caught; a syntax error is
       the same class of "it would have failed at release time, on the
       production line, after the merge".
    """
    scripts = sorted((_REPO_ROOT / ".github" / "release").glob("*.sh"))
    assert len(scripts) >= 4, (
        f"expected the four release scripts, found {len(scripts)}. This arm "
        f"would otherwise pass by checking almost nothing."
    )

    for script in scripts:
        text = script.read_text()
        relative = script.relative_to(_REPO_ROOT)

        assert "set -euo pipefail" in text, (
            f"{relative} does not `set -euo pipefail`. It runs with write "
            f"access to the production line, so continuing past a failed "
            f"command is how a half-finished release gets published."
        )
        # Comments stripped BEFORE the check, for the second time in this
        # file. The first version failed on the scripts' own comments
        # explaining why they do not use workflow interpolation. That is the
        # same mistake P8 made and the same one build phase 4.14 was defeated
        # by from the other side: a checker that cannot tell comment from code
        # is measuring the wrong text, whether it then passes something unsafe
        # or fails something safe.
        code = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )
        assert "${{" not in code, (
            f"{relative} contains a `${{{{` expression in executable code. "
            f"GitHub does not expand those inside a script, so it is either "
            f"dead text or workflow syntax copied into the wrong file."
        )

        parsed = subprocess.run(
            ["bash", "-n", str(script)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert parsed.returncode == 0, (
            f"{relative} does not parse: {parsed.stderr.strip()[:300]}"
        )


# ---------------------------------------------------------------------------
# P10: each web app is actually wired to its own API
# ---------------------------------------------------------------------------


@requires_live
def test_p10_each_web_app_is_built_against_its_own_api() -> None:
    """The shipped JavaScript bundle points at that deployment's API.

    ADDED 2026-08-27 after finding F-4.15-A-14, a CRITICAL, and this arm is the
    clearest illustration in the phase of why an adversary round is not
    optional.

    The develop web app was live, returned 200, and could not reach any API at
    all. `VITE_API_BASE_URL` is a COMPILE-TIME substitution: Vite bakes it into
    the bundle at build time, so setting it afterwards changes nothing that
    ships. The develop bundle therefore carried the local development fallback
    `http://127.0.0.1:8000`, which in a visitor's browser means the visitor's
    own machine. The deployment satisfied every acceptance criterion this phase
    had written, including "all four live surfaces answer 200", while being
    useless for the single thing the phase exists to provide.

    NOTHING CAUGHT IT, and that is the transferable part. P1 compared the two
    `web` values as FIXTURE STRINGS and never issued one HTTP request to either
    web URL. P4 tested CORS at the API. Every arm was about the API or about
    configuration, and the web app was only ever asserted to exist. A gate can
    be thorough about everything it looks at and blind to a whole surface.

    So this arm downloads the bundle the browser would download and reads the
    hosts out of it. Two assertions, and the second is the one that fails on a
    stale build:

    1. The deployment's own API host appears in the bundle.
    2. No loopback address appears in it, since a loopback in shipped
       JavaScript means the visitor's own machine.
    """
    for name in ("develop", "production"):
        entry = _require(name)
        web = entry["web"].rstrip("/")
        api_host = entry["api"].rstrip("/")

        with _client() as client:
            index = client.get(web + "/")
            assert index.status_code == 200, (
                f"{name}'s web app returned {index.status_code} for its index, "
                f"so there is no bundle to inspect"
            )
            bundles = re.findall(r'src="(/assets/[^"]+\.js)"', index.text)
            assert bundles, (
                f"{name}'s index.html references no /assets/*.js bundle, so "
                f"this arm cannot read what the app was built against. Index "
                f"was {len(index.text)} bytes."
            )

            found_api = False
            found_loopback: list[str] = []
            for path in bundles:
                asset = client.get(web + path)
                assert asset.status_code == 200, (
                    f"{name} serves an index referencing {path} and that asset "
                    f"returns {asset.status_code}"
                )
                if api_host in asset.text:
                    found_api = True
                for loopback in ("127.0.0.1", "localhost:"):
                    if loopback in asset.text:
                        found_loopback.append(f"{path} contains {loopback}")

        assert found_api, (
            f"{name}'s bundle does not contain its own API host {api_host}. "
            f"VITE_API_BASE_URL is baked in at BUILD time, so this means the "
            f"bundle was built before the variable was set and the app is "
            f"talking to whatever the fallback is. Rebuild the service; "
            f"setting the variable alone does not change what ships."
        )
        assert not found_loopback, (
            f"{name}'s shipped JavaScript contains a loopback address, which "
            f"in a visitor's browser means the VISITOR'S OWN machine: "
            f"{found_loopback}. This is finding F-4.15-A-14."
        )


@requires_live
def test_p3c_a_token_signed_with_the_other_key_is_refused_for_a_user_that_exists() -> None:
    """The direct arm. No proxy, and it distinguishes the two 401s.

    ADDED 2026-08-28 after finding F-4.15-GC-01, which is the FOURTH iteration
    on one property in this phase and the reason the whole sequence is worth
    reading before writing a gate anywhere else.

    The history, because each step looked like a fix and the first three were
    not:

    - The original P3 minted a token on develop, presented it to production,
      and read the 401 as proof the keys differ. It was not: with separate
      databases the 401 arrives on the MISSING USER ROW
      (`auth/dependencies.py:108-110`) whether the key is shared or not. That
      was F-4.15-J-04, a critical.
    - It was split into P3a, which corrupts a signature, and P3b, which
      compares the configured values as digests. F-4.15-GC-01 showed the PAIR
      still proves nothing about the composition: P3a proves each deployment
      verifies with the same key IT MINTS WITH, whatever that key is, and never
      reads a variable; P3b reads variables and never sends a request. Nothing
      tied the key the running process holds to the value compared.
    - The concrete state that made both green while the property was false: two
      containers holding the same signing key while the two CONFIGURED values
      differ, which is what an environment duplicate followed by rotating one
      side produces before the other side redeploys. That is not hypothetical
      in this phase; it is close to what happened at F-4.15-04.

    THIS ARM CLOSES IT by removing every proxy at once. It creates a real
    account on production and reads that account's REAL user id, so the subject
    exists in production's database. Then it mints a token for that id signed
    with DEVELOP's key and presents it to production. A 401 can now only mean
    the signature was rejected, because the row is present. The positive
    control mints the same id with PRODUCTION's own key and requires 200, which
    proves the 401 is about the key rather than about anything else in the
    request.

    In one line: the previous arms could not tell "wrong key" from "unknown
    user". This one makes the user known, so only the key is left.

    The token is minted here rather than fetched, using this repository's own
    `mint_access_token` contract read from `auth/tokens.py`: HS256 over
    `user_id`, `iat` and `exp`. Minting locally is what makes it possible to
    sign a chosen subject with a chosen key, which no endpoint will do for us.
    """
    prod = _require("production")
    prod_api = prod["api"].rstrip("/")

    prod_secret = _signing_key_for("production")
    dev_secret = _signing_key_for("develop")
    assert prod_secret != dev_secret, (
        "the two deployments hold the same configured signing key, so this arm "
        "cannot distinguish them. That is P3b's finding, not this one."
    )

    email, password = _throwaway_credentials()
    with _client() as client:
        created = client.post(
            prod_api + "/auth/signup", json={"email": email, "password": password}
        )
        assert created.status_code == 201, (
            f"could not create an account on production: {created.status_code} "
            f"{created.text[:200]}"
        )
        logged_in = client.post(
            prod_api + "/auth/login", json={"email": email, "password": password}
        )
        assert logged_in.status_code == 200, (
            f"could not log in on production: {logged_in.status_code}"
        )
        real_token = logged_in.json()["access_token"]

        me = client.get(
            prod_api + "/auth/me", headers={"Authorization": f"Bearer {real_token}"}
        )
        assert me.status_code == 200, (
            f"could not read the account back from production: {me.status_code}"
        )

        # PRODUCTION'S OWN CLAIMS, re-signed. Not a claim set built here.
        #
        # The first version of this arm constructed its own claims, and the
        # positive control below caught it: production refused a token this
        # test minted with production's own key, so the cross-key assertion
        # would have proved nothing about keys. Diagnosed rather than worked
        # around, and the diagnosis is why this reads the way it does. A real
        # production token verified against the key read from Railway, so the
        # key was right; a re-signed copy of that token's exact claims was
        # accepted; only a hand-built claim set was refused.
        #
        # So the arm stopped building claims. It takes the claim set
        # production itself minted, without inspecting or rewriting a single
        # value, and re-signs it. That makes the KEY the only variable in the
        # comparison, which is the whole point, and it cannot drift when the
        # token contract changes: `decode_access_token` enforces required
        # claims and a 15-minute ceiling independently of the minter
        # (F-1.1-09), and a claim set assembled here would have to track all
        # of it forever.
        claims = jwt.decode(real_token, options={"verify_signature": False})
        assert "user_id" in claims, (
            f"production's own token carries no user_id claim, so re-signing "
            f"it proves nothing about a user that exists: {sorted(claims)}"
        )

        # Positive control FIRST. If a token this test re-signs with
        # production's own key is not accepted, the rejection below says
        # nothing about keys.
        own_key = jwt.encode(claims, prod_secret, algorithm="HS256")
        accepted = client.get(
            prod_api + "/auth/me", headers={"Authorization": f"Bearer {own_key}"}
        )
        assert accepted.status_code == 200, (
            f"production refused a token carrying its OWN claims re-signed "
            f"with its OWN key ({accepted.status_code}). Either the key read "
            f"from Railway is not the key the running process holds, which is "
            f"itself the finding, or the token expired between minting and "
            f"this request. Either way the cross-key rejection below would "
            f"prove nothing. Response: {accepted.text[:200]}"
        )

        other_key = jwt.encode(claims, dev_secret, algorithm="HS256")
        crossed = client.get(
            prod_api + "/auth/me", headers={"Authorization": f"Bearer {other_key}"}
        )

    assert crossed.status_code == 401, (
        f"production ACCEPTED a token for one of its own users signed with "
        f"DEVELOP's key ({crossed.status_code}). The two deployments verify "
        f"with the same key. This cannot be the missing-row 401 that defeated "
        f"the original P3, because the positive control above proved this exact "
        f"user id is accepted when the token is signed with production's key."
    )
