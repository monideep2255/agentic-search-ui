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

_EXISTING_CALL_SITES = {
    "guardrail.attack_classification",
    "think.ask_or_proceed",
    "think.classification",
    "act.cypher_generation_fallback",
    "act.reader_pass",
    "write.sentence_check",
    "write.answer_synthesis",
    "write.repair_pass",
}

_CLASSIFIER_DECISION_POINTS = {
    "guardrail.relevancy",
    "think.ask_back",
    "plan.literature",
    "think.recent_years",
    "plan.resource",
}


def test_all_thirteen_call_sites_are_present() -> None:
    names = {entry.call_site for entry in ALL_TASK_TIERS}
    assert names == _EXISTING_CALL_SITES | _CLASSIFIER_DECISION_POINTS
    assert len(ALL_TASK_TIERS) == 13


def test_table_is_sorted_by_call_site() -> None:
    names = [entry.call_site for entry in ALL_TASK_TIERS]
    assert names == sorted(names)


def test_the_five_classifier_decision_points_carry_the_classifier_tier() -> None:
    for name in _CLASSIFIER_DECISION_POINTS:
        assert task_tier_for(name).tier == "classifier"


def test_existing_call_sites_carry_a_real_tier_never_classifier() -> None:
    for name in _EXISTING_CALL_SITES:
        assert task_tier_for(name).tier in {"guard", "plan", "synth"}


def test_unknown_call_site_raises_a_named_error() -> None:
    with pytest.raises(UnknownCallSiteError, match="unknown call site"):
        task_tier_for("nonexistent.call_site")
