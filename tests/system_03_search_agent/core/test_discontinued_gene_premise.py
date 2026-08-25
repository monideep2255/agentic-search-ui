"""Premise gate for F-4.7-A-02: a discontinued gene record must never be
answered as its successor.

## The defect this grades

Build phase 4.7's adversary round asked "Which diseases are associated with
BRCA3?" and got back, verbatim:

    The knowledge graph search returned a gene record for BRCA2 [1].

with `trust_outcome: answer`, `grounded: true`, `risk_tier: low`, a real
citation to `/gene/675/`, and no sentence anywhere saying the subject had
been substituted. The user asked about BRCA3 and was answered about BRCA2.

`BRCA3` is NCBIGene:60500, an NCBI gene record with `status=1`
(discontinued) whose `currentid` is 675 (BRCA2). `_resolve_symbol_to_curie_
uncached` fetches exactly that ESummary record, reads exactly one field from
it (`name`), sees `"BRCA3"`, and returns the withdrawn id as a confirmed
CURIE. The unconditional unresolved-entity refusal built for F-4.5-J-01
cannot fire, because it triggers only on `not target_curies and
unresolved_symbols` and a `target_curie` was in fact produced. The safety net
is downstream of the substitution.

Classified PRE-EXISTING, not caused by build phase 4.7: the heuristic that
phase retired was `\\b[A-Z][A-Z0-9]{1,9}\\b`, which matches `BRCA3`, and the
resolver is the same `resolve_symbol_to_curie`, so the identical wrong answer
was reachable before.

## The product decision this encodes

Product owner, 2026-08-24: REFUSE, NAMING THE SUCCESSOR. The resolver
contributes no CURIE for a withdrawn record, so no answer about a substituted
gene is reachable at all, and the refusal names what was actually found so
the user can re-ask. The two rejected alternatives are recorded because the
arms below would look arbitrary without them: refusing silently throws away a
successor id already in hand, and answering-with-a-disclosure leaves the
substitution in place and makes the disclosure depend on a Synth model
actually emitting a sentence.

## A WRONG PREMISE IN THE TICKET, CORRECTED HERE RATHER THAN INHERITED

`tracker/BOARD.md` and the adversary report both state the fix is
single-site, because "`status` and `currentid` are already inside the
ESummary response the resolver retrieves and it reads only `name`". That is
true of the raw HTTP body and FALSE of what the resolver can see. The
`summary` action allowlists per-database field sets
(`ncbi_eutils_actions._SUMMARY_FIELDS_BY_DB`), and the `gene` row is

    ("name", "description", "chromosome", "maplocation", "genomicinfo",
     "mim", "organism")

so `status` and `currentid` are stripped before the resolver is handed the
record. Measured, not argued, against the live tool on 2026-08-24:

    FIELDS THE RESOLVER CAN SEE:
      ['chromosome','description','genomicinfo','maplocation','mim',
       'name','organism']
      name = 'BRCA3'   status = None   currentid = None

A fix that reads `fields.get("status")` without widening that allowlist
therefore reads `None` for EVERY gene, live or withdrawn, and refuses
nothing, while looking exactly like a working fix. P1 exists to make that
specific failure impossible to ship: it grades the allowlist directly,
upstream of any resolver behaviour.

Widening that allowlist has no citation blast radius, checked rather than
assumed: `action="summary", db="gene"` has exactly ONE production caller in
the repository, this resolver (`core/graph.py:1888`). `act_node`'s
answer-bearing Layer 2 call uses `dataset_report`, a different action
entirely, so no citation the user ever sees is built from these two fields.

## THE FIELD TYPES ARE INCONSISTENT, AND THAT IS THE TRAP

Probed live, 2026-08-24, three records:

    7157   (TP53,  live)        name='TP53'   status=''  (str)  currentid=''  (str)
    60500  (BRCA3, withdrawn)   name='BRCA3'  status=1   (int)  currentid=675 (int)
    353129 (ADHD,  withdrawn)   name='ADHD'   status=1   (int)  currentid=1816(int)

A live record's `status` is the EMPTY STRING. A withdrawn record's is the
INTEGER 1. The adversary report transcribed it as `status= '1'`, a string,
which is a third shape again. So `status == 1` and `status == "1"` are each
correct against some real records and silently inert against others, and
"inert" here means the withdrawn record resolves and the wrong answer ships.
P4 mutates exactly this: it feeds the string form and the int form and
requires both to refuse.

## Exercised here

- P1, THE ALLOWLIST, FIRST, because every other arm is downstream of it and
  passes vacuously if it is wrong. `status` and `currentid` survive the
  `summary` action for `db="gene"` on a real withdrawn record.
- P2, the resolver contributes NO CURIE for a withdrawn symbol, with a LIVE
  control symbol resolved in the same run so a blanket-`None` resolver (a
  blocked network, a dead key) cannot pass this arm.
- P3, the withdrawn record is REPORTED, not merely dropped: the successor id
  is carried out so the refusal can name it.
- P4, TYPE TOLERANCE, offline: `status` as int `1` and as str `"1"` both
  refuse; a live record's empty-string `status` still resolves.
- P5, A SECOND, INDEPENDENT WITHDRAWN SYMBOL (`ADHD`), live, so nothing here
  can pass by special-casing `BRCA3`.
- P6, END OF THE PIPE: `_select_planned_tool_call` returns a refusal and the
  refusal TEXT names the successor, so the decision survives to the user
  rather than stopping at the resolver.
- P7, DISCONTINUED WITH NO SUCCESSOR: refuse, and do NOT fabricate a
  replacement id.
- P8, THE SECOND CHANNEL, added after a live end-to-end run caught what this
  gate could not. The refusal reaches the user as `token` events AND as
  `TrustSignalPayload.message`, and the first version of this fix updated
  only the first, so the event still asserted "NCBI has no record matching
  the name" beside an answer naming the record. P6 could not have caught it:
  the defect was in a call site that never went through the function P6
  grades.

## What this gate does NOT cover, stated because a coverage claim it cannot
## support is the same defect one level up

- It does not run the full `core.run.run()` loop against a real Synth model
  and assert on the rendered answer string. The end-to-end run was performed
  by hand and its transcript is in `tracker/fix_a02_discontinued_gene.md`;
  what is automated here stops at the refusal text. That gap is NOT
  theoretical and is the reason P8 exists: the hand run is what found the
  `trust_signal` half, after every arm in this file was green.
- It does not cover the Datasets leg, because that leg cannot reach this
  defect: `gene/symbol/BRCA3/taxon/human` and `gene/symbol/ADHD/taxon/human`
  each return ZERO reports (probed live 2026-08-24), so a withdrawn symbol
  always falls through to the ESearch leg. If Datasets ever starts returning
  withdrawn records, this gate will not notice, and that is a known gap
  rather than an oversight.
- It does not enumerate every withdrawn gene in NCBI. Two are pinned.
- Vacuity is graded in `test_discontinued_gene_mutation.py`, not here. An arm
  in this file that cannot fail is caught there, in the ordinary suite.

Depends on:
    - system_03_search_agent.core.graph (resolve_symbol_to_curie,
      withdrawn_record_for, _select_planned_tool_call,
      _build_unresolved_entity_refusal_text, _SYMBOL_CURIE_CACHE,
      _WITHDRAWN_SYMBOL_RECORDS)
    - system_03_search_agent.tools.ncbi_efetch (ncbi_efetch)
"""

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

#: A discontinued gene record carrying a replacement. Pinned, with the live
#: values this file was written against, so a reader can re-probe rather than
#: trust the comment.
WITHDRAWN_SYMBOL = "BRCA3"
WITHDRAWN_GENE_ID = "60500"
WITHDRAWN_SUCCESSOR_ID = "675"

#: A SECOND withdrawn symbol, deliberately unrelated to the first. P5 exists
#: because a fix special-cased to BRCA3 passes every other arm in this file.
SECOND_WITHDRAWN_SYMBOL = "ADHD"
SECOND_SUCCESSOR_ID = "1816"

#: A live control. Its `status` is the EMPTY STRING, not absent and not 0,
#: which is exactly the value a naive truthiness check gets wrong in the safe
#: direction and a naive `is not None` check gets wrong in the UNSAFE one.
LIVE_SYMBOL = "TP53"
LIVE_GENE_ID = "7157"


def _load_env_explicitly() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _live_network_is_permitted() -> bool:
    """Whether `tests/conftest.py` is letting real outbound HTTP through.

    Without this the live arms do not skip, they FAIL, and they fail in the
    single most misleading way available for THIS file: a blocked lookup
    makes `resolve_symbol_to_curie` return `None`, which is EXACTLY the value
    P2 is asserting on. A blocked network would render this gate green while
    proving nothing, which is the vacuity failure this whole fix branch is
    downstream of.
    """
    _load_env_explicitly()
    return os.environ.get("RUN_PREMISE_GATE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


#: DELIBERATELY NOT GATED ON THE GRAPH. Nothing in this file traverses Layer
#: 1; every arm is a Layer 2 resolver question. Gating on the graph here
#: would be the false-skip-reason defect build phase 4.12 already owns for
#: seven pre-4.11 files, newly written.
premise_gate = pytest.mark.skipif(
    not _live_network_is_permitted(),
    reason=(
        "this arm reaches live NCBI E-utilities and needs RUN_PREMISE_GATE=1 "
        "so tests/conftest.py permits real outbound HTTP"
    ),
)


@pytest.fixture(autouse=True)
def _clear_resolver_state():
    """Both process-lifetime maps, cleared together, before AND after.

    `_SYMBOL_CURIE_CACHE` short-circuits `resolve_symbol_to_curie` before any
    network call, and `_WITHDRAWN_SYMBOL_RECORDS` is written on the same path.
    Clearing one without the other is how an arm reads a withdrawn note left
    behind by a previous arm and passes without doing the lookup it claims to
    grade.
    """
    from system_03_search_agent.core import graph as graph_module

    graph_module._SYMBOL_CURIE_CACHE.clear()
    graph_module._WITHDRAWN_SYMBOL_RECORDS.clear()
    yield
    graph_module._SYMBOL_CURIE_CACHE.clear()
    graph_module._WITHDRAWN_SYMBOL_RECORDS.clear()


# ---------------------------------------------------------------------------
# P1: the allowlist. First, because every arm below it is vacuous if it fails.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
async def test_p1_summary_action_exposes_status_and_currentid_for_gene():
    """`status` and `currentid` reach the resolver at all.

    This is the arm that the ticket's own stated premise would have skipped.
    It asserts on the TOOL's output, not the resolver's, because the defect it
    guards (an allowlist that strips the two fields) is invisible from the
    resolver: every gene simply looks live.
    """
    from system_03_search_agent.tools.ncbi_efetch import ncbi_efetch
    from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchInput

    output = await ncbi_efetch(
        NcbiEfetchInput.model_validate(
            {"action": "summary", "db": "gene", "ids": [WITHDRAWN_GENE_ID]}
        )
    )

    # POPULATE-CHECK. Not "did the call succeed" but "did it return the
    # record this arm is about". Without this, an empty or errored response
    # makes every assertion below vacuous in the passing direction, since
    # there would be no record to contradict them.
    assert output.status == "ok", f"expected a live ESummary, got {output.status}"
    assert output.records, "ESummary returned no record; nothing to assert on"
    fields = output.records[0].fields
    assert fields.get("name") == WITHDRAWN_SYMBOL, (
        f"pinned id {WITHDRAWN_GENE_ID} is no longer {WITHDRAWN_SYMBOL} "
        f"(got {fields.get('name')!r}); re-pin this arm before trusting it"
    )

    assert "status" in fields, (
        "`status` was stripped before the resolver could see it. The `gene` "
        "row of `_SUMMARY_FIELDS_BY_DB` does not allowlist it, so every "
        "withdrawn record looks live and the F-4.7-A-02 fix is inert."
    )
    assert "currentid" in fields, (
        "`currentid` was stripped before the resolver could see it, so the "
        "refusal cannot name the successor even when it correctly refuses."
    )

    # The VALUES, not merely the keys. A key present with a value the check
    # downstream cannot act on is the safety-by-proxy shape build phase 4.3
    # shipped as a critical twice.
    assert str(fields["status"]).strip() == "1", (
        f"{WITHDRAWN_SYMBOL} is no longer marked discontinued upstream "
        f"(status={fields['status']!r}); this arm's premise is gone"
    )
    assert str(fields["currentid"]).strip() == WITHDRAWN_SUCCESSOR_ID, (
        f"{WITHDRAWN_SYMBOL}'s successor changed upstream "
        f"(currentid={fields['currentid']!r})"
    )


# ---------------------------------------------------------------------------
# P2: the resolver contributes no CURIE.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
async def test_p2_withdrawn_symbol_resolves_to_nothing_live_control_resolves():
    """The defect, at the resolver, with a control that rules out a dead path.

    The control is the whole point of the arm. `None` is both the correct
    answer for a withdrawn symbol AND what a blocked network, an expired key,
    or a rate-limited host returns for EVERY symbol. Asserting only that
    BRCA3 resolves to None cannot tell those apart, so it is an assertion
    that passes when the system is broken.
    """
    from system_03_search_agent.core.graph import resolve_symbol_to_curie

    # POPULATE-CHECK, and it runs FIRST so a dead lookup path fails here with
    # an honest message rather than passing the real assertion below.
    live = await resolve_symbol_to_curie(LIVE_SYMBOL)
    assert live == f"NCBIGene:{LIVE_GENE_ID}", (
        f"the control symbol {LIVE_SYMBOL} did not resolve (got {live!r}), so "
        "the lookup path is dead and a `None` for the withdrawn symbol below "
        "would prove nothing"
    )

    withdrawn = await resolve_symbol_to_curie(WITHDRAWN_SYMBOL)
    assert withdrawn is None, (
        f"{WITHDRAWN_SYMBOL} is a discontinued record and must contribute no "
        f"CURIE, but resolved to {withdrawn!r}. If this is "
        f"NCBIGene:{WITHDRAWN_SUCCESSOR_ID} the system is answering about "
        "BRCA2, which is F-4.7-A-02 exactly."
    )


# ---------------------------------------------------------------------------
# P3: the withdrawal is reported, not merely dropped.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
async def test_p3_withdrawn_record_is_reported_with_its_successor():
    """Refusing is half the decision; naming why is the other half.

    Separated from P2 deliberately. A fix that returns `None` and discards
    everything it learned passes P2 and fails here, and that fix is the
    "refuse silently" option the product owner rejected.
    """
    from system_03_search_agent.core.graph import (
        resolve_symbol_to_curie,
        withdrawn_record_for,
    )

    # POPULATE-CHECK: nothing is recorded until the lookup runs, so an arm
    # that forgot to resolve would read an empty map and could not fail.
    assert withdrawn_record_for(WITHDRAWN_SYMBOL) is None, (
        "the withdrawn map was already populated before this arm looked "
        "anything up; the autouse fixture is not clearing it"
    )

    resolved = await resolve_symbol_to_curie(WITHDRAWN_SYMBOL)
    assert resolved is None, "P2's premise broke; fix that arm first"

    record = withdrawn_record_for(WITHDRAWN_SYMBOL)
    assert record is not None, (
        f"{WITHDRAWN_SYMBOL} was refused but nothing was recorded about WHY, "
        "so the refusal cannot name the successor"
    )
    assert record.curie == f"NCBIGene:{WITHDRAWN_GENE_ID}", (
        f"recorded the wrong withdrawn id: {record.curie!r}"
    )
    assert record.successor_curie == f"NCBIGene:{WITHDRAWN_SUCCESSOR_ID}", (
        f"recorded the wrong successor: {record.successor_curie!r}"
    )


# ---------------------------------------------------------------------------
# P4: type tolerance. Offline, because it is a pure shape question.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status_value", "currentid_value", "expect_withdrawn"),
    [
        # The shape NCBI actually returns for a withdrawn record (int).
        (1, 675, True),
        # The shape the adversary report transcribed (str). Both are real.
        ("1", "675", True),
        # A live record: `status` is the EMPTY STRING, not absent, not 0.
        ("", "", False),
        # Defensive: an absent field must not read as withdrawn.
        (None, None, False),
        # A non-1 status is not a withdrawal.
        (0, "", False),
    ],
    ids=["int-1", "str-1", "live-empty-string", "absent", "status-0"],
)
def test_p4_status_is_read_by_value_not_by_type(
    status_value, currentid_value, expect_withdrawn
):
    """`status` is `1` (int) on a real withdrawn record and `""` (str) on a
    live one. A check written against either type alone is inert against the
    other, and "inert" means the wrong answer ships.

    Graded through the module's own classifier rather than by re-implementing
    the rule here, which would make this arm agree with itself.
    """
    from system_03_search_agent.core.graph import _classify_gene_record_status

    fields = {"name": WITHDRAWN_SYMBOL}
    if status_value is not None:
        fields["status"] = status_value
    if currentid_value is not None:
        fields["currentid"] = currentid_value

    result = _classify_gene_record_status(fields)

    assert (result is not None) is expect_withdrawn, (
        f"status={status_value!r} ({type(status_value).__name__}) classified "
        f"as {'withdrawn' if result else 'live'}, expected "
        f"{'withdrawn' if expect_withdrawn else 'live'}"
    )
    if expect_withdrawn:
        assert result == WITHDRAWN_SUCCESSOR_ID, (
            f"successor id not read from currentid={currentid_value!r}: "
            f"got {result!r}"
        )


# ---------------------------------------------------------------------------
# P5: a second, independent withdrawn symbol.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
async def test_p5_a_second_unrelated_withdrawn_symbol_also_refuses():
    """Nothing here may pass by special-casing BRCA3.

    ADHD is the other shape of this defect that matters in practice: it is a
    common acronym a user types meaning the condition, and it resolves to a
    withdrawn GENE record whose successor is an unrelated gene.
    """
    from system_03_search_agent.core.graph import (
        resolve_symbol_to_curie,
        withdrawn_record_for,
    )

    resolved = await resolve_symbol_to_curie(SECOND_WITHDRAWN_SYMBOL)
    assert resolved is None, (
        f"{SECOND_WITHDRAWN_SYMBOL} is discontinued and must contribute no "
        f"CURIE, but resolved to {resolved!r}"
    )

    record = withdrawn_record_for(SECOND_WITHDRAWN_SYMBOL)
    assert record is not None, (
        f"{SECOND_WITHDRAWN_SYMBOL} refused with nothing recorded about why"
    )
    # The SUCCESSOR, not just presence. A fix that records a constant, or
    # records BRCA3's successor for every symbol, passes a presence check.
    assert record.successor_curie == f"NCBIGene:{SECOND_SUCCESSOR_ID}", (
        f"{SECOND_WITHDRAWN_SYMBOL}'s successor recorded as "
        f"{record.successor_curie!r}, expected NCBIGene:{SECOND_SUCCESSOR_ID}"
    )


# ---------------------------------------------------------------------------
# P6: end of the pipe. The decision reaches the user.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p6_refusal_text_names_the_successor():
    """A resolver that refuses correctly and a refusal the user never sees is
    the "refuse silently" option, not the one that was chosen.

    Offline on purpose: it grades the TEXT built from a recorded withdrawal,
    which is a pure function of that record. The live half (that the record
    gets there at all) is P3's job, and splitting them means a network
    failure cannot make this arm skip and hide a text regression.
    """
    from system_03_search_agent.core import graph as graph_module

    graph_module._WITHDRAWN_SYMBOL_RECORDS["BRCA3:human"] = (
        graph_module._WithdrawnGeneRecord(
            symbol=WITHDRAWN_SYMBOL,
            curie=f"NCBIGene:{WITHDRAWN_GENE_ID}",
            successor_curie=f"NCBIGene:{WITHDRAWN_SUCCESSOR_ID}",
        )
    )

    planned = await graph_module._select_planned_tool_call(
        "Which diseases are associated with BRCA3?",
        "multi_hop",
        [],
        [WITHDRAWN_SYMBOL],
    )
    assert isinstance(planned, graph_module._UnresolvedEntityRefusal), (
        f"a withdrawn symbol must refuse, not plan a tool call: {planned!r}"
    )

    text = graph_module._build_unresolved_entity_refusal_text(
        planned.attempted_symbols
    )

    assert WITHDRAWN_SYMBOL in text, (
        f"the refusal does not name what the user asked about: {text!r}"
    )
    assert "discontinued" in text.lower(), (
        "the refusal does not say the record was discontinued, so it reads "
        f"as an ordinary 'no such gene': {text!r}"
    )
    assert WITHDRAWN_SUCCESSOR_ID in text, (
        f"the refusal does not name the successor id, which is the whole "
        f"difference between this option and refusing silently: {text!r}"
    )
    # The refusal must not read as an ANSWER about the successor. This is the
    # exact sentence F-4.7-A-02 shipped.
    assert "returned a gene record for" not in text, (
        f"the refusal is phrased as an answer about the successor: {text!r}"
    )


# ---------------------------------------------------------------------------
# P7: discontinued with no successor.
# ---------------------------------------------------------------------------


def test_p7_discontinued_without_successor_refuses_without_inventing_one():
    """Not every withdrawn record has a replacement.

    The failure this blocks is a fix that reads `currentid` unconditionally
    and emits `NCBIGene:` with nothing after it, or worse, `NCBIGene:0`, into
    a user-facing sentence.
    """
    from system_03_search_agent.core import graph as graph_module

    for empty in ("", 0, None):
        fields = {"name": "SOMEGENE", "status": 1}
        if empty is not None:
            fields["currentid"] = empty

        result = graph_module._classify_gene_record_status(fields)
        assert result is not None, (
            f"status=1 with currentid={empty!r} must still be a withdrawal; "
            "a missing successor is not a live record"
        )
        assert result == "", (
            f"currentid={empty!r} produced a fabricated successor {result!r}"
        )

    record = graph_module._WithdrawnGeneRecord(
        symbol="SOMEGENE", curie="NCBIGene:99999", successor_curie=""
    )
    text = graph_module._withdrawn_clause([record])
    assert "SOMEGENE" in text
    assert "discontinued" in text.lower()
    assert "NCBIGene:" not in text.replace("NCBIGene:99999", ""), (
        f"a successor CURIE was fabricated where there is none: {text!r}"
    )


# ---------------------------------------------------------------------------
# P8: the SECOND channel. Added after a live run caught what P6 could not.
# ---------------------------------------------------------------------------


def test_p8_trust_signal_message_states_the_same_fact_as_the_answer_text():
    """The refusal reaches the user through TWO channels, and P6 graded one.

    `write_node` emits the refusal as `token` events AND as
    `TrustSignalPayload.message`, which is what a surface rendering the
    structured event shows instead of the stream. The first version of this
    fix updated the token text and left the event pointed at the bare
    constant, so a live end-to-end run produced:

        [trust_signal] "...NCBI has no record matching the name in your
                        question, so no graph query was attempted."
        ANSWER TEXT    "BRCA3 is a discontinued NCBI gene record
                        (NCBIGene:60500), replaced by NCBIGene:675. ..."

    Both describing the same refusal, disagreeing on whether NCBI holds a
    record. That is worse than either being wrong alone: whichever channel a
    consumer trusts is now a coin flip.

    This arm exists because P6 could not have caught it. P6 grades
    `_build_unresolved_entity_refusal_text`, and the defect was in a call
    site that never went through that function. Found by RUNNING the thing,
    not by reading it, which is the same lesson build phase 4.8 recorded when
    two major layout defects survived 147 unit tests.
    """
    from system_03_search_agent.core import graph as graph_module

    graph_module._WITHDRAWN_SYMBOL_RECORDS["BRCA3:human"] = (
        graph_module._WithdrawnGeneRecord(
            symbol=WITHDRAWN_SYMBOL,
            curie=f"NCBIGene:{WITHDRAWN_GENE_ID}",
            successor_curie=f"NCBIGene:{WITHDRAWN_SUCCESSOR_ID}",
        )
    )

    message = graph_module._unresolved_entity_refusal_message([WITHDRAWN_SYMBOL])
    text = graph_module._build_unresolved_entity_refusal_text([WITHDRAWN_SYMBOL])

    # POPULATE-CHECK: the withdrawn branch actually fired. Without this both
    # channels could agree on the GENERIC message and the arm would pass
    # while stating nothing about a withdrawal.
    assert "discontinued" in message.lower(), (
        f"the withdrawn branch did not fire, so agreement below is vacuous: "
        f"{message!r}"
    )

    assert message in text, (
        "the two channels are not built from one source: the event message "
        f"{message!r} is not contained in the answer text {text!r}"
    )
    assert "NCBI has no record matching" not in message, (
        f"the event still asserts NCBI holds no record: {message!r}"
    )
    # The event field is bounded at 500 characters by the contract.
    assert len(message) <= 500, (
        f"message is {len(message)} chars, over TrustSignalPayload's bound"
    )


# ---------------------------------------------------------------------------
# P9: an alias-ambiguous symbol still resolves to its OWN gene.
# ---------------------------------------------------------------------------

#: A real gene whose `[sym]` ESearch returns MORE THAN ONE id, because NCBI
#: indexes that tag against alias and synonym tables as well as the approved
#: symbol. Probed live 2026-08-24: `GCK[sym] AND human[orgn]` returns
#: ['2645', '56975', '5871']. 2645 is GCK; the other two match by alias.
ALIAS_AMBIGUOUS_SYMBOL = "GCK"
ALIAS_AMBIGUOUS_GENE_ID = "2645"


@premise_gate
@pytest.mark.asyncio
async def test_p9_an_alias_ambiguous_symbol_resolves_to_its_own_gene():
    """The refusal this closes was over-strict, not wrong-headed.

    The rule it replaces ("zero or multiple ids resolve to None rather than
    guessing among them") exists because a `[sym]`-tagged match is not proof
    the returned gene's OWN symbol is the one searched for. That reasoning is
    correct and is NOT being relaxed: what changes is that the answer is
    looked up rather than assumed absent.

    The resolver already confirms the official symbol for a single hit. It
    simply never did so for a multi-hit, and so refused `GCK`, a real gene
    with a real record, because two OTHER genes list it as an alias. Measured
    live on the deployed demo, 2026-08-24: "Variants in GCK causing MODY"
    returned "I could not identify that gene. NCBI has no record matching the
    name in your question", which is a false statement about a gene NCBI
    plainly has.

    The safety property is unchanged and is asserted here: EXACTLY ONE
    candidate may claim the symbol as its own. Zero still refuses, and so
    does more than one.
    """
    from system_03_search_agent.core.graph import resolve_symbol_to_curie

    # POPULATE-CHECK first: the live control resolves, so a None below is
    # about this symbol rather than about a dead lookup path.
    live = await resolve_symbol_to_curie(LIVE_SYMBOL)
    assert live == f"NCBIGene:{LIVE_GENE_ID}", (
        f"the control symbol {LIVE_SYMBOL} did not resolve (got {live!r}); "
        "the lookup path is dead and this arm would prove nothing"
    )

    resolved = await resolve_symbol_to_curie(ALIAS_AMBIGUOUS_SYMBOL)
    assert resolved == f"NCBIGene:{ALIAS_AMBIGUOUS_GENE_ID}", (
        f"{ALIAS_AMBIGUOUS_SYMBOL} resolved to {resolved!r}. It must resolve "
        f"to NCBIGene:{ALIAS_AMBIGUOUS_GENE_ID}, the gene whose OWN official "
        "symbol is that string, rather than being refused because two other "
        "genes list it as an alias"
    )


def test_p9b_ambiguity_still_refuses_when_no_candidate_owns_the_symbol():
    """The half that must NOT be relaxed.

    Selecting among candidates is only safe because exactly one of them can
    claim the symbol as its own official name. If none can, or if two could,
    the original refusal is still the right answer, and this arm is what
    stops the fix from degrading into "pick the first hit".
    """
    from system_03_search_agent.core.graph import _select_candidate_owning_symbol

    def rec(uid, name):
        return type("R", (), {"id": uid, "fields": {"name": name}})()

    # None of the three owns "GCK": all match by alias only.
    assert _select_candidate_owning_symbol(
        [rec("1", "HK4"), rec("2", "MODY2"), rec("3", "HHF3")], "GCK"
    ) is None

    # Two claim it: genuinely ambiguous, refuse.
    assert _select_candidate_owning_symbol(
        [rec("1", "GCK"), rec("2", "GCK")], "GCK"
    ) is None

    # Exactly one owns it, among decoys.
    chosen = _select_candidate_owning_symbol(
        [rec("56975", "CTDP1"), rec("2645", "GCK"), rec("5871", "MAP4K2")], "GCK"
    )
    assert chosen is not None and chosen.id == "2645"
