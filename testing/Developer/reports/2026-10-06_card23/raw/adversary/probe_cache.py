"""Card 23 adversary: is a disease name 'read live from NCBI'? Throwaway.

Patches the two E-utilities actions the resolver calls so NCBI's MedGen title
changes between two answers, and counts how many NCBI calls the second answer
makes. Also checks what the shown cell does to the title.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd() / "src"))

from system_03_search_agent.synthesis import disease_names as D
from system_03_search_agent.synthesis.answer_layout import table_second_cell
from system_03_search_agent.tools import ncbi_eutils_actions as A

NCBI_TITLE = {"value": "Diabetes mellitus, type 2"}
CALLS = {"n": 0}


async def fake_search(_inp):
    CALLS["n"] += 1
    return SimpleNamespace(status="ok", records=[SimpleNamespace(fields={"idlist": ["41522"]})])


async def fake_summary(_inp):
    CALLS["n"] += 1
    return SimpleNamespace(
        status="ok",
        records=[SimpleNamespace(fields={"conceptid": "C0011860", "title": NCBI_TITLE["value"]})],
    )


async def main():
    A.search, A.summary = fake_search, fake_summary
    D.reset_cache_for_tests()
    first = await D.resolve_concept_ids(["MedGen:C0011860"])
    print("answer 1:", first, "NCBI calls so far:", CALLS["n"])
    NCBI_TITLE["value"] = "Type 2 diabetes mellitus (renamed upstream)"
    # Six days later in the same process.
    real = time.monotonic
    time.monotonic = lambda: real() + 6 * 24 * 3600
    second = await D.resolve_concept_ids(["MedGen:C0011860"])
    print("answer 2, six days later, NCBI now says", repr(NCBI_TITLE["value"]), "->", second,
          "NCBI calls so far:", CALLS["n"])
    time.monotonic = real
    cell = table_second_cell(
        "SequenceVariant", {"clinvar_condition_ids": ["MedGen:C0011860"]}, first
    )
    print("MedGen title:", repr(first["MedGen:C0011860"]), "cell shown:", repr(cell))
    for title in (
        "Breast-ovarian cancer, familial, susceptibility to, 1",
        "Fanconi anemia, complementation group D1",
        "Maturity-onset diabetes of the young, type 3",
    ):
        c = table_second_cell("SequenceVariant", {"clinvar_condition_ids": ["MedGen:C1"]}, {"MedGen:C1": title})
        print("MedGen title:", repr(title), "cell shown:", repr(c))


asyncio.run(main())
