"""Unit tests for `synthesis.freshness`. See that module's docstring for
the Section 7.1/7.3/7.4 rules these enforce."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from system_03_search_agent.synthesis.freshness import (
    AsOfMarker,
    graph_snapshot_date_from_version,
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


# ---------------------------------------------------------------------------
# T-3.4-06: graph_snapshot_date_from_version. See the function's own
# docstring for why this exists: the running default
# (`cypher_query._DEFAULT_GRAPH_SNAPSHOT_VERSION`, "ncbi_kg_v1_2026-04-22")
# is not itself a bare date, so `is_stale` cannot be called against it
# directly via the pre-existing `_parse_date` contract alone.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        # 1. A bare date or ISO timestamp: _parse_date's existing,
        # unmodified contract, unchanged behavior.
        ("2026-04-22", "2026-04-22"),
        ("2026-04-22T12:34:56Z", "2026-04-22"),
        # 2. The real, live-confirmed running default: a trailing date on
        # a Hetzner disaster-recovery snapshot label.
        ("ncbi_kg_v1_2026-04-22", "2026-04-22"),
        # 3. A different name/version prefix, same trailing-date shape.
        ("ncbi_kg_v2_2026-07-01", "2026-07-01"),
        # 4. A date embedded but not trailing: last-resort "anywhere in
        # the string" search still finds it.
        ("2026-04-22_backup_manual", "2026-04-22"),
    ],
)
def test_graph_snapshot_date_from_version_extracts_a_real_date(
    version: str, expected: str
) -> None:
    assert graph_snapshot_date_from_version(version) == expected


@pytest.mark.parametrize(
    "version",
    [
        "prod-snapshot-42",  # no date anywhere: an opaque label
        "ncbi_kg_v1",  # the naming convention with the date dropped
        "",
        "not-a-date-at-all",
    ],
)
def test_graph_snapshot_date_from_version_returns_none_not_a_fabricated_date(
    version: str,
) -> None:
    """No date anywhere in the string: None, never a guess."""
    assert graph_snapshot_date_from_version(version) is None


def test_graph_snapshot_date_from_version_feeds_is_stale_directly() -> None:
    """The whole point of this function: its output is a valid
    `is_stale` argument, proven end to end rather than just type-checked.
    """
    old_version = f"ncbi_kg_v1_{_days_ago(45)}"
    recent_version = f"ncbi_kg_v1_{_days_ago(5)}"

    old_date = graph_snapshot_date_from_version(old_version)
    recent_date = graph_snapshot_date_from_version(recent_version)
    assert old_date is not None and recent_date is not None

    assert is_stale("volatile", old_date) is True
    assert is_stale("volatile", recent_date) is False
