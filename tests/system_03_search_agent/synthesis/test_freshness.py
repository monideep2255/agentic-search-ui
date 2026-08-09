"""Unit tests for `synthesis.freshness`. See that module's docstring for
the Section 7.1/7.3/7.4 rules these enforce."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from system_03_search_agent.synthesis.freshness import (
    AsOfMarker,
    is_stale,
    prefer_live_for_currency,
    resolve_assembly,
)


def _days_ago(days: int) -> str:
    today = datetime.now(tz=UTC).date()
    return (today - timedelta(days=days)).isoformat()


@pytest.mark.parametrize(
    ("field_class", "age_days", "expected"),
    [
        ("volatile", 45, True),
        ("volatile", 5, False),
        ("volatile", 30, False),  # exactly at threshold: not yet stale
        ("volatile", 31, True),
        ("stable", 45, False),
        ("stable", 91, True),
        ("stable", 90, False),
    ],
)
def test_is_stale(field_class: str, age_days: int, expected: bool) -> None:
    assert is_stale(field_class, _days_ago(age_days)) is expected


def test_is_stale_accepts_a_full_iso_timestamp_not_only_a_bare_date() -> None:
    timestamp = f"{_days_ago(45)}T12:34:56Z"
    assert is_stale("volatile", timestamp) is True


def test_is_stale_raises_on_an_unparseable_date() -> None:
    with pytest.raises(ValueError):
        is_stale("volatile", "not-a-date")


def test_as_of_marker_requires_exactly_one_of_snapshot_or_fetched_at() -> None:
    AsOfMarker(citation_id="c1", graph_snapshot_version="2026-08-01")
    AsOfMarker(citation_id="c2", fetched_at="2026-08-09T00:00:00Z")

    with pytest.raises(ValueError):
        AsOfMarker(citation_id="c3")

    with pytest.raises(ValueError):
        AsOfMarker(
            citation_id="c4",
            graph_snapshot_version="2026-08-01",
            fetched_at="2026-08-09T00:00:00Z",
        )


def test_prefer_live_for_currency_never_drops_the_graph_value() -> None:
    resolution = prefer_live_for_currency(graph_value="old", live_value="new")
    assert resolution.current_value == "new"
    assert resolution.current_source == "live"
    assert resolution.also_cited == "old"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("GRCh38", "GRCh38"),
        ("grch38", "GRCh38"),
        ("GRCh37", "GRCh37"),
        ("hg19", "GRCh37"),
        ("hg38", "GRCh38"),
        ("GRCh_38", "GRCh38"),
        (None, None),
        ("", None),
        ("T2T-CHM13", None),
    ],
)
def test_resolve_assembly(raw: str | None, expected: str | None) -> None:
    assert resolve_assembly(raw) == expected
