"""Deterministic parsing and call planning for an NCBI accession (golden question G-007).

A question like "For BioProject PRJNA31257, list the BioSamples, the SRA
runs and any genome assemblies, and say how to retrieve each" names an
accession, not a gene symbol, a disease, or a coordinate window, so nothing
in the agent loop resolved it before this module existed. Everything here is
a pure function of its arguments: no network call, no model call, the same
discipline `core.breadth_plan` and `core.coordinate_window` document for the
same reason, so `think_node` in `core/graph.py` can call it and hand the
result to its own resolution and planning logic without owning any of the
logic here.

Four accession kinds, one dataclass. `Accession` holds a `kind` (one of
`ACCESSION_KINDS`: `bioproject`, `biosample`, `sra`, `assembly`), the
upper-cased `value`, and the `span` it was found at. `label()` renders it for
a sentence: `BioProject PRJNA31257`, `BioSample SAMN12121739`, `SRA run
SRR9496657`, `assembly GCF_000001405.40`.

Five jobs, read top to bottom:

- `parse_accession`: find the first accession-shaped token in a question's
  text, case-insensitively, with a fixed rule, never the model, the same
  reasoning `coordinate_window.parse_coordinate_window` gives for its own
  window regex.
- `search_input`: the ESearch that resolves an accession to its Entrez uid.
  Probed live on 2026-09-22 against real NCBI for PRJNA31257
  (`testing/Developer/reports/2026-09-22_bioproject_accession/probes.md`,
  Fact 1): the plain unscoped term finds the record in one hit, while the
  idiomatic scoped `[ACCN]` term this codebase already uses for `db=gene`
  (`BRCA1[sym]`) matches ZERO records for the same accession, a genuine trap
  rather than an HTTP error, so this module deliberately never emits it.
- `link_inputs`: the ELink calls from a resolved accession to every other
  database `LINK_TARGETS` says it fans out to, one call per target, in a
  fixed order.
- `plan_summary_calls`: the ESummary calls once linked ids are known, the
  record's own summary first, then one per non-empty linked target, ids
  sorted and capped with `breadth_plan.select_ids`.
- `disclosure`: the one sentence the think narrative needs, stating what an
  accession resolved to and how many of each linked record it found.

Depends on:
    - system_03_search_agent.core.breadth_plan (PlannedCall, select_ids)
    - system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchInput)

Reads:
    - Nothing. Pure functions over their arguments.

Writes:
    - Nothing.

Depended by:
    - Nothing yet. Planned wiring: system_03_search_agent.core.graph and
      core.state (golden question G-007, the BioProject accession; not yet
      wired when this module landed, see
      testing/Developer/reports/2026-09-22_bioproject_accession/probes.md)
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from system_03_search_agent.core.breadth_plan import PlannedCall, select_ids
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

# The four accession kinds this module recognises, also the four legal
# `SearchDb`/`SummaryDb` values this module ever sends: `NcbiEfetchSchemas`
# lists all four in both enums, confirmed by reading `ncbi_efetch_schemas.py`
# rather than assumed.
ACCESSION_KINDS: Final[tuple[str, ...]] = ("bioproject", "biosample", "sra", "assembly")

# Rendered prefixes for `Accession.label()`. The `sra` kind is deliberately
# absent here: its label word depends on the accession's own third letter,
# handled separately by `_SRA_SUBTYPE_WORDS` below.
_LABEL_PREFIXES: Final[dict[str, str]] = {
    "bioproject": "BioProject",
    "biosample": "BioSample",
    "assembly": "assembly",
}

# An SRA accession's third letter names which of the four SRA object types it
# is: run, experiment, sample or study. `ACCESSION_KINDS` has only one `sra`
# entry because all four share one Entrez database and one ELink fan-out, so
# the subtype is read from the value itself rather than carried as a second
# field.
_SRA_SUBTYPE_WORDS: Final[dict[str, str]] = {
    "R": "run",
    "X": "experiment",
    "S": "sample",
    "P": "study",
}


@dataclass(frozen=True)
class Accession:
    """One accession found in text: which kind, its upper-cased value, and its span.

    `value` is upper-cased exactly as NCBI writes the accession, `PRJNA31257`
    rather than `prjna31257` or `Prjna31257`. The assembly kind's optional
    `.version` suffix is written through unchanged by this rule rather than
    stripped or reformatted, and that is a no-op in practice: it is only
    digits and a dot, both case-invariant under `str.upper()`, so
    `GCF_000001405.40` upper-cases to itself. `span` is the matched text's
    character offsets in the original question, `(match.start(), match.end())`,
    the same convention `coordinate_window.CoordinateWindow.span` uses.
    """

    kind: str
    value: str
    span: tuple[int, int]

    def label(self) -> str:
        """Render for a sentence: `BioProject PRJNA31257`, `SRA run SRR9496657`.

        The `sra` kind reads its own subtype word from the accession's third
        letter (`R` run, `X` experiment, `S` sample, `P` study), since one
        `kind` covers all four SRA object types per `parse_accession`'s own
        pattern. Every other kind uses a fixed prefix word. A value too short
        to have a third letter falls back to the word `record` rather than
        raising; this can only happen for a hand-built `Accession`, never one
        `parse_accession` returns, since the pattern requires three letters.
        """
        if self.kind == "sra":
            subtype = _SRA_SUBTYPE_WORDS.get(self.value[2:3], "record")
            return f"SRA {subtype} {self.value}"
        return f"{_LABEL_PREFIXES.get(self.kind, self.kind)} {self.value}"


# The four token shapes, each a plain alternative inside one combined pattern
# so "the first accession by position" falls out of `re.search`'s own
# leftmost-match behaviour rather than needing four separate searches merged
# and re-sorted by hand.
_BIOPROJECT_TOKEN: Final[str] = r"PRJ(?:NA|EB|DB)[0-9]{1,9}"
_BIOSAMPLE_TOKEN: Final[str] = r"SAM(?:N|EA|D)[0-9]{1,12}"
_SRA_TOKEN: Final[str] = r"[SED]R[RXSP][0-9]{1,12}"
_ASSEMBLY_TOKEN: Final[str] = r"GC[AF]_[0-9]{9}(?:\.[0-9]{1,3})?"

_ACCESSION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:"
    r"(?P<bioproject>" + _BIOPROJECT_TOKEN + r")"
    r"|(?P<biosample>" + _BIOSAMPLE_TOKEN + r")"
    r"|(?P<sra>" + _SRA_TOKEN + r")"
    r"|(?P<assembly>" + _ASSEMBLY_TOKEN + r")"
    r")\b",
    re.IGNORECASE,
)


def parse_accession(text: str) -> Accession | None:
    """The first accession-shaped token in `text` by position, or None.

    Recognises, case-insensitively, with a mandatory word boundary on both
    sides: a BioProject accession (`PRJ` then `NA`, `EB` or `DB`, then 1 to 9
    digits), a BioSample accession (`SAM` then `N`, `EA` or `D`, then 1 to 12
    digits), an SRA run, experiment, sample or study accession (`S`, `E` or
    `D`, then `R`, then `R`, `X`, `S` or `P`, then 1 to 12 digits), or an
    assembly accession (`GCA` or `GCF`, then an underscore, then exactly 9
    digits, then an optional `.` and 1 to 3 version digits). Only the FIRST
    match in the text is returned, by position, regardless of which of the
    four kinds it is: a question naming two accessions is out of scope here,
    the same way a second coordinate window is out of scope for
    `coordinate_window.parse_coordinate_window`.

    `None` for anything that is not a non-empty string, and for any text with
    no accession-shaped token, including a PubMed id (`PMID 11237011`), a
    dbSNP id (`rs334`), a RefSeq accession (`NM_007294.4`), a coordinate
    range, or an accession missing its required letters or digit count
    (`PRJ12345` has no `NA`/`EB`/`DB` source letters; `GCF_12345` has only 5
    of the required 9 digits). All are distinguishable from a real accession
    only by the exact letter-and-digit shape each pattern requires.

    The returned `value` is upper-cased; see `Accession`'s own docstring for
    why that is a no-op on the assembly kind's version suffix.
    """
    if not isinstance(text, str) or not text:
        return None
    match = _ACCESSION_PATTERN.search(text)
    if match is None:
        return None
    for kind in ACCESSION_KINDS:
        value = match.group(kind)
        if value is not None:
            return Accession(kind=kind, value=value.upper(), span=match.span())
    return None


def search_input(accession: Accession) -> NcbiEfetchInput:
    """The ESearch that finds `accession`'s own Entrez uid.

    The term is the PLAIN accession value with no field tag, `PRJNA31257`
    rather than `PRJNA31257[ACCN]`. Probed live on 2026-09-22 against real
    ESearch for exactly this BioProject accession
    (`testing/Developer/reports/2026-09-22_bioproject_accession/probes.md`,
    Fact 1): the scoped `[ACCN]` term is a genuine NCBI-recognised field, its
    querytranslation echoes `[ACCN]` back rather than falling back to `[All
    Fields]`, the signal E-utilities gives for a field it does not recognise,
    and it still matches ZERO records for an accession that demonstrably
    exists, while the bare unscoped term finds it immediately, one hit, on
    the first try. `retmax` is 1: this call exists only to resolve the uid,
    never to browse.
    """
    return NcbiEfetchInput.model_validate(
        {"action": "search", "db": accession.kind, "term": accession.value, "retmax": 1}
    )


# Which other databases a resolved accession fans out to, and in what order
# `link_inputs` and `plan_summary_calls` both walk them. Never `bioproject` as
# a target: nothing in this probe's scope links back to it.
LINK_TARGETS: Final[dict[str, tuple[str, ...]]] = {
    "bioproject": ("biosample", "sra", "assembly"),
    "biosample": ("sra", "assembly"),
    "sra": ("biosample",),
    "assembly": ("biosample",),
}


def link_inputs(accession: Accession, uid: str) -> tuple[NcbiEfetchInput, ...]:
    """One ELink call per target `LINK_TARGETS[accession.kind]` names, in order.

    Probed live on 2026-09-22 for a BioProject accession
    (`testing/Developer/reports/2026-09-22_bioproject_accession/probes.md`,
    Fact 3): three ELink calls, `dbfrom=bioproject` against `db=biosample`,
    `db=sra` and `db=assembly`, each carrying the SAME resolved uid. `db` is
    always sent explicitly, never left to ELink's own default, which
    `NcbiEfetchLinkInput`'s own docstring documents as sometimes dominated by
    computed `pubmed_pubmed*` neighbours rather than the direct
    cross-reference asked for.
    """
    return tuple(
        NcbiEfetchInput.model_validate(
            {"action": "link", "dbfrom": accession.kind, "db": target, "ids": [uid]}
        )
        for target in LINK_TARGETS[accession.kind]
    )


# Section 21.3's per-query call ceiling is the reason for a cap at all, the
# same reasoning `coordinate_window.MAX_WINDOW_GENES` states for its own
# fan-out. Ten matches the cap `core.breadth_plan` already uses for a ClinVar
# or OMIM search result.
MAX_LINKED_PER_DB: Final[int] = 10


def _coerce_id_list(value: Any) -> list[Any]:
    """`value` as a plain list when it is a list or tuple, else empty.

    A bare string is deliberately excluded even though Python iterates it
    character by character: a `linked` entry is meant to be a sequence of id
    strings, never a single string read as a sequence of characters. This is
    the guard that lets every read of a `linked` mapping stay malformed-safe
    without raising, per this module's contract never to raise on a
    malformed `linked` value.
    """
    return list(value) if isinstance(value, (list, tuple)) else []


def _target_ids(linked: Any, target: str) -> list[Any]:
    """The raw id list `linked` holds for `target`, or empty for anything malformed.

    Handles `linked` itself not being a mapping (for example `None`), and
    `linked[target]` not being a list or tuple, the same way: both read as no
    ids for that target rather than raising.
    """
    if not isinstance(linked, Mapping):
        return []
    return _coerce_id_list(linked.get(target))


def plan_summary_calls(
    accession: Accession, uid: str, linked: Mapping[str, Sequence[str]]
) -> tuple[PlannedCall, ...]:
    """The ESummary calls for `accession` and each of its non-empty linked targets.

    Always first: the record's own summary, `db=accession.kind`, purpose
    `f"{accession.kind}_summary"`, on `[uid]`. Then, in
    `LINK_TARGETS[accession.kind]` order, one summary call per target whose
    `linked` entry holds at least one valid uid, ids sorted numerically
    highest first and capped at `MAX_LINKED_PER_DB` by
    `breadth_plan.select_ids`, the same helper `plan_clinvar_follow_up` and
    `plan_omim_follow_up` already use for the same reason: deterministic
    output regardless of the order or repetition ids arrived in. A target
    whose ids are empty, all invalid, or whose `linked` mapping is itself
    malformed, is skipped rather than raising or emitting an empty-ids call.
    """
    calls: list[PlannedCall] = [
        PlannedCall(
            tool="ncbi_efetch",
            layer="layer_2_api",
            prefix="ne",
            purpose=f"{accession.kind}_summary",
            tool_input=NcbiEfetchInput.model_validate(
                {"action": "summary", "db": accession.kind, "ids": [uid]}
            ),
        )
    ]
    for target in LINK_TARGETS[accession.kind]:
        selected = select_ids(_target_ids(linked, target), MAX_LINKED_PER_DB)
        if not selected:
            continue
        calls.append(
            PlannedCall(
                tool="ncbi_efetch",
                layer="layer_2_api",
                prefix="ne",
                purpose=f"{target}_summary",
                tool_input=NcbiEfetchInput.model_validate(
                    {"action": "summary", "db": target, "ids": selected}
                ),
            )
        )
    return tuple(calls)


# The singular and plural noun `disclosure` uses per target kind. Never
# `bioproject`: see the `LINK_TARGETS` comment above.
_TARGET_NOUNS: Final[dict[str, tuple[str, str]]] = {
    "biosample": ("BioSample", "BioSamples"),
    "sra": ("SRA run", "SRA runs"),
    "assembly": ("assembly", "assemblies"),
}

# The character budget `disclosure` keeps its sentence under, and the
# character it cuts with, matching `coordinate_window.window_disclosure`'s
# own constants exactly, including the reasoning: defence in depth against an
# input this module's own bounded vocabulary should never actually produce.
_MAX_DISCLOSURE_CHARS: Final[int] = 300
# Written as the \u2026 escape, never a literal character, so the byte in
# the source is unambiguous regardless of editor or terminal encoding, the
# same discipline `coordinate_window._DISCLOSURE_ELLIPSIS` documents.
_DISCLOSURE_ELLIPSIS: Final[str] = "\u2026"


def _valid_id_count(linked: Any, target: str) -> int:
    """How many valid, deduplicated uids `linked` holds for `target`, uncapped.

    Reuses `breadth_plan.select_ids`'s own uid validation and dedup logic
    rather than a second copy of it, with the cap set to the raw list's own
    length so nothing is ever truncated here: `disclosure` reports how much
    was actually found, independent of the `MAX_LINKED_PER_DB` cap
    `plan_summary_calls` applies when it plans the actual fetch.
    """
    raw = _target_ids(linked, target)
    return len(select_ids(raw, cap=len(raw)))


def _count_phrase(count: int, nouns: tuple[str, str]) -> str:
    """`"1 BioSample"`, `"2 BioSamples"`, or `"no BioSamples"` for zero."""
    singular, plural = nouns
    if count == 0:
        return f"no {plural}"
    return f"{count} {singular if count == 1 else plural}"


def _join_with_and(parts: list[str]) -> str:
    """Comma-join every part but the last, then join the last with `" and "`.

    No Oxford comma, matching the fixed example sentence `disclosure`
    reproduces exactly: `"1 BioSample, 1 SRA run and 1 assembly"`.
    """
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def disclosure(accession: Accession, uid: str | None, linked: Mapping[str, Sequence[str]]) -> str:
    """One sentence for the think narrative: what `accession` resolved to.

    Two shapes. With no uid: `"BioProject PRJNA31257 was not found in
    NCBI"`. `uid` counts as missing for `None`, for anything that is not a
    string, and for an empty or whitespace-only string, since none of those
    is a real Entrez uid. With a uid: `"BioProject PRJNA31257 links to 1
    BioSample, 1 SRA run and 1 assembly"`, one clause per target
    `LINK_TARGETS[accession.kind]` names, in that order, pluralised properly
    and reading `"no assemblies"` for a target with zero links. Counts are of
    VALID ids, deduplicated, before `MAX_LINKED_PER_DB` capping, since the
    count should say how much was actually found even where
    `plan_summary_calls` only fetches the first ten. Always under
    `_MAX_DISCLOSURE_CHARS` characters in practice, since the vocabulary here
    is a handful of short fixed words and an id count; the final cut below is
    defence in depth, the same discipline
    `coordinate_window.window_disclosure` applies to its own unbounded gene
    list, kept here even though no realistic input reaches it.
    """
    if not isinstance(uid, str) or not uid.strip():
        return f"{accession.label()} was not found in NCBI"
    parts = [
        _count_phrase(_valid_id_count(linked, target), _TARGET_NOUNS[target])
        for target in LINK_TARGETS[accession.kind]
    ]
    sentence = f"{accession.label()} links to {_join_with_and(parts)}"
    if len(sentence) > _MAX_DISCLOSURE_CHARS:
        sentence = sentence[: _MAX_DISCLOSURE_CHARS - 1].rstrip() + _DISCLOSURE_ELLIPSIS
    return sentence
