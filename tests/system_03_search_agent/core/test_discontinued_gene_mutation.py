"""Mutation coverage for the F-4.7-A-02 premise gate: can each arm FAIL?

## Why this file exists

Build phase 4.7 produced three separate vacuous-gate-arm findings, every one
written by the lead, in a file whose own docstring quoted build phase 4.11's
lesson against writing them. One of those three SURVIVED ITS OWN REPAIR: the
populate-check added to make the defect mechanical proved the token appeared
in the QUESTION and said nothing about the CODOMAIN of the value being
asserted on, so the arm still could not fail. That triggered a Rule 4 stop.

The transferable conclusion is not "be careful". It is that reading an
assertion has now been demonstrated, repeatedly, by people who knew the
failure mode by name, not to be a method for validating it. So this file
breaks each control the premise gate claims to protect and asserts the
corresponding arm goes RED. An arm that stays green while the thing it
grades is destroyed is not an arm, and that verdict is delivered here in the
ordinary suite rather than in a review report.

## How it runs

Entirely offline. `tests/conftest.py` hard-fails real outbound HTTP and
nothing here sets `RUN_PREMISE_GATE`, so a leaked call raises rather than
passing quietly.

The gate's live arms are replayed against CANNED NCBI payloads captured from
the real API on 2026-08-24 (the exact records are in this file's fixtures and
their live values are pinned in the gate's own module docstring). That is a
deliberate departure from the gate's rule that a live arm must be live, and
the two are not in conflict: the GATE grades the product against real NCBI
and must not stub it, while THIS file grades the GATE, and "can this
assertion take a failing value?" is a property of the assertion. Answering it
needs an API that can be told to commit the defect on demand, which a real
one cannot be.

## Coverage, stated because a coverage claim this file cannot support would
## be the same defect one level up

Mutated here: all seven arms, P1 through P7, against eleven distinct
mutations.

NOT mutated, and why:

- P2's live-control assertion is mutated (M2b) but its NETWORK-blocked shape
  is not. Simulating "conftest blocks HTTP" from inside a test that conftest
  is already permitting is not reachable in-process; the control is argued
  from the code path, not proven here.
- The `_SYMBOL_CURIE_CACHE`/`_WITHDRAWN_SYMBOL_RECORDS` clearing fixture is
  exercised by M3b (a stale record left in place) but the cross-process
  lifetime of either map is not mutated, since neither is reachable from
  another process.
"""

from typing import Any

import pytest

from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.tools import ncbi_eutils_actions
from system_03_search_agent.tools.ncbi_efetch_schemas import (
    NcbiEfetchOutput,
    NcbiEfetchRecord,
)

from .test_discontinued_gene_premise import (
    LIVE_GENE_ID,
    LIVE_SYMBOL,
    SECOND_SUCCESSOR_ID,
    SECOND_WITHDRAWN_SYMBOL,
    WITHDRAWN_GENE_ID,
    WITHDRAWN_SUCCESSOR_ID,
    WITHDRAWN_SYMBOL,
)

# ---------------------------------------------------------------------------
# Canned NCBI payloads, captured live on 2026-08-24.
#
# The `status`/`currentid` TYPES are part of the fixture and must not be
# "tidied" into strings: a live record returns `status` as the empty STRING
# and a withdrawn one as the INTEGER 1, and that inconsistency is precisely
# what M4a and M4b exist to catch.
# ---------------------------------------------------------------------------

_SUMMARY_BY_ID: dict[str, dict[str, Any]] = {
    WITHDRAWN_GENE_ID: {
        "name": WITHDRAWN_SYMBOL,
        "description": "breast cancer 3",
        "status": 1,
        "currentid": int(WITHDRAWN_SUCCESSOR_ID),
        "organism": {"scientificname": "Homo sapiens"},
    },
    "353129": {
        "name": SECOND_WITHDRAWN_SYMBOL,
        "description": "attention deficit hyperactivity disorder",
        "status": 1,
        "currentid": int(SECOND_SUCCESSOR_ID),
        "organism": {"scientificname": "Homo sapiens"},
    },
    LIVE_GENE_ID: {
        "name": LIVE_SYMBOL,
        "description": "tumor protein p53",
        "status": "",
        "currentid": "",
        "organism": {"scientificname": "Homo sapiens"},
    },
}

_ESEARCH_IDS: dict[str, str] = {
    WITHDRAWN_SYMBOL: WITHDRAWN_GENE_ID,
    SECOND_WITHDRAWN_SYMBOL: "353129",
    LIVE_SYMBOL: LIVE_GENE_ID,
}


def _install_canned_ncbi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace `core.graph.ncbi_efetch` with the three legs the resolver uses.

    `dataset_report` returns ZERO records for every symbol, which is not a
    convenience: probed live on 2026-08-24, NCBI Datasets genuinely returns
    zero reports for both BRCA3 and ADHD, so a withdrawn symbol always falls
    through to the ESearch leg. Stubbing it as empty replays the real API
    rather than steering the test down a chosen path.
    """

    async def _fake(payload: Any) -> NcbiEfetchOutput:
        # `NcbiEfetchInput` is a `RootModel` over the 7-way discriminated
        # union, so the validated branch lives at `.root` and the fields are
        # NOT reachable on the wrapper. Getting this wrong made three
        # mutations in this file raise `AttributeError` instead of exercising
        # the arm, which pytest reported as "DID NOT RAISE" -- a stub that
        # fails to stub reads exactly like a control that failed to break.
        inner = getattr(payload, "root", payload)
        action = inner.action

        def _out(records: list[NcbiEfetchRecord]) -> NcbiEfetchOutput:
            # `record_count` and `truncated` are REQUIRED on this schema, with
            # no defaults. Omitting them made the stub raise ValidationError,
            # which pytest surfaced as "DID NOT RAISE AssertionError" -- the
            # mutation looked like a control that failed to break when in fact
            # the harness never reached the control at all. Building every
            # output through one helper is what stops that recurring per branch.
            return NcbiEfetchOutput(
                action=action,
                status="ok" if records else "empty",
                records=records,
                record_count=len(records),
                truncated=False,
            )

        if action == "dataset_report":
            return _out([])
        if action == "search":
            term = inner.term or ""
            symbol = term.split("[", 1)[0].strip().upper()
            gene_id = _ESEARCH_IDS.get(symbol)
            if gene_id is None:
                return _out([])
            return _out([NcbiEfetchRecord(fields={"idlist": [gene_id]})])
        if action == "summary":
            gene_id = inner.ids[0]
            fields = _SUMMARY_BY_ID.get(gene_id)
            if fields is None:
                return _out([])
            return _out([NcbiEfetchRecord(id=gene_id, fields=dict(fields))])
        raise AssertionError(f"unexpected action {action!r}")

    monkeypatch.setattr(graph_module, "ncbi_efetch", _fake)


@pytest.fixture(autouse=True)
def _clear_state():
    graph_module._SYMBOL_CURIE_CACHE.clear()
    graph_module._WITHDRAWN_SYMBOL_RECORDS.clear()
    yield
    graph_module._SYMBOL_CURIE_CACHE.clear()
    graph_module._WITHDRAWN_SYMBOL_RECORDS.clear()


# ---------------------------------------------------------------------------
# M1: P1's control is the ALLOWLIST.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m1a_p1_goes_red_when_the_allowlist_drops_status(
    monkeypatch: pytest.MonkeyPatch,
):
    """Revert the allowlist to Section 6.2's seven fields; P1 must fail.

    This is the mutation that matters most in this file, because dropping
    `status` is not a hypothetical regression: it is the state the repository
    was in before this branch, and the state the ticket's own written premise
    asserted was already fixed.
    """
    monkeypatch.setitem(
        ncbi_eutils_actions._SUMMARY_FIELDS_BY_DB,
        "gene",
        ("name", "description", "chromosome", "maplocation", "genomicinfo",
         "mim", "organism"),
    )

    entry = dict(_SUMMARY_BY_ID[WITHDRAWN_GENE_ID])
    known = ncbi_eutils_actions._SUMMARY_FIELDS_BY_DB["gene"]
    extracted = {name: entry[name] for name in known if name in entry}

    assert "status" not in extracted and "currentid" not in extracted, (
        "the mutation did not take effect, so the assertion below would be "
        "graded against an unmutated allowlist"
    )
    with pytest.raises(AssertionError):
        assert "status" in extracted, "P1's assertion"


@pytest.mark.asyncio
async def test_m1b_p1_goes_red_when_status_is_present_but_not_the_marker():
    """A key present with a value the resolver cannot act on.

    P1 asserts on the VALUE, not merely the key, precisely because
    "allowlisted key" and "usable value" are different properties and
    verifying the first as a proxy for the second is the safety-by-proxy
    shape build phase 4.3 shipped as a critical twice.
    """
    fields = {"name": WITHDRAWN_SYMBOL, "status": "", "currentid": ""}

    assert "status" in fields, "populate-check: the key IS present"
    with pytest.raises(AssertionError):
        assert str(fields["status"]).strip() == "1", "P1's value assertion"


# ---------------------------------------------------------------------------
# M2: P2's controls.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m2a_p2_goes_red_when_withdrawal_detection_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
):
    """Restore the pre-fix behaviour: never classify anything as withdrawn.

    The withdrawn symbol must then resolve to the successor's id, which is
    F-4.7-A-02 exactly, and P2's assertion must fail on it.
    """
    _install_canned_ncbi(monkeypatch)
    monkeypatch.setattr(
        graph_module, "_classify_gene_record_status", lambda fields: None
    )

    resolved = await graph_module.resolve_symbol_to_curie(WITHDRAWN_SYMBOL)

    assert resolved == f"NCBIGene:{WITHDRAWN_GENE_ID}", (
        "the mutation did not reproduce the defect, so P2's assertion is not "
        f"being graded against it (got {resolved!r})"
    )
    with pytest.raises(AssertionError):
        assert resolved is None, "P2's assertion"


@pytest.mark.asyncio
async def test_m2b_p2s_live_control_goes_red_when_every_lookup_returns_none(
    monkeypatch: pytest.MonkeyPatch,
):
    """The blanket-`None` case P2's control exists for.

    Without the control, an arm asserting only `withdrawn is None` passes
    when the lookup path is entirely dead, which is the single most likely
    way this gate could go green while proving nothing. This mutation makes
    every symbol unresolvable and requires the CONTROL to be what fails.
    """

    async def _all_none(symbol: str, **kwargs: object) -> str | None:
        return None

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _all_none)

    live = await graph_module.resolve_symbol_to_curie(LIVE_SYMBOL)
    withdrawn = await graph_module.resolve_symbol_to_curie(WITHDRAWN_SYMBOL)

    # The real assertion still passes, which is the whole point: it cannot
    # tell a correct refusal from a dead path.
    assert withdrawn is None
    with pytest.raises(AssertionError):
        assert live == f"NCBIGene:{LIVE_GENE_ID}", "P2's populate-check"


# ---------------------------------------------------------------------------
# M3: P3's control is that the withdrawal is RECORDED.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m3a_p3_goes_red_when_the_reason_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
):
    """The "refuse silently" implementation: correct refusal, no reason kept.

    It passes P2 and must fail P3. This mutation is what separates the option
    the product owner chose from the one they rejected, so without it the two
    are indistinguishable to this gate.
    """
    _install_canned_ncbi(monkeypatch)
    real = graph_module._classify_gene_record_status

    def _detect_but_discard(fields: dict[str, Any]) -> str | None:
        result = real(fields)
        return "" if result is not None else None

    monkeypatch.setattr(
        graph_module, "_classify_gene_record_status", _detect_but_discard
    )

    class _DiscardingDict(dict):
        """Accepts the write and keeps nothing.

        Substituting a plain `{}` here is NOT this mutation, and getting that
        wrong cost a round: the resolver writes the record and
        `withdrawn_record_for` reads it back through the SAME global, so
        swapping the dict swaps it for both and the record is still found.
        The mutation being modelled is the write never having been added at
        all, which is what the rejected "refuse silently" option would have
        shipped, so the write has to be the thing that is dropped.
        """

        def __setitem__(self, key, value):
            return None

    monkeypatch.setattr(
        graph_module, "_WITHDRAWN_SYMBOL_RECORDS", _DiscardingDict()
    )

    resolved = await graph_module.resolve_symbol_to_curie(WITHDRAWN_SYMBOL)
    assert resolved is None, "populate-check: the refusal half still works"

    record = graph_module.withdrawn_record_for(WITHDRAWN_SYMBOL)
    with pytest.raises(AssertionError):
        assert record is not None, "P3's assertion"


@pytest.mark.asyncio
async def test_m3b_p3s_clearing_populate_check_goes_red_on_a_stale_record():
    """P3 opens by asserting the map is EMPTY before it looks anything up.

    That opening assertion is not decoration: without it, a record left
    behind by an earlier arm satisfies every later assertion in P3 without
    any lookup having happened, which is an arm that grades the fixture
    rather than the code.
    """
    graph_module._WITHDRAWN_SYMBOL_RECORDS["BRCA3:human"] = (
        graph_module._WithdrawnGeneRecord(
            symbol=WITHDRAWN_SYMBOL,
            curie=f"NCBIGene:{WITHDRAWN_GENE_ID}",
            successor_curie=f"NCBIGene:{WITHDRAWN_SUCCESSOR_ID}",
        )
    )
    with pytest.raises(AssertionError):
        assert graph_module.withdrawn_record_for(WITHDRAWN_SYMBOL) is None, (
            "P3's opening populate-check"
        )


# ---------------------------------------------------------------------------
# M4: P4's control is TYPE TOLERANCE. Two mutations, one per real-world shape.
# ---------------------------------------------------------------------------


def test_m4a_p4_goes_red_when_status_is_compared_as_an_int_only(
    monkeypatch: pytest.MonkeyPatch,
):
    """`status == 1` is correct against the live API and inert against the
    string shape the adversary report transcribed."""

    def _int_only(fields: dict[str, Any]) -> str | None:
        if fields.get("status") != 1:
            return None
        return str(fields.get("currentid") or "")

    monkeypatch.setattr(graph_module, "_classify_gene_record_status", _int_only)

    assert graph_module._classify_gene_record_status(
        {"status": 1, "currentid": 675}
    ) is not None, "populate-check: the int shape still classifies"

    with pytest.raises(AssertionError):
        result = graph_module._classify_gene_record_status(
            {"status": "1", "currentid": "675"}
        )
        assert result is not None, "P4's str-1 case"


def test_m4b_p4_goes_red_when_status_is_compared_as_a_string_only(
    monkeypatch: pytest.MonkeyPatch,
):
    """The mirror image, and the one that would actually ship: `status ==
    "1"` reads as careful and is inert against every real NCBI record, since
    the live API returns the integer."""

    def _str_only(fields: dict[str, Any]) -> str | None:
        if fields.get("status") != "1":
            return None
        return str(fields.get("currentid") or "")

    monkeypatch.setattr(graph_module, "_classify_gene_record_status", _str_only)

    with pytest.raises(AssertionError):
        result = graph_module._classify_gene_record_status(
            {"status": 1, "currentid": 675}
        )
        assert result is not None, "P4's int-1 case"


def test_m4c_p4_goes_red_when_a_live_records_empty_status_reads_as_withdrawn(
    monkeypatch: pytest.MonkeyPatch,
):
    """A truthiness check (`if fields.get("status") is not None`) classifies
    EVERY live gene as withdrawn, because a live record carries `status` as
    the empty string rather than omitting it. That mutation refuses the whole
    product, and P4's live-empty-string case is what catches it."""

    def _presence_only(fields: dict[str, Any]) -> str | None:
        if fields.get("status") is None:
            return None
        return str(fields.get("currentid") or "")

    monkeypatch.setattr(
        graph_module, "_classify_gene_record_status", _presence_only
    )

    with pytest.raises(AssertionError):
        result = graph_module._classify_gene_record_status(
            {"status": "", "currentid": ""}
        )
        assert result is None, "P4's live-empty-string case"


# ---------------------------------------------------------------------------
# M5: P5's control is that the successor is READ, not constant.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_m5_p5_goes_red_when_the_successor_is_hardcoded(
    monkeypatch: pytest.MonkeyPatch,
):
    """A fix that records BRCA3's successor for every withdrawn symbol passes
    a presence check and passes P3. P5 asserts ADHD's OWN successor, so it is
    the arm that catches a constant."""
    _install_canned_ncbi(monkeypatch)
    monkeypatch.setattr(
        graph_module,
        "_classify_gene_record_status",
        lambda fields: (
            WITHDRAWN_SUCCESSOR_ID
            if str(fields.get("status") or "").strip() == "1"
            else None
        ),
    )

    resolved = await graph_module.resolve_symbol_to_curie(SECOND_WITHDRAWN_SYMBOL)
    assert resolved is None, "populate-check: the refusal half still works"

    record = graph_module.withdrawn_record_for(SECOND_WITHDRAWN_SYMBOL)
    assert record is not None, "populate-check: something WAS recorded"

    with pytest.raises(AssertionError):
        assert record.successor_curie == f"NCBIGene:{SECOND_SUCCESSOR_ID}", (
            "P5's successor assertion"
        )


# ---------------------------------------------------------------------------
# M6: P6's control is the refusal TEXT.
# ---------------------------------------------------------------------------


def test_m6a_p6_goes_red_when_the_refusal_falls_back_to_the_generic_message(
    monkeypatch: pytest.MonkeyPatch,
):
    """The refusal is built but the withdrawn branch never fires, so the user
    is told "NCBI has no record matching the name" about a symbol NCBI holds
    a record for. Correct refusal, false sentence."""
    monkeypatch.setattr(
        graph_module, "_withdrawn_records_for_symbols", lambda symbols: []
    )

    text = graph_module._build_unresolved_entity_refusal_text([WITHDRAWN_SYMBOL])

    assert text, "populate-check: a refusal was still produced"
    with pytest.raises(AssertionError):
        assert "discontinued" in text.lower(), "P6's discontinued assertion"


def test_m6b_p6_goes_red_when_the_successor_is_not_named(
    monkeypatch: pytest.MonkeyPatch,
):
    """The clause says "discontinued" but drops the id, which is the
    "refuse silently" option wearing the right adjective."""
    monkeypatch.setattr(
        graph_module,
        "_withdrawn_clause",
        lambda records: f"{records[0].symbol} is a discontinued record.",
    )
    graph_module._WITHDRAWN_SYMBOL_RECORDS["BRCA3:human"] = (
        graph_module._WithdrawnGeneRecord(
            symbol=WITHDRAWN_SYMBOL,
            curie=f"NCBIGene:{WITHDRAWN_GENE_ID}",
            successor_curie=f"NCBIGene:{WITHDRAWN_SUCCESSOR_ID}",
        )
    )

    text = graph_module._build_unresolved_entity_refusal_text([WITHDRAWN_SYMBOL])

    assert "discontinued" in text.lower(), "populate-check: still a withdrawal"
    with pytest.raises(AssertionError):
        assert WITHDRAWN_SUCCESSOR_ID in text, "P6's successor-id assertion"


# ---------------------------------------------------------------------------
# M7: P7's control is that a missing successor is not INVENTED.
# ---------------------------------------------------------------------------


def test_m7a_p7_goes_red_when_currentid_zero_becomes_a_fabricated_id(
    monkeypatch: pytest.MonkeyPatch,
):
    """`currentid` is the integer `0` on a withdrawn record with no
    replacement. Passing it straight through emits `NCBIGene:0`, a real-
    looking identifier for a gene that does not exist, into a user-facing
    sentence."""

    def _no_zero_guard(fields: dict[str, Any]) -> str | None:
        if str(fields.get("status") or "").strip() != "1":
            return None
        # Deliberately `.get(key, "")` and NOT `.get(key) or ""`. The second
        # form maps the integer 0 to "" by accident, because 0 is falsy, so
        # writing the mutation that way produced a version that was already
        # correct and reported as "DID NOT RAISE". A mutation that does not
        # mutate is the same class of defect as an arm that cannot fail.
        return str(fields.get("currentid", ""))

    monkeypatch.setattr(
        graph_module, "_classify_gene_record_status", _no_zero_guard
    )

    result = graph_module._classify_gene_record_status(
        {"name": "SOMEGENE", "status": 1, "currentid": 0}
    )
    assert result is not None, "populate-check: still classified as withdrawn"
    with pytest.raises(AssertionError):
        assert result == "", "P7's no-fabrication assertion"


def test_m7b_p7_goes_red_when_the_clause_names_an_empty_successor(
    monkeypatch: pytest.MonkeyPatch,
):
    """The other half: the classifier is right and the SENTENCE still emits a
    bare `NCBIGene:` prefix with nothing after it."""
    monkeypatch.setattr(
        graph_module,
        "_withdrawn_clause",
        lambda records: (
            f"{records[0].symbol} is a discontinued NCBI gene record "
            f"({records[0].curie}), replaced by NCBIGene:."
        ),
    )
    record = graph_module._WithdrawnGeneRecord(
        symbol="SOMEGENE", curie="NCBIGene:99999", successor_curie=""
    )
    text = graph_module._withdrawn_clause([record])

    assert "discontinued" in text.lower(), "populate-check: still a withdrawal"
    with pytest.raises(AssertionError):
        assert "NCBIGene:" not in text.replace("NCBIGene:99999", ""), (
            "P7's no-fabricated-CURIE assertion"
        )


# ---------------------------------------------------------------------------
# M8: P8's control is that BOTH channels come from one builder.
# ---------------------------------------------------------------------------


def test_m8_p8_goes_red_when_the_event_channel_uses_the_bare_constant(
    monkeypatch: pytest.MonkeyPatch,
):
    """Reinstate the defect a live run caught: the answer text is rebuilt and
    the `trust_signal` message still points at the generic constant."""
    graph_module._WITHDRAWN_SYMBOL_RECORDS["BRCA3:human"] = (
        graph_module._WithdrawnGeneRecord(
            symbol=WITHDRAWN_SYMBOL,
            curie=f"NCBIGene:{WITHDRAWN_GENE_ID}",
            successor_curie=f"NCBIGene:{WITHDRAWN_SUCCESSOR_ID}",
        )
    )
    monkeypatch.setattr(
        graph_module,
        "_unresolved_entity_refusal_message",
        lambda symbols: graph_module._UNRESOLVED_ENTITY_REFUSAL_MESSAGE,
    )

    message = graph_module._unresolved_entity_refusal_message([WITHDRAWN_SYMBOL])
    assert message, "populate-check: a message was still produced"

    with pytest.raises(AssertionError):
        assert "discontinued" in message.lower(), "P8's populate-check"
