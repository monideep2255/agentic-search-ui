"""Tests for task_tiers.py: the call-site to tier/provider lookup table
(build phase 8.2, card 8).

Pure data plus a lookup function; no monkeypatching needed anywhere.
"""

from __future__ import annotations

import pytest

from system_03_search_agent.harness.task_tiers import (
    ALL_TASK_TIERS,
    UnknownCallSiteError,
    task_tier_for,
)

# The call sites one of the three tiers serves.
_TIER_CALL_SITES = {
    "guardrail.attack_classification",
    "think.ask_or_proceed",
    "think.classification",
    "act.cypher_generation_fallback",
    "act.reader_pass",
    "write.answer_synthesis",
    "write.repair_pass",
}

# The classification decisions whose model CLASSIFIER_PROVIDER chooses: the
# sentence check since build phase 8.6 (T-8.6-02), the five decision points
# of build phase 8.2 and the two build phase 8.6 wired (fix round, F-8.6-J16).
_CLASSIFIER_CALL_SITES = {
    "write.sentence_check",
    "guardrail.relevancy",
    "think.ask_back",
    "plan.literature",
    "think.recent_years",
    "plan.resource",
    "guardrail.injection",
    "think.asks_features",
}


def test_all_fifteen_call_sites_are_present() -> None:
    names = {entry.call_site for entry in ALL_TASK_TIERS}
    assert names == _TIER_CALL_SITES | _CLASSIFIER_CALL_SITES
    assert len(ALL_TASK_TIERS) == 15


def test_table_is_sorted_by_call_site() -> None:
    names = [entry.call_site for entry in ALL_TASK_TIERS]
    assert names == sorted(names)


def test_every_classifier_decision_carries_the_classifier_tier() -> None:
    for name in _CLASSIFIER_CALL_SITES:
        assert task_tier_for(name).tier == "classifier"


def test_tier_call_sites_carry_a_real_tier_never_classifier() -> None:
    for name in _TIER_CALL_SITES:
        assert task_tier_for(name).tier in {"guard", "plan", "synth"}


def test_unknown_call_site_raises_a_named_error() -> None:
    with pytest.raises(UnknownCallSiteError, match="unknown call site"):
        task_tier_for("nonexistent.call_site")
