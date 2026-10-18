"""Does the leaked-vocabulary filter catch the `[MeSH] D000818` form?

`core/graph.py`'s `_is_vocabulary_token_artifact` exists precisely to stop a
leaked controlled-vocabulary token being presented as a genuine name. Reading it
suggests the bracketed form escapes, because the function returns False as soon
as it sees a space and `[MeSH]` is not the bare token the list holds. Reading is
not proof, so this runs the real function against the real strings the graph
returned tonight.

The `[stub]` form IS handled explicitly, which is what makes the gap worth
checking rather than assuming: somebody already thought about bracketed ETL
placeholders and covered one of the two shapes.

Usage, from the repository root:

    venv/bin/python testing/Developer/reports/2026-09-23_overnight/probe_artifact_filter.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path("src").resolve()))

from system_03_search_agent.core.graph import (
    _is_vocabulary_token_artifact,
)

# Every value below was returned by the live graph tonight, or is a control.
CASES: list[tuple[str, bool, str]] = [
    # value, expected_to_be_flagged, why
    ("[MeSH] D000818", True, "a real OntologyClass name G-019 reaches, an identifier"),
    ("[MeSH] D000001", True, "a real OntologyClass name, sampled"),
    ("[stub] HP:0000002", True, "a real PhenotypicFeature name, already handled"),
    ("GARD", True, "a real Disease name, the bare token the list holds"),
    ("MONDO", True, "a real Disease name"),
    ("MedGen", True, "a real Disease name"),
    ("MeSH", True, "a real Disease name, bare"),
    ("SNOMEDCT_US", True, "a real Disease name"),
    ("OMIM allelic variant", True, "a real Disease name, token plus qualifier"),
    # Controls: genuine values that must NOT be flagged.
    ("fibrillin 1", False, "the real Gene name for NCBIGene:2200"),
    (
        "Initial sequencing and analysis of the human genome.",
        False,
        "the real Article name for PMID:11237011",
    ),
    ("Marfan syndrome", False, "a genuine disease name, what SHOULD be stored"),
    ("Breast neoplasms", False, "a genuine MeSH term, what SHOULD be stored"),
]


def main() -> None:
    wrong = 0
    print(f"{'flagged':>8}  {'want':>5}  value")
    print("-" * 78)
    for value, expected, why in CASES:
        got = _is_vocabulary_token_artifact(value)
        mark = "ok " if got == expected else "MISS"
        if got != expected:
            wrong += 1
        print(f"{mark} {got!s:>5}  {expected!s:>5}  {value!r}  ({why})")
    print("-" * 78)
    print(f"{wrong} case(s) where the filter does not do what the data needs")


if __name__ == "__main__":
    main()
