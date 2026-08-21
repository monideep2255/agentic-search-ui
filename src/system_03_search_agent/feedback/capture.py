"""The capture assembler: one finished run folded into one row (T-4.6-03).

Depends on:
    - system_03_search_agent.contracts.query (Query)
    - system_03_search_agent.contracts.events (Event, ThinkPayload,
      PlanPayload, CostPayload, DonePayload)
    - system_03_search_agent.feedback.contracts (InteractionRow)
    - system_03_search_agent.feedback.rubric (rubric_outcome_for)
    - system_03_search_agent.feedback.coverage (coverage_tags_for)
    - system_03_search_agent.core.session_memory (session_row_key,
      `_account_uuid`): the SAME owner-scoped mapping session memory uses,
      imported rather than reimplemented so capture and memory can never
      disagree about which row a conversation is.

Reads:
    - Nothing. `assemble_interaction` is a pure function: no database, no
      network call, no model call, no environment read. Every field it
      produces traces to a typed field on `query` or on one of `events`.

Writes:
    - Nothing. The caller (`feedback/writer.py`, by way of
      `feedback.capture_run`) persists the row this module returns.

Section 15's column-to-decision mapping is this module's specification,
field by field; Section 16 stage 1 is the pipeline stage it implements.
"""

from __future__ import annotations

from typing import Any

from system_03_search_agent.contracts.events import (
    CostPayload,
    DonePayload,
    Event,
    PlanPayload,
    ThinkPayload,
)
from system_03_search_agent.contracts.query import Query
from system_03_search_agent.core.session_memory import _account_uuid, session_row_key
from system_03_search_agent.feedback.contracts import InteractionRow
from system_03_search_agent.feedback.coverage import coverage_tags_for
from system_03_search_agent.feedback.rubric import rubric_outcome_for

# Section 15's per-row cap on `normalized_entities`
# (`InteractionRow.normalized_entities`, `max_length=20`) and on `citations`
# (`max_length=50`). Enforced here too, not only left to the model
# validator, so a run that resolved or cited more than the cap is
# truncated deterministically rather than raising at construction.
_MAX_NORMALIZED_ENTITIES = 20
_MAX_CITATIONS = 50


def _last_of_type(events: list[Event], event_type: str) -> Event | None:
    """The most recent event of one type, or `None` if the run never emitted one.

    "Most recent" rather than "first": a run that somehow re-entered a step
    (a retried Act, a corrected Think) should be read from its final state,
    not its first attempt. In today's single-pass loop this is usually a
    difference without a case, since each step runs once, but reading the
    last one costs nothing and is the more defensible default either way.
    """
    for event in reversed(events):
        if event.type == event_type:
            return event
    return None


def _normalized_entities_from(plan_events: list[Event]) -> list[dict[str, Any]]:
    """Section 15's `normalized_entities`: `{surface_form, curie, entity_type,
    resolution_confidence}`, one entry per entity a `plan` event resolved.

    Read from `PlanPayload.resolved_entities`, never from `ThinkPayload`:
    `think_node` is still the build-phase-2.0 stub and emits an empty list,
    while `plan_node` runs the live symbol lookup (T-4.5-06's own comment on
    `PlanPayload.resolved_entities` says exactly this; build phase 4.7 owns
    moving resolution to Think, per F-2.0-15).

    The event contract's `ResolvedEntity` is `{text, curie, confidence}`; the
    decision-G shape wants `{surface_form, curie, entity_type,
    resolution_confidence}`. Those are different shapes for different jobs,
    so the translation is explicit here rather than a spread, the same
    choice `core/run.py::_remember_turn` already made translating the
    identical event field into the session-memory contract's own
    `ResolvedEntity`. `entity_type` is `"Unknown"` for the same reason that
    function gives: the event carries no entity type, and deriving `"Gene"`
    from a CURIE prefix would be reading a fact off a naming convention
    rather than off something the run actually determined.

    Deduplicated on `curie`, first occurrence wins, across every `plan`
    event in the run (there is ordinarily one, but nothing here assumes
    that), and truncated to `_MAX_NORMALIZED_ENTITIES` as a defensive
    mirror of `InteractionRow`'s own cap.
    """
    normalized: list[dict[str, Any]] = []
    seen_curies: set[str] = set()
    for event in plan_events:
        payload = PlanPayload.model_validate(event.payload)
        for entity in payload.resolved_entities:
            if entity.curie in seen_curies:
                continue
            seen_curies.add(entity.curie)
            normalized.append(
                {
                    "surface_form": entity.text,
                    "curie": entity.curie,
                    "entity_type": "Unknown",
                    "resolution_confidence": entity.confidence,
                }
            )
    return normalized[:_MAX_NORMALIZED_ENTITIES]


def _route_from(plan_events: list[Event], events: list[Event]) -> dict[str, Any]:
    """Section 15's `route`: `{layers, tools, model_tiers}`.

    `layers` and `tools` come from every `plan` event's `tool_calls`
    (`ToolCall.layer`, `ToolCall.tool`); `model_tiers` comes from every
    `cost` event's `model_tier` (`CostPayload.model_tier`), the harness's
    own record of which tier actually ran, not a value this function
    invents. All three are deduplicated and sorted for a deterministic
    column value: two runs that used the identical tool/layer/tier set
    produce byte-identical JSON, never an ordering artifact of event
    sequence.

    Every value drawn here is a typed field off an already-validated event
    payload. Nothing here ever reads configuration, a header, or a
    connection string, which is the property build phase 4.6's own premise
    gate arm P10 plants a secret in the environment and greps every column
    to check.
    """
    layers: set[str] = set()
    tools: set[str] = set()
    for event in plan_events:
        payload = PlanPayload.model_validate(event.payload)
        for call in payload.tool_calls:
            layers.add(call.layer)
            tools.add(call.tool)

    model_tiers: set[str] = set()
    for event in events:
        if event.type != "cost":
            continue
        model_tiers.add(CostPayload.model_validate(event.payload).model_tier)

    return {
        "layers": sorted(layers),
        "tools": sorted(tools),
        "model_tiers": sorted(model_tiers),
    }


def _query_class_from(think_event: Event | None) -> str:
    """Section 15's `query_class`, or the stub's own fallback.

    A Guardrail refusal short-circuits before Think ever runs, so a run
    with no `think` event is a real, expected shape (see the module
    docstring's "THE CASE MOST LIKELY TO BE MISSED"), not a defect to raise
    on. `"lookup"` is the correct fallback for that case specifically
    because it is the identical value `think_node`'s build-phase-2.0 stub
    would have produced had it run at all (F-2.0-15, owned by build phase
    4.7): every row this phase writes reads `"lookup"` today regardless of
    whether Think ran, so a run with no think event getting the same value
    a run WITH one gets is consistent with the stub's own behaviour, not an
    invented "better" value standing in for it.
    """
    if think_event is None:
        return "lookup"
    return ThinkPayload.model_validate(think_event.payload).query_class


def _hard_fails_for(trust_signal: str, citations: list[dict[str, Any]]) -> list[str]:
    """The one hard-fail check available at zero LLM cost on the live path.

    `requirements/Evaluation_playbook.md`'s hard-fail list names three
    conditions; only the first, "Provenance = 0 (a claim with no source)",
    is checkable without a model call: an `answer` or `flag` outcome (a run
    that asserted something) with zero citations is exactly an uncited
    claim. The other two ("Safety and limits = 0 on a clinical or
    pathogenicity question", "Missing assembly or version context on a
    coordinate or sequence question") require judging the CONTENT of the
    answer against the question, which is what the full graded rubric does
    in build phase 5.1's offline replay; they are out of scope for a
    zero-cost, live-path check and are not approximated here.

    `"ask"` is excluded from the check on purpose: an outcome that asked a
    clarifying question made no claim yet, so having no citation is its
    correct, expected shape, not a provenance failure.
    """
    if trust_signal in ("answer", "flag") and not citations:
        return ["uncited_claim"]
    return []


def assemble_interaction(query: Query, events: list[Event]) -> InteractionRow | None:
    """Fold one finished run into one `InteractionRow`, or `None`.

    `None` only when `events` carries no `done` event at all, which is not
    a shape any real caller produces (`run()`'s own contract, including its
    crash-fallback path, always ends in `done`; see `core/run.py`'s module
    docstring), but a defensive guard against an empty or truncated events
    list costs nothing and keeps this function honest about the one thing
    it actually cannot proceed without: a trace to attribute the row to.

    Every other field is read from whichever typed event actually carries
    it, and every step below tolerates that event being absent, because a
    Guardrail refusal produces a run with no `plan`, no `think`, and no
    `citation` events at all (see the ticket's own "THE CASE MOST LIKELY TO
    BE MISSED").
    """
    done_event = _last_of_type(events, "done")
    if done_event is None:
        return None

    done_payload = DonePayload.model_validate(done_event.payload)
    trust_signal = done_payload.trust_outcome

    think_event = _last_of_type(events, "think")
    plan_events = [event for event in events if event.type == "plan"]
    citations = [event.payload for event in events if event.type == "citation"][
        :_MAX_CITATIONS
    ]

    query_class = _query_class_from(think_event)
    route = _route_from(plan_events, events)
    normalized_entities = _normalized_entities_from(plan_events)
    coverage_tags = coverage_tags_for(citations)
    hard_fails = _hard_fails_for(trust_signal, citations)
    rubric_outcome = rubric_outcome_for(trust_signal=trust_signal, hard_fails=hard_fails)

    # F-4.5-A-02's ownership lesson, restated at a new table: `owner_id` is
    # the namespaced principal (`user:<uuid>` or `guest:<uuid>`), never
    # `query.user_id` (advisory-only, and NULL for every guest). Passing it
    # straight through and letting `session_row_key` raise
    # `CallerIdentityRequired` on a missing owner_id is deliberate, not an
    # oversight: a query with no caller identity is a real error state this
    # function refuses to paper over with an anonymous-bucket default, the
    # exact shape of bug F-4.5-A-02 was.
    owner_id = query.owner_id
    session_id = session_row_key(  # type: ignore[arg-type]
        query.session_id, owner_id=owner_id
    )
    # Reached only once `session_row_key` above did not raise, so `owner_id`
    # is guaranteed a valid non-empty string at this point.
    user_id = _account_uuid(owner_id)  # type: ignore[arg-type]

    return InteractionRow(
        trace_id=done_event.trace_id,
        user_id=user_id,
        session_id=session_id,
        # The SAME owner_id already used above to compute session_id. Never
        # re-derived or re-parsed: it is passed straight through from
        # `query.owner_id`, which `session_row_key` already validated by not
        # raising `CallerIdentityRequired`. This is F-4.6-01's fix, the fact
        # `write_feedback`'s ownership check now compares directly.
        owner_id=owner_id,
        query_text=query.text,
        normalized_entities=normalized_entities,
        query_class=query_class,  # type: ignore[arg-type]
        route=route,
        trust_signal=trust_signal,  # type: ignore[arg-type]
        rubric_outcome=rubric_outcome,  # type: ignore[arg-type]
        # Section 15: populated only by build phase 5.1's offline
        # golden-dataset replay, never on this live path.
        rubric_score=None,
        citations=citations,
        coverage_tags=coverage_tags,
        # Capture never writes feedback; `record_feedback` does, on a row
        # that already exists.
        user_feedback=None,
        cost_usd=done_payload.total_cost_usd,
        latency_ms=done_payload.elapsed_ms,
    )
