"""Unit tests for the CLI renderer (build phase 4.2, ticket T-4.2-04).

Exercises `system_03_search_agent.adapters.cli.render.Renderer` and
`render_client_error` directly, against hand-built `Event` envelopes, per
Section 13.3's ten rendering rules. This is the ticket's OWN verify
surface, distinct from `tests/system_03_search_agent/adapters/cli/
test_phase_4_2_premise.py` (T-4.2-01's premise gate, not owned by this
ticket and not run from here): that file drives the real `main()` entry
point end to end and needs `credentials.py`, `client.py`, and `main.py` to
exist, none of which this ticket builds. This file needs only `render.py`
and the `Event`/payload models `contracts/events.py` already ships, so it
can run standalone against just this ticket's own deliverable.

Depends on:
    - system_03_search_agent.adapters.cli.render (Renderer, render_client_error)
    - system_03_search_agent.contracts.events (Event and the Section 2.3 payload models)
"""

from __future__ import annotations

import io
from datetime import UTC, datetime

import httpx
import pytest

from system_03_search_agent.adapters.cli.render import Renderer, render_client_error
from system_03_search_agent.contracts.events import (
    CitationPayload,
    CostPayload,
    DonePayload,
    ErrorPayload,
    Event,
    GuardPayload,
    PlanPayload,
    ThinkPayload,
    TokenPayload,
    ToolCall,
    ToolResultPayload,
    ToolStartPayload,
    TrustSignalPayload,
)

_TRACE_ID = "trace-1"


def _event(event_type: str, seq: int, payload) -> Event:
    return Event(
        type=event_type,  # type: ignore[arg-type]
        version="v1",
        trace_id=_TRACE_ID,
        seq=seq,
        ts=datetime.now(UTC),
        payload=payload.model_dump(),
    )


def _citation(citation_id: str, display_index: int) -> CitationPayload:
    return CitationPayload(
        citation_id=citation_id,
        display_index=display_index,
        source="ncbi_gene",
        source_id="672",
        source_url="https://www.ncbi.nlm.nih.gov/gene/672",
        layer="layer_1_graph",
        field="symbol",
        claim_text="BRCA1 is a protein-coding gene.",
        evidence_kind="direct",
        assertion_confidence="high",
        population_ancestry_context=None,
        license="public-domain",
    )


def _guard_passed() -> Event:
    return _event("guard", 0, GuardPayload(passed=True, category="ok", reason=None))


def _feed_golden_path(renderer: Renderer) -> None:
    renderer.handle(_guard_passed())
    renderer.handle(
        _event(
            "think", 1,
            ThinkPayload(
                narrative="classified as a single-hop lookup", query_class="single_hop",
                resolved_entities=[], clarifying_question=None,
            ),
        )
    )
    renderer.handle(
        _event(
            "plan", 2,
            PlanPayload(
                narrative="dispatch cypher_query",
                tool_calls=[ToolCall(tool="cypher_query", call_id="call-1", layer="layer_1_graph")],
            ),
        )
    )
    renderer.handle(
        _event(
            "tool_start", 3,
            ToolStartPayload(call_id="call-1", tool="cypher_query", layer="layer_1_graph", status="ok"),
        )
    )
    renderer.handle(
        _event(
            "tool_result", 4,
            ToolResultPayload(
                call_id="call-1", tool="cypher_query", layer="layer_1_graph", status="ok",
                summary="found 1 row", result_count=1, truncated=False,
            ),
        )
    )
    renderer.handle(
        _event("token", 5, TokenPayload(text="BRCA1 is a protein-coding gene [1]. ", marker_ids=["c1"]))
    )
    renderer.handle(_event("citation", 6, _citation("c1", 1)))
    renderer.handle(
        _event(
            "trust_signal", 7,
            TrustSignalPayload(
                outcome="answer", risk_tier="low", grounded=True, triangulated=None,
                citation_id="c1", scope="claim",
            ),
        )
    )
    renderer.handle(
        _event(
            "trust_signal", 8,
            TrustSignalPayload(
                outcome="answer", risk_tier="low", grounded=True, triangulated=None,
                citation_id=None, scope="answer",
            ),
        )
    )
    renderer.handle(
        _event("cost", 9, CostPayload(query_cost_usd=0.0123, query_cap_usd=1.0, cap_fraction=0.0123, model_tier="synth"))
    )
    renderer.handle(
        _event("done", 10, DonePayload(total_cost_usd=0.0123, total_tool_calls=1, elapsed_ms=120, trust_outcome="answer"))
    )


class TestGoldenPath:
    def test_golden_path_answer_streams_to_stdout_with_references_and_exits_0(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)

        _feed_golden_path(renderer)
        exit_code = renderer.finish()

        assert exit_code == 0
        rendered = out.getvalue()
        assert "BRCA1 is a protein-coding gene [1]." in rendered
        assert "[answer]" in rendered
        assert "ncbi_gene" in rendered
        assert "https://www.ncbi.nlm.nih.gov/gene/672" in rendered

    def test_status_lines_never_reach_stdout_only_answer_and_references_do(self) -> None:
        """Constraint 1: `s3 ask "..." > answer.txt` must put the answer
        and its references in the file and every status line on the
        terminal. Captured as two SEPARATE streams, never one combined
        buffer, so a status line leaking onto stdout cannot hide behind a
        stray substring match against a merged log."""
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)

        _feed_golden_path(renderer)
        renderer.finish()

        stdout_text = out.getvalue()
        stderr_text = err.getvalue()
        # Mutation: write a think/plan/tool status line to `self._out`
        # instead of `self._err` -> one of these would appear in stdout.
        for status_fragment in ("[think]", "[plan]", "[tool]"):
            assert status_fragment not in stdout_text
        # Mutation: write the answer body or references to stderr instead
        # of stdout -> these would appear in stderr.
        assert "BRCA1 is a protein-coding gene" not in stderr_text
        assert "ncbi_gene" not in stderr_text
        # And the status lines DO land somewhere (stderr), proving the
        # split is a real routing decision, not just an absence on stdout.
        assert "[think]" in stderr_text
        assert "[plan]" in stderr_text
        assert "[tool]" in stderr_text


class TestRefusalPath:
    def test_a_zero_retrieval_run_prints_the_honest_refusal_and_exits_nonzero(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)

        renderer.handle(_guard_passed())
        renderer.handle(
            _event(
                "token", 1,
                TokenPayload(text="I could not find information on this in the available sources. ", marker_ids=[]),
            )
        )
        renderer.handle(
            _event(
                "trust_signal", 2,
                TrustSignalPayload(
                    outcome="refuse", risk_tier="low", grounded=False, triangulated=None,
                    citation_id=None, scope="answer",
                    message="No groundable citation was found for this query.",
                    fallback_link="https://www.ncbi.nlm.nih.gov/gene/",
                ),
            )
        )
        renderer.handle(
            _event("done", 3, DonePayload(total_cost_usd=0.005, total_tool_calls=1, elapsed_ms=90, trust_outcome="refuse"))
        )
        exit_code = renderer.finish()

        assert exit_code != 0
        rendered = out.getvalue()
        assert "[refuse]" in rendered
        assert "I could not find information on this" in rendered
        # Mutation: render an empty references block as if complete, or
        # fabricate a citation to fill it -> "ncbi_gene" or "672" would
        # appear despite no citation event ever being sent.
        assert "ncbi_gene" not in rendered
        assert "672" not in rendered

    def test_flag_and_ask_outcomes_still_count_as_a_delivered_answer_and_exit_0(self) -> None:
        """`answer` and `refuse` are the only two outcomes the premise
        gate directly tests. `flag` and `ask` both still carry generated
        answer text (Section 8.3.3: only a failed grounding check
        refuses), so this asserts the deliberate design choice that only
        `refuse` is treated as "no answer delivered" for exit-code
        purposes."""
        for outcome in ("flag", "ask"):
            out, err = io.StringIO(), io.StringIO()
            renderer = Renderer(out, err, operator=False)
            renderer.handle(_guard_passed())
            renderer.handle(TokenPayloadEventBuilder.token("a caveated answer. "))
            renderer.handle(
                _event(
                    "trust_signal", 2,
                    TrustSignalPayload(
                        outcome=outcome, risk_tier="high", grounded=True, triangulated=False,
                        citation_id=None, scope="answer",
                    ),
                )
            )
            renderer.handle(
                _event("done", 3, DonePayload(total_cost_usd=0.01, total_tool_calls=1, elapsed_ms=90, trust_outcome=outcome))
            )
            assert renderer.finish() == 0, f"outcome={outcome!r} should still exit 0"
            assert f"[{outcome}]" in out.getvalue()


class TokenPayloadEventBuilder:
    """Tiny local helper so `test_flag_and_ask_outcomes...` above does not
    repeat the seq-1 token event construction inline."""

    @staticmethod
    def token(text: str) -> Event:
        return _event("token", 1, TokenPayload(text=text, marker_ids=[]))


class TestGuardRejected:
    def test_a_guard_rejection_prints_to_stderr_only_and_exits_nonzero(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)

        renderer.handle(
            _event("guard", 0, GuardPayload(passed=False, category="off_topic", reason="not biomedical"))
        )
        exit_code = renderer.finish()

        assert exit_code != 0
        assert out.getvalue() == ""
        assert "biomedical research" in err.getvalue()
        # Mutation: interpolate the raw `guard.reason` model text directly
        # instead of the fixed category copy -> the exact string
        # "not biomedical" would appear verbatim.
        assert "not biomedical" not in err.getvalue()

    def test_every_guard_category_has_copy_and_none_of_it_leaks_to_stdout(self) -> None:
        for category in (
            "off_topic", "medical_advice", "injection", "rate_limited", "cost_capped", "write_seeking",
        ):
            out, err = io.StringIO(), io.StringIO()
            renderer = Renderer(out, err, operator=False)
            renderer.handle(_event("guard", 0, GuardPayload(passed=False, category=category, reason=None)))
            assert renderer.finish() != 0
            assert err.getvalue().strip() != "", f"category={category!r} produced no copy"
            assert out.getvalue() == ""


class TestErrorEvents:
    def test_a_fatal_error_prints_a_sanitized_literal_never_the_raw_message(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)

        renderer.handle(
            _event(
                "error", 1,
                ErrorPayload(
                    fatal=True, scope="run", source="write",
                    error_class="unexpected", message="psycopg2 connect failed: host=10.0.0.7 dbname=kg",
                    retry_after_s=0,
                ),
            )
        )
        exit_code = renderer.finish()

        assert exit_code != 0
        rendered = err.getvalue()
        assert "failed unexpectedly" in rendered
        # Mutation: interpolate `error.message` directly instead of the
        # fixed error_class literal -> the leaked host/dbname string would
        # appear verbatim (the exact F-4.1-A-09 failure mode this ticket's
        # constraints name).
        assert "10.0.0.7" not in rendered
        assert "psycopg2" not in rendered

    def test_a_non_fatal_transient_error_does_not_force_a_nonzero_exit(self) -> None:
        """Section 13.3: a non-fatal error whose error_class is transient
        or recoverable does not exit; the retry policy gets its chance
        first. Proven here by following it with a normal successful
        `done` and asserting the earlier non-fatal error did not poison
        the final exit code."""
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)

        renderer.handle(_guard_passed())
        renderer.handle(
            _event(
                "error", 1,
                ErrorPayload(
                    fatal=False, scope="tool", source="ncbi_efetch",
                    error_class="transient", message="upstream 503", retry_after_s=2,
                ),
            )
        )
        renderer.handle(TokenPayloadEventBuilder.token("BRCA1 is a protein-coding gene. "))
        renderer.handle(
            _event(
                "trust_signal", 2,
                TrustSignalPayload(
                    outcome="answer", risk_tier="low", grounded=True, triangulated=None,
                    citation_id=None, scope="answer",
                ),
            )
        )
        renderer.handle(
            _event("done", 3, DonePayload(total_cost_usd=0.01, total_tool_calls=1, elapsed_ms=90, trust_outcome="answer"))
        )

        assert renderer.finish() == 0
        # Still surfaced, just not fatal: the retry note is visible on
        # stderr for a human tailing the run.
        assert "Retry in about 2s" in err.getvalue()

    def test_a_non_fatal_error_with_an_unexpected_or_cancelled_class_still_exits_nonzero(self) -> None:
        """The literal reading of Section 13.3's "unless fatal is false
        AND error_class is transient or recoverable": fatal=False with
        error_class NOT in that pair still exits nonzero."""
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)
        renderer.handle(
            _event(
                "error", 1,
                ErrorPayload(
                    fatal=False, scope="run", source="run_registry",
                    error_class="cancelled", message="stopped by caller", retry_after_s=0,
                ),
            )
        )
        assert renderer.finish() != 0


class TestErrorBodyShapes:
    """`render_client_error`: this ticket's own answer to the "MIXED
    ERROR-BODY SHAPES" constraint, exercised directly against the same
    exception shape an `httpx.AsyncClient` raises from
    `response.raise_for_status()` (`tracker/phase_4.2.md`'s pre-build
    source read on `app.py` error bodies)."""

    @staticmethod
    def _status_error(status_code: int, detail) -> httpx.HTTPStatusError:
        """`detail` is whatever FastAPI's `HTTPException(detail=...)` was
        given: a dict for the structured 429 shape, a bare string for
        401/403/404/409 (`tracker/phase_4.2.md`'s pre-build source read on
        `app.py` error bodies). The real wire body is always `{"detail":
        detail}`, per FastAPI's own exception handler, so this helper
        wraps it the same way rather than handing `render_client_error` an
        unwrapped body no real server response ever actually sends."""
        request = httpx.Request("POST", "http://test/v1/query")
        response = httpx.Response(status_code, json={"detail": detail}, request=request)
        return httpx.HTTPStatusError("refused", request=request, response=response)

    def test_a_structured_429_body_renders_without_crashing_and_is_actionable(self) -> None:
        err = io.StringIO()
        exc = self._status_error(
            429, {"reason": "concurrent_run_cap_exceeded", "message": "wait for an existing run to finish, or stop one"}
        )
        exit_code = render_client_error(err, exc)
        assert exit_code != 0
        assert "wait" in err.getvalue().lower() or "stop" in err.getvalue().lower()

    def test_a_bare_string_401_body_renders_without_crashing(self) -> None:
        err = io.StringIO()
        exc = self._status_error(401, "invalid or expired refresh token")
        exit_code = render_client_error(err, exc)
        assert exit_code != 0
        assert "invalid or expired refresh token" in err.getvalue()
        assert "s3 login" in err.getvalue()

    def test_a_403_a_404_and_a_409_all_render_without_crashing(self) -> None:
        for status_code, detail in ((403, "you do not own this run"), (404, "no such run"), (409, "run has not finished")):
            err = io.StringIO()
            exc = self._status_error(status_code, detail)
            exit_code = render_client_error(err, exc)
            assert exit_code != 0
            assert detail in err.getvalue()

    def test_an_unparseable_or_unexpected_body_shape_never_crashes(self) -> None:
        err = io.StringIO()
        request = httpx.Request("POST", "http://test/v1/query")
        response = httpx.Response(500, content=b"not json at all", request=request)
        exc = httpx.HTTPStatusError("refused", request=request, response=response)
        exit_code = render_client_error(err, exc)
        assert exit_code != 0
        assert err.getvalue().strip() != ""

    def test_a_connection_level_failure_renders_an_actionable_message(self) -> None:
        err = io.StringIO()
        request = httpx.Request("POST", "http://test/v1/query")
        exc = httpx.ConnectError("connection refused", request=request)
        exit_code = render_client_error(err, exc)
        assert exit_code != 0
        assert "server" in err.getvalue().lower()


class TestMarkerFidelity:
    def test_token_text_is_printed_verbatim_never_renumbered(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)
        renderer.handle(_guard_passed())
        renderer.handle(TokenPayloadEventBuilder.token("first claim [3]. second claim [1]. "))
        renderer.handle(_event("citation", 2, _citation("c-a", 3)))
        renderer.handle(_event("citation", 3, _citation("c-b", 1)))
        renderer.handle(
            _event(
                "trust_signal", 4,
                TrustSignalPayload(
                    outcome="answer", risk_tier="low", grounded=True, triangulated=None,
                    citation_id=None, scope="answer",
                ),
            )
        )
        renderer.handle(
            _event("done", 5, DonePayload(total_cost_usd=0.0, total_tool_calls=1, elapsed_ms=1, trust_outcome="answer"))
        )
        rendered = out.getvalue()
        # Mutation: strip the server's own [n] markers and reinsert
        # sequential numbers client-side -> "first claim [3]" would become
        # "first claim [1]" (renumbered in arrival order).
        assert "first claim [3]" in rendered
        assert "second claim [1]" in rendered

    def test_an_unresolved_marker_is_reported_honestly_never_dropped_silently(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)
        renderer.handle(_guard_passed())
        # marker_ids references "c-missing", but no citation event for it
        # is ever sent -- the exact gap this rule exists to catch.
        renderer.handle(_event("token", 1, TokenPayload(text="a claim [9]. ", marker_ids=["c-missing"])))
        renderer.handle(
            _event(
                "trust_signal", 2,
                TrustSignalPayload(
                    outcome="flag", risk_tier="high", grounded=True, triangulated=False,
                    citation_id=None, scope="answer",
                ),
            )
        )
        renderer.handle(
            _event("done", 3, DonePayload(total_cost_usd=0.0, total_tool_calls=1, elapsed_ms=1, trust_outcome="flag"))
        )
        rendered = out.getvalue()
        assert "c-missing" in rendered
        assert "unresolved" in rendered.lower()


class TestNeverCostTwoLayers:
    def test_a_non_operator_renderer_prints_no_dollar_figure_from_any_event(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)

        renderer.handle(
            _event("cost", 0, CostPayload(query_cost_usd=9.99, query_cap_usd=10.0, cap_fraction=0.999, model_tier="synth"))
        )
        renderer.handle(
            _event("done", 1, DonePayload(total_cost_usd=9.99, total_tool_calls=1, elapsed_ms=100, trust_outcome="answer"))
        )
        renderer.finish()

        # Mutation: render done.total_cost_usd or the cost event
        # unconditionally instead of gating both on `operator` -> "9.99"
        # or "$" would appear.
        assert "9.99" not in out.getvalue()
        assert "$" not in out.getvalue()
        assert "9.99" not in err.getvalue()
        assert "$" not in err.getvalue()

    def test_an_operator_renderer_shows_cost_but_only_on_stderr_never_stdout(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=True)

        renderer.handle(
            _event("cost", 0, CostPayload(query_cost_usd=9.99, query_cap_usd=10.0, cap_fraction=0.999, model_tier="synth"))
        )
        renderer.handle(
            _event("done", 1, DonePayload(total_cost_usd=9.99, total_tool_calls=1, elapsed_ms=100, trust_outcome="answer"))
        )
        renderer.finish()

        assert "9.99" in err.getvalue()
        assert "$" not in out.getvalue()
        assert "9.99" not in out.getvalue()


class TestFinishDefault:
    def test_finish_defaults_to_failure_when_the_run_never_reached_a_terminal_event(self) -> None:
        """A run cut off before any guard rejection, fatal error, or
        `done` is not a run that finished cleanly; the safe default is
        failure, never success by omission."""
        out, err = io.StringIO(), io.StringIO()
        renderer = Renderer(out, err, operator=False)
        renderer.handle(_guard_passed())
        renderer.handle(TokenPayloadEventBuilder.token("partial answer, then nothing else arrives"))
        assert renderer.finish() != 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
