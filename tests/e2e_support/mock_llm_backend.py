"""T-1.2-07: a standalone process entrypoint that runs the real FastAPI app
with only the outbound LLM call faked, for Playwright's `webServer` to spawn
as the E2E suite's backend.

Depends on:
    - system_03_search_agent.adapters.web_sse.app (app): the real,
      unmodified FastAPI application. This module never edits app.py; it
      only extends the already-constructed `app` object at runtime (adds
      middleware, adds one debug-only route), the same way a test module
      monkeypatches an attribute on an already-imported module.
    - system_03_search_agent.harness.harness (litellm reference this
      module monkeypatches)
    - system_03_search_agent.core.run_registry (default_registry,
      RunNotFoundError): read-only, for the `/__e2e__/run_status`
      introspection route below.

Reads:
    - Environment: PORT (backend listen port, default 8931), everything
      listed in `_ENV_DEFAULTS` below (only set if not already present in
      the environment, so a caller can still override any of them).

Writes:
    - Nothing. This process holds no state beyond what `run_registry`
      already keeps in memory for the life of the process.

---------------------------------------------------------------------------
WHY THIS FILE EXISTS AT ALL (the in-process-monkeypatch problem)
---------------------------------------------------------------------------
Every other test in this repo that needs a fast, deterministic,
no-real-API-key model response uses `monkeypatch.setattr(harness_module
.litellm, "acompletion", mock_acompletion)` (see
`tests/system_03_search_agent/adapters/web_sse/test_streaming_endpoints.py`,
`_mock_litellm`). That works because pytest's `monkeypatch` mutates an
attribute on a module object living in the SAME Python process as the
test.

Playwright's `webServer` config spawns the backend as a genuinely separate
OS process (a real `uvicorn` server a real browser makes real HTTP
requests to). `monkeypatch` cannot reach into a different process; there is
no fixture or mechanism that would let a Playwright test file mutate an
attribute inside the backend process from outside it. Starting the real
backend via `uvicorn system_03_search_agent.adapters.web_sse.app:app` with
no further changes would mean every query tries to call a real LLM
provider: it would fail with no real API key configured (and none should
ever be configured for a test run, per `ai-security-standards.md`), or
worse, silently reach a real provider if a stray key were ever present in
the environment.

The fix applies the identical monkeypatch technique, just once, at process
start, before any request can reach the harness: this module imports
`harness_module.litellm` (the real module, exactly as the app's own code
does) and reassigns its `acompletion`/`get_model_info` attributes to the
fakes below, then starts `uvicorn.run(app, ...)`. Every route, every piece
of real wiring (auth, the run registry, SSE streaming, cost-cap
enforcement, the LangGraph loop itself), stays completely real. Only the
one network call that would otherwise leave this machine is faked.

---------------------------------------------------------------------------
WHY PER_QUERY_COST_CAP_USD IS SET TO 0.02, NOT A GENEROUS VALUE
---------------------------------------------------------------------------
This is the least obvious design choice in this file, so it is spelled out
in full rather than left to be reverse-engineered from a magic number.

As of this build phase (2.0), `core/graph.py`'s `write_node` only ever
emits a `token` event on ONE code path: the per-query cap-exceeded partial
result (`_partial_result_for_cap`, which emits
`cost_control.PER_QUERY_CAP_PARTIAL_RESULT_NOTE` as a single token). The
normal, cap-not-exceeded success path emits `cost` then `done` and NO
`token` event at all (real citation-grounded synthesis, which would turn a
model's answer into `token` events, is phase 2.2's job; see
`write_node`'s own "Stub only" comment). This means this ticket's
acceptance criterion "observes the answer stream render tokens" cannot be
satisfied by a normal successful run in this build phase: there is
genuinely no other code path that produces one yet. Fabricating a `token`
event at the test layer (a fixture, or a hand-built SSE frame) would
violate `ai-security-standards.md`'s "treat AI output as untrusted" spirit
in reverse: it would test the frontend against events the real backend can
never actually produce today, which is a worse kind of dishonesty than a
test that exercises a real, if less obvious, code path.

So this suite deliberately drives the ONE real code path that does emit a
token: the per-query cap-exceeded branch. `PER_QUERY_COST_CAP_USD=0.02` is
chosen precisely so that a normal query passes guard, think, and plan (so
the pipeline stepper genuinely progresses through all three core steps),
and ONLY the write step's own pre-flight cap check trips, exactly the
"discovered only at Write" case `write_node`'s docstring names.

The arithmetic behind 0.02, using this file's own fixed mocked response
(`prompt_tokens=10, completion_tokens=5`, `get_model_info` returning
input/output cost of 1e-6/2e-6 per token, mirroring
`test_streaming_endpoints.py`'s `_fake_response`/`_mock_litellm` exactly so
this backend's real, metered cost tracking matches what that test suite
already establishes as correct):

    - Real metered cost per call: 10 * 1e-6 + 5 * 2e-6 = 0.00002 USD.
    - `cost_control.check_per_query_cap` compares a PROJECTED cost
      (accumulated-so-far PLUS a fixed, conservative per-tier ESTIMATE,
      not the real metered cost) against the cap, before every call:
        - guard's own check: projected = 0 + estimate(guard, 600 tok *
          5e-6 = 0.003) = 0.003 <= 0.02 -> passes, guard's real call runs,
          accumulated becomes 0.00002.
        - think's own check (tier="guard" too): projected = 0.00002 +
          0.003 = 0.00302 <= 0.02 -> passes, accumulated becomes 0.00004.
        - plan's own check (tier="plan", 2500 tok * 5e-6 = 0.0125):
          projected = 0.00004 + 0.0125 = 0.01254 <= 0.02 -> passes,
          accumulated becomes 0.00006.
        - write's own check (tier="synth", 5000 tok * 5e-6 = 0.025):
          projected = 0.00006 + 0.025 = 0.02506 > 0.02 -> TRIPS. write_node
          catches `QueryCapExceededError` and calls
          `_partial_result_for_cap`, which emits a real `token` event
          (`PER_QUERY_CAP_PARTIAL_RESULT_NOTE`) and a real `done` event
          (`trust_outcome="flag"`).

The per-tier estimate constants (`_TYPICAL_TOKEN_PROFILE`,
`_CONSERVATIVE_PRICE_PER_TOKEN_USD`) live in
`system_03_search_agent/harness/cost_control.py` and are read directly from
that module's source for this calculation, not guessed or reverse-engineered
from observed behavior.

Net effect: every query this backend serves reaches guard done, think
done, plan done (full pipeline-stepper progression through every core
step this build phase has), then a real cap-exceeded token plus a real
terminal done event. This is deterministic (the same fixed mocked
response every time) and fast (no artificial delay unless a query's own
text asks for one, see `_SLOW_QUERY_MARKER` below), and it is a real
backend code path, not a fabricated event sequence.

---------------------------------------------------------------------------
WHY THE STOP TEST NEEDS AN ARTIFICIAL DELAY, GATED BY QUERY TEXT
---------------------------------------------------------------------------
With the fixed mocked response above and no delay, a full run (four model
calls, each answered instantly) completes in well under 100ms end to end,
too fast for Playwright to reliably click "Stop" mid-stream. Rather than a
global delay (which would slow down the full-flow test for no reason), the
fake `acompletion` below inspects the outgoing messages for a fixed marker
string (`_SLOW_QUERY_MARKER`) and only sleeps `_SLOW_QUERY_DELAY_S` seconds
per call when a query's own text contains it. The stop-button spec test
opts into this by including the marker in its query text; the full-flow
spec test does not, and stays fast.

---------------------------------------------------------------------------
WHY A CORS MIDDLEWARE IS ADDED HERE, NOT IN app.py
---------------------------------------------------------------------------
This ticket's E2E suite runs the frontend (Vite dev server) and the
backend (this script) as two separate processes on two different local
ports, exactly what real browser-driven E2E testing needs. `app.py` (T-1.2-02,
merged, out of this ticket's file-edit scope) carries no CORS middleware, and
`lib/api.ts`'s `DEFAULT_BASE_URL` defaults to same-origin ("", no
`VITE_API_BASE_URL` set). Two options were available: (a) point the frontend
at the backend's absolute URL via `VITE_API_BASE_URL` and add CORS handling
somewhere, or (b) add a Vite dev-server proxy so the browser only ever talks
to one origin. (b) was rejected: `fetch`-based SSE consumption
(`hooks/useAgentRun.ts`) reads `response.body` as a live `ReadableStream`,
and routing that through Vite's dev-server HTTP proxy is an unverified,
harder-to-reason-about streaming path with a real risk of buffering an SSE
response instead of forwarding it chunk by chunk. (a) is simpler and
verifiable: this module extends the already-constructed, real `app` object
with `CORSMiddleware` (the same "extend the live object, never edit the
file" technique the litellm monkeypatch above uses), scoped to loopback
origins only (`http://localhost:<any port>`, `http://127.0.0.1:<any port>`),
since this process only ever serves a local Vite dev server, never a real
deployment. Judgment call, logged in DECISIONS.md.

---------------------------------------------------------------------------
WHY A `/__e2e__/run_status` ROUTE IS ADDED HERE
---------------------------------------------------------------------------
T-1.2-06 explicitly deferred its own acceptance criterion 5 to this ticket
with this exact wording: "proves stopping a real, running query actually
halts the server-side loop, not just the client-side UI state." A pure
browser-level check cannot prove that on its own: once the frontend's
`AbortController.abort()` runs (`StopButton.tsx`'s `handleClick`, via
`useAgentRun`'s `stop()`), the BROWSER stops reading the stream
unconditionally, whether or not the SERVER'S background task actually got
cancelled. Asserting "no more events arrived in the browser after I
clicked stop" is true by construction the moment the client stops
listening; it does not distinguish a genuine server-side halt from a
server that is still happily running in the background while nobody is
listening. That gap is exactly what T-1.2-06 flagged as unproven.

The one existing, already-trusted way to prove a genuine server-side halt
is `run_registry.RunEntry.task.cancelled()`, the same assertion
`test_streaming_endpoints.py`'s
`TestStopEndpoint::test_stops_a_still_running_run_and_returns_200` already
uses at the Python level. This route exposes exactly that one boolean pair
(`task_done`, `task_cancelled`) for a given `run_id`, read-only, so the
Playwright spec can poll it (via Playwright's own `request` fixture, an
independent Node-side HTTP client that never goes through the browser's
`AbortController` and so is never itself affected by the client-side stop)
after clicking Stop in the browser, and get a real, out-of-band answer to
"did the server's background task actually get cancelled." No
authentication on this route: it is bound to `127.0.0.1` only (never
`0.0.0.0`), added only by this E2E-only script, and never reachable outside
this one throwaway test process. Judgment call, logged in DECISIONS.md.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Make `src/` importable before anything under `system_03_search_agent` is
# imported. This project's package lives under `src/` with no `package-dir`
# mapping in pyproject.toml; pytest finds it only because
# `[tool.pytest.ini_options]` sets `pythonpath = ["src"]`. A bare `python -m`
# invocation gets no such help, so this script does the same thing by hand,
# rather than relying on a caller to export PYTHONPATH correctly.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ---------------------------------------------------------------------------
# Env defaults. Mirrors test_streaming_endpoints.py's `_harness_env`/
# `_auth_secret` fixtures exactly (same variable names, same values) so this
# backend's cost accounting and auth behavior match what that already-passing
# test suite establishes as correct. Uses setdefault, never a blind
# overwrite, so an operator running this script with real env overrides
# (e.g. a different USER_DB_URL) is respected.
#
# Applied inside `main()`, not at module import time: this file lives under
# `tests/` with an `__init__.py`, so it is importable by name. A future test
# that imports this module for any reason (even just to reuse a helper)
# would otherwise silently set AUTH_SECRET, PER_QUERY_COST_CAP_USD, and
# USER_DB_URL for the rest of that pytest process as a side effect of the
# import alone. Nothing imports this module today (only `playwright.config
# .ts` invokes it via `python3 -m`), but a bare import should never be able
# to mutate global process state regardless.
# ---------------------------------------------------------------------------
_TEST_AUTH_SECRET = "e2e-only-auth-secret-do-not-reuse-outside-playwright-webserver"

_ENV_DEFAULTS = {
    "GUARD_MODEL": "test-provider/guard-model",
    "PLAN_MODEL": "test-provider/plan-model",
    "SYNTH_MODEL": "test-provider/synth-model",
    # See this module's docstring for the full arithmetic behind 0.02: it
    # is chosen so guard/think/plan all pass their own pre-flight cap
    # check and only write's own check trips, which is the one code path
    # in this build phase that emits a real `token` event.
    "PER_QUERY_COST_CAP_USD": "0.02",
    "PER_USER_DAILY_QUERY_CAP": "1000",
    "SYSTEM_DAILY_CAP_USD": "1000000",
    # T-4.16-02. Its ABSENCE meant the entire guest path was unexercisable
    # in the browser suite, and had been since build phase 4.10 built it.
    #
    # `cost_control.anon_daily_run_cap` reads this through `_read_int_env`,
    # which RAISES `RuntimeError` when it is unset rather than defaulting.
    # So every anonymous `POST /v1/query` against this backend 500'd, the
    # connection reset, and the browser reported `net::ERR_FAILED` with no
    # CORS headers on the response, which reads like a CORS or networking
    # problem and is neither. Guest coverage was not failing, it was
    # missing: no spec had ever asked a question without signing up first,
    # which is exactly how the deployed demo is actually used.
    #
    # This is the same unset variable build phase 4.12 hit in production
    # (its defect 3), fixed there and not here, because nothing local was
    # exercising the path that needs it. 1000, matching the other caps
    # above rather than `env.example`'s production 200, since a suite must
    # never fail for having asked too many questions in a day.
    "ANON_DAILY_RUN_CAP": "1000",
    "AUTH_SECRET": _TEST_AUTH_SECRET,
    "USER_DB_URL": "postgresql://localhost:5432/search_agent_users",
}


def _apply_env_defaults() -> None:
    for key, value in _ENV_DEFAULTS.items():
        os.environ.setdefault(key, value)


# A query's own text opts into an artificial per-call delay by containing
# this marker (see this module's docstring). Never a global delay: only the
# stop-button spec test's query text carries it.
_SLOW_QUERY_MARKER = "E2E_SLOW_STOP_TEST"
_SLOW_QUERY_DELAY_S = 2.0


def _can_connect_to_user_db() -> bool:
    import sqlalchemy as sa

    try:
        probe_engine = sa.create_engine(os.environ["USER_DB_URL"])
        with probe_engine.connect():
            pass
        probe_engine.dispose()
        return True
    except Exception:  # noqa: BLE001 - a reachability probe must catch any failure mode
        return False


def _fake_response(content: str = "ok") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


# Section 10.4's classification schema, exactly as `guardrail/classifier.py`
# validates it. FOUR required fields, not three: `is_injection` and
# `is_off_topic` (both StrictBool, so "true" as a string is rejected),
# `confidence` (float, 0.0 to 1.0 inclusive) and `reason` (str, max 200).
# `extra="forbid"`, so an added field is rejected too.
#
# The count matters. An earlier version of this comment said "only
# is_injection, is_off_topic and reason" while the literal below correctly
# carried `confidence`, so a maintainer trusting the comment and removing it
# would break every run through this backend. That is the F-2.1-J5-01 pattern
# `classifier.py` itself warns about: a confident comment is exactly where the
# next reader stops checking.
_GUARD_ADMIT_JSON = (
    '{"is_injection": false, "is_off_topic": false, '
    '"confidence": 0.99, "reason": "ok"}'
)


def _looks_like_guard_call(blob: str) -> bool:
    """Whether this call is the guardrail's own classification request.

    Matched on the classifier's prompt markers rather than on a tier name,
    because this helper replaces `litellm.acompletion` and never sees which
    tier the harness resolved.
    """
    lowered = blob.lower()
    return "is_injection" in lowered or "is_off_topic" in lowered


async def _fake_acompletion(*_args: object, **kwargs: object):
    """Replaces `litellm.acompletion` for the life of this process. Never
    reaches a real model provider: the only "network" activity here is the
    marker-gated `asyncio.sleep` used to make the stop-button test's run
    genuinely still in flight when Playwright clicks Stop.

    TIER-AWARE SINCE BUILD PHASE 4.8, and the reason is worth recording.

    This returned the bare string "ok" for every call, which was correct when
    written: build phase 1.2's `guardrail_node` made a throwaway Guard-tier
    call and discarded the response. Build phase 3.0 replaced that stub with a
    real classifier that parses the response as JSON against a strict schema,
    and this mock was never updated, so every run through this backend has died
    at the guard step with "the guard tier did not return valid JSON" ever
    since.

    Nobody noticed for five phases because the Playwright suite could not start
    at all: its webServer probe waited on 127.0.0.1 while Vite bound to [::1],
    carried as "a pre-existing environment quirk" until build phase 4.8
    diagnosed it. Fixing that unmasked this.

    The lesson worth keeping: a test double is a contract with the code it
    stands in for, and changing that contract without updating the double
    leaves a suite that cannot pass. A suite that cannot RUN hides it.
    """
    messages = kwargs.get("messages", [])
    blob = " ".join(
        str(message.get("content", ""))
        for message in messages  # type: ignore[union-attr]
        if isinstance(message, dict)
    )
    if _SLOW_QUERY_MARKER in blob:
        await asyncio.sleep(_SLOW_QUERY_DELAY_S)
    if _looks_like_guard_call(blob):
        return _fake_response(_GUARD_ADMIT_JSON)
    return _fake_response()


def _fake_get_model_info(model: str) -> dict[str, float]:
    return {"input_cost_per_token": 1e-6, "output_cost_per_token": 2e-6}


def _patch_litellm() -> None:
    from system_03_search_agent.harness import harness as harness_module

    harness_module.litellm.acompletion = _fake_acompletion
    harness_module.litellm.get_model_info = _fake_get_model_info


def _build_app():
    from fastapi.middleware.cors import CORSMiddleware

    from system_03_search_agent.adapters.web_sse.app import app
    from system_03_search_agent.core.run_registry import RunNotFoundError, default_registry

    # See this module's docstring, "WHY A CORS MIDDLEWARE IS ADDED HERE".
    # Loopback only: this process never serves anything but a local Vite
    # dev server spawned by the same Playwright run.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # See this module's docstring, "WHY A `/__e2e__/run_status` ROUTE IS
    # ADDED HERE". Read-only, no side effects, exposes only the same two
    # booleans test_streaming_endpoints.py already asserts on directly.
    @app.get("/__e2e__/run_status/{run_id}")
    async def _e2e_run_status(run_id: str) -> dict[str, bool]:
        try:
            entry = default_registry.get_run(run_id)
        except RunNotFoundError:
            return {"found": False, "task_done": False, "task_cancelled": False}
        return {
            "found": True,
            "task_done": entry.task.done(),
            "task_cancelled": entry.task.cancelled(),
        }

    return app


def main() -> None:
    _apply_env_defaults()
    backend_port = int(os.environ.get("PORT", "8931"))

    if not _can_connect_to_user_db():
        print(
            "mock_llm_backend: search_agent_users PostgreSQL database is not "
            "reachable at USER_DB_URL="
            f"{os.environ['USER_DB_URL']!r}. Start PostgreSQL and ensure this "
            "database exists (see README.md's Quick start) before running the "
            "E2E suite.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    _patch_litellm()
    app = _build_app()

    import uvicorn

    # 127.0.0.1 only, never 0.0.0.0: this process is throwaway test
    # infrastructure for one local Playwright run, not a deployment.
    uvicorn.run(app, host="127.0.0.1", port=backend_port, log_level="warning")


if __name__ == "__main__":
    main()
