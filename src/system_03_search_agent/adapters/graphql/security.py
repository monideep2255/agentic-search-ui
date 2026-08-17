"""The security layer: build phase 4.3, ticket T-4.3-04.

Spec: `tracker/phase_4.3.md`'s "The library, verified against the installed
version rather than the docs" section (the four wrong-for-production
`GraphQLRouter`/`StrawberryConfig` defaults this module overrides), its
"Module contracts" section (this module's required public surface), and its
"Premise gate design" table's Depth/Alias/Token/Complexity/Timeout/
Introspection/No-IDE-GET-WS/Errors-are-masked rows, which this module exists
to satisfy.

Every Strawberry and graphql-core name this module imports was probed
directly against the INSTALLED `strawberry-graphql==0.324.0` (and its
`graphql-core` dependency) rather than trusted from documentation, per the
same discipline `types.py` and `fold.py` already followed: signatures,
default values, and the extension-instantiation contract below were all
read from the installed source, not assumed.

One correction this module makes to a literal reading of its own dispatch
brief, stated here rather than made silently: the brief lists
`SCHEMA_EXTENSIONS` as already-constructed instances (`DisableIntrospection()`,
`QueryDepthLimiter(max_depth=...)`, ...). The installed `strawberry.Schema.
__init__` (`schema.py:319-330` in the installed package) emits a
`DeprecationWarning` for exactly that pattern, because `Schema.get_extensions`
(`schema.py:442-448`) only calls `ext()` to build a fresh instance when `ext`
is NOT already a `SchemaExtension` instance; a pre-built instance is instead
reused, unmodified, across every request `Schema.execute` ever serves,
because `Schema.execute` calls `self.get_extensions()` fresh on EVERY call
(`schema.py:745`) and only skips construction for objects that are already
instances. `RequestTimeoutExtension.on_execute` holds `self.execution_context`
across the request's full resolver-execution await chain (this surface's
`fold_run`, which awaits `default_registry.subscribe` for as long as
`_FOLD_LOOP_TIMEOUT_S`), and `execution_context` is reassigned onto every
extension object fresh at the top of every `execute()` call
(`schema.py:748-749`) whether or not the extension instance is shared. Two
concurrent requests sharing one `RequestTimeoutExtension` instance can
therefore race: request B's `execution_context` assignment can land on the
SAME shared object while request A is still awaiting inside its own
`on_execute`, so request A's post-await code (the code that turns a timeout
into a disclosed error) can read or write request B's `execution_context`
instead of its own. This is not hypothetical for this codebase: every
delivery surface in this repository serves concurrent callers by design
(`system-design-patterns.md` pattern 6, streaming by default; the
concurrent-run cap this same phase's T-4.3-05 ticket decoupled from the free
allowance exists precisely because concurrent callers are the normal case,
not the exception). `SCHEMA_EXTENSIONS` below is therefore a tuple of
zero-argument factories (bare classes where no constructor argument is
needed, `lambda: ...` where one is), never pre-built instances, so
`Schema.get_extensions` constructs a fresh, request-isolated instance of
every extension on every call, matching the modern usage the installed
library's own deprecation warning recommends. This changes nothing about
WHICH extensions are used or WHICH arguments configure each one; it only
changes when each is instantiated.

Depends on:
    - strawberry, strawberry.extensions (DisableIntrospection,
      QueryDepthLimiter, MaxAliasesLimiter, MaxTokensLimiter, MaskErrors,
      AddValidationRules, SchemaExtension), strawberry.schema.config
      (StrawberryConfig): the library surface this module configures.
    - graphql (GraphQLError, ExecutionResult, FieldNode,
      FragmentDefinitionNode, FragmentSpreadNode, InlineFragmentNode,
      OperationDefinitionNode, ValidationContext, ValidationRule): the
      graphql-core primitives `ComplexityBudgetExtension`'s validation rule
      and `RequestTimeoutExtension`'s short-circuit result are built from.

Reads:
    - The module-level `REQUEST_TIMEOUT_S` attribute, read fresh inside
      `RequestTimeoutExtension.on_execute` on every call rather than
      captured at import or `__init__` time, so a test (or a future runtime
      reconfiguration) that reassigns `security_module.REQUEST_TIMEOUT_S`
      takes effect on the very next request.

Writes:
    - Nothing. This module only builds configuration objects and schema
      extensions; it performs no I/O of its own.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Callable, Mapping

from graphql import (
    ExecutionResult as GraphQLExecutionResult,
)
from graphql import (
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    GraphQLError,
    InlineFragmentNode,
    OperationDefinitionNode,
    ValidationContext,
    ValidationRule,
)
from strawberry.extensions import (
    AddValidationRules,
    DisableIntrospection,
    MaskErrors,
    MaxAliasesLimiter,
    MaxTokensLimiter,
    QueryDepthLimiter,
    SchemaExtension,
)
from strawberry.schema.config import StrawberryConfig

# ---------------------------------------------------------------------------
# Exception base. Every exception this module raises subclasses this one,
# so a catch site dispatches on a base class rather than an enumerated list
# of subclasses; that list drifted out of sync with its raiser three
# separate times inside build phase 4.2 alone.
#
# Disclosure is a SEPARATE question from inheritance, and the two were
# conflated until the fix round (F-4.3-A-12). An exception reaches a caller
# only if its class declares `PUBLIC_ERROR_MARKER`, which is an explicit,
# reviewable line. Sharing a base class, or a package, grants nothing.
# ---------------------------------------------------------------------------


class GraphQLSecurityError(Exception):
    """Base exception for this module's own errors.

    Declares itself caller-safe via `PUBLIC_ERROR_MARKER`, which is what
    `_should_mask_error` reads. That declaration carries an obligation:
    every message raised as this class or a subclass must be a fixed literal,
    or built only from values the caller already supplied, and never from a
    caught internal exception, a host, a path, or a configured bound.
    """

    __graphql_public__ = True


# ---------------------------------------------------------------------------
# Bounds. Every one is a named module constant, per this ticket's brief and
# production-standards.md's "every string field bounded and every list
# capped" gate, extended here to documents rather than payload fields
# because GraphQL's own schema language has no maxLength/maxItems to attach.
# ---------------------------------------------------------------------------

# A legitimate document on this schema nests at most 3 levels deep: the
# mutation/query root (depth 0 in the installed QueryDepthLimiter's own
# counting, see strawberry/extensions/query_depth_limiter.py's
# `determine_depth`), the one root field (`ask`/`run`/`citations`/
# `stopRun`, depth 1), a compound field on its result (`trustSignal`/
# `citations`/`disclosures`, depth 2), and that compound field's own leaf
# scalars (depth 3). 10 leaves roughly 3x headroom above that real shape
# while still refusing the crafted-depth-40 attack this phase's premise
# gate drives (tracker/phase_4.3.md's Depth bound row).
MAX_QUERY_DEPTH = 10

# A legitimate document on this schema carries zero aliases in the common
# case, and at most a small handful even for a client that deliberately
# aliases a field to fetch it twice under different names. 20 is generous
# headroom above any real client shape while still well below the crafted
# 60-alias attack this phase's premise gate drives (its Alias bound row).
MAX_ALIAS_COUNT = 20

# The installed MaxTokensLimiter's own docstring example uses this exact
# value (strawberry/extensions/max_tokens.py). A legitimate document on
# this schema (the full `_ASK_DOCUMENT` shape in the premise gate, every
# field on AskResult/TrustSignal/Citation/Disclosures selected at once)
# lexes to well under 200 tokens; 1000 is ~5x headroom above that real
# shape while remaining an order of magnitude below the crafted 5000-field
# attack this phase's premise gate drives (its Token bound row).
MAX_TOKEN_COUNT = 1000

# THE bound this whole module exists for. Every other bound above limits
# WORK a hostile document can demand; this one limits MONEY, because each
# selection of `ask` starts a real, billed model run. A legitimate document
# selects `ask` at most once (a normal mutation) or not at all (a `run`/
# `citations`/`stopRun` query document); the premise gate's own two-armed
# proof is exactly this: a document selecting `ask` under 3 aliases must be
# refused before any run is created, and a document selecting it once must
# still succeed (tracker/phase_4.3.md's Complexity bound row).
MAX_RUN_CREATING_FIELDS_PER_DOCUMENT = 1

# The one field name this bound polices, as a named constant per this
# ticket's brief ("never a literal scattered across the file"), so
# ComplexityBudgetExtension's validation rule and its own error message
# always agree on which field they are counting.
RUN_CREATING_FIELD_NAME = "ask"

# Bounds the WHOLE GraphQL operation, independent of fold.py's own
# `_FOLD_LOOP_TIMEOUT_S` (240.0s, the harness's published worst case for one
# full Guardrail->Think->Plan->Act->Write loop). Strawberry ships no
# request-level timeout of its own (tool-call-budgets.md: a call path
# without a declared timeout is not finished). Set 30s above fold.py's own
# bound so, in the common case, fold_run's own more specific
# FoldTimeoutError fires and is disclosed by name before this coarser
# whole-operation bound would trigger; this bound exists as the backstop
# for any future resolver on this surface that does not already carry its
# own timeout, not to race the one resolver that does.
REQUEST_TIMEOUT_S = 270.0

# The GraphQLError.extensions["code"] this surface's RequestTimeoutExtension
# and MaskErrors's allowlist path use, named once so both agree.
_REQUEST_TIMEOUT_CODE = "REQUEST_TIMEOUT"
_TOO_MANY_RUN_CREATING_FIELDS_CODE = "TOO_MANY_RUN_CREATING_FIELDS"

# The generic message MaskErrors substitutes for a masked (non-allowlisted)
# error. Never varies per exception, by design: a message that varied with
# the masked exception's own text would just be a slower way of leaking it.
_MASKED_ERROR_MESSAGE = "This request could not be completed due to an internal error."

# ---------------------------------------------------------------------------
# The allowlist. `_should_mask_error` is MaskErrors's `should_mask_error`
# callback: it returns True (mask) for anything that is not a deliberate,
# already-reviewed application exception raised by this surface's own code,
# and False (do not mask) for one that is.
# ---------------------------------------------------------------------------

# The marker an exception must CARRY to be disclosed. Trust is declared by
# the exception class itself, never inferred from where the class happens to
# be defined.
#
# REPLACED a package-origin check at the fix round for build phase 4.3
# (finding F-4.3-A-12, critical). The old rule read `type(exc).__module__`
# and disclosed anything defined anywhere under this package. An adversary
# built a class with `__module__` set to a module in this package and got
# back, verbatim: a DSN with its password, the host, the port, the database
# user, an absolute source path and a line number. An identical
# `RuntimeError` with the identical message was correctly masked. Only the
# package differed.
#
# The lead had filed that risk as MINOR and "safe as it stands". That was
# wrong in the direction that matters: the rule failed OPEN on the
# disclosure axis, in a repository whose own F-4.1-A-09 was a live database
# host, port and username reaching a caller through a field assumed safe. It
# was not fully safe at rest either, since `types.py`'s
# `InvalidCitationPayloadError` interpolates a Pydantic `ValidationError`
# whose string embeds the rejected `input_value`; only its call sites
# happened to swallow it, which is a property of those call sites and not of
# this allowlist.
#
# Declaring the marker inverts the default. A new exception added to this
# package in a future phase is MASKED unless its author opts it in, and
# opting in is a visible, reviewable line rather than an accident of file
# placement.
PUBLIC_ERROR_MARKER = "__graphql_public__"

_CAMEL_RUN_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_RUN_2 = re.compile(r"([a-z0-9])([A-Z])")


def _error_code_for(exc: BaseException) -> str:
    """A stable, machine-readable `extensions.code` derived from `exc`'s own
    class name, never from its message (which may vary run to run), and
    never from a maintained per-exception-type mapping: a new safe
    exception type added anywhere under this package automatically gets a
    stable code with nothing to keep in sync, per this ticket's "never a
    literal scattered across the file" instruction applied to error codes
    as much as to the field-name constant above. Example:
    `GraphQLSecurityError` -> `"GRAPH_QL_SECURITY_ERROR"`.
    """
    name = _CAMEL_RUN_1.sub(r"\1_\2", type(exc).__name__)
    name = _CAMEL_RUN_2.sub(r"\1_\2", name)
    return name.upper()


def _is_allowlisted_application_exception(exc: BaseException) -> bool:
    """True only for an exception whose class DECLARES itself caller-safe by
    setting `PUBLIC_ERROR_MARKER` to `True`.

    Declared, never inferred. The marker has to be written on the class, so
    an exception is disclosed because somebody decided it carries no internal
    detail, not because of which file it happens to live in. Everything else,
    including every exception defined in this same package, is masked.

    `getattr` with a `False` default is what makes the default deny: an
    exception that says nothing about itself says "mask me". The `is True`
    comparison is deliberate too, so a truthy-but-unintended attribute value
    cannot open the channel.

    See `PUBLIC_ERROR_MARKER` above for the finding that replaced the old
    package-origin rule (F-4.3-A-12, critical, driven end to end by an
    adversary that recovered a DSN with its password).
    """
    return getattr(type(exc), PUBLIC_ERROR_MARKER, False) is True


def _should_mask_error(error: GraphQLError) -> bool:
    """MaskErrors's `should_mask_error` callback.

    A `GraphQLError` with no `original_error` never wrapped a raised Python
    exception: it was built directly by a validation-phase rule
    (`DisableIntrospection`, `QueryDepthLimiter`, `MaxAliasesLimiter`,
    `MaxTokensLimiter`, `ComplexityBudgetExtension`'s own validation rule)
    or by `RequestTimeoutExtension`'s own short-circuit. None of those carry
    internal exception text; all of them exist to give an actionable,
    already-reviewed reason a document was rejected, so none is masked.

    A `GraphQLError` that DOES wrap a raised Python exception is masked
    UNLESS that exception is one of this surface's own, deliberate,
    safe-to-expose application exceptions (`_is_allowlisted_application_
    exception` above). An allowlisted exception's `extensions["code"]` is
    attached here, as a side effect, before returning `False`: `located_
    error` (graphql-core's own resolver-exception-to-GraphQLError wrapper,
    `graphql/error/located_error.py`) rebuilds a fresh `GraphQLError` from
    `message`/`nodes`/`source`/`positions`/`path`/`original_error` only,
    never forwarding whatever `extensions` a raised `GraphQLError` subclass
    might have carried, so setting `extensions` at construction time on a
    raised exception would silently be lost by the time it reaches this
    callback. Mutating the error object actually delivered here is the one
    point in the pipeline where a code can still be attached and survive:
    `MaskErrors._process_errors` (`strawberry/extensions/mask_errors.py`)
    appends this exact object, unmodified, to the processed list whenever
    this callback returns `False`, so a mutation made here is never
    overwritten afterward.
    """
    original = error.original_error
    if original is None:
        return False
    if not _is_allowlisted_application_exception(original):
        return True
    if error.extensions is None or "code" not in error.extensions:
        error.extensions = {**(error.extensions or {}), "code": _error_code_for(original)}
    return False


# ---------------------------------------------------------------------------
# RequestTimeoutExtension: a per-request wall-clock bound on the whole
# GraphQL operation. Strawberry ships no timeout of its own
# (tool-call-budgets.md: a call path without a declared timeout is not
# finished).
# ---------------------------------------------------------------------------


class RequestTimeoutExtension(SchemaExtension):
    """SUPERSEDED at T-4.3-07 as the ENFORCEMENT point, kept as a second
    layer. Read `enforce_request_timeout` in `router.py` for the mechanism
    that actually bounds a request, and read this note before reinstating
    this one as primary, because the reason it could not be primary is not
    obvious and cost real time to establish.

    This extension bounds `on_execute` with `asyncio.timeout`, which works
    by cancelling the running task. Measured at first assembly: the bound
    FIRED correctly and on time, the `CancelledError` was converted to
    `TimeoutError`, this handler ran, and it set a perfectly good
    short-circuit result. The request then died with `CancelledError`
    anyway. The cancellation had already travelled through graphql-core's
    and Strawberry's execution frames on its way here, and the task it
    poisoned is the same task that must go on to serialize the response, so
    suppressing the error at this one point does not make the task healthy
    again. Adding `Task.uncancel()` did not change it either; both were
    tried and neither worked.

    The durable fix is isolation rather than suppression: `router.py` runs
    the whole GraphQL request in a CHILD task and bounds that with
    `asyncio.wait_for`, so the cancellation is confined to the child, and
    the parent, which was never cancelled, is free to build a clean error
    response. That is the standard shape for this problem and it is the one
    the premise gate's timeout arm now exercises.

    This extension stays in the chain because it is a genuine second layer
    with a different reach: it wraps execution specifically, so it remains
    the bound if the router-level wrapper is ever bypassed. Both read the
    same `REQUEST_TIMEOUT_S`, so they cannot disagree about the deadline.

    Original note, still true of this extension's own mechanics: bounds the
    whole `on_execute` phase (parsing and validation have
    already completed by the time `on_execute` runs) to `REQUEST_TIMEOUT_S`
    seconds, read from the MODULE attribute fresh on every call rather than
    captured once, so a caller (this module's own tests, or any future
    runtime reconfiguration) that reassigns `security_module.REQUEST_
    TIMEOUT_S` changes the bound on the very next request. Referencing the
    bare module-level name `REQUEST_TIMEOUT_S` inside `on_execute`, rather
    than stashing it on `self` in an `__init__`, is what makes this true:
    Python resolves a bare global name from the enclosing module's
    `__dict__` at the moment each statement runs, not at function-definition
    time, so `monkeypatch.setattr(security_module, "REQUEST_TIMEOUT_S",
    ...)` (which mutates that same `__dict__`) is visible here immediately.
    A test that captured the value instead (`self.timeout = REQUEST_TIMEOUT_
    S` in `__init__`) would silently stop responding to that monkeypatch,
    which is this repository's single most repeated failure class per this
    ticket's own dispatch brief.

    On timeout, short-circuits by setting `self.execution_context.result`
    directly (never raising), the same technique `ComplexityBudgetExtension`
    below uses at the validation phase: a `GraphQLExecutionResult` built
    here, with `extensions` set directly on the `GraphQLError` at
    construction, is never routed through `located_error` (that path only
    wraps a raised Python exception), so the code attached here survives
    unmodified all the way to the response.
    """

    async def on_execute(self) -> AsyncIterator[None]:  # type: ignore[override]
        # `CancelledError` is caught alongside `TimeoutError`, and the
        # distinction between the two is made by `cm.expired()`, never by
        # the exception type. This is not defensive noise; it was measured
        # at the first full assembly of this surface (T-4.3-07).
        #
        # What happens on a real timeout: `asyncio.timeout` cancels the
        # running task, the `CancelledError` surfaces at whatever the
        # resolver was awaiting (in the measured case, the run registry's
        # `asyncio.Condition.wait`), and it then travels back up through
        # graphql-core's and Strawberry's own execution frames before being
        # thrown into this generator at the `yield`. Along that path the
        # conversion `asyncio.timeout.__aexit__` normally performs did NOT
        # happen, so a bare `except TimeoutError` never fired and a
        # timed-out request crashed the whole request instead of returning
        # the actionable error below. The BOUND was working; only its
        # reporting was broken, which is the more dangerous half to get
        # wrong, since a crash is what a caller sees.
        #
        # The "was it MY deadline" question is answered by the WALL CLOCK,
        # not by `asyncio.Timeout.expired()`. `expired()` was tried first
        # and did not work here: it reports the context manager's own
        # internal state machine, and that state depends on the cancel
        # being delivered and converted within frames this generator does
        # not control, which is exactly what the round trip through
        # Strawberry's execution machinery breaks. A deadline comparison
        # asks the question directly and depends on nothing.
        #
        # An unrelated cancellation (a client disconnecting mid-request, a
        # server shutting down) arrives BEFORE the deadline and is re-raised
        # untouched, so it is never silently reported to the caller as a
        # timeout that did not happen. A cancellation arriving after the
        # deadline is reported as a timeout, which is true regardless of who
        # issued it.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + REQUEST_TIMEOUT_S
        try:
            async with asyncio.timeout_at(deadline):
                yield
        except (TimeoutError, asyncio.CancelledError):
            if loop.time() < deadline:
                raise
            # Absorbing a cancellation is not just a matter of not
            # re-raising it. Since 3.11 a task counts its pending
            # cancellations, and a coroutine that swallows the
            # `CancelledError` without balancing that count leaves the task
            # still in a cancelling state, so the error simply reappears at
            # the next suspension point and the request dies anyway. That
            # is precisely what was observed here before this call was
            # added: the handler below ran, set a perfectly good result,
            # and the request still failed with `CancelledError`.
            # `asyncio.timeout` calls `uncancel()` itself when its own
            # conversion succeeds; this path is the one where that
            # conversion did not happen, so the balancing is ours to do.
            current_task = asyncio.current_task()
            if current_task is not None:
                current_task.uncancel()
            self.execution_context.result = GraphQLExecutionResult(
                data=None,
                errors=[
                    GraphQLError(
                        f"This GraphQL operation exceeded this surface's "
                        f"{REQUEST_TIMEOUT_S:.0f}s request timeout and was aborted "
                        "before finishing. Retry with a narrower question, or "
                        "select fewer fields.",
                        extensions={"code": _REQUEST_TIMEOUT_CODE},
                    )
                ],
            )


# ---------------------------------------------------------------------------
# ComplexityBudgetExtension: at most MAX_RUN_CREATING_FIELDS_PER_DOCUMENT
# selections of RUN_CREATING_FIELD_NAME per document, enforced at the
# VALIDATION phase (via AddValidationRules), which graphql-core always runs
# strictly before the execution phase, so a violating document is refused
# before any resolver, and therefore before any run, ever runs. Modeled
# directly on the installed MaxAliasesLimiter (strawberry/extensions/
# max_aliases.py), which is the library's own precedent for exactly this
# "count occurrences of X across the whole document, fragments included"
# shape of validation rule.
# ---------------------------------------------------------------------------

_RunCreatingCountableNode = (
    OperationDefinitionNode | FieldNode | InlineFragmentNode | FragmentDefinitionNode
)


def _count_run_creating_fields(
    node: _RunCreatingCountableNode,
    fragments: Mapping[str, FragmentDefinitionNode],
    visited_fragments: frozenset[str] = frozenset(),
) -> int:
    """Count every `FieldNode` literally named `RUN_CREATING_FIELD_NAME`
    anywhere under `node`'s selection set, following inline fragments and
    (once, per fragment name, via `visited_fragments`) fragment spreads, the
    same fragment-aware traversal `MaxAliasesLimiter`'s own `count_fields_
    with_alias` uses. Aliasing a field changes only its OUTPUT key
    (`selection.alias`); the field actually being resolved
    (`selection.name.value`) is unchanged, so an aliased `ask` still counts
    here exactly as an unaliased one does. This is why the bound cannot be
    left to `MaxAliasesLimiter` alone: that limiter's own floor is
    necessarily above one (a legitimate document may alias other fields),
    so it can never itself forbid a SECOND `ask` alias without also
    forbidding ordinary, harmless aliasing of every other field.
    """
    if node.selection_set is None:
        return 0
    total = 0
    for selection in node.selection_set.selections:
        if isinstance(selection, FieldNode):
            if selection.name.value == RUN_CREATING_FIELD_NAME:
                total += 1
            total += _count_run_creating_fields(selection, fragments, visited_fragments)
        elif isinstance(selection, InlineFragmentNode):
            total += _count_run_creating_fields(selection, fragments, visited_fragments)
        elif isinstance(selection, FragmentSpreadNode):
            fragment_name = selection.name.value
            if fragment_name in visited_fragments:
                continue
            fragment = fragments.get(fragment_name)
            if fragment is None:
                continue
            total += _count_run_creating_fields(
                fragment, fragments, visited_fragments | {fragment_name}
            )
    return total


def _create_complexity_budget_validation_rule() -> type[ValidationRule]:
    """Build the `ValidationRule` subclass `ComplexityBudgetExtension`
    registers via `AddValidationRules`, mirroring the installed
    `MaxAliasesLimiter.create_validator`'s own shape exactly (construct-time
    check, `validation_context.report_error` on violation, no execution-time
    component at all).
    """

    class ComplexityBudgetValidationRule(ValidationRule):
        """Reports a validation error when this document selects
        `RUN_CREATING_FIELD_NAME` more than `MAX_RUN_CREATING_FIELDS_PER_
        DOCUMENT` times, counted by `_count_run_creating_fields` above.
        """

        def __init__(self, validation_context: ValidationContext) -> None:
            document = validation_context.document
            fragments = {
                definition.name.value: definition
                for definition in document.definitions
                if isinstance(definition, FragmentDefinitionNode)
            }
            operations = [
                definition
                for definition in document.definitions
                if isinstance(definition, OperationDefinitionNode)
            ]
            total = sum(
                _count_run_creating_fields(operation, fragments) for operation in operations
            )
            if total > MAX_RUN_CREATING_FIELDS_PER_DOCUMENT:
                validation_context.report_error(
                    GraphQLError(
                        f"this document selects {RUN_CREATING_FIELD_NAME!r} "
                        f"{total} time(s) (directly, through an alias, or "
                        "through a spread fragment); at most "
                        f"{MAX_RUN_CREATING_FIELDS_PER_DOCUMENT} is allowed per "
                        "document, because each selection starts a real, "
                        "billed run. Split any additional runs into "
                        "separate requests.",
                        extensions={"code": _TOO_MANY_RUN_CREATING_FIELDS_CODE},
                    )
                )
            super().__init__(validation_context)

    return ComplexityBudgetValidationRule


class ComplexityBudgetExtension(AddValidationRules):
    """At most `MAX_RUN_CREATING_FIELDS_PER_DOCUMENT` selections of
    `RUN_CREATING_FIELD_NAME` per document, enforced before execution.
    """

    def __init__(self) -> None:
        super().__init__([_create_complexity_budget_validation_rule()])


# ---------------------------------------------------------------------------
# The public surface this ticket's module contract requires:
# SCHEMA_EXTENSIONS, ROUTER_SETTINGS, STRAWBERRY_CONFIG.
# ---------------------------------------------------------------------------

# Factories, not instances: see this module's own docstring above for why.
# Order matters for MaskErrors specifically: entering `on_operation` happens
# in list order, exiting happens in REVERSE list order (an ExitStack/
# AsyncExitStack unwind), so an extension listed BEFORE MaskErrors here
# exits AFTER it, meaning RequestTimeoutExtension's and
# ComplexityBudgetExtension's own result-setting has already happened by
# the time MaskErrors does its final masking pass. This is also why
# MaskErrors is listed before the two custom extensions below, matching
# this ticket's own dispatch brief ordering.
SCHEMA_EXTENSIONS: tuple[Callable[[], SchemaExtension], ...] = (
    DisableIntrospection,
    lambda: QueryDepthLimiter(max_depth=MAX_QUERY_DEPTH),
    lambda: MaxAliasesLimiter(max_alias_count=MAX_ALIAS_COUNT),
    lambda: MaxTokensLimiter(max_token_count=MAX_TOKEN_COUNT),
    lambda: MaskErrors(
        should_mask_error=_should_mask_error, error_message=_MASKED_ERROR_MESSAGE
    ),
    RequestTimeoutExtension,
    ComplexityBudgetExtension,
)

# Overrides three `GraphQLRouter` defaults that are wrong for this surface,
# per tracker/phase_4.3.md's "The library, verified against the installed
# version rather than the docs" table. `graphql_ide=None` was confirmed
# against the installed `strawberry.fastapi.GraphQLRouter.__init__` default
# of `'graphiql'`; `allow_queries_via_get=False` against its default of
# `True`; `subscription_protocols=()` against its default of
# `('graphql-transport-ws', 'graphql-ws')`. Off, refused, and empty BY
# DEFAULT, not only under a production environment-variable check: a
# surface hardened only when correctly configured is unhardened.
ROUTER_SETTINGS: dict[str, object] = {
    "graphql_ide": None,
    "allow_queries_via_get": False,
    "subscription_protocols": (),
}

# `disable_field_suggestions=True`: GraphQL's "Did you mean ...?" hint
# enumerates the schema field by field even with introspection fully
# disabled via `DisableIntrospection` above, so disabling introspection
# without this is a locked front door beside an open window. Confirmed
# against the installed `strawberry.schema.config.StrawberryConfig`'s own
# default of `False`.
STRAWBERRY_CONFIG = StrawberryConfig(disable_field_suggestions=True)
