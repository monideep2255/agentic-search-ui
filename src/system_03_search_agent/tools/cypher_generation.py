"""Cypher generation with one informed repair retry.

Section 6.1's second pipeline step: generate a Cypher query body with a
plan-tier LLM call, constrained by a sliced schema. This module owns
exactly that one call plus deterministic extraction of the Cypher body
from the model's raw response. It does not validate the generated Cypher
(system_03_search_agent.tools.cypher_validator, a different builder's
module, owns that) and it does not retry internally: T-2.1-07's
`cypher_query` pipeline is what calls `generate_cypher` a second time with
`prior_error` set, after the validator rejects the first attempt.

Depends on:
    - system_03_search_agent.tools.cypher_schemas (CypherQueryInput), for
      the structured intent this module reads from.
    - The `harness` argument's `call_tier` method, at the "plan" tier
      (system-design-patterns.md rule 11: model identity is a harness
      decision, never hardcoded here). No import of
      system_03_search_agent.harness.harness is taken at module level, so
      this module accepts anything exposing an async
      `call_tier(tier, messages, *, cache_prefix=None)` returning an
      object with a `.content` string attribute; production code passes a
      real `Harness`, tests pass a lightweight fake.

Reads:
    - Nothing at import time. No network call, no database call: the one
      network-shaped call is the harness's own `call_tier`, mocked in
      every test in this ticket's file scope.

Writes:
    - Nothing.

Depended by:
    - system_03_search_agent.tools.cypher_query (T-2.1-07, integration)
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from system_03_search_agent.tools.cypher_schemas import CypherQueryInput

# Cypher clauses that legally open a query body. A response with no fenced
# code block and no line starting with one of these is treated as having
# no recoverable Cypher at all.
_CYPHER_START_KEYWORDS: tuple[str, ...] = (
    "MATCH",
    "OPTIONAL MATCH",
    "WITH",
    "RETURN",
    "CALL",
    "UNWIND",
)

# Matches a fenced code block, with or without a language tag
# (```cypher, ```sql, or a bare ```), non-greedy so the FIRST fenced block
# is the one extracted.
_FENCE_PATTERN = re.compile(r"```[A-Za-z]*\s*\n?(.*?)```", re.DOTALL)

# AGE's dollar-quoting for the Cypher body inside a
# SELECT * FROM cypher('ncbi_kg', $$ ... $$) AS (...) wrapper. Used to
# recover the inner Cypher if the model emits the SQL wrapper by mistake,
# rather than accepting the wrapper through as-is.
_DOLLAR_QUOTE_PATTERN = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)


class CypherGenerationError(RuntimeError):
    """The model response contained no Cypher that could be recovered
    deterministically. T-2.1-07's pipeline treats this the same as a
    validation failure: it retries once with `prior_error` set, and
    returns `status: "error"` on a second failure.
    """


class HarnessLike(Protocol):
    """The subset of `Harness` this module actually calls. A Protocol,
    not an import of the concrete `Harness` class, so this module stays
    decoupled from the harness package and a test's fake harness needs
    only to satisfy this shape.
    """

    async def call_tier(
        self,
        tier: str,
        messages: list[dict[str, str]],
        *,
        cache_prefix: str | None = None,
    ) -> Any: ...


def _strip_sql_wrapper(body: str) -> str:
    """If `body` is itself a `SELECT * FROM cypher('ncbi_kg', $$ ... $$)`
    wrapper, recover the inner Cypher between the dollar quotes instead of
    returning the wrapper as-is. `generate_cypher`'s prompt instructs the
    model never to emit this wrapper; this is the deterministic recovery
    path for when it does anyway, not a silent pass-through.
    """
    stripped = body.strip()
    if not stripped.upper().startswith("SELECT"):
        return body
    match = _DOLLAR_QUOTE_PATTERN.search(stripped)
    if match is None:
        return body
    inner = match.group(1).strip()
    return inner if inner else body


def _extract_cypher_body(raw: str | None) -> str:
    """Deterministically recover the Cypher body from a raw model
    response, or raise `CypherGenerationError`.

    `raw` is typed `str | None` because a provider genuinely returns
    `content=None`, which finding F-2.1-B03 observed live: this function
    was annotated `raw: str`, called `raw.strip()` on it, and raised
    `AttributeError` out of a pipeline whose own docstring promises it
    never raises. `act_node` catches only `HarnessCallError`, so it
    escaped `run()` entirely and crashed the query rather than degrading.

    A `None` response is a model that produced nothing, which is exactly
    the condition `CypherGenerationError` already exists to signal, so it
    routes there and the caller's existing retry-then-error path handles
    it like any other unrecoverable response.

    Order of attempts:
        1. The first fenced code block (```cypher, ```sql, or bare```),
           since a fenced response unambiguously marks its own boundary.
        2. Failing that, a bare `SELECT * FROM cypher(...)` SQL wrapper
           spanning the whole response with no fence and no surrounding
           prose, recovered via `_strip_sql_wrapper` directly.
        3. Failing that, the first line that opens with a Cypher clause
           keyword (MATCH, OPTIONAL MATCH, WITH, RETURN, CALL, UNWIND)
           onward, on the assumption that any prose the model added lives
           only before the first such line, never interleaved after it.

    Every path also runs its result through `_strip_sql_wrapper`, so a
    recovered body that is itself a `SELECT * FROM cypher(...)` wrapper is
    reduced to the inner Cypher rather than returned whole.

    A response with neither a fence, a recoverable SQL wrapper, nor a
    recognizable opening keyword, or one whose only recoverable content
    is empty, is not passed through raw: it raises
    `CypherGenerationError` instead.
    """
    if raw is None:
        raise CypherGenerationError(
            "model returned no content at all (content=None); no Cypher to extract"
        )

    text = raw.strip()
    if not text:
        raise CypherGenerationError("model returned an empty response; no Cypher to extract")

    fence_match = _FENCE_PATTERN.search(text)
    if fence_match is not None:
        body = fence_match.group(1).strip()
        if not body:
            raise CypherGenerationError("model response contained an empty fenced code block")
        return _strip_sql_wrapper(body)

    unwrapped = _strip_sql_wrapper(text)
    if unwrapped != text:
        unwrapped = unwrapped.strip()
        if not unwrapped:
            raise CypherGenerationError(
                "model response's SQL wrapper contained no recoverable Cypher body"
            )
        return unwrapped

    lines = text.splitlines()
    start_index: int | None = None
    for index, line in enumerate(lines):
        upper = line.strip().upper()
        if any(upper.startswith(keyword) for keyword in _CYPHER_START_KEYWORDS):
            start_index = index
            break

    if start_index is None:
        raise CypherGenerationError(
            "model response contained no recoverable Cypher: no fenced code "
            "block and no line opening with MATCH, OPTIONAL MATCH, WITH, "
            "RETURN, CALL, or UNWIND"
        )

    body = "\n".join(lines[start_index:]).strip()
    if not body:
        raise CypherGenerationError("model response had a Cypher-opening line but no body")
    return _strip_sql_wrapper(body)


def _build_system_message(schema_slice: str) -> dict[str, str]:
    content = (
        "You are the Cypher generation step for a read-only biomedical "
        "knowledge graph tool. Generate exactly one Cypher query body for "
        "the AGE graph described below. Follow these rules strictly.\n\n"
        "1. Every relationship pattern must carry an explicit edge label, "
        "for example [:is_sequence_variant_of]. Never emit an untyped "
        "relationship such as [r], [], or -->; an untyped edge compiles to "
        "a slow UNION ALL across every edge table.\n"
        "2. Never interpolate a caller-supplied entity value as a literal "
        "in the Cypher text. Use a named Cypher parameter instead, "
        "referenced as $param_name, for every value drawn from "
        "target_entities or query_intent.\n"
        "3. Return only the Cypher query body: no markdown code fence, no "
        "prose before or after it, and no SQL wrapper such as "
        "SELECT * FROM cypher(...).\n"
        "4. Do not add a LIMIT clause yourself; the caller injects the row "
        "limit separately after validation.\n\n"
        f"Graph schema:\n{schema_slice}"
    )
    return {"role": "system", "content": content}


def _build_user_message(
    tool_input: CypherQueryInput,
    prior_error: str | None,
    entity_bindings: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the generation call's user message.

    `entity_bindings` is the naming contract that closes finding F-2.1-B01.
    Before it existed, the caller listed `target_entities` as a bare array
    and let the model name its own parameters, then bound them back
    POSITIONALLY. A query naming two entities therefore bound the first
    extracted CURIE to whatever parameter the model happened to write
    first, which is not necessarily the entity the question was about.

    Reproduced: "Compare NCBIGene:7157 and BRCA1: which diseases is BRCA1
    linked to?" bound TP53, returned 12 real TP53 disease rows with valid
    NCBI citations, and reported `status="ok"` with
    `trust_outcome="answer"`. A fully cited, confident answer about the
    wrong gene, with every gate green.

    Naming each value explicitly, and requiring the model to use only
    those names, removes the guess. The binding is then by name on the way
    back, never by position, and a parameter the model invents anyway is
    rejected by the validator rather than silently bound to the wrong
    value.
    """
    lines = [
        f"query_intent: {tool_input.query_intent}",
        f"query_class: {tool_input.query_class.value}",
    ]

    if entity_bindings:
        lines.append(
            "Bound parameters. Use ONLY these parameter names, exactly as "
            "written, and use the one whose value is the entity the "
            "query_intent actually asks about:"
        )
        for name, value in entity_bindings.items():
            lines.append(f"  ${name} = {value}")
        lines.append(
            "Do not invent any other $parameter name. Do not write an "
            "entity value as a literal; reference it by its bound name."
        )
    else:
        lines.append(f"target_entities: {tool_input.target_entities}")

    lines.append(f"row_limit: {tool_input.row_limit}")
    if prior_error:
        lines.append("")
        lines.append(
            "The previous attempt was rejected by the Cypher validator. "
            "Fix the query below to address the validator's error; do not "
            "repeat the same mistake."
        )
        lines.append(f"Validator error: {prior_error}")
    return {"role": "user", "content": "\n".join(lines)}


async def generate_cypher(
    harness: HarnessLike,
    tool_input: CypherQueryInput,
    schema_slice: str,
    prior_error: str | None = None,
    entity_bindings: dict[str, str] | None = None,
) -> str:
    """Issue exactly one plan-tier call and return the generated Cypher
    body.

    `harness.call_tier("plan", messages)` is the only network-shaped call
    made here; the model id it resolves to is never named in this module
    (system-design-patterns.md rule 11). When `prior_error` is supplied,
    the user message includes both the validator's error text and enough
    context to make the retry an informed repair rather than a blind
    resample (T-2.1-03's acceptance criterion).

    Raises:
        CypherGenerationError: if the model's response contains no Cypher
            that can be recovered deterministically. This is treated by
            the caller the same way a validation failure is: as a signal
            to retry once with `prior_error` set, and to return
            `status: "error"` if a second attempt also fails.
    """
    messages = [
        _build_system_message(schema_slice),
        _build_user_message(tool_input, prior_error, entity_bindings),
    ]
    response = await harness.call_tier("plan", messages)
    return _extract_cypher_body(response.content)
