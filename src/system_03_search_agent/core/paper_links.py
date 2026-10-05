"""Call planning for the data records one PubMed paper links to (card 74, golden G-006).

A question like "sequence data for PMID 11237011" anchors on one paper and asks
for the records NCBI links to it: sequences, BioProjects, BioSamples, SRA runs,
GEO series, assemblies. The knowledge graph holds no edge from a paper to any of
them (measured 2026-10-05), so only a live ELink call from `pubmed` can answer.
Everything here is a pure function of its arguments: no network call, no model
call, the same discipline `core.accession` documents. Which kind of record the
question asks for is decided by a classifier in `core.graph`, never by words
matched here.

Three jobs:

- `targets_for`: the explicit ELink target databases one classifier pick means.
- `link_calls`: one ELink call per target, `dbfrom=pubmed`, `db` always named,
  never left to ELink's own default (`NcbiEfetchLinkInput`'s docstring).
- `plan_summary_follow_up`: the ESummary call for the ids one ELink returned,
  ids sorted and capped by `breadth_plan.select_ids`, so each linked record is
  cited to its own NCBI page.

Depends on:
    - system_03_search_agent.core.breadth_plan (PlannedCall, select_ids)
    - system_03_search_agent.tools.ncbi_efetch_schemas (NcbiEfetchInput)

Reads:
    - Nothing. Pure functions over their arguments.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.core.graph (the plan and write steps)
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from system_03_search_agent.core.breadth_plan import PlannedCall, select_ids
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

#: The prefix of a link call's purpose, followed by the target database.
LINK_PURPOSE_PREFIX: Final[str] = "paper_link_"

#: What each classifier pick means, as the ELink target databases in a fixed
#: order. `sequences` is sequence data in the wide sense a reader means by it:
#: GenBank and RefSeq records, sequencing runs and genome assemblies.
TARGETS_BY_KIND: Final[dict[str, tuple[str, ...]]] = {
    "sequences": ("nuccore", "sra", "assembly"),
    "projects": ("bioproject",),
    "samples": ("biosample",),
    "reads": ("sra",),
    "expression": ("gds",),
    "assemblies": ("assembly",),
    "all_data": ("nuccore", "bioproject", "biosample", "sra", "gds", "assembly"),
}

#: The ESummary database each target is cited from. Every target is its own.
_SUMMARY_PURPOSE: Final[str] = "{db}_summary"

#: Singular and plural nouns for the plain sentences about each target.
_NOUNS: Final[dict[str, tuple[str, str]]] = {
    "nuccore": ("sequence record", "sequence records"),
    "bioproject": ("BioProject", "BioProjects"),
    "biosample": ("BioSample", "BioSamples"),
    "sra": ("SRA run record", "SRA run records"),
    "gds": ("GEO record", "GEO records"),
    "assembly": ("genome assembly", "genome assemblies"),
}

#: How many linked records of one target are summarised and cited, the same
#: cap `core.accession` and the ClinVar and OMIM follow-ups use, kept under
#: Section 21.3's per-question call ceiling and the answer's finding cap.
MAX_LINKED_PER_DB: Final[int] = 10

_PMID_CURIE: Final[re.Pattern[str]] = re.compile(r"^PMID:([1-9][0-9]{0,8})$")


def single_pmid(curies: Iterable[str]) -> str | None:
    """The one PubMed id among `curies`, or None for none or for several.

    A question that names two papers is out of scope here, the same way
    `accession.parse_accession` takes one accession.
    """
    found = {match.group(1) for curie in curies if (match := _PMID_CURIE.match(curie))}
    return next(iter(found)) if len(found) == 1 else None


def targets_for(kind: str) -> tuple[str, ...]:
    """The ELink target databases a classifier pick means, empty for any other value."""
    return TARGETS_BY_KIND.get(kind, ())


def target_of_purpose(purpose: str) -> str | None:
    """The target database a link call's purpose names, or None for any other purpose."""
    if not purpose.startswith(LINK_PURPOSE_PREFIX):
        return None
    target = purpose[len(LINK_PURPOSE_PREFIX) :]
    return target if target in _NOUNS else None


def link_calls(pmid: str, targets: Iterable[str]) -> tuple[PlannedCall, ...]:
    """One ELink call from `pubmed` to each target, `db` always explicit."""
    return tuple(
        PlannedCall(
            tool="ncbi_efetch",
            layer="layer_2_api",
            prefix="ne",
            purpose=f"{LINK_PURPOSE_PREFIX}{target}",
            tool_input=NcbiEfetchInput.model_validate(
                {"action": "link", "dbfrom": "pubmed", "db": target, "ids": [pmid]}
            ),
        )
        for target in targets
    )


def plan_summary_follow_up(target: str, ids: Iterable[str]) -> tuple[PlannedCall, ...]:
    """The ESummary call for the linked ids of one target, or nothing for no valid id."""
    selected = select_ids(ids, MAX_LINKED_PER_DB)
    if not selected or target not in _NOUNS:
        return ()
    return (
        PlannedCall(
            tool="ncbi_efetch",
            layer="layer_2_api",
            prefix="ne",
            purpose=_SUMMARY_PURPOSE.format(db=target),
            tool_input=NcbiEfetchInput.model_validate(
                {"action": "summary", "db": target, "ids": selected}
            ),
        ),
    )


def noun(target: str, count: int) -> str:
    """`"genome assembly"` for one, `"genome assemblies"` otherwise."""
    singular, plural = _NOUNS[target]
    return singular if count == 1 else plural


def none_linked_message(pmid: str, targets: Iterable[str]) -> str:
    """The plain sentence for a paper NCBI links to no record of the asked kinds."""
    words = [_NOUNS[target][1] for target in targets if target in _NOUNS]
    if not words:
        words = ["data records"]
    listed = words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]
    return f"NCBI lists no linked {listed} for PMID {pmid}."


def count_note(pmid: str, target: str, total: int, shown: int = MAX_LINKED_PER_DB) -> str | None:
    """The sentence naming how many linked records NCBI lists when more than are shown."""
    if total <= shown:
        return None
    return (
        f"NCBI lists {total} {noun(target, total)} linked to PMID {pmid}; "
        f"this answer shows {shown}."
    )


def empty_target_note(pmid: str, target: str) -> str:
    """The sentence for one kind with no links, beside kinds that have some."""
    return f"NCBI lists no linked {_NOUNS[target][1]} for PMID {pmid}."
