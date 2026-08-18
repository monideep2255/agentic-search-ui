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
        ],
    )
    def test_a_message_reaches_a_caller_only_if_its_shape_was_authored(
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
        # `_disclose_if_message_is_authored`.
        from graphql import GraphQLError

        original: BaseException | None
        if raiser == "graphql":
            original = GraphQLError(message)
        elif raiser == "runtime":
            original = RuntimeError(message)
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
