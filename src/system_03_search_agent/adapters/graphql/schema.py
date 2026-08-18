"""The GraphQL operation roots and their resolvers: build phase 4.3, the
first half of ticket T-4.3-07, the integration seam.

Spec: `tracker/phase_4.3.md`'s "The interfaces, fixed by the lead before
dispatch" (the locked four-operation set), `requirements/Technical_
specification.md` Section 13.1 (the REST behaviors each operation mirrors),
Section 13.2 (the controlling precedent for a non-streaming surface folding
the event stream into one response).

This module is deliberately thin. It constructs a `Query` and a
`RequestContext`, calls the run registry, and hands the resulting run to
`fold.py`. It contains no retrieval, no grounding, no cost logic and no
second authorization rule, per Section 1.5's boundary table and Decision A.
Every guarantee it appears to make is already made by the core.

WHY THIS FILE IS NOT PARALLELIZED, stated here because it is the reason it
exists as its own ticket: build phase 4.2's finding F-4.2-08 was a seam
defect, not a logic defect. One builder wrote an error renderer that
dispatched on `httpx` exception types while a sibling builder, in the same
phase, raised its own unrelated hierarchy, so every typed error fell through
to a generic message. Both builders satisfied their own ticket. Nobody owned
the interface between them. So the four modules this file wires together
(`types`, `fold`, `context`, `security`) were each built independently
against a fixed contract, and the wiring was held back for one agent that
could see all four at once.

TWO IMPORT DISCIPLINES THIS FILE MUST KEEP, both load-bearing rather than
stylistic, because breaking either one silently disables a premise-gate arm
rather than failing loudly:

    - `fold` is reached through the MODULE (`from . import fold`, then
      `fold.fold_run(...)`), never as `from .fold import fold_run`. The
      premise gate's error-masking arm monkeypatches
      `fold_module.fold_run`; a direct name import binds the original
      function at import time, so the patch would be silently ignored and
      the arm would become a test that cannot fail. That is the single most
      repeated failure class in this repository's LEARNINGS.md.
    - This module never imports `adapters/web_sse/app.py`. That module
      imports this surface's router in order to mount it, so the reverse
      import is circular. This is also why the run-ownership rule was
      promoted into `core/run_registry.py` (`resolve_owned_run`) rather
      than imported from `app.py`'s `_get_owned_run`.

Depends on:
    - system_03_search_agent.adapters.graphql.context (GraphQLContext)
    - system_03_search_agent.adapters.graphql.fold (fold_run,
      fold_run_snapshot, fold_citations), reached through the module
    - system_03_search_agent.adapters.graphql.security (SCHEMA_EXTENSIONS,
      STRAWBERRY_CONFIG, RUN_CREATING_FIELD_NAME)
    - system_03_search_agent.adapters.graphql.types (every result type, the
      `SchemaError` base this module re-exports, `InvalidAskInput` and its
      published code and message table)
    - pydantic (ValidationError), caught around the core `Query`
      construction so an input failure is never masked into a bare internal
      error (F-4.3-A-16 / J-10)
    - system_03_search_agent.contracts.query (Query, RequestContext)
    - system_03_search_agent.core.run_registry (default_registry,
      resolve_owned_run's two errors, the concurrent-run cap error)

Reads:
    - Nothing directly.

Writes:
    - Nothing directly. Run state lives in the registry.
"""

from __future__ import annotations

import uuid

import strawberry
from pydantic import ValidationError

from system_03_search_agent.adapters.graphql import fold, security
from system_03_search_agent.adapters.graphql.context import GraphQLContext
from system_03_search_agent.adapters.graphql.types import (
    ASK_INPUT_ERROR_CODE,
    ASK_INPUT_MESSAGES_BY_CORE_FIELD,
    AskInput,
    AskResult,
    CitationsExport,
    InvalidAskInput,
    RunResult,
    SchemaError,
    StopRunResult,
)
from system_03_search_agent.contracts.query import Query as CoreQuery
from system_03_search_agent.contracts.query import RequestContext
from system_03_search_agent.core.run_registry import (
    ConcurrentRunCapExceededError,
    RunNotFoundError,
    RunNotOwnedError,
    default_registry,
)

# ---------------------------------------------------------------------------
# The public error shapes. Each carries a stable machine-readable code so a
# caller branches on the kind without parsing prose (tool-call-budgets.md:
# an error must say what to do next, not only that something failed).
#
# HOW THESE BECOME PUBLIC, and the one surprising coupling in this file.
# `security.py`'s `MaskErrors` allowlist masks BY DEFAULT and discloses an
# exception only when its class declares `security.PUBLIC_ERROR_MARKER`
# (`__graphql_public__ = True`), which every class below inherits from
# `SchemaError`. It derives the wire `extensions.code` from the CLASS NAME.
# Both choices are deliberate and documented there. Two things follow for
# this module, and neither is obvious from reading either file alone:
#
#   - Nothing is unmasked by accident. The marker rule REPLACED an earlier
#     "trusted because of the package the class lives in" rule, which
#     F-4.3-A-12 drove end to end into a credential disclosure. Declaring
#     the marker is now the whole permission, and it is only defensible
#     while every message below is a fixed literal, never interpolated from
#     an exception, a host, or a caller value. F-4.1-A-09 measured a live
#     database host, port and username reaching a caller through a field
#     assumed safe. Filed as F-4.3-L-03.
#   - THE CLASS NAME IS THE WIRE CONTRACT. `RunNotFound` publishes
#     `code: "RUN_NOT_FOUND"`. Renaming the class silently changes the
#     public API, so these names are chosen for the codes they produce and
#     are pinned by a test rather than left to a future refactor's judgment.
#     Filed as F-4.3-L-04.
# ---------------------------------------------------------------------------

_RUN_NOT_FOUND_MESSAGE = "no such run"
_RUN_NOT_OWNED_MESSAGE = "you do not own this run"

# Mirrors adapters/web_sse/app.py's _CONCURRENT_RUN_CAP_MESSAGE in substance:
# actionable (it says what to do), and carrying NOTHING derived from the
# exception, whose own string embeds the internal namespaced owner id and the
# internal cap value (F-4.10-J-04, and F-4.1-J3-01 against the same habit).
_CONCURRENCY_CAP_MESSAGES_BY_BOUND: dict[str, str] = {
    "concurrency": (
        "too many of your runs are already in flight; wait for one to finish, "
        "or stop one with the stopRun mutation, then retry"
    ),
}
_CONCURRENCY_CAP_FALLBACK_MESSAGE = _CONCURRENCY_CAP_MESSAGES_BY_BOUND["concurrency"]


# `SchemaError` is DEFINED IN `types.py` and imported above, not declared
# here where it was first written. It moved at the F-4.3-A-16 / J-10 fix
# because `types.py` now raises a caller-facing error of its own
# (`InvalidAskInput`, from an input scalar) and cannot import this module:
# schema.py imports types.py, so one shared base for the whole surface has to
# sit on that side of the edge. This module re-exports it, so
# `schema.SchemaError` still names the same class, every subclass below is
# unchanged, and every published `extensions.code` is unchanged too (the code
# is derived from the class name alone). The discipline it carries is
# unchanged and still binding: every message raised through it is a fixed
# literal, never interpolated from a caught exception, a host, a path, or an
# internal bound.


class RunNotFound(SchemaError):
    # Publishes code RUN_NOT_FOUND. Name is the wire contract, see above.
    pass


class RunNotOwned(SchemaError):
    # Publishes code RUN_NOT_OWNED.
    pass


class ConcurrentRunCapExceeded(SchemaError):
    # Publishes code CONCURRENT_RUN_CAP_EXCEEDED.
    pass


def _resolve_owned(run_id: str, owner_id: str):
    """Resolve `run_id` under `owner_id` through THE one ownership rule.

    Calls `RunRegistry.resolve_owned_run`, the rule promoted into the
    registry at T-4.3-07 precisely so this surface enforces the identical
    check `adapters/web_sse/app.py`'s `_get_owned_run` enforces rather than
    deriving a second one. This function only maps the rule's two domain
    errors onto this surface's transport, exactly as `_get_owned_run` maps
    them onto 404 and 403.

    The unknown-before-ownership ordering is the registry's, not this
    function's, so the two surfaces cannot drift on it.
    """
    try:
        return default_registry.resolve_owned_run(run_id, owner_id)
    except RunNotFoundError:
        raise RunNotFound(_RUN_NOT_FOUND_MESSAGE) from None
    except RunNotOwnedError:
        raise RunNotOwned(_RUN_NOT_OWNED_MESSAGE) from None


def _owner_id_of(info: strawberry.Info) -> str:
    """The authenticated caller's namespaced owner id.

    `context.py` has already refused every unauthenticated caller BEFORE
    this module runs (its `get_context` raises out of the FastAPI dependency
    layer, ahead of GraphQL parsing), so a resolver never has to handle an
    absent principal. Reading the principal here rather than re-deriving it
    keeps this surface's auth in exactly one place.
    """
    context: GraphQLContext = info.context
    return f"user:{context.principal.id}"


def _caller_fixable_ask_input_message(exc: ValidationError) -> str | None:
    """The fixed, published message for the first caller-supplied field
    `exc` rejected, or `None` when nothing the caller sent is at fault.

    The SECOND half of the F-4.3-A-16 / J-10 fix, and the reason it exists
    even though `AskInput`'s scalars already refuse an out-of-bounds value
    before this resolver runs: the `Query` built here also carries
    `trace_id` and `user_id`, which the SERVER supplies, so this
    construction can still fail on a field no scalar guards. Without this
    split, either every such failure stays a masked internal error (the bug)
    or every one of them tells the caller to fix input they never sent
    (a second wrong message dressed as a fix).

    Only `exc`'s structural `loc` is read, never its message and never its
    `input_value`, whose string embeds the rejected content (F-4.3-A-12).
    The returned message comes wholly from `types.ASK_INPUT_MESSAGES_BY_
    CORE_FIELD`, the same shape `_CONCURRENCY_CAP_MESSAGES_BY_BOUND` above
    already uses: the table is the message source, the exception picks a key.
    """
    for error in exc.errors():
        location = error.get("loc") or ()
        if not location:
            continue
        message = ASK_INPUT_MESSAGES_BY_CORE_FIELD.get(str(location[0]))
        if message is not None:
            return message
    return None


@strawberry.type
class Query:
    @strawberry.field
    async def run(self, info: strawberry.Info, run_id: strawberry.ID) -> RunResult:
        # Non-blocking by design: reports what the run has produced so far
        # and says whether it is finished, so a caller can poll without this
        # surface growing a second live-stream transport (phase file scope
        # reading 3).
        owner_id = _owner_id_of(info)
        _resolve_owned(str(run_id), owner_id)
        return await fold.fold_run_snapshot(str(run_id))

    @strawberry.field
    async def citations(self, info: strawberry.Info, run_id: strawberry.ID) -> CitationsExport:
        # Mirrors GET /v1/query/{run_id}/citations, including the two facts
        # REST can only disclose as HTTP response headers. GraphQL has no
        # header channel, so both are fields on CitationsExport; without
        # them the disclosure would vanish silently on this surface, which
        # is how F-4.0-A-12 went wrong once already.
        owner_id = _owner_id_of(info)
        entry = _resolve_owned(str(run_id), owner_id)
        return fold.fold_citations(entry)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def ask(self, info: strawberry.Info, input: AskInput) -> AskResult:
        # `input` shadows a builtin. The name is part of the locked GraphQL
        # operation set in tracker/phase_4.3.md and is the conventional
        # GraphQL argument name, so the published schema is not renamed to
        # satisfy a Python convention. This repo's ruff config does not
        # enable flake8-builtins, so no suppression is needed either.
        #
        # A state-changing operation, hence a mutation rather than a query:
        # it creates a run and spends a real model budget. That is also why
        # security.py enforces AT MOST ONE of this field per document.
        owner_id = _owner_id_of(info)
        context: GraphQLContext = info.context

        run_id = str(uuid.uuid4())
        # `AskInput`'s two scalars have already refused an out-of-bounds
        # `text` or `sessionId` during input coercion, before this resolver
        # was entered. This catch is the defense-in-depth half: `trace_id`
        # and `user_id` below are server-supplied and carry their own bounds
        # on `Query`, so a `ValidationError` is still reachable here, and an
        # unhandled one is masked into a generic internal error with no code
        # (F-4.3-A-16 / J-10). A caller-supplied field at fault becomes a
        # coded, actionable refusal; anything else stays masked, because it
        # is a genuine server fault and saying otherwise would misdirect the
        # caller into "fixing" input that was already correct.
        try:
            core_query = CoreQuery(
                text=input.text,
                session_id=input.session_id,
                trace_id=run_id,
                user_id=str(context.principal.id),
                audience_depth=(
                    input.audience_depth.value if input.audience_depth is not None else "researcher"
                ),
            )
        except ValidationError as exc:
            message = _caller_fixable_ask_input_message(exc)
            if message is None:
                raise
            raise InvalidAskInput(
                message, extensions={"code": ASK_INPUT_ERROR_CODE}
            ) from None
        # `run_id` is passed through rather than letting the registry mint
        # its own, so the id the caller holds and the `trace_id` threaded
        # through every event and every audit record are the same string
        # under two names, never two identifiers.
        #
        # `operator_mode` is pinned False in code, matching the MCP surface
        # rather than deriving it from the caller's role the way the SSE
        # surface does. This surface has no field a cost figure could be
        # selected into, so an operator allowlist entry must not be able to
        # open one here.
        run_context = RequestContext(surface="graphql", operator_mode=False)
        try:
            default_registry.create_run(
                core_query,
                run_context,
                run_id=run_id,
                owner_id=owner_id,
            )
        except ConcurrentRunCapExceededError as exc:
            raise ConcurrentRunCapExceeded(
                _CONCURRENCY_CAP_MESSAGES_BY_BOUND.get(
                    exc.bound, _CONCURRENCY_CAP_FALLBACK_MESSAGE
                )
            ) from None

        return await fold.fold_run(run_id)

    @strawberry.mutation
    async def stop_run(self, info: strawberry.Info, run_id: strawberry.ID) -> StopRunResult:
        # Idempotent, mirroring POST /v1/query/{run_id}/stop: stopping a
        # finished or already-stopped run is a no-op, never an error
        # (production-standards.md's retry-safety gate, since the caller may
        # legitimately retry).
        #
        # `stopped` REPORTS WHAT HAPPENED, and used to be the fixed literal
        # `True` (F-4.3-A-20). `cancel_run` is a documented no-op on a run
        # whose task has already finished, so the old literal claimed a stop
        # that never occurred, and contradicted `citations.runCancelled` on
        # this same surface, which reported `false` for the same run. Two
        # fields disagreeing about one run is worse than either answer alone,
        # and "did my stop do anything" is the one thing a caller calls this
        # mutation to find out. Idempotency requires that a repeated stop not
        # ERROR; it never required saying something untrue.
        #
        # The read and the cancel are adjacent with NO await between them, so
        # the event loop cannot advance the run's task in the gap: this is an
        # exact report, not a sampled guess. `task.done()` is the only signal
        # available synchronously (`entry.cancelled` is set later, by the
        # drain loop, once the cancellation is actually observed).
        owner_id = _owner_id_of(info)
        resolved = str(run_id)
        entry = _resolve_owned(resolved, owner_id)
        was_in_flight = not entry.task.done()
        default_registry.cancel_run(resolved)
        return StopRunResult(run_id=resolved, stopped=was_in_flight)


# The one schema this surface serves. Built once at import time, with the
# hardened extension list and config security.py owns, so no caller-facing
# path can assemble a schema that skips a bound.
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=list(security.SCHEMA_EXTENSIONS),
    config=security.STRAWBERRY_CONFIG,
)

# Cross-checked at import rather than trusted: security.py enforces "at most
# one run-creating field per document" against a field NAME, and this module
# is what publishes that name. If the two ever disagree, the bound silently
# stops matching the real mutation and one document could start many runs,
# which is the single most expensive failure available on this surface. A
# name mismatch is therefore an import-time crash, not a runtime surprise.
# `get_field_for_type` is Strawberry's own public lookup (verified present on
# strawberry.Schema in the installed 0.324.0), used here rather than reaching
# into the schema converter's internal type map, so this check cannot itself
# break on a library internal.
if schema.get_field_for_type(security.RUN_CREATING_FIELD_NAME, "Mutation") is None:
    raise RuntimeError(
        f"security.RUN_CREATING_FIELD_NAME is {security.RUN_CREATING_FIELD_NAME!r}, which names no "
        "published field on the Mutation type, so the one-run-per-document bound "
        "would silently stop matching the real run-creating mutation"
    )
