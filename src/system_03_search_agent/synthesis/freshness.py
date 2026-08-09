"""Section 7: layer authority, freshness, and the as-of marker.

Three of Section 7's four rules live here as pure functions, deliberately
free of any citation-building or network-call code so they can be unit
tested without a live dependency and reused identically by every tool's own
citation builder:

    7.1 Live wins for currency. `prefer_live_for_currency` states which of a
        graph value and a live value to present as current; it never
        silently drops the other, which stays cited (Section 7.1's own
        text: "both cited... disagreement never silently drops one side").
    7.3 The as-of marker. `AsOfMarker` is a separate structure, joined to a
        citation by `citation_id`, the same join pattern `trust_signal`
        already uses; it is never a field ON `CitationPayload` itself.
    7.4 Staleness. `is_stale` implements the two thresholds (30 days
        volatile, 90 days stable) and applies to Layer 1 only; Layer 2 and
        Layer 3 have no staleness threshold at all, since their Redis TTLs
        are a cache-cost lever, never a data-age claim.

Section 7.2 (conflict detection) is a separate module,
`synthesis.conflict_detection`, since it is a comparison between two values
already resolved via this module's 7.1 rule, not a freshness computation in
its own right.

Depends on:
    - Nothing beyond the standard library.

Reads:
    - Nothing.

Writes:
    - Nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

FieldClass = Literal["volatile", "stable"]

# Section 7.4's two thresholds, Layer 1 only.
_VOLATILE_STALENESS_DAYS = 30
_STABLE_STALENESS_DAYS = 90

# Section 7.4's own named examples, kept here as documentation of intent
# rather than an enforced classifier: which table a given field belongs to
# is a call each Layer 1 citation builder makes when it calls `is_stale`,
# not something this module infers from a field name.
VOLATILE_FIELD_EXAMPLES = (
    "clinical_significance", "review_status",  # ClinVar
    "gtr_test_status",  # GTR
)
STABLE_FIELD_EXAMPLES = (
    "gene_coordinates", "chromosome_location",  # Gene
    "taxonomy",  # Taxonomy
)

Assembly = Literal["GRCh37", "GRCh38"]


def _parse_date(value: str) -> date:
    """Accept a bare `YYYY-MM-DD` or a full ISO timestamp, either way."""
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise ValueError(
            f"graph_snapshot_date {value!r} is not a parseable date"
        ) from exc


def is_stale(field_class: FieldClass, graph_snapshot_date: str) -> bool:
    """Whether a Layer 1 field of `field_class` is past its Section 7.4
    staleness threshold, measured from `graph_snapshot_date` to today.

    Applies to Layer 1 only, by construction: a caller with a Layer 2/3
    `fetched_at` has no staleness question to ask this function, since
    Section 7.4 states plainly that layer has no staleness threshold at
    all. Passing a Layer 2/3 timestamp here would be a caller error, not
    something this function can detect from the value alone.
    """
    threshold = (
        _VOLATILE_STALENESS_DAYS if field_class == "volatile"
        else _STABLE_STALENESS_DAYS
    )
    today = datetime.now(tz=UTC).date()
    age_days = (today - _parse_date(graph_snapshot_date)).days
    return age_days > threshold


@dataclass(frozen=True)
class AsOfMarker:
    """Section 7.3: an as-of marker, joined to a citation by `citation_id`.

    Exactly one of `graph_snapshot_version` (Layer 1) or `fetched_at`
    (Layer 2/3) is set, never both and never neither; which one applies is
    determined entirely by the citation's own `layer` field. `assembly` is
    populated only for a coordinate- or sequence-bearing claim and is `None`
    (never a fabricated guess) when the assembly could not be resolved.
    """

    citation_id: str
    graph_snapshot_version: str | None = None
    fetched_at: str | None = None
    assembly: Assembly | None = None

    def __post_init__(self) -> None:
        has_snapshot = self.graph_snapshot_version is not None
        has_fetched_at = self.fetched_at is not None
        if has_snapshot == has_fetched_at:
            raise ValueError(
                "AsOfMarker requires exactly one of graph_snapshot_version "
                "(Layer 1) or fetched_at (Layer 2/3), never both or neither: "
                f"citation_id={self.citation_id!r}"
            )


def fetched_at_now() -> str:
    """An ISO-8601 UTC timestamp for a Layer 2/3 `AsOfMarker.fetched_at`.

    A thin, named wrapper rather than an inline `datetime.now` call at every
    tool's citation-building call site, so every Layer 2/3 citation stamps
    the same format.
    """
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


@dataclass(frozen=True)
class CurrencyResolution:
    """Section 7.1's output: which value to present as current, and the
    fact that the other is still cited, never dropped.
    """

    current_value: object
    current_source: Literal["graph", "live"]
    also_cited: object


def prefer_live_for_currency(
    graph_value: object, live_value: object
) -> CurrencyResolution:
    """Section 7.1: "Live API wins for currency" whenever both exist.

    Both values are always returned; this function decides which one a
    narrative should present as CURRENT, it never decides which one gets a
    citation. The caller still cites both, per Section 7.1's own text:
    "Both cited — disagreement never silently drops one side."
    """
    return CurrencyResolution(
        current_value=live_value, current_source="live", also_cited=graph_value
    )


def resolve_assembly(raw_assembly: str | None) -> Assembly | None:
    """Normalize a raw assembly string to Section 7.3's `Assembly` literal.

    Returns `None`, never a fabricated guess, when `raw_assembly` is absent
    or does not resolve to one of the two supported genome builds. A
    coordinate/sequence claim built from a `None` result is refused with
    `assembly: null`, per this phase's premise: never silently omitted.
    """
    if not raw_assembly:
        return None
    normalized = raw_assembly.strip().upper().replace(" ", "").replace("_", "")
    if normalized in ("GRCH37", "HG19"):
        return "GRCh37"
    if normalized in ("GRCH38", "HG38"):
        return "GRCh38"
    return None
