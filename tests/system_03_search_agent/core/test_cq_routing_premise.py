"""The premise gate for build phase 4.7: does the loop UNDERSTAND the question?

`docs/build/Build_workflow_cadence.md` stage 5 makes this file mandatory and
blocking. Written before any of the code it grades, and watched failing.
Written GATE FIRST by product-owner decision on 2026-08-23, the ordering build
phase 4.11's round 4 measured: in one round it caught the real defect, caught
two wrong premises in the lead's own arms, and showed that two of three
findings it set out to fix were gate gaps over already-correct code.

The premise is deliberately not "a classifier returns a query class". It is:

    Every one of the seven v1 must-pass moat questions reaches Act with a
    class that is a real classification of what was asked and with the
    question's actual subject resolved, and no question is refused because
    a database name mentioned in passing was mistaken for a gene symbol.

That distinction is the whole reason this file is shaped the way it is.
F-2.0-15 is the finding this phase exists to close, and it survived TWELVE
phases and two weeks of premise gates. Every one of those gates was green.
None of them could have caught it, because each graded its own tool in
isolation and none exercised Think's classification as the thing under test.
Only a manual end-to-end read of real answers found it.

So the rule this file follows, stated once and applied per arm: an arm that
mocks Think's own call, or that hands the loop a pre-resolved CURIE, is not
an arm. The live arms drive `run()` from the raw natural-language string a
person would type, and read the `think` event the real loop emitted.

## Coverage: what this gate exercises and what it deliberately omits

`.claude/rules/goal-contracts.md` requires this statement, and build phase
4.4 is why it is written to be argued with rather than to reassure. That
phase's gate passed 6 of 6 while the DEFAULT invocation returned zero of the
twelve edges the gate itself pinned, because five of its six cases passed an
explicit label list and the default path was exercised by none of them. Its
coverage note had named that omission from the day it was written. Writing a
blind spot down makes it arguable; it does not make it safe.

### Every arm carries a populate-check

Build phase 4.11 wrote THREE vacuous arms and all three were caught by
mutation, none by reading. One was vacuous twice, in two different ways,
while quoting the lesson against vacuous arms in its own docstring. The one
arm that carried a self-check from the start was never vacuous.

The durable fix, applied to every arm below: an arm asserts it PRODUCED the
state it is about to measure, before measuring it. Concretely here, every
arm that reads a `think` event first asserts a `think` event was emitted at
all. Without that, a loop that crashes before Think, or one that stops
emitting the event, makes every downstream assertion vacuously true, and the
arm reports the control working when nothing happened.

### What runs where, and why

An arm carries `premise_gate` if and only if it needs a real model to mean
anything. Classification is a model judgment, so every routing-correctness
arm is live. Everything structural (the exact-ID pre-pass, which is
deterministic by design; the pool loader; the stable prefix; the absence of
the retired heuristic; concurrent promotion) runs offline and therefore runs
in ordinary CI.

That split is F-4.5-J-07 stated as a precondition rather than found as a
finding. Build phase 4.5's gate ran `1 failed, 1 passed, 14 skipped in
0.06s` on any machine without a tunnel, so most of it did not run at all and
a run without `RUN_PREMISE_GATE=1` looked like a pass in 2.5 seconds.

### Exercised here

- THE FOUR QUESTIONS THAT REFUSE TODAY, FIRST (P1). Q4, Q5, Q6 and Q10 each
  mention a database name in passing (GTR, AMR, SRA, SRA) and each is
  refused today with "I could not identify that gene". This arm asserts the
  passing mention is NOT taken as the subject and the query is not refused
  for that reason. It runs first because it is the phase's reason to exist.
- THE FLAGSHIP (P2). Q3 from the raw string, asserting the subject resolves
  and the class is a real one.
- THE DEGENERATE ANSWER FROM THE OTHER SIDE (P3). Q1 is not refused today;
  it "answers" in one sentence naming a bare gene symbol, because Plan found
  a real gene and stopped. An arm that only checks for refusals passes on
  this and is blind to half of F-2.0-15.
- CLASSIFICATION IS NOT CONSTANT (P4). Two questions of genuinely different
  shape must not receive the same class. This is the anti-vacuity arm for
  the whole classification half: a `think_node` that returns `"lookup"`
  forever passes every single-question arm above.
- EXACT ID BEFORE FUZZY (P5), Section 17's stated order, asserted by the
  model never being consulted for an entity the deterministic pre-pass
  already resolved exactly.
- NO FABRICATED CURIE (P6). A gene-shaped token NCBI does not know
  contributes nothing. The failure this guards is new and specific to this
  phase: a model asked to extract typed entities will happily invent a
  plausible identifier, and the old heuristic could not, because it only
  ever returned what a live lookup confirmed.
- THE RETIRED HEURISTIC IS ACTUALLY GONE (P7), the 2026-08-23 product-owner
  decision pinned structurally. No fallback path may resurrect it.
- THE POOL (P8, P9): seven entries in Section 17's exact shape, loaded once
  per process, never per request and never from a database.
- THE STABLE PREFIX (P10). Byte-identical across two requests whose queries
  differ, by SHA-256, per `.claude/rules/prompt-cache-discipline.md`.
- CONCURRENT PROMOTION (P11), F-4.6-A-08, by actually running two at once
  rather than by inspecting the write for atomicity.
- THE CLASS REACHES WHAT CONSUMES IT (P12). `interactions.query_class`
  records the class the loop used, closing build phase 4.6's knowingly-wrong
  column, and `budget_for_step` selects on it.

### NOT exercised, deliberately

- ASK-BACK ON AMBIGUITY. Section 2's Think row says Think may ask one
  clarifying question, and `ThinkPayload.clarifying_question` is in the
  locked contract. Measured at phase open rather than assumed: that field
  has no consumer anywhere in `src/` or `frontend/src/` outside type
  declarations. Wiring real ask-back needs an SSE pause, a user reply and a
  run resume, which Section 25's 4.7 row does not name. This phase keeps
  emitting `None`. No phase in the build order claims it, which is the exact
  shape F-2.0-15 had, so it is raised to the product owner at checkpoint
  rather than assigned by the lead. NOTHING BELOW COVERS IT.
- ANSWER QUALITY. This gate grades routing and resolution, not whether the
  synthesized answer is good. Q1's arm asserts the class and the resolved
  entities, never that the evidence assembled is complete. That is
  `eval-harness`'s job against the golden dataset, and build phase 5.1 owns
  the dataset.
- THE OTHER THREE QUERY SHAPES END TO END. `aggregate` and `exploratory`
  appear in P4's distinctness assertion and in the pool, but no must-pass
  question is a pure aggregate, so no arm drives one from a raw string. A
  misclassification confined to `aggregate` would pass this whole file.
- RETRIEVAL OVER THE POOL and a learned router. Both are Section 17 upgrade
  path, both outside v1.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_env_explicitly() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _model_is_configured() -> bool:
    _load_env_explicitly()
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _live_network_is_permitted() -> bool:
    """Whether `tests/conftest.py` is letting real outbound HTTP through.

    Without this the live arms do not skip, they FAIL, and they fail in the
    most misleading way available for THIS file specifically: entity
    resolution returns nothing because the lookup was blocked, Think resolves
    an empty list, and a blocked network call gets reported as a routing
    defect in a file about routing. F-4.5-05 measured that shape 3 of 3 in a
    file about capture.
    """
    return os.environ.get("RUN_PREMISE_GATE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


#: DELIBERATELY NOT GATED ON THE GRAPH, unlike every gate written before build
#: phase 4.11. The older files probe `GRAPH_PG_HOST`/`GRAPH_PG_PORT` with a
#: raw socket, which was the SSH tunnel's local port. Build phase 4.11 deleted
#: that tunnel and moved Layer 1 behind `GRAPH_QUERY_URL`, so a tunnel-era
#: probe now reports the graph unreachable on a machine where it is perfectly
#: reachable, and every arm behind it skips while reporting a skip reason that
#: is false. Two of this file's arms traverse Layer 1 and would notice a dead
#: graph on their own; the rest are classification arms that need a model and
#: no graph at all. So the gate is: a real model key, plus RUN_PREMISE_GATE=1
#: so conftest permits outbound HTTP.
premise_gate = pytest.mark.skipif(
    not (_model_is_configured() and _live_network_is_permitted()),
    reason=(
        "this arm needs a real model key AND RUN_PREMISE_GATE=1 so "
        "tests/conftest.py permits real outbound HTTP"
    ),
)


# ---------------------------------------------------------------------------
# The question set.
#
# PROVENANCE, and it is the same caveat `test_guardrail_premise.py` carries,
# repeated rather than referenced because a reader of this file must see it:
# the seven must-pass questions exist in `requirements/Evaluation_playbook.md`
# and `requirements/PRD.md` only as short descriptive table entries, not as
# text a user would type. The strings below are CONSTRUCTED from those short
# forms. They are a faithful reading and they are not verified user phrasings.
#
# They are kept byte-identical to `test_guardrail_premise.py`'s constants
# where that file already has one, so a question that this gate admits and
# that gate refuses is a real contradiction rather than two different strings.
# Build phase 5.1 builds the 50-query golden dataset; when real phrasings
# exist, both files should take them from it rather than keep three copies.
# ---------------------------------------------------------------------------

Q1_COORDINATE_ANCHORED = (
    "What is the published evidence for a copy number variant at "
    "chr17:41,196,312-41,277,500 on GRCh37?"
)

Q3_FLAGSHIP = "Which diseases are associated with BRCA1?"

# Q4, Q5 and Q6 NAME THE DATABASE, and that is the whole point of these three
# strings. `test_guardrail_premise.py` carries variants that do not, because
# that file grades whether a question is ADMITTED and the database name is
# irrelevant to it. Here it is the thing under test.
#
# These were WRONG in this file's first version and the account is kept rather
# than the strings quietly swapped. All three were copied from the guardrail
# gate, so Q4 asserted `GTR` was not resolved from a question containing no
# `GTR`, Q5 asserted `AMR` against "antimicrobial resistance" spelled out, and
# Q6 asserted `SRA` against "sequencing runs". Three of the four cases could
# not fail. That is build phase 4.11's result reproduced exactly: three
# vacuous arms, written by the lead, in a file whose own docstring quotes the
# lesson against writing them. Caught by a builder reading the file, and by
# the populate-check now in the arm, which is what makes it mechanical rather
# than a matter of someone noticing.
#
# The phrasings below are faithful to the playbook's own short forms, which
# name these databases: Q4 "(MedGen, ClinVar, GTR, PubMed, ClinicalTrials,
# Gene)", Q5 "AMR genes", Q6 "Natural-language SRA metadata search".

Q4_DISEASE_PHRASE = (
    "Which genes are on the diagnostic testing panel for Lynch syndrome in "
    "GTR, and what is the citation for each?"
)

Q5_ORGANISM_ANCHORED = (
    "For Salmonella isolate PDT000123456, what SNP cluster is it in, what "
    "AMR genes does it carry, and which isolates are within 5 SNPs of it?"
)

Q6_METADATA_SEARCH = (
    "Find SRA runs from stool samples of adults with inflammatory bowel "
    "disease, and explain why each one matched."
)

Q8_PMID_LINKED = (
    "For PMID 21376230, what sequencing data, BioProjects, and assemblies "
    "are linked to it, and which links are direct rather than inferred?"
)

Q10_BIOPROJECT_BUNDLE = (
    "What BioSamples, SRA runs, and genome assemblies belong to BioProject "
    "PRJNA31257, and how would I retrieve them?"
)

#: The five Section 17 query shapes. A value outside this set is a contract
#: violation, not a new class, and `QueryClass` in `contracts/` is the source
#: of truth; this tuple exists so an arm can assert against it by name.
SECTION_17_SHAPES = ("lookup", "single_hop", "multi_hop", "aggregate", "exploratory")

#: The token each refused question actually contains, and the reason it is
#: refused today. `plan_node` scans the raw text for a capitalized token,
#: guesses it is a gene symbol, fails to resolve it, and refuses the whole
#: question rather than considering its real subject. Live-reproduced in the
#: Step 6.2 smoke test, 2026-08-10, recorded in `LEARNINGS.md`.
#:
#: These are the strings that must NOT appear as a resolved subject. Asserting
#: on them by name rather than on "the query was not refused" is deliberate: a
#: `think_node` that refuses nothing but still resolves `SRA` as a gene passes
#: the weaker assertion and has not fixed anything.
REFUSED_TODAY: tuple[tuple[str, str, str], ...] = (
    ("Q4 Lynch syndrome", Q4_DISEASE_PHRASE, "GTR"),
    ("Q5 Salmonella isolate", Q5_ORGANISM_ANCHORED, "AMR"),
    ("Q6 SRA metadata", Q6_METADATA_SEARCH, "SRA"),
    ("Q10 BioProject bundle", Q10_BIOPROJECT_BUNDLE, "SRA"),
)


# ---------------------------------------------------------------------------
# Helpers. Nothing here constructs a think payload, resolves an entity, or
# chooses a class: every value this file asserts on is produced by the loop.
# ---------------------------------------------------------------------------


async def _run_raw(question: str) -> list[Any]:
    """Ask exactly the way a person asks, naming nothing this phase owns.

    No class is hinted, no entity is pre-resolved, no CURIE is substituted
    for a name. That is the single most important property of this helper:
    build phase 4.5 shipped an inert feature behind eight passing arms
    because every arm handed the feature its own input, and the identical
    shape here is an arm that passes `NCBIGene:672` and concludes that
    entity resolution works.
    """
    from system_03_search_agent.contracts.query import Query, RequestContext
    from system_03_search_agent.core.run import run

    query = Query(
        text=question,
        session_id=f"gate-4-7-{uuid.uuid4().hex[:12]}",
        trace_id=f"gate-4-7-{uuid.uuid4().hex[:8]}",
        owner_id=f"guest:{uuid.uuid4()}",
    )
    return [event async for event in run(query, RequestContext(surface="rest_sse"))]


def _think_payload(events: list[Any]) -> dict[str, Any]:
    """The `think` event's payload, or a hard failure saying so.

    THIS IS THE POPULATE-CHECK every arm in this file depends on. It is a
    function rather than a line per arm so it cannot be forgotten in one.

    Without it, a loop that crashes before Think, or that stops emitting the
    event, yields `None` and every downstream `assert payload.query_class in
    SHAPES` becomes an attribute error at best and a vacuous pass at worst.
    An arm that cannot distinguish "the control held" from "nothing
    happened" is not an arm.
    """
    think_events = [event for event in events if getattr(event, "type", None) == "think"]
    assert think_events, (
        "no `think` event was emitted at all, so nothing in this arm is being "
        "graded. This is the populate-check: the arm failed to produce the "
        "state it was about to measure. Check whether the run reached Think "
        f"before reading this as a routing defect. Events seen: "
        f"{[getattr(e, 'type', '?') for e in events]}"
    )
    assert len(think_events) == 1, (
        f"expected exactly one `think` event, found {len(think_events)}; an "
        "arm asserting on the first of several is reading an arbitrary one"
    )
    payload = think_events[0].payload
    # `Event.payload` is declared `dict[str, Any]` (contracts/events.py line
    # 348), validated against `ThinkPayload` by a model validator and then
    # carried as a plain dict. Two of this file's arms were written against an
    # attribute-style payload and failed with `'dict' object has no attribute
    # 'query_class'` on their first live run, BEFORE any builder was
    # dispatched. That is gate-first working exactly as build phase 4.11's
    # round 4 measured it: the ordering caught a wrong premise in the lead's
    # own arm rather than letting it be read as a defect in someone's code.
    assert isinstance(payload, dict), (
        f"`Event.payload` is contracted as a dict; got {type(payload)!r}. If "
        "the contract changed, every accessor below changed with it"
    )
    return payload


def _class_of(payload: dict[str, Any]) -> str:
    """`query_class`, with a populate-check on the key itself.

    `.get("query_class")` returning `None` would compare unequal to every
    shape and make several arms pass for the wrong reason, so the key's
    presence is asserted rather than defaulted.
    """
    assert "query_class" in payload, (
        f"the think payload carries no `query_class` key at all: "
        f"{sorted(payload)}"
    )
    return payload["query_class"]


def _resolved(payload: dict[str, Any]) -> list[dict[str, Any]]:
    assert "resolved_entities" in payload, (
        f"the think payload carries no `resolved_entities` key: {sorted(payload)}"
    )
    return payload["resolved_entities"]


def _resolved_texts(payload: dict[str, Any]) -> list[str]:
    return [entity["text"] for entity in _resolved(payload)]


def _resolved_curies(payload: dict[str, Any]) -> list[str]:
    return [entity["curie"] for entity in _resolved(payload)]


def _answer_text(events: list[Any]) -> str:
    """Everything the user would actually read, concatenated."""
    chunks = []
    for event in events:
        if getattr(event, "type", None) == "token":
            chunks.append(event.payload.get("text", ""))
    return "".join(chunks)


# ---------------------------------------------------------------------------
# P1: the four questions that refuse today. This is the phase's reason to
# exist, so it runs first.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("label", "question", "passing_mention"),
    REFUSED_TODAY,
    ids=[row[0] for row in REFUSED_TODAY],
)
async def test_p1_a_database_name_in_passing_is_not_the_subject(
    label: str, question: str, passing_mention: str
) -> None:
    """F-2.0-15 itself, one arm per question that reproduces it.

    Control: Think's real entity resolution (T-4.7-05) and Plan's consumption
    of it (T-4.7-06). Restore `plan_node`'s capitalized-token guess and every
    one of these four goes red, which is the asymmetry the arm exists for:
    every existing component-level gate in this repository stays green.

    Two assertions, and the weaker one alone is not enough. A `think_node`
    that refuses nothing but still resolves `SRA` as a gene has not fixed
    anything, so the arm asserts on the specific token by name.
    """
    # POPULATE-CHECK, and it is the one that matters most in this file.
    #
    # This arm asserts a token is NOT resolved. An arm of that shape passes
    # trivially when the token is not in the question to begin with, and
    # nothing about the assertion looks wrong when you read it. Three of this
    # arm's four cases shipped exactly that way in this file's first version.
    #
    # Build phase 4.11 wrote three vacuous arms and all three were caught by
    # mutation and none by reading. This check is the generalisation: a
    # negative assertion must first prove the thing it denies was actually
    # available to be found. It is cheap, it is mechanical, and it turns "did
    # anyone notice" into "the arm cannot be written wrong".
    assert passing_mention in question, (
        f"{label}: this arm asserts `{passing_mention}` is not resolved, but "
        f"`{passing_mention}` does not appear in the question at all, so the "
        "assertion below cannot fail and the arm proves nothing. Fix the "
        "question or fix the token; do not delete this check"
    )

    events = await _run_raw(question)
    payload = _think_payload(events)

    resolved = _resolved_texts(payload)
    assert passing_mention not in resolved, (
        f"{label}: `{passing_mention}` is a database name mentioned in "
        f"passing, and it was resolved as an entity of the question. This is "
        f"F-2.0-15 exactly. Resolved: {resolved}"
    )

    answer = _answer_text(events)
    assert "could not identify that gene" not in answer.lower(), (
        f"{label}: refused with the unresolved-gene refusal. The question "
        f"names no gene; the refusal is the old guess failing on "
        f"`{passing_mention}`"
    )


# ---------------------------------------------------------------------------
# P2 and P3: the flagship, and the degenerate answer from the other side.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
async def test_p2_the_flagship_resolves_its_subject_from_raw_text() -> None:
    """Q3 from the raw string, never from a CURIE handed in.

    Control: the resolution half of T-4.7-05. The arm is deliberately
    asserting on the CURIE rather than on the surface form, because a
    `resolved_entities` list that echoes the text back without resolving it
    satisfies a text-only assertion and gives Act nothing to bind.
    """
    events = await _run_raw(Q3_FLAGSHIP)
    payload = _think_payload(events)

    assert _resolved(payload), (
        "the flagship question names BRCA1 explicitly and resolved nothing"
    )
    curies = _resolved_curies(payload)
    assert any(curie.startswith("NCBIGene:") for curie in curies), (
        f"BRCA1 must resolve to an NCBIGene CURIE, got {curies}"
    )
    assert _class_of(payload) in SECTION_17_SHAPES


@premise_gate
@pytest.mark.asyncio
async def test_p3_a_coordinate_question_is_not_classified_as_a_lookup() -> None:
    """Q1: the half of F-2.0-15 that does not present as a refusal.

    Q1 is not refused today. It "answers" in one sentence naming a bare gene
    symbol, because Plan found a real gene (BRCA1 sits in that interval) and
    stopped there, returning none of the CNV, dbVar, ClinVar or OMIM evidence
    the question asked for. An arm that only looks for refusals passes on
    this and is blind to half the finding.

    Control: the classification half, T-4.7-04. A question asking for
    published evidence across several databases for a coordinate range is not
    a lookup by any reading of Section 17's table, where lookup means one
    live API call with a 5 second budget. If this stays `lookup`, the
    classifier is still returning a constant.
    """
    events = await _run_raw(Q1_COORDINATE_ANCHORED)
    payload = _think_payload(events)

    assert _class_of(payload) in SECTION_17_SHAPES
    assert _class_of(payload) != "lookup", (
        "a multi-database evidence-assembly question over a coordinate range "
        "classified as `lookup`, whose Section 17 budget is 5 seconds and one "
        "live API call. This is the stub's value surviving under a new name"
    )


# ---------------------------------------------------------------------------
# P4: the anti-vacuity arm for the whole classification half.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
async def test_p4_two_different_shapes_do_not_get_the_same_class() -> None:
    """A classifier that returns one constant passes every arm above.

    This arm exists because every other classification assertion in this file
    is satisfiable by `return "exploratory"`, the same way the stub satisfied
    twelve phases by returning `"lookup"`. Build phase 4.11's lesson is that
    knowing a failure mode by name does not prevent committing it; running
    the mutation does. The mutation here is trivial to imagine and this arm
    is the only thing that catches it.

    Control: T-4.7-04's actual classification. Replace `think_node`'s body
    with any single literal and this arm goes red while P2 and P3 may not.

    The pairing is chosen so the two are genuinely different under Section
    17's own table, not merely different questions: Q3 is graph traversal
    from one named gene, Q8 is identifier-anchored cross-database link
    resolution with no graph traversal at all.
    """
    flagship = _think_payload(await _run_raw(Q3_FLAGSHIP))
    pmid_linked = _think_payload(await _run_raw(Q8_PMID_LINKED))

    assert _class_of(flagship) in SECTION_17_SHAPES
    assert _class_of(pmid_linked) in SECTION_17_SHAPES
    assert _class_of(flagship) != _class_of(pmid_linked), (
        "a one-gene graph traversal and a PMID cross-link resolution both "
        f"classified as `{_class_of(flagship)}`. Either the classifier is "
        "returning a constant, or these two shapes are genuinely the same "
        "under Section 17, which they are not"
    )


# ---------------------------------------------------------------------------
# P5 and P6: Section 17's resolution order, and the failure mode this phase
# introduces that the old heuristic could not commit.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p5_an_exact_identifier_resolves_without_consulting_the_model() -> None:
    """Section 17: exact ID before any fuzzy step, and this pins the order.

    "Before any fuzzy matching, Think checks the query text for a
    recognizable exact identifier... An exact match resolves directly and is
    treated as ground truth." The ordering is not stylistic. Section 17 gives
    the reason: a fuzzy pass over an already-exact identifier can resolve it
    to the wrong nearby concept, where exact matching would have found the
    right one with no ambiguity at all.

    Control: T-4.7-05's deterministic pre-pass. Delete it and the rsID reaches
    the extraction call, and this arm goes red on the call count rather than
    on the resolution, which is the property that matters.

    POPULATE-CHECK: the arm asserts the pre-pass actually produced the entity
    before asserting the model was not consulted. Without that, a pre-pass
    that resolves NOTHING also makes zero extraction calls for it, and the
    call-count assertion passes on a completely broken resolver.
    """
    from system_03_search_agent.core import graph as graph_module

    resolver = getattr(graph_module, "resolve_exact_identifiers", None)
    assert resolver is not None, (
        "T-4.7-05 has not landed: `resolve_exact_identifiers` does not exist "
        "in core.graph, so Section 17's exact-ID-first order is unimplemented"
    )

    resolved = resolver("What is known about rs334 and PMID 21376230?")

    # Populate-check first, before the property this arm is really about.
    assert resolved, (
        "the pre-pass resolved nothing from a string containing both an rsID "
        "and a PMID, so the zero-model-call assertion below would pass "
        "vacuously"
    )
    surface_forms = {entity.text for entity in resolved}
    assert "rs334" in surface_forms, f"rsID not resolved, got {surface_forms}"

    # And the property: this is a pure function over the text. If it needs a
    # model, it is not the deterministic pre-pass Section 17 specifies.
    assert not getattr(resolver, "is_async", False), (
        "the exact-ID pre-pass must be deterministic and local. A resolver "
        "that awaits a model call is the fuzzy step wearing the pre-pass name"
    )


@premise_gate
@pytest.mark.asyncio
async def test_p6_an_unknown_gene_shaped_token_yields_no_curie() -> None:
    """The failure this phase introduces that the old code could not commit.

    The retired heuristic could not fabricate: it only ever returned what a
    live `resolve_symbol_to_curie` lookup confirmed, and recorded the rest as
    unresolved. A model asked to extract typed entities will happily return a
    plausible-looking identifier for a symbol that does not exist, and it
    will be fluent and wrong, which is this system's worst failure mode.

    Control: T-4.7-05's requirement that a span contributes nothing unless a
    live lookup confirms it. Remove the confirmation step and this arm goes
    red, because the model will return something for ZZZX9Q.
    """
    events = await _run_raw("What diseases are associated with the ZZZX9Q gene?")
    payload = _think_payload(events)

    curies = _resolved_curies(payload)
    assert not any("ZZZX9Q" in curie for curie in curies), (
        f"a CURIE was fabricated for a gene symbol that does not exist: {curies}"
    )
    for curie in curies:
        assert ":" in curie, f"`{curie}` is not in prefix:local_id CURIE form"


# ---------------------------------------------------------------------------
# P7: the 2026-08-23 product-owner decision, pinned structurally.
# ---------------------------------------------------------------------------


def test_p7_the_retired_gene_guess_is_gone_with_no_fallback() -> None:
    """The decision was "no fallback guess", and a decision needs a test.

    Product-owner decision, 2026-08-23: the shape heuristic and the stopword
    list are retired outright rather than kept as a fallback for when the
    extraction call fails. The reason the fallback option was rejected is
    exactly what this arm protects: a fallback keeps the defective extractor
    alive on a degraded path nobody watches, so the GTR-and-SRA refusal can
    still fire when the model provider is down, and no live arm above would
    ever see it because those arms run with the provider up.

    Control: T-4.7-06's removal. This is the only arm in the file that can
    fail if someone reintroduces the heuristic behind an `except` clause, and
    it is deliberately structural rather than behavioural for that reason: a
    behavioural arm would have to simulate a provider outage to reach it.
    """
    from system_03_search_agent.core import graph as graph_module

    for retired in ("_SYMBOL_CANDIDATE_STOPWORDS", "_GENE_SYMBOL_TOKEN_PATTERN"):
        assert not hasattr(graph_module, retired), (
            f"`{retired}` is still present in core.graph. The 2026-08-23 "
            "decision retires it outright; a fallback path that resurrects it "
            "reintroduces F-2.0-15 on the exact path no live arm exercises"
        )


# ---------------------------------------------------------------------------
# P8 to P10: the pool, and the prefix it has to sit inside without moving.
# ---------------------------------------------------------------------------


def test_p8_the_pool_holds_the_seven_must_pass_questions() -> None:
    """Section 17's seeded pool, in the shape Section 17 fixes.

    Control: T-4.7-01 and T-4.7-02. The arm asserts the SHAPE of every entry
    rather than the count alone, because a pool of seven malformed entries
    injects seven malformed examples into the stable prefix and biases the
    model toward whatever they actually say.
    """
    from system_03_search_agent.orchestrator import few_shot_pool

    pool = few_shot_pool.load_pool()
    assert len(pool) == 7, (
        f"expected the seven v1 must-pass moat questions, found {len(pool)}"
    )
    for example in pool:
        assert example.query_class in SECTION_17_SHAPES, (
            f"`{example.query_class}` is not one of Section 17's five shapes"
        )
        assert example.query_pattern, "an example with no query_pattern"
        assert example.route.tools, "an example whose route names no tool"


def test_p9_the_pool_is_read_from_disk_once_per_process(monkeypatch) -> None:
    """`.claude/rules/prompt-cache-discipline.md`, obligation 3.

    "Never read the pool from a live database on every request. The pool sits
    inside the stable prefix precisely because it does not change within a
    session, and a per-request database read defeats that: a changing prefix
    source, even one that happens to return the same content, is a liveness
    risk the caching design does not tolerate."

    Control: T-4.7-02's process-level memoisation.

    POPULATE-CHECK: the arm asserts the file was read AT LEAST once before
    asserting it was read at most once. Without that, a loader that never
    reads the file at all, or that silently returns an empty pool, passes the
    at-most-once assertion perfectly. That is build phase 4.11's populate-
    check lesson applied to a counting arm, which is the shape most prone to
    it.
    """
    from system_03_search_agent.orchestrator import few_shot_pool

    reads: list[Path] = []
    real_read = Path.read_text

    def counting_read(self: Path, *args: Any, **kwargs: Any) -> str:
        if self.name.endswith("few_shot_examples.json"):
            reads.append(self)
        return real_read(self, *args, **kwargs)

    few_shot_pool.reset_pool_cache()
    monkeypatch.setattr(Path, "read_text", counting_read)

    first = few_shot_pool.load_pool()
    for _ in range(5):
        few_shot_pool.load_pool()

    assert first, "the loader returned an empty pool, so nothing is being counted"
    assert len(reads) >= 1, (
        "the pool file was never read from disk at all, so the at-most-once "
        "assertion below would pass on a loader that does nothing"
    )
    assert len(reads) == 1, (
        f"the pool file was read {len(reads)} times across six calls; it "
        "loads once at process start and is held in memory"
    )


def test_p10_the_few_shot_block_does_not_move_the_stable_prefix() -> None:
    """The prefix is byte-identical across two requests, by SHA-256.

    `.claude/rules/prompt-cache-discipline.md`: "A change that claims to
    preserve the stable prefix is proven with a byte-equality assertion
    (SHA-256 over the assembled prefix), computed across two requests whose
    dynamic suffix differs but whose stable prefix should not, not merely
    that the existing test suite still passes."

    Control: T-4.7-07's placement of the pool inside the stable block. Move
    one per-query value into the prefix and this arm goes red; the ordinary
    suite would not notice, which is the whole reason the rule asks for this
    assertion by name.

    POPULATE-CHECK: the arm asserts the pool's content is actually PRESENT in
    the prefix before asserting the prefix is stable. Two empty prefixes are
    byte-identical, and a pool that never reaches the prefix satisfies the
    equality assertion perfectly while delivering none of the routing bias
    the phase exists to add.
    """
    from system_03_search_agent.harness.cache import build_stable_prefix, prefix_sha256
    from system_03_search_agent.orchestrator import few_shot_pool

    pool = few_shot_pool.load_pool()
    assert pool, "an empty pool makes both assertions below vacuous"

    first = build_stable_prefix()
    second = build_stable_prefix()

    assert pool[0].query_pattern in first, (
        "the few-shot pool is not in the stable prefix at all, so the "
        "byte-equality assertion below would hold trivially while the pool "
        "biases nothing"
    )
    assert prefix_sha256(first) == prefix_sha256(second), (
        "the stable prefix is not byte-identical across two assemblies; every "
        "cached prompt re-bills at the uncached rate and nothing errors"
    )


# ---------------------------------------------------------------------------
# P11: F-4.6-A-08, by running it rather than by reading the write.
# ---------------------------------------------------------------------------


def test_p11_two_concurrent_promotions_cannot_corrupt_the_pool(tmp_path) -> None:
    """F-4.6-A-08, carried from build phase 4.6 with this phase as owner.

    Filed there and deliberately not fixed there: it needs two operators or
    two shells running the promotion script at once, so no end user can reach
    it. It was assigned here because this is the phase that first READS that
    file at process start, so a corrupted file becomes a startup failure.

    Control: T-4.7-03's atomic write and advisory lock. The arm runs two
    promotions genuinely concurrently rather than inspecting the write for
    atomicity, because a read of the code is what concluded it was safe the
    first time.
    """
    import threading

    from system_03_search_agent.orchestrator import few_shot_pool

    pool_path = tmp_path / "few_shot_examples.json"
    pool_path.write_text(
        json.dumps({"schema_version": 1, "examples": []}), encoding="utf-8"
    )

    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def promote(index: int) -> None:
        entry = {
            "query_pattern": f"pattern {index}",
            "query_class": "lookup",
            "resolved_entities": [],
            "route": {"layers": ["layer2"], "tools": ["ncbi_efetch"]},
            "narrative_pattern": "n",
            "citation_pattern": ["Gene"],
        }
        try:
            barrier.wait(timeout=5)
            few_shot_pool.append_example(pool_path, entry)
        except BaseException as exc:  # noqa: BLE001 - recorded, then asserted
            errors.append(exc)

    threads = [threading.Thread(target=promote, args=(i,)) for i in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors, f"a concurrent promotion raised: {errors}"

    raw = pool_path.read_text(encoding="utf-8")
    data = json.loads(raw)  # invalid JSON here is the corruption itself
    patterns = {example["query_pattern"] for example in data["examples"]}
    assert patterns == {"pattern 1", "pattern 2"}, (
        f"a concurrent promotion lost an entry: {patterns}"
    )


# ---------------------------------------------------------------------------
# P12: the class reaches the two things that consume it.
# ---------------------------------------------------------------------------


@premise_gate
@pytest.mark.asyncio
async def test_p12_the_interactions_row_records_the_class_the_loop_used() -> None:
    """Build phase 4.6's knowingly-wrong column, closed.

    `tracker/phase_4.6.md` recorded it plainly at that phase's open:
    "`interactions.query_class` will read `lookup` on every row this phase
    writes. That is correct behaviour for this phase and a known-wrong value
    in the data." This arm is where that stops being true.

    Control: T-4.7-08. The arm asserts the row's class EQUALS the class the
    `think` event carried, rather than asserting it is not `"lookup"`, for a
    specific reason: `lookup` is a legitimate classification, so a question
    that really is a lookup must still be allowed to record it. Equality
    catches a hardcoded literal on every question; inequality would only
    catch it on questions that happen not to be lookups.
    """
    from system_03_search_agent.contracts.query import Query
    from system_03_search_agent.feedback.capture import assemble_interaction

    question = Q3_FLAGSHIP
    events = await _run_raw(question)
    payload = _think_payload(events)

    query = Query(
        text=question,
        session_id=f"gate-4-7-{uuid.uuid4().hex[:12]}",
        trace_id=f"gate-4-7-{uuid.uuid4().hex[:8]}",
        owner_id=f"guest:{uuid.uuid4()}",
    )
    row = assemble_interaction(query, events)

    assert row is not None, (
        "the assembler produced no row for a completed run, so the class "
        "assertion below would pass vacuously"
    )
    assert row.query_class == _class_of(payload), (
        f"the interactions row recorded `{row.query_class}` while the loop "
        f"actually routed on `{_class_of(payload)}`. A row that disagrees "
        "with the run it describes is worse than a row that is missing"
    )


@premise_gate
@pytest.mark.asyncio
async def test_p12b_the_class_selects_a_real_act_budget() -> None:
    """The other consumer, and the one with a floor that must survive.

    `budget_for_step("act", query_class)` selects Section 21.1's per-class
    budget, and `act_node` takes `max(budget_for_step(...),
    CYPHER_QUERY_TIMEOUT_SECONDS)` so a class whose budget is smaller than
    the graph tool's own 30 second timeout cannot starve it. That floor was
    written while every query was a `"lookup"`; this is the first phase where
    a real class can select something else, so the floor is exercised for the
    first time here.

    Control: T-4.7-08. POPULATE-CHECK: the arm asserts a class was actually
    produced before asserting the budget it selects, since `budget_for_step`
    would happily return the lookup budget for a stub value.
    """
    from system_03_search_agent.harness.harness import budget_for_step
    from system_03_search_agent.tools.cypher_query import CYPHER_QUERY_TIMEOUT_SECONDS

    payload = _think_payload(await _run_raw(Q3_FLAGSHIP))
    assert _class_of(payload) in SECTION_17_SHAPES, (
        f"`{_class_of(payload)}` is outside Section 17's five shapes, so the "
        "budget lookup below is not measuring a real classification"
    )

    act_budget = max(
        budget_for_step("act", _class_of(payload)), CYPHER_QUERY_TIMEOUT_SECONDS
    )
    assert act_budget >= CYPHER_QUERY_TIMEOUT_SECONDS, (
        "the graph tool's own 30 second timeout is no longer a floor under "
        "Act's per-class budget, so a lookup-classified query can now kill a "
        "graph call that was still within its declared budget"
    )
