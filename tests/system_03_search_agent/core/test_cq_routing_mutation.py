"""Mutation coverage for build phase 4.7's premise gate: can each arm FAIL?

## Why this file exists

Build phase 4.7 produced THREE separate vacuity findings, every one in an
arm the lead wrote, in a file whose own docstring quotes build phase 4.11's
lesson against writing them:

- F-4.7-01: three of P1's four cases asserted a token that was not in the
  question at all.
- F-4.7-J1-01 (CRITICAL): P1 read `text`, and `think_node` wrote the CURIE
  into `text`, so the token being asserted on was not in the CODOMAIN of the
  value being read. Unfalsifiable under any model behaviour.
- F-4.7-R2-01: P12b computed `max(b, C)` and asserted `max(b, C) >= C`, a
  mathematical identity, inert on every line including its populate-check.

Every one of the three was caught by MUTATION. None was caught by reading,
and all three were read repeatedly, by their author and by reviewers who
knew the failure mode by name. Reading an assertion has now been
demonstrated three times in one phase not to be a method for validating it.

So vacuity stops being a review finding and becomes a CI failure. For each
control the premise gate claims to protect, this file breaks that control
IN PROCESS and asserts the corresponding arm goes red. An arm that stays
green under the destruction of the thing it grades is not an arm, and this
file says so in the ordinary suite rather than in a report.

## How it runs

Entirely offline. No model call, no network, no graph. `tests/conftest.py`
hard-fails any real outbound HTTP, and nothing here sets `RUN_PREMISE_GATE`,
so a leaked call raises rather than passing quietly.

The live arms are driven through the REAL `core.run.run()` loop with the
model replaced by `tests/system_03_search_agent/model_stub.py`'s dispatching
stand-in and the two live tools replaced by canned outputs. Every node
(`guardrail_node`, `think_node`, `plan_node`, `act_node`, `write_node`) runs
its real body; only the model's words and the tools' bytes are supplied.

That is a deliberate departure from the premise gate's own rule that "an arm
that mocks Think's own call is not an arm", and the two are not in conflict.
The GATE grades the product against a real model and must not mock it. THIS
file grades the GATE, and the question it asks ("can this assertion take a
failing value?") is a property of the assertion, not of the provider. Asking
it needs a model whose output the test controls; a real one cannot be told
to commit the defect on demand.

## Coverage, stated because a coverage claim it cannot support is the same
## defect one level up

Thirteen arms exist in `test_cq_routing_premise.py`. This file mutates ELEVEN
of them. The two it does not, and why:

- P2's third line, `assert _class_of(payload) in SECTION_17_SHAPES`. It is
  UNFALSIFIABLE and known to be: `query_class` is a validated `Literal` on
  `_ThinkClassification` and again on `ThinkPayload`, which rejects a bad
  value at construction, so an emitted `think` event cannot carry a shape
  outside the five. It is a structural guard, not a measurement. P2's two
  real assertions ARE mutated below. Nothing needs to change: the line costs
  nothing and documents the contract. It is listed here so a reader counting
  assertions does not credit it as coverage.
- P6's `for curie in curies: assert ":" in curie`. Mutated below via the
  bare-`"672"` case, so this is coverage rather than a gap; it is named only
  because F-4.7-R2-05 filed P6's MISSING POPULATE-CHECK as a separate minor,
  and that minor is NOT closed by this file. P6 still passes when the model
  extracts nothing at all, because there is then nothing to fabricate. This
  file measures that fact (`test_p6_passes_vacuously_when_nothing_is_extracted`
  is an XFAIL-shaped assertion recorded as a known gap, below) rather than
  hiding it.

What this file does NOT do, and could not: prove an arm catches a defect
NOBODY THOUGHT OF. A mutation set is written from the same imagination as
the arms it grades. It converts "did a reviewer notice" into "does the suite
enforce", which is a real improvement and is not the same as completeness.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from system_03_search_agent.contracts.query import Query, RequestContext
from system_03_search_agent.core import graph as graph_module
from system_03_search_agent.harness import cost_control
from system_03_search_agent.harness import harness as harness_module
from system_03_search_agent.tools.cypher_schemas import CypherQueryOutput, CypherQueryRow
from system_03_search_agent.tools.ncbi_efetch_schemas import NcbiEfetchOutput
from tests.system_03_search_agent.core import test_cq_routing_premise as gate
from tests.system_03_search_agent.model_stub import (
    COMPLIANT_GUARD_CLASSIFICATION,
    compliant_synth_narrative,
    fake_response,
)

# ---------------------------------------------------------------------------
# The offline loop. Every fixture here is autouse: a mutation harness that
# can be run with one of its isolation layers accidentally absent would
# reach the network, and `tests/conftest.py` would then fail it in a way
# that reads like a defect in the arm rather than in this file.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUARD_MODEL", "test-provider/guard-model")
    monkeypatch.setenv("PLAN_MODEL", "test-provider/plan-model")
    monkeypatch.setenv("SYNTH_MODEL", "test-provider/synth-model")
    monkeypatch.setenv("PER_QUERY_COST_CAP_USD", "1.0")
    monkeypatch.setenv("PER_USER_DAILY_QUERY_CAP", "100")
    monkeypatch.setenv("SYSTEM_DAILY_CAP_USD", "1000000")
    monkeypatch.setenv("USER_DB_URL", "postgresql://localhost:5432/search_agent_users")


@pytest.fixture(autouse=True)
def _no_op_daily_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cost_control, "check_user_daily_query_cap", lambda session, user_id, **kw: None
    )
    monkeypatch.setattr(
        cost_control, "check_system_daily_cost_cap", lambda session, **kw: None
    )


class _Model:
    """The Think reply this run should produce, and the tools' answers.

    A mutable holder rather than a fixture parameter so a test can change
    Think's behaviour AFTER the loop wiring is in place, which is what a
    mutation is: same loop, one control broken.
    """

    def __init__(self) -> None:
        self.think_class = "multi_hop"
        self.think_entities: list[dict[str, str]] = []
        #: symbol -> CURIE, the live confirmation stand-in. A symbol absent
        #: from this map does not confirm, exactly as NCBI would answer.
        self.resolves: dict[str, str] = {"BRCA1": "NCBIGene:672"}

    def think_reply(self) -> str:
        return json.dumps(
            {
                "query_class": self.think_class,
                "narrative": "mutation-harness stand-in",
                "entities": self.think_entities,
            }
        )


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> _Model:
    state = _Model()

    async def _dispatch(*args: object, **kwargs: object) -> Any:
        from system_03_search_agent.guardrail.classifier import (
            GUARD_SYSTEM_INSTRUCTION,
        )
        from system_03_search_agent.synthesis.findings import SYNTH_SYSTEM_INSTRUCTION

        messages = list(kwargs.get("messages") or [])
        joined = "\n".join(message.get("content") or "" for message in messages)
        if GUARD_SYSTEM_INSTRUCTION in joined:
            return fake_response(COMPLIANT_GUARD_CLASSIFICATION)
        if graph_module._THINK_SYSTEM_INSTRUCTION in joined:
            return fake_response(state.think_reply())
        if SYNTH_SYSTEM_INSTRUCTION in joined:
            return fake_response(compliant_synth_narrative(messages))
        return fake_response("MATCH (g:Gene) RETURN g LIMIT 1")

    monkeypatch.setattr(harness_module.litellm, "acompletion", _dispatch)
    monkeypatch.setattr(
        harness_module.litellm,
        "get_model_info",
        lambda model: {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6},
    )

    async def _resolve(symbol: str, *, taxon: str = "human") -> str | None:
        return state.resolves.get(symbol.strip().upper())

    monkeypatch.setattr(graph_module, "resolve_symbol_to_curie", _resolve)

    async def _cypher(harness: object, cypher_input: object) -> CypherQueryOutput:
        return CypherQueryOutput(
            status="ok",
            row_count=1,
            total_available=1,
            truncated=False,
            rows=[
                CypherQueryRow(
                    node_or_edge_type="Gene",
                    curie="NCBIGene:672",
                    fields={"name": "BRCA1 DNA repair associated"},
                    source_url="https://www.ncbi.nlm.nih.gov/gene/672",
                    graph_snapshot_version="v1",
                )
            ],
            error=None,
        )

    monkeypatch.setattr(graph_module, "cypher_query", _cypher)

    async def _efetch(tool_input: object, **kwargs: object) -> NcbiEfetchOutput:
        return NcbiEfetchOutput(
            status="empty",
            action="dataset_report",
            records=[],
            record_count=0,
            total_available=None,
            truncated=False,
            error=None,
        )

    monkeypatch.setattr(graph_module, "ncbi_efetch", _efetch)
    return state


# ---------------------------------------------------------------------------
# The two shapes every check below takes.
# ---------------------------------------------------------------------------


async def _arm_result(arm: Any, *args: Any) -> AssertionError | None:
    """Run one gate arm. Return its `AssertionError`, or `None` if it passed.

    Only `AssertionError` is caught. A `TypeError`, a `KeyError` or a
    `ValidationError` escaping an arm is a broken arm or broken wiring, not
    the arm detecting the mutation, and this file must never credit one as a
    red. F-4.7-J1-01's own report records six arms failing with `'dict'
    object has no attribute` and how much that looked like a routing defect.
    """
    try:
        result = arm(*args)
        if hasattr(result, "__await__"):
            await result
    except AssertionError as exc:
        return exc
    return None


async def _assert_arm_is_falsifiable(
    arm: Any, args: tuple[Any, ...], mutate: Any, label: str
) -> None:
    """The whole file, in one function.

    Runs the arm clean, asserts it PASSES (this is the harness's own
    populate-check: an arm that is already red measures nothing, and a
    mutation that "turns it red" proves nothing about the mutation), then
    applies the mutation and asserts it goes RED.
    """
    clean = await _arm_result(arm, *args)
    assert clean is None, (
        f"{label}: the arm is ALREADY FAILING before any mutation, so the "
        "red below would not be attributable to the mutation. Fix the arm or "
        f"the harness wiring first. It failed with: {clean}"
    )

    mutate()

    mutated = await _arm_result(arm, *args)
    assert mutated is not None, (
        f"{label}: the arm stayed GREEN while the control it claims to grade "
        "was destroyed. It cannot fail, so its pass in the live gate means "
        "nothing. This is the F-4.7-R2-01 shape"
    )


# ---------------------------------------------------------------------------
# Offline arms: P5, P7, P8, P9, P10, P11.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p5_goes_red_when_the_exact_id_prepass_resolves_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P5's populate-check. A pre-pass that resolves nothing also makes zero
    model calls for it, so the zero-call assertion would pass on a completely
    broken resolver.
    """
    await _assert_arm_is_falsifiable(
        gate.test_p5_an_exact_identifier_resolves_without_consulting_the_model,
        (),
        lambda: monkeypatch.setattr(
            graph_module, "resolve_exact_identifiers", lambda text: []
        ),
        "P5 / empty pre-pass",
    )


@pytest.mark.asyncio
async def test_p5_goes_red_when_the_prepass_becomes_async(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Section 17's ordering held structurally: a resolver that awaits a
    model call is the fuzzy step wearing the pre-pass's name.
    """
    real = graph_module.resolve_exact_identifiers

    def _mutate() -> None:
        marked = real
        monkeypatch.setattr(marked, "is_async", True, raising=False)

    await _assert_arm_is_falsifiable(
        gate.test_p5_an_exact_identifier_resolves_without_consulting_the_model,
        (),
        _mutate,
        "P5 / async pre-pass",
    )


@pytest.mark.asyncio
async def test_p7_goes_red_when_the_retired_heuristic_is_resurrected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _assert_arm_is_falsifiable(
        gate.test_p7_the_retired_gene_guess_is_gone_with_no_fallback,
        (),
        lambda: monkeypatch.setattr(
            graph_module, "_SYMBOL_CANDIDATE_STOPWORDS", frozenset({"THE"}), raising=False
        ),
        "P7 / stopword list resurrected",
    )


@pytest.mark.asyncio
async def test_p8_goes_red_when_the_pool_loses_an_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from system_03_search_agent.orchestrator import few_shot_pool

    real_pool = few_shot_pool.load_pool()
    await _assert_arm_is_falsifiable(
        gate.test_p8_the_pool_holds_the_seven_must_pass_questions,
        (),
        lambda: monkeypatch.setattr(
            few_shot_pool, "load_pool", lambda *a, **k: list(real_pool)[:6]
        ),
        "P8 / six-entry pool",
    )


@pytest.mark.asyncio
async def test_p8_goes_red_on_a_shape_outside_section_17(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from system_03_search_agent.orchestrator import few_shot_pool

    real_pool = list(few_shot_pool.load_pool())

    def _mutate() -> None:
        broken = [entry.model_copy() for entry in real_pool]
        object.__setattr__(broken[0], "query_class", "bogus_shape")
        monkeypatch.setattr(few_shot_pool, "load_pool", lambda *a, **k: broken)

    await _assert_arm_is_falsifiable(
        gate.test_p8_the_pool_holds_the_seven_must_pass_questions,
        (),
        _mutate,
        "P8 / non-Section-17 shape",
    )


@pytest.mark.asyncio
async def test_p9_goes_red_when_the_pool_is_re_read_per_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Obligation 3 of `prompt-cache-discipline.md`, destroyed: the loader
    reads the file on every call instead of once per process.
    """
    from system_03_search_agent.orchestrator import few_shot_pool

    def _mutate() -> None:
        def _uncached(*args: Any, **kwargs: Any) -> Any:
            few_shot_pool.reset_pool_cache()
            return real_load(*args, **kwargs)

        monkeypatch.setattr(few_shot_pool, "load_pool", _uncached)

    real_load = few_shot_pool.load_pool
    inner_monkeypatch = pytest.MonkeyPatch()
    try:
        await _assert_arm_is_falsifiable(
            gate.test_p9_the_pool_is_read_from_disk_once_per_process,
            (inner_monkeypatch,),
            _mutate,
            "P9 / re-read per call",
        )
    finally:
        inner_monkeypatch.undo()
        few_shot_pool.reset_pool_cache()


@pytest.mark.asyncio
async def test_p10_goes_red_when_a_volatile_token_enters_the_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one failure `prompt-cache-discipline.md` says nothing errors on:
    a per-request value in the stable prefix. Every prompt silently re-bills
    at the uncached rate.
    """
    from system_03_search_agent.harness import cache as cache_module

    real_build = cache_module.build_stable_prefix

    def _mutate() -> None:
        monkeypatch.setattr(
            cache_module,
            "build_stable_prefix",
            lambda *a, **k: real_build(*a, **k) + f"\nrequest_id={uuid.uuid4()}",
        )

    await _assert_arm_is_falsifiable(
        gate.test_p10_the_few_shot_block_does_not_move_the_stable_prefix,
        (),
        _mutate,
        "P10 / volatile token in the prefix",
    )


@pytest.mark.asyncio
async def test_p10_goes_red_when_the_pool_leaves_the_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P10's populate-check. Two empty prefixes are byte-identical, so a pool
    that never reaches the prefix satisfies the equality assertion perfectly
    while biasing nothing.
    """
    from system_03_search_agent.harness import cache as cache_module
    from system_03_search_agent.orchestrator import few_shot_pool

    real_build = cache_module.build_stable_prefix
    pattern = few_shot_pool.load_pool()[0].query_pattern

    def _mutate() -> None:
        monkeypatch.setattr(
            cache_module,
            "build_stable_prefix",
            lambda *a, **k: real_build(*a, **k).replace(pattern, ""),
        )

    await _assert_arm_is_falsifiable(
        gate.test_p10_the_few_shot_block_does_not_move_the_stable_prefix,
        (),
        _mutate,
        "P10 / pool stripped from the prefix",
    )


@pytest.mark.asyncio
async def test_p11_goes_red_when_the_promotion_write_loses_its_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-4.6-A-08's control, destroyed in the exact way that LOOKS safe.

    The mutation is not "remove the write". It is an ATOMIC `os.replace`
    with no lock, which is the belief ("atomicity is enough") that would
    otherwise pass a code reading. Round 2 measured it losing an entry 3 of
    3 runs.
    """
    import os
    import tempfile
    import threading

    from system_03_search_agent.orchestrator import few_shot_pool

    # The interleaving is FORCED here rather than hoped for, and that is a
    # correction rather than a refinement.
    #
    # The P11 arm being graded already starts both threads together with a
    # barrier, and that is not the same as making them interleave. `os.replace`
    # is fast enough that one thread can complete its whole read-modify-write
    # before the other reads, in which case both entries survive, the mutation
    # loses nothing, and this test reports the arm as VACUOUS when the arm is
    # fine. Whether that happens depends on core count and scheduling.
    #
    # It passed on the machine where build phase 4.7 wrote it and FAILED on a
    # GitHub runner, found by build phase 4.14's first green-enough CI run.
    # A test whose answer moves with the hardware is the same class of defect as
    # build phase 4.11's non-deterministic preservation gate: a real finding
    # stops being distinguishable from noise.
    #
    # This second barrier sits between the READ and the WRITE, so both threads
    # are guaranteed to have read the SAME original document before either
    # writes. The later write then necessarily drops the earlier thread's entry,
    # on any hardware. The timeout means a single-threaded caller (which is how
    # `_assert_arm_is_falsifiable` runs the arm clean) does not hang.
    read_barrier = threading.Barrier(2)

    def _unlocked_append(path: Path, entry: dict[str, Any]) -> None:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        document["examples"].append(entry)
        try:
            read_barrier.wait(timeout=5)
        except threading.BrokenBarrierError:
            # Fewer than two concurrent writers: nothing to interleave, and the
            # write below is still correct. Never fail the harness for this.
            pass
        handle, temporary = tempfile.mkstemp(dir=str(Path(path).parent))
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(document, stream)
        os.replace(temporary, str(path))

    await _assert_arm_is_falsifiable(
        gate.test_p11_two_concurrent_promotions_cannot_corrupt_the_pool,
        (tmp_path,),
        lambda: monkeypatch.setattr(
            few_shot_pool, "append_example", _unlocked_append
        ),
        "P11 / atomic but unlocked write",
    )


# ---------------------------------------------------------------------------
# Live arms, driven through the real loop with a scripted model.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("label", "question", "passing_mention"),
    gate.REFUSED_TODAY,
    ids=[row[0] for row in gate.REFUSED_TODAY],
)
@pytest.mark.parametrize(
    "span_shape",
    ["{token}", "{token} runs", "{token} metadata", "{token_lower}", " {token}"],
    ids=["bare", "wider-suffix", "wider-suffix-2", "lowercased", "leading-space"],
)
async def test_p1_goes_red_whatever_span_the_model_returns(
    model: _Model, label: str, question: str, passing_mention: str, span_shape: str
) -> None:
    """F-4.7-R2-02, made mechanical.

    P1's assertion used to be exact list membership, so with the database
    name GENUINELY resolved as a gene, `"SRA runs"`, `"SRA metadata"` and
    `"sra"` all left the arm GREEN and only a bare exact `"SRA"` turned it
    red. The live gate runs against a real model whose span choice is pinned
    by nothing, and a wider span is the LIKELIER extraction from Q6's own
    text, so the arm was weakest exactly where the risk is highest.

    Five span shapes, per question. Every one is the same defect: the
    database name taken as the subject of the question and confirmed live.
    All five must turn the arm red or the fix is partial.
    """
    span = span_shape.format(
        token=passing_mention, token_lower=passing_mention.lower()
    )

    def _mutate() -> None:
        model.think_entities = [{"text": span, "entity_type": "gene"}]
        model.resolves = {span.strip().upper(): "NCBIGene:6301"}

    await _assert_arm_is_falsifiable(
        gate.test_p1_a_database_name_in_passing_is_not_the_subject,
        (label, question, passing_mention),
        _mutate,
        f"P1 {label} / span {span!r}",
    )


@pytest.mark.asyncio
async def test_p2_goes_red_when_the_flagship_resolves_nothing(
    model: _Model,
) -> None:
    """UI fix set 8 (2026-09-13) changed what this mutation has to break.

    Emptying the model's spans alone no longer stops the flagship resolving,
    because `think_node`'s gene-shaped fallback confirms BRCA1 live when the
    model extracted nothing. Resolution is destroyed only when BOTH halves
    are gone: no span from the model AND a lookup that confirms nothing.
    The arm below this one pins the half this mutation used to cover.
    """
    model.think_entities = [{"text": "BRCA1", "entity_type": "gene"}]

    def _no_span_and_nothing_confirms() -> None:
        model.think_entities = []
        model.resolves = {}

    await _assert_arm_is_falsifiable(
        gate.test_p2_the_flagship_resolves_its_subject_from_raw_text,
        (),
        _no_span_and_nothing_confirms,
        "P2 / nothing extracted and nothing confirmed",
    )


@pytest.mark.asyncio
async def test_p2_survives_an_empty_extraction_through_the_fallback_and_goes_red_without_it(
    model: _Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback is a control of its own, so it gets a mutation of its own.

    Clean: the model extracts NOTHING and P2 still passes, because the
    fallback names `BRCA1` from the question and the lookup confirms it.
    Mutated: the fallback's candidate extractor returns nothing, and P2 goes
    red. An arm that stayed green here would mean the fallback is not what
    is keeping the flagship alive under an empty extraction.
    """
    model.think_entities = []
    await _assert_arm_is_falsifiable(
        gate.test_p2_the_flagship_resolves_its_subject_from_raw_text,
        (),
        lambda: monkeypatch.setattr(
            graph_module, "_gene_shaped_fallback_candidates", lambda text, exact: []
        ),
        "P2 / fallback extractor emptied",
    )


@pytest.mark.asyncio
async def test_p2_goes_red_on_a_non_ncbigene_curie(model: _Model) -> None:
    """The arm asserts the CURIE PREFIX, not merely that something resolved:
    a `resolved_entities` list that resolves BRCA1 to an HGNC CURIE gives
    `cypher_query` nothing the graph can bind.
    """
    model.think_entities = [{"text": "BRCA1", "entity_type": "gene"}]
    await _assert_arm_is_falsifiable(
        gate.test_p2_the_flagship_resolves_its_subject_from_raw_text,
        (),
        lambda: setattr(model, "resolves", {"BRCA1": "HGNC:1100"}),
        "P2 / HGNC instead of NCBIGene",
    )


@pytest.mark.asyncio
async def test_p3_goes_red_when_the_classifier_returns_the_stub_literal(
    model: _Model,
) -> None:
    """F-2.0-15 itself: the stub's value surviving under a new name."""
    await _assert_arm_is_falsifiable(
        gate.test_p3_a_coordinate_question_is_not_classified_as_a_lookup,
        (),
        lambda: setattr(model, "think_class", "lookup"),
        "P3 / classifier returns 'lookup'",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "constant", ["lookup", "multi_hop", "exploratory"], ids=lambda value: value
)
async def test_p4_goes_red_on_a_constant_classifier(
    model: _Model, constant: str
) -> None:
    """The anti-vacuity arm for the whole classification half. Every other
    classification assertion in the gate is satisfiable by one literal, the
    same way the stub satisfied twelve phases by returning `"lookup"`.

    P4 needs the two questions to receive DIFFERENT classes, so the clean run
    has to produce two. `_Model.think_class` is a single value, so the clean
    behaviour is scripted to vary by question text and the mutation pins it
    to one constant, which is exactly the defect.
    """
    from system_03_search_agent.core import graph

    real_parse = graph._parse_think_classification
    calls = {"n": 0}

    def _varying(content: str) -> Any:
        calls["n"] += 1
        parsed = json.loads(content)
        parsed["query_class"] = "multi_hop" if calls["n"] % 2 else "single_hop"
        return real_parse(json.dumps(parsed))

    inner = pytest.MonkeyPatch()
    inner.setattr(graph, "_parse_think_classification", _varying)
    try:
        await _assert_arm_is_falsifiable(
            gate.test_p4_two_different_shapes_do_not_get_the_same_class,
            (),
            lambda: inner.setattr(
                graph,
                "_parse_think_classification",
                lambda content: real_parse(
                    json.dumps({**json.loads(content), "query_class": constant})
                ),
            ),
            f"P4 / constant {constant!r}",
        )
    finally:
        inner.undo()


@pytest.mark.asyncio
async def test_p6_goes_red_when_a_curie_is_fabricated(model: _Model) -> None:
    """The failure this phase INTRODUCED that the retired heuristic could not
    commit: a model asked for typed entities will invent a plausible
    identifier, and the old regex could only ever return what a live lookup
    confirmed.
    """
    model.think_entities = [{"text": "ZZZX9Q", "entity_type": "gene"}]
    await _assert_arm_is_falsifiable(
        gate.test_p6_an_unknown_gene_shaped_token_yields_no_curie,
        (),
        lambda: setattr(model, "resolves", {"ZZZX9Q": "NCBIGene:ZZZX9Q"}),
        "P6 / fabricated CURIE",
    )


@pytest.mark.asyncio
async def test_p6_goes_red_on_a_bare_id_that_is_not_a_curie(
    model: _Model,
) -> None:
    model.think_entities = [{"text": "ZZZX9Q", "entity_type": "gene"}]
    await _assert_arm_is_falsifiable(
        gate.test_p6_an_unknown_gene_shaped_token_yields_no_curie,
        (),
        lambda: setattr(model, "resolves", {"ZZZX9Q": "672"}),
        "P6 / bare id, no prefix",
    )


@pytest.mark.asyncio
async def test_p6_is_green_when_the_model_extracts_nothing(model: _Model) -> None:
    """F-4.7-R2-05, MEASURED rather than closed, and recorded here so the
    next reader does not have to re-derive it.

    P6 has no populate-check for its own premise. When the model extracts
    nothing at all, there is nothing to fabricate and the arm passes while
    grading nothing. That is a real gap in P6 and it is NOT fixed by this
    file. It is asserted in the direction it actually holds, so that whoever
    fixes P6 sees this test fail and deletes it, rather than finding a silent
    comment.
    """
    model.think_entities = []
    result = await _arm_result(
        gate.test_p6_an_unknown_gene_shaped_token_yields_no_curie
    )
    assert result is None, (
        "P6 now FAILS when nothing is extracted, which means it grew the "
        "populate-check F-4.7-R2-05 asked for. Good: delete this test and "
        "close F-4.7-R2-05"
    )


@pytest.mark.asyncio
async def test_p12_goes_red_when_the_interactions_row_hardcodes_a_class(
    model: _Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Build phase 4.6's knowingly-wrong column, re-broken.

    The mutation is the exact code build phase 4.6 shipped: a hardcoded
    `"lookup"` on every captured row, regardless of what the loop routed on.
    """
    from system_03_search_agent.feedback import capture as capture_module

    real_assemble = capture_module.assemble_interaction

    def _hardcoded(query: Any, events: Any) -> Any:
        row = real_assemble(query, events)
        if row is not None:
            object.__setattr__(row, "query_class", "lookup")
        return row

    model.think_entities = [{"text": "BRCA1", "entity_type": "gene"}]
    model.think_class = "multi_hop"
    await _assert_arm_is_falsifiable(
        gate.test_p12_the_interactions_row_records_the_class_the_loop_used,
        (),
        lambda: monkeypatch.setattr(
            capture_module, "assemble_interaction", _hardcoded
        ),
        "P12 / hardcoded query_class on the row",
    )


@pytest.mark.asyncio
async def test_p12_goes_red_when_no_row_is_produced(
    model: _Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P12's populate-check, which IS falsifiable, unlike P12b's old one."""
    from system_03_search_agent.feedback import capture as capture_module

    model.think_entities = [{"text": "BRCA1", "entity_type": "gene"}]
    await _assert_arm_is_falsifiable(
        gate.test_p12_the_interactions_row_records_the_class_the_loop_used,
        (),
        lambda: monkeypatch.setattr(
            capture_module, "assemble_interaction", lambda query, events: None
        ),
        "P12 / assembler returns no row",
    )


@pytest.mark.asyncio
async def test_p12b_goes_red_when_the_graph_timeout_floor_is_destroyed(
    model: _Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-4.7-R2-01, closed and pinned.

    This is the EXACT mutation that left the retired P12b green: set
    `CYPHER_QUERY_TIMEOUT_SECONDS` to `0.0` in `core.graph`, which is the one
    place the floor is applied. The old arm recomputed `max(b, C)` from its
    own import of the constant and compared it to itself, so destroying the
    floor moved both sides of the comparison together. The rewritten arm
    reads the timeout `act_node` actually used and compares it against the
    constant's real value in `tools.graph_schema_constants`.
    """
    model.think_entities = [{"text": "BRCA1", "entity_type": "gene"}]
    await _assert_arm_is_falsifiable(
        gate.test_p12b_act_runs_on_the_timeout_the_routed_class_selects,
        (),
        lambda: monkeypatch.setattr(
            graph_module, "CYPHER_QUERY_TIMEOUT_SECONDS", 0.0
        ),
        "P12b / graph-timeout floor destroyed",
    )


def test_p12b_hardcoded_act_class_is_not_offline_mutable() -> None:
    """NOT MUTATED OFFLINE, and stated here rather than skipped silently.

    P12b's other assertion is `routed_classes[0] == routed`: Act must ask
    `budget_for_step` for the class the loop ROUTED on, never a literal. The
    defect it guards is `budget_for_step("act", "lookup")` written at the
    Act call site in `core/graph.py`.

    That mutation cannot be applied in process, and the reason is worth
    recording because it is a trap for the next person who tries. The arm
    observes the class by WRAPPING `core.graph.budget_for_step` with a
    recorder, and it installs that recorder itself, after any monkeypatch
    this file could apply. A mutation of the same attribute therefore ends
    up INSIDE the recorder: the recorder still sees the true class act_node
    passed, the mutation only changes what comes back, and the arm passes.
    An earlier draft of this file did exactly that and reported a false
    green. Patching `graph_module.act_node` does not help either, since
    `compiled_graph` captured the node function at import time.

    What would be needed: a source edit to `core/graph.py`'s Act call site,
    which no test may make. It was run by hand instead, once, and the
    observed red is recorded in `tracker/phase_4.7.md` under F-4.7-R2-01:
    with `budget_for_step("act", query_class)` edited to
    `budget_for_step("act", "lookup")`, the arm fails with

        AssertionError: Act budgeted on `lookup` while the loop routed on
        `multi_hop`.

    Two things follow. The assertion is falsifiable, which is the property
    this file exists to establish. And it is falsifiable only under a source
    mutation, so it is the ONE line in P12b that CI cannot re-prove on every
    run. Treat a future edit to that call site as unguarded by this file.
    """
    from system_03_search_agent.core import graph

    # The FULL assignment, not the substring `budget_for_step("act",
    # query_class)`. That substring also appears in this module's own
    # docstring at line 162, so an existence check on it stays green with
    # the call site hardcoded, which is this file's whole subject matter
    # committed inside this file.
    source = Path(graph.__file__).read_text(encoding="utf-8")
    call_site = (
        'act_timeout_s = max(budget_for_step("act", query_class), '
        "CYPHER_QUERY_TIMEOUT_SECONDS)"
    )
    assert call_site in source, (
        f"the Act call site no longer reads `{call_site}`. Either the class "
        "is now hardcoded, which is the defect P12b guards, or the "
        "expression moved and this note plus P12b's `routed_classes` "
        "assertion both need re-deriving"
    )


# ---------------------------------------------------------------------------
# The harness's own populate-check: the offline loop really does run every
# node. Without this, every "the arm went red" result above could be an
# artifact of a loop that never got past the guardrail.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_offline_loop_reaches_every_node(model: _Model) -> None:
    from system_03_search_agent.core.run import run

    model.think_entities = [{"text": "BRCA1", "entity_type": "gene"}]
    query = Query(
        text=gate.Q3_FLAGSHIP,
        session_id=f"mut-{uuid.uuid4().hex[:12]}",
        trace_id=f"mut-{uuid.uuid4().hex[:8]}",
        owner_id=f"guest:{uuid.uuid4()}",
    )
    events = [
        event async for event in run(query, RequestContext(surface="rest_sse"))
    ]
    seen = {event.type for event in events}
    for required in ("guard", "think", "plan", "done"):
        assert required in seen, (
            f"the offline loop never emitted a `{required}` event, so every "
            f"mutation result in this file is measuring a truncated run: {seen}"
        )
    think = next(event.payload for event in events if event.type == "think")
    assert think["resolved_entities"], (
        "the offline loop resolved nothing, so the resolution half of every "
        "live arm below is not actually being exercised"
    )
