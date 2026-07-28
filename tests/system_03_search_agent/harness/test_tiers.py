"""Tests for tier resolution (T-2.0-01).

Covers resolve_model()'s env-set and env-unset-fallback paths, TierContext's
resolve-once-per-query caching (mid-query env mutation must not change an
already-resolved value), the invalid-tier typed error, and a repo-wide scan
proving no model id is hardcoded outside harness/tiers.py's one app-config
default table (system-design-patterns.md pattern 11).
"""

import ast
import re
from pathlib import Path

import pytest

from system_03_search_agent.harness.tiers import (
    _DEFAULT_MODELS,
    TierContext,
    UnknownTierError,
    resolve_model,
)

_TIERS = ("guard", "plan", "synth")

# The env var names are the public contract (env.example, Section 3.1), not
# an implementation detail: named here directly rather than imported from
# the module's private mapping.
_ENV_VAR_BY_TIER = {"guard": "GUARD_MODEL", "plan": "PLAN_MODEL", "synth": "SYNTH_MODEL"}

# --- resolve_model(): env var set ---


@pytest.mark.parametrize("tier", _TIERS)
def test_resolve_model_valid_input_env_set_returns_env_value(
    tier: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ENV_VAR_BY_TIER[tier], "some-provider/some-model")
    assert resolve_model(tier) == "some-provider/some-model"


# --- resolve_model(): env var unset or empty falls back to the default table ---


@pytest.mark.parametrize("tier", _TIERS)
def test_resolve_model_missing_input_env_unset_falls_back_to_default(
    tier: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(_ENV_VAR_BY_TIER[tier], raising=False)
    assert resolve_model(tier) == _DEFAULT_MODELS[tier]


@pytest.mark.parametrize("tier", _TIERS)
def test_resolve_model_invalid_input_env_empty_string_falls_back_to_default(
    tier: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ENV_VAR_BY_TIER[tier], "")
    assert resolve_model(tier) == _DEFAULT_MODELS[tier]


# --- resolve_model(): invalid tier ---


def test_resolve_model_invalid_input_unknown_tier_raises_before_any_lookup() -> None:
    with pytest.raises(UnknownTierError):
        resolve_model("orchestrator")  # type: ignore[arg-type]


def test_resolve_model_missing_input_none_tier_raises() -> None:
    with pytest.raises(UnknownTierError):
        resolve_model(None)  # type: ignore[arg-type]


def test_resolve_model_missing_input_empty_string_tier_raises() -> None:
    with pytest.raises(UnknownTierError):
        resolve_model("")  # type: ignore[arg-type]


# --- TierContext: resolve-once-per-query caching ---


@pytest.mark.parametrize("tier", _TIERS)
def test_tier_context_valid_input_caches_first_resolution(
    tier: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_ENV_VAR_BY_TIER[tier], "some-provider/first-resolution")
    context = TierContext()
    assert context.resolve(tier) == "some-provider/first-resolution"


def test_tier_context_valid_input_mid_query_env_mutation_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tier's resolved model is fetched once at query start and held for
    the query's duration: mutating the env var mid-query must not change
    an already-resolved value (system-design-patterns.md pattern 11).
    """
    monkeypatch.setenv("PLAN_MODEL", "some-provider/original-model")
    context = TierContext()
    first = context.resolve("plan")

    monkeypatch.setenv("PLAN_MODEL", "some-provider/mutated-model")
    second = context.resolve("plan")

    assert first == "some-provider/original-model"
    assert second == "some-provider/original-model"
    assert first == second


def test_tier_context_valid_input_two_contexts_resolve_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two separate TierContext instances must not share cached state: a
    fresh context for a new query re-reads the (now current) environment.
    """
    monkeypatch.setenv("GUARD_MODEL", "some-provider/context-one-model")
    first_context = TierContext()
    assert first_context.resolve("guard") == "some-provider/context-one-model"

    monkeypatch.setenv("GUARD_MODEL", "some-provider/context-two-model")
    second_context = TierContext()
    assert second_context.resolve("guard") == "some-provider/context-two-model"


def test_tier_context_invalid_input_unknown_tier_raises() -> None:
    context = TierContext()
    with pytest.raises(UnknownTierError):
        context.resolve("orchestrator")  # type: ignore[arg-type]


# --- repo-wide scan: no hardcoded model id outside the one default table ---
#
# A plain substring/line grep for a "/" false-positives on ordinary prose
# ("request/response", "mint/decode/generate", "alembic/versions/...") that
# already exists throughout this repo's docstrings and comments. Scanning
# only the string *constants* the AST actually parses, and requiring the
# ENTIRE constant (not a substring of a longer sentence) to match a bare
# provider/model slug shape, keys the check to what the acceptance
# criterion actually means: a literal model id value, not a slash anywhere
# in a file.

_MODEL_ID_SHAPE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.\-]*/[a-zA-Z0-9][a-zA-Z0-9_.\-]*$")
_SRC_ROOT = Path(__file__).resolve().parents[3] / "src" / "system_03_search_agent"
_TIERS_FILE = _SRC_ROOT / "harness" / "tiers.py"


def _iter_string_constants(path: Path) -> list[tuple[int, str]]:
    """Return (line, value) for every string constant an AST parse finds.

    This deliberately excludes docstrings and comments from being matched
    as "just more text": a docstring IS a string constant to `ast`, so a
    short, single-line docstring shaped like a model id would still be
    caught. What it avoids is treating one line of a long, multi-sentence
    docstring or comment as if it were a standalone literal, since the
    fullmatch in the caller requires the ENTIRE constant, not one line of
    a bigger string, to look like a model id.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_model_id_shape_regex_matches_known_default_values() -> None:
    """Positive control: prove the scan regex below is not dead code by
    checking it actually matches the real default table's values.
    """
    for model_id in _DEFAULT_MODELS.values():
        assert _MODEL_ID_SHAPE.fullmatch(model_id) is not None


def test_model_id_shape_regex_rejects_ordinary_prose_with_slashes() -> None:
    """Negative control: ordinary multi-word prose containing a "/" (the
    shape already present elsewhere in this repo's docstrings, e.g.
    "request/response") must not be mistaken for a model id.
    """
    prose_examples = [
        "request/response model",
        "mint/decode/generate/hash/verify",
        "alembic/versions/0001_user_data_schema.py",
        "FastAPI application entry point for the web/SSE adapter.",
    ]
    for prose in prose_examples:
        assert _MODEL_ID_SHAPE.fullmatch(prose) is None


def test_no_model_id_shaped_string_outside_the_default_table() -> None:
    """system-design-patterns.md pattern 11: resolve_model() never
    hardcodes a model id anywhere outside the one app-config default
    table. A repo-wide scan of every string constant for a literal,
    OpenRouter-shaped provider/model slug must find matches only among
    harness/tiers.py's _DEFAULT_MODELS values, never inline in any other
    harness, node, or graph module.
    """
    allowed_values = set(_DEFAULT_MODELS.values())
    violations: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        for lineno, value in _iter_string_constants(path):
            if _MODEL_ID_SHAPE.fullmatch(value) is None:
                continue
            if path == _TIERS_FILE and value in allowed_values:
                continue
            violations.append(f"{path.relative_to(_SRC_ROOT)}:{lineno}: {value!r}")

    assert violations == [], (
        "model-id-shaped string found outside harness/tiers.py's "
        f"_DEFAULT_MODELS table: {violations}"
    )
