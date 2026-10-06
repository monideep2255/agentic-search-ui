"""Card 56 round 3: run Think on the regression questions against one tree
(develop's or this branch's) with the same faked model replies and NCBI, and
print one JSON line per scenario, so two runs can be diffed line by line.

Usage: python compare_r3.py <tree-root>
The tree must hold `src/` and the round 3 test file, whose fakes are reused.
Develop's tree is a scratch export of origin/develop outside the repository
with that one test file copied in; nothing in it is committed.
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import pytest

from system_03_search_agent.core import graph as g
from tests.system_03_search_agent.core import test_think_sra_disease_fallback as T

SARS = (
    "Find SRA runs of SARS-CoV-2 sequenced on Illumina from clinical respiratory "
    "samples, and explain why each one matched."
)
#: Each regression question with the extraction the live model gave it in
#: round 2 (build_r2.md, "Live runs"), plus empty extractions under every
#: record type, the case the disease fallback runs on.
QUESTIONS = {
    "What diseases are linked to BRCA1?": ([("BRCA1", "gene")], "none"),
    "Mycobacterium tuberculosis genome assemblies": (
        [("Mycobacterium tuberculosis", "organism")],
        "assembly",
    ),
    "SRA runs of BRCA9 knockouts in human cells": (
        [("BRCA9", "gene"), ("human", "organism")],
        "sra",
    ),
    "SRA runs of BRCA1 knockout cells": ([("BRCA1", "gene")], "sra"),
    "What causes type-2 diabetes?": ([("type-2 diabetes", "disease")], "none"),
    "SRA runs from MODY patients": ([("MODY", "disease")], "sra"),
    SARS: ([("SARS-CoV-2", "organism")], "sra"),
}


async def scenario(question: str, entities: list, record_type: str) -> dict:
    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(T, "TAXONOMY", {**T.TAXONOMY, "human": ["9606"]})
        searched = T._install_ncbi(mp)
        T._install_model(mp, record_type, entities)
        result = await g.think_node(T._state(question))
        return {
            "question": question[:48],
            "entities": entities,
            "record_type": record_type,
            "outcome": T._outcome(result),
            "medgen_terms": [term for db, term in searched if db == "medgen"],
        }
    finally:
        mp.undo()


async def main() -> None:
    for question, (tagged, record_type) in QUESTIONS.items():
        cases = [(tagged, record_type)] + [([], kind) for kind in ("sra", "assembly", "none")]
        for entities, kind in cases:
            print(json.dumps(await scenario(question, entities, kind)), flush=True)


asyncio.run(main())
