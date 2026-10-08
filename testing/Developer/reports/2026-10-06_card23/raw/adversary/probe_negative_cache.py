"""Card 23 adversary: a failed MedGen lookup is cached as 'no title' for a week. Throwaway."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path.cwd() / "src"))
from system_03_search_agent.synthesis import disease_names as D
from system_03_search_agent.tools import ncbi_eutils_actions as A

state = {"up": False, "calls": 0}


async def search(_inp):
    state["calls"] += 1
    if not state["up"]:
        raise TimeoutError("one blip")
    return SimpleNamespace(status="ok", records=[SimpleNamespace(fields={"idlist": ["41522"]})])


async def summary(_inp):
    state["calls"] += 1
    return SimpleNamespace(status="ok", records=[SimpleNamespace(fields={"conceptid": "C0011860", "title": "Type 2 diabetes mellitus"})])


async def main():
    A.search, A.summary = search, summary
    D.reset_cache_for_tests()
    print("answer 1 during a blip:", await D.resolve_concept_ids(["MedGen:C0011860"]), "calls", state["calls"])
    state["up"] = True
    print("answer 2, NCBI healthy:", await D.resolve_concept_ids(["MedGen:C0011860"]), "calls", state["calls"])
    D.reset_cache_for_tests()
    print("answer 3, cold process:", await D.resolve_concept_ids(["MedGen:C0011860"]), "calls", state["calls"])


asyncio.run(main())
