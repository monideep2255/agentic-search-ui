"""Deterministic parsing and call planning for a genomic coordinate window (fix-plan item 1).

A question like "What ACMG-relevant evidence is available for a copy number
variant spanning chr17:43,044,295-43,125,364 on GRCh38?" names a locus, not a
gene, a variant, a disease, or an organism, so it answered with a request to
name one of those until this module existed. Everything here is a pure
function of its arguments: no network call, no model call, the same
discipline `core.breadth_plan` documents for the same reason, so `think_node`
in `core/graph.py` can call it and hand the result to its own resolution and
planning logic without owning any of the logic here.

Four jobs, read top to bottom:

- `parse_coordinate_window`: find the first `chrN:start-end` window in a
  question's text, with its assembly if one was named. A fixed rule, never
  the model, the same reasoning `core.breadth_plan`'s module docstring gives
  for keeping the literature fan-out deterministic.
- `gene_search_term`: the NCBI Gene ESearch term for the genes at a window's
  position, GRCh38 only, because Entrez Gene's position fields are indexed
  against the current human annotation and nothing else.
- `genes_in_window`: filter a batch of Gene ESummary records down to the
  ones whose own genomic placement actually overlaps the window, the same
  discipline `NcbiEfetchCoordinateOverlapInput`'s docstring states for
  dbVar and ClinVar: an ESearch position filter is a coarse prefilter, never
  the overlap predicate itself.
- `plan_overlap_calls`: the two `coordinate_overlap` calls, ClinVar then
  dbVar, that a window with a named assembly always plans, regardless of
  whether gene resolution from coordinates ends up shipping.

`window_disclosure` and `ASSEMBLY_QUESTION` are the two sentences the rest of
the loop needs: what Think found under the window, and what to ask when no
assembly was named, since GRCh37 and GRCh38 put different genes under the
same numbers and guessing would be a confident wrong answer.

Depends on:
    - system_03_search_agent.core.breadth_plan (PlannedCall)
    - system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchInput)

Reads:
    - Nothing. Pure functions over their arguments.

Writes:
    - Nothing.

Depended by:
    - Nothing yet. Planned wiring: system_03_search_agent.core.graph and
      core.state (fix-plan item 1, the coordinate range; not yet wired when
      this module landed, see
      testing/Developer/reports/2026-09-22_coordinate_range/plan.md)
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from system_03_search_agent.core.breadth_plan import PlannedCall
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

# A whole-arm or whole-chromosome span is not a locus question this module
# answers: it is a different question shape with a different answer, not a
# bigger version of the same one. 50,000,000 bases is the bound the plan for
# this item sets.
MAX_WINDOW_SPAN_BASES: Final[int] = 50_000_000

# The chromosome token: 1 to 22, X, Y, M, MT. Longer alternatives are listed
# before their prefixes (MT before M) so a match completes in one pass rather
# than relying on backtracking, though backtracking would find it either way
# because the literal colon that must follow is the real gate.
_CHROMOSOME_TOKEN: Final[str] = r"(?:1[0-9]|2[0-2]|[1-9]|MT|M|X|Y)"

# A position number: thousands-grouped (43,044,295) or a plain digit run
# (43044295). The grouped alternative requires exactly three digits after
# every comma, so it never swallows an unrelated trailing comma the way a
# looser "[0-9,]*" class would (a sentence comma right after the number, as
# in "...364, GRCh37", is never mistaken for part of the number).
_NUMBER_TOKEN: Final[str] = r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)"

# The separator between start and end: a hyphen, an en dash, or the word
# "to" padded by real whitespace on both sides. The en dash is written as
# the `\u2013` escape, never as a literal character in this file, so the
# byte in the source is unambiguous regardless of editor or terminal
# encoding; `re` interprets `\uXXXX` in a pattern string the same way a
# string literal would, so this matches the actual EN DASH character
# (U+2013) at runtime.
_SEPARATOR_TOKEN: Final[str] = r"(?:\s*-\s*|\s*\u2013\s*|\s+to\s+)"

_COORDINATE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:chr|chromosome\s+)?(?P<chromosome>"
    + _CHROMOSOME_TOKEN
    + r")\s*:\s*(?P<start>"
    + _NUMBER_TOKEN
    + r")"
    + _SEPARATOR_TOKEN
    + r"(?P<end>"
    + _NUMBER_TOKEN
    + r")",
    re.IGNORECASE,
)

# Assembly names, found anywhere in the text rather than only after the
# window, because a question can name the assembly first ("On GRCh38, what
# genes sit in chr17:..."). Word-bounded so "GRCh380" or "bb38" never match.
_ASSEMBLY_38_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(?:grch38|hg38|b38)\b", re.IGNORECASE)
_ASSEMBLY_37_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b(?:grch37|hg19|b37)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CoordinateWindow:
    """A parsed genomic coordinate window: one locus, one assembly or none.

    `chromosome` is stored exactly as named after any `chr` or `chromosome`
    prefix, upper-cased, with `M` normalised to `MT`, NCBI's own name for the
    human mitochondrial chromosome. `start` and `end` are always
    forward-ordered (`start <= end`) even when the question wrote them
    reversed. `assembly` is `None` both when the question named no assembly
    and when it named both families in the same text; the two are
    indistinguishable downstream on purpose, since either way no single
    assembly can be assumed. `span` is the matched text's character offsets
    in the original question, `(match.start(), match.end())`, so a caller
    can quote or highlight exactly what was parsed.
    """

    chromosome: str
    start: int
    end: int
    assembly: str | None
    span: tuple[int, int]

    def label(self) -> str:
        """Render as `chr17:43,044,295-43,125,364 (GRCh38)`, thousands-separated.

        `(assembly not named)` stands in for a `None` assembly, so a
        disclosure or a clarifying question never implies an assembly the
        question never gave.
        """
        assembly_text = self.assembly if self.assembly else "assembly not named"
        return f"chr{self.chromosome}:{self.start:,}-{self.end:,} ({assembly_text})"


def _normalise_chromosome(token: str) -> str:
    """Upper-case a matched chromosome token, normalising `M` to `MT`."""
    upper = token.upper()
    return "MT" if upper == "M" else upper


def _find_assembly(text: str) -> str | None:
    """`GRCh38`, `GRCh37`, or `None` for neither or both, read from anywhere in `text`."""
    has_38 = _ASSEMBLY_38_PATTERN.search(text) is not None
    has_37 = _ASSEMBLY_37_PATTERN.search(text) is not None
    if has_38 and has_37:
        return None
    if has_38:
        return "GRCh38"
    if has_37:
        return "GRCh37"
    return None


def parse_coordinate_window(text: str) -> CoordinateWindow | None:
    """The first `chrN:start-end` style window in `text`, or `None`.

    Recognises, case-insensitively: an optional `chr` or `chromosome ` prefix,
    a chromosome token (`1` to `22`, `X`, `Y`, `M`, `MT`), a colon with
    optional surrounding spaces, a start position with optional thousands
    commas, a separator (a hyphen, an en dash, or the word `to` padded by
    spaces), and an end position with optional thousands commas. Only the
    FIRST window in the text is returned; a question naming two windows is
    out of scope here, the same way it is out of scope for the rest of the
    agent loop.

    An inverted window, where the text gives the larger number first, is
    swapped so `start <= end` always holds. A window wider than
    `MAX_WINDOW_SPAN_BASES` returns `None` outright: a whole-arm request is
    not a locus question this module answers.

    `None` for anything that is not a non-empty string, and for any text with
    no window shaped like the above, including a bare `start-end` range with
    no chromosome, a dbSNP id, a cytogenetic band, a gene symbol, a PubMed
    id, or a calendar date. All are distinguishable from a coordinate window
    only by the presence of a chromosome token directly followed by a colon,
    which is exactly what this pattern requires.
    """
    if not isinstance(text, str) or not text:
        return None
    match = _COORDINATE_PATTERN.search(text)
    if match is None:
        return None
    start = int(match.group("start").replace(",", ""))
    end = int(match.group("end").replace(",", ""))
    if start > end:
        start, end = end, start
    if end - start + 1 > MAX_WINDOW_SPAN_BASES:
        return None
    return CoordinateWindow(
        chromosome=_normalise_chromosome(match.group("chromosome")),
        start=start,
        end=end,
        assembly=_find_assembly(text),
        span=match.span(),
    )


# [CHR] and [CPOS] are ESearch position field tags for db=gene, live-verified
# against real ESearch by a parallel probe running in the same fix-plan item
# (see this folder's findings.md). If the probe finds a different tag or a
# different term shape works, the planner corrects this constant in the same
# change that records the probe's result; the call site below does not
# change either way.
GENE_WINDOW_TERM: Final[str] = "{chromosome}[CHR] AND {start}:{end}[CPOS] AND human[ORGN]"


def gene_search_term(window: CoordinateWindow) -> str | None:
    """The Gene ESearch term for the genes overlapping `window`, GRCh38 only.

    `None` unless `window.assembly == "GRCh38"`: Entrez Gene's position
    fields are indexed against the current human annotation only, so a
    GRCh37 window, or a window with no assembly at all, has no live position
    search to run here. A GRCh37 window's genes come from the
    `coordinate_overlap` records `plan_overlap_calls` plans instead, and a
    window with no assembly is not searched at all, per `ASSEMBLY_QUESTION`.
    """
    if window.assembly != "GRCh38":
        return None
    return GENE_WINDOW_TERM.format(chromosome=window.chromosome, start=window.start, end=window.end)


@dataclass(frozen=True)
class WindowGene:
    """One gene whose own genomic placement overlaps a coordinate window."""

    symbol: str
    curie: str
    start: int
    end: int


@dataclass(frozen=True)
class WindowGenes:
    """The genes a window overlaps, capped, with the count before capping."""

    genes: tuple[WindowGene, ...]
    total_overlapping: int
    truncated: bool


# Section 21.3's per-query call ceiling is the reason for a cap at all: a
# window over a gene-dense region could otherwise turn one resolved question
# into dozens of downstream calls. Ten matches the cap `core.breadth_plan`
# already uses for a ClinVar or OMIM search result.
MAX_WINDOW_GENES: Final[int] = 10


def _coerce_uint(value: Any) -> int | None:
    """Best-effort non-negative int from a value that may be an int or a digit string.

    `None` for a bool (Python's `bool` is an `int` subclass), a negative
    number, a float, or anything else that is not cleanly a non-negative
    integer, so a malformed field is skipped rather than mis-parsed. This is
    the same defensive shape `core.breadth_plan.select_ids` uses for a
    uid that may arrive as an int or a string.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _record_source(record: Mapping[str, Any]) -> Mapping[str, Any]:
    """Unwrap a `fields` mapping when present, else the record itself.

    The same unwrap `core.breadth_plan.filter_omim_titles` applies to an
    OMIM record's `title`, applied here to a Gene ESummary record's `name`
    and `genomicinfo`: a caller may hand in the bare fields mapping directly,
    or the full record with a `fields` key wrapping it, and either shape
    reads the same from here on.
    """
    fields = record.get("fields")
    return fields if isinstance(fields, Mapping) else record


def _resolve_uid(record: Mapping[str, Any], source: Mapping[str, Any]) -> int | None:
    """The record's uid, read from `uid` if present, else from `id`.

    NCBI's own ESummary JSON keeps a docsum's `uid` as a sibling of its other
    fields, but `ncbi_eutils_actions.py`'s allowlist for `db="gene"` never
    lets `uid` through into the `fields` object it builds (only `name`,
    `description`, `chromosome`, `maplocation`, `genomicinfo`, `mim`,
    `organism`, `status`, `currentid`, `summary` survive it, per
    `_SUMMARY_FIELDS_BY_DB["gene"]`); the uid ends up on the WRAPPING
    record's own `id` field instead (`NcbiEfetchRecord(id=uid, ...)`,
    `ncbi_eutils_actions.summary`). So `uid` is checked on `source` first,
    for a caller that hands in a flat mapping with `uid` included directly,
    and `id` is checked on the outer `record` second, for the realistic
    wrapped shape this repository actually produces. A uid of zero is not a
    real Entrez id, the same finding `core.breadth_plan`'s F-06 recorded for
    a PMID of zero, so it is treated the same as a missing one.
    """
    value = source.get("uid")
    if value is None:
        value = record.get("id")
    uid = _coerce_uint(value)
    return uid if uid else None


def _overlapping_placements(
    placements: Any, window: CoordinateWindow
) -> tuple[list[int], list[int]]:
    """The (start, stop) pairs from `placements` that overlap `window`.

    Each placement is a mapping carrying `chrstart` and `chrstop` (accepted
    as ints or digit strings; `chraccver` is part of the real shape but is
    not read here, since the Gene ESearch `[CHR]` term that produces these
    candidates is trusted to have already restricted them to the requested
    chromosome, the same trust `NcbiEfetchCoordinateOverlapInput`'s
    docstring places in its own coarse ESearch prefilter). A placement
    missing either bound is ignored rather than failing the whole record.
    Gene reports a minus-strand placement with `chrstart` greater than
    `chrstop`, so the smaller of the two is always treated as the start.
    Overlap is `placement_start <= window.end and placement_stop >=
    window.start`, the same interval test the coordinate_overlap tool
    applies.
    """
    starts: list[int] = []
    stops: list[int] = []
    if not isinstance(placements, (list, tuple)):
        return starts, stops
    for placement in placements:
        if not isinstance(placement, Mapping):
            continue
        raw_start = _coerce_uint(placement.get("chrstart"))
        raw_stop = _coerce_uint(placement.get("chrstop"))
        if raw_start is None or raw_stop is None:
            continue
        placement_start = min(raw_start, raw_stop)
        placement_stop = max(raw_start, raw_stop)
        if placement_start <= window.end and placement_stop >= window.start:
            starts.append(placement_start)
            stops.append(placement_stop)
    return starts, stops


_UNNAMED_LOCUS: Final[re.Pattern[str]] = re.compile(r"^LOC[0-9]+$")


def _is_unnamed_locus(symbol: str) -> bool:
    """NCBI's placeholder symbol for an annotated feature with no name."""
    return _UNNAMED_LOCUS.match(symbol) is not None


def genes_in_window(records: Iterable[Mapping[str, Any]], window: CoordinateWindow) -> WindowGenes:
    """Filter Gene ESummary records to the ones overlapping `window`, capped.

    `records` are, each, the `fields` mapping of an NCBI Gene ESummary
    record as `ncbi_eutils_actions` shapes it, or the record itself with a
    `fields` key (`_record_source` reads `fields` when present, exactly as
    `core.breadth_plan.filter_omim_titles` does for OMIM). The symbol comes
    from `name`; the placements come from `genomicinfo`; the uid comes from
    `uid` or `id` per `_resolve_uid`. A record is kept only when at least one
    of its placements overlaps the window; a record with no usable uid, no
    usable symbol, or no overlapping placement is skipped, and nothing here
    ever raises on a malformed record; it is skipped instead.

    A kept gene's `start`/`end` are the minimum start and maximum end among
    ONLY its overlapping placements, so a gene with several placements is
    reported by the span that actually intersects the window, not by a
    placement that does not. Results are sorted with named genes before
    unnamed loci (a symbol of the form `LOC` followed by digits, NCBI's
    placeholder for an annotated feature with no name), each group by start
    ascending then by symbol, and capped at `MAX_WINDOW_GENES`;
    `total_overlapping` is the count before capping and `truncated` says
    whether the cap dropped any. Named first because the FIRST resolved gene
    is the one the rest of the turn follows for the literature, OMIM and the
    gene summary: measured live on the CFTR window on 2026-09-22, a
    regulatory locus that starts before CFTR sorted ahead of it by position
    alone, and the answer's fan-out was about the locus.
    """
    kept: list[WindowGene] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        source = _record_source(record)
        if not isinstance(source, Mapping):
            continue
        uid = _resolve_uid(record, source)
        if uid is None:
            continue
        symbol = source.get("name")
        if not isinstance(symbol, str) or not symbol.strip():
            continue
        starts, stops = _overlapping_placements(source.get("genomicinfo"), window)
        if not starts:
            continue
        kept.append(
            WindowGene(
                symbol=symbol.strip(),
                curie=f"NCBIGene:{uid}",
                start=min(starts),
                end=max(stops),
            )
        )
    kept.sort(key=lambda gene: (_is_unnamed_locus(gene.symbol), gene.start, gene.symbol))
    total = len(kept)
    return WindowGenes(
        genes=tuple(kept[:MAX_WINDOW_GENES]),
        total_overlapping=total,
        truncated=total > MAX_WINDOW_GENES,
    )


def plan_overlap_calls(window: CoordinateWindow) -> tuple[PlannedCall, ...]:
    """The ClinVar then dbVar `coordinate_overlap` calls for `window`.

    An empty tuple when `window.assembly` is `None`: neither call is
    assembly-agnostic (`NcbiEfetchCoordinateOverlapInput.assembly` is a
    required `Literal["GRCh37", "GRCh38"]`), and guessing an assembly is
    exactly what `ASSEMBLY_QUESTION` exists to avoid. Otherwise, always both
    calls, in a fixed order, regardless of whether `gene_search_term` also
    ran: a GRCh37 window has no Gene position search at all, so these two
    calls are its only path to citable evidence under the window.
    """
    if window.assembly is None:
        return ()
    calls: list[PlannedCall] = []
    for purpose, db in (("clinvar_overlap", "clinvar"), ("dbvar_overlap", "dbvar")):
        calls.append(
            PlannedCall(
                tool="ncbi_efetch",
                layer="layer_2_api",
                prefix="ne",
                purpose=purpose,
                tool_input=NcbiEfetchInput.model_validate(
                    {
                        "action": "coordinate_overlap",
                        "db": db,
                        "chromosome": window.chromosome,
                        "start": window.start,
                        "end": window.end,
                        "assembly": window.assembly,
                    }
                ),
            )
        )
    return tuple(calls)


ASSEMBLY_QUESTION: Final[str] = (
    "These coordinates could be on GRCh38 or GRCh37, and the two put "
    "different genes under the same numbers. Add the assembly to the "
    'question, for example "on GRCh38", and I will search.'
)

# The character budget `window_disclosure` keeps its sentence under, and the
# character it cuts a long symbol list with rather than a plain truncation.
_MAX_DISCLOSURE_CHARS: Final[int] = 300
_DISCLOSURE_ELLIPSIS: Final[str] = "\u2026"


def _bounded_symbol_list(symbols: list[str], prefix: str, budget: int) -> str:
    """Join `symbols` with commas, cut with an ellipsis so `prefix` plus the result fits `budget`.

    `prefix` is everything the caller will place before the list, so the
    budget already available to the list itself is `budget - len(prefix)`.
    The join is cut at a comma boundary where possible, rather than
    mid-symbol, so a truncated list still reads as a list.
    """
    remaining = budget - len(prefix)
    if remaining <= 0:
        return _DISCLOSURE_ELLIPSIS
    joined = ", ".join(symbols)
    if len(joined) <= remaining:
        return joined
    cut = max(remaining - len(_DISCLOSURE_ELLIPSIS), 0)
    partial = joined[:cut].rstrip(", ")
    return f"{partial}{_DISCLOSURE_ELLIPSIS}" if partial else _DISCLOSURE_ELLIPSIS


def window_disclosure(window: CoordinateWindow, genes: WindowGenes) -> str:
    """A short sentence for the think narrative describing what a window overlaps.

    Three shapes: no genes ("overlaps no gene in NCBI Gene"), some genes
    within the cap ("overlaps 1 gene: BRCA1" or "overlaps 3 genes: A, B,
    C"), and more genes than the cap ("overlaps 37 genes; the 10 nearest its
    start are searched: A, B, ..."). Always under `_MAX_DISCLOSURE_CHARS`
    characters: a long symbol list is cut with an ellipsis character rather
    than left to grow without bound, since this sentence is meant to be read
    inline, not to enumerate every gene under a wide window.
    """
    label = window.label()
    if genes.total_overlapping == 0:
        return f"the window {label} overlaps no gene in NCBI Gene"
    symbols = [gene.symbol for gene in genes.genes]
    if genes.truncated:
        prefix = (
            f"the window {label} overlaps {genes.total_overlapping} genes; "
            f"the {len(genes.genes)} nearest its start are searched: "
        )
    else:
        noun = "gene" if genes.total_overlapping == 1 else "genes"
        prefix = f"the window {label} overlaps {genes.total_overlapping} {noun}: "
    sentence = prefix + _bounded_symbol_list(symbols, prefix, _MAX_DISCLOSURE_CHARS)
    if len(sentence) > _MAX_DISCLOSURE_CHARS:
        sentence = sentence[: _MAX_DISCLOSURE_CHARS - 1].rstrip() + _DISCLOSURE_ELLIPSIS
    return sentence
