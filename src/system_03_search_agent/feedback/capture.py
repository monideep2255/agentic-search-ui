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
    CitationPayload,
    CostPayload,
    DonePayload,
    Event,
    PlanPayload,
    ThinkPayload,
    TokenPayload,
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

#: The stored bound on a saved answer, measured rather than picked. See
#: `alembic/versions/0010_interactions_saved_answer.py`'s docstring for the
#: measurement; the short form is that the longest answer in 150 live runs
#: was about 8,900 characters of prose, a table-bearing answer renders about
#: 2.1 times its prose, and 32000 clears the product of those with headroom.
#: An answer OVER this bound is stored as None, never truncated: the person
#: is offered Run again instead of being shown a different answer from the
#: one they saw.
MAX_ANSWER_MARKDOWN = 32000

#: The two outcomes that actually put an answer on screen. A refusal or a
#: clarifying question is deliberately NOT saved, and this is the narrow
#: choice rather than the generous one. The answer screen renders those two
#: outcomes from other events entirely (`useRunView.ts` strips a no-data
#: refusal's own tokens from the claims list and renders the refusal message
#: off the `trust_signal` payload instead), so saving their tokens would
#: produce a stored view that differs from the screen the person saw. They
#: fall back to today's behaviour, which costs that person nothing: someone
#: who was refused wants to ask again anyway.
_SAVEABLE_OUTCOMES = ("answer", "flag")


def _cell(value: str) -> str:
    """One markdown table cell: pipes escaped, whitespace flattened.

    A raw `|` would end the cell early and silently reshape the table, and a
    raw newline would end the row. Both are escaped or flattened rather than
    dropped, so no character of the value is lost.
    """
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()


def _markers_for(marker_ids: list[str], display_index_by_id: dict[str, int]) -> str:
    """The `[1][2]` markers a row or list item cites, in the screen's own numbers.

    Built from the run's `citation` events rather than from the token text,
    because a `table_row` token's `text` is the grounded sentence and its
    VISIBLE content is `cells`, which carries no marker at all. A marker id
    with no citation event is skipped rather than guessed a number for.
    """
    numbers = [display_index_by_id[mid] for mid in marker_ids if mid in display_index_by_id]
    return "".join(f"[{n}]" for n in numbers)


def answer_markdown_from(events: list[Event]) -> str | None:
    """The finished answer as it stood on screen, as markdown, or None.

    MEASURED BEFORE IT WAS WRITTEN, and the measurement is the reason this
    function exists at all rather than a one-line join. From a real run
    (`testing/Developer/reports/2026-09-22_isolate_search/round2/
    tokens_G-035.json`, 31 live `token` events):

    - A `table_header` token has `text: ""` and its whole visible content in
      `cells: ["Isolate", "AMR genes"]`.
    - A `table_row` token's visible content is `cells: ["C236-11", "acrF,
      aph(3'')-Ib, blaCTX-M-15, ..."]`, while its `text` is the grounded
      sentence "Pathogen Detection isolate name: C236-11 [1]. ".

    So `"".join(token.text)`, which is what the 150-run measurement harness
    does (`run_consistency.py:208`) and what "the answer text" sounds like it
    means, turns a twenty-row table into twenty repetitive sentences and
    drops every AMR gene the person actually read. Measured on that run: 1448
    characters joined against 3095 of markdown, so more than half the answer
    is in `cells`. DO NOT SIMPLIFY THIS BACK INTO A JOIN.

    Returns None, never a partial answer, when the run emitted no tokens or
    when the result exceeds `MAX_ANSWER_MARKDOWN`. None means "there is no
    saved answer for this row", and the surface falls back to re-asking,
    which is exactly what it does today.

    ## What this deliberately does not carry

    `TokenPayload.emphasis` is read by the answer screen but is NOT rendered
    as bold here. That is fidelity, not laziness: UI fix 11.27 (product
    owner, 2026-09-14, "There is too much bold") made the screen bold exactly
    one emphasis term in the lead summary and render every other one at
    regular weight. Bolding all of them in the saved answer would rebuild the
    wall of bold that fix removed, so the saved answer would look MORE
    emphasised than the one the person saw. The words are identical either
    way.
    """
    display_index_by_id: dict[str, int] = {}
    for event in events:
        if event.type != "citation":
            continue
        payload = CitationPayload.model_validate(event.payload)
        display_index_by_id.setdefault(payload.citation_id, payload.display_index)

    blocks: list[str] = []
    prose: list[str] = []
    table: list[str] = []

    def flush_prose() -> None:
        text = "".join(prose).strip()
        prose.clear()
        if text:
            blocks.append(text)

    def flush_table() -> None:
        if table:
            blocks.append("\n".join(table))
            table.clear()

    def flush_all() -> None:
        flush_prose()
        flush_table()

    for event in events:
        if event.type != "token":
            continue
        payload = TokenPayload.model_validate(event.payload)
        kind = payload.kind
        cells = payload.cells or []
        markers = _markers_for(payload.marker_ids, display_index_by_id)

        if kind == "paragraph_break":
            flush_all()
            continue
        if kind == "heading":
            flush_all()
            heading = payload.text.strip()
            if heading:
                blocks.append(f"## {heading}")
            continue
        if kind == "note":
            flush_all()
            note = payload.text.strip()
            if note:
                blocks.append(note)
            continue
        if kind == "table_header":
            flush_all()
            if cells:
                table.append("| " + " | ".join(_cell(c) for c in cells) + " |")
                table.append("| " + " | ".join("---" for _ in cells) + " |")
            continue
        if kind == "table_row":
            flush_prose()
            if not cells:
                continue
            if not table:
                # A row with no header before it. Rendered as a list item
                # rather than given an invented header row: markdown has no
                # headerless table, and making up column labels would put
                # words on screen that no run produced. Not a shape any
                # measured run emits; `write_node` always sends the header
                # first.
                label = ": ".join(_cell(c) for c in cells)
                blocks.append(f"- {label}{markers}".rstrip())
                continue
            rendered = [_cell(c) for c in cells]
            # The markers go on the FIRST cell, where the record's own name
            # is and where the screen puts the citation chip for the row.
            rendered[0] = f"{rendered[0]} {markers}".strip() if markers else rendered[0]
            table.append("| " + " | ".join(rendered) + " |")
            continue
        if kind == "list_item":
            flush_all()
            label = _cell(cells[0]) if cells else payload.text.strip()
            if label:
                blocks.append(f"- {label}{markers}".rstrip())
            continue

        # `claim`, and a token from a producer that sends no `kind` at all.
        # Its text already carries its own `[1][2]` markers inline and its
        # own trailing space, so consecutive claims join into one paragraph
        # exactly as they read on screen.
        flush_table()
        prose.append(payload.text)

    flush_all()

    markdown = "\n\n".join(block for block in blocks if block)
    if not markdown:
        return None
    if len(markdown) > MAX_ANSWER_MARKDOWN:
        return None
    return markdown


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

    # Fix-plan item 10.2. The saved answer, so clicking a past search shows
    # the answer they already got instead of paying for a second search.
    #
    # THE GUEST EXCLUSION IS HERE, at the write, and nowhere else is enough.
    # `owner_id` is the namespaced principal, so `user:` is an account and
    # `guest:` is not. A guest run never builds the markdown at all, which
    # is cheaper than building it and discarding it and, more importantly,
    # means no guest answer ever exists in memory long enough to be written
    # by accident. `InteractionRow` refuses the pairing anyway and the
    # database refuses it again (alembic 0010), so this is the first of
    # three statements of one rule, not the only one.
    answer_markdown: str | None = None
    audience_depth: str | None = None
    answer_trust_line: str | None = None
    if owner_id.startswith("user:") and trust_signal in _SAVEABLE_OUTCOMES:
        answer_markdown = answer_markdown_from(events)
        if answer_markdown is not None:
            audience_depth = query.audience_depth
            answer_trust_line = done_payload.trust_line

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
        answer_markdown=answer_markdown,
        audience_depth=audience_depth,  # type: ignore[arg-type]
        answer_trust_line=answer_trust_line,
    )
