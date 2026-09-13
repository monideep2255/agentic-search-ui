"""Pins the opt-in real-model mode of `tests/e2e_support/mock_llm_backend.py`
(fix set 6 item 6.1, requirement D3).

The mode itself can only be exercised end to end by spending real budget, so
what is pinned here is everything that decides WHETHER real money is spent and
WHETHER a caller can tell which mode they got:

    - the flag unset means the fakes are installed, exactly as before;
    - the flag set with a required variable missing refuses at startup, naming
      the VARIABLE NAME and never a value;
    - the `.env` loader never overrides a value already in the environment;
    - `/__e2e__/mode` reports "fake" by default.

Every test drives a temporary `.env` through `monkeypatch`, never the
repository's own. A test that read the real file would pass or fail depending
on a developer's credentials, which is the opposite of a pin.

WHAT THIS FILE DOES NOT COVER, stated rather than left to be discovered: it
never starts a real model call, never reaches the network, and therefore
cannot prove that a real answer arrives. That is
`frontend/e2e/real-answer.spec.ts`'s job, and it only runs when someone opts
in to spending budget.

Depends on:
    - tests.e2e_support.mock_llm_backend (the module under test)
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.e2e_support import mock_llm_backend as backend

_REQUIRED = backend._REAL_MODEL_REQUIRED_ENV


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Give each test its own `os.environ`.

    `_apply_env_defaults` calls `os.environ.setdefault`, which monkeypatch
    cannot undo because it never saw the write. Without this, one test in this
    file would leave AUTH_SECRET and USER_DB_URL set for every test that runs
    after it, anywhere in the suite. Swapping the mapping itself is undone by
    monkeypatch, and both `monkeypatch.setenv` and python-dotenv resolve
    `os.environ` at call time, so they write into the copy.
    """
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setenv("PORT", "8931")
    yield


def _set_all_required(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give every required variable a placeholder so one can be removed."""
    for name in _REQUIRED:
        monkeypatch.setenv(name, f"placeholder-for-{name.lower()}")


def _stub_uvicorn(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Replace `uvicorn` so `main` returns instead of serving forever."""
    served: list[object] = []
    stub = type("_UvicornStub", (), {"run": staticmethod(lambda app, **_: served.append(app))})()
    monkeypatch.setitem(sys.modules, "uvicorn", stub)
    return served


class TestFlagParsing:
    def test_absent_flag_is_fake_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(backend._REAL_MODEL_ENV_FLAG, raising=False)
        assert backend.real_model_mode_enabled() is False

    @pytest.mark.parametrize("value", ["", "0", "true", "yes", "2", "1 "])
    def test_only_the_exact_string_one_opts_in(
        self, monkeypatch: pytest.MonkeyPatch, value: str
    ) -> None:
        """An opt-in that also fires on "0" or "false" is not an opt-in."""
        monkeypatch.setenv(backend._REAL_MODEL_ENV_FLAG, value)
        assert backend.real_model_mode_enabled() is False

    def test_one_opts_in(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(backend._REAL_MODEL_ENV_FLAG, "1")
        assert backend.real_model_mode_enabled() is True


class TestEnvDefaults:
    def test_fake_mode_applies_every_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in backend._ENV_DEFAULTS:
            monkeypatch.delenv(name, raising=False)

        backend._apply_env_defaults()

        for name, value in backend._ENV_DEFAULTS.items():
            assert os.environ[name] == value

    def test_real_mode_skips_the_fake_path_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The excluded four must stay ABSENT, or the startup check is vacuous:
        the gate would be satisfied by values this file set itself."""
        for name in backend._ENV_DEFAULTS:
            monkeypatch.delenv(name, raising=False)

        backend._apply_env_defaults(real_model=True)

        for name in backend._REAL_MODEL_EXCLUDED_DEFAULTS:
            assert name not in os.environ, f"{name} was applied in real-model mode"
        # POPULATE-CHECK: the loop above would also pass if NOTHING had been
        # applied, which is a different defect wearing the same green.
        assert os.environ["ANON_DAILY_RUN_CAP"] == backend._ENV_DEFAULTS["ANON_DAILY_RUN_CAP"]

    def test_the_three_tier_variables_are_both_excluded_and_required(self) -> None:
        for name in ("GUARD_MODEL", "PLAN_MODEL", "SYNTH_MODEL"):
            assert name in backend._REAL_MODEL_EXCLUDED_DEFAULTS
            assert name in backend._REAL_MODEL_REQUIRED_ENV


class TestDotenvLoader:
    def test_never_overrides_an_existing_environment_value(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        """The load-bearing property. Playwright hands this process its own
        PORT; a `.env` that won would move the backend off the port the suite
        waits on."""
        dotenv = tmp_path / ".env"
        dotenv.write_text(
            "# a comment line\n"
            "\n"
            "PORT=9999\n"
            'S3_TEST_QUOTED="from-dotenv"\n'
            "S3_TEST_FRESH=from-dotenv\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(backend, "_REPO_ROOT", tmp_path)
        monkeypatch.setenv("PORT", "8931")
        monkeypatch.delenv("S3_TEST_QUOTED", raising=False)
        monkeypatch.delenv("S3_TEST_FRESH", raising=False)

        assert backend._load_repo_dotenv() is True

        assert os.environ["PORT"] == "8931", "the .env overrode an explicit environment value"
        # POPULATE-CHECK: proves the file was genuinely read, so the assertion
        # above cannot pass merely because nothing happened.
        assert os.environ["S3_TEST_FRESH"] == "from-dotenv"
        assert os.environ["S3_TEST_QUOTED"] == "from-dotenv", "matching quotes were not stripped"

    def test_a_missing_dotenv_is_reported_not_raised(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setattr(backend, "_REPO_ROOT", tmp_path)
        assert backend._load_repo_dotenv() is False


class TestMissingRequiredEnv:
    @pytest.mark.parametrize("missing", _REQUIRED)
    def test_each_required_variable_is_reported_by_name(
        self, monkeypatch: pytest.MonkeyPatch, missing: str
    ) -> None:
        _set_all_required(monkeypatch)
        monkeypatch.delenv(missing, raising=False)

        assert backend._missing_real_model_env() == [missing]

    def test_a_blank_value_counts_as_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_all_required(monkeypatch)
        monkeypatch.setenv("OPENROUTER_API_KEY", "   ")

        assert backend._missing_real_model_env() == ["OPENROUTER_API_KEY"]

    def test_nothing_missing_when_all_are_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_all_required(monkeypatch)
        assert backend._missing_real_model_env() == []

    def test_startup_refuses_and_names_the_variable_without_its_value(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A run that cannot reach a model must say which variable is missing,
        and must never print a value (`ai-security-standards.md`)."""
        monkeypatch.setenv(backend._REAL_MODEL_ENV_FLAG, "1")
        monkeypatch.setattr(backend, "_REPO_ROOT", tmp_path)  # no .env to load
        _set_all_required(monkeypatch)
        monkeypatch.setenv("GRAPH_QUERY_TOKEN", "")
        # Would otherwise be reached first and probe a real database.
        monkeypatch.setattr(backend, "_can_connect_to_user_db", lambda: True)
        # Proves no value leaks: a distinctive value on a variable that IS set.
        monkeypatch.setenv("OPENROUTER_API_KEY", "sentinel-value-must-not-be-printed")

        with pytest.raises(SystemExit) as exit_info:
            backend.main()

        assert exit_info.value.code == 1
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "GRAPH_QUERY_TOKEN" in combined
        assert "sentinel-value-must-not-be-printed" not in combined
        for name in _REQUIRED:
            if name != "GRAPH_QUERY_TOKEN":
                assert name not in combined, f"{name} is set but was reported missing"


class TestPatchingAndModeRoute:
    def test_fake_mode_installs_the_fakes(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        """The default path is unchanged: `main` reaches `_patch_litellm` and
        reads no `.env`."""
        monkeypatch.delenv(backend._REAL_MODEL_ENV_FLAG, raising=False)
        monkeypatch.setattr(backend, "_REPO_ROOT", tmp_path)
        monkeypatch.setattr(backend, "_can_connect_to_user_db", lambda: True)

        patched: list[bool] = []
        loaded: list[bool] = []
        monkeypatch.setattr(backend, "_patch_litellm", lambda: patched.append(True))
        monkeypatch.setattr(backend, "_load_repo_dotenv", lambda: bool(loaded.append(True)))
        monkeypatch.setattr(backend, "_build_app", lambda **kwargs: kwargs)
        served = _stub_uvicorn(monkeypatch)

        backend.main()

        assert patched == [True], "the fakes were not installed on the default path"
        assert loaded == [], "the default path read a .env file"
        assert served == [{"real_model": False}]

    def test_real_mode_skips_the_fakes(self, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
        monkeypatch.setenv(backend._REAL_MODEL_ENV_FLAG, "1")
        monkeypatch.setattr(backend, "_REPO_ROOT", tmp_path)
        monkeypatch.setattr(backend, "_can_connect_to_user_db", lambda: True)
        _set_all_required(monkeypatch)

        patched: list[bool] = []
        monkeypatch.setattr(backend, "_patch_litellm", lambda: patched.append(True))
        monkeypatch.setattr(backend, "_build_app", lambda **kwargs: kwargs)
        served = _stub_uvicorn(monkeypatch)

        backend.main()

        assert patched == [], "real-model mode installed the model fakes"
        assert served == [{"real_model": True}]

    def test_mode_route_reports_fake_by_default(self) -> None:
        """Over real HTTP, so the route is proven wired, not just present.

        Only ONE app is ever built in this file: `_build_app` extends the one
        module-level `app` object, and Starlette refuses `add_middleware` after
        that app has served a request, so a second build would raise. The other
        arm is covered by `test_mode_payload_names_each_arm` below.
        """
        with TestClient(backend._build_app()) as client:
            response = client.get("/__e2e__/mode")

        assert response.status_code == 200
        assert response.json() == {"model": "fake"}

    def test_mode_payload_names_each_arm(self) -> None:
        assert backend.mode_payload(real_model=True) == {"model": "real"}
        assert backend.mode_payload(real_model=False) == {"model": "fake"}
