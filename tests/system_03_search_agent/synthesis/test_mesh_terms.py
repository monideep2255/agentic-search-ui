"""The MeSH descriptor resolver: two calls, joined by identifier, never guessed.

Golden question G-019, "What MeSH terms are assigned to PMID 11237011?",
reached 26 `OntologyClass` rows and answered two passes of three while
carrying no terms at all: every `OntologyClass` name in the live graph is
`[MeSH] D000818`, the identifier. `synthesis/mesh_terms.py` reads the terms
from the live MeSH record instead.

EVERY ARM CARRIES A POPULATE CHECK, because this repository has shipped
vacuous assertions in six separate build phases, and the shape that keeps
winning is an arm that cannot tell its control holding from nothing having
happened. Concretely here:

- An arm that asserts a mapping is "correct" passes vacuously if the
  resolver returned an empty dict, so every positive arm asserts the exact
  headings AND that the map is the size it should be.
- An arm that counts calls passes vacuously if the resolution silently
  failed, so every call-count arm also asserts a real heading came back.
- The order-independence arm asserts the headings DIFFER from one another,
  since a fixture whose records all share one heading would pass whether the
  join key was read or ignored.

The fake transport stands in for `ncbi_eutils_actions.search` and
`.summary`, which is where the shared rate pool, the call budget and the
audit hook live. It records every call, so an arm can assert the count that
the 20-call-per-query ceiling actually cares about.
"""

from __future__ import annotations

import os
import re
from types import SimpleNamespace

import pytest

from system_03_search_agent.synthesis import mesh_terms
from system_03_search_agent.synthesis.disease_names import readable_disease_name

# G-019's real ids and their real headings, read from live ESummary on
# 2026-09-23. Kept as a fixture rather than invented so an arm that claims
# to exercise "the golden question's ids" actually does.
G019_HEADINGS = {
    "D000818": "Animals",
    "D002874": "Chromosome Mapping",
    "D017124": "Conserved Sequence",
    "D018899": "CpG Islands",
    "D004251": "DNA Transposable Elements",
    "D016208": "Databases, Factual",
    "D004345": "Drug Industry",
    "D019143": "Evolution, Molecular",
    "D005544": "Forecasting",
    "D020862": "GC Rich Sequence",
    "D020440": "Gene Duplication",
    "D005796": "Genes",
    "D030342": "Genetic Diseases, Inborn",
    "D005826": "Genetics, Medical",
    "D015894": "Genome, Human",
    "D016045": "Human Genome Project",
    "D006801": "Humans",
    "D009154": "Mutation",
    "D017149": "Private Sector",
    "D011506": "Proteins",
    "D020543": "Proteome",
    "D017150": "Public Sector",
    "D012313": "RNA",
    "D012091": "Repetitive Sequences, Nucleic Acid",
    "D017422": "Sequence Analysis, DNA",
    "D013045": "Species Specificity",
}

# The real descriptor-to-UID mapping for the six-digit ids above is
# `68` + the digits, but NINE-digit descriptors do not follow it at all
# (D000066428 is UID 2009637, live). The fake below therefore mints UIDs
# from a table rather than by arithmetic, so no arm can accidentally pass
# because the code computed a UID instead of asking for one.
_UID_FOR = {mesh_id: f"68{mesh_id[1:]}" for mesh_id in G019_HEADINGS}
_UID_FOR["D000066388"] = "2009636"
_UID_FOR["D000066428"] = "2009637"
_HEADINGS = dict(G019_HEADINGS)
_HEADINGS["D000066388"] = "Oil and Gas Industry"
_HEADINGS["D000066428"] = "Coal Industry"

_MHUI_CLAUSE = re.compile(r"(D\d+)\[MHUI\]")


class _FakeEutils:
    """Records every call and answers like the live endpoint.

    `reverse_summary` inverts the order ESummary hands records back, which is
    what the live endpoint was measured doing on 2026-09-23: ESearch returned
    G-019's UIDs in descending numeric order while the request listed them in
    the graph's order. A resolver that joined on position would be wrong on
    the real endpoint today, not merely one day in the future.
    """

    def __init__(self, *, known=None, reverse_summary=False, raises=None):
        self.known = _HEADINGS if known is None else known
        self.reverse_summary = reverse_summary
        self.raises = raises
        self.calls: list[tuple[str, str]] = []
        # A UID per known id: the real table where one was measured, and a
        # distinct synthetic one otherwise. Built here rather than looked up
        # in the module-level table so an arm driving its own id set gets
        # UIDs too; the first version of this fake raised KeyError instead,
        # and the arm that caught it did so through its populate check
        # rather than through the assertion it was written for.
        self._uid_for = {
            mesh_id: _UID_FOR.get(mesh_id, f"77{mesh_id[1:]}") for mesh_id in self.known
        }
        self._id_for_uid = {uid: mesh_id for mesh_id, uid in self._uid_for.items()}

    async def search(self, params):
        self.calls.append(("search", params.term))
        if self.raises:
            raise self.raises
        ids = [
            self._uid_for[m]
            for m in _MHUI_CLAUSE.findall(params.term)
            if m in self.known
        ]
        return SimpleNamespace(
            status="ok" if ids else "empty",
            records=[SimpleNamespace(fields={"idlist": ids})] if ids else [],
        )

    async def summary(self, params):
        self.calls.append(("summary", ",".join(params.ids)))
        if self.raises:
            raise self.raises
        records = []
        for uid in params.ids:
            mesh_id = self._id_for_uid.get(uid)
            if mesh_id is None or mesh_id not in self.known:
                continue
            heading = self.known[mesh_id]
            records.append(
                SimpleNamespace(
                    fields={
                        "ds_meshui": mesh_id,
                        # The preferred heading FIRST, then entry terms, which
                        # is the live shape: D000818 answers
                        # ["Animals", "Animal", "Animalia", "Metazoa"].
                        "ds_meshterms": [heading, f"{heading} entry term"],
                        "ds_recordtype": "descriptor",
                    }
                )
            )
        if self.reverse_summary:
            records.reverse()
        return SimpleNamespace(status="ok" if records else "empty", records=records)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch):
    """Install a fake transport and start from a cold cache."""

    def _install(**kwargs):
        stub = _FakeEutils(**kwargs)
        import system_03_search_agent.tools.ncbi_eutils_actions as actions

        monkeypatch.setattr(actions, "search", stub.search)
        monkeypatch.setattr(actions, "summary", stub.summary)
        return stub

    mesh_terms.reset_cache_for_tests()
    yield _install
    mesh_terms.reset_cache_for_tests()


# ---------------------------------------------------------------------------
# The call count, which is the constraint this design was built against
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_twenty_six_ids_cost_exactly_two_calls(fake) -> None:
    """G-019's full set resolves in two calls, not twenty-six.

    THE POPULATE CHECK IS THE SECOND HALF: a resolver that made two calls and
    returned nothing would satisfy the count alone, so this asserts all 26
    headings came back and names three of them exactly. A naive per-id
    resolution would be 52 calls and would breach the 20-call ceiling on its
    own.
    """
    stub = fake()
    curies = [f"MeSH:{mesh_id}" for mesh_id in G019_HEADINGS]

    resolved = await mesh_terms.resolve_descriptor_ids(curies)

    assert [kind for kind, _ in stub.calls] == ["search", "summary"], stub.calls
    assert len(resolved) == 26
    assert all(resolved[c] for c in curies), resolved
    assert resolved["MeSH:D000818"] == "Animals"
    assert resolved["MeSH:D015894"] == "Genome, Human"
    assert resolved["MeSH:D016045"] == "Human Genome Project"


@pytest.mark.asyncio
async def test_one_id_costs_the_same_two_calls_as_twenty_six(fake) -> None:
    """The floor is two, and it is a floor rather than a per-id price."""
    stub = fake()
    resolved = await mesh_terms.resolve_descriptor_ids(["MeSH:D000818"])
    assert len(stub.calls) == 2
    assert resolved == {"MeSH:D000818": "Animals"}


@pytest.mark.asyncio
async def test_a_warm_cache_costs_nothing(fake) -> None:
    """A repeat inside one process issues no call at all.

    Populate-checked by asserting the SECOND resolution returned the real
    heading: a resolver that made no calls and returned None would otherwise
    pass the call-count half of this arm.
    """
    stub = fake()
    first = await mesh_terms.resolve_descriptor_ids(["MeSH:D000818"])
    assert first["MeSH:D000818"] == "Animals"
    before = len(stub.calls)

    second = await mesh_terms.resolve_descriptor_ids(["MeSH:D000818"])

    assert len(stub.calls) == before
    assert second["MeSH:D000818"] == "Animals"


@pytest.mark.asyncio
async def test_an_unresolvable_id_is_cached_as_unresolvable(fake) -> None:
    """A negative result is cached too, so a repeat does not re-spend two calls."""
    stub = fake(known={"D000818": "Animals"})
    first = await mesh_terms.resolve_descriptor_ids(["MeSH:D999999"])
    assert first == {"MeSH:D999999": None}
    before = len(stub.calls)

    second = await mesh_terms.resolve_descriptor_ids(["MeSH:D999999"])

    assert len(stub.calls) == before
    assert second == {"MeSH:D999999": None}


# ---------------------------------------------------------------------------
# The join key. This is the arm that would catch a confident wrong answer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_headings_join_on_the_records_own_id_not_on_position(fake) -> None:
    """Each id gets ITS heading even when ESummary hands records back reversed.

    The live endpoint does exactly this: measured 2026-09-23, ESearch returned
    G-019's 26 UIDs in descending numeric order while the term listed them in
    the graph's order.

    POPULATE CHECK, and it is the load-bearing one: the fixture's headings are
    asserted to be DISTINCT from one another. An arm built on a fixture where
    every record shared one heading would pass identically whether the
    resolver read `ds_meshui` or matched by position, which is the exact
    safety-by-proxy shape build phase 4.3 shipped as a critical twice.
    """
    stub = fake(reverse_summary=True)
    curies = [f"MeSH:{mesh_id}" for mesh_id in G019_HEADINGS]

    resolved = await mesh_terms.resolve_descriptor_ids(curies)

    values = [resolved[c] for c in curies]
    assert len(set(values)) == len(values), "fixture must not share headings"
    assert resolved == {f"MeSH:{k}": v for k, v in G019_HEADINGS.items()}
    assert stub.reverse_summary is True


@pytest.mark.asyncio
async def test_only_the_preferred_heading_is_taken_never_an_entry_term(fake) -> None:
    """`ds_meshterms[0]` is the assigned heading; the rest are synonyms.

    Populate-checked against the fixture's own second entry, so the arm fails
    if the resolver took the wrong index or joined the list.
    """
    stub = fake()
    resolved = await mesh_terms.resolve_descriptor_ids(["D000818"])
    assert resolved["D000818"] == "Animals"
    assert "entry term" not in (resolved["D000818"] or "")
    assert len(stub.calls) == 2


# ---------------------------------------------------------------------------
# Never invents, never raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_id_mesh_does_not_hold_keeps_its_identifier(fake) -> None:
    """An unknown id maps to None and STAYS IN THE MAP.

    Dropping it would make it vanish from the answer with no disclosure,
    which is the silent version of the defect this module exists to fix.
    Populate-checked by resolving a real id in the same batch, so the arm
    fails if the whole resolution collapsed rather than one id missing.
    """
    fake(known={"D000818": "Animals"})
    resolved = await mesh_terms.resolve_descriptor_ids(["MeSH:D000818", "MeSH:D999999"])
    assert resolved == {"MeSH:D000818": "Animals", "MeSH:D999999": None}


@pytest.mark.asyncio
async def test_a_transport_failure_degrades_and_never_raises(fake) -> None:
    """A failure turns a readable answer unreadable, never a query into none.

    `CallBudgetExceededError` reaches the resolver through this same path.
    """
    stub = fake(raises=RuntimeError("transport down"))
    resolved = await mesh_terms.resolve_descriptor_ids(["MeSH:D000818"])
    assert resolved == {"MeSH:D000818": None}
    assert stub.calls, "the arm must have actually attempted a call"


@pytest.mark.asyncio
async def test_a_medgen_curie_is_declined_without_spending_a_call(fake) -> None:
    """The MeSH resolver never looks up another vocabulary's identifier.

    Populate-checked with a real MeSH id in the same batch: the arm fails
    both if the MedGen id was looked up and if declining it suppressed the
    lookup that should have happened.
    """
    stub = fake()
    resolved = await mesh_terms.resolve_descriptor_ids(
        ["MedGen:C0346153", "MeSH:D000818"]
    )
    assert resolved == {"MedGen:C0346153": None, "MeSH:D000818": "Animals"}
    assert "C0346153" not in stub.calls[0][1]


@pytest.mark.asyncio
async def test_a_malformed_id_never_reaches_the_network(fake) -> None:
    """Nothing shaped unlike a descriptor is sent, so no rate slot is spent."""
    stub = fake()
    resolved = await mesh_terms.resolve_descriptor_ids(
        ["MeSH:", "", "D", "MeSH:D00A818", "X000818", "mesh:D000818"]
    )
    assert set(resolved.values()) == {None}
    assert stub.calls == []


@pytest.mark.asyncio
async def test_a_non_ascii_digit_is_rejected(fake) -> None:
    """F-2.1-A5-07's lesson: `\\d` without `re.ASCII` matches Devanagari digits."""
    stub = fake()
    resolved = await mesh_terms.resolve_descriptor_ids(["MeSH:D०००818"])
    assert set(resolved.values()) == {None}
    assert stub.calls == []


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_search_term_stays_inside_the_schemas_own_cap(fake) -> None:
    """The assembled term never exceeds `NcbiEfetchSearchInput.term`'s 500 cap.

    Checked against the SCHEMA rather than against a copied number, so the
    two cannot drift. Driven with nine-digit descriptors, whose clauses are
    the longest real ones (20 characters against 17), and with more ids than
    can fit, so the batching path is the one exercised.

    Populate-checked: the term must actually carry clauses, and the ids that
    did not fit must come back as None rather than be dropped.
    """
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchSearchInput

    cap = NcbiEfetchSearchInput.model_fields["term"].metadata[0].max_length
    stub = fake(known={f"D{600000000 + n}": f"heading {n}" for n in range(40)})
    curies = [f"MeSH:D{600000000 + n}" for n in range(40)]

    resolved = await mesh_terms.resolve_descriptor_ids(curies)

    term = stub.calls[0][1]
    assert 0 < len(term) <= cap, len(term)
    assert term.count("[MHUI]") >= 20
    assert len(resolved) == 40
    assert sum(1 for v in resolved.values() if v is None) > 0
    assert sum(1 for v in resolved.values() if v) >= 20


@pytest.mark.asyncio
async def test_resolution_is_skipped_when_the_query_has_no_headroom(
    fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two calls are not spent when fewer than two remain under the ceiling.

    Populate-checked in both directions in one arm: at 19 of 20 calls made
    nothing is issued, and at 18 the same input resolves for real. An arm
    that only checked the refusal would pass if resolution were broken
    outright.
    """
    from system_03_search_agent.harness import call_budget

    stub = fake()
    monkeypatch.setattr(call_budget, "calls_made", lambda: 19)
    blocked = await mesh_terms.resolve_descriptor_ids(["MeSH:D000818"])
    assert blocked == {"MeSH:D000818": None}
    assert stub.calls == []

    mesh_terms.reset_cache_for_tests()
    monkeypatch.setattr(call_budget, "calls_made", lambda: 18)
    allowed = await mesh_terms.resolve_descriptor_ids(["MeSH:D000818"])
    assert allowed == {"MeSH:D000818": "Animals"}
    assert len(stub.calls) == 2


@pytest.mark.asyncio
async def test_no_bound_budget_does_not_disable_resolution(
    fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`calls_made()` returning None means no ceiling, never no headroom.

    Off the query path (a unit test, a script) no budget is bound. Reading
    that as zero headroom would silently disable resolution everywhere except
    inside a run, which is the failure a reader would not notice.
    """
    from system_03_search_agent.harness import call_budget

    fake()
    monkeypatch.setattr(call_budget, "calls_made", lambda: None)
    assert (await mesh_terms.resolve_descriptor_ids(["MeSH:D000818"])) == {
        "MeSH:D000818": "Animals"
    }


# ---------------------------------------------------------------------------
# The premise the wiring rests on: the enum, the allowlist, the reorder rule
# ---------------------------------------------------------------------------


def test_mesh_is_a_legal_summary_database() -> None:
    """RED before this change: `db="mesh"` was rejected by the input schema.

    `mesh` was already a `SearchDb` value and was not a `SummaryDb` one, so
    the descriptor-to-UID half of the path was legal and the UID-to-heading
    half was not.
    """
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchSummaryInput

    validated = NcbiEfetchSummaryInput(action="summary", db="mesh", ids=["68000818"])
    assert validated.db == "mesh"


def test_the_mesh_summary_allowlist_carries_the_join_key() -> None:
    """RED before this change: `mesh` had no allowlist entry at all.

    `ds_meshui` is the field the whole join rests on. Without it in the
    allowlist the extractor strips it and every heading is orphaned, which is
    the shape of build phase 4.7's discontinued-gene defect: the field was in
    the raw body and the allowlist removed it before the resolver was handed
    the record.
    """
    from system_03_search_agent.tools.ncbi_eutils_actions import _SUMMARY_FIELDS_BY_DB

    fields = _SUMMARY_FIELDS_BY_DB["mesh"]
    assert "ds_meshui" in fields
    assert "ds_meshterms" in fields


def test_every_summary_database_still_has_an_allowlist() -> None:
    """Adding an enum value without an allowlist would reopen F-3.1-10.

    That finding was a `SummaryDb` value falling through to
    `_generic_summary_fields`, which copies every response key. This arm ties
    the two lists together so the next added database cannot repeat it.
    """
    from typing import get_args

    from system_03_search_agent.tools.ncbi_efetch_schemas import SummaryDb
    from system_03_search_agent.tools.ncbi_eutils_actions import _SUMMARY_FIELDS_BY_DB

    databases = set(get_args(SummaryDb))
    assert "mesh" in databases
    assert databases <= set(_SUMMARY_FIELDS_BY_DB)


def test_the_readable_name_reorder_leaves_every_mesh_heading_alone() -> None:
    """A MeSH inverted heading IS the canonical form and must not be reordered.

    `apply_resolved_disease_names` runs `readable_disease_name` over whatever
    it is handed, which was written for MedGen's OMIM-style inversions
    ("Breast-ovarian cancer, familial, susceptibility to, 1"). Its qualifier
    set is closed, so "Genome, Human" and "Genetic Diseases, Inborn" pass
    through untouched today. This arm pins that, so widening the qualifier
    set later cannot silently start rewriting MeSH headings into terms NLM
    does not use.

    Populate-checked: the fixture is asserted to contain inverted headings,
    so the arm cannot pass on a set with no commas in it.
    """
    inverted = [h for h in G019_HEADINGS.values() if "," in h]
    assert len(inverted) >= 5, inverted
    for heading in G019_HEADINGS.values():
        assert readable_disease_name(heading) == heading, heading


# ---------------------------------------------------------------------------
# The live arm. Skipped without a key; run it before trusting any of the above
# ---------------------------------------------------------------------------


def _premise_gate_is_active() -> bool:
    """The repository's own opt-in, not a second one beside it.

    `tests/conftest.py` installs a session-scoped blocker that raises
    `LiveHttpCallInUnitSuiteError` in place of any real outbound call, and
    stands aside only for `RUN_PREMISE_GATE`. A private env var here would
    read as an opt-in and would not be one: the first draft of this arm used
    its own flag, ran green-looking, and was actually exercising the
    resolver's transport-failure path against the blocker rather than
    against NCBI. Recorded rather than quietly corrected, because a live arm
    that never reaches the network is exactly the vacuous shape this file's
    docstring is about.
    """
    return os.environ.get("RUN_PREMISE_GATE", "").strip().lower() in {"1", "true", "yes"}


live_arm = pytest.mark.skipif(
    not _premise_gate_is_active(),
    reason=(
        "the live arm calls real E-utilities. Run it with RUN_PREMISE_GATE=1, "
        "the same opt-in tests/conftest.py's live-HTTP blocker honours. It "
        "issues exactly two requests, inside the 3-per-second unauthenticated "
        "limit in .claude/rules/tool-call-budgets.md"
    ),
)


@live_arm
@pytest.mark.asyncio
async def test_live_g019_ids_resolve_to_real_headings_in_two_calls() -> None:
    """The whole premise, against the real endpoint, on G-019's own 26 ids.

    Not a mock in sight. If NCBI changes `[MHUI]`, `ds_meshui` or
    `ds_meshterms`, this is the arm that says so, and the mocked arms above
    would keep passing against a contract that no longer exists.
    """
    mesh_terms.reset_cache_for_tests()
    curies = [f"MeSH:{mesh_id}" for mesh_id in G019_HEADINGS]

    resolved = await mesh_terms.resolve_descriptor_ids(curies)

    assert resolved == {f"MeSH:{k}": v for k, v in G019_HEADINGS.items()}
