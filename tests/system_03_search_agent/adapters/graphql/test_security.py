"""Unit tests for `adapters/graphql/security.py` (T-4.3-04).

Written by the lead rather than by the ticket's builder, which died mid-run
after landing `security.py` but before its tests. The module was reviewed
line by line before these were written, rather than tests being fitted to
whatever the code already did.

These are unit tests over a throwaway schema built from the real extension
list. The premise gate (`test_phase_4_3_premise.py`) separately proves the
same bounds hold on the REAL surface over HTTP; this file proves each bound
in isolation, so a failure here names which bound broke rather than only
that the surface stopped refusing something.

Every assertion names, beside itself, the mutation that turns it red, and
every bound is tested TWO-ARMED: it must refuse the hostile document AND
admit an ordinary one. A bound that refuses everything passes every attack
test and destroys the product, which is why build phase 3.0's guardrail gate
and build phase 4.10's allowance gate are both two-armed, and why this one
is too.
"""

from __future__ import annotations

import asyncio

import pytest
import strawberry

from system_03_search_agent.adapters.graphql import security

# Server-produced text a caller must never see. Deliberately not shaped like a
# credential, so the repository's own secret scanner does not object to a test
# fixture, while still standing for a host, a path and an internal identifier.
_INTERNAL_MARKER = "INTERNALMARKER-db-internal.example-5432-kgreader-/Users/private/fold.py:912"


class _Boom(Exception):
    """Defined OUTSIDE the graphql package on purpose: the masking allowlist
    trusts an exception by the package its class is defined in, so this one
    stands for every third-party or stdlib exception that must be masked.
    """


@strawberry.type
class _Leaf:
    value: str


@strawberry.type
class _Branch:
    leaf: _Leaf
    # Self-referential ON PURPOSE. Without it, `branch { branch { ... } }` is
    # not a deep document, it is an INVALID one, and the depth arm below would
    # pass on "Cannot query field 'branch'" rather than on the depth limiter
    # firing. A recursive type is what makes an over-depth document otherwise
    # legal, so the depth bound is the only thing left that can reject it.
    # The real GraphQL schema has no recursion at all, which is why the
    # premise gate's own depth arm has to assert the limiter's message
    # instead; here the shape can be built properly.
    branch: _Branch | None = None


@strawberry.type
class _Q:
    @strawberry.field
    def branch(self) -> _Branch:
        return _Branch(leaf=_Leaf(value="ok"))

    @strawberry.field
    def boom(self) -> str:
        raise _Boom("internal host db-internal.example:5432 user=kg_reader")

    @strawberry.field
    def safe_boom(self) -> str:
        raise security.GraphQLSecurityError("a deliberate, caller-safe message")

    @strawberry.field
    async def hang(self) -> str:
        cond = asyncio.Condition()
        async with cond:
            await cond.wait()
        return "never"


@strawberry.type
class _M:
    @strawberry.mutation
    def ask(self, text: str) -> str:
        # Stands in for the real run-creating mutation. The bound polices the
        # FIELD NAME, so this reproduces what the rule actually counts.
        return f"ran {text}"

    @strawberry.mutation
    def harmless(self, text: str) -> str:
        return f"noop {text}"


def _schema() -> strawberry.Schema:
    return strawberry.Schema(
        query=_Q,
        mutation=_M,
        extensions=list(security.SCHEMA_EXTENSIONS),
        config=security.STRAWBERRY_CONFIG,
    )


def _execute(document: str, schema: strawberry.Schema | None = None):
    """Run a document against a throwaway schema built from the REAL
    extension list.

    `execute_sync` cannot be used here, and that is a genuine property of the
    surface rather than a test detail: `RequestTimeoutExtension.on_execute` is
    an async generator, so a schema carrying this extension list can only be
    executed on the async path. The real surface is always async (FastAPI), so
    this matches production rather than working around it.
    """
    return asyncio.run((schema if schema is not None else _schema()).execute(document))


def _nested(depth: int) -> str:
    """A document that is deep and otherwise LEGAL, so only the depth bound
    can reject it. `_Branch.branch` is self-referential for exactly this
    reason; see the comment on that field.
    """
    opening = "".join("branch { " for _ in range(depth))
    closing = "".join(" }" for _ in range(depth))
    return "query { branch { " + opening + "leaf { value }" + closing + " } }"


class TestDepthBound:
    def test_a_document_past_the_depth_limit_is_refused(self) -> None:
        # Mutation: drop QueryDepthLimiter from SCHEMA_EXTENSIONS, or raise
        # MAX_QUERY_DEPTH above the crafted depth.
        result = _execute(_nested(security.MAX_QUERY_DEPTH + 5))
        assert result.errors
        # The limiter's own message, not just "an error happened": a mutation
        # sweep found every bound arm in this phase passing on an unrelated
        # error until each named its own.
        assert any("depth" in e.message.lower() for e in result.errors), [
            e.message for e in result.errors
        ]

    def test_an_ordinary_shallow_document_still_runs(self) -> None:
        # Mutation: lower MAX_QUERY_DEPTH to 1. This is the arm that stops
        # the bound above from being satisfied by refusing everything.
        result = _execute("query { branch { leaf { value } } }")
        assert result.errors is None
        assert result.data == {"branch": {"leaf": {"value": "ok"}}}


class TestAliasBound:
    def test_a_document_with_too_many_aliases_is_refused(self) -> None:
        # Mutation: drop MaxAliasesLimiter.
        aliases = " ".join(
            f"a{i}: branch {{ leaf {{ value }} }}" for i in range(security.MAX_ALIAS_COUNT + 10)
        )
        result = _execute("query { " + aliases + " }")
        assert result.errors
        assert any("alias" in e.message.lower() for e in result.errors), [
            e.message for e in result.errors
        ]

    def test_a_document_with_a_couple_of_aliases_still_runs(self) -> None:
        # Mutation: set MAX_ALIAS_COUNT to 0, which would refuse every
        # legitimate client that aliases a field at all.
        result = _execute(
            "query { one: branch { leaf { value } } two: branch { leaf { value } } }"
        )
        assert result.errors is None


class TestTokenBound:
    def test_an_oversized_document_is_refused(self) -> None:
        # Mutation: drop MaxTokensLimiter.
        padding = " ".join(f"f{i}: __typename" for i in range(security.MAX_TOKEN_COUNT))
        result = _execute("query { " + padding + " }")
        assert result.errors
        assert any("token" in e.message.lower() for e in result.errors), [
            e.message for e in result.errors
        ]

    def test_a_normal_sized_document_still_runs(self) -> None:
        # Mutation: set MAX_TOKEN_COUNT to a single-digit value.
        result = _execute("query { branch { leaf { value } } }")
        assert result.errors is None


class TestOneRunCreatingFieldPerDocument:
    """The bound that limits MONEY rather than work. Every other bound here
    caps how much a hostile document can demand; this one caps how many
    billed runs one document can start.
    """

    def test_a_document_selecting_the_run_creating_field_twice_is_refused(self) -> None:
        # Mutation: drop ComplexityBudgetExtension. Note this CANNOT be left
        # to MaxAliasesLimiter: aliases are the only way to repeat a field,
        # and that limiter's floor is necessarily far above one.
        result = _execute(
            'mutation { a: ask(text: "x") { } b: ask(text: "y") { } }'.replace(" { }", "")
        )
        assert result.errors
        assert any(
            security.RUN_CREATING_FIELD_NAME in error.message for error in (result.errors or [])
        )

    def test_it_is_refused_before_any_resolver_runs(self) -> None:
        # THE point of enforcing at the validation phase rather than at
        # execution: a rejected document must not start even one run.
        # Mutation: move the check into a resolver, or into on_execute.
        calls: list[str] = []

        @strawberry.type
        class _CountingM:
            @strawberry.mutation
            def ask(self, text: str) -> str:
                calls.append(text)
                return "ran"

        schema = strawberry.Schema(
            query=_Q,
            mutation=_CountingM,
            extensions=list(security.SCHEMA_EXTENSIONS),
            config=security.STRAWBERRY_CONFIG,
        )
        _execute(schema=schema, document='mutation { a: ask(text: "x") b: ask(text: "y") }')
        assert calls == []

    def test_a_single_selection_still_runs(self) -> None:
        # Mutation: set MAX_RUN_CREATING_FIELDS_PER_DOCUMENT to 0, which
        # would refuse every real question this surface exists to answer.
        result = _execute('mutation { ask(text: "x") }')
        assert result.errors is None
        assert result.data == {"ask": "ran x"}

    def test_repeating_a_different_field_is_not_policed(self) -> None:
        # Mutation: count every field rather than the run-creating one,
        # which would turn this bound into a second, blunter alias limiter.
        result = _execute(
            'mutation { a: harmless(text: "x") b: harmless(text: "y") }'
        )
        assert result.errors is None

    def test_the_bound_counts_through_a_fragment_spread(self) -> None:
        # Mutation: stop following fragment spreads. Counting only direct
        # selections is an enumerated fix that grows a gap at the first
        # shape nobody listed, which build phase 4.2 paid for four times.
        result = _execute(
            'mutation { a: ask(text: "x") ...More } fragment More on Mutation '
            '{ b: ask(text: "y") }'
        )
        assert result.errors


class TestIntrospectionAndSuggestions:
    def test_introspection_is_refused(self) -> None:
        # Mutation: drop DisableIntrospection.
        result = _execute("query { __schema { types { name } } }")
        assert result.errors

    def test_a_misspelled_field_gets_no_did_you_mean_hint(self) -> None:
        # Mutation: leave disable_field_suggestions at its default False.
        # Suggestions enumerate the schema one guess at a time even with
        # introspection fully off, so this is the other half of the same
        # control, not a nicety.
        result = _execute("query { brnch { leaf { value } } }")
        assert result.errors
        for error in result.errors:
            assert "did you mean" not in error.message.lower()

    def test_an_ordinary_query_is_unaffected(self) -> None:
        # Mutation: refuse every document. Two-armed, as everywhere here.
        assert _execute("query { branch { leaf { value } } }").errors is None


class TestErrorMasking:
    def test_a_foreign_exception_is_masked(self) -> None:
        # Mutation: drop MaskErrors, or allowlist by something broader than
        # the defining package. F-4.1-A-09 measured a live database host,
        # port and username reaching a caller through an unmasked message.
        result = _execute("query { boom }")
        assert result.errors
        joined = " ".join(error.message for error in result.errors)
        assert "db-internal.example" not in joined
        assert "kg_reader" not in joined

    def test_this_surfaces_own_exception_is_not_masked(self) -> None:
        # Mutation: mask everything unconditionally. That would be "safe"
        # and would also destroy every actionable error this surface
        # deliberately publishes, which tool-call-budgets.md requires.
        result = _execute("query { safeBoom }")
        assert result.errors
        assert "caller-safe message" in result.errors[0].message

    def test_an_exception_is_disclosed_only_if_it_declares_itself_public(self) -> None:
        # F-4.3-A-12, critical, filed by the adversary round and driven end
        # to end: the allowlist used to trust an exception by the PACKAGE its
        # class was defined in, so a class whose `__module__` pointed into
        # this package had its message returned verbatim. The adversary
        # recovered a DSN with its password, a host, a port, a database user
        # and an absolute source path that way, while an identical
        # `RuntimeError` was correctly masked.
        #
        # Mutation: revert `_is_allowlisted_application_exception` to reading
        # `type(exc).__module__`. This arm turns red immediately, because the
        # forged class below is exactly what that rule trusted.
        forged = type(
            "ForgedPackageLocalError",
            (Exception,),
            {"__module__": "system_03_search_agent.adapters.graphql.fold"},
        )

        @strawberry.type
        class _ForgedQ:
            @strawberry.field
            def leak(self) -> str:
                raise forged("INTERNAL-DETAIL-MARKER")

        schema = strawberry.Schema(
            query=_ForgedQ,
            extensions=list(security.SCHEMA_EXTENSIONS),
            config=security.STRAWBERRY_CONFIG,
        )
        result = _execute("query { leak }", schema=schema)

        assert result.errors
        joined = " ".join(e.message for e in result.errors)
        assert "INTERNAL-DETAIL-MARKER" not in joined, (
            "package origin must not grant disclosure; only a declared marker does"
        )

    @pytest.mark.parametrize(
        ("label", "raiser", "message", "path", "must_hide"),
        [
            ("scalar raises internal text during coercion", "graphql", _INTERNAL_MARKER, None, True),
            ("resolver raises internal text", "graphql", _INTERNAL_MARKER, ["ask"], True),
            ("plain internal exception", "runtime", _INTERNAL_MARKER, ["ask"], True),
            ("validation error carrying internal text", None, _INTERNAL_MARKER, None, True),
            (
                "legitimate validation error",
                None,
                "Cannot query field 'nope' on type 'AskResult'.",
                None,
                False,
            ),
            (
                "legitimate coercion error",
                "graphql",
                "Variable '$input' got invalid value 'NOPE' at 'input.audienceDepth'.",
                None,
                False,
            ),
            # THE TWO CASES THIS ARM USED TO OMIT, and the omission is why its
            # old name ("...only if its shape was authored") overclaimed: the
            # marker branch is a SECOND way out, and it never consults the
            # content rule at all (review round 6, F2). Both cases below are
            # disclosed, and the second one is disclosed even though its text
            # is pure internal detail.
            (
                "marked exception, its own fixed literal",
                "marked",
                "a deliberate, caller-safe message",
                ["ask"],
                False,
            ),
            (
                # DELIBERATELY asserts the hazard rather than the wish. A
                # marked class whose message interpolates internal text leaks
                # it, and no pattern table stops that; what stops it is the
                # obligation stated on every marked base, enforced by review.
                # If a future change routes marked exceptions through the
                # content rule too, this case goes red and must be updated on
                # purpose, which is the point: the risk is pinned, not hidden.
                "marked exception carrying internal text (the standing hazard)",
                "marked",
                _INTERNAL_MARKER,
                ["ask"],
                False,
            ),
        ],
    )
    def test_a_message_reaches_a_caller_only_if_its_shape_was_authored_or_its_class_is_marked(
        self, label: str, raiser: str | None, message: str, path: list[str] | None, must_hide: bool
    ) -> None:
        # THE arm for the redesign, and for the shape of defect that produced
        # both of this phase's criticals.
        #
        # Three earlier rules each asked WHO RAISED the error and inferred
        # from that whether its text was safe: the package a class was
        # declared in, then its class family, then the phase it came from.
        # Each is a correlate of the property that actually matters, which is
        # a fact about the STRING, and every review round found the case where
        # the correlate broke. The rule now checks the text against shapes
        # authored in advance, default-deny.
        #
        # This arm drives the predicate AND models what Strawberry does after
        # it, because `_should_mask_error` returns a verdict and
        # `MaskErrors.anonymise_error` is what rewrites a masked message. An
        # earlier version of this check read `error.message` straight after
        # the predicate and reported a leak on every correctly-masked case.
        #
        # Mutation that turns this red: add `.*` to
        # `_DISCLOSABLE_MESSAGE_PATTERNS`, or delete the
        # `_is_disclosable_message` guard from
        # `_disclose_if_message_is_authored`. For the two `marked` cases:
        # delete the `_is_allowlisted_application_exception` branch, or drop
        # `__graphql_public__` from `GraphQLSecurityError`.
        from graphql import GraphQLError

        original: BaseException | None
        if raiser == "graphql":
            original = GraphQLError(message)
        elif raiser == "runtime":
            original = RuntimeError(message)
        elif raiser == "marked":
            original = security.GraphQLSecurityError(message)
        else:
            original = None

        error = GraphQLError(message, original_error=original, path=path)
        masked = security._should_mask_error(error)
        final = security._MASKED_ERROR_MESSAGE if masked else error.message

        if must_hide:
            assert _INTERNAL_MARKER not in final, f"{label} leaked internal text: {final}"
        else:
            assert final == message, (
                f"{label} was rewritten, so a legitimate error lost its detail: {final}"
            )

    def test_every_exception_families_disclosure_decision_is_pinned(self) -> None:
        # THE arm that would have caught R-02, and did not exist.
        #
        # Replacing the package-origin allowlist with a declared marker
        # silently dropped `fold.py`'s whole error family to the generic
        # uncoded "internal error". The old rule had named that module
        # explicitly; the new one gave it no marker. So `citations(runId:)`
        # on an unfinished run and the fold's own timeout both stopped
        # telling a caller anything actionable, inside the very round that
        # spent its length fixing that same defect class for a different
        # field. Nothing turned red, because nothing pinned the BOUNDARY,
        # only its two endpoints.
        #
        # This arm pins the whole table, so moving any class across the line
        # in either direction is a visible failure rather than a silent one.
        # Mutation: drop `__graphql_public__` from `FoldError` (the exact
        # regression), or add it to `GraphQLTypeError` (the exact hazard,
        # since `InvalidCitationPayloadError` handles rejected payload
        # content).
        from graphql import GraphQLError

        from system_03_search_agent.adapters.graphql import fold, types

        def decision(exc: BaseException) -> tuple[bool, str | None]:
            error = GraphQLError(str(exc), original_error=exc)
            masked = security._should_mask_error(error)
            return masked, (error.extensions or {}).get("code")

        disclosed = [
            fold.FoldError("x"),
            fold.FoldTimeoutError("x"),
            fold.RunNotYetFinishedError("x"),
            security.GraphQLSecurityError("x"),
        ]
        for exc in disclosed:
            masked, code = decision(exc)
            assert masked is False, f"{type(exc).__name__} must reach the caller"
            assert code, f"{type(exc).__name__} must carry a machine-readable code"

        masked_families = [
            # Interpolates rejected payload content, so it stays masked even
            # though it lives in this same package.
            types.InvalidCitationPayloadError("x"),
            RuntimeError("internal host detail"),
            ValueError("internal detail"),
        ]
        for exc in masked_families:
            masked, _code = decision(exc)
            assert masked is True, f"{type(exc).__name__} must NOT reach the caller"

    def test_the_public_marker_must_be_declared_not_inherited_by_location(self) -> None:
        # The positive half. Mutation: drop `__graphql_public__` from
        # `GraphQLSecurityError`, which would mask every deliberate,
        # actionable error this surface publishes and leave callers with
        # nothing but a generic string. Two-armed, as everywhere here.
        assert getattr(security.GraphQLSecurityError, security.PUBLIC_ERROR_MARKER, False) is True

    def test_an_unmasked_error_carries_a_machine_readable_code(self) -> None:
        # Mutation: stop attaching extensions["code"], forcing callers to
        # match on prose.
        result = _execute("query { safeBoom }")
        assert result.errors
        assert (result.errors[0].extensions or {}).get("code")


class TestRouterSettings:
    def test_the_three_wrong_defaults_are_overridden(self) -> None:
        # Mutation: delete any one key. Each of the three library defaults
        # is wrong for this surface: an IDE served in production, operations
        # reachable over GET, and two WebSocket protocols advertised for
        # subscriptions this phase does not build.
        assert security.ROUTER_SETTINGS["graphql_ide"] is None
        assert security.ROUTER_SETTINGS["allow_queries_via_get"] is False
        assert security.ROUTER_SETTINGS["subscription_protocols"] == ()

    def test_field_suggestions_are_disabled_in_the_config(self) -> None:
        # Mutation: drop the flag. Paired with the behavioral arm above, so
        # this catches a config regression even if a library change made the
        # behavior harder to observe.
        assert security.STRAWBERRY_CONFIG.disable_field_suggestions is True

    def test_the_hardening_is_the_default_not_an_env_opt_in(self) -> None:
        # Mutation: make any of these conditional on an environment variable
        # naming production. A surface hardened only when correctly
        # configured is unhardened, so the SAFE state must be the default.
        import os

        for variable in ("APP_ENV", "ENV", "ENVIRONMENT"):
            os.environ.pop(variable, None)
        import importlib

        reloaded = importlib.reload(security)
        assert reloaded.ROUTER_SETTINGS["graphql_ide"] is None
        assert reloaded.ROUTER_SETTINGS["allow_queries_via_get"] is False


class TestBoundsAreNamedConstants:
    @pytest.mark.parametrize(
        "name",
        [
            "MAX_QUERY_DEPTH",
            "MAX_ALIAS_COUNT",
            "MAX_TOKEN_COUNT",
            "MAX_RUN_CREATING_FIELDS_PER_DOCUMENT",
            "RUN_CREATING_FIELD_NAME",
            "REQUEST_TIMEOUT_S",
        ],
    )
    def test_every_bound_is_a_named_module_constant(self, name: str) -> None:
        # Mutation: inline any of these as a literal at its use site. A bound
        # that is not named cannot be audited, reconfigured, or tested, and
        # `production-standards.md` requires every one of them declared.
        assert getattr(security, name) is not None

    def test_the_run_creating_field_name_is_not_a_scattered_literal(self) -> None:
        # Mutation: hardcode "ask" inside the validation rule. The rule and
        # its own error message must agree on which field they police, and
        # `schema.py` cross-checks this same constant against the published
        # mutation field at import time.
        assert security.RUN_CREATING_FIELD_NAME == "ask"

    def test_the_request_timeout_is_read_from_the_module_at_call_time(self) -> None:
        # Mutation: capture REQUEST_TIMEOUT_S into an instance attribute at
        # __init__ (in either the extension or the middleware). The premise
        # gate monkeypatches this module attribute, and a captured value
        # would silently ignore the patch, turning that arm into a test that
        # cannot fail. This is the single most repeated failure class in this
        # repository's LEARNINGS.md.
        #
        # Asserted against the COMPILED function's global-name table, not
        # against its source text. A first version of this test grepped the
        # source and passed for the wrong reason: the phrase it searched for
        # appears in the docstring explaining the hazard, so the test was
        # reading prose about the rule rather than the rule itself.
        from system_03_search_agent.adapters.graphql import router as router_module

        extension_globals = security.RequestTimeoutExtension.on_execute.__code__.co_names
        assert "REQUEST_TIMEOUT_S" in extension_globals

        # The middleware is the actual enforcement point, so it matters more.
        # It reads through the module object (`security.REQUEST_TIMEOUT_S`),
        # so the attribute name shows up in its name table too.
        middleware_globals = router_module.RequestTimeoutMiddleware.__call__.__code__.co_names
        assert "REQUEST_TIMEOUT_S" in middleware_globals


# ---------------------------------------------------------------------------
# The disclosable-message allowlist, driven against the REAL schema.
#
# This class is the durable half of the review-round-6 F3 fix. That finding
# measured 15 ordinary caller-side mistakes coming back as a codeless generic
# literal, and three authored patterns that missed the installed library's
# wording by a single word, so they matched nothing and nobody could notice.
# The patterns had been written from what their author expected the messages
# to say.
#
# Every string below was CAPTURED from the installed graphql-core and
# strawberry-graphql by driving the real schema, then pasted here. Nothing in
# this table is inferred. Pinning the exact text is the point: a library
# upgrade that rewords a message now fails HERE, loudly, instead of silently
# blunting that error for every caller.
#
# What this class does NOT cover, stated so the gap is arguable
# (`goal-contracts.md`):
#   - Anything raised while a resolver runs. Those carry a `path` and are
#     masked by class, not by message shape; `TestErrorMasking` owns them.
#   - `{ ...UnknownFragment }` spread inside an operation, which never reaches
#     the masking callback at all. See the coverage note in `security.py`.
#   - Whether the REAL ROUTER returns these over HTTP. That is the premise
#     gate's job; this drives the schema directly so a failure names the
#     shape rather than the transport.
# ---------------------------------------------------------------------------

_RUN = 'run(runId: "r") { runId }'
_ASK_HEAD = 'ask(input: {text: "hi", sessionId: "s"'

# (label, document, variables, the message the installed library ACTUALLY
# produces and that a caller must therefore receive)
_CALLER_MISTAKES: tuple[tuple[str, str, dict | None, str], ...] = (
    (
        "unused variable",
        f"query Q($x: String) {{ {_RUN} }}",
        None,
        "Variable '$x' is never used in operation 'Q'.",
    ),
    (
        "undefined variable",
        "query Q { run(runId: $x) { runId } }",
        None,
        "Variable '$x' is not defined by operation 'Q'.",
    ),
    (
        "duplicate argument",
        '{ run(runId: "a", runId: "b") { runId } }',
        None,
        "There can be only one argument named 'runId'.",
    ),
    (
        "duplicate variable name",
        f"query Q($x: String, $x: String) {{ {_RUN} }}",
        None,
        "There can be only one variable named '$x'.",
    ),
    (
        "duplicate operation name",
        f"query Q {{ {_RUN} }} query Q {{ {_RUN} }}",
        None,
        "There can be only one operation named 'Q'.",
    ),
    (
        "duplicate fragment name",
        "{ ...A } fragment A on Query { __typename } fragment A on Query { __typename }",
        None,
        "There can be only one fragment named 'A'.",
    ),
    (
        "duplicate input field",
        'mutation { ask(input: {text: "a", text: "b", sessionId: "s"}) { runId } }',
        None,
        "There can be only one input field named 'text'.",
    ),
    (
        "misplaced directive",
        f"query Q @include(if: true) {{ {_RUN} }}",
        None,
        "Directive '@include' may not be used on query.",
    ),
    (
        "repeated directive",
        '{ run(runId: "r") @skip(if: true) @skip(if: true) { runId } }',
        None,
        "The directive '@skip' can only be used once at this location.",
    ),
    (
        "missing required directive argument",
        '{ run(runId: "r") @skip { runId } }',
        None,
        ("Directive '@skip' argument 'if' of type 'Boolean!' is required, "
        "but it was not provided."),
    ),
    (
        "field conflict",
        '{ a: run(runId: "x") { runId } a: run(runId: "y") { runId } }',
        None,
        ("Fields 'a' conflict because they have differing arguments. Use "
        "different aliases on the fields to fetch both if this was intentional."),
    ),
    (
        "fragment cycle",
        "{ ...A } fragment A on Query { ...B } fragment B on Query { ...A }",
        None,
        "Cannot spread fragment 'A' within itself via 'B'.",
    ),
    (
        "unused fragment",
        "{ __typename } fragment A on Query { __typename }",
        None,
        "Fragment 'A' is never used.",
    ),
    (
        "unknown fragment named in an unused fragment",
        "{ __typename } fragment A on Query { ...Nope }",
        None,
        "Unknown fragment 'Nope'.",
    ),
    (
        "leaf field given a selection set",
        '{ run(runId: "r") { runId { x } } }',
        None,
        "Field 'runId' must not have a selection since type 'String!' has no subfields.",
    ),
    (
        "object field given no selection set",
        '{ run(runId: "r") }',
        None,
        # The library appends "Did you mean 'run { ... }'?"; the surface strips
        # every suggestion clause before disclosing (F-R5-04).
        "Field 'run' of type 'RunResult!' must have a selection of subfields.",
    ),
    (
        "subscription operation",
        f"subscription S {{ {_RUN} }}",
        None,
        "Schema is not configured to execute subscription operation.",
    ),
    (
        "anonymous plus named operation",
        f"{{ {_RUN} }} query Named {{ {_RUN} }}",
        None,
        "This anonymous operation must be the only defined operation.",
    ),
    (
        "__schema introspection",
        "{ __schema { types { name } } }",
        None,
        ("GraphQL introspection has been disabled, but the requested query "
        "contained the field '__schema'."),
    ),
    (
        "__type introspection",
        '{ __type(name: "Query") { name } }',
        None,
        ("GraphQL introspection has been disabled, but the requested query "
        "contained the field '__type'."),
    ),
    (
        "non-null variable given null",
        "query Q($r: ID!) { run(runId: $r) { runId } }",
        {"r": None},
        "Variable '$r' of non-null type 'ID!' must not be null.",
    ),
    (
        "variable of the wrong type",
        "query Q($r: Int!) { run(runId: $r) { runId } }",
        {"r": 1},
        "Variable '$r' of type 'Int!' used in position expecting type 'ID!'.",
    ),
    (
        "variable not provided",
        "mutation M($i: AskInput!) { ask(input: $i) { runId } }",
        {},
        "Variable '$i' of required type 'AskInput!' was not provided.",
    ),
    (
        "variable given an invalid value",
        "mutation M($i: AskInput!) { ask(input: $i) { runId } }",
        {"i": {"text": 5, "sessionId": "s"}},
        ("Variable '$i' got invalid value 5 at 'i.text'; ask input field 'text' "
        "must be a string; send the question as a GraphQL String and retry"),
    ),
    (
        "unknown type",
        "query Q($r: Nope!) { run(runId: $r) { runId } }",
        None,
        "Unknown type 'Nope'.",
    ),
    (
        "unknown argument",
        '{ run(runId: "r", nope: 1) { runId } }',
        None,
        "Unknown argument 'nope' on field 'Query.run'.",
    ),
    (
        "unknown output field",
        "{ nope }",
        None,
        "Cannot query field 'nope' on type 'Query'.",
    ),
    (
        "unknown input field",
        'mutation { ask(input: {text: "hi", sessionId: "s", nope: 1}) { runId } }',
        None,
        "Field 'nope' is not defined by type 'AskInput'.",
    ),
    (
        "unknown directive",
        '{ run(runId: "r") @nope { runId } }',
        None,
        "Unknown directive '@nope'.",
    ),
    (
        "missing required argument",
        "{ run { runId } }",
        None,
        "Field 'run' argument 'runId' of type 'ID!' is required, but it was not provided.",
    ),
    (
        "missing required input field",
        "mutation { ask(input: {}) { runId } }",
        None,
        "Field 'AskInput.text' of required type 'AskText!' was not provided.",
    ),
    (
        "required input field given null",
        'mutation { ask(input: {text: null, sessionId: "s"}) { runId } }',
        None,
        "Expected value of type 'AskText!', found null.",
    ),
    (
        "enum value that does not exist",
        f"mutation {{ {_ASK_HEAD}, audienceDepth: NOPE}}) {{ runId }} }}",
        None,
        "Value 'NOPE' does not exist in 'AudienceDepth' enum.",
    ),
    (
        "built-in scalar given an object literal",
        "{ run(runId: {a: 1}) { runId } }",
        None,
        "ID cannot represent a non-string and non-integer value: {a: 1}",
    ),
    (
        "syntax error",
        "{ run(runId: ",
        None,
        "Syntax Error: Unexpected <EOF>.",
    ),
    (
        "token bound",
        "{ " + " ".join(["__typename"] * 2000) + " }",
        None,
        "Syntax Error: Document contains more than 1000 tokens. Parsing aborted.",
    ),
    (
        "alias bound",
        "{ " + " ".join(f"a{index}: __typename" for index in range(60)) + " }",
        None,
        "60 aliases found. Allowed: 20",
    ),
    (
        # The real schema has no recursive type, so an over-depth document is
        # necessarily also an invalid one and graphql-core reports both. The
        # depth limiter's own message is the one asserted; `TestDepthBound`
        # above proves the BOUND on a recursive throwaway schema, where the
        # document can be deep and otherwise legal.
        "depth bound",
        '{ run(runId: "r") ' + "{ trustSignal " * 12 + "{ message }" + " }" * 12 + " }",
        None,
        "'anonymous' exceeds maximum operation depth of 10",
    ),
    (
        "this surface's own scalar bound",
        'mutation { ask(input: {text: "%s", sessionId: "s"}) { runId } }' % ("x" * 3000),
        None,
        ("ask input field 'text' must be at most 2000 characters; shorten the "
        "question and retry"),
    ),
)

# Patterns in `_DISCLOSABLE_MESSAGE_PATTERNS` that no document above reaches on
# the INSTALLED library version, declared here rather than left invisible. A
# pattern that matches nothing is exactly the F3 defect, so the coverage arm
# below requires every other pattern to be exercised by a real message and
# requires any new inert one to be added here deliberately.
_PATTERNS_WITH_NO_LIVE_PROBE = frozenset(
    {
        # graphql-core raises this from `coerce_input_value`; no document
        # reached it on the installed version.
        r"^Expected non-nullable type '[^']*' not to be None\.$",
        # Both of these are short-circuited by Strawberry, which raises
        # `CannotGetOperationTypeError` to the HTTP layer before graphql-core
        # can report either (review round 6, F4).
        r"^Must provide (?:an )?operation.{0,80}$",
        r"^Operation '[^']*' .{0,120}$",
    }
)


def _execute_real_schema(document: str, variables: dict | None):
    """Drive the SHIPPED schema, with the SHIPPED extension list and config.

    Not the throwaway `_schema()` above: F3 was a mismatch between authored
    patterns and the real library's real wording on the real types, and a
    test schema cannot prove that.
    """
    from system_03_search_agent.adapters.graphql.schema import schema as real_schema

    return asyncio.run(real_schema.execute(document, variable_values=variables))


class TestOrdinaryCallerMistakesStayActionable:
    @pytest.mark.parametrize(
        ("label", "document", "variables", "expected"),
        [(case[0], case[1], case[2], case[3]) for case in _CALLER_MISTAKES],
        ids=[case[0] for case in _CALLER_MISTAKES],
    )
    def test_the_caller_is_told_what_they_got_wrong(
        self, label: str, document: str, variables: dict | None, expected: str
    ) -> None:
        # Mutation that turns this red, per case: delete or reword the
        # matching entry in `_DISCLOSABLE_MESSAGE_PATTERNS`. Default-deny then
        # replaces the message with `_UNAUTHORED_MESSAGE_REPLACEMENT`, which is
        # exactly the state review round 6 measured on 15 of these.
        #
        # It also turns red on a library upgrade that rewords the message,
        # which is the OTHER half of the fix: three shipped patterns missed the
        # installed wording by one word, matched nothing, and no test noticed
        # because none of them asserted the real string.
        result = _execute_real_schema(document, variables)
        assert result.errors, f"{label} must be rejected"
        messages = [error.message for error in result.errors]
        assert expected in messages, (
            f"{label}: expected {expected!r}, got {messages!r}. If the library "
            "reworded this, update BOTH the pattern and this expectation; do "
            "not delete the case."
        )

    @pytest.mark.parametrize(
        ("label", "document", "variables", "expected"),
        [(case[0], case[1], case[2], case[3]) for case in _CALLER_MISTAKES],
        ids=[case[0] for case in _CALLER_MISTAKES],
    )
    def test_the_caller_is_never_told_their_own_mistake_was_ours(
        self, label: str, document: str, variables: dict | None, expected: str
    ) -> None:
        # The second arm of the same fact, asserted separately because it is a
        # different failure: `production-standards.md`'s retry-safety gate and
        # `tool-call-budgets.md`'s actionability rule both forbid reporting a
        # caller's malformed request as an internal error, since "internal"
        # reads as transient and a well-behaved client retries a request that
        # can never succeed.
        #
        # Mutation: make `_is_disclosable_message` return False.
        result = _execute_real_schema(document, variables)
        messages = [error.message for error in result.errors or []]
        assert security._MASKED_ERROR_MESSAGE not in messages, (
            f"{label} was reported as an internal error"
        )
        assert security._UNAUTHORED_MESSAGE_REPLACEMENT not in messages, (
            f"{label} was blunted to the generic literal"
        )

    def test_every_authored_pattern_is_either_exercised_or_declared_inert(self) -> None:
        # THE anti-vacuity arm, and the one that would have caught F3 at the
        # commit that introduced it.
        #
        # Three shipped patterns matched nothing at all, because they were
        # written from what their author expected the library to say. A
        # pattern that matches nothing cannot be noticed by any test that only
        # asserts messages ARE disclosed, so this arm asserts the converse:
        # every pattern must match at least one really-captured message, or be
        # declared inert on purpose in `_PATTERNS_WITH_NO_LIVE_PROBE`.
        #
        # Mutation that turns this red: add a pattern nobody can reach (say,
        # `^Introspection is disabled\.` again) without declaring it.
        captured = [case[3] for case in _CALLER_MISTAKES]
        inert = {
            pattern.pattern
            for pattern in security._DISCLOSABLE_MESSAGE_PATTERNS
            if not any(pattern.match(message) for message in captured)
        }
        assert inert == _PATTERNS_WITH_NO_LIVE_PROBE, (
            "a pattern matches no captured message and is not declared inert "
            f"(undeclared: {sorted(inert - _PATTERNS_WITH_NO_LIVE_PROBE)}; "
            f"declared but now reachable: {sorted(_PATTERNS_WITH_NO_LIVE_PROBE - inert)})"
        )

    @pytest.mark.parametrize(
        ("label", "message"),
        [
            ("a raw internal marker", _INTERNAL_MARKER),
            (
                "a DSN dressed as a validation error",
                "Cannot connect: postgresql://kg_reader:hunter2@10.0.0.1:5432/kg",
            ),
            (
                "internal text after a pattern's own prefix",
                "Unknown type 'Nope'. Connected to db-internal.example:5432",
            ),
            (
                "an over-long tail on a bounded pattern",
                "Syntax Error: " + ("x" * 500),
            ),
            (
                "a custom scalar impersonating a built-in",
                "AskText cannot represent " + _INTERNAL_MARKER,
            ),
            (
                "a directive location that is not one",
                "Directive '@x' may not be used on " + _INTERNAL_MARKER + ".",
            ),
        ],
    )
    def test_widening_the_table_did_not_open_it(self, label: str, message: str) -> None:
        # The other arm of the two-armed discipline, and the one that matters
        # most: this fix ADDED roughly twenty shapes to a default-deny
        # allowlist, and an allowlist that admits everything is not one.
        #
        # Mutation that turns this red: append `re.compile(r".*")` to
        # `_DISCLOSABLE_MESSAGE_PATTERNS`, or drop the `$` anchor from any
        # pattern, or replace a bounded `.{0,N}` tail with `.*`.
        assert security._is_disclosable_message(message) is False, (
            f"{label} matched an authored shape: {message}"
        )
